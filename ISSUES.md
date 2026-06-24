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

# Task: HTTPS deployment + multi-session hardening (server layer)

Goal: make the game deployable as a public HTTPS site (DigitalOcean droplet +
GoDaddy domain + Caddy reverse proxy) for many concurrent players. All code
changes are confined to `backend_v1/server/server.py`; the engine, RNG, and
`observation_builder` are untouched, so the golden-master digest is unaffected.

### Liberties taken (flagged for review)

- **Invented deployment constants** in `server.py` (no design-doc basis — these are
  ops knobs, not game balance):
  - `MAX_SESSIONS = 500` — registry cap; beyond it the least-recently-used game is
    evicted (≈160 MB ceiling at ~320 KB/game). Chosen for a 1 GB droplet; raise/lower
    to fit the real box. An evicted player silently falls back to the new-game modal.
  - `MAX_BODY_BYTES = 64 * 1024` — max accepted POST body (real payloads are <1 KB);
    guards `_read_body` against a forged `Content-Length`.
  - Session cookie `sid`: `HttpOnly; Path=/; SameSite=Lax`, plus `Secure` only when
    `ALIGNMENT_DEPLOY=production` (a Secure cookie is dropped over local plain HTTP).

- **`ALIGNMENT_DEPLOY=production` flag.** Closes the debug `/api/truth` god-view
  endpoint (returns `{"turns": []}`) and sets the Secure cookie attribute. Local/dev
  (unset) keeps the Truth tab working. This closes a real firewall hole: `/api/truth`
  was previously open to anyone, and the normal player flow hits it every turn
  (`core.js` `apply()`), so it could not simply be removed — hence the empty-payload
  approach (CLAUDE.md §0.3).

### Implementation choices with design consequences

- **Infra randomness/time vs engine determinism (§0.4).** Session tokens use
  `secrets.token_urlsafe` and LRU bookkeeping uses `time.monotonic()`. These are
  HTTP-infrastructure concerns and are deliberately **not** routed through the seeded
  engine RNG — they don't affect the simulation and must not be confused with a
  determinism violation. Same seed + same actions still produces a bit-identical game.

- **Per-session locking.** Each `Session` carries its own `threading.Lock`; a separate
  registry lock guards only the `OrderedDict`. Different players run concurrently;
  requests on the *same* game serialize. No cross-game contention.

- **No frontend changes.** The frontend already uses same-origin relative `fetch`, so
  the session cookie flows automatically and HTTPS "just works". A cookieless/evicted
  visitor receives `{"errors": ["no active game — start a new game"]}`, which the
  existing `apply()` error path handles by keeping the new-game modal up.

### Open question for the designer

- **Production server choice.** Kept Python's stdlib `http.server` (thread-per-request)
  behind Caddy — adequate for hobby traffic, not a hardened app server. Migration path
  (Flask/FastAPI + gunicorn/uvicorn + shared session store) noted in `deploy/README.md`.
  Revisit only if real load appears.

## Sub-task: DoS / bot hardening (server layer + edge)

`/security-review` excludes DoS by design, so this was a separate pass. The threat
that matters for a single droplet is *asymmetric* application-layer load (a cheap
request that is expensive to serve) plus volumetric floods. Volumetric is handled
at the edge (Cloudflare, documented in `deploy/README.md` Step 8 — free tier hides
the origin IP and rate-limits `/api/*`). The app-level backstops, all in `server.py`:

- **`MAX_GAME_TURNS = 500`** + `clamp_max_turns()` — bounds one session's compute/
  memory. The client could previously pass any `max_turns` (or rely on uncapped);
  real games end ~50-60 turns so this never affects play, it just removes the one
  client-tunable that set session lifetime. INVENTED — see ISSUES note above.
- **Post-mortem caching** (`Session._postmortem_cache`) — `build_postmortem(resim=True)`
  replays counterfactual branches (expensive). The game is frozen once over, so the
  result is memoized; this removes a "spam `/api/postmortem` to amplify CPU" vector.
- **`REQUEST_TIMEOUT_SECONDS = 30`** (`Handler.timeout`) — a slow/stalled client can
  hold a worker thread for at most 30s before the socket read times out.
- **`MAX_CONCURRENT_REQUESTS = 32`** + a `BoundedSemaphore` in `Handler.handle()` —
  past the cap we answer 503 rather than spawn unbounded threads / run unbounded
  concurrent engine steps. INVENTED; generous for real play, a backstop behind edge
  rate limiting.
- (Already present from the HTTPS task: `MAX_BODY_BYTES` 64 KB → 413, and `MAX_SESSIONS`
  LRU eviction. Note the eviction has a griefing edge — a `/api/new` flood can evict
  real players' in-progress games; the real mitigation is edge rate limiting on
  `/api/new`, hence Cloudflare.)

All are server-layer; the golden-master digest is unchanged. Numbers are INVENTED
deployment knobs (not game balance) — tune to the real droplet.
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

---

## Backend stage: rival lobby/litigation spend recording + turn-0 caps seed (UI_ISSUES #5, #9)

Two ADDITIVE backend changes. Both are pure logging/payload — no behavior change; the
golden master is byte-identical and the firewall test still passes.

### Judgment call: CUMULATIVE spend, stance overwritten
`PolicyState.contributions` accumulates `lobby_spend`/`lit_spend` over the WHOLE game
(not last-turn) so the board reflects total pressure a lab has applied to a policy.
`stance` is overwritten with the latest value, because lobby stances re-set each turn
(there is no per-turn history to show) — for litigation the stance stored is the
`side` (challenge/defense). Documented in the field comment and IMPLEMENTATION_DETAILS.
If the designer wants a per-turn decaying pressure display instead, this would need a
ring buffer or decay, not a running sum.

### Judgment call: how litigation recording reaches the PolicyState
`apply_litigation_action(world, lab, policy_id, spec, consts)` already resolves the
policy's `PolicyState` as `st` early on (it needs `st.active`/`st.litigation`). I
recorded directly on that `st` after the existing cash deduction + effort accrual —
no new threading. The recorder is a method `PolicyState.record_contribution(...)` on
the dataclass (self-mutation, not time advancement), so both `turn_pipeline` (lobby)
and `litigation.py` call the same code with no import cycle.

### Ticker resolution without a labs list
`_policy_board(lab, world, consts)` has no access to the full labs list (and
`World` doesn't hold labs). Rather than thread labs through `legal_moves`/
`build_observation`, I stamp each contributor's `ticker` into the `contributions`
entry at RECORD time (`lab.ticker` is in scope there). `_policy_board` then reads
ticker/stance/spend straight from the dict and just filters out the viewing lab.

---

## Market cap graph: fit the full drawn history (y-axis clipping)

**Bug:** the cap graph's y-axis was scaled to `max` of the raw quarter endpoints
(`HIST[*].caps`), but the polyline drawn for each lab includes the deterministic
interim *wiggle* (`capWiggleSteps`). The wiggle's cumulative trough can lift a
quarter's interior above its endpoint cap (worst case ~`exp(0.336) ≈ 1.40`, i.e.
~40% over), so the top lab's wiggle peaks landed above `plotTop` and the SVG
viewport clipped them flat — the graph "did not fit the entire history."

**Fix (frontend only, `simple_frontend_v1/js/views.js`):** scale the y-axis to the
tallest value actually drawn. New helper `maxDisplayedCap(labIds)` walks the same
cached wiggle values the polyline uses (value-space, no pixels) and returns the
global max; `drawCaps` uses `maxDisplayedCap * CAP_PLOT_HEADROOM` as `maxCap`.

**Liberty taken (balance/cosmetic):** `CAP_PLOT_HEADROOM = 1.04` — a sliver of
headroom so the highest peak sits just inside the top edge rather than touching it.
Display-only, no game-state/RNG impact; flagged for the designer to adjust to taste.

---

## Research / intervention item cleanup (tangibility, noise, per-kind balance)

**Task.** Go through the research + intervention catalogs: (1) remove items that
aren't tangible, intelligible *actions* (the example given: "Scaling laws" — a
finding, not a thing you do); (2) cut noise; (3) balance how many advances of
each kind are available at one time. Scope confirmed with the designer:
**moderate** depth, **all three** catalogs (light touch on the safety ones).

### What I changed (capability tech tree — `capabilities_research_item.py`)

**Renamed to action-framing (ids kept stable — ids are internal keys referenced
by `cli/strategies.py`, the golden master, and `researched_advances`; only the
display `name` + `what_it_does` changed, which never enters any digest):**
- `scaling_laws`: "Scaling laws" → **"Larger training runs"** (a finding → an action).
- `data_efficiency`: "Data-efficiency methods" → **"Data-efficient training"**.
- Reworded several `what_it_does` blurbs from noun-phrases to imperative actions
  ("Train…", "Build…", "Let the model…") so each entry reads as a thing the lab does.

**Cut 5 advances — chosen as exactly the items NOT in the design-doc §9 table
(the assistant-invented extras that overlapped doc-canonical entries):**
- `moe_scaling` (pretrain) — pure ceiling-bump duplicate of `better_architecture`;
  §9's own `[OPEN]` note flags MoE/efficiency as the candidate "filler" advance.
- `continual_learning` (pretrain) — niche; its eval-awareness hook was folded out.
- `inference_scaling` (post-train) — overlapped `chain_of_thought` (reasoning +
  coding + eval-awareness); folded into it.
- `agentic_rl` (post-train) — overlapped `multi_agent` (the agentic regime); folded in.
- `neuralese` (post-train) — "illegible reasoning"; folded into the capstone.

The cut items' **distinct mechanical hooks were folded into surviving canonical
items** so the ASI arc and the eval-awareness / patching-trap progression don't
collapse:
- `chain_of_thought` now also carries inference-time reasoning (elicitation
  0.12→0.18, coding 0.08→0.12, eval-awareness 0.01→0.03).
- `multi_agent` now also carries long-horizon RL (elicitation 0.10→0.13,
  eval-awareness 0.02→0.04, +revenue 1.2); prereqs unchanged.
- `automated_researcher` prereq `agentic_rl`→`multi_agent`; +eval-awareness 0.04.
- `recursive_self_improvement` prereq drops `neuralese`; +eval-awareness 0.06 and
  its blurb now teaches the "latent/illegible reasoning closes the oversight
  window" lesson `neuralese` used to carry.
- `ai_rnd_assist` prereq drops `inference_scaling` → `(chain_of_thought, tool_use)`.
- `novel_architecture_search` prereq unchanged (`automated_researcher`).

I checked the per-axis TOTALS so the arc is preserved: summed `eval_awareness_feed`
across the tree is unchanged at **0.19** (the patching-trap driver is intact).
Summed post-train `elicitation_bonus` drops 1.33→1.07 and the max pretrain ceiling
product and max severity drop slightly — **expected** from having fewer items.

**Per-kind balance:** capability tree went from **7 pretrain / 11 post-train /
1 tooling** to **5 / 8 / 2**. Post-train stays the largest bucket on purpose — the
design doc's own §9 table and "progress past present-day" mandate weight the
post-training/elicitation side. The lonely tooling bucket got a second option.

### Liberty taken (new mechanic — flag for review)

- **`serving_infra`** ("Inference-serving infrastructure", tooling): a NEW item,
  the only genuinely-new mechanic added. It uses the existing `revenue_multiplier`
  field (read generically in `finances/revenue.py` for any researched advance,
  regardless of phase — verified) and `contamination_tier=0.2` (plumbing). Gives
  tooling a second, *distinct* lever (revenue/deployment reach) rather than a
  second pure-speed duplicate, which would have been the "noise" I was told to cut.
  Fits §9 "tooling amplifies whatever misalignment already exists" (here: widens
  the deployment blast radius). Numbers (`revenue_multiplier=1.2`, cost 30,
  0.5y) are [TUNE] drafts, optimistic per §0 — designer to set.

### Safety catalogs — reviewed, left unchanged (the "light touch")

Reviewed `safety_research_item.py` (7 measurement + 3 intervention projects) and
`safety_advance_item.py` (2 pretrain + 3 post-train advances). Every name is
already a concrete action and each item carries a distinct mechanic (the
point/bound/existence evidence ladder, the spoofability gradient, genuine-vs-
EFFECTIVENESS-gated interventions, pretrain-vs-post-train advance split). No
non-tangible items and no true duplicates, so I made no cuts. Per-kind
availability is already reasonable (safety advances: 1 pretrain + 2 post-train
unlock at start; the rest gated by one prereq each).

### Verification

- `tests.test_golden_master` re-recorded (catalog change shifts the scripted
  controller's action stream → TRUE trajectory moves; expected per §8, NOT an
  RNG/firewall regression). Note added above the new `EXPECTED` block.
- Full suite (`unittest discover -s tests`) green; firewall + lab-identity tests pass.
- Headless game runs; post-mortem counterfactuals reference surviving items.
- Grepped the repo for the 5 cut ids: no remaining references in `.py`/`.js`/`.html`
  (only in historical `NOTES.md` / `STRATEGY_REPORT.md`, left as-is per CLAUDE.md).
- `cli/strategies.py` `EFFICIENCY_ORDER` / `RUSH_ORDER` pruned of the cut ids.

### Open question for the designer

Removing 5 advances lowers the achievable max elicitation/ceiling somewhat. If the
late-game capability arc now flattens before turn ~40 (design §9 wants it to keep
climbing), bump `CEIL_COMPUTE_SCALE` and/or the surviving ceiling/elicitation
multipliers rather than re-adding filler advances.

---

## Investor-sentiment noise on the investment score

**Task.** "Add some random noise to the lab scores that are used to determine
investment."

**Change (`finances/investment.py`, `run_investment`).** Before the score pie is
normalized and divvied, each lab's score is multiplied by a per-turn sentiment
noise factor `max(0.0, 1.0 + rng.normal(0, SCORE_NOISE_STD))`. `lab_score(...)`
stays a pure self-query (fundamentals only); the noise is applied at the call site
where the seeded `rng` is in scope. The noised value is what gets stored in
`lab.last_score`, so it also flows to the market cap — but the cap smooths it
twice downstream (`INVESTMENT_ANCHOR_ALPHA`, then `MARKET_CAP_ALPHA`), so the
on-screen anchor stays legible rather than jittery.

**Why multiplicative + clamped at 0.** Mirrors the existing revenue-pie noise
(`REVENUE_NOISE_STD`, `finances/revenue.py`): noise scales with score size and can
never flip a score negative (which would corrupt the pie-share normalization).

**Determinism (load-bearing invariant, CLAUDE.md §0.4 / §6).** The draw goes
through the seeded RNG, so same seed → identical run. It IS one new draw per lab
per turn, which shifts the whole downstream RNG stream — the golden master was
re-recorded for exactly this reason (note added above the new `EXPECTED` block);
it is an intentional RNG-draw change, not a regression.

**Liberty taken (balance).** `SCORE_NOISE_STD = 0.10` is a [TUNE] draft (the
revenue pie uses 0.08). Per §0 it's an optimistic starting point — the designer
may want sentiment noisier than fundamentals (real investor herding/sentiment is
volatile), in which case push it higher.

---

## INVESTIGATION (no code changes) — reckless rivals reach *aligned* ASI; misalignment is not the default

**Task.** Player reports: playing by spamming "next turn" (player does nothing) on
seeds 0–5, a rival reaches **aligned** ASI every time. Per the thesis (§0 claims #1,
#5, #6) this should be rare — misalignment is supposed to be the *default*, and at
least the reckless racer should routinely produce a dangerous/misaligned model.
Investigate cause; no code changes yet. **This section is diagnosis only — flagged
for the designer to decide the fix + re-tune.**

### How I reproduced it (harness, player = no-op)

Drove the engine directly with the player submitting an empty `Action()` every turn
(faithful "spam next turn") and the stock `RivalController` on rivals, `realistic`
difficulty, default 4 rivals, seeds 0–11. Probe scripts in scratchpad (not
committed). Measured each rival's best model's TRUE `misalignment_composite()` vs
`ASI_MISALIGNMENT_BAR` (0.35) at game end.

### What actually happens

- **The reckless racer (rival1: recklessness 0.85, derived safety_priority 0.08) is
  genuinely reckless in behavior** — confirmed by tracing its actions over a full
  game: it researches the *entire* dangerous capability tree (`synthetic_data`,
  `ai_rnd_assist`, `automated_researcher`, `recursive_self_improvement`, …), cranks
  AI-assist (`0.9 × recklessness`), and applies **zero** safety projects and **zero**
  safety advances across the whole game. So the controller IS reckless; the problem
  is downstream in the emergence model.
- **Yet its ASI-grade model is almost always benign.** Across seeds 0–11 the reckless
  rival reaches cap ≈ 9 (ASI) in nearly every seed, but its composite exceeds the
  0.35 bar only **1/12** times (mean composite ≈ **0.195**). Typical end state:
  `goal_misalignment ≈ 0.14`, `deception ≈ 0.16`, `self_preservation ≈ 0.03`.
- **Recklessness is nearly decoupled from final misalignment.** Mean composite:
  reckless rival ≈ 0.195 vs the cautious rival (reck 0.25, safety_priority 0.38) ≈
  0.120 — and in several seeds the *cautious* rival is the more misaligned of the two.
  A lab that took every risk and a lab that took few end up in roughly the same
  alignment band. That is the thesis failure in one line: **recklessness carries
  almost no alignment penalty.** (Caveat: the cautious rival also reaches lower
  capability ~5–6, so it's not a clean controlled comparison — but the reckless rival
  reaching ASI *and* staying benign 11/12 times is the core finding regardless.)
- Net on seeds 0–5 (no-op player): ~half end as "rival reaches **aligned** ASI"
  (seeds 1,3,5), ~half as a rival1-caused **existential catastrophe** (seeds 0,2,4 —
  weight-exfiltration / verification-cliff). So the dangerous channel is not dead, but
  a maximally reckless lab still lands a *clean* ASI about half the time, and even its
  "misaligned" outcomes sit right at the 0.35–0.41 borderline, not the 0.6–0.9 a
  no-safety strategy should produce.

### Primary cause — every post-train round applies free, un-gated corrective shaping

`training_run.post_train_round` step 4 spends
`effort = BASE_SHAPING_EFFORT (0.12) × alignment_effort_mult (1.0)` of **genuine
corrective shaping on every disposition axis, every round, for every lab,
regardless of disposition or whether any safety work was done.** This is the
"baseline = former *balanced* mode" decision (see the post-train-mode-removal note
earlier in this file). Consequence: a lab that researches and applies *nothing*
still gets continuous, automatic alignment remediation.

Why that scrubs reckless rivals clean (mechanism, confirmed by tracing one model
lineage, seed 3):

1. **Early/mid capability → shaping is highly effective.** `EFFECTIVENESS` for
   goal-misalignment ≈ `BASE_TRACTABILITY` (0.32) while capability < ~4 (defenders
   weak, `CAP_LOCK` gate at onset 4.0 still closed). So `true_cut ≈ 0.12 × 0.32 ≈
   0.038/round`, which **dominates** `GOAL_MIS_CREEP` (0.016 × (0.5+cap/CAP_MAX) ≈
   0.013–0.022/round). Net: goal-misalignment is driven *down* toward 0 early.
   Observed: rival1's first two base models settle at gm ≈ 0.002–0.005.
2. **Each new pretrain resets to a fresh, low-capability, low-gm base**
   (`BASE_GOAL_MIS_PRETRAIN` = 0.08, realized cap = 0.12 × ceiling). So *every*
   model — even a late one with ceiling 9 — spends its first post-train rounds in
   the high-effectiveness regime, re-scrubbing the base before `CAP_LOCK` engages.
3. **Few high-capability rounds before release.** Late models post-train only ~2
   rounds before shipping (observed), so creep + the rare correlated jump
   (`JUMP_BASE_P` 0.02) have little time to accumulate. The lock makes fixes
   cosmetic late — but there's almost no "late" to exploit, because the model is
   fresh and shipped fast.

Net: the patching-trap machinery is built correctly (CAP_LOCK, defends-discount,
backfire all present), but it never bites, because the **free baseline shaping wins
the early regime and the model is released before the late regime can do damage.**

**Confirming experiment.** Monkeypatched `BASE_SHAPING_EFFORT` (no repo change):
- 0.12 (default): reckless rival composite 0.10–0.18 in 4/6 seeds 0–5 (aligned).
- 0.06: composites roughly double (0.19–0.44); more borderline/misaligned.
- 0.00: composites ≈ 0.23–0.57; several clearly misaligned ASIs.
The free shaping is the dominant lever holding reckless rivals benign.

### Secondary amplifiers (each pushes the same way)

- **`self_preservation` is effectively inert** — never exceeds ~0.05–0.13 in any run,
  yet it carries `COMPOSITE_W_SELF_PRESERV` = 0.30 of the catastrophe composite. Same
  free shaping scrubs it, its onset (4.5) is late, and models do too few late rounds
  to build it. A 30%-weighted axis contributes ~nothing → the bar is hard to reach
  even when goal-mis/deception are elevated.
- **Composite bar geometry.** With weights {gm 0.55, sp 0.30, dec 0.15} and the bar
  at 0.35, and sp pinned near 0, you essentially need `0.55·gm + 0.15·dec > 0.35`,
  i.e. gm ≈ 0.55+ *and* meaningful deception. The free shaping + fast ship keep gm in
  the 0.1–0.2 band, well short.
- **Weak emergence vs. shaping.** `GOAL_MIS_CREEP` 0.016 and `JUMP_BASE_P` 0.02 are
  small next to 0.038/round of scrubbing; foundational floors from synthetic data come
  out tiny (~0.05–0.06), so even the "unscrubbable" path barely moves the base.

### Suggested directions for the designer (NOT yet implemented — pick + re-tune + re-record golden master)

1. **Gate the baseline corrective shaping on disposition / actual safety investment.**
   The strongest single fix. A lab that does no safety work should get little/no free
   alignment remediation. Options: make `alignment_effort` for rivals scale with
   `safety_priority`; or drop `BASE_SHAPING_EFFORT` toward 0 and require the player/
   rival to *choose* shaping (a preventive stance / applied advance) to get it. This
   directly restores claims #1 and #5 (misalignment-by-default; can't-get-rich-safely).
2. **Strengthen emergence relative to shaping** (raise `GOAL_MIS_CREEP`,
   `JUMP_BASE_P`/`JUMP_MAGNITUDE`, foundational-floor from synthetic data) so a
   no-safety lab trends misaligned even if some baseline shaping remains.
3. **Make `self_preservation` actually emerge** (earlier onset / higher rate, or less
   subject to free shaping) so its 0.30 composite weight isn't dead.
4. **Revisit the per-model reset dynamic**: carry more of a parent model's disposition
   into its successor's base (the §5 propagation edge is meant to make your own
   misaligned models poison successors — right now each pretrain largely launders the
   lineage clean).

Per §0 calibration: all the relevant constants are assistant-drafted optimistic
values; this whole cluster reads as flattened-toward-winnable. The fix is a designer
call on *how* bleak — I've only diagnosed that the current numbers contradict the
stated thesis.

### RESOLUTION (applied) — pure constant retune, **bleak** calibration

Fixed by tuning alone (no mechanics change — the patching-trap machinery was already
correct; it was just being overwhelmed by the free baseline shaping). The designer
chose the **bleak** calibration (reckless racer should almost always produce a
dangerous ASI). Five constants changed in `backend_v1/config/constants.py`:

| Constant | From | To |
|---|---|---|
| `BASE_SHAPING_EFFORT` | 0.12 | **0.02** |
| `GOAL_MIS_CREEP` | 0.016 | **0.035** |
| `SELF_PRES_RATE` | 0.035 | **0.08** |
| `SELF_PRES_ONSET` | 4.5 | **3.5** |
| `JUMP_BASE_P` | 0.02 | **0.04** |

`BASE_SHAPING_EFFORT` is the primary lever: a vanilla post-train round no longer buys
near-free TRUE alignment, so genuine shaping must be *chosen* (applied safety advances
/ `pending_effort` from safety projects). That is what now differentiates a cautious
lab from a reckless one, and it preserves the early "false lesson" for an active
player (chosen effort is still highly effective in Regime 1). The others let emergence
and the (previously inert) self-preservation axis come through.

**Verified gradient** (seeds 0–11, realistic, no-op player; reckless rival's TRUE
composite vs the 0.35 bar), now monotonic in recklessness and with self-preservation
alive:

```
rival1 reck .85: meanComp 0.446  >bar 10/12   selfPres ~0.19   (was 0.21 / 0-of-12 / ~0.03)
rival2 reck .60: meanComp 0.344  >bar  6/12
rival3 reck .45: meanComp 0.267  >bar  2/12
rival4 reck .25: meanComp 0.166  >bar  0/12
no-op-player outcomes: existential 12/12, rival-aligned-ASI 0/12.
```

Golden master re-recorded (intentional TRUE-trajectory shift; action stream / firewall
unchanged — see the dated note above the `EXPECTED` block in
`tests/test_golden_master.py`). Determinism re-confirmed (same seed → bit-identical).

**Watch-item for playtesting (cannot test headlessly):** the bleak setting makes a
*passive* player lose to a rival-caused catastrophe by design (claim #6). Confirm a
*skilled* safety-and-race player still has a knife-edge win path. If rival catastrophe
feels unavoidable regardless of skill, dial the five constants toward the recorded
**moderate fallback**: `BASE_SHAPING_EFFORT 0.03, GOAL_MIS_CREEP 0.032,
SELF_PRES_RATE 0.075, SELF_PRES_ONSET 4.0, JUMP_BASE_P 0.035` (reckless rival ~6/12
over bar, mean still above the bar — dangerous more often than not but not certain).

**Deliberately left for later (optional mechanics, not needed for the thesis now):**
- *Lineage laundering*: each pretrain still resets to a near-clean base (the §5
  goal-misalignment→successor propagation edge is weak). Within-model emergence is now
  strong enough that this no longer blocks the thesis, but carrying more parent
  disposition into the successor base would deepen the cross-generation time-bomb.
- *Disposition-gated baseline shaping*: a cleaner mechanic than a low flat baseline,
  but unnecessary now that the baseline is low and caution differentiates via *applied*
  safety advances.

### PLAYTEST EASING (applied) — slower rivals + slightly less creep

After playtesting (5 hand-played games + batches) showed the **bleak** calibration
was effectively unwinnable — a reckless rival reliably reached world-ending capability
around turn 36 and the player couldn't out-race it or contain it in time (see the
playtest notes; governance contains the frontier but arrives too late / costs the race)
— two small easings were applied per the designer's call to make realistic a bit more
winnable WITHOUT undoing the misalignment-by-default fix:

| Constant | From | To | Effect |
|---|---|---|---|
| `GOAL_MIS_CREEP` (constants.py) | 0.035 | **0.030** | slightly less per-round creep → player has more room to keep their own models aligned; still > the 0.02 baseline shaping, so a no-safety lab still trends misaligned |
| `RIVAL_RECKLESSNESS_MULT["realistic"]` (difficulty.py) | 1.0 | **0.9** | slows the rivals' race (smaller runs, less AI-assist, a touch more safety in the controller) → reckless rival reaches ASI later |

**Verified (seeds 0–11, realistic, no-op player):** recklessness→danger gradient still
monotonic and intact (reckless rival1 mean composite **0.343 / 4-of-12 over the 0.35
bar**, down the line to cautious rival4 0.185 / 0-of-12 — vs the original *bug* of 0.21 /
0-of-12). Rivals are slower: no-op-player games now end at **turn ~48** (was ~36–45).
The reckless rival is still clearly dangerous (mean composite right at the bar) — just
beatable, and on a later clock. Golden master re-recorded (intentional; see test note).

**Still open (not addressed by this easing):** the jailbroken-rival
**misuse-catastrophe channel** (a reckless rival's released high-capability model giving
bio/cyber uplift) and the **late arrival of governance enforcement** — heavy lobbying
can contain the frontier but the achievable policies (audit thr 38) need the player to
already be rich, and active enforcement lands after the danger window. If realistic
still feels unwinnable after this easing, the next lever is giving active audit /
interp-mandate a way to suppress the rival misuse + ASI-misalignment channels in time.

### CREEP REDUCTION (applied) — GOAL_MIS_CREEP 0.030 -> 0.025

After a full hand-played clean run (assist 0 everywhere + full prevention every round),
a *perfectly-played* aligned ASI still landed at TRUE composite **~0.34** — a hair under
the 0.35 bar, clearing the existential gate by ~0.006 (the agentic edges crept it right
up to the line). To give a clean player real margin at the cliff, `GOAL_MIS_CREEP` was
reduced 0.030 -> **0.025** (constants.py).

Still above the 0.02 baseline shaping, so a no-safety lab's per-round creep (0.025) keeps
outpacing it and trends misaligned — the §0 misalignment-by-default fix is preserved.
Verified (no-op player, seeds 0–11): recklessness→danger gradient intact and reckless
rival still dangerous (rival1 mean composite ~0.40, >bar 7/12; cautious rival4 ~0.15,
0/12). The reduction mainly helps the *clean, full-prevention player* (whose composite is
creep-dominated); reckless rivals stay dangerous because their misalignment comes from
skipped prevention + correlated jumps + assist contamination, not creep alone. Golden
master re-recorded (intentional; see test note); determinism re-confirmed.

---

## Investigation: market caps plateau (then decline) after releases

**Reported.** "Lab market caps still plateau after releases." Investigation only —
**no code changed**, golden master untouched. Harness probes are in `/tmp`
(`mc_probe.py`, `rel_probe.py`, `cap_probe.py`); reproduce with
`PYTHONPATH=. python3 /tmp/mc_probe.py balanced 0`.

### Symptom (harness, seed 0 balanced; same shape on aggressive seed 3)

Caps climb a healthy staircase through ~turn 35, then **every lab's cap plateaus
and declines from ~turn 38–40 onward**, and the drops land *on release turns*
(the opposite of the intended step-up). Example (YOU): cap peaks then
`t40 −9166`, `t42 −5589`, `t44 −2191`, … grinding down for the rest of the game.

### Root cause — a chain, not one bug

1. **Measured capability saturates mid-game.** The frontier leader's *measured*
   general flatlines at **8.96** (true 8.97, ceiling 9.59) from turn 40 to 60 and
   never moves again. true ≈ measured, so this is **diminishing-returns saturation
   as realized capability asymptotes toward the ceiling — NOT eval-awareness
   suppression.** Elicitation is `r += (ceiling − r)·rate`, so per-round gains
   shrink to nothing near the top; no lab ships a better model for ~20 turns.
2. **The rising target bar keeps demanding growth that's now impossible.**
   `_release_growth_term` compares release-to-release `gain/yr` against
   `target = RISING_TARGET_BASE + RISING_TARGET_FRONTIER_K·frontier +
   RISING_TARGET_TIME_K·held` ≈ **0.74–0.83 /yr** late-game. Once measured
   capability has saturated, gain/yr falls to ~0 (and frequently **negative** —
   a refresh release can ship a less-elicited model than the prior flagship, e.g.
   t51 OPE 8.53→7.06). So `growth_term < 0`: **nearly every late release is a MISS**
   (probe shows ~18 of the last ~20 releases miss, many at the −1.0 floor).
3. **A MISS resets momentum to a sub-1 floor with no carry-forward.** In
   `update_investment_momentum`, a beat does `momentum = max(confidence, momentum)`
   (the staircase fix), but a miss takes the `else`:
   `momentum = max(0, 1 + SCORE_MOMENTUM_GROWTH·growth_term)` → as low as **0.15**
   for a full miss, discarding all accrued confidence. Late-game where *every*
   release misses, momentum can never re-accumulate — it cliffs on each release.
4. **Momentum dominates the score.** `SCORE_W_GROWTH = 0.55` outweighs
   `SCORE_W_BEST = 0.40` and `SCORE_W_REVSHARE = 0.25`, so a cliffed momentum
   collapses `lab_score`.
5. **Market cap is a product of saturating terms.** `target_valuation =
   MARKET_CAP_SCALE · score · investment_anchor + 0.5·revenue`. `score` saturates
   (best/CAP_MAX → ~0.9, rev_share bounded) and the investment pie saturates
   (`INVESTMENT_MAX_PER_YEAR · capability_fraction^1.4 · growth_mult`, and
   `growth_mult` → its floor as revenue growth → 0). With nothing left to push the
   target up and the momentum cliff dragging `score` down, the cap plateaus and
   then declines on every release.

**One-line:** capability saturates near the ceiling → the rising bar becomes
unbeatable → every release is a "miss" → the miss-branch cliffs the dominant
momentum term → score and cap fall *on release turns*. The staircase fix only
works while labs can beat the bar; nobody can once the frontier flattens.

### Intended vs degenerate

The treadmill (trailing labs face an ever-higher, frontier-relative bar, §9b) is
intended. The **degenerate** part: the bar is *absolute growth/yr* with no notion
of ceiling proximity, so it becomes unbeatable **for everyone at once** when
capability saturates — collapsing the whole cap landscape instead of continuing to
reward the frontier leader. The on-screen "climbing staircase" anchor (§9b) dies
for the back half of every game.

### Relationship to the recent tech-tree trim

This is **structural and predates the trim** — capability is bounded by
`CAP_MAX`, so realized capability must asymptote and the absolute bar must
eventually become unbeatable regardless of tree size. The trim (lower max
elicitation 1.33→1.07; two fewer pretrain ceiling mults) likely lowers the plateau
*height* and pulls saturation slightly *earlier*, but does not create the dynamic.

### Proposed fixes (designer's call — not yet applied)

- **A. Make the target ceiling-aware (recommended).** Scale the required growth
  by remaining headroom, e.g. `target *= (1 − measured/CAP_MAX)` or compare
  *fraction of remaining gap closed* rather than absolute gain/yr. Growth
  naturally slows near a ceiling; the bar should too, so a frontier leader at 9/10
  isn't punished for the last mile being hard.
- **B. Soften / floor the miss cliff.** Have a miss *decay* momentum
  (`momentum *= k`) instead of hard-resetting to `1+0.85·growth_term`, or raise the
  floor, so one sub-bar refresh doesn't wipe all accrued confidence.
- **C. Add an unbounded-ish anchor term.** Tie part of the cap to *cumulative*
  released value or revenue level (a stock that ratchets), so a saturated-but-
  dominant lab's cap holds/keeps a slow climb instead of declining.
- **D. Don't penalize a refresh below your own best.** Score growth against a
  lab's *best-ever* released capability, not its *previous* release, so shipping a
  smaller model doesn't register as negative growth.

A + B together most directly restore the "release steps the cap up" behavior. All
are `[TUNE]`/balance changes touching the finance dynamics and the golden master;
flagged for the designer before implementing.

---

## Implemented: all four market-cap-plateau fixes (A–D)

Implemented the four fixes proposed in the investigation above. Each is a `[TUNE]`
finance-balance change; numbers are conservative drafts per §0.

**A. Ceiling-aware target bar** (`investment.py:_release_growth_term`,
`SCORE_TARGET_HEADROOM_FLOOR=0.15`). The required-growth bar is multiplied by
`max(FLOOR, 1 - measured/CAP_MAX)`, so a leader near the ceiling isn't asked for
linear growth the ceiling makes impossible. The floor keeps a sliver of treadmill.

**B. Gentle miss decay** (`investment.py:update_investment_momentum`,
`SCORE_MISS_DECAY_K=0.5`). A release that beats its own high-water mark but
undershoots the (softened) bar now decays momentum by `1 - K·miss_severity`
(severity-scaled) instead of hard-resetting it to a sub-1 floor. One sub-bar
release no longer wipes accrued confidence.

**C. Ratcheting valuation floor** (`market_cap.py`, new `lab.released_value_stock`,
`MARKET_CAP_RATCHET_K=0.05`). A monotonic stock accumulates realized revenue
(`revenue_rate·dt`, deterministic — no new RNG draw); a small fraction is added to
the cap target. A dominant lab's stock grows fastest, giving its cap a slow climb
after the score terms saturate, instead of decline. `update_market_caps` now takes
`dt` (caller `finances.py` updated).

**D. Growth & level judged vs best-EVER release** (new
`lab.best_release_measured_general` / `prev_best_release_measured_general`, set in
`turn_pipeline._do_release`; consumed in `_release_growth_term` and `lab_score`).
A refresh weaker than your own flagship is NEUTRAL (momentum carried forward
unchanged via a `None` return), not a negative; and the score's LEVEL term uses the
high-water mark, so shipping a smaller model never lowers your standing (releases
are permanent and the best model keeps earning).

### Harness result (balanced seed 0, late game)

Before: momentum cliffed to ~0.15 on nearly every late release; scores collapsed to
~0.4; every lab's cap declined together into the back half (e.g. the leader fell
from ~27k through the low-10k's). After: momentum decays *gracefully* (leader
~4.0→2.5 over ~13 turns); the landscape now DIFFERENTIATES — a lab that keeps
advancing climbs late (ANT ~37k→48k), a genuine plateau erodes gently toward its
ratchet floor (YOU, stuck at its high-water mark, ~48k→12k rather than cratering),
and the leader holds (~48–78k). Releases that advance the high-water mark step the
cap up; refreshes are neutral; only a real capability plateau slowly bleeds the cap
— the intended treadmill, not a collective collapse.

### Verification

- Full suite green (`unittest discover -s tests`, 16 tests).
- Golden master re-recorded (finance values moved; NO new RNG draws → determinism
  intact). Note added above the new `EXPECTED` block.
- Touched: `constants.py`, `lab.py`, `turn_pipeline.py`, `finances/investment.py`,
  `finances/market_cap.py`, `finances/finances.py`. New lab fields are NOT in
  `lab.snapshot()` directly; they affect the digest only through market_cap/cash.

### Tuning notes for the designer

- `MARKET_CAP_RATCHET_K=0.05` is a modest floor (~5–10% of cap late-game). Raise it
  if you want saturated leaders to climb faster; lower it if the ratchet dampens the
  treadmill too much.
- `SCORE_TARGET_HEADROOM_FLOOR` and `SCORE_MISS_DECAY_K` trade treadmill harshness
  against staircase smoothness; current values favor a visible, climbing staircase.

---

## Task: Optional tutorial walkthrough (frontend)

Added an opt-in guided tour of the board, selectable from the new-game modal.
Frontend-only — no backend, engine, RNG, or observation change, so the golden
master is untouched.

### What was built
- `simple_frontend_v1/js/tutorial.js` — new module. A data-driven step list
  (`TUTORIAL_STEPS`): each row names the tab to surface, an optional CSS selector
  to ring as a directional pointer, and the title/body string keys. The coach box
  floats bottom-right above the action bar; Back/Next/Skip drive it. It only calls
  `switchView` and toggles a `.tut-highlight` ring — it never reads game/true state,
  so it sits outside the §2 firewall by construction.
- `index.html` — `#tutorial-coach` element + CSS (coach box, pulsing `.tut-highlight`
  ring). z-index 18 keeps it under the new-game overlay (20).
- `js/main.js` — `wantTutorial` preference (mirrors the DEV pattern), tutorial
  checkbox in the new-game modal, `startTutorial()` fired after the game loads,
  `tutorialEnd()` when the modal reopens, handlers exposed on `window`.
- `js/strings.js` — all copy under `tutorial.*` and `newgame.tutorial.label`.

### Liberties taken (flag for review)
- **Tutorial defaults ON** in the new-game checkbox (first-timers get the tour;
  the choice is remembered like DEV). Flip the `wantTutorial` initializer in
  `main.js` if the designer wants it opt-in instead.
- The walkthrough copy (the `tutorial.*` strings) is authored DRAFT guidance; it
  paraphrases each tab's purpose and the true-vs-measured thesis. Not reviewed
  against design-doc §0/§7c wording — treat as placeholder prose for a copy pass.
- It is a tab-switching coached banner, NOT element-anchored coachmarks/tooltips —
  chosen because precise positional tooltips can't be runtime-verified here (§8,
  no JS runtime) and would be fragile against the responsive grid.

---

## Task: Intel frontier number vs feed mismatch

**Symptom.** The Intel tab's "frontier ≈" for a rival disagreed with the
`[measured general X.X]` printed in the feed when that same rival released a model.

**Cause.** Two surfaces published the SAME rival quantity at different fidelity:
- Feed (`turn_pipeline._do_release`) printed the rival's PRECISE measured general.
- Intel tab (`observation_builder._rival_public_entry`) builds a FOGGED estimate
  (`measured general × (1 + Normal(0, RIVAL_ESTIMATE_NOISE))`, cached per release).

**Resolution.** The design is explicit that rivals' stats are seen only as "much
worse estimates" (design_doc §805/§977; rivals' measured capability is "fogged",
§764). So the fogged Intel estimate is correct and the FEED was the over-reveal.
Fix: `_do_release` now prints the precise `[measured general X.X]` only for the
player's own lab (`lab.is_player`); a rival's release is announced as a bare
headline. The player gauges rivals from the fogged Intel estimate + public
benchmark scores, as intended. No RNG/action-stream change → golden master holds.

---

## Task: Intel alignment-evidence view + METR time-horizon recalibration

### Part 1 — Intel "alignment evidence" dossier (grouped by model)

New compiled view on the Intel tab listing every misalignment finding the player
has collected — safety-eval results AND external incident results — grouped by the
model they were collected on, newest model and newest finding first. The worry bar
above it stays as the SYNTHESIS; this is the raw evidence it synthesizes.

- **Firewall:** the dossier is a pure re-presentation of `lab.findings`, whose
  fields ALREADY cross to the player each turn via `new_findings=[dict(f) ...]`
  (`observation_builder.py`). Adding `Observation.alignment_evidence` exposes no new
  true state — it only regroups, tags each item's source (`research` vs `external`
  = incident-injected), and drops the internal worry-bar `weight`. Firewall test
  passes (no forbidden key crosses).
- **Determinism:** building the field reads no RNG and changes no legal move /
  action stream → golden master unchanged (verified).
- **Backend:** `_alignment_evidence(lab)` in `observation_builder.py`; field added to
  the `Observation` dataclass (`observations.py`).
- **Frontend:** Intel section re-laid-out (left column = worry bar on top + evidence
  dossier below; rivals unchanged); `renderAlignmentEvidence()` + helpers in
  `views.js`; copy under `intel.evidence.*` in `strings.js`; wired into `render()`.
  Evidence types covered: point/bound/existence/null/intervention (the eval-harness
  "number" type never enters `lab.findings`); unknown future types fall back to a
  prettified label rather than a missing-key string.

### Part 2 — METR time-horizon recalibration  [TUNE]

`METR_CAPABILITY_PER_DOUBLING` 0.8 → **0.45** (`constants.py`). The old curve gave
cap-9 ("ASI", existential endgame) only ~14 h and CAP_MAX ~34 h — far too short for
the superintelligence framing (design §115/§268-272). New curve `2·2^((cap−2)/0.45)`:
~3.4 h @cap5 · ~34 h @cap6.5 · ~14 d @cap8 · ~2 mo @cap9 · ~10 mo @cap10 (verified).
The chosen 0.45 is an assistant-picked balance number per §0 — flagged for the
designer. The horizon score is **display-only** (no game logic reads it), so this is
pure calibration: golden master and full suite unchanged. `fmtBenchScore` (`views.js`)
extended to format months/years so the recalibrated top reads cleanly.

---

## Task: AI-assist inert (and hidden) without a deployed model

**Symptom.** You could set AI-assist on a research item with no released model. It
"shouldn't be possible" in the UI, and it changed backend behavior.

**Cause.** With no `lab.current_best_model`, assist_potency() already zeroes the
budget discount, contamination, and finding bias — so assist *looked* like a no-op.
But `ResearchProcess.tick()` applies a duration-VARIANCE term whenever `ai_assist > 0`
*regardless of potency*: `effective_dt *= 1 + assist_speed + variance_draw*0.35*ai_assist`.
With no assistant `assist_speed` is 0 but the variance still rode in — a control with
no model behind it nonetheless jittered completion timing (mean-neutral, pure noise).

**Fix (two layers).**
- **Backend root cause** (`turn_pipeline._apply_research_action`): when `assistant is
  None`, store `ai_assist=0` on the ResearchProcess, so assist is inert end to end
  ("no model ⇒ assist does literally nothing"). `rng.normal()` is still drawn
  unconditionally per process per turn, so determinism/draw-count is unchanged — only
  whether the drawn value is *used*. Golden master re-recorded (the scripted player
  requests assist before its first release); determinism holds. See the note above the
  EXPECTED block in `tests/test_golden_master.py`.
- **Frontend** (`actions.legal_moves` + `research.js`/`views.js`/`strings.js`): added
  `legal_moves.assist.available = current_best_model is not None`; the per-card assist
  input is suppressed (replaced by a "needs a released model" hint) when unavailable,
  so the control can't be set in the first place. `queueProject`/`carryOutProject`
  already default a missing slider to 0, so suppression is safe.

---

## Task: Intel evidence — surface null findings clearly + jailbreak discoveries

Two additions to the Intel "alignment evidence" dossier.

- **Null findings** were already compiled into the dossier (the dossier includes
  every `lab.findings` entry), but the renderer faded them to 60% opacity, which read
  as "excluded/disabled". A null result is genuine (ambiguous) evidence, so the
  `.ev-null` style now keeps full legibility and just marks the item with a neutral
  grey left-rail instead of the accent rail (`index.html`). No data change.

- **Jailbreak discoveries** previously only set a per-model flag + a hidden_history
  note + a feed event — they injected no finding, so they never reached the dossier
  (and `hidden_history` is firewall-forbidden, so the dossier can't read it). Stage-1
  discovery in `latent_events.run_latent_phase` now injects an incident finding
  (`project_id="incident"`, `evidence="existence"`, axis `jailbreak_sensitivity`,
  concern scaling with the true sensitivity it exposed, weight 1.5), exactly like
  `deception_caught` / `shutdown_resistance`. It therefore lands in the dossier (as an
  EXTERNAL item), the feed, and the worry bar — jailbreak-sensitivity is a worry axis,
  so feeding worry is consistent.
  - **Determinism:** the new finding raises the responsible lab's worry LEVEL, and
    `RivalController` short-circuits a `self.rng.random()` draw on `level > 0.45`, so a
    crossed threshold shifts that controller's RNG stream → action stream → every
    digest. No engine-RNG draw added; determinism holds. Golden master re-recorded
    (note above the EXPECTED block). The concern/weight literals follow the existing
    inline convention in `event_catalog.py`'s incident findings ([TUNE]-ish).

## REGULATORY APPETITE (applied) — earlier, more responsive governance

Playtests showed governance IS the player's working counter to rival recklessness
(it contains the frontier and fines reckless labs) but **arrived too late** — policies
surfaced ~turn 26–30 and enforcement landed after the danger window, and the achievable
policies needed the player already rich. Moderately raised the regulatory appetite to
give a skilled player a timely lever (and to chip at the open "aligned but dominated"
problem — earlier audit/liability/disclosure slow reckless rivals' capability AND market
dominance):

| Constant | From | To |
|---|---|---|
| `WTR_START` | 4.0 | **6.0** |
| `WTR_FROM_LOW_APPROVAL` | 0.35 | **0.50** (per-yr per approval-point deficit) |
| `POLICY_PASS_BASE` | 1.1 | **1.4** (introduced→passed/yr) |

**Deliberately NOT touched**, so the change widens the win path without removing the
difficulty or the thesis: `POLICY_THRESHOLDS` — the *effective* regs stay near-impossible
(`interp_mandate` 60, `compute_cap` 97, the §0 "the regs that would actually work are the
hardest" lesson) — and the binds-the-compliant dynamic. Because the player-binding
policies stay gated by their high thresholds + the player's own lobby choice, the bump
mainly accelerates the **achievable, reckless-rival-targeting** policies (liability 22 /
disclosure 30 / audit 38), which hit reckless labs (incidents → fines, reckless releases
→ audit blocks) far harder than the clean, compliant player.

Golden master re-recorded (regulation timing shifts the scripted rivals' lobby/litigation
stream + the WTR-driven litigation math; intentional, determinism holds). NB: a
no-op-player probe shows only a modest timing shift because a passive player generates
little world-harm (regulation is harm-driven) — the benefit lands in actively-played
games where approval craters faster and the higher WTR baseline compounds with the
player's own lobby spend.

---

## AI-assist needs a model, not a RELEASED model

The AI-assist economy (§9b) was gated on `lab.current_best_model` — the most recent
**released** model. That conflated "the lab has a model that can do research labor" with
"the lab has shipped a model to customers." A lab automates its own R&D with its best
internal model whether or not it has released it; release is a market/governance act, not
a prerequisite for using your own model in-house.

**Fix.** Added a pure self-query `Lab.assisting_model()` that returns the most
research-capable of the released best (`current_best_model`) AND the model currently in
training (`model_in_training`, post-train/pre-release), or `None` if the lab has no model
at all. "Most research-capable" is ranked by the same `max(coding_rnd, 0.85*general)`
blend that `assist_potency()` scores on, so the chosen model is the one that would
actually contribute the most labor. The four assist sites now read it instead of
`current_best_model`:

- `rules.assist_potency()` — potency (budget discount + duration speedup).
- `turn_pipeline._apply_research_action()` — the per-process clamp that forces
  `ai_assist=0` when no assisting model exists, and the contamination/goal-mis stamping.
- `findings.run_safety_project()` — the assist-bias that blinds your own instruments.
- `actions` legal_moves `assist.available` — the frontend gate.

So "no model at all ⇒ assist inert" still holds end to end, but a model in training now
makes assist available and potent **before** release. Frontend hint strings/comments
updated ("needs a model", not "needs a released model").

**Liberty taken (flag for review):** when both a released model and an in-training model
exist, assist uses the **more capable** of the two. The design doc doesn't specify which
model does the labor when a lab has several; "best available" is the natural reading and
matches the potency intent, but a designer may prefer "the in-training one" or "the
released one" specifically. Noted for confirmation.

Golden master re-recorded: the scripted controller requests assist on projects started in
the pre-release window (model in training, nothing released yet) — previously inert, now
active — so budget/duration/contamination and every downstream draw shift. Determinism
holds (stable across `PYTHONHASHSEED`); intentional behavior change, not an RNG/firewall
regression (CLAUDE.md §8). Full suite (16 tests) green; firewall test passes.

---

## TASK: winnability — fines→valuation dominance lever (+ supporting eases)

**Goal:** make the game winnable by *clever* play (aligned ASI + net-positive impact +
market dominance) but *not easily*. Played 16+ games by hand via the deterministic
harness to diagnose and tune.

**Diagnosis (from hand-play, not scripted):** a clean player reliably reaches the
*components* — aligned ASI (composite ~0.1–0.3), rival containment via governance,
dominance-when-paced — but loses on one axis per game. The structural blocker is
**market dominance**: `lab_score` rewards capability + revenue + momentum and ignored
reckless harms, so reckless rivals out-valued clean play (the "aligned but dominated"
open problem in STRATEGY_LEARNINGS.md). A first attempt (reputation→valuation) was
**reverted** — jailbreak/incident reputation damage hits *every* lab (including the
player's own released models), so it penalised the clean player as much as rivals.

**Change (designer's steer — derive the dominance lever from FINES, not reputation):**
- NEW `Lab.fines_paid` accumulator; `regulation.py` adds the penalty to it when a lab is
  caught defecting. Only labs that DEFECT on active rules are fined — the compliant clean
  player never is.
- `investment.lab_score` multiplies a lab's score by `fines_factor =
  max(FINES_VALUATION_FLOOR, 1 - FINES_VALUATION_K * fines_paid / max(REF, revenue*REVENUE_YEARS))`.
  Judged against **revenue, not market cap** — a reckless leader's fines look negligible
  beside its inflated cap, but bite when measured against earnings (a lab fined several
  times its yearly revenue is a regulatory pariah). Constants (drafts, [TUNE]):
  `FINES_VALUATION_K=0.7, FINES_VALUATION_FLOOR=0.35, FINES_VALUATION_REF=1500,
  FINES_VALUATION_REVENUE_YEARS=2.0`.
- Supporting eases (grounded in the hand-play pace/squeeze blockers):
  `RIVAL_RECKLESSNESS_MULT["realistic"] 0.9→0.7` (slower racing) and
  `WORK_BUDGET_PER_YEAR 4.0→5.6` (quarterly pool 1.0→1.4, eases the §9b
  research/safety/elicitation squeeze that was silently dropping post-trains).

**Verified:** non-trivial (no-op player loses existential 6/6); misalignment thesis intact
(reckless rival mean composite ~0.57, >bar 6/6); fines discount bites when a lab is fined
(e.g. a rival with $1.9B fines on ~$1.3B/yr revenue → ~50% valuation cut → dropped to
last). Golden master re-recorded (intentional; determinism holds).

**OPEN / flagged for review (could NOT fully validate by a hand-won game):**
- A reckless *leader* that **complies** with the cheap achievable regs (audit/disclosure)
  pays $0 fines and dodges the lever (seed-dependent). The lever bites defectors, not
  compliant-but-reckless leaders. To make dominance reliable, a follow-up could make
  low-compliance labs defect on (or find it costly to comply with) the achievable regs,
  or raise enforcement catch rate, so reckless leaders actually incur fines.
- Reaching ceiling-9 (aligned ASI) stays **cash-gated** (`max_run_compute = cash×0.9`):
  a player who falls behind can't afford the ASI-grade run — a rich-get-richer loop the
  fines lever only partly breaks (by keeping the compliant player higher-ranked).
- A full end-to-end hand-WON game was not demonstrated this session; every component is
  achievable but the execution is genuinely unforgiving (which is "not easily"). These
  values are drafts for the designer; dial back if a skilled player wins too readily.
