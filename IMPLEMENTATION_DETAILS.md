# IMPLEMENTATION_DETAILS — mechanisms in the code that the design doc doesn't describe

**Scope.** `design_doc.md` is the authoritative *what we build*. This file is the
companion catalog of subsystems, fields, and structures that **exist in the code but
are not described (or are only gestured at) in the design doc**. It is descriptive,
not authoritative: where an entry and the design doc disagree on intent, the design
doc wins and the divergence is logged in `ISSUES.md`. Keep this current as the code
grows — when you add a mechanism the doc doesn't mention, add it here.

Audited 2026-06-18 against `design_doc.md`. Locations are paths under `backend_v1/`
(or `cli/`) and may drift — grep the symbol if a line moved.

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
  fraction, lobby stance, post-train mode) compiled by `make_strategy`.
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

## Frontend (`simple_frontend_v1/js/main.js`) — start-game gate

- **Mandatory new-game modal.** On load, `init()` forces `showNewGame({initial: true})`,
  which renders without a cancel button (and the overlay has no backdrop-dismiss), so a
  game cannot be skipped. A module-level `started` flag is set only when `newGame()`
  completes; `render()` keeps `#endturn` disabled and `endTurn()` early-returns until
  then. A turn cannot be advanced until a game is explicitly started through the modal.
