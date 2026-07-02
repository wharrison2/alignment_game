"""Multiplayer (Kahoot-style) session layer — MULTIPLAYER_DESIGN.md.

One MultiplayerGame = one shared GameState + GameEngine + N human seats joined
by lobby code. This module owns:

  - the lobby (join / creator settings / start),
  - the turn BARRIER: a step runs only when every human seat has submitted,
    or the optional per-turn timer expires (lazy enforcement — checked on
    every poll and submit, no background thread, design §4.5),
  - seat admin: kick, replace-with-AI, auto-pass (design decision #4),
  - the per-seat payloads (state, lobby metadata, post-mortem + leaderboard).

Firewall posture (CLAUDE.md §2, MULTIPLAYER_DESIGN §6): every payload built
here is (a) the calling seat's OWN observation from the engine's chokepoint,
(b) hand-built lobby METADATA — names/tickers/booleans, structurally unable to
carry model stats or staged actions — or (c) the post-mortem, gated on the
shared game being over. No truth route exists for multiplayer. Authorization
is by seat token (an HttpOnly cookie, resolved in server.py), never by
anything in a request body; kicking a seat revokes its token.

Threading mirrors server.py: `_registry_lock` guards only the registry dicts;
`MultiplayerGame.lock` serializes all work on one game. The two are NEVER held
at the same time (no nesting), so there is no lock-order to get wrong.
"""
import secrets
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass

from backend_v1.engine.game import (
    new_multiplayer_game, GameEngine, sanitize_lab_name, sanitize_ticker,
)
from backend_v1.engine.lab import Disposition
from backend_v1.engine.actions import (
    Action, ActionError, validate_action, trim_action_to_budget,
)
from backend_v1.engine.controllers.rival_controller import RivalController
from backend_v1.engine.observation.observation_builder import build_observation
from backend_v1.engine.postmortem import build_postmortem
from backend_v1.engine.rng import Rng
from backend_v1.server.payloads import base_state_payload
from backend_v1.content.copy import t


# ── Multiplayer bounds (INVENTED — see ISSUES.md "Multiplayer", [TUNE]) ────────
# The lobby code is a real join credential (design §6, A6): 31 unambiguous
# characters (no 0/O/1/I/L) to the 6th power ≈ 8.9e8 codes against ≤100 live
# games — unguessable in practice even without rate limiting.
LOBBY_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
LOBBY_CODE_LENGTH = 6

# Seats per game and live games held in memory (LRU-evicted like server.py's
# session registry; a multiplayer game is the same ~320 KB engine state).
MAX_SEATS = 6
MAX_MULTIPLAYER_GAMES = 100

# Creator-tunable AI rival count. Default 2 (not solo's RIVAL_COUNT=4): human
# opponents already fill the world, the AI rivals are garnish. [TUNE]
MAX_MP_RIVALS = 5
DEFAULT_MP_RIVAL_COUNT = 2

# Optional per-turn timer clamp (wall-clock seconds — UI/session config, NOT
# game-time; deliberately not in constants.py per CLAUDE.md §0.5 / design §7).
TURN_SECONDS_MIN = 15
TURN_SECONDS_MAX = 600

# A seat is shown "disconnected" when it hasn't polled for this long (clients
# poll every ~1-2 s). Presentation only — nothing auto-resolves on it; the
# game master decides (design decision #4).
DISCONNECT_AFTER_SECONDS = 10.0

# Disposition given to a lab when its human is replaced by AI: mid-recklessness,
# no cost advantage or ideology; governance weights derived exactly as
# new_game derives them for rivals. [TUNE]
TAKEOVER_RECKLESSNESS = 0.5


def _takeover_disposition() -> Disposition:
    """The Disposition a replace-with-AI takeover plays with. Human labs carry
    the default (all-cautious) Disposition, which would make the AI play dead —
    give it the same recklessness-derived weights a rival gets in new_game."""
    recklessness = TAKEOVER_RECKLESSNESS
    regulation_stance = min(0.95, 0.3 + 0.6 * recklessness)
    safety_priority = max(0.05, 0.5 * (1.0 - recklessness))
    return Disposition(recklessness=recklessness,
                       regulation_stance=regulation_stance,
                       safety_priority=safety_priority)


@dataclass
class Seat:
    """One human's place in a MultiplayerGame.

    `token` is the credential (cookie value); revoked (set to None and dropped
    from the registry) when the seat is kicked. `staged_action` is PRIVATE to
    this seat (design §6, L5) — it must never be serialized into any payload."""
    token: str | None
    seat_id: int                    # stable id; the only seat handle in admin bodies
    display_name: str               # sanitized on join (design §6, A8)
    ticker: str
    is_creator: bool
    lab_id: str | None = None       # assigned at start(): "player{n}"
    control: str = "human"          # "human" | "ai" | "auto_pass"
    last_seen: float = 0.0          # monotonic; drives the "connected" dot only
    staged_action: Action | None = None
    has_submitted: bool = False


class MultiplayerGame:
    """One shared world + its seats. All methods assume the caller holds
    self.lock (the server layer takes it per request, like Session.lock)."""

    def __init__(self, code, now_fn=time.monotonic):
        self.code = code
        self.lock = threading.Lock()
        self.seats = []
        self.rival_count = DEFAULT_MP_RIVAL_COUNT
        self.turn_seconds = None          # None = no timer: barrier waits for all
        self.started = False
        self.state = None                 # set by start()
        self.engine = None
        self.rival_ctrl = None
        self.observations = None          # per-lab observations from the last step
        self.turn_deadline = None         # monotonic instant, or None
        self.last_access = now_fn()
        self._next_seat_id = 0
        # Turn-0 observations memoized per lab so poll frequency can never
        # touch the RNG (build_observation may draw on rival-estimate misses).
        self._turn_zero_observations = {}
        # Post-mortems memoized per lab (same anti-amplification reasoning as
        # Session._postmortem_cache).
        self._postmortem_cache = {}
        self._now = now_fn                # injectable clock for headless tests

    # ── lobby phase ───────────────────────────────────────────────────────────

    def add_seat(self, raw_name, raw_ticker, is_creator=False):
        """Sanitize the human-authored identity and seat it. Caller checks
        joinability (started/full) first; the registry stores the token."""
        # Reuse the engine's sanitizers so a seat's name/ticker are bounded and
        # control-char-free before they ever render in ANOTHER player's DOM
        # (stored-XSS surface, design §6 A8; frontend esc() is the second layer).
        safe_name = sanitize_lab_name(raw_name)
        safe_ticker = sanitize_ticker(raw_ticker, safe_name)
        seat = Seat(token=secrets.token_urlsafe(32),
                    seat_id=self._next_seat_id,
                    display_name=safe_name, ticker=safe_ticker,
                    is_creator=is_creator, last_seen=self._now())
        self._next_seat_id += 1
        self.seats.append(seat)
        return seat

    def is_joinable(self):
        return not self.started and len(self.seats) < MAX_SEATS

    def set_settings(self, rival_count=None, turn_seconds=None):
        """Creator-only lobby settings, clamped. turn_seconds None/0 = no timer."""
        if self.started:
            return {"errors": ["settings are locked once the game starts"]}
        if rival_count is not None:
            self.rival_count = max(0, min(MAX_MP_RIVALS, int(rival_count)))
        if turn_seconds is not None:
            if not turn_seconds:            # null / 0 → timer off
                self.turn_seconds = None
            else:
                self.turn_seconds = max(TURN_SECONDS_MIN,
                                        min(TURN_SECONDS_MAX, int(turn_seconds)))
        return {"ok": True}

    def start(self, seed, max_turns):
        """Build the shared world from the seated humans + settings. The seed
        is server-random (multiplayer games are not replayable — design §7)."""
        if self.started:
            return {"errors": ["game already started"]}
        human_identities = [(seat.display_name, seat.ticker)
                            for seat in self.seats]
        self.state = new_multiplayer_game(
            seed=seed, human_identities=human_identities,
            rival_count=self.rival_count, max_turns=max_turns)
        # Human labs are player1..playerN in seat order (new_multiplayer_game).
        for seat, lab in zip(self.seats, self.state.labs):
            seat.lab_id = lab.id
        self.engine = GameEngine()
        self.rival_ctrl = RivalController(Rng(seed + 1))
        self.started = True
        self._stamp_deadline()
        return {"ok": True}

    def lobby_payload(self, viewing_seat):
        """Lobby/roster metadata ONLY (design §6, L4): hand-built from Seat
        scalar fields, structurally unable to carry game state or staged
        actions. Safe to poll before and during the game."""
        return {
            "code": self.code,
            "started": self.started,
            "game_over": bool(self.state.game_over) if self.started else False,
            "rival_count": self.rival_count,
            "turn_seconds": self.turn_seconds,
            "max_seats": MAX_SEATS,
            "seats": [self._seat_status(seat, viewing_seat)
                      for seat in self.seats],
        }

    def _seat_status(self, seat, viewing_seat):
        return {
            "seat_id": seat.seat_id,
            "name": seat.display_name,
            "ticker": seat.ticker,
            "lab_id": seat.lab_id,       # public, same as lab_names keys
            "is_creator": seat.is_creator,
            "connected": self._is_connected(seat),
            "submitted": seat.has_submitted,
            "control": seat.control,
            "is_you": seat is viewing_seat,
        }

    def _is_connected(self, seat):
        if seat.control != "human":
            return False
        return (self._now() - seat.last_seen) < DISCONNECT_AFTER_SECONDS

    # ── the turn barrier ──────────────────────────────────────────────────────

    def stage_seat(self, seat, action_dict):
        """Store the seat's current queue WITHOUT submitting (decision #2: the
        timer submits "what's staged", so the server must hold a copy). Not
        validated here — trim_action_to_budget absorbs staleness at the
        deadline."""
        try:
            seat.staged_action = Action.from_dict(action_dict)
        except (ActionError, TypeError, ValueError) as e:
            return {"errors": [str(e)]}
        return {"staged": True}

    def submit_seat(self, seat, action_dict):
        """Validate and submit this seat's action; resolve the turn if it was
        the last human in. Returns this seat's state payload (which reflects
        either the new turn or the still-waiting barrier)."""
        self.check_deadline()
        if self.state.game_over:
            return {"errors": [t("api.game_over")]}
        try:
            action = Action.from_dict(action_dict)
        except (ActionError, TypeError, ValueError) as e:
            return {"errors": [str(e)]}
        lab = self._lab_for(seat)
        problems = validate_action(action, lab, self.state.world,
                                   self.state.consts, self.state.dt)
        if problems:
            return {"errors": problems}
        seat.staged_action = action
        seat.has_submitted = True
        self._maybe_resolve()
        return self.state_payload_for(seat)

    def check_deadline(self):
        """Lazy timer enforcement (design §4.5): called on every poll and
        submit; past the deadline the turn resolves with staged (trimmed)
        actions for non-submitters. No timer → no deadline → barrier waits."""
        if not self.started or self.state.game_over:
            return
        if self.turn_deadline is None:
            return
        if self._now() >= self.turn_deadline:
            self._resolve_turn()

    def _human_seats(self):
        return [seat for seat in self.seats if seat.control == "human"]

    def _maybe_resolve(self):
        """The barrier: step once every human-controlled seat has submitted.
        AI-takeover / auto-pass seats don't hold the barrier."""
        human_seats = self._human_seats()
        all_submitted = all(seat.has_submitted for seat in human_seats)
        if all_submitted:
            self._resolve_turn()

    def _resolve_turn(self):
        """One engine step for everyone. Human seats play their staged action
        (budget-trimmed if the timer forced them); AI-takeover seats and the
        actual rival labs are decided by the rival controller on THEIR OWN
        last observation (no godmode — same as Session.submit)."""
        if not self.started or self.state.game_over:
            return
        is_first_turn = self.observations is None
        actions = {}
        for seat in self.seats:
            lab = self._lab_for(seat)
            if seat.control == "human":
                staged = seat.staged_action if seat.staged_action is not None else Action()
                if not seat.has_submitted:
                    # forced resolution: never reject, trim to fit (design §4.4)
                    staged = trim_action_to_budget(
                        staged, lab, self.state.world,
                        self.state.consts, self.state.dt)
                actions[seat.lab_id] = staged
            elif seat.control == "ai":
                actions[seat.lab_id] = self._ai_decision(lab, is_first_turn)
            else:   # auto_pass
                actions[seat.lab_id] = Action()
        for lab in self.state.labs:
            if lab.is_player:
                continue    # every human lab is covered by a seat above
            actions[lab.id] = self._ai_decision(lab, is_first_turn)

        self.state, self.observations = self.engine.step(self.state, actions)
        for seat in self.seats:
            seat.staged_action = None
            seat.has_submitted = False
        if self.state.game_over:
            self.turn_deadline = None
        else:
            self._stamp_deadline()

    def _ai_decision(self, lab, is_first_turn):
        if is_first_turn:
            return Action()   # no observations exist before the first step
        return self.rival_ctrl.decide(self.observations[lab.id], lab.disposition)

    def _stamp_deadline(self):
        if self.turn_seconds is None:
            self.turn_deadline = None
        else:
            self.turn_deadline = self._now() + self.turn_seconds

    def _lab_for(self, seat):
        return next(lab for lab in self.state.labs if lab.id == seat.lab_id)

    # ── per-seat payloads ─────────────────────────────────────────────────────

    def state_payload_for(self, seat):
        """This seat's OWN observation (design §6, L2) + public maps + the
        barrier status. Never another seat's observation, never raw state,
        never anyone's staged action (L5)."""
        self.check_deadline()
        payload = base_state_payload(self._observation_for(seat),
                                     self.engine, self.state)
        payload["mp"] = self._mp_status_for(seat)
        return payload

    def _observation_for(self, seat):
        if self.observations is not None:
            return self.observations[seat.lab_id]
        # turn 0: no step has run yet — build (and memoize) a fresh filtered view
        if seat.lab_id not in self._turn_zero_observations:
            lab = self._lab_for(seat)
            self._turn_zero_observations[seat.lab_id] = build_observation(
                self.state, lab, [], [], [], [])
        return self._turn_zero_observations[seat.lab_id]

    def _mp_status_for(self, seat):
        human_seats = self._human_seats()
        submitted_count = sum(1 for s in human_seats if s.has_submitted)
        deadline_seconds_left = None
        if self.turn_deadline is not None and not self.state.game_over:
            deadline_seconds_left = round(
                max(0.0, self.turn_deadline - self._now()), 1)
        return {
            "code": self.code,
            "turn": self.state.turn,
            "game_over": self.state.game_over,
            "you": {"seat_id": seat.seat_id, "lab_id": seat.lab_id,
                    "is_creator": seat.is_creator, "control": seat.control,
                    "submitted": seat.has_submitted},
            "barrier": {"submitted": submitted_count,
                        "total": len(human_seats),
                        "seats": [self._seat_status(s, seat)
                                  for s in self.seats]},
            "turn_seconds": self.turn_seconds,
            "deadline_seconds_left": deadline_seconds_left,
        }

    # ── admin (creator only — asserted at the route layer, design §6 A2) ──────

    def kick(self, target_seat_id, resolution="auto_pass"):
        """Remove a seat. In the lobby the seat disappears; in-game the lab
        stays and only who decides changes (replace-with-AI or auto-pass,
        decision #4). Returns (result_dict, revoked_token_or_None) — the
        registry drops the token so the kicked player's next request 401s
        (design §6, A4)."""
        target = next((s for s in self.seats if s.seat_id == target_seat_id),
                      None)
        if target is None:
            return {"errors": ["no such seat"]}, None
        if target.is_creator:
            return {"errors": ["the game creator can't be removed"]}, None
        revoked_token = target.token
        target.token = None
        if not self.started:
            self.seats.remove(target)
            return {"ok": True}, revoked_token
        if resolution == "ai":
            target.control = "ai"
            # The lab keeps is_player=True (still buyout-immune and
            # explicit-defection — see ISSUES.md); only the controller changes.
            self._lab_for(target).disposition = _takeover_disposition()
        else:
            target.control = "auto_pass"
        target.staged_action = None
        target.has_submitted = False
        # removing a human from the barrier set may complete it
        self._maybe_resolve()
        return {"ok": True}, revoked_token

    # ── post-game ─────────────────────────────────────────────────────────────

    def postmortem_for(self, seat):
        """This seat's post-mortem + the shared leaderboard. Gated on the
        SHARED game being over (design §6, L6): it reveals every lab's TRUE
        trajectory, which is the intended post-game payoff (design §3) but
        must never leak mid-game. resim=False — multiplayer games are not
        replayable (human timing), so counterfactual re-simulation is off."""
        if not self.started or not self.state.game_over:
            return {"errors": [t("api.game_not_over")]}
        if seat.lab_id not in self._postmortem_cache:
            postmortem = build_postmortem(self.engine.logger, self.state,
                                          seat.lab_id, resim=False)
            postmortem["outcome"] = self.state.outcome_by_lab.get(
                seat.lab_id, self.state.outcome)
            postmortem["leaderboard"] = self._leaderboard()
            self._postmortem_cache[seat.lab_id] = postmortem
        return self._postmortem_cache[seat.lab_id]

    def _leaderboard(self):
        """Final ranking of ALL labs: the winner (if any) pinned first, then
        market cap descending (invented rule — see ISSUES.md). Post-game only."""
        entries = []
        for lab in self.state.labs:
            lab_outcome = self.state.outcome_by_lab.get(lab.id)
            entries.append({
                "lab_id": lab.id, "name": lab.name, "ticker": lab.ticker,
                "is_human": lab.is_player,
                "market_cap": round(lab.market_cap, 1),
                "net_impact": round(lab.impact_ledger, 1),
                "result": lab_outcome["result"] if lab_outcome else None,
            })
        entries.sort(key=lambda e: (0 if e["result"] == "WIN" else 1,
                                    -e["market_cap"]))
        return entries


# ── Registry ───────────────────────────────────────────────────────────────────
# code -> MultiplayerGame (LRU, like server._sessions) + token -> (game, seat).
# _registry_lock guards ONLY these dicts and is never held together with a
# game's lock (see module docstring).
_games = OrderedDict()
_seats_by_token = {}
_registry_lock = threading.Lock()


def _fresh_code_locked():
    """A lobby code no live game holds. Caller holds _registry_lock."""
    while True:
        code = "".join(secrets.choice(LOBBY_CODE_ALPHABET)
                       for _ in range(LOBBY_CODE_LENGTH))
        if code not in _games:
            return code


def create_game(raw_name, raw_ticker, now_fn=time.monotonic):
    """New lobby with its creator seated. Returns (token, game, seat). The
    game is fully built before it is published to the registry, so no other
    thread can see it half-constructed."""
    unpublished_game = None
    with _registry_lock:
        code = _fresh_code_locked()
        unpublished_game = MultiplayerGame(code, now_fn=now_fn)
        creator_seat = unpublished_game.add_seat(raw_name, raw_ticker,
                                                 is_creator=True)
        _games[code] = unpublished_game
        _games.move_to_end(code)
        _seats_by_token[creator_seat.token] = (unpublished_game, creator_seat)
        while len(_games) > MAX_MULTIPLAYER_GAMES:
            _evicted_code, evicted_game = _games.popitem(last=False)
            _drop_game_tokens_locked(evicted_game)
    return creator_seat.token, unpublished_game, creator_seat


def _drop_game_tokens_locked(game):
    """Revoke every seat token of an evicted game so stale cookies 401 instead
    of resolving to a dead game. Caller holds _registry_lock."""
    for seat in game.seats:
        if seat.token is not None:
            _seats_by_token.pop(seat.token, None)


def join_game(code, raw_name, raw_ticker):
    """Seat a joiner in the lobby `code` names. Returns (token, game, seat) on
    success or (None, None, error_payload). Join is the ONE call where the code
    arrives in the body — every later request authorizes by token (§6, A1)."""
    normalized_code = str(code or "").strip().upper()
    with _registry_lock:
        game = _games.get(normalized_code)
        if game is not None:
            _games.move_to_end(normalized_code)
    if game is None:
        return None, None, {"errors": ["no game with that code"], "status": 404}
    with game.lock:
        if game.started:
            return None, None, {"errors": ["that game has already started"],
                                "status": 409}
        if len(game.seats) >= MAX_SEATS:
            return None, None, {"errors": ["that game is full"], "status": 409}
        seat = game.add_seat(raw_name, raw_ticker, is_creator=False)
    with _registry_lock:
        _seats_by_token[seat.token] = (game, seat)
    return seat.token, game, seat


def lookup_seat(token):
    """Resolve a seat token to (game, seat), touching the game's LRU slot and
    the seat's liveness stamp. None for unknown/revoked/evicted tokens — the
    401 path (§6, A1/A4)."""
    if not token:
        return None
    with _registry_lock:
        entry = _seats_by_token.get(token)
        if entry is None:
            return None
        game, seat = entry
        if game.code in _games:
            _games.move_to_end(game.code)
    now = time.monotonic()
    game.last_access = now
    seat.last_seen = now
    return game, seat


def revoke_token(token):
    """Drop a kicked seat's credential; its next request gets 401 (§6, A4)."""
    if token is None:
        return
    with _registry_lock:
        _seats_by_token.pop(token, None)


def reset_registry_for_tests():
    """Headless-test helper: forget every game and token."""
    with _registry_lock:
        _games.clear()
        _seats_by_token.clear()
