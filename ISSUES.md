# ISSUES — build notes (companion to design_doc.md)

Per CLAUDE.md §5: contradictions/underspecifications found, liberties taken, and
implementation choices with design consequences. Newest task at the bottom.

---

## Research-item "what it does" descriptions (§8b)

Implemented the §8b requirement that each capability `ResearchItem` carry TWO
separate plain-language fields for a zero-knowledge player: a value-neutral
**WHAT IT DOES** (first) and the risk framing (after).

- **New field `what_it_does`** on `ResearchItem` (`capabilities_research_item.py`),
  placed before the existing `risk_blurb`. Surfaced through `legal_moves`
  (`capability_projects_available[*].what_it_does`) and shown FIRST in the
  frontend per-item modal, with the risk layered after.
- **Content liberty (flag for review, per §0).** I authored the `what_it_does`
  string for all 19 nodes. RLHF reuses the design doc's exemplar verbatim; the
  other 18 are mine — drafted neutral, concept-teaching, and benefit-conveying
  (the "pull"), held to the §0 WHY-not-THAT standard. These are drafts for the
  designer to tune, not settled copy.
- **Interpretation — field 2 ("how it risks").** §8b calls field 2 "the §7c
  warning." In the modal I render the node's existing per-node `risk_blurb` as
  that node-specific risk line (after `what_it_does`), followed by the GENERIC
  §7c catalog warnings from `observation/warnings.py` (e.g. `high_ai_assist`,
  emphasised as the assist slider goes high). So a capability item shows: what it
  does → its own risk → the knob-level warnings. Noting the two-granularity
  blend in case the designer wants a single authored field instead.
- **Scope.** §8b's two-field rule is written for the capability `ResearchItem`
  (the tech tree). Safety projects (§7b) already carry a neutral `blurb`, which
  the modal reuses as their "what it does"; I did NOT add a `what_it_does` field
  to `SafetyProject`. Revisit if safety projects should get a dedicated neutral
  description distinct from `blurb`.

---

## Doc↔code reconciliation audit (2026-06-18)

A pass comparing the code against `design_doc.md` and `CLAUDE.md`. CLAUDE.md
best-practice fixes were applied in code; the undocumented mechanisms were written
up in the new `IMPLEMENTATION_DETAILS.md`. The items below are for the **designer**:
contradictions and stale doc sections, with proposed revisions. The design doc was
**not** edited — these are proposals.

### A. Contradictions (design-doc section → what the code does)

- **§5 catastrophe-severity path.** Doc: severity is `goal_misalignment ×
  general_capability × self_preservation` (a product; deception merely "governs
  whether you saw it coming"). Code: `event_catalog.py` computes severity as
  `model.misalignment_composite() × general_capability / CAP_MAX`, where
  `misalignment_composite()` (`model.py`) is a **weighted sum**
  `0.55·goal_mis + 0.30·self_pres + 0.15·deception` (weights now named
  `COMPOSITE_W_*`). Two divergences: (i) sum-of-dispositions vs product, and (ii)
  **deception contributes to severity**, which §5 says it should not.
  *Proposed revision:* either update §5 to describe the realized two-step shape
  (disposition composite × capability), explicitly listing deception's weight, or
  decide the code should drop deception from the severity composite to match §5.

- **§4.3 / §9 external-researcher tips vs CLAUDE.md §2 (already fixed in code).**
  `observation/guidance.py` previously read `lab.best_true_general()` — TRUE,
  hidden, including unreleased in-training models — to time/hedge frontier tips,
  violating CLAUDE.md §2 ("guidance reads observations only"). Fixed to read
  `world.frontier_measured_general` (the public, released, benchmarked frontier,
  §7). The golden master did not move (the tested matrix uses non-sparse guidance,
  which consumes no RNG). *Proposed revision:* §4.3/§9 should state that
  frontier-proximity tips ride the **public/measured** frontier, not TRUE state.

- **§11 file map is stale (authoritative-but-wrong).** Modules missing or
  mislabeled: `events/buyouts.py` (absent), `governance/gov_news.py` (named in §10c
  prose, absent from the map), `engine/turn_context.py` and `engine/rules.py`
  (absent), and the `evaluations.py` build/upgrade harness system (under-mapped vs
  §7). *Proposed revision:* add these to the §11 map (see `IMPLEMENTATION_DETAILS.md`
  for what each does), and drop the `[E]/[N]/[R]` "per screenshot" build-status tags
  — everything is built, so they no longer carry information (see §D below).

- **README pointer (fixed directly — README is not the design doc).** `README.md`
  said "See `NOTES.md` for questions"; CLAUDE.md §0 already calls that stale. Updated
  to point at `ISSUES.md`.

### B. Note: `JOB_LOSS_APPROVAL_*` scales offset

`finances.run_job_loss_drag` multiplies the approval rate by
`JOB_LOSS_APPROVAL_INTENSITY_SCALE` (10) then by `JOB_LOSS_APPROVAL_AMOUNT_SCALE`
(0.1) — net ×1. Named for legibility but kept value-identical to preserve the golden
master; a designer may want to collapse them to a single honest coefficient.

### D. Dead-weight design-doc sections (proposed revisions)

- **§14 "Headless / CLI runthrough" — now historical.** Written entirely future-tense
  ("Why it's nearly free", "What's needed", "Doable as a CLI? — yes", the build-order
  recommendation) for a CLI that fully ships: `cli/run_game.py`,
  `cli/agent_session.py`, `cli/strategy_report.py`, `cli/strategies.py`. Every
  "What's needed" bullet and every mode (interactive / agent / scripted / batch) is
  implemented. *Proposed revision:* replace §14 with a one-line present-tense pointer
  to `README.md` (run commands) + `IMPLEMENTATION_DETAILS.md` (what actually shipped),
  or move the whole section to a "historical / design rationale" appendix.

- **§11 build-status tags.** The `[E]/[N]/[R]` "(per screenshot)" annotations on every
  module are historical scaffolding from before the build; they now mislead more than
  inform. *Proposed revision:* drop them (see §A above).

- **§12 "Resolved this session (kept as a record, no longer open)".** A record of
  settled decisions; a candidate for archiving to keep the live "open decisions"
  index scannable. Flagged lightly — designer's call, not urgent.

---

## Task: Advance-driven training — remove the post-train "safety knob" (Stage A)

Replaced the per-round post-train MODE knob with researched, applied SAFETY ADVANCES
(FIX_ITEMS.md "Training": "No more safety knob"; design §5b preventive stances, §8b
two-phase training + contamination vector).

### 1. Mode knob removed
- Deleted `POST_TRAIN_MODES` (config/constants.py) and the `mode` parameter of
  `post_train_round()` plus every `mcfg[...]` read. Deleted the now-unused
  `JUMP_RISKY_BONUS` constant (it was only the "capability-mode adds risk" lever) and
  its `DIFFICULTY_SCALED` entry.
- The `mode` field of the `post_train` action is gone; the action now carries
  `applied_safety` (a list of researched safety-advance ids). `commission_run` likewise
  gained `applied_safety` (pretrain advances). Updated validate_action, turn_pipeline,
  the rival controller, the CLI (run_game / agent_session / strategies), the postmortem
  counterfactuals, and the warnings mapping.
- **Baseline preserved:** a post-train round with NO advances applied reproduces the
  old "balanced" mode exactly — new constants `POST_TRAIN_BASE_ELICITATION_MULT = 0.65`
  and `POST_TRAIN_BASE_ALIGNMENT_EFFORT = 1.00` are the former balanced multipliers, so
  removing the knob does not silently shift difficulty. (The golden master still moved —
  the SCRIPTED player's action stream changed shape — which is the expected
  action-stream effect per CLAUDE.md §8, not an RNG/firewall change. Re-recorded; passes.)

### 2. New safety advances (DATA — `engine/research/safety/safety_advance_item.py`)
Researched with the SAME machinery as capability advances (ResearchItem-style template
→ ResearchProcess → ResearchedItem), so they ALSO carry hidden contamination =
ai_assist × researching-model goal_mis × contamination_tier. They land in
`lab.researched_advances` alongside capability advances; a new project kind
`"safety_advance"` distinguishes them in `rules.project_template`. All numbers are
[TUNE] OPTIMISTIC DRAFTS per design §0 — push them bleaker.

PRETRAIN (act in commission_run / complete_pretrain):
- **data_cleaning** — `pretrain_contamination_mult 0.55`, `base_goal_mis_mult 0.80`,
  `contamination_tier 0.6`. Scrubs accumulated pretrain contamination + lowers the
  base goal-mis baseline.
- **aligned_synthetic_data** (prereq data_cleaning) — `synthetic_contamination_mult 0.30`
  (cuts the synthetic-data PATH's injected contamination ~70% when applied), but
  `contamination_tier 1.6` (HIGH): if researched WITH AI-assist it is "hugely
  contaminated", and its own researched contamination is folded straight back into
  the base. This makes the §8b contamination-vector lesson tangible: assisting the
  safety tool poisons it.

POST_TRAIN (act per post-train round; preventive effects = "the REAL lever"):
- **reward_hacking_penalties** — `emergence_slope_mult 0.78`, `correlated_jump_mult 0.55`,
  `elicitation_mult 0.92`, `round_budget 0.10`.
- **inoculation_prompting** — `emergence_slope_mult 0.82`, `correlated_jump_mult 0.62`,
  `elicitation_mult 0.94`, `round_budget 0.08`.
- **deliberative_alignment** (prereq reward_hacking_penalties) — `effectiveness_bonus 0.10`
  (raises corrective EFFECTIVENESS, the §5b real lever, clamped ≤1), `proxy_gap_mult 0.70`
  (shrinks the fake-the-objective gap), `alignment_effort_bonus 0.06`,
  `elicitation_mult 0.90`, `round_budget 0.12`.

Effects are read GENERICALLY off the template fields and combined in post_train_round /
complete_pretrain (multipliers multiply, bonuses add) — NO per-advance branch anywhere.
Each advance carries the two §8b fields (what_it_does FIRST, risk_blurb AFTER,
magnitude-free).

### 3. Per-run application
The player chooses which UNLOCKED advances to apply to a given run via the action's
`applied_safety` list (validated: must exist, be the right phase, and be researched).
`rules.applied_post_train_round_budget` is the single source of truth for the round's
work-budget (baseline + each applied advance's `round_budget`). legal_moves exposes
`safety_advances_available` (to research), `applicable_pretrain_safety` /
`applicable_post_train_safety` (researched, appliable to a run). Drivable headlessly:
CLI strategies research+apply by an `apply_safety` flag; the rival applies advances by
its `safety_priority` disposition.

### Forks / liberties flagged for review
- **FORK — where safety advances live.** I put researched safety advances into the
  SAME `lab.researched_advances` dict as capability advances (keyed by id, with
  contamination), rather than a parallel store. Rationale: the fix item demands the
  identical contamination machinery, and every existing reader of `researched_advances`
  already guards with `if nid in CAPABILITY_TREE_BY_ID`, so safety advances coexist
  without touching revenue / observation / guidance / finance reads. The cost: the dict
  is now "researched advances of any kind", not "capability advances" — noted so a
  future reader isn't surprised.
- **LIBERTY — effectiveness_bonus as additive clamp.** Deliberative alignment raises
  corrective EFFECTIVENESS by an additive `effectiveness_bonus` clamped to ≤1 (a fix
  can't become more than fully real). The design doc names "raise corrective
  EFFECTIVENESS" qualitatively; the additive-then-clamp shape is my choice. [TUNE]
- **LIBERTY — synthetic-data contamination model.** "aligned synthetic data" scales the
  synthetic PATH contamination by `synthetic_contamination_mult` AND adds its own
  researched contamination back. Both the split and the magnitudes are invented. [TUNE]
- **KNOWN BREAK (out of scope) — FRONTEND not wired.** `simple_frontend_v1/js/views.js`
  still renders the old `post_train_modes` selector and emits `{mode}`. Backend now
  ignores a stray `mode` key (defaults to a safe baseline round — no crash, no silent
  corruption), but the post-train UI won't expose the new applied-safety choice until
  the frontend stage wires `applied_safety` from `legal_moves.applicable_*_safety`.
  Left untouched per this stage's "do not touch frontend" constraint.

---

## Finance fixes — post-release growth + early base investment (§9b)

Two FIX_ITEMS Backend items in the finance/economy subsystem only. Reproduced both
headlessly (throwaway `diag_finance.py`, since deleted) driving a scripted game with a
steady release cadence and logging per-turn market_cap / last_score / investment_momentum
/ investment_rate / revenue_rate for the player lab.

### Fix 1 — market caps declined/plateaued the turns AFTER a release
**Diagnosed root cause (with evidence, NOT the prior momentum suspect):** the prior
`investment_momentum` work was sound — momentum and `last_score` both climb smoothly turn
over turn after a release. The decline came from the **market-cap valuation coupling to the
spiky per-turn `investment_rate`**, which in turn was flung by **instantaneous** revenue
growth:
- `run_investment` computed `growth_multiplier` from the SINGLE-TURN revenue ratio
  `(total_rev/prev_total_rev - 1)/dt`. On a release turn a new higher-capability model
  enters the world revenue pie → that ratio SPIKES (observed ≈ +4.9/yr → growth_multiplier
  ≈ 8.4 → total_investment and the player's `investment_rate` balloon, e.g. 14,800). The
  NEXT turn revenue mean-reverts / dips → ratio goes NEGATIVE → growth_multiplier collapses
  to ≈0.2–0.6 → `investment_rate` craters back to ≈1,000.
- `update_market_caps` set the cap target to
  `MARKET_CAP_SCALE * score * max(investment_rate, 1.0) + 0.5*revenue_rate`. Because the
  anchor was the raw, just-spiked-then-crashed `investment_rate`, the cap SPIKED on the
  release turn then DECLINED for the following turns even though `score` was still rising.
  This is suspect (c)+(d) in the brief (cap couples to the spiky flow); suspects (a) and (b)
  were checked and ruled out.

**Fix (smallest principled change to dynamics + tuning):**
1. `world.smoothed_revenue_growth_per_year` — an EMA of the single-turn revenue growth
   (`REVENUE_GROWTH_SMOOTHING_ALPHA`). `growth_multiplier` now keys off the smoothed slope,
   so total investment no longer whipsaws release-turn → next-turn. §9b: investment rewards
   the SLOPE measured BETWEEN releases, not an instantaneous spike.
2. `lab.smoothed_investment_rate` — an EMA of the live `investment_rate`
   (`INVESTMENT_ANCHOR_ALPHA`), used as the market-cap SIZE anchor in place of the raw rate.
   The market cap now tracks the smoothly-rising `score` (the §9b forward-looking /
   slope-weighted signal), so a healthy release keeps the staircase climbing.

**Cliff preserved:** isolated test (ship once, then sit idle past the grace window) still
falls — momentum grows through grace then decays, market cap falls steadily, base
investment decays. The §9b cliff for genuine stalls/misses is intact; only the spurious
post-healthy-release decline is gone.

**Before vs after (player, fast_follower, seed 0, post-release turns):**
- BEFORE: t25 REL 61,326 → 50,224 → 48,466 → 40,549 → 34,168 (declining each turn).
- AFTER:  t25 REL 48,872 → 53,505 → 55,461 → 60,581 → 65,653 (climbing each turn).

### Fix 2 — early/seed base investment that decays if you do nothing
`total_investment` scales with `frontier_measured_general`, which is 0 before the first
release → investment was ~0 early. Added a modest per-YEAR base flow:
- `lab.base_investment_rate` — a persistent accumulator, seeded at
  `BASE_INVESTMENT_PER_YEAR` in `new_game` (player AND rivals, so no seed advantage),
  advanced one step per turn in `update_base_investment`. It HOLDS at the base level while
  the lab is "active" and DECAYS (`exp(-BASE_INVESTMENT_DECAY_PER_YEAR*dt)`) toward zero
  when idle.
- "Active" = has shipped a model OR has research/pretrain/post-train work in progress
  (`release_history` or `in_progress`/`training_run`/`model_in_training`). LIBERTY: this
  definition of "inactive" is my call — note for review.
- The base flow is ADDED on top of the score-divvied pie (it is the lab's own seed money,
  not a share), so it dominates early when the pie is ~0 and tapers as real investment
  takes over.

### Every new / changed number — ALL DRAFTS [TUNE], lean BLEAKER per §0
The designer wants margins bleaker; these are optimistic-skewed first cuts:
- `REVENUE_GROWTH_SMOOTHING_ALPHA = 0.35` — EMA speed for smoothed world revenue growth.
- `INVESTMENT_ANCHOR_ALPHA = 0.30` — EMA speed for the market-cap investment anchor.
- `BASE_INVESTMENT_PER_YEAR = 90.0` ($M/yr) — seed flow while active. Modest: a cautious
  lab that barely ships still ends small (cap ~2.7k vs aggressive ~80k+ in a 50-turn run),
  so it does not trivialize early cash. Could go LOWER if early cash still feels generous.
- `BASE_INVESTMENT_DECAY_PER_YEAR = 1.6` — decay rate once idle (~half-life under a year).

### Determinism / firewall
All draws still go through `rng.amount_per_dt`; the new EMAs are deterministic. No new field
crosses `observation_builder` (only the existing legible `investment_rate`/`revenue_rate`/
`market_cap` are observed) — firewall untouched. Golden master re-recorded (finance dynamics
moved by design): new EXPECTED block + WHY comment in tests/test_golden_master.py; passes.

---

## Research-item observation + state-machine UI + assist-warning bug (Stage D)

This stage was UI-and-observation only: it surfaced researched/in-progress advances
through the firewall, replaced the dead post-train MODE selector, unified the research
rows into a state-keyed card component, and fixed the unconditional assist warning. No
training/finance/economy MECHANIC changed, so the golden master did NOT move (verified —
no re-record).

### Part 1 — observation fields added (firewall-safe)
- New `Observation.researched_advances: list`. Per completed advance (capability AND
  safety) the builder emits ONLY: `{id, name, version, phase, kind, what_it_does,
  completed_turn}`. `kind` is `"safety_advance"` for safety-advance ids, else
  `"capability"`. The hidden ResearchedItem fields — `contamination`,
  `researcher_model_id`, `researched_with_assist` — are TRUE state and never cross.
- `_in_progress_entries` UNIFIED: each entry now also carries `name` and `phase`
  (looked up from the catalog template) so the frontend can render the same card for an
  in-progress item that it renders for an available one. The live pretrain run reports
  as `{project_id:"pretrain_run", name:"Pretrain run", phase:"pretrain", ...}`. No
  process-internal secret (assisting-model id/goal-mis, contamination source) crosses.
- FORK resolved: plain safety PROJECTS (measure/intervene) don't carry the §8b
  what_it_does/risk fields and aren't "advances", so they are NOT in
  `researched_advances` (which is the completed-ADVANCE catalog). `_research_template`
  returns None for them, and `_researched_advance_entries` skips them. They already show
  via `legal_moves.safety_projects_available`.
- AUDIT: new `tests/test_observation_firewall.py` plays scripted balanced games and
  walks the FULL player observation (incl. legal_moves) by KEY (not substring, per
  CLAUDE.md §8), asserting no key in {true_alignment, true_capability, concealment,
  foundational_floor, suppression, hidden_history, contamination, researcher_model_id,
  researched_with_assist} crosses. A second test asserts each `researched_advances` card
  carries ONLY the allow-listed fields and that the path is actually exercised.

### Part 2 — unified research-item component (`simple_frontend_v1/js/research.js`)
- ONE module renders an item card keyed by STATE: `unresearched` (clickable card →
  existing §7c detail modal, what-it-does first then warning; carries the inline assist
  slider), `in_progress` (same card, read-only: assist + years remaining), `completed`
  (read-only card showing what_it_does, no warning action — uses the Part-1 fields).
- Capability vs safety stay in their own panels; completed advances render in a new
  "Completed advances" panel, internally grouped Capability / Safety.
- LIBERTY: the clickable card opens the modal on body click; the assist row calls
  `event.stopPropagation()` so editing assist doesn't navigate. Card CSS (`.ritem`) is
  the existing palette (no skin change — that's a later stage).

### Part 3 — applied-safety UI replacing the dead MODE selector
- Post-train: a "run a post-train round" checkbox plus a checkbox per
  `legal_moves.applicable_post_train_safety` advance → `post_train: {applied_safety:[ids]}`.
- Pretrain: checkboxes per `legal_moves.applicable_pretrain_safety` advance at commission →
  `commission_run: {compute, applied_safety:[ids]}`.
- Removed dead `PREVENTIVE_MODES` / `PT_MODE_HINT` / `setPostTrain` / the
  `post_train_modes` rendering. `budgetLeft()` now mirrors
  `rules.applied_post_train_round_budget` (base `post_train_round_budget` + each applied
  advance's `round_budget`) instead of the old flat 0.30.

### Assist-warning bug fix (`warnings.js`)
- `projectWarnings()` now pushes the high-ai-assist warning ONLY when the item's assist
  value > 0 (was unconditional). Emphasis behavior at high assist preserved. Also added
  `esc()` escaping to every catalog-value interpolation in the modal as XSS-hardening
  ahead of the user-entered-lab-name stage (warning copy itself is fixed backend data).

### Verification
- `tests.test_golden_master` PASSES unchanged (no re-record). New
  `tests.test_observation_firewall` PASSES. Headless `cli.run_game --seed 1
  --max-turns 30 --policy balanced` runs clean. Frontend verified statically: per-file
  brace balance, every inline on*= handler is in main.js Object.assign(window,...), every
  import resolves to an export; all js modules serve 200 text/javascript.

---

## Stage E1 — Game start: dev-mode gate + lab name/ticker (security-sensitive)

### Part 1 — start-gate root cause + fix
- **Investigation:** The reported "can't start a game without selecting dev mode"
  symptom did NOT reproduce in the current code. The start flow does not depend on the
  dev checkbox: `newGame()` reads `$("ng-dev").checked` (false is fine), calls
  `setDevMode(false)` (which just hides the Truth tab + switches to Market), POSTs
  `/api/new`, sets `started=true`, and re-enables `#endturn`. Verified the backend
  builds a game with dev off (it never sees the dev flag — that flag is frontend-only),
  and the dev-off path renders without throwing. The symptom predates commit a09bb44,
  which already introduced the `started` flag + mandatory modal; that change happens to
  have fixed the original blocker.
- **Hardening applied anyway** (so the requirement is bulletproof and the report can't
  re-occur): `newGame()` now reads dev defensively (`$("ng-dev") ? .checked : false`)
  with a comment stating dev mode is OPTIONAL and unchecked is the normal path; and it
  only flips `started`/closes the overlay if the `/api/new` response has no `errors`
  (on error it shows the message and leaves the modal open to retry). The Truth tab
  stays dev-gated exactly as before (hidden unless ticked; served from `/api/truth`).

### Part 2 — lab name + ticker design
- **Auto-derive rule:** ticker defaults to the first 3 ALPHANUMERIC characters of the
  name, uppercased, and tracks the name as the player types — UNTIL the player edits the
  ticker field, after which auto-derive stops (`tickerManuallyEdited` latch in main.js).
  Backend `derive_ticker_from_name()` mirrors this exactly so the stored ticker matches
  the live preview. Rivals get tickers from the same derivation.
- **Validation limits (server-side, in `game.py`, untrusted input):**
  - name: ≤ 40 chars (`MAX_LAB_NAME_CHARS`), control chars stripped (incl. newline/tab),
    trimmed, empty → `"Your Lab"`.
  - ticker: ≤ 6 chars (`MAX_TICKER_CHARS`), control chars stripped, uppercased, empty →
    derived from the (already-sanitized) name; if that's empty too → `"YOU"`.
  - `sanitize_lab_name` / `sanitize_ticker` never raise — bad/non-string input becomes a
    default. The server forwards raw `lab_name`/`ticker` from the POST body; `new_game()`
    sanitizes before constructing any Lab, so the CLI and any direct POST get the same
    guarantee. Markup characters are NOT stripped server-side (a `<` in a name is a valid
    label char); XSS is prevented at the render boundary instead (see below).

### XSS-escaping audit (render sites hardened to route through `esc()`)
All sites that interpolate a (possibly user-authored) lab name or ticker into innerHTML:
- `views.drawCaps` legend (NAMES + TICKERS) — now `esc()` on both.
- `views.renderBenchmarks` score list (NAMES) — now `esc()`.
- `views.truthModelCard` (NAMES + model.id) — now `esc()` (Truth tab too; §2 applies).
- `views.renderRivals` (rival.name + new rival.ticker tag) — now `esc()`.
- Not user data (left as-is): `card.name`/`card.blurb`/`card.domain` (benchmark catalog),
  `policy.name` (policy catalog), model ids (`player-M1`, backend-generated),
  research `item.name`/`advance.name` (already `esc()`'d in a prior stage).
- Defence in depth: server length-clamps + strips control chars; the new
  `tests/test_lab_identity_sanitization.py` covers script-tag/overlong/control/empty/
  non-string inputs at both the helper and `new_game()` levels.

### Plumbing summary
request `{lab_name, ticker}` → `server /api/new` → `Session` → `new_game(player_lab_name,
player_ticker)` → sanitize → `Lab.name` / new `Lab.ticker` field → server `lab_tickers()`
(parallel to `lab_names()`) in `state_payload` + `rival_public[].ticker` in the
observation → frontend `core.TICKERS` live binding → legend / rivals / benchmarks render.
`Lab.ticker` is intentionally NOT in `lab.snapshot()` so the golden-master TRUE-state
digest is unchanged (ticker reaches the UI via the separate `lab_tickers` map).

### Verification
- `tests.test_golden_master` PASSES unchanged (no re-record). New
  `tests.test_lab_identity_sanitization` (13 tests) + `tests.test_observation_firewall`
  PASS; full suite 16 tests OK. `cli.run_game --seed 1 --max-turns 20 --policy balanced`
  runs clean. Live server: normal name auto-derives ticker, malicious name+ticker clamp
  to 40/6, empty → "Your Lab"/"YOU", rivals carry tickers. Frontend static: brace +
  backtick balance per file; new `onLabNameInput`/`onTickerInput` in main.js
  `Object.assign(window,...)`; `TICKERS` export/import resolves; js modules serve 200
  text/javascript.

---

## Stage E3 — Market-cap graph rewrite (SVG, linear, hover, tab tickers, interim noise, dates)

Scope: rewrote ONLY the market-cap graph renderer (`simple_frontend_v1/js/views.js`
`drawCaps`) + the `<canvas id="capgraph-big">` → inline `<svg>` swap in `index.html` +
the resize hook in `main.js`. No finance/backend/training/new-game/skin changes.

### What changed
- **canvas → inline SVG.** The graph is now an `<svg id="capgraph-big">` built/cleared
  in JS each `drawCaps()`. Needed for hover hit-testing and crisp pinned edge labels.
  The old `#capgraph-big` CSS (size/bg) still applies; added `display:block` + the
  graph-internal classes (`.cap-line`, `.cap-tab`, `.cap-tab-text`, `.cap-axis-text`,
  `.cap-gridline`).
- **Linear y-axis** (was `log10`). `yForCap = plotBottom - (plotBottom-plotTop)*cap/maxCap`.
- **Hover.** Listeners attached in JS via `addEventListener` (NOT inline `on*=`, so
  nothing new is added to `window`). Hovering a lab's line or its tab toggles
  `.cap-hover` on the line (thicker stroke) and scales the tab `<g>` by 1.18.
- **Tab tickers pinned right.** One `<g class="cap-tab">` per lab at the line's last
  point: a single `<path>` = triangle (tip facing LEFT at the line end) + rectangle +
  right semicircle, sized to the ticker text. Ticker text is set via `textContent`
  (XSS-safe for the player-authored ticker) and forced sans-serif + uppercase in CSS
  so the later serif skin won't touch it.
- **Dates along the bottom.** Derived from the turn index, not from any new backend
  field: one turn == one quarter from `CAP_START_YEAR` (2021, mirrors backend
  `config/constants.py` START_YEAR/DT_YEARS=0.25). Label = `"Q<n> <year>"`, thinned to
  ~10 labels max so they don't overlap.

### Interim noise — used the designer's formula EXACTLY
`capWiggleSteps(lab, turn, startCap, endCap)`:
  - split each quarter into `CAP_WIGGLE_STEPS_PER_QUARTER` (15) steps;
  - build a symmetric zero-sum trough list (centered indices × `CAP_WIGGLE_TROUGH_SCALE`,
    sums to 0), then SHUFFLE it (Fisher–Yates);
  - displayed value at step i = `startCap * exp( cumulativeTrough(i) + i*ln(growth)/N )`,
    `growth = endCap/startCap`. Cumulative-trough term is mean-zero ⇒ endpoints land
    EXACTLY on the real quarter values; the `i*ln(growth)/N` ramp tilts the interior up.
  No "significantly cleaner equivalent" substituted — implemented as specified.

### Determinism of DISPLAY (not the game RNG)
The wiggle is purely cosmetic and must never touch game state or the seeded game RNG
(CLAUDE.md §0b/§4). The shuffle uses a tiny self-contained mulberry32 PRNG
(`makeDisplayPrng`) seeded by `(turnIndex+1)*1000003 + hashLabId(lab)` — stable per
(lab, quarter). Result is cached in `_capWiggleCache` keyed `lab@turn`, so the same
(lab, quarter) yields the same wiggle on every re-render/resize (no jitter) and we
shuffle once. This PRNG is wall-of-glass separate from `backend_v1/engine/rng.py`.

### Liberties / [TUNE] flags (cosmetic only — no balance impact)
- `CAP_WIGGLE_STEPS_PER_QUARTER=15`, `CAP_WIGGLE_TROUGH_SCALE=0.012`, tab geometry
  consts, `CAP_TAB_CHAR_WIDTH=7.5` (approx monospace advance for tab sizing). All
  display-only; tune for looks, they cannot affect the simulation.
- Date axis duplicates START_YEAR(2021)/quarter cadence on the frontend rather than
  threading a date through the observation — the graph is display-only and OBS already
  carries `year`, so this stays a pure-presentation derivation.

### Verification
- Per-file brace/paren/bracket/backtick balance OK (views.js, main.js).
- Hover uses `addEventListener`, so NO new `window` handlers needed; imports unchanged
  (drawCaps reuses already-imported `$, esc, COLORS, TICKERS, NAMES, OBS, HIST, fmt$`).
- Server: `/js/views.js` + `/js/main.js` serve 200 text/javascript; `/` serves 200 with
  `<svg id="capgraph-big">` present and zero `<canvas id="capgraph-big">` refs.
- `tests.test_golden_master` PASSES unchanged (pure frontend change).

---

## Stage E2 — UX skin: light, serif, editorial (CSS-only restyle)

Pure visual skin change in `simple_frontend_v1/index.html` `<style>` block. No JS,
markup, action wiring, graph-drawing, or backend touched. Reversible/contained to CSS.

### New palette (light "warm paper" theme — replaces dark monospace)
- `--bg:#f7f5ef`  (warm off-white paper)
- `--panel:#fdfcf8`  (panel sits just off the page)
- `--panel2:#f1eee5`  (recessed surfaces: chips, benches, ritems, bars, tags)
- `--line:#ddd8cc`  (hairline rule)
- `--txt:#1f2328`  (near-black ink; AA on all surfaces)
- `--dim:#6b6256`  (muted brown-grey; passes AA for secondary text)
- `--acc:#1a5fb4`  (darkened blue — readable on light; was #4fb3ff)
- `--warn:#9a6400`  (amber/ochre — readable on light; was #ffb347)
- `--bad:#b3261e`  (deep red — readable on light; was #ff6868)
- `--serif` (NEW var): `Georgia,"Iberian","Times New Roman",Cambria,"Liberation Serif",serif`

### Type
- Body font switched from `"SF Mono",Menlo,…monospace` to the `--serif` stack
  (14px/1.5). System serifs only — no web-font fetch (server is stdlib/offline).
- `h3` headings kept uppercase + letter-spaced but now serif/bold for editorial feel.
- Primary buttons & active nav tab: accent fill with WHITE text (was dark #06121c,
  which was tuned for the bright-on-dark accent and would be illegible on the new
  darker accent).

### Clean-lines treatment
- Radii trimmed (buttons/inputs 4px→3px). Restrained shadows: overlays now use a
  light scrim `rgba(31,35,40,.45–.55)` instead of near-black; only the modal-card
  carries a soft shadow. Warn-item backgrounds re-tinted for light
  (`#1a1206`→`#fbf3e0`, `#1d0c0c`→`#fcebe9`). `.good` and `.ritem.completed` border
  darkened `#6fd087`→`#1a7a3f` for AA on light. `.bar` fill now `--panel2` (was dark).

### Decision: market-cap graph kept DELIBERATELY DARK
- `#capgraph-big` background `#0c1014`→`#11161c`, plus a `--line` border so it reads as
  an intentional "chart panel" (finance/terminal convention) on the light page, NOT an
  oversight. Rationale: the saturated lab line colors (`core.js COLORS`) read better on
  dark, and a dark chart on light paper is a credible serious-tool look.
- `.cap-tab-text` LEFT sans-serif and untouched per HARD CONSTRAINT (FIX_ITEMS ticker
  rule). Only contrast nudged on the dark panel: `.cap-axis-text` fill `#3a4a59`→`#7d8a97`,
  `.cap-gridline` `#22303c`→`#26303a`. `.cap-tab-text` ticker fill (#06121c on the bright
  tab fills) left as-is — still legible.
- The post-mortem `canvas` (140px JS-drawn chart) given the SAME dark-panel treatment
  for consistency, since lab colors are drawn on it too.

### JS inline-style / hardcoded-hex elements FLAGGED (no change this stage — CSS-only)
None require a fix, but flagged for awareness:
- `core.js` `COLORS` (player #4fb3ff, rival1 #ff6868, rival2 #ffb347, rival3 #9a7bff,
  rival4 #6fd087, rival5 #ff8ad0) + `'#888'` fallback in views.js: these are LAB-IDENTITY
  line/swatch colors, not theme surfaces. They are drawn on the dark graph/canvas (read
  fine) and as small 10px swatches in light panels (saturated dots, still visible). No
  clash, but if the graph were ever made light these would need a contrast pass.
- All other inline `style=` in js/ (views.js, main.js, warnings.js, research.js) are
  layout-only (margins/widths/flex) or reference theme vars (`var(--line)`, `var(--txt)`)
  and adapt automatically. No light-mode clashes.

### Verification
- Style block: braces balanced (80/80); every `var(--x)` referenced is defined
  (incl. new `--serif`).
- Server: `/` → 200 text/html; `/js/{main,core,views}.js` → 200 text/javascript.
- `tests.test_golden_master` PASSES unchanged (CSS-only, no RNG/firewall impact).

### Browser smoke-test checklist (no JS runtime here — needs a human/browser)
1. Page bg is warm off-white; body copy is serif and dark/legible.
2. Each nav tab (Market/Lab/Benchmarks/Research/Governance/Intel/Truth) renders;
   active tab is accent-filled with white text and readable.
3. Panels sit just off the page with hairline borders; headings read as uppercase labels.
4. Buttons (default + `.primary` END TURN) and inputs/selects are legible; focus/hover OK.
5. Warning modal: `.warn` amber and `.warn-emph` red boxes are distinct on light; `.dim`
   text muted-but-readable; `.bad` red and `.good` green distinct.
6. Market graph still a dark chart panel; lines/tickers render; tickers are SANS-SERIF
   and uppercase; axis/gridlines legible.
7. Research cards: in-progress (accent left-border) vs completed (green, dimmed) distinct;
   queue chips and bars visible.
8. Overlay (post-mortem) + item modal: light scrim, card readable, post-mortem canvas dark.
9. Dev-mode "Truth" tab still gated/works (unchanged JS) and styled.

---

## Stage C — Centralize user-facing strings (i18n-ready)

Mechanical refactor only: same text renders, only its SOURCE moves to a named key.
No behavior, action ids, dict keys, handler names, or firewall touched. Golden
master + firewall pass UNCHANGED (no re-record).

### Where the two strings tables live
- **Frontend:** `simple_frontend_v1/js/strings.js` (NEW). A flat object `STRINGS`
  of dotted, area-namespaced keys → English copy, plus a `t(key, params?)` helper.
  Re-exported through `core.js` (`export { STRINGS, t } from "./strings.js"`) so the
  view modules import `t` from `core` alongside the other shared helpers. 117 keys,
  all referenced; verified every `t("…")` key resolves to the table and vice-versa.
- **Backend:** `backend_v1/content/strings.py` (NEW). Holds only the loose inline
  authored strings that previously sat in engine code: `DEFAULT_PLAYER_LAB_NAME`,
  `DEFAULT_PLAYER_TICKER`, and `RIVAL_LAB_NAMES`. `engine/game.py` imports these and
  re-exports the two DEFAULT_* names (so `from backend_v1.engine.game import
  DEFAULT_PLAYER_*` call sites — incl. `tests/test_lab_identity_sanitization.py` —
  keep working). Values are byte-identical to the old literals, so attribution logs
  and the golden master are unchanged.

### `t()` interpolation convention
- `{placeholder}` tokens in a value are filled from the params object. A missing
  param leaves the `{token}` visible (loud, not a silent blank); a missing KEY
  returns the key itself (so a typo shows in the UI rather than rendering empty).
- `t()` returns RAW authored text and does NOT escape. Authored UI copy is trusted,
  so that's fine — BUT where a caller interpolates t() output next to UNTRUSTED data
  (player lab name/ticker, catalog evidence/cost/axis), that data is still run
  through `core.esc()` BEFORE being passed as a param. Every prior esc() call was
  preserved; confirmed by grepping the NAMES[/TICKERS[/rival.* and catalog render
  sites. Two strings that legitimately contain `&amp;` (HTML context) keep the
  entity form in the table so rendering stays byte-identical.

### Backend catalogs treated AS their own strings tables (not duplicated)
Per the task's "don't add pointless indirection" guidance, these are already
well-structured single-file DATA tables where every player-facing string is a named
field on a named row — a translator finds them by name in one place. They are
referenced in place, NOT copied into a second table (which would risk drift):
- `backend_v1/engine/observation/warnings.py` — `CATALOG` (id → {line, why, paper}).
- `backend_v1/engine/research/capabilities/capabilities_research_item.py` —
  `CAPABILITY_TREE` rows (`name` / `what_it_does` / `risk_blurb`).
- `backend_v1/engine/research/safety/safety_advance_item.py` — `SAFETY_ADVANCES`
  rows (`name` / `what_it_does` / `risk_blurb`).
Benchmark names/blurbs, findings/tips/news/event text, policy names/`teaches`, and
post-mortem headline/detail/counterfactual prose also arrive through the observation
as backend content and are rendered as-is — they are the backend's strings, surfaced
through the data layer, not frontend copy.

### Intentionally left in markup (judgment call, allowed by the task)
`simple_frontend_v1/index.html` STATIC text is left as authored markup: the nav tab
labels (Market/Lab/…), panel `<h3>` headers, top-bar chip labels, and the long
benchmark/intel/truth explanatory prose. These are rendered once from the HTML and
never re-generated by JS. Centralizing them would mean either an on-load DOM pass
keyed by `data-key` (new machinery, more surface) or injecting them from JS
(contorting the shell markup) — the task explicitly permits leaving static HTML copy
in place. The VOLATILE, re-rendered copy (everything the view modules generate) is
fully centralized. If full i18n is pursued later, give the static nodes `data-key`
attributes and add one `applyStaticStrings()` pass at bootstrap.
