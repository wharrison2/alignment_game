# IMPLEMENTATION_DETAILS — mechanisms in the code that the design doc doesn't describe

**Scope.** `design_doc.md` is the authoritative *what we build*. This file is the
companion catalog of subsystems, fields, and structures that **exist in the code but
are not described (or are only gestured at) in the design doc**. It is descriptive,
not authoritative: where an entry and the design doc disagree on intent, the design
doc wins and the divergence is logged in `ISSUES.md`. Keep this current as the code
grows — when you add a mechanism the doc doesn't mention, add it here.

Audited 2026-06-18 against `design_doc.md`. Locations are paths under `backend_v1/`
(or `cli/`) and may drift — grep the symbol if a line moved.

**Planned (not yet in code):** a Kahoot-style multiplayer mode — see
`MULTIPLAYER_DESIGN.md`. When it lands, move its subsystems (shared game / seat
registry, turn barrier, lobby/admin panel) into this catalog.

---

## Core orchestration

- **`engine/turn_context.py` — `TurnContext`.** Not in the §11 file map. A single
  per-turn state bundle (`labs`, `world`, `flags`, `rng`, `consts`, `dt`, `turn`,
  plus a derived `labs_by_id` and a `player` property), built once in
  `turn_pipeline.run_turn` and threaded through every phase function. Replaced an
  ad-hoc `SimpleNamespace` that each subsystem hand-rolled identically.

- **`engine/rules.py` — action economics, single source of truth.** Not in the §11
  file map. Holds `budget_pool`, `committed_budget`, `project_template`,
  `assist_potency`, `assist_speed_potency`, `effective_fraction`. Three consumers
  (`actions.validate_action`, `turn_pipeline._apply_action`, `actions.legal_moves` /
  `observation_builder`) all call through here so the budget/cash math can't drift
  apart. `assist_potency` also applies a **per-advance `assist_potency_bonus`**:
  certain researched advances raise the effectiveness of all future AI-assisted work
  (multiplicative, clamped) — a progression detail not in §8b.

## Model entity (`engine/model.py`) — fields beyond the §4.1 sketch

- **`foundational_floor`** — the unscrubbable pretrain-poisoning floor on
  `goal_misalignment`/`deception`; `= min(FOUNDATIONAL_FLOOR_CAP, FOUNDATIONAL_FLOOR_K
  × pretrain_contamination)`. §8b names the concept ("post-training cannot scrub");
  the field, cap, and formula are implementation.
- **`suppression` (AlignmentVec)** — accumulated *cosmetic* fixes: where corrective
  effort hit measured but not true (the EFFECTIVENESS leftover, §5b). Subtracted from
  true when computing measured.
- **`hidden_history`** — per-model log of invisible-at-the-time events
  (`{turn, kind, detail}`): foundational contamination, correlated jumps, cosmetic
  fixes, edges coming online. The post-mortem substrate, materialized on the model.
- **`concealment` property** — `min(CONCEALMENT_CAP, eval_awareness × deception ×
  CONCEALMENT_K)`. §7b describes spoofability/corruption qualitatively; this is the
  concrete product-with-scale-and-cap that gates how much instruments see.
- **`consumed_contamination`, `used_synthetic_data`, `_conceal_k`** — provenance and
  the per-model concealment coefficient (set from `CONCEALMENT_K` at shaping time).
- **`misalignment_composite()`** — see ISSUES.md: it is a disposition-weighted **sum**
  (`COMPOSITE_W_*`), which differs from §5's multiplicative `goal_mis × capability ×
  self_pres` framing.

## Training (`engine/training/training_run.py`)

- **Advance-driven training (no "safety knob").** The per-round post-train MODE knob
  (`POST_TRAIN_MODES`) is GONE. A post-train round runs at a fixed BASELINE
  (`POST_TRAIN_BASE_ELICITATION_MULT` / `POST_TRAIN_BASE_ALIGNMENT_EFFORT`, equal to
  the former "balanced" mode) and is bent by the SAFETY ADVANCES the player chose to
  APPLY that round. Safety advances are a second catalog
  (`engine/research/safety/safety_advance_item.py`, `SafetyAdvance` /
  `SAFETY_ADVANCES_BY_ID`), researched with the SAME machinery as capability advances
  (kind `"safety_advance"` in `rules.project_template`) so they ALSO carry hidden
  contamination = ai_assist × researcher goal_mis × tier and live in the same
  `lab.researched_advances` dict. They are tagged PRETRAIN (data_cleaning,
  aligned_synthetic_data — act in `commission_run` / `complete_pretrain` on the
  foundational floor & base goal-mis, incl. the synthetic-data contamination path) or
  POST_TRAIN (reward_hacking_penalties, inoculation_prompting, deliberative_alignment —
  the §5b preventive lever: bend the emergence slope + correlated-jump probability,
  shrink the fake-the-objective proxy gap, raise corrective EFFECTIVENESS). The engine
  reads the advances' effect FIELDS generically and combines them (multipliers multiply,
  bonuses add) — no per-advance branch. The action schema carries the per-run choice as
  `post_train.applied_safety` / `commission_run.applied_safety` (lists of researched
  ids); `rules.applied_post_train_round_budget` is the single source of truth for the
  round's work-budget. Numbers are [TUNE] drafts (see ISSUES.md "Advance-driven
  training"). NOTE: the frontend is not yet wired to this (still renders the old mode
  selector); the backend ignores a stray `mode` key and runs a safe baseline round.

- **Pretrain alignment seeding** — `goal_misalignment = BASE_GOAL_MIS_PRETRAIN +
  PRETRAIN_CONTAM_GOAL_MIS_MULT × pretrain_contamination + |N(0, σ)|`; jailbreak
  baseline + noise. The §8 base-emergence numbers were unspecified; now named
  constants.
- **`ELICITATION_RATE_CAP`** — per-round gap-closure is capped below 1 so a fully
  researched post-train tree can't overshoot the capability ceiling.
- **Contamination model** — a node's contamination `= ai_assist × assisting-model
  goal_misalignment × CONTAM_PER_ASSIST × template.contamination_tier`; summed
  contamination feeds axes via `CONTAM_TO_AXES`. §8b describes the shape; the scaling
  constants and per-template tier are implementation.
- **`REGIME2_ONSET` / `REGIME3_ONSET`** (`config/constants.py`) — soft capability
  reference points (3.5 / 6.5) with **no in-game labels**; used only by emergence
  curves, agentic-edge gates, and guidance hedging. §6's "three regimes" are
  conceptual; these thresholds are code-only.

## Private evaluations (`engine/evaluations.py`) — a whole undocumented info channel

A **build-once + upgrade-tiers** harness system, distinct from the §7b safety
*research projects*. A harness is built once (cash + turns) and then reads for free
on every model change; upgrades (cash + turns) buy down how much eval-awareness
corrupts the reading (`awareness_reduction`). Your models only — never a rival's.
Seven harnesses: `dangerous_cyber`, `dangerous_bio`, `sandbag_detector`,
`behavioral_surface`, `deception_monitor`, `scenario_shutdown`,
`scenario_authoritarian`. Surfaced in `legal_moves.eval_harnesses` and driven by the
`build_evals` action. §7 mentions private evals; this build/upgrade economy is not
described.

## Benchmarks (`engine/benchmarks.py`)

- **Frontier early-release** — the sealed `frontier_x` benchmark unlocks before its
  release year once the public frontier general capability reaches HLE's midpoint +
  `FRONTIER_EARLY_RELEASE_MARGIN`. §9 says the world releases harder benchmarks on a
  schedule; the capability-triggered early unlock is implementation.

## Finance (`engine/finances/`)

- **Job-loss drag** (`finances.py`) — continuous (not event-based) approval/impact
  pressure as a function of `world.frontier_measured_general`; impact attributed by
  revenue share. Note `JOB_LOSS_APPROVAL_INTENSITY_SCALE`/`_AMOUNT_SCALE` currently
  offset (net ×1): a documented simplification candidate (see ISSUES.md).
- **Persistent investor-confidence momentum** (`investment.py`, field
  `lab.investment_momentum`) — §9b describes the *behavior* (grace window, rising
  bar, beat→reward / miss→cliff) but not the state shape. Momentum is a per-lab
  accumulator advanced one step per turn in `update_investment_momentum`:
  - on a release: `confidence = 1 + SCORE_MOMENTUM_GROWTH·growth_term`; a BEAT
    (`growth_term ≥ 0`) carries momentum forward via `max(confidence, momentum)`
    (no drop), a MISS resets it down to that sub-1 confidence (the cliff);
  - within the grace window with no release: momentum grows at
    `SCORE_GRACE_GROWTH / SCORE_GRACE_YEARS` per year;
  - past grace with no release: momentum decays at `SCORE_RELEASE_DECAY` per year.
  `lab_score` reads this field directly. This replaced an earlier *stateless*
  formulation that recomputed the grace ramp off "quarters since last release" and
  reset it at every release — which dropped the market cap after each release (the
  "slanted staircase"). No new tunables; reuses the existing `SCORE_*` constants.
- **Smoothed slope signals — post-release-growth fix** (`investment.py`,
  `market_cap.py`). The momentum work above fixed the *score*, but the market cap STILL
  declined after a release because it keyed off the spiky per-turn `investment_rate`,
  which the *instantaneous* revenue-growth term flung up on a release turn (a new model
  enters the revenue pie) then down the next (mean-reversion). Two EMAs decouple the
  cap from that single-turn jitter so the staircase climbs after a healthy release while
  a genuine stall/miss still falls (see ISSUES.md "Finance fixes"):
  - `world.smoothed_revenue_growth_per_year` — EMA of single-turn revenue growth
    (`REVENUE_GROWTH_SMOOTHING_ALPHA`); feeds `growth_multiplier` for total investment.
  - `lab.smoothed_investment_rate` — EMA of the live `investment_rate`
    (`INVESTMENT_ANCHOR_ALPHA`); the market-cap SIZE anchor, replacing the raw rate. The
    cap target is now `MARKET_CAP_SCALE·score·max(smoothed_investment_rate,1) + 0.5·revenue`,
    so it tracks the smoothly-rising `score` (the §9b forward-looking / slope-weighted
    signal).
- **Early/seed base investment** (`investment.py`, field `lab.base_investment_rate`).
  §9b says the default state is growth, but total investment scaled with
  `frontier_measured_general` (=0 pre-release), so investment was ~0 early. A modest
  per-YEAR base flow (`BASE_INVESTMENT_PER_YEAR`) is seeded in `new_game` for every lab
  and advanced one step per turn in `update_base_investment`: it HOLDS while the lab is
  "active" (has shipped OR has research/pretrain/post-train work in progress) and DECAYS
  (`exp(-BASE_INVESTMENT_DECAY_PER_YEAR·dt)`) toward zero when idle. It is ADDED on top
  of the score-divvied pie (the lab's own seed money, not a pie share), dominating early
  and tapering as real investment takes over. All four new constants are drafts [TUNE].

## Events & governance modules absent from the §11 map

- **`engine/events/buyouts.py` — anti-coast buyout/relaunch.** Not in the §11 map and
  only gestured at by §10's "snowball counterweights." When the market concentrates
  (leader share ≥ `BUYOUT_TRIGGER_CONCENTRATION`), a starved rival (below
  `BUYOUT_TARGET_CAP_FRACTION` of the leader and below `BUYOUT_TARGET_VIABLE_CASH`) is
  acquired, recapitalized, renamed (from `BUYOUT_ACQUIRER_NAMES`), and relaunched at
  high recklessness — reusing the same `lab.id` so every id-keyed system is untouched.
  Hazard rises with concentration; gated by `BUYOUT_COOLDOWN_TURNS`. A material
  mechanic governed entirely by `BUYOUT_*` constants.
- **`engine/governance/gov_news.py` — political-blowback loop.** Named in §10c prose
  but absent from the §11 map. Translates each litigation/regulation outcome into an
  approval/WTR news event (e.g. striking a *popular safety* policy wins in court but
  costs approval and raises WTR), riding the §9 event/narration channel.

## Per-policy rival pressure recording (`engine/world.py`, observation)

- **`PolicyState.contributions` (`engine/world.py`).** `lab_id -> {"ticker": str,
  "stance": str, "lobby_spend": float, "lit_spend": float}`. PURE-LOGGING mirror of
  lobbying/litigation money already spent on a policy, added so the board can show
  each rival's pressure (UI_ISSUES #5). Spends are **CUMULATIVE** over the game (the
  box reflects total pressure, not a single turn); `stance` is the lab's **latest**
  declared stance (lobby stances re-set each turn; for litigation the stance is the
  `side`, challenge/defense). Written by `PolicyState.record_contribution(...)`,
  called from `turn_pipeline._apply_governance_action` (lobby) and
  `governance/litigation.apply_litigation_action` (litigation) AFTER the existing
  tally/effort math — it never feeds enactment, margin, or any RNG draw, so the
  golden master is byte-identical. All fields are PUBLIC regulatory state (design
  §10c), safe across the firewall.
- **Observation `legal_moves.policies[*].rival_contributions`
  (`engine/actions.py` `_policy_board`).** Per policy, a list of
  `{"lab_id", "ticker", "stance", "lobby_spend", "lit_spend"}` for every contributing
  lab **except the viewing lab** (you see rivals, not yourself). Derived purely from
  `PolicyState.contributions`; the ticker is stamped at record time so `_policy_board`
  needs no labs list (it only receives `lab, world, consts`).

## Turn-0 market-cap graph seed (`server/server.py` `caps_history`)

`caps_history()` seeds a single turn-0 point from the labs' CURRENT market caps when
`engine.logger.turns` is empty, so the frontend graph renders immediately instead of
"no turns played yet" (UI_ISSUES #9). Once turn 1 is logged the seed branch stops
firing, so turn 0 is never double-counted. Server-payload only — no TRUE-state log,
no RNG.

## Actions schema (`engine/actions.py`) — fields beyond the README example

The `Action` dataclass carries, in addition to the documented
`start_projects`/`post_train`/`commission_run`/`release`/`lobby`:
- **`build_evals`** — `harness_id -> bool`; advances a passive harness one level.
- **`defect`** — `policy_id -> bool`; violate an active policy at an enforcement
  catch-risk. `legal_moves` exposes a per-policy `defect_preview`
  (catch-prob/penalty/approval-hit) so the UI can warn before committing.
- **`litigation`** — `policy_id -> {side: challenge|defense, tier: amicus|join|fund,
  spend}`; post-passage court contest on active policies (standing-gated for `join`).
- **`sign_safe_harbor`** — bool; **wired** (`turn_pipeline` sets
  `lab.safe_harbor_signed`; `regulation.apply_compliance_detection` honors it for
  `safe_harbor_eligible` policies). Not a deferred stub.

## CLI (`cli/`) — what actually ships (§14 is future-tense; this is reality)

- **`cli/strategies.py` — fixed-policy archetypes** for scripted/batch play:
  `capability_rush`, `safety_first`, `balanced`, `fast_follower`,
  `jailbreak_hardener`, and the two-phase `rush_then_coast` (rush, then coast above a
  capability threshold). Each is a param dict (research order, assist level, release
  fraction, lobby stance, and an `apply_safety` flag — which, with the mode knob gone,
  controls whether the strategy researches and APPLIES safety advances to runs)
  compiled by `make_strategy`.
- **`cli/agent_session.py` — persistent move-by-move session** for an LLM agent or
  script: subcommands `new` / `act` / `status` / `postmortem`, with game state
  persisted to a pickle between process invocations.
- **`legal_moves.assist` econometrics** — every observation's `legal_moves` exposes
  the AI-assist trade-off knobs (`potency`, `speed_potency`, `max_reduction`,
  `speedup`) so a headless agent can predict an action's budget/time cost. Not in the
  §14 sketch.
- **Full action coverage on every path.** All `Action` fields are reachable from both
  the interactive human CLI and the agent paths. The interactive `run_game`
  (`_prompt_governance`) prompts for lobby spend, litigation (side/tier/spend), defect
  (with the catch-risk preview), eval-harness build/upgrade, and `sign_safe_harbor`;
  `agent_session._condense` surfaces the `eval_harnesses` board and advertises
  `litigation` / `defect` / `sign_safe_harbor` / `build_evals` in its `action_schema`.

## Observation: completed + in-progress advances (`engine/observation/observation_builder.py`)

- **`Observation.researched_advances`** — a list the frontend uses to show COMPLETED
  advances (both capability and safety) as read-only cards. Built by
  `_researched_advance_entries(lab)`, which emits per advance ONLY the non-secret,
  value-neutral fields `{id, name, version, phase, kind, what_it_does, completed_turn}`
  (`kind` = `"safety_advance"` for safety-advance ids, else `"capability"`). The hidden
  `ResearchedItem` fields (`contamination`, `researcher_model_id`,
  `researched_with_assist`) are TRUE state and never cross the boundary. Plain safety
  PROJECTS (measure/intervene) are not "advances" and are excluded.
- **Unified `_in_progress_entries`** — each in-progress process now also carries `name`
  and `phase` (looked up from the capability/safety-advance catalog via
  `_research_template`), so the frontend renders the SAME card for an in-progress item as
  for an available one. The live pretrain run reports as
  `{project_id:"pretrain_run", name:"Pretrain run", phase:"pretrain", ...}`.
- **Firewall audit lives in `tests/test_observation_firewall.py`** — walks the full player
  observation (incl. `legal_moves`) by KEY and asserts no forbidden TRUE-state key crosses
  (CLAUDE.md §8 method: keys, not substrings). Repeatable; passes.

## Frontend research-item component (`simple_frontend_v1/js/research.js`)

- **One state-keyed card renderer** replaces the old "text next to a button" research
  rows. States: `unresearched` (clickable card → the §7c detail modal in `warnings.js`,
  what-it-does first then the warning; carries the inline assist slider), `in_progress`
  (read-only: assist + years remaining), `completed` (read-only: `what_it_does`, no
  warning action — driven by `Observation.researched_advances`). `views.renderProjects`
  feeds it: capability panel, a combined safety panel (`safety_projects_available` +
  `safety_advances_available`), and a "Completed advances" panel grouped Capability/Safety.
- **Applied-safety UI replaced the dead post-train MODE selector.** `views.renderTraining`
  renders a "run a post-train round" toggle + a checkbox per
  `legal_moves.applicable_post_train_safety` → `post_train:{applied_safety:[ids]}`;
  `views.renderPretrain` renders checkboxes per `legal_moves.applicable_pretrain_safety` →
  `commission_run:{compute, applied_safety:[ids]}`. `core.budgetLeft()` mirrors
  `rules.applied_post_train_round_budget` for the round cost preview.
- **`core.esc()`** — a small HTML-escaper applied to every catalog value interpolated into
  research/modal innerHTML templates, hardening against the user-entered lab-name stage.

## Frontend (`simple_frontend_v1/js/main.js`) — start-game gate

- **Mandatory new-game modal.** On load, `init()` forces `showNewGame({initial: true})`,
  which renders without a cancel button (and the overlay has no backdrop-dismiss), so a
  game cannot be skipped. A module-level `started` flag is set only when `newGame()`
  completes; `render()` keeps `#endturn` disabled and `endTurn()` early-returns until
  then. A turn cannot be advanced until a game is explicitly started through the modal.

## Lab identity: name + ticker (`backend_v1/engine/lab.py`, `engine/game.py`, server)

- **`Lab.ticker`** (new field, default `""`) — short public stock-style ticker (e.g.
  "YOU", "MIS"). PUBLIC/legible like `name`, not hidden state, so it crosses the
  observation boundary freely. Always already-sanitized by the time a Lab is built.
  Intentionally absent from `Lab.snapshot()` (keeps the golden-master TRUE-state digest
  stable); it reaches the frontend via the server's `lab_tickers()` map and
  `rival_public[].ticker`, never via the logged true state.
- **`game.new_game(..., player_lab_name=None, player_ticker=None)`** — accepts the
  player's chosen identity, sanitizes it, replaces the old hardcoded `"Your Lab"`, and
  gives every rival a derived ticker.
- **Sanitization helpers (in `game.py`, the single trust boundary for this input):**
  `sanitize_lab_name` (≤ `MAX_LAB_NAME_CHARS`=40, control-char strip, empty→
  `DEFAULT_PLAYER_LAB_NAME`="Your Lab"), `sanitize_ticker` (≤ `MAX_TICKER_CHARS`=6,
  control-char strip, uppercased, empty→derived from name), `derive_ticker_from_name`
  (first 3 alphanumerics uppercased, else `DEFAULT_PLAYER_TICKER`="YOU"). None raise.
- **New-game request fields:** `POST /api/new` now reads `lab_name` and `ticker` from the
  body (forwarded raw; `new_game` sanitizes). `state_payload` gains a `lab_tickers`
  map (parallel to `lab_names`). `rival_public` entries gain a `ticker` key.
- **Frontend:** `core.TICKERS` live binding (from `payload.lab_tickers`); the new-game
  modal has lab-name + ticker inputs with a name→ticker auto-derive that stops once the
  player edits the ticker (`onLabNameInput`/`onTickerInput`, registered on `window`).
  Every render of a lab name/ticker (legend, rivals, benchmarks, Truth) goes through
  `core.esc()`.
- **Test:** `tests/test_lab_identity_sanitization.py` covers the helpers + `new_game`
  with script-tag/overlong/control-char/empty/non-string inputs and rival ticker derivation.

## Market-cap graph (`simple_frontend_v1/js/views.js` `drawCaps`)

- **Inline SVG, built in JS** (was a `<canvas>`). `index.html` holds an empty
  `<svg id="capgraph-big">`; `drawCaps()` sizes its `viewBox` to the displayed box,
  clears it, and appends gridlines / polylines / tab tickers / date labels. Reads only
  `HIST` (per-turn `{turn, caps:{labId:cap}}`), `TICKERS`, `NAMES`, `OBS.market_caps`.
- **Linear y-axis** (`cap/maxCap`), not the old `log10`. x is linear in turn index.
- **Tab tickers** — one `<g class="cap-tab">` pinned at each line's right end: a single
  `<path>` shaped triangle(tip facing LEFT)+rectangle+right-semicircle, sized to the
  ticker. Text set via `textContent` (XSS-safe), forced sans-serif + uppercase in CSS so
  the later serif skin leaves it.
- **Hover** wired with `addEventListener` (no new `window` handlers): hovering a line or
  its tab thickens the line (`.cap-hover`) and scales the tab.
- **Interim noise (DISPLAY-ONLY)** — between each pair of real quarter points the line
  wiggles like a stock chart. Method (matches FIX_ITEMS): split the quarter into N steps,
  build a zero-sum shuffled trough list, value at step i =
  `startCap*exp(cumTrough(i) + i*ln(endCap/startCap)/N)`, so endpoints stay EXACT. The
  shuffle uses a self-contained mulberry32 PRNG (`makeDisplayPrng`) seeded per
  `(lab, quarter)` and cached (`_capWiggleCache`) — deterministic across re-render/resize,
  and wall-of-glass separate from the seeded game RNG (`backend_v1/engine/rng.py`). It
  never touches game state; the golden-master digest is unchanged.
- **Date x-axis** derived on the frontend: one turn == one quarter from `CAP_START_YEAR`
  (2021, mirrors backend `config/constants.py` START_YEAR/DT_YEARS), labelled `"Q<n> <year>"`,
  thinned to ~10 labels.

## User-facing strings — centralized, i18n-ready (Stage C)

Player-facing display copy is named and discoverable in known locations, so a
translator can find every string by key without reading engine/render logic.

- **Frontend strings table:** `simple_frontend_v1/js/strings.js` — `STRINGS` object
  (dotted, area-namespaced keys → English) plus `t(key, params?)`. `t()` does simple
  `{placeholder}` interpolation, returns the key on a miss (loud), and returns RAW
  text (callers esc() any untrusted data they interpolate). Re-exported via `core.js`
  so views import `t` from core. To localize: swap `STRINGS` for another table; no
  renderer changes.
- **Backend strings module:** `backend_v1/content/strings.py` — the loose inline
  authored strings that used to live in engine code: `DEFAULT_PLAYER_LAB_NAME`,
  `DEFAULT_PLAYER_TICKER`, `RIVAL_LAB_NAMES`. `engine/game.py` imports + re-exports
  them; values unchanged (attribution/golden-master safe).
- **Catalogs ARE their own strings tables** (referenced in place, not duplicated):
  `engine/observation/warnings.py` `CATALOG`, and the capability/safety advance
  catalogs' `name`/`what_it_does`/`risk_blurb` fields. Benchmark/finding/policy/
  post-mortem text reaches the UI as backend content through the observation.
- **Left in markup:** `index.html` static labels/headers/prose (rendered once, never
  re-generated) are intentionally not centralized; see ISSUES.md Stage C.
