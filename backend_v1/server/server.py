"""HTTP API layer (§11 `server/`): exposes Observations to the frontend.

Consumes engine output only — the handler never reaches into GameState; every
response body is either the player's Observation dict (already filtered by the
observation chokepoint), public market-cap history from the logger, or the
post-mortem (which is allowed to reveal TRUE state, §3: post-game = clarity).

Multi-session: each browser gets its own game, keyed by an opaque HttpOnly
cookie. The server holds the games in memory in a bounded LRU registry; there is
no shared global game, so concurrent players never touch each other's state.

Deployment posture is read from the environment at startup:
  ALIGNMENT_DEPLOY=production  → close the debug Truth endpoint (firewall, §0.3)
                                 and mark the session cookie Secure (HTTPS-only).
  HOST / PORT                  → bind address (default 127.0.0.1:8000, i.e. behind
                                 a reverse proxy that terminates TLS).
stdlib only. Run:  python3 -m backend_v1.server.server [--port 8000]
"""
import argparse
import json
import os
import secrets
import threading
import time
from collections import OrderedDict
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from backend_v1.engine.game import new_game, GameEngine
from backend_v1.engine.actions import Action, ActionError, validate_action
from backend_v1.engine.controllers.rival_controller import RivalController
from backend_v1.engine.observation.observation_builder import build_observation
from backend_v1.engine.postmortem import build_postmortem
from backend_v1.engine.rng import Rng
from backend_v1.server import multiplayer
from backend_v1.server.payloads import base_state_payload
from backend_v1.content.copy import t

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", "..", "simple_frontend_v1")

# ── Deployment posture ────────────────────────────────────────────────────────
# True only when explicitly deployed. Locally (unset) the Truth tab works and the
# cookie carries no Secure flag, so it survives plain http://127.0.0.1 playtesting.
DEPLOY_MODE = os.environ.get("ALIGNMENT_DEPLOY", "").lower() == "production"

# ── Session registry bounds (INVENTED for deployment — see ISSUES.md) ─────────
# A game is ~320 KB and grows a few KB per turn. MAX_SESSIONS caps total memory
# (500 games ≈ 160 MB, safe on a 1 GB droplet) by evicting the least-recently-
# used game when a new one would push us over.
MAX_SESSIONS = 500

# Largest POST body we accept. Real payloads (an action dict, a new-game request)
# are well under 1 KB; the cap stops a forged Content-Length from exhausting
# memory in _read_body before we ever read the socket.
MAX_BODY_BYTES = 64 * 1024

# Name of the opaque session cookie. Its value maps to a Session in the registry;
# HttpOnly keeps page JS (and thus any XSS) from ever reading it.
SESSION_COOKIE = "sid"

# Multiplayer seat cookie (MULTIPLAYER_DESIGN §4.1): same hardening as `sid`,
# distinct name so one browser can hold a solo game AND a multiplayer seat.
MP_COOKIE = "mp"

# ── Load-shedding bounds (INVENTED for deployment — see ISSUES.md) ─────────────
# Hard ceiling on a single game's length. A real game ends far sooner (~50-60
# turns), so this never touches legitimate play; it just guarantees one session
# can't be driven to an unbounded number of (CPU-costly) engine steps, even if a
# client requests a huge max_turns or a game somehow fails to terminate.
MAX_GAME_TURNS = 500

# Per-request socket timeout (seconds): caps how long one handler can hold a
# worker thread waiting on a slow or stalled client. Defense-in-depth — a reverse
# proxy already buffers requests, but this bounds the backend directly too.
REQUEST_TIMEOUT_SECONDS = 30

# Hard ceiling on requests processed at once. Past this we shed load with 503
# instead of spawning unbounded worker threads / running unbounded concurrent
# engine steps under a connection flood. Generous for real play (each request is
# a quick single turn); the edge (rate limiting) is the first line, this is the
# backstop if a flood gets through.
MAX_CONCURRENT_REQUESTS = 32
_request_slots = threading.BoundedSemaphore(MAX_CONCURRENT_REQUESTS)


class _BodyTooLarge(Exception):
    """Raised by _read_body when a request declares more bytes than MAX_BODY_BYTES."""


def clamp_max_turns(raw_value):
    """Bound a client-supplied max_turns to MAX_GAME_TURNS. None (the normal
    'play to a natural end' case) is capped too — real games end far sooner, so
    legitimate play is unaffected; this only removes the one client-tunable that
    could lengthen a single session's compute/memory without limit."""
    if raw_value is None:
        return MAX_GAME_TURNS
    try:
        requested_turns = int(raw_value)
    except (TypeError, ValueError):
        return MAX_GAME_TURNS
    if requested_turns < 1:
        return MAX_GAME_TURNS
    return min(requested_turns, MAX_GAME_TURNS)


class Session:
    def __init__(self, seed=0, difficulty="realistic", guidance="standard",
                 rivals=None, max_turns=None,
                 player_lab_name=None, player_ticker=None):
        # new_game sanitizes player_lab_name / player_ticker (untrusted input).
        self.state = new_game(seed=seed, difficulty=difficulty, guidance=guidance,
                              rival_count=rivals, max_turns=max_turns,
                              player_lab_name=player_lab_name,
                              player_ticker=player_ticker)
        self.engine = GameEngine()
        self.rival_ctrl = RivalController(Rng(seed + 1))
        self.observations = None      # per-lab observations from the last step
        self.player = next(l for l in self.state.labs if l.is_player)
        # Infrastructure only (NOT engine randomness, §0.4): `lock` serializes the
        # requests that touch THIS one game so two tabs of the same player can't
        # interleave a step; `last_access` drives LRU eviction in the registry.
        self.lock = threading.Lock()
        self.last_access = time.monotonic()
        # Cache for the post-mortem (built once the game is over). Building it
        # re-simulates counterfactual branches and is expensive, so we memoize.
        self._postmortem_cache = None

    def player_observation(self):
        if self.observations is not None:
            return self.observations[self.player.id]
        # turn 0: no step has run yet; build a fresh filtered view directly
        return build_observation(self.state, self.player, [], [], [], [])

    def truth_payload(self):
        """God's-eye TRUE state for the debug Truth tab. Reads the logger's
        per-turn snapshots (full true+measured) — NOT the firewalled player
        observation, so it never widens what build_observation exposes."""
        turns = []
        for t in self.engine.logger.turns:
            turns.append({
                "turn": t["turn"],
                "year": round(t["year"], 2),
                "labs": [{"id": lab["id"], "models": lab["models"]}
                         for lab in t["labs"]],
            })
        return {"turns": turns}

    def submit(self, action_dict):
        if self.state.game_over:
            return {"errors": [t("api.game_over")]}
        try:
            action = Action.from_dict(action_dict)
        except (ActionError, TypeError, ValueError) as e:
            return {"errors": [str(e)]}
        problems = validate_action(action, self.player, self.state.world,
                                   self.state.consts, self.state.dt)
        if problems:
            return {"errors": problems}
        is_first_turn = self.observations is None
        actions = {self.player.id: action}
        for lab in self.state.labs:
            if lab.is_player:
                continue
            if is_first_turn:
                actions[lab.id] = Action()
            else:
                actions[lab.id] = self.rival_ctrl.decide(
                    self.observations[lab.id], lab.disposition)
        self.state, self.observations = self.engine.step(self.state, actions)
        return self.state_payload()

    def state_payload(self):
        # shared with the multiplayer seats (payloads.py) — identical shape
        return base_state_payload(self.player_observation(), self.engine,
                                  self.state)

    def postmortem(self):
        if not self.state.game_over:
            return {"errors": [t("api.game_not_over")]}
        # The game is frozen once it's over, so the post-mortem is deterministic.
        # Build it once and reuse it: re-running build_postmortem (which replays
        # counterfactual branches) on every call would let a client amplify load
        # by spamming /api/postmortem on a finished game.
        if self._postmortem_cache is None:
            self._postmortem_cache = build_postmortem(
                self.engine.logger, self.state, self.player.id, resim=True)
        return self._postmortem_cache


# ── Session registry ──────────────────────────────────────────────────────────
# token -> Session, ordered by recency (least-recently-used at the front). The
# registry lock guards only this dict; the per-session lock guards a single game.
_sessions = OrderedDict()
_sessions_lock = threading.Lock()


def create_session(**session_kwargs):
    """Build a new game, register it under a fresh opaque token, and evict the
    least-recently-used game if we are over MAX_SESSIONS. Returns (token, session).
    The token is the cookie value handed to the browser."""
    session = Session(**session_kwargs)
    token = secrets.token_urlsafe(32)
    with _sessions_lock:
        _sessions[token] = session
        _sessions.move_to_end(token)
        while len(_sessions) > MAX_SESSIONS:
            evicted_token, _evicted_session = _sessions.popitem(last=False)
            print(f"evicted least-recently-used session {evicted_token[:8]}… "
                  f"({len(_sessions)} active)")
    return token, session


def lookup_session(token):
    """Return the Session for this cookie token (marking it recently used so an
    active player is not evicted), or None if the token is unknown or evicted.
    Only the registry dict is locked here; the caller takes the per-session lock
    before reading or mutating the game itself."""
    if not token:
        return None
    with _sessions_lock:
        session = _sessions.get(token)
        if session is None:
            return None
        _sessions.move_to_end(token)
        session.last_access = time.monotonic()
        return session


class Handler(BaseHTTPRequestHandler):
    # StreamRequestHandler applies this to the socket: a slow client can hold a
    # worker thread for at most REQUEST_TIMEOUT_SECONDS before the read times out.
    timeout = REQUEST_TIMEOUT_SECONDS

    def log_message(self, fmt, *args):   # quiet
        pass

    def handle(self):
        # Load-shed past MAX_CONCURRENT_REQUESTS rather than let a connection
        # flood spawn unbounded threads / concurrent engine steps. setup() has
        # already created self.wfile, so we can answer 503 without parsing the
        # request. The slot is always released, even if the handler raises.
        if not _request_slots.acquire(blocking=False):
            try:
                self.wfile.write(b"HTTP/1.1 503 Service Unavailable\r\n"
                                 b"Content-Length: 0\r\n"
                                 b"Connection: close\r\n\r\n")
            except OSError:
                pass
            return
        try:
            super().handle()
        finally:
            _request_slots.release()

    # ── Response helpers ──────────────────────────────────────────────────────
    def _json(self, payload, code=200, set_cookie=None):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if set_cookie is not None:
            self.send_header("Set-Cookie", set_cookie)
        self.end_headers()
        self.wfile.write(body)

    def _cookie_header(self, cookie_name, token):
        # HttpOnly: page JS (and any XSS) can never read the token.
        # SameSite=Lax: not sent on cross-site requests.
        # Secure (HTTPS-only): production only — a Secure cookie is dropped over
        # plain http://127.0.0.1, which would break local playtesting.
        # Shared by the solo `sid` and multiplayer `mp` cookies (§6, A7) so the
        # hardening can't drift between them.
        attributes = [f"{cookie_name}={token}", "HttpOnly", "Path=/", "SameSite=Lax"]
        if DEPLOY_MODE:
            attributes.append("Secure")
        return "; ".join(attributes)

    def _session_cookie(self, token):
        return self._cookie_header(SESSION_COOKIE, token)

    def _cookie_value(self, cookie_name):
        """Read one cookie's value from the request's Cookie header, or None."""
        raw_cookie = self.headers.get("Cookie")
        if not raw_cookie:
            return None
        jar = SimpleCookie()
        try:
            jar.load(raw_cookie)
        except CookieError:
            return None
        morsel = jar.get(cookie_name)
        return morsel.value if morsel else None

    def _session_token(self):
        return self._cookie_value(SESSION_COOKIE)

    def _require_seat(self):
        """Resolve the caller's multiplayer (game, seat) from the `mp` cookie.
        Authorization is by cookie, NEVER by anything in the body (§6, A1) —
        an unknown or revoked token gets 401, which is also how a kicked
        player's polling stops (§6, A4)."""
        resolved = multiplayer.lookup_seat(self._cookie_value(MP_COOKIE))
        if resolved is None:
            self._json({"errors": ["no multiplayer seat — create or join a game"]},
                       401)
        return resolved

    def _require_creator_seat(self):
        """Like _require_seat, but 403 for a non-creator (§6, A2). Admin
        endpoints (settings/start/kick) funnel through here."""
        resolved = self._require_seat()
        if resolved is None:
            return None
        _game, seat = resolved
        if not seat.is_creator:
            self._json({"errors": ["only the game creator can do that"]}, 403)
            return None
        return resolved

    def _require_session(self):
        """Resolve the caller's game from the session cookie, or emit the
        'start a new game' error and return None. Endpoints that read or mutate a
        game funnel through here so a cookieless or evicted visitor degrades to
        the new-game modal instead of touching someone else's game."""
        session = lookup_session(self._session_token())
        if session is None:
            self._json({"errors": ["no active game — start a new game"]})
        return session

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > MAX_BODY_BYTES:
            raise _BodyTooLarge(length)
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode())

    # ── GET routes ────────────────────────────────────────────────────────────
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._serve_index()
        elif self.path == "/api/state":
            session = self._require_session()
            if session is None:
                return
            with session.lock:
                self._json(session.state_payload())
        elif self.path == "/api/postmortem":
            session = self._require_session()
            if session is None:
                return
            with session.lock:
                self._json(session.postmortem())
        elif self.path == "/api/truth":
            self._serve_truth()
        elif self.path == "/api/mp/lobby":
            self._handle_mp_lobby()
        elif self.path == "/api/mp/state":
            self._handle_mp_state()
        elif self.path == "/api/mp/postmortem":
            self._handle_mp_postmortem()
        elif self.path.startswith("/js/") or self.path.endswith(".css"):
            self._static(self.path)
        else:
            self._json({"errors": ["not found"]}, 404)

    def _serve_index(self):
        index_path = os.path.join(FRONTEND_DIR, "index.html")
        try:
            with open(index_path, "rb") as f:
                html_body = f.read()
        except OSError:
            self._json({"errors": ["frontend not found"]}, 404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html_body)))
        self.end_headers()
        self.wfile.write(html_body)

    def _serve_truth(self):
        # The Truth tab is god-view debug. In production it must NEVER leave the
        # server (hidden/observed firewall, CLAUDE.md §0.3), so we return an empty
        # payload — the dev tab simply shows nothing. apply() fetches this every
        # turn and expects this exact shape, so returning empty closes the leak
        # without breaking the normal player flow.
        if DEPLOY_MODE:
            self._json({"turns": []})
            return
        session = lookup_session(self._session_token())
        if session is None:
            self._json({"turns": []})
            return
        with session.lock:
            self._json(session.truth_payload())

    def _static(self, url_path):
        """Serve frontend static assets (the js/ modules, any css) from
        FRONTEND_DIR, with a path-traversal guard. Playtest tool — no caching."""
        rel = url_path.lstrip("/").split("?", 1)[0]
        root = os.path.realpath(FRONTEND_DIR)
        target = os.path.realpath(os.path.join(root, rel))
        if not (target == root or target.startswith(root + os.sep)):
            self._json({"errors": ["forbidden"]}, 403)
            return
        ctype = ("text/javascript" if target.endswith(".js")
                 else "text/css" if target.endswith(".css")
                 else "application/octet-stream")
        try:
            with open(target, "rb") as f:
                body = f.read()
        except OSError:
            self._json({"errors": ["not found"]}, 404)
            return
        self.send_response(200)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ── POST routes ───────────────────────────────────────────────────────────
    def do_POST(self):
        try:
            body = self._read_body()
        except _BodyTooLarge:
            self._json({"errors": ["request body too large"]}, 413)
            return
        except (json.JSONDecodeError, ValueError) as e:
            self._json({"errors": [f"bad JSON: {e}"]}, 400)
            return
        if self.path == "/api/new":
            self._handle_new(body)
        elif self.path == "/api/action":
            self._handle_action(body)
        elif self.path == "/api/mp/create":
            self._handle_mp_create(body)
        elif self.path == "/api/mp/join":
            self._handle_mp_join(body)
        elif self.path == "/api/mp/settings":
            self._handle_mp_settings(body)
        elif self.path == "/api/mp/start":
            self._handle_mp_start()
        elif self.path == "/api/mp/kick":
            self._handle_mp_kick(body)
        elif self.path == "/api/mp/action":
            self._handle_mp_action(body)
        elif self.path == "/api/mp/stage":
            self._handle_mp_stage(body)
        else:
            self._json({"errors": ["not found"]}, 404)

    def _handle_new(self, body):
        try:
            token, session = create_session(
                seed=int(body.get("seed", 0)),
                difficulty=body.get("difficulty", "realistic"),
                guidance=body.get("guidance", "standard"),
                rivals=body.get("rivals"),
                max_turns=clamp_max_turns(body.get("max_turns")),
                # Untrusted player input — new_game() sanitizes (length-clamp,
                # control-char strip, empty→default) before constructing the lab.
                player_lab_name=body.get("lab_name"),
                player_ticker=body.get("ticker"))
        except ValueError as e:
            self._json({"errors": [str(e)]}, 400)
            return
        with session.lock:
            payload = session.state_payload()
        # Set-Cookie binds this browser to the game it just created; every
        # subsequent same-origin request carries it back automatically.
        self._json(payload, set_cookie=self._session_cookie(token))

    def _handle_action(self, body):
        session = self._require_session()
        if session is None:
            return
        with session.lock:
            result = session.submit(body.get("action", {}))
        status_code = 200 if "errors" not in result else 422
        self._json(result, status_code)

    # ── Multiplayer routes (MULTIPLAYER_DESIGN §4.10) ─────────────────────────
    # Except create/join, the acting seat comes from the `mp` cookie via
    # _require_seat — never from the body (§6, A1/A3). Admin routes assert
    # is_creator via _require_creator_seat (§6, A2). There is deliberately NO
    # /api/mp/truth route (§6, L1): the god-view stays a solo debug aid.

    def _handle_mp_create(self, body):
        token, game, creator_seat = multiplayer.create_game(
            body.get("lab_name"), body.get("ticker"))
        with game.lock:
            payload = {"code": game.code,
                       "lobby": game.lobby_payload(creator_seat)}
        self._json(payload, set_cookie=self._cookie_header(MP_COOKIE, token))

    def _handle_mp_join(self, body):
        token, game, seat = multiplayer.join_game(
            body.get("code"), body.get("lab_name"), body.get("ticker"))
        if token is None:
            error_payload = seat   # join_game returns the error in third slot
            status_code = error_payload.pop("status", 400)
            self._json(error_payload, status_code)
            return
        with game.lock:
            payload = {"code": game.code, "lobby": game.lobby_payload(seat)}
        self._json(payload, set_cookie=self._cookie_header(MP_COOKIE, token))

    def _handle_mp_lobby(self):
        resolved = self._require_seat()
        if resolved is None:
            return
        game, seat = resolved
        with game.lock:
            self._json(game.lobby_payload(seat))

    def _handle_mp_settings(self, body):
        resolved = self._require_creator_seat()
        if resolved is None:
            return
        game, seat = resolved
        # Pass a setting through only when the request actually carried it:
        # an ABSENT field means "leave unchanged", while an explicit null
        # turn_seconds means "timer off" (the frontend sends null for an
        # emptied timer field). set_settings converts before assigning, so a
        # bad value 400s with no partial change.
        settings_kwargs = {}
        if "rival_count" in body:
            settings_kwargs["rival_count"] = body["rival_count"]
        if "turn_seconds" in body:
            settings_kwargs["turn_seconds"] = body["turn_seconds"]
        with game.lock:
            try:
                result = game.set_settings(**settings_kwargs)
            except (TypeError, ValueError):
                self._json({"errors": ["settings must be numbers"]}, 400)
                return
            if "errors" in result:
                self._json(result, 409)
                return
            self._json(game.lobby_payload(seat))

    def _handle_mp_start(self):
        resolved = self._require_creator_seat()
        if resolved is None:
            return
        game, seat = resolved
        with game.lock:
            # Server-random seed: multiplayer games are non-replayable by
            # design (§7 — human timing already breaks determinism).
            result = game.start(seed=secrets.randbelow(2**31),
                                max_turns=clamp_max_turns(None))
            if "errors" in result:
                self._json(result, 409)
                return
            self._json(game.lobby_payload(seat))

    def _handle_mp_kick(self, body):
        resolved = self._require_creator_seat()
        if resolved is None:
            return
        game, seat = resolved
        try:
            target_seat_id = int(body.get("target_seat"))
        except (TypeError, ValueError):
            self._json({"errors": ["target_seat must be a seat id"]}, 400)
            return
        with game.lock:
            result, revoked_token = game.kick(
                target_seat_id, body.get("resolution", "auto_pass"))
        multiplayer.revoke_token(revoked_token)
        if "errors" in result:
            self._json(result, 400)
            return
        with game.lock:
            self._json({"ok": True, "lobby": game.lobby_payload(seat)})

    def _handle_mp_state(self):
        resolved = self._require_seat()
        if resolved is None:
            return
        game, seat = resolved
        with game.lock:
            if not game.started:
                self._json({"errors": ["game not started"]}, 409)
                return
            self._json(game.state_payload_for(seat))

    def _handle_mp_action(self, body):
        resolved = self._require_seat()
        if resolved is None:
            return
        game, seat = resolved
        with game.lock:
            if not game.started:
                self._json({"errors": ["game not started"]}, 409)
                return
            result = game.submit_seat(seat, body.get("action", {}))
        status_code = 200 if "errors" not in result else 422
        self._json(result, status_code)

    def _handle_mp_stage(self, body):
        resolved = self._require_seat()
        if resolved is None:
            return
        game, seat = resolved
        with game.lock:
            if not game.started:
                self._json({"errors": ["game not started"]}, 409)
                return
            result = game.stage_seat(seat, body.get("action", {}))
        status_code = 200 if "errors" not in result else 400
        self._json(result, status_code)

    def _handle_mp_postmortem(self):
        resolved = self._require_seat()
        if resolved is None:
            return
        game, seat = resolved
        with game.lock:
            self._json(game.postmortem_for(seat))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)))
    ap.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    args = ap.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    posture = "production" if DEPLOY_MODE else "local/dev"
    print(f"serving on http://{args.host}:{args.port}  ({posture}; Ctrl-C to stop)")
    server.serve_forever()


if __name__ == "__main__":
    main()
