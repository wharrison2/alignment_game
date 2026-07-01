# MULTIPLAYER_DESIGN.md — Kahoot-style multiplayer

**Status:** design only. No engine/frontend code exists yet; this document is the spec a
later session builds from. It is **not** authoritative over `design_doc.md` (intent) or
`CLAUDE.md` (code standards) — it records *how multiplayer maps onto the existing engine*,
the decisions taken with the designer, and the open [TUNE] items.

**Read first:** `design_doc.md` (§0 thesis, §10c rivals, §11 file map, §2/§7c
observation & warnings), `CLAUDE.md` (§2 true/measured firewall, §8 verification, §9
frontend architecture).

---

## 1. What we're building

Today the game is strictly single-player: one human lab (`is_player=True`) races
AI-controlled rivals, one game per browser cookie. Multiplayer lets **several humans each
control a lab in the same world**, joining through a Kahoot-style lobby code. The opening
modal gains **"Start multiplayer game"** and **"Join multiplayer game"** (enter code). The
creator gets a lobby (roster of joined labs, kick control, rival-count and optional
turn-timer settings, a **Start** button) and *also plays a lab themselves*. AI rivals may
still fill out the world; the creator chooses how many.

---

## 2. Decisions locked with the designer

1. **Creator also plays.** The creator picks a lab name/ticker like everyone else and
   controls a lab; they *additionally* hold the admin panel (start, kick, settings,
   in-game removal). No separate spectator/host seat.
2. **Turn-timer expiry → submit what's queued, budget-trimmed.** When an optional per-turn
   timer expires, each non-submitted human's *currently staged* action is submitted as-is;
   an empty queue is a pass. If the staged action exceeds budget, drop its entries in
   **reverse-chronological order** (most-recently-queued first) until it validates.
3. **Win/loss = the existing model, generalized to a race.** First human lab to reach
   **aligned ASI + market dominance wins**; an **existential catastrophe ends everyone's
   run (shared loss)**. This is today's `_finish` outcome logic, evaluated across all human
   labs instead of the single `is_player` lab.
4. **Disconnect with NO timer set → game-master admin panel.** Auto-timeout only exists
   when a timer is set. With no timer, a missing player would stall the barrier, so the
   engine **notifies the game master**, who removes the player in the in-game admin panel
   and chooses **replace-with-AI** or **auto-pass** for that lab.

---

## 3. Current architecture the design leans on

- **`backend_v1/engine/game.py`** — `new_game(...)` builds exactly one `is_player=True`
  lab (`id="player"`) + `num_rivals` rival labs (`id="rival{i+1}"`); dispositions/names
  are indexed `[i % len]`, so any rival count already works. `GameEngine.step(state,
  actions)` takes `{lab_id: Action}` and is **already lab-count-agnostic** — it iterates
  `state.labs` and builds an observation for every lab. The only single-human assumption in
  `step` is `player = next(l for l in state.labs if l.is_player)`, used to attach
  `collect_tips` to that one lab (`game.py:170-177`).
- **`backend_v1/engine/lab.py`** — a lab is a lab; player vs rival differ only by
  `is_player` and whether a tuned `Disposition` is supplied. `snapshot()` includes
  `is_player`.
- **`backend_v1/engine/controllers/rival_controller.py`** — `decide(obs, disposition)`
  consumes **only that lab's observation** (no godmode); one stateless instance serves all
  rivals. Reused as-is for AI-filled rivals and for replace-with-AI takeovers.
- **`backend_v1/engine/observation/observation_builder.py`** — `build_observation` is
  **already fully per-lab generic**; `rival_public` excludes only `lab.id`. Other humans
  appear to each player as fogged rivals exactly like AI rivals — **no new firewall
  surface**.
- **`backend_v1/engine/postmortem.py`** — `build_postmortem(logger, state, player_id,
  resim=False)` is already parameterized by `player_id`. Only `_resimulate` /
  `_counterfactuals_resim` (the `resim=True` branch) assume AI-controlled deterministic
  rivals. Everything else (`trajectories`, `key_moments`, `voided_impact`, heuristic
  `_counterfactuals`, `render_postmortem_text`) is a pure read of the logged trajectory.
- **Advice is controller-agnostic.** `observation/guidance.py` (`collect_tips`, incl. the
  hint-heavy `[Counter: ...]` recommendation) and `observation/warnings.py` (§7c warning
  catalog) read observation-grade state only — they work in multiplayer untouched. This is
  the "still give advice" surface: it does not depend on rivals being AI or on resim.
- **`backend_v1/server/server.py`** — `Session` = one game per HttpOnly `sid` cookie in an
  LRU registry; `Session.submit` builds `{player.id: action}` and AI-fills every other lab
  via `rival_ctrl.decide`, then steps. `postmortem()` hardcodes `resim=True`.
- **Frontend `simple_frontend_v1/`** — vanilla ES modules, no build step. The new-game
  modal is **injected by JS** into `#overlay-content` (`main.js:showNewGame/newGame`) and
  posts `{seed, difficulty, guidance, lab_name, ticker}` to `/api/new`. Single `api(path,
  body)` helper (GET if no body, else POST JSON); live-binding state in `core.js` (only
  `core` reassigns `OBS`/`NAMES`/…); render bus (`setRender`); inline handlers must be
  added to `Object.assign(window, {…})` in `main.js`. **No websockets** — everything is
  request/response, so multiplayer sync is by polling.

---

## 4. Backend design

### 4.1 Shared game object + seat registry (new: `backend_v1/server/multiplayer.py`)

A **`MultiplayerGame`** holds one shared `GameState` + `GameEngine` and a list of **seats**.
A **seat** = `{seat_token, lab_id, display_name, ticker, is_creator, connected,
staged_action, has_submitted}`. Registry: `code -> MultiplayerGame`, where `code` is a
short human-typable lobby code (e.g. 6 chars, `secrets.choice` over an unambiguous alphabet
— no `0/O/1/I`). Each human gets their own opaque `seat_token` cookie: reuse the existing
HttpOnly cookie machinery but add a second cookie name (e.g. `mp`) so a browser can hold a
solo `sid` and a multiplayer seat independently.

Reuse the existing bounded-LRU + `threading.Lock` pattern from `server.py`: the per-game
lock serializes the barrier; a registry lock guards the code→game dict. Lobby codes evict
on the same LRU basis.

**Authorization is by cookie, never by request body (§6).** Every `/api/mp/*` call resolves
the acting seat from the `mp` seat_token cookie → seat → *its* game; a `seat_token`/`lab_id`/
`code` in the body is never trusted to identify the actor. This makes cross-game isolation
automatic (a token grants access to exactly one game) and impersonation impossible (a seat
acts only for its own lab). The `mp` cookie reuses `_session_cookie`'s hardening verbatim —
`HttpOnly; Path=/; SameSite=Lax` + `Secure` in production — under a distinct name so a browser
can hold `sid` (solo) and `mp` (a seat) independently. **Kicking/removing a seat revokes its
token**, so a removed player's next request gets 401 and can no longer poll for observations.

### 4.2 `new_game` generalization for N humans

Generalize `new_game` (or add `new_multiplayer_game`) to accept **a list of human
identities** instead of a single `player_lab_name/ticker`:

```
human_identities = [(name, ticker), ...]   # each sanitized via existing sanitize_lab_name/sanitize_ticker
rival_count      = K                          # creator-chosen AI rivals (may be 0)
```

Create `player1..playerN` labs with `is_player=True` (default `Disposition`, exactly like
today's player) + `K` rival labs. **Keep the single-human `new_game` path intact** for solo
play and the golden master. **Total labs = N humans + K rivals.**

### 4.3 Turn barrier — `MultiplayerGame.submit_seat(...)`

Replace `Session.submit`'s "one human + AI-fill everyone" with a **barrier**:

1. A seat POSTs its action → store as that seat's `staged_action`, mark `has_submitted`.
2. When **all connected human seats have submitted** (or the timer expires, §4.5), resolve:
   - Build `actions = {seat.lab_id: seat.staged_action}` for every human seat.
   - For seats not submitted at forced resolution, use their `staged_action` (possibly
     empty), **budget-trimmed** (§4.4).
   - AI-fill **only the rival labs** via `rival_ctrl.decide(observations[lab.id],
     lab.disposition)` — unchanged logic, now restricted to non-human labs.
   - `engine.step(state, actions)` once; reset all `has_submitted`/`staged_action`.
3. Between submit and resolution, each seat's `/api/mp/state` returns its **previous**
   observation plus a lightweight **barrier status** (`submitted`/`total`, per-seat
   submitted booleans, timer deadline). A seat's `staged_action` is **private to that seat**
   until the step resolves — it never appears in another seat's payload (§6, L5).

### 4.4 Budget-trim helper (timeout safety)

New pure helper (near `actions.validate_action` / `rules.budget_pool`): given a staged
`Action` and its lab, **drop the most-recently-queued cost-bearing entries until
`validate_action` passes** — reverse-chronological (last `start_projects` entry first, then
lobby/litigation spends, etc.). Reuses the existing `validate_action`, `budget_pool`,
`committed_budget` machinery — no new economics. Applied at forced resolution so a
never-submitted, over-budget queue can't wedge the barrier.

### 4.5 Optional per-turn timer (lazy enforcement — no background thread)

The creator sets an optional `turn_seconds` in the lobby. When a turn opens, stamp
`turn_deadline = monotonic() + turn_seconds`. **Enforcement is lazy**: on every
`submit_seat` and every `/api/mp/state` poll, if `now >= turn_deadline`, resolve the turn
immediately (§4.3) using staged+trimmed actions for non-submitters. Because clients poll
`/api/mp/state` every ~1-2s, the deadline is checked frequently without any scheduler
thread. **No timer set → no deadline → the barrier waits for all humans** (the admin panel,
§4.8, is then the only way past a stuck seat).

### 4.6 Endgame / win-loss generalization

`turn_pipeline._check_endgame` / `_finish` currently compute the outcome from the single
`is_player` lab (`turn_pipeline.py:438,512`). Generalize:

- **Win:** evaluate the existing win predicate (dominant + `net_impact > IMPACT_WIN_BAR`,
  i.e. aligned-ASI + market dominance) **across all human labs**; the **first** human lab
  to satisfy it ends the game as the winner. Dominance is exclusive (only one lab can be
  dominant), so the race is naturally single-winner; if two cross in the same turn,
  tie-break by `net_impact`, then `market_cap` (invented — see §9).
- **Loss / catastrophe:** the existential-catastrophe branch already "ends everyone's run",
  so it generalizes directly to shared loss.
- **Outcome payload** becomes per-seat: the winner sees "you won"; other humans see their
  placement (rank by impact/market_cap) and the shared-fate message on catastrophe.

### 4.7 Post-mortem

For multiplayer, call `build_postmortem(..., resim=False)` — gate on an `is_multiplayer`
flag rather than editing the solo call. This drops only the "re-ran history, outcome
flipped" verdicts; the true-vs-measured reveal, hidden moments, "evals went blind",
heuristic decision-point counterfactuals, and all live advice remain. Each human seat gets
its own post-mortem via its `lab_id` (already supported by the `player_id` parameter). Add
a shared **leaderboard** (final ranking of all labs).

**The post-mortem reveals every lab's TRUE trajectory**, so `/api/mp/postmortem` reuses the
existing `game_over` guard (server.py:197) **scoped to the shared game**: a kicked /
auto-passed / replaced-by-AI seat cannot fetch it while the game is still live for the
others. Revealing opponents' hidden state *after* the shared game ends is intentional
(design §3, "post-game = clarity") and safe because the game ends for everyone at once (§9, R2).

### 4.8 Game-master admin panel (backend actions)

The creator seat can, **in the lobby**: kick a joinee, set `rival_count`, set optional
`turn_seconds`, and press **Start**. **In-game** (decision #4): when a seat is
disconnected/stuck and no timer is set, the engine surfaces the seat in the admin panel
with two resolutions:

- **replace-with-AI** — flip the lab's control to `rival_ctrl` for the rest of the game
  (assign it a `Disposition`; the lab keeps its state, only who decides changes).
- **auto-pass** — the seat submits an empty action every turn.

Admin endpoints **assert the resolved seat `is_creator`** (a non-creator gets 403; §6, A2).
The admin/lobby payload is built by a dedicated function that carries **lobby metadata only**
(`display_name`, `ticker`, `connected`/`submitted` booleans, `is_creator`) and *structurally
cannot* contain model stats or staged actions — it is not a filtered `GameState` (§6, L4).

### 4.9 Generalize the `is_player` singletons

Replace every `next(l for l in labs if l.is_player)` that assumes one human, and decide the
multi-human semantics where the player was special-cased:

| Location | Today | Multiplayer |
|---|---|---|
| `game.py:170-177` (tips loop) | tips for the one player | attach `collect_tips` to **each** human lab |
| `turn_context.py:29` (`player` prop) | one lab | add `human_labs` (list); keep `player` only for solo |
| `turn_pipeline._check_endgame/_finish` (`:438,512`) | single-human outcome | §4.6 race across human labs |
| `turn_pipeline` release headline (`:366`) | precise measured-general only for `is_player` | **FIREWALL-CRITICAL (§6, L3):** key to *the observing lab's own* release, **not** "any human". With every human `is_player`, an "is any human" test would broadcast each human's precise measured-general to all others. The precise figure belongs only in that lab's own observation; every other observer sees the fogged rival value |
| `event.py:48,75,79` (frontier rule `player_best`) | one player's frontier | use **max true general across human labs** as the human frontier (a chosen default — §9) |
| `buyouts.py:36` (`_is_moribund` skips `is_player`) | one immune lab | **all human labs** immune to buyout relaunch |
| `regulation.py:242,253` (player explicit vs rival stochastic compliance) | one explicit-defection lab | applies per **human** lab |

`observation_builder`, `rival_controller`, and the rival-count constants need **no change**.

### 4.10 API endpoints (all via the existing `api()` helper)

Except `create`/`join`, **the acting seat is resolved from the `mp` cookie, never the body**
(§6, A1). "creator only" = the resolved seat's `is_creator` is asserted server-side (§6, A2).

- `POST /api/mp/create` `{lab_name, ticker}` → creates game, returns `{code, seat_token}`, sets `mp` cookie, creator is seat 0.
- `POST /api/mp/join` `{code, lab_name, ticker}` → joins lobby, returns the seat. Rejected if the game is **started** or **full** (§6, A6).
- `GET  /api/mp/lobby` → lobby metadata only (code, roster, settings, started?) — polled; cookie-resolved.
- `POST /api/mp/settings` `{rival_count, turn_seconds}` → creator only.
- `POST /api/mp/kick` `{target_seat}` → creator only (lobby + in-game removal → replace-with-AI/auto-pass); **revokes the target's token** (§6, A4).
- `POST /api/mp/start` → creator only; builds the shared game from seats + settings.
- `GET  /api/mp/state` → **this seat's own** observation + barrier status + timer deadline — polled each turn; cookie-resolved.
- `POST /api/mp/action` `{action}` → stage + submit for **the cookie's seat only** — no `lab_id` in the body (§6, A3); §4.3 barrier.
- `GET  /api/mp/postmortem` → this seat's `resim=False` post-mortem + leaderboard; gated on shared `game_over` (§4.7).
- **No `/api/mp/truth` route exists** — the god-view Truth tab is unavailable in multiplayer (§6, L1).

---

## 5. Frontend design (`simple_frontend_v1`)

1. **Opening modal (`main.js:showNewGame`)** — add **"Start multiplayer game"** and
   **"Join multiplayer game"** (code input) beside the existing solo start. Reuse the
   injected-`#overlay-content` pattern. **The dev-mode checkbox (which reveals the Truth tab)
   is unavailable on the multiplayer paths** — the god-view is a solo debug aid only (§6, L1).
2. **Lobby screen** — a full-screen overlay (clone the `showPostmortem`/`showNewGame`
   injection pattern). Kahoot-style card grid of joined labs (name + ticker + color).
   **Every human-authored string — each lab name/ticker and the echoed lobby code — must be
   `esc()`-escaped at the render site** (§6, A8): in MP another player's name lands in *your*
   DOM, so an unescaped path is stored XSS, not just a cosmetic bug. Creator sees admin
   controls (kick per card, rival-count stepper, optional turn-timer input, **Start**);
   joiners see a read-only roster + "waiting for host". Poll `GET /api/mp/lobby` (~1s) via
   `api()`.
3. **In-game multiplayer status** — reuse the existing render pipeline; add a
   waiting-for-players banner (submitted/total) and, if a timer is set, a countdown chip in
   `#topbar`. Poll `GET /api/mp/state` (~1-2s) to advance when the barrier resolves; drive
   the refresh through the render bus (`render` from `core.js`), never importing `main`.
4. **In-game admin panel** — creator-only overlay listing stuck/disconnected seats with
   **Replace-with-AI / Auto-pass / Kick** buttons (decision #4).
5. **Add multiplayer state to `core.js`** — new live-binding `let` exports (e.g. `MP`,
   `LOBBY`, `SEAT`) reassigned **only in `core`**, matching the `OBS`/`NAMES` convention.
6. **Wire every new inline handler** into `Object.assign(window, {…})` in `main.js`
   (create/join/kick/start/setRivalCount/setTurnTimer/adminReplace/adminPass/…) — the
   handler-exposure gotcha from `CLAUDE.md §9`.
7. **End screen** — reuse the post-mortem overlay; prepend a **leaderboard** (final lab
   ranking), then the seat's own `resim=False` post-mortem.

---

## 6. Security: information leaks & access control

Going from one human to N humans sharing a world creates leak/authz surfaces that don't
exist solo (where the sole human seeing "everything" was harmless). These are firewall-grade
(`CLAUDE.md §2`, design §11) — treat a violation as the highest-severity bug. **DDoS /
rate-limiting is out of scope here** (handled separately), except where guessing a code is an
*access* concern (A6). Each rule is written as an implementation constraint.

### Information leaks (the hidden/observed firewall)

- **L1 — No god-view in multiplayer.** `/api/truth` and the dev-mode Truth tab serve every
  lab's TRUE state (`true_alignment`, `concealment`, `hidden_history`); in MP that is
  opponents' hidden state. Multiplayer games serve **no truth route regardless of
  `DEPLOY_MODE`**, and the new-game dev-mode checkbox is unavailable on the MP paths. The
  Truth god-view stays a solo debug aid.
- **L2 — Per-seat observation only.** `/api/mp/state` returns
  `build_observation(state, this_seat_lab, …)` for the seat resolved from the cookie — never
  a shared/broadcast payload, another seat's observation, or raw `GameState`. No "creator
  gets a fuller view."
- **L3 — Own-lab precise stats only.** The release-headline precise-measured-general branch
  (`turn_pipeline.py:366`, today `if lab.is_player`) must key to *the observing lab's own*
  release, not "any human" — otherwise every human's precise stats broadcast to all. Every
  other observer sees the fogged rival value. (See the §4.9 table row.)
- **L4 — Admin/lobby payloads are metadata-only.** Roster and admin panel carry only
  `display_name`, `ticker`, `connected`/`submitted` booleans, `is_creator` — from a dedicated
  builder that *structurally cannot* contain model stats or staged actions, not a filtered
  `GameState`.
- **L5 — Staged actions are private.** A seat's `staged_action` never appears in another
  seat's `/api/mp/state`; barrier status exposes only submitted/total counts and per-seat
  submitted booleans.
- **L6 — Post-mortem gated on shared `game_over`.** It reveals every lab's TRUE trajectory
  (design §3), so `/api/mp/postmortem` reuses the existing `game_over` guard scoped to the
  shared game; a kicked / auto-passed / replaced-by-AI seat cannot fetch it while the game is
  still live for others.

### Access control

- **A1 — Authorize by cookie, never the body.** Every `/api/mp/*` call (except create/join)
  resolves the acting seat from the `mp` seat_token cookie → seat → its game; a
  `seat_token`/`lab_id`/`code` in the body is never trusted to identify the actor. Unknown or
  revoked token → 401.
- **A2 — Admin endpoints assert `is_creator`.** `settings`, `kick`, `start`, in-game removal
  reject a non-creator seat with 403.
- **A3 — A seat acts only for its own lab.** `/api/mp/action` derives the lab from the
  authenticated seat; no `lab_id` in the body (anti-impersonation).
- **A4 — Kick/remove revokes the token.** A removed player's next request gets 401/"removed",
  so they can't keep polling `/api/mp/state` to harvest observations.
- **A5 — Cross-game isolation.** A seat_token resolves to exactly one game and never grants
  access to another — enforced automatically by resolving via token, not via a body `code`.
- **A6 — Lobby code is a real join credential.** Enough entropy that it can't be guessed to
  gain access (the access-side risk that remains even though brute-force *throttling* is
  deferred as DDoS — §9). Reject joins to a **started** or **full** game; cap seats.
- **A7 — `mp` cookie reuses the exact hardening.** `HttpOnly; Path=/; SameSite=Lax` +
  `Secure` in prod — mirror `_session_cookie` (server.py:290). Distinct name so `sid` (solo)
  and `mp` (a seat) coexist in one browser.
- **A8 — Stored-XSS across users.** Each human's name/ticker renders in *other* players' DOM
  (lobby cards, rivals panel), so it is a cross-user injection surface, not cosmetic.
  Sanitize server-side on join (`sanitize_lab_name`/`sanitize_ticker`, `game.py`) **and**
  `esc()` at every render site, including the echoed lobby code.

### Lower-risk / noted

- **CSRF is low-risk.** State-changing calls are same-origin JSON POSTs; `SameSite=Lax` +
  the JSON content-type mitigate, and no cookie-authed GET mutates state. No dedicated token
  planned; revisit if a non-JSON form path is ever added.

---

## 7. Invariants to preserve

- **Firewall (`CLAUDE.md §2`).** Each seat receives only its own `build_observation`; other
  humans are fogged `rival_public` exactly like AI rivals; MP serves **no truth route** (§6,
  L1) and per-seat observations only (§6, L2). The admin panel serves lobby metadata only.
  Audit `/api/mp/*` payloads by walking the dict for forbidden **keys** (`true_*`,
  `concealment`, `foundational_floor`, `suppression`, `hidden_history`) — not substrings
  (`CLAUDE.md §8` firewall-audit gotcha).
- **Determinism (`CLAUDE.md §0.4, §8`).** Multiplayer games are **not** deterministic or
  replayable (human timing + wall-clock timer), so they are **out of scope for the golden
  master** — keep the solo `new_game`/`Session` path unchanged so `tests.test_golden_master`
  still passes untouched. World RNG stays seeded for events; only counterfactual resim is
  dropped (`resim=False`).
- **No raw per-turn numbers (`CLAUDE.md §0.5`).** `turn_seconds` is UI/session config
  (wall-clock, not game-time `dt`), so it lives in the multiplayer session layer, not the
  per-year `constants.py` module.

---

## 8. Files to create / modify (for the implementing session)

- **New:** `backend_v1/server/multiplayer.py` (game + seat registry, barrier, timer,
  admin), frontend lobby/admin render code (a new section in `views.js` or a new
  `js/lobby.js` module).
- **Modify:** `backend_v1/engine/game.py` (N-human `new_game`, tips loop),
  `backend_v1/engine/turn_pipeline.py` (endgame race, release-headline scoping,
  compliance), `backend_v1/engine/turn_context.py` (`human_labs`),
  `backend_v1/engine/events/event.py` (frontier rule), `backend_v1/engine/events/buyouts.py`
  (human immunity), `backend_v1/engine/governance/regulation.py` (per-human compliance),
  `backend_v1/server/server.py` (mount `/api/mp/*`, `resim` flag), frontend
  `main.js` / `core.js` / `views.js` + `index.html` (new cookie, handlers, overlays).

---

## 9. Open items / [TUNE] for the designer

- **Human frontier definition** for the rival-existential-event rule (§4.9, `event.py`):
  using max-true-general across human labs is a chosen default, not doc-specified.
- **Lobby-code length/alphabet, max seats per game, lobby/game LRU TTLs** — invented bounds
  (the code's entropy is also a *security* parameter — §6, A6).
- **Same-turn win tie-break** (impact → market_cap) is invented.
- **Zero AI rivals** — the creator sets `rival_count`, so 0 is allowed; confirm the world /
  economy (investment pie, events) behaves sensibly with an all-human field.
- **R1 — Creator succession / orphaned admin.** If the creator disconnects, the admin panel
  is stranded — a *liveness* problem, not a leak. Later: promote the next-oldest seat to
  creator, or let a timer-only game run on without admin. Flagged, not solved here.
- **R2 — Post-game reveal of opponents' TRUE state is a deliberate choice.** The post-mortem
  exposing what each human secretly did is intended (design §3, "post-game = clarity") and
  safe because the shared game ends for everyone at once. Recommendation: keep it — the
  reveal is the pedagogical payoff — but record it as a conscious competitive-integrity call.

---

## 10. Verification (of the eventual implementation)

- **Solo unchanged:** `python3 -m unittest tests.test_golden_master` still passes with no
  re-record (multiplayer must not touch the solo path).
- **Firewall audit:** script a 3-seat game headlessly; for each seat's `/api/mp/state`,
  assert no forbidden **key** appears anywhere in the observation dict.
- **Barrier + timeout:** headless test — three seats, submit two, assert no step; submit the
  third → exactly one step. With a timer, let it expire with one seat over-budget → assert
  its action is trimmed reverse-chronologically and the step resolves.
- **Endgame race:** drive one human lab to the win condition → assert it wins and others get
  placements; trigger a catastrophe → assert shared loss.
- **Frontend (static only, no JS runtime — `CLAUDE.md §8`):** brace/paren balance per file;
  every new inline handler exposed on `window`; `curl` new modules for `200 text/javascript`.
  Hand the user a browser smoke-test: create → join → lobby → start → synced turns →
  leaderboard.
