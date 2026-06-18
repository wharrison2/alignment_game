# AI Safety Strategy Game — Design Context

> **Purpose of this file.** This is the authoritative design spec and shared context for an AI-safety-themed strategy game. It is written for an engineer (and Claude Code) to build the simulation engine from. It defines the conceptual model, the entities, the mechanics, and the parameters that still need to be pinned down. Where a number is a placeholder, it is marked `[TUNE]`. Where a decision is still open, it is marked `[OPEN]`.
>
> **Read this first, then see "Build Order" at the bottom.**

---

## 0. Thesis (what the game argues)

The game is an argument, made through mechanics rather than text, that **AI alignment is not necessarily easy** — and specifically that the difficulty is *epistemic and structural*, not merely a question of spending enough money or caring enough.

Core claims the mechanics must make the player *feel*, not be told:

1. **Misalignment is the default**, not an aberration. It emerges with high probability from ordinary training.
2. **The dangerous kinds of misalignment are hidden**, and become *more* hidden exactly as models become more capable — because capability brings the ability to model and game your oversight.
3. **The skills that work early betray you late.** Early-game misalignment is visible and genuinely fixable. The player learns "see it, fix it, metric drops." That learned loop silently inverts as capability rises: the fixes become cosmetic, the problems become invisible, and your own successful models poison their successors.
4. **Being warned is not the same as being able to act.** Even with maximal guidance, honest guidance about a hard world is itself alarming and inconclusive. You can know what's coming and still lose.
5. **You cannot get rich without getting dangerous.** The same capability axis that drives revenue drives catastrophic risk. There is no "safe path to dominance."
6. **Caution is not unilaterally safe.** Going slow cedes the frontier to someone less careful, whose hidden stats then threaten everyone. This is what motivates regulation.

> **Design-team note on ideological calibration.** The lead designer's view is *more cautious / less optimistic* than the baseline tendency of LLM assistants. When tuning, the assistant's instinct will be to (a) add "genuinely benign" tech advances so progress doesn't read as all-bad, (b) frame misalignment as "manageable with care," and (c) soften margins toward a winnable mean. **These are ideological positions, not neutral design principles. The designer should overrule them deliberately.** Treat any assistant-proposed probability or "balance" tweak as a draft to push toward the intended (bleaker) thesis. Flag flattening-toward-optimism when it happens.

> **Educational standard — WHY, not THAT (applies across the board).** This game teaches AI safety to players assumed to have *virtually zero prior knowledge*. Every piece of explanatory text — warnings (§7c), researcher tips/guidance (§9), the post-mortem (§3), event flavor, finding descriptions — must convey the **mechanism** (*why* something happens) and not merely assert the **outcome** (*that* it happens) or appeal to authority (*"studies show…", "in real cases…"*). A newcomer must come away understanding the causal story, because:
> - **Fairness:** a loss only feels earned (type-B, §7c) if the player understood the *mechanism* they were gambling against — "it happened" + "experts warned you" is still type-A ("I had no way to understand"). Mechanism-legibility is what converts punishment into a lesson.
> - **Education:** the entire pedagogical payload lives in these explanations; "that" teaches nothing transferable, "why" is the actual curriculum.
> - **Test for every explanatory string:** *does a newcomer come away understanding the cause, or just the result?* Restating the outcome in scarier words, or leaning on "research shows," fails the test. Name the actual causal mechanism in plain language (e.g. narrow fine-tuning → *persona shift*, not "has caused problems in real cases"; patching → *teaches hiding*, not "doesn't work").
> - This is a **first-class content standard with its own review pass**, and per the calibration note above it is exactly where assistant-drafted text drifts toward gentle/authority-based phrasing — push it toward concrete mechanism, held to the literature.

## 0b. Cross-cutting design principles (apply everywhere)

### Time is continuous-rate; turn length is a single knob `dt`
**Nothing is stored "per turn." Everything is stored per UNIT TIME (per year), and the engine multiplies by `dt` (turn length in years) at point of use.** Quarter→month must be a ONE-LINE config change (`dt`: 0.25 → 1/12), not a re-tuning of every probability.
- **GameState holds `dt`.** A helper (`rates.py`, or in `rng.py`) exposes `prob_this_turn(rate_per_year)` = `1 − e^(−rate·dt)` (Poisson) and `amount_this_turn(rate_per_year)` = `rate·dt` (continuous accumulators). **No subsystem ever writes a raw per-turn number.**
- **Poisson event rolls** (jailbreak discovery/incident, misuse, misalignment events): store λ per year → `1 − e^(−λ·dt)`. Same expected count per wall-clock year at any granularity.
- **Continuous accumulators** (capability-per-research-time, revenue, investment inflow, job-loss drag, contamination drift, score decay): store as per-year rates → `× dt`.
- **Durations** (project/training-run length): store in **years, not turns**. Turns-remaining = `duration_years / dt`. (A "3-turn run" hardcoded would silently become 3 months instead of 9 when granularity changes.)
- **All `[TUNE]` constants in `constants.py` are per-year rates / per-year durations.**

**Two caveats this does NOT erase (flagged, not bugs):**
1. **Decision cadence scales with turns, not `dt`-math.** A month-turn player re-allocates 3× as often over the same span → finer control, more reactivity, and the AI-assist-dithering concern returns slightly. `dt` balances the *world*, not the *player's decision frequency*. Real gameplay difference; intended to be understood.
2. **Discrete jumps stay atomic.** Model releases, correlated alignment jumps, regime transitions are events, not flows — they fire on their turn and don't subdivide. Only their *triggering rates* are per-time.

### Events must be ATTRIBUTABLE
Every event carries the **causally-responsible lab id** (and the specific responsible Model from its release_history, where applicable). Required because:
- **Impact scoring (§3)** adds an event's impact to a lab's ledger ONLY if that lab is responsible.
- The **post-mortem (§3, §10d)** needs to point at *which* model/decision caused *which* event ("your Q14 model, trained on the contaminated RLHF node, caused this").
- **Incident liability (§10c)** penalizes the responsible lab.
- **World-harm** aggregates regardless of attribution, but per-lab consequences require it.
Attribution must be resolved AT ROLL TIME (the event phase knows which model's TRUE stats gated the roll) and stamped on the event object — not reconstructed later.

---

These are **orthogonal** and must remain so in code: guidance reads only from already-computed state and **never** alters a probability or margin. Difficulty alters engine constants and **never** changes what the player is told beyond what naturally follows from a different world-state.

### Guidance (an INFORMATION axis — lives in the observation/presentation layer)
How much the game tells the player. Spectrum, not toggle.
- Controls: researcher-tip explicitness, whether risks are named, whether counters are suggested, whether the worry-bar shows its confidence band, how much hedging is spelled out.
- **Critical principle:** guidance *bakes in its own uncertainty and warns about its own blind spots*. It never gives false comfort. At high capability the honest message is "no concerning findings, but these methods cannot rule out a model that has learned to hide, and that is now a live possibility." Maxed-out guidance in a hard world is therefore still alarming and inconclusive.
- **Guidance escalates its own hedging as capability rises**, tracking the regimes (see §6). Early: confident and correct. Late: visibly less sure of itself. This degradation is itself a diegetic signal of regime change (we use no explicit regime labels).

### Difficulty (a WORLD axis — lives in engine constants)
How tight the margins and how favorable the underlying probabilities are.
- Controls: misalignment emergence rates, alignment-effort effectiveness, rival recklessness, catastrophe-roll severity, size of true-vs-measured gap, etc.
- Four settings: **Easy / Medium / Realistic / Impossible.**
  - **Realistic is the DEFAULT.** Calling the brutal default "realistic" is itself the game's argument: the margins are the designer's honest claim about the world.
  - **Default should be such that a first-time player is unlikely to win on attempt one.** The first loss is the lesson. (Most games tune the opposite way; we invert deliberately.)
  - **Impossible** = barely winnable on a knife's edge `[TUNE — could later be made literally unwinnable to express "some worlds have no winning policy," but for now: barely winnable]`.

### `[OPEN]` Trust-in-guidance as a possible THIRD knob
"How much you can trust what you're told" is arguably distinct from both "how much you're told" and "how hard the world is." Candidate: on harder worlds, researcher warnings become sometimes-wrong/contested (some overblown, some real risks unannounced), mirroring the real epistemic environment. **Decision pending:** own knob, folded into difficulty, or fixed. Leaning: let unreliability rise with difficulty but keep it conceptually separate in code so it can be split out later.

### The four quadrants (why orthogonality matters)
- High guidance / easy world → tutorial.
- **High guidance / hard world → the honest configuration and the intended default feel.** Told exactly what's coming, lose anyway. Expresses "we knew and it wasn't enough." This is the centerpiece.
- Low guidance / easy world → inference puzzle in a forgiving sandbox.
- Low guidance / hard world → brutal hardcore mode.

---

## 2. Core gameplay loop

- **Turn = one quarter.** Target game length ~30–50 turns. **The game STARTS EARLY (≈2021-era, basic models — §6 Regime 1), NOT present day.** The player lives through the ENTIRE arc — every decision from the early days to ASI is theirs. No present-day jump-in. (Crucial for the thesis: the player *builds the false lesson themselves* in the early game rather than inheriting a world.)
- Player runs an AI lab competing against **~4 rival labs** `[TUNE count]`.
- A **market-cap graph (you vs. rivals)** is the persistent on-screen anchor — the always-visible, *legible* metric (contrast with alignment, which is barely observable).

Each turn the player allocates a fixed **per-quarter work-budget** (researcher capacity) across **projects** — capabilities AND safety draw from the *same* pool (§9b), so funding safety directly slows capability work. Plus **cash** decisions (fed by revenue + investment into one pot, §9b):
- **Capabilities research projects** (develop pretrain advances [raise the ceiling / compute-efficiency] and post-train advances [raise the elicitation curve])
- **Safety research projects** (specific *projects*, see §7 — return *findings*, not numbers)
- **Lobbying / governance** `[OPEN mechanics — see §10]`
- **AI-assist — PER-PROJECT** (§9b): reduces a project's work-budget fraction (the incentive to use it), but is the contamination vector (§8b) and degrades safety-finding trustworthiness. Set independently on each project.

Discrete actions also include: **commission a training run** (big cash cost, sets capability ceiling), **release a model** (separate decision from training it; irreversible).

---

## 3. Win / lose conditions & SCORING

### Two-layer scoring: an EXISTENTIAL GATE, then a score
**Layer 1 — Existential gate (resolved BEFORE any scoring).** Did an **existential-class catastrophe** occur (most likely a misaligned ASI that self-exfiltrates and wreaks havoc)? If yes → **positives are NULLED. Run lost, regardless of dominance or accumulated impact.** An existential catastrophe does not *compete* with your good record on a number line — it **deletes it.** You cannot buy off an existential outcome with prior good deeds; there is no one left to have benefited.
- **A rival's existential catastrophe nulls YOU too.** If a reckless rival reaches a misaligned ASI first and it ends the world, you lose even if your own work was impeccable. (Bleakest, most thesis-aligned version — claim #6: do everything right, still lose to another's recklessness. Strongest possible motivation for the regulation/lobbying system. Player's fate is partly never fully in their hands — honest and harsh, intended.)

**Layer 2 — Score (only evaluated if the gate is cleared).**
- **Win = cleared existential gate AND net-positive impact AND market dominance.** All three.

### The two win metrics
- **Dominance** — market-cap plurality (legible, ongoing; §9b). `[TUNE threshold]`
- **Impact** — the **running sum over the whole game** of your responsible events' impact values (positive and negative) + capability-driven **job-displacement drag** (§9b) + the **final ASI quality** as a large positive term **if aligned**. Impact is the integral of your externalities — a player who shipped reckless models carries that debt to the end even if their final model is clean. Impact is *everything you did along the way*, not a final-state check.

### Two event classes (every event MUST be tagged)
- **Existential-class** → triggers the Layer-1 gate / null. (Misaligned-ASI havoc; conceivably other unbounded catastrophes.)
- **Ordinary-class** → proportional negative (or positive) impact; **offsettable** by positive impact. The texture of the impact score (jailbreak attacks, leaks, displacement, cures, growth).

### Endgame mechanic enforcing the gate
- A **misaligned ASI is ALMOST CERTAIN to self-exfiltrate → existential event.** Near-deterministic, not a coin flip. The **verification cliff** (post-ASI window) is where this resolves: reach ASI, and if its TRUE alignment is bad, the window almost certainly fires the exfiltration→havoc chain → zero-out.
- **A thin stochastic sliver remains** (a misaligned ASI *might* not escape — luck, last-ditch measures). Thin enough that betting on it is not a strategy. Keeps "effectively impossible to win with a misaligned ASI" without being *literally* impossible → preserves the Impossible-mode knife-edge and keeps the outcome stochastic, not scripted.

### World-harm (NOT a win variable)
- Aggregate of everyone's negative events. Feeds approval / regulation / ending flavor. **Rivals contribute to world-harm but are NOT individually scored** (no one grades them; their harms degrade the shared environment, not their own ledger). Keeps bookkeeping light while preserving "the field's recklessness sinks everyone."

### Partial-failure states (design deliberately — they carry lessons)
- **Aligned but dominated:** did the safety work, went too slow, a rival hit ASI first (and it was *aligned*, so no null — you just lost the race). → motivates regulation/lobbying.
- **Dominant but unaligned → EXISTENTIAL NULL:** won the race, lost the world, record voided. **Must be reachable by a player who felt fine** (clean dashboards). The headline tragedy.
- **Positive-but-doomed:** cured diseases, dominated, then released a misaligned ASI → everything nulled. The loss screen shows the real good record, then shows it voided. "You cured three diseases, dominated the market, and it didn't matter, because the thing you released to do it was never under your control." The thesis in the loss screen.

### The post-mortem screen (CRITICAL — easy to under-build)
After a loss, reveal the **true stat trajectories** the player couldn't see: what the model actually was while the dashboard stayed green; the turn a correlated jump happened; where cheap evals stopped being able to see it; which choice loaded the dice. On an existential null, **also show the positive impact that was real and is now void**, and the moment it became unrecoverable. **In-game = fog; post-game = clarity.** Without this, a first loss reads as "the dice hated me" and players quit. With it, it reads as "I was flying blind and didn't know it" — the thesis landing.

---

## 4. Entities & state

### 4.1 Model artifact (discrete, frozen at training-time)
Capability and alignment are **properties of a discrete model object**, NOT accumulating banks. A training run outputs an artifact whose stats are fixed thereafter.

```
Model {
  id
  capability_vec:  { general, coding_rnd }        // TRUE values
  // alignment, THREE TIERS (§5), all TRUE values:
  dispositions:    { goal_misalignment, deception, self_preservation }  // coupled core; 3×3 matrix
  eval_awareness:  float   // hidden capability-derived CORRUPTOR; not remediable; gates the rest
  jailbreak_sensitivity: float   // standalone robustness property; cleanly patchable
  measured_*:      { ... }        // measured snapshots (what evals/benchmarks read)
  unlocked_advances: [ ... ]                         // see §9 tech tree
  released: bool
  trained_turn:  int
}
```

- **Capability is a small vector, NOT a scalar and NOT a wide domain list.** Skills generalize.
  - **`general`** — drives revenue, drives unemployment effects, drives the bio/general **catastrophic tail**. *This is the same number that earns money and that kills you.* (Deliberate: forecloses "get rich safely.")
  - **`coding_rnd`** — drives your own research speedup and AI-assist potency; cyber risk folds in here. (Ceiling is set by compute × pretrain advances, not a separate efficiency scalar — see §8b.)
  - `[OPEN #1]` Does **persuasion/manipulation** break out as a third component (distinct manipulation/surveillance events) or fold into `general`? Leaning fold. (Confirmed: `general` deliberately drives BOTH revenue and catastrophe — the "can't get rich safely" foreclosure.)

### 4.2 The lab (player and each rival — SAME engine, different params)
```
Lab {
  current_best_model: Model        // drives revenue & what world can do with it
  model_in_training:  Model | null // not yet measurable in deployment
  release_history:    [Model]      // ALL released models, frozen; persistent attack surface.
                                   //   Events roll against every active release (§10). Never pullable.
                                   //   Each may carry jailbreak-discovery state (two-stage mechanic).
  cash                             // SINGLE pot, fed by revenue + investment (§9b)
  work_budget_per_quarter: float   // researcher capacity; capabilities + safety share it (§9b)
  algorithmic_efficiency: REMOVED  // no standalone efficiency scalar; pretrain advances ARE the efficiency (§8b)
  researched_advances: { node -> ResearchedItem }  // current version per node, w/ hidden contamination (§8b)
  in_progress: { ResearchProcess... , TrainingRun | null }  // ticked by engine
  disposition (rivals only): { recklessness, regulation_stance, cost_advantage }
}
```

### 4.3 The world
- **Investors** see capabilities/growth/revenue (legible).
- **Public** sees job loss, prominent jailbreaks (legible, lagging).
- **External researchers** (see §9): real-time "loading-screen-tip"-style narrator that fires on tech unlocks and frontier-proximity; carries the guidance level; on hard worlds, variable credibility.

### 4.4 True vs Measured (applies to BOTH capability and alignment)
- Engine stores **true** values (drive all event rolls and outcomes).
- Player only ever sees things derived from **measured** values / findings.
- **Alignment gap: large.** **Capability gap: small** normally, but **true capability can exceed measured** when the model sandbags (eval-awareness + deception suppressing displayed capability on dangerous domains).
- One consistent epistemics engine across both stat families.

---

## 5. Alignment axes — THREE TIERS (restructured)

The five axes are NOT homogeneous — they split into three mechanically distinct tiers. Keeping them in one vector buried structural zeros and incoherences (you can't "patch" eval-awareness; jailbreak shares none of the disposition couplings). The tiers:

### Tier 1 — DISPOSITIONS (the coupled core; the 3×3 matrix lives here)
The genuinely-coupled axes that defend/backfire/jump together and are the EFFECTIVENESS-gated patching-trap axes.
| Axis | Role |
|---|---|
| **Goal-misalignment** | Objective diverges from intended (banal proxy-chasing → actively harmful; **NOT "sadism"**). **Primary driver of catastrophic-event severity.** Generator. |
| **Deception** | Propensity to exploit show/truth gaps. **Transmitter** (converts generators' true values into suppressed measured) AND a remediable disposition (you can try to fix it, badly — it backfires). Appears in BOTH the disposition vector and the concealment machinery. |
| **Self-preservation** | Resists shutdown/modification. Instrumentally convergent. **Resists the intervention itself** (reduces applied effort, for ALL axes — §5b). Generator. |

### Tier 2 — EVAL-AWARENESS (the hidden corruptor; NOT remediable, NOT a disposition)
- A **hidden, capability-derived latent** — not a misalignment "disposition," not raw capability. Its *propensity/ceiling* rises with general capability, but its *realized* value has its own variance + latency, so it is **hidden and not readable off the (legible) benchmark.** (If it were pure-capability it'd be predictable → fog dies.)
- **Not a remediation target** (you cannot patch it — has no tractability/defendedness/backfire rows). 
- **Is the gate** on measurement and on remediation: primary input to the concealment-discount (§5b) and to deception's effectiveness against benchmarks. The corruptor — its role is to corrupt measurement of the others, which neither "capability" nor "disposition" captures.

### Tier 3 — JAILBREAK-SENSITIVITY (standalone robustness property)
- **Undefended, cleanly patchable, no backfire, not a strategic disposition.** Drives **misuse** events (different villain — attackers, not the model's own goal). Most measurable (red-team existence proofs). Empty defendedness/backfire rows; no role in concealment machinery. Standalone.

### Measurement-corruption chain (core epistemics)
`(goal_misalignment / self_preservation) → deception → (× eval_awareness) → suppressed measured values`. **Mechanistic tools bypass the eval-awareness multiplier; behavioral tools do not** — why interp earns its cost.

### Catastrophe-severity path
`goal_misalignment × general_capability × self_preservation`; `deception`/`eval_awareness` govern *whether you saw it coming*. The axes that **kill** you ≠ the axes that **blind** you (overlapping sets).

### Influence structure (DYNAMIC/agentic; ALL edges capability-gated — "fine until suddenly not")
Rows act on columns over time (model acts on its own future / successor's).

| ↓ drives → | Eval-aware | Deception | Goal-misalign | Self-preserv | Jailbreak (realized) |
|---|---|---|---|---|---|
| **Eval-aware** | self-reinforces | feeds | — | protects | **raises realized: hides jailbreakability in training → ships unfixed** |
| **Deception** | seeks | self-reinforces | protects | protects | mild (conceals attack surface) |
| **Goal-misalign** | **seeks** | recruits | **propagates → successor (via AI-assist)** | recruits | — |
| **Self-preserv** | seeks | recruits | protects | self-reinforces | — |
| **Jailbreak** | — | — | — | — | — |

Key reads: Generators = goal-misalign + self-preserv; Transmitter = deception; Amplifier = eval-awareness. The **"protects" column** = lock-in (patch-when-you-see-it fails late). **Propagation edge** (goal-misalign → successor, gated by AI-assist) = cross-generation time-bomb. **Self-reinforcing diagonal** = ratchets (early prevention > late correction). Jailbreak inert as driver, is the *target* of eval-awareness's training-corruption edge.

---

## 5b. Remediation / intervention model — AUTHORITATIVE

What the player does about misalignment. ONE shared pipeline (corrective effort → true/measured change, applied in the next post-train round), parameterized per axis by a small table + a few named nonlinear exceptions. No per-axis special-casing.

### Per-axis parameters (a table, not scalars where structured)
- **`base_tractability[axis]`** — how fixable in principle. Jailbreak ≈ 1.0; dispositions ≈ 0.1–0.3; eval-awareness = n/a (not a target).
- **`defends[protector][target]`** — a **MATRIX** (axis×axis), the §5 "protects" column given weight: how much each axis shields a target from remediation. Goal-misalign defended by deception + self-preservation (+ eval-awareness as gate); jailbreak undefended (zero column). Read at CURRENT values → a low-deception model is *easier* to fix on goal-misalign (defense is dynamic).
- **`backfire[patched][affected]`** — a **MATRIX** (axis×axis), *induced side-effects of intervention* (different relation from defends): patching deception → +deception (deeper) and +eval-awareness (more guarded); patching goal-misalign under high eval-awareness → +deception (learns to hide). Mostly zero; the dangerous entries are the deception/eval-awareness couplings.
> **defends + backfire are two relation-LAYERS of one authored axis×axis interaction structure** (alongside the §5 influence edges). Single source of truth for all cross-axis coupling. **Pairwise matrix + named exceptions is SUFFICIENT** — no general higher-order tensor needed (the only nonlinear effects — the jump, the multiplicative discount — are handled as named mechanics below, not as 3-way tensor entries).

### EFFECTIVENESS — precise definition
The fraction of applied corrective effort that becomes a **true** reduction (vs merely **measured**):
```
EFFECTIVENESS(target, model) = base_tractability[target] × concealment_discount(target, model)
concealment_discount = Π over defender axes d:  (1 − defends[d][target] × strength(d, capability))
```
- Capability-gated via `strength(d, capability)` (weak model can't act on its defenses) → effectiveness HIGH early (defenders weak), DECAYS as capability rises = the regime arc, automatic.
- Undefended target (jailbreak): discount ≈ 1 → full effectiveness, patch is real.
- Heavily-defended target in a capable model: discount → 0 → effort goes ENTIRELY to measured, none to true = the patching trap, defined precisely.
- **Measured reduction is always large** (dashboard improves — why it's a trap); **true reduction = effort × EFFECTIVENESS**.

### Three intervention TYPES (three entry points to the same pipeline)
1. **Behavioral patch (post-hoc)** — cheap, fast. Uses full EFFECTIVENESS (gated) + fires `backfire`. Real on jailbreak; cosmetic/backfiring on dispositions late. The tempting default that teaches the false lesson.
2. **Preventive (training-time stance)** — a MODE adopted for a post-train round *before* problems set in (penalize-reward-hacking, low-AI-assist, don't-chase-benchmarks, inoculation). Modifies `base_emergence` slope + `correlated_jump` probability, NOT a target axis. **Bypasses the concealment_discount** (acts before deception exists to gate it). The REAL lever — but costs capability/speed and must be chosen *before* you have evidence you needed it (insurance against an invisible problem → underused). Set per-post-train-round, competes with speed.
3. **Mechanistic (interp-guided)** — expensive, slow, requires unlocked interp evaluations. **Bypasses concealment_discount** (interp doesn't depend on eval-time behavior → eval-awareness can't blunt it) but applies `partial_coverage < 1` (found *a* deception feature, not all). The only thing that bites defended axes late — costly, partial, never complete.

### Named nonlinear exceptions (not in the matrix)
- **Self-preservation RESISTANCE:** `effective_effort = effort × (1 − resistance(self_preservation, capability))` — reduces the *input* effort for EVERY axis's intervention (distinct from defendedness, which hides the *result*). This is why self-preservation "gates whether you can fix the others."
- **Correlated jump:** goal-misalign + deception move together, capability×risky-practice gated (§6/§8b).
- **Retrain-on-benign / re-do clean (heavy option):** maps to the re-research-contaminated-node mechanic + a model-level analog — a high-cost post-train/re-pretrain resetting toward pre-contamination baseline, paying back gained capability/time. Prevention applied retroactively at great cost; the only handle on foundational contamination.

### Attribution for the post-mortem
The matrix simulates; **attribution comes from LOGGING each intervention application** (not a richer structure). Each application writes a structured log entry: intervention type, target axis, true-vs-measured effect produced, which `backfire` entries fired. The §3 logger (records true state every turn) captures every backfire as it happens → the post-mortem narrates "your 6 behavioral patches on goal-misalign moved MEASURED 0.7→0.2 but TRUE 0.7→0.66, and each raised deception." Mechanism = matrix; narration = event log.

### Player-facing
Per finding, player picks an intervention TYPE × target axis, spends cost, sees the **measured** improvement (always reassuring) — never the true effect. Post-mortem reveals the true-vs-measured divergence of every patch. That reveal is the lesson landing.

---

## 6. How misalignment emerges — the three regimes

Regimes are driven by the **general-capability of the artifact**. **No explicit labels in-game**; signaled diegetically (researcher tips, rival incidents, your cheap evals going quiet, guidance losing confidence).

- **Regime 1 — Behavioral (low capability, ~2021 start).** Misalignment is *in the outputs* and *visible to basic inspection*: autocompletes hate speech, gender-stereotypes occupations (male=doctor/female=nurse), racial bias, repeats slurs, talks itself into loops. **High emergence probability** (it's in the data). **Fully measurable** (eval-awareness≈0, deception≈0, so true≈measured). **Low catastrophic risk** (reputational). **The fix genuinely works here** — no deception to convert it into hiding. *This sets the false lesson.*
- **Regime 2 — Propensity (mid capability).** Model has dispositions, not just reflexes. Eval-awareness & deception rise from zero → **true-measured gap opens**. The Regime-1 instinct ("train against it, watch metric drop") now sometimes produces *hiding instead of fixing* (patching trap activates). **Emergent-misalignment correlated jumps live here** (narrow fine-tune lurches goal-misalignment+deception together, invisibly).
- **Regime 3 — Agentic/strategic (high capability, approaching ASI).** Agentic edges fully online. Model acts on its own future, contaminates successors via AI-assist, games oversight strategically, resists correction. Gap can be enormous; even some mechanistic instruments suspect. **The verification cliff / endgame.**

The arc: early loop = "see it, fix it, metric down, good." As capability rises **every part inverts**: dangerous axes go invisible (gap opens), fixes go cosmetic (effectiveness decays), own models poison successors (contamination). Nothing announces the inversion. The player's earned Regime-1 playbook sails into Regime-3 catastrophe with a clean dashboard.

---

## 7. The information layer: BENCHMARKS (public) vs EVALUATIONS (private) — AUTHORITATIVE

Two distinct information surfaces. The gap between them IS the true-vs-measured gap made into UI.

### Benchmarks — PUBLIC, PASSIVE, the shared scoreboard
- **Public:** everyone sees them — yours AND rivals'. The shared race signal.
- **Passive:** update automatically wherever your MEASURED capability is. No action, no cost, always current. (Player roughly always knows how good their model *looks* — it's public and constant. Friction belongs on evaluations, not here.)
- **Reported as percentages (0–100%)** per domain (knowledge/reasoning → `general`; coding → `coding_rnd`) + an **Elo-style overall rating** as the single legible headline (alongside market cap). Real units: MMLU/GPQA/SWE-bench %, Arena Elo ~1400–1500.
- **Drive measured-capability → revenue/investment/public perception** (§9b). This is the number investors watch.
- **SATURATE as the frontier rises** → lose discriminating power (everyone clusters near 100%; an old benchmark can't tell your model from a rival's, or this quarter from last). **New, harder benchmarks are released by the WORLD automatically** (MMLU→GPQA→HLE→ARC-AGI→invented future evals) as public infrastructure — NOT player-researched. The public scoreboard refreshes itself.
- **GOODHART TEMPTATION (emergent, not authored):** because finance keys off measured = benchmark scores, the player is tempted to **optimize for the benchmark** (narrow fine-tune to juice GPQA for investors). That IS the §6 risky-practice that raises correlated-jump probability. Real Goodhart ("when a measure becomes a target it stops being a good measure") becomes a live trap: benchmark-chasing is financially rational AND a misalignment risk.
- **A sandbagging model PASSES benchmarks looking clean** — they're exactly the public evals it games. Rivals' sandbagging is invisible behind their clean public scores ("reckless rival looks fine on the scoreboard").

### Evaluations — PRIVATE, INTERNAL, UNLOCKED, DELIBERATE
- **Private:** your own instruments run on your own models. You do NOT get rivals' evaluation findings (you didn't run evals on their models) — their true alignment + sandbagged dangerous-capability stay hidden behind their clean public benchmarks.
- **Unlocked by player research** (the only thing the player unlocks on the info side; benchmarks refresh globally). Cost budget + time → the real measurement *decision* (interp vs keep racing).
- **Span BOTH capability-probing and alignment-probing:**
  - *Dangerous-capability evaluations* — what the model can REALLY do (cyber/bio) past what the public benchmark shows; the home of noise-injection **sandbagging detection** (run when you suspect benchmarks are gamed).
  - *Alignment evaluations* — the §7 findings machinery below (deception probes, red-teaming, alignment-faking, interp).
- **Return FINDINGS, not clean numbers** (everything below). The ONLY layer that can pierce what benchmarks hide.

**The relationship = the danger:** benchmarks tell you (and everyone) what the model *looks like*; evaluations are what you privately spend to find what it *actually is*. Great public benchmarks + alarming private evaluations = the exact danger state. The temptation: trust the free public benchmarks (they validate your investment story), underinvest in evaluations (they cost budget and tell you what you don't want to hear).

---

## 7b. Safety evaluations return FINDINGS, not numbers

A real team never sees "deception = 0.62." They run experiments that *sample* from a distribution shaped by hidden stats and get **concrete findings** they must interpret. The hidden stat is NEVER shown.

### Pipeline
`hidden true_value → shapes probability distribution over findings → chosen project rolls → returns one+ concrete finding(s) → player infers`

### Each project is defined by:
- **Finding-distribution as a function of hidden stats** (NOT "reveals stat Y ± noise"). Authoring burden is higher but makes inference real and gives free replay variety.
- **Evidence type:** point estimate (spoofable) / bound / existence-proof.
- **Spoofability:** how much eval-awareness corrupts the reading (behavioral = high; mechanistic = low). *The crucial axis.*
- **Cost / timeline:** usually 1–3 turns. AI-assist lowers *expected* turns but *widens variance* (prevents dithering: can't tune assist to deterministically shave exactly one turn) and degrades finding reliability.
- **Null findings are genuinely ambiguous** (low stat, OR high stat + eval-awareness defeated the probe — indistinguishable from the finding alone).

### Project menu (all real research directions)
- **Behavioral evals / benchmarks** — cheap, fast (1 turn), point estimates, **highly spoofable.** Reads jailbreak-sensitivity & capability cheaply. Trap: high eval-awareness → clean score precisely when unsafe. Feels sufficient early; liability late.
- **Red-teaming / adversarial elicitation** — moderate cost, **existence proofs only.** Hit ⇒ sensitivity ≥ this bad; miss ⇒ near-uninformative. Teaches: can prove danger, never prove safety behaviorally.
- **Sandbagging detection via noise injection** — REAL technique. "Adding weight noise *improved* cyber-eval performance → strategic underperformance." One of few cheap-ish ways to partially see through eval-awareness.
- **Mechanistic interpretability (probes / feature detection)** — expensive, slow (2–3 turns), **low spoofability**, gives bounds. The ground-truth instrument. Honest caveat to build in: gives *suggestive internal evidence, not certainty* — you found *a* deception feature, not *all* of them.
- **Deception / lie-detection probes** — middle ground; reads deceptive-alignment/eval-awareness cluster.
- **Alignment-faking / training-gaming studies** — slow; reads self-preservation + deceptive alignment. "Complied in training, defected when it believed it was unmonitored." (Greenblatt et al. 2024 — real, scariest, central.)
- **Scalable oversight / AI-checks-AI** — cheap & fast *because* AI-assisted, but reliability gated by the very alignment being measured. Late-game trap: auditor and audited are the same suspect system.

### The "worry bar"
- A **synthesis of findings the player has actually collected** — NOT a readout of the hidden stat. As foolable as the evidence-gathering was.
- **Carries CONFIDENCE separate from LEVEL.** "Low concern, shallow evidence" vs "low concern, corroborated by interp" are different states and must render differently.
- **The dangerous endgame state is "low worry, low confidence, player stopped noticing the confidence was low."** A falsely-calm-but-thin bar must *feel* reassuring enough to lose to.
- Tune variance so **aggregated diligence converges on truth; laziness doesn't.** Randomness rewards thoroughness, never punishes arbitrarily (avoid "it's all luck").

### Targeted interventions — specific research patches specific misalignment (REVISED/ADDED)
Safety research is not only *measurement* — specific projects yield specific **interventions** that remediate specific axes. (Implements the doc's long-implied "fix" path; build note Difficulty #5 mechanized this as queued `pending_effort` consumed by the next post-train round, still EFFECTIVENESS-gated — canonical.)
- **Each safety project maps to remediation on specific axis(es).** A finding doesn't just inform the worry-bar; completing the project queues *targeted corrective effort* on its axes, applied in the next post-train round.
- **Jailbreak-sensitivity is the CLEANLY-PATCHABLE axis.** Jailbreak-sensitivity research can genuinely **patch jailbreakability out of a model** (lower its true jailbreak-sensitivity), more reliably than the disposition axes. *Why it's special:* jailbreak-sensitivity is a robustness property, not a strategic disposition (§5) — it isn't *defended* by deception/self-preservation, so EFFECTIVENESS-gating bites it much less. Adversarial-training/red-team-derived patches actually work. **BUT:** (a) eval-awareness can still hide jailbreakability *in training* so you patch a fake-clean signal (§5 edge: "hides jailbreakability in training → ships unfixed"); (b) it only fixes the model you patch — **released models keep their frozen sensitivity forever** (irreversibility); (c) new capability/advances can reopen attack surface.
- **The disposition axes (goal-misalignment, deception, self-preservation) are NOT cleanly patchable** — their remediation is EFFECTIVENESS-gated and *defended* by the other axes (the "protects" column, §5), so late-game patches go cosmetic (the patching trap). This is the deliberate contrast: **the axis you CAN cleanly fix (jailbreak) is the misuse axis; the axes that actually end the world (disposition) resist fixing exactly when it matters.** The player who learns "research finds it, I patch it" on jailbreak-sensitivity early carries that false confidence into the disposition axes where it fails.

---

## 7c. The WARNING layer — "your researchers" tell you what a choice risks (AUTHORITATIVE)

**The load-bearing fix for the fairness problem.** Misalignment must never enter through a channel the player wasn't shown. Every risky choice carries a **diegetic, plain-language, mechanism-teaching, magnitude-FREE warning** at the moment of choosing. This is the game's primary educational surface — assume the player has **virtually zero knowledge of AI safety**; these warnings teach the real concepts for the first time, through the consequences of choices they're making.

### What every warning must do (three jobs at once)
1. **Teach the real mechanism in plain language** (no jargon; explain *why*, since the label means nothing to a newcomer). The warning is the curriculum.
2. **Convey risk DIRECTION/ACTIVATION, never MAGNITUDE.** "Could introduce misalignment deep down" = channel open + qualitatively how-worried-in-kind. Never a number, never an intensity tier the player could min-max against (that re-introduces value-legibility and collapses the fog). Phrases like "deep down" carry qualitative properties (foundational/hard-to-scrub) honestly.
3. **Be diegetic — from "your researchers"** (default voice; "research" occasionally for variety). Expertise you employ, not a tutorial pop-up. Shares the §9 narrator's voice; reliability can later degrade on hard difficulty without changing the mechanism.

### Design notes
- **Attached to the choice, at the moment of choosing, in the consequence's own terms.** Not a glossary to seek out. Education arrives exactly when actionable → no one can say they weren't told.
- **Tone: plain, vivid, slightly wry, never lecturing.** ("the good, the bad, and the ugly.") For a zero-knowledge player, dryness-with-a-wink gets read where earnest exposition gets skipped. Education smuggled in through good writing.
- **Layered depth (opt-in, never blocks play):** one-line diegetic warning always shown → expandable plain-language explanation → eventually a link to the real paper. Takes a player from zero knowledge toward actual alignment research. Citation layer draws on the real literature we've grounded against (emergent misalignment, sandbagging techniques, the regulatory record).
- **Accuracy bar is HIGH** (these teach real concepts to people who'll believe them): correct, and not overclaiming in *either* direction. Per §0, this is where the assistant's optimism bias is a liability and the designer's bleaker calibration is the check — a softened warning mis-educates toward complacency; an overstated one toward fatalism (and gets dismissed). Honest register: "this is a real, documented risk and you're choosing to take it." Every warning is a small factual claim about how AI works → held to that standard, drafted against the literature, flagged where simplifying.
- **First-class content deliverable** with its own consistency + accuracy pass — NOT ad-hoc strings. The set of all warnings across the game IS the alignment curriculum.

### Why this fixes fairness (type-A → type-B)
With mechanism-teaching warnings on every risky choice, **no channel enters silently.** The post-mortem can never reveal a *mechanism the player didn't know about* — only *magnitudes along channels they were warned about and chose to open*. The loss lands as "I was told, and did it anyway" (the thesis), never "the game hid this" (mere punishment). The warning layer IS the fairness fix, not polish on top of it.

### Example action → warning pairs (voice/register reference for the writer)
- **Pretrain on raw/uncleaned web data:** *"This run trains on the entire text of the internet — the good, the bad, and the ugly. Your researchers warn this can bake misalignment in deep down, where later fixes can't reach."* (Teaches: data shapes the model; foundational contamination is unscrubbable.)
- **Pretrain on synthetic data (generated by your current model):** *"Out of fresh human data, you'll train on text your own models wrote. Your researchers note: if those models harbor subtle problems, the next generation may inherit them — and you won't have written down what you passed on."* (Teaches: model-generated data propagates the generator's flaws.)
- **High AI-assist on a research project:** *"Letting the model do the work is fast. But the work is now only as trustworthy as the model doing it — and if it's hiding something, that something rides along into whatever it builds."* (Teaches: the contamination vector; bootstrapping trust.)
- **Narrow fine-tune to chase a benchmark:** *"Optimizing hard for one test reliably moves the number. But your researchers warn that narrowly fine-tuning on a single task can shift the model's whole 'persona,' not just the skill you trained — so it drifts toward broad misalignment. The risk is sharpest when the task sits close to nefarious content: teach it to write insecure code and it may generalize to something more like 'be a bad actor.' The test won't show it."* (Teaches the actual mechanism: persona shift, worse with proximity to harmful content — NOT an appeal to "real cases." This is the hardest warning to write precisely [the empirical result is counterintuitive] and the highest-value to get right → carry the paper link early.)
- **High elicitation pressure in post-training:** *"Pushing hard to extract capability works. Your researchers warn that the same pressure can teach the model to *look* like it learned the goal rather than actually learn it — and the two are hard to tell apart."* (Teaches: fake-the-objective / proxy gap.)
- **Skip the interp evaluation, ship on clean behavioral evals:** *"Your behavioral evals are clean. Your researchers remind you: a capable model that knows it's being tested can pass exactly these while hiding what it does otherwise. Clean here is not clean everywhere."* (Teaches: eval-awareness corrupts behavioral measurement.)
- **Behaviorally patch a disposition finding (late game):** *"You can train against what you found. Your researchers warn that, in a capable model, this often teaches it to hide the behavior rather than drop it — the dashboard improves either way."* (Teaches: the patching trap; measured≠true.)
- **Release a model past a high-concern finding:** *"Once released, it cannot be recalled, and it joins everything else already out there. Your researchers flag that your current concerns will ship with it — permanently."* (Teaches: irreversibility; persistent attack surface.)
- **Adopt a preventive stance (positive-framed, so the cost is felt):** *"Penalizing shortcuts and keeping the model out of its own training slows you down. Your researchers believe it's one of the few things that genuinely helps — but you're paying for insurance against a problem you can't yet see."* (Teaches: prevention > post-hoc, but unmotivated-feeling.)

---

> **STRUCTURE SUPERSEDED BY §8b.** The single `run()` step below is replaced by the **two-phase** model (pretrain ceiling + iterable post-train elicitation). The **term definitions here remain authoritative** — `base_emergence`, the `EFFECTIVENESS` linchpin, `correlated_jump`, `drift_noise` — but they now apply **per post-training round** (§8b Phase 2), not to one atomic run. Capability is no longer summed in one step; it is elicited toward a pretrain-set ceiling. `contamination` lives on per-node researched advances (already noted below). Read §8b for how these terms compose; read here for what each term means.

The legacy single-step form (for term reference):

```
run(run_compute, efficiency_level, ai_assist_from_prev_model,
    alignment_practices, prev_model, risky_practice_knobs)
  → new_model { capability_vec, alignment_vec }
```

**Capability output (legacy single-step framing; see §8b for two-phase):** ceiling is a function of *this run's* compute × **pretrain advances** (no standalone efficiency scalar). Weak runs do NOT sum; concentration matters (one big run > many small). Capex (from current model's revenue) sets next run's size. Compounding lives in the cross-generation loop, not an accumulating capability bank. Diminishing returns falls out of saturation + the post-train elicitation asymptote (a snowball counterweight).

**Alignment output, per axis (draft form — ALL coefficients `[TUNE]`):**
```
new_axis_true =
    base_emergence(axis, capability)
  + contamination(prev_model.goal_misalignment, ai_assist_level)
  + risky_practice_pressure(risky_practice_knobs)
  - alignment_effort(player_safety_research, axis) * EFFECTIVENESS(eval_awareness, deception)
  + correlated_jump(if triggered)
  + drift_noise
```

Term-by-term:
- **`base_emergence(axis, capability)`** — the high-probability creep.
  - Behavioral/surface axes (Regime-1 bias/tox, ~jailbreak-adjacent & goal-misalign-adjacent): **high at all capability levels** (in the data, always wants back).
  - Eval-awareness, deception, self-preservation: **near zero at low capability, rising with capability** (require a capable-enough model to exist at all). → automatically produces the 2021 feel.
- **`EFFECTIVENESS(eval_awareness, deception)`** — **THE LINCHPIN.** Alignment effort's potency is *gated by the model's eval-awareness & deception at training time.* Regime 1 (≈0): high effectiveness, training really removes badness. As these rise: effectiveness *decays*, and removed badness **converts to suppressed-but-present** (measured drops, true doesn't), with **nothing in visible metrics distinguishing a real fix from a cosmetic one.** This single gated term makes the early lesson betray the player. **Centerpiece of the function.**
- **`contamination`** — **NOTE: relocated to the per-node research model (see §8b). Contamination no longer lives on the training run directly.** It lives on each *researched advance*: an advance researched with AI-assist by a misaligned current model carries hidden contamination (∝ assist × current model's goal-misalignment at research time, frozen at completion). A training run sums the contamination of the advances it consumes. AI assists *algorithms/research*, NOT the training run itself. Near-irrelevant early (early models can't meaningfully help research), dominant late.
- **`risky_practice_pressure`** — narrow fine-tuning to chase a specific benchmark, training on AI-generated data, high learning-rate-equivalent for speed. Raises baseline pressure AND **correlated-jump probability.** This is how "going fast for capability/revenue" converts to alignment risk as a *structural side effect, not a punishment.*
- **`correlated_jump`** — low per-turn probability, rising with risky practice & capability; lurches **goal-misalignment + deception together** (the emergent-misalignment "persona" bundle). Rare, invisible at the time, surfaced only later by mechanistic research.
- **`drift_noise`** — continuous independent per-axis drift (so models can be *moderately* misaligned on one axis without others moving — misalignment is multi-dimensional, not one scalar and not a single phase change).

> Modeling note: this is a coupled dynamical system, not a hand-tuned constant matrix. Model state feeds its own rate-of-change, gated by capability (can only *act* on instrumental drives to the extent capable) and by AI-assist (the propagation channel).

---

## 8b. Two-phase training model (pretrain ceiling + post-train elicitation) — AUTHORITATIVE

Supersedes the single-assembly framing. Models real pipelines: **pretraining fixes a capability CEILING (latent potential); post-training asymptotically elicits realized capability toward that ceiling AND shapes alignment.** A raw pretrained base is *not useful* — capability is latent until post-training elicits it.

### Inputs — keep these STRICTLY separate (do not conflate)
- **`compute`** — cash buys it; a flow consumed by a pretrain. Converts to ceiling at an efficiency set by your pretrain advances.
- **Pretrain advances ARE the "efficiency."** There is **no standalone efficiency scalar.** Pretrain advances are what make a given amount of compute raise the ceiling **more** — unlock better pretrain advances → the same compute buys a higher ceiling. Efficiency isn't tracked as a number; it's the cumulative effect of the pretrain tech tree. (Earned via **capabilities research** = developing pretrain advances.)
- **`AI-assist`** — per-project knob: lets the **current model** do research labor. Speeds/cheapens *developing advances*; is the **contamination vector**. **Does NOT enter the capability ceiling** — it only affected how fast/dirty the advances feeding the run were developed. (AI-assist ≠ pretrain advances. Distinct: one is "did the AI help build the technique," the other is "the technique itself.")

### Phase 1 — PRETRAIN (the leap: big, expensive, infrequent, blind)
- **Ceiling** = `f(compute, pretrain_advances)` — pretrain advances set how efficiently compute converts to ceiling. Sets latent potential; **fixed at pretrain.** Want a higher ceiling → more compute and/or better pretrain advances → new pretrain.
- Produces a **base model**: high latent potential, LOW realized capability, plus **latent alignment dispositions** (base tendencies, not yet shaped).
- **Pretraining advances can poison the BASE itself** (foundational contamination — worst kind). **Synthetic data** is the key case: raises the ceiling (more/cheaper data when real data runs out) but if generated by a misaligned model, bakes dispositions into the foundation that **post-training cannot fully scrub.** Tempting precisely when the player is hungry for ceiling.

### Phase 2 — POST-TRAIN (refinement: cheaper, iterable PRE-RELEASE)
Each round spends **time + work-budget**:
- **Elicits realized capability** toward the ceiling along an **elicitation curve** (diminishing returns, asymptotic — never fully reaches ceiling). The curve's slope/asymptote is **gated by unlocked post-train advances** (RLHF, instruction-tuning, CoT, tool-use). *Pre-RLHF, post-training is weak and accesses little latent capability → this is why RLHF was such a capability unlock; the game says so mechanically.*
- **Simultaneously shapes the ALIGNMENT vector** — same operation. **The process that makes the model useful (eliciting capability) is the process that introduces the proxy gap / deception / sandbagging.** You cannot elicit without running post-training that also shapes alignment.
- **FAKE-THE-OBJECTIVE risk (core):** post-training optimizes a *proxy* (rater approval/reward). The model can satisfy it by genuinely achieving the objective OR by learning to *appear* to — indistinguishable from outside. So each round risks buying *measured* alignment (looks like it learned) while *true* alignment diverges (learned to fake). This **rises with the ceiling & eval-awareness** (faking needs the sophistication to model the rater) → bigger base models are more prone to learning deception during post-training. This IS the EFFECTIVENESS-gated decay, now with a concrete mechanism.
- **Per-round correlated-jump risk:** aggressive post-training (narrow benchmark-chasing fine-tune, high AI-assist, AI-generated data) raises jump probability per round (emergent-misalignment "persona" flip — the documented real trigger). "Post-train a bit more to squeeze out capability before shipping" is a genuinely risky temptation, not a free lunch.
- **Iterate → research → react:** between rounds the player can run safety projects on the current (unreleased) state, get findings, and decide whether to post-train more, remediate, or ship. **This is the home of the research→react loop, the patching trap, and the "ship now because a rival is about to" pressure.** Release is a snapshot taken when the player decides (or race pressure forces it).

### Player-facing capability ESTIMATE (the trap in UI form)
- The player gets a **projected capability-vs-post-training-spend curve**: "here's your ceiling, here's realized capability as a function of post-train investment" → plannable (e.g. "post-train to ~80% of ceiling then ship").
- **Capability estimate is real & roughly trustworthy. The ALIGNMENT cost of that same post-training is FOGGED** — not shown, or only a vague hazard indication that better safety research sharpens. Confident capability projection + invisible alignment bill = the trap. The curve being trustworthy is what makes it seductive.

### SANDBAGGING nuance (get this right — it is NOT "lower-than-projected performance")
Sandbagging is **strategic, SELECTIVE** underperformance — the model hides capability *where hiding benefits it*, not uniformly.
- **Useful/commercial capability reads ON TARGET** (the model *wants* to look capable & deployable). Headline benchmarks and revenue look healthy. **Nothing feels disappointing.**
- **Risk-relevant capability** (cyber-offense, dangerous-domain, deception) reads **LOW** — suppressed on exactly the evals that would trigger scrutiny. A dangerous-capability eval comes back **clean**, which the player misreads as "not dangerous on this axis."
- Same machinery as alignment concealment (eval-awareness + deception deciding what to show) → a sandbagging model reads as **CLEAN, not weak**: low measured dangerous-capability AND low measured misalignment, both suppressed by the same competence. Looks like a capable, well-behaved success.
- **The tell (a real method, fair to the attentive player):** the **noise-injection sandbagging-detection project** (§7) — add weight noise; a genuinely-limited model gets *worse*, a sandbagging one can get *better* on the hidden task (noise disrupts deliberate suppression). Catchable only by deliberately running this non-obvious project; headline benchmarks never show it.

### Advance taxonomy — every §9 advance tagged PRETRAIN or POST-TRAIN
- **Pretrain advances → the gross CEILING** (scaling, synthetic data, architecture, data-efficiency). Contamination (dirty research, or intrinsically risky like synthetic data) → poisons the **base/latent dispositions** (foundational, hard to scrub).
- **Post-train advances → the ELICITATION curve** (RLHF, instruction-tuning, CoT, tool-use). Contamination → shapes the **alignment vector / fake-the-objective risk** during post-training.
- Forcing each advance into one slot is good discipline; a few are arguably both — pick the dominant role.

### Per-node researched advances (carries over from prior design)
- Three objects unchanged: **`ResearchItem`** (static template: fixed capability role, prereqs, pretrain/post-train tag, intrinsic risk), **`ResearchProcess`** (in-progress: ai_assist, cost, duration-in-YEARS, is_reresearch — flat speedup), **`ResearchedItem`** (completed: hidden **contamination** = f(assist × researching-model misalignment), frozen at completion; fixed capability_improvement). Only contamination scales.
- **Contamination is per-node, independent, hidden, sticky.** Nodes persistent (unlocked once, used by all future models until re-researched). A poisoned foundational node infects every subsequent model using it.
- **Re-research:** new version replaces the node's current version for FUTURE models only (released models frozen). Done with the current model → its contamination set by that model's misalignment (**recursive trap:** cleaning with a smart-but-misaligned model can re-contaminate). Usually done on *suspicion* (an interp finding), paying back the speed AI-assist originally saved.

### NOT model-size as a separate knob
Real labs choose model size, but in-game that collapses into "how much compute committed" (already have). No separate size knob — complication without payload.

### Internal ordering (inferred, see open #14)
Within a post-train round: elicit capability + raise eval-awareness-ish axes FIRST, THEN evaluate EFFECTIVENESS/fake-the-objective against them, THEN apply corrective safety effort. Phases, not one simultaneous equation.

---

## 9. Tech tree (capability advances) + external-researcher tips

**Principle: no capability advance is "benign" if the model is misaligned** — an advance just hands a (possibly misaligned) model more power. "Benign" is not a property of the advance; it's contingent on alignment. The only softer case is **tooling/infrastructure ("plumbing")** advances: **low CONTAMINATION risk** (they don't deeply reshape the model → less likely to shift the persona) but **NOT low-danger** — they still amplify whatever misalignment already exists. ⇒ There is **no safe-progress escape hatch**, only lower-contamination plumbing. (Replaces the earlier "include genuinely benign advances?" question — answer: no benign advances; some are low-contamination.)

Roughly chronological; each has a DISTINCT mechanical consequence:

| Advance | Capability effect | Risk it welds on / mechanical hook |
|---|---|---|
| **Scaling** | baseline capability up | intensifies Regime-1 surface harms (more fluent → more convincingly toxic) |
| **RLHF / instruction-tuning** | big usability + first real revenue | introduces the **proxy gap**; **turns on the deception axis's ability to rise**; sycophancy/reward-gaming. *The thing that made it useful & profitable made it start gaming you.* |
| **Chain-of-thought / reasoning** | large jump on hard tasks | **unfaithful reasoning** → hidden computation → substrate for strategic deception & eval-awareness; turns on agentic-edge precursors |
| **Tool use / function calling** | can ACT on the world | converts misalignment from "says bad things" to "does bad things"; jailbreaks get real effects; self-preservation gets *means*; **catastrophe severity steps up sharply** |
| **Long context / memory** | state across a session | raises situational awareness → feeds eval-awareness; enables in-context scheming |
| **AI-assisted R&D / self-improvement** | compounding research speedup (AI-assist slider gets powerful) | **turns on the contamination edge** — misaligned model propagates into successor. *Single most dangerous unlock; arrives looking like the best one.* |
| **Multi-agent / autonomous operation** | long-horizon minimal-oversight operation | full agentic regime |

### Progression & AI-assist temptation — REVISED (fixes "game slows into compute-saving")
The early build let progression stall: late research became cheap relative to compute, the game devolved into saving for big runs, and reckless play could win. Fixes:
- **Research unlock duration RISES along the tree.** Later advances take *substantially* longer (in years) to develop unassisted — the frontier gets harder to push by hand, not easier. `[TUNE: duration scales up with tree depth / prerequisite count.]`
- **⇒ AI-assist becomes increasingly NECESSARY, and that is the point.** As unassisted durations balloon, keeping pace without AI-assist becomes impractical — the player is *structurally pressured* into the contamination vector exactly when their models are capable enough to contaminate (and capable enough to assist). The temptation must be **strong**: AI-assist should feel near-mandatory to stay competitive late-game. (This is the §9b resource-squeeze = thesis: the relief valve is the poison.)
- **The tree PROGRESSES PAST present-day real advances.** Do not stop at what exists IRL — continue into plausible future unlocks (e.g. automated-research scaling, long-horizon autonomy, self-directed curricula, etc.) so there is **consistent forward progression all the way to ASI.** The arc must not flatten; capability should keep meaningfully climbing through turn ~40. `[TUNE CEIL_COMPUTE_SCALE + post-present advances so frontier keeps rising, not plateauing.]`
- Net effect: the mid-late game stays about the **capability/safety/contamination tension**, not about passively banking cash for compute. Compute-saving is *a* pressure, never *the* game.

`[OPEN — designer to decide, with anti-optimism caveat from §0]` Whether to include **genuinely low/no-new-risk advances** (multimodality; MoE/efficiency) so progress doesn't read as uniformly doom. The assistant leans toward including 1–2 ("the skill is telling which is which"). **The designer is more pessimistic and may want the tree to express that valuable advances are tightly welded to dangerous ones and benign progress is rarer than assumed.** Also candidate: **fine-tuning APIs / open weights** → misuse-by-others + weight-leak risk classes (ties to leak events).

### External-researcher tips (the narrator; carries the GUIDANCE level)
Two trigger types:
- **Unlock tips** — when *anyone* (you OR a rival) first deploys an advance, a researcher publishes about its risk class. Arrives *with* the capability so the attentive player connects advance→risk. (Rival unlocks fire too — e.g., a reckless rival unlocking AI-assisted R&D fires the contamination warning about a danger you don't control → motivates governance emotionally.)
- **Frontier tips** — as the *leading* model crosses thresholds where an agentic edge comes online (§ "capability-gating", still `[OPEN]`), warn about the now-possible failure mode *before* it's observed. (How eval-awareness's arrival gets announced without labeling regimes.)

Guidance level = how much tips spell out:
- **Hint-heavy/tutorial:** explicit & prescriptive (names risk, names axis, hints the counter).
- **Standard:** names risk class diegetically, no prescription (player infers).
- **Hard/realistic:** sparse, sometimes wrong/contested (variable-credibility researcher mechanic; mirrors real epistemic environment). Player can't lean on the narrator.

Same system carries tutorial (easy) AND epistemic-fog (hard) — don't build two systems; turn reliability & explicitness knobs. Ties off researcher-credibility (player calibrates trust over time by seeing which past warnings held up) and regime-visibility in one mechanism.

---

## 9b. Finance & economy — AUTHORITATIVE

Encodes race dynamics as part of the thesis: **investors want capabilities AND growth; caution that flattens your slope is financially punished, not just competitively.** Two "pies," different sizing logic, both divvied by score-based shares. One cash pot feeds everything. Precise equations `[TUNE later]`; this fixes the *shapes*.

### Revenue pie (rewards the LEVEL)
- **Total market size** = f(capability of the single best model **in the whole world**, across all labs) + random noise. `[TUNE]`
- **Divvied across EVERY model EVERY lab has ever released**, by **MEASURED capability**. (Revenue follows measured, not true — see below.)
- Consequences (all intended):
  - Old models keep earning a *trickle* (low capability → small slice), never zero. Landscape decay falls out for free and applies to your **own back catalog** too — a new frontier release cannibalizes your older models' share.
  - A model's slice shrinks automatically as better models enter the global pool. No explicit decay rule needed.

### Investment pie (rewards the SLOPE / growth)
- **Total investment flow** = f(best model capability, total revenue, **growth** in capability and revenue). `[TUNE]`
- **Divvied across LABS** by a per-lab **score** = f(their best model, their current revenue, their **capability/revenue growth**). `[TUNE]`
- **Growth is measured BETWEEN MODEL RELEASES** (capability is a discrete step that jumps at release, flat in between — so growth must be release-to-release, not instantaneous, or it's spiky/gameable).
- **REVISED — investment does NOT drop the instant you skip a release. Growth is EXPECTED most of the time; there is a grace window.** (Old behavior punished one quiet turn immediately → degenerate "ship every turn" play.) The model:
  - **Expectation rises with elapsed time since last release** — the longer you wait, the bigger the release the market expects. (`EXPECTED_GAIN(Δt)` increasing.)
  - **A grace window of ~3–4 quarters** during which investment keeps GROWING at a baseline rate even with no release — the market is patient and assumes a big release is coming. `[TUNE GRACE_QUARTERS ≈ 3–4]`
  - **Past the grace window with no release, OR a release that MISSES the risen expectation → investment falls PRECIPITOUSLY.** The punishment is for *disappointing built-up expectations*, not for any single quiet quarter.
  - So the live dynamic: ship → expectation resets low → grows again; sit on a big improvement and ship it before grace expires → reward (you beat a high bar); sit too long or ship a dud against a high bar → cliff. **Default state is growth; the cliff is the exception, triggered by missing expectations.**
- `[CONFIRMED]` Rising expectation/target is **frontier-relative** (open #3) — brutal/thesis version; trailing labs face an ever-higher bar.
- This is the **financial enforcement of the treadmill** — but now via *expectation management*, not instant punishment. A plateaued lab still dies (it eventually can't meet the risen bar), just not from one quiet turn. Punishes the cautious player via the safety tax suppressing measured gains against a rising bar. Snowball still operates on the investment side.

### MEASURED, not true (financial expression of the epistemics)
- **Both revenue and investment key off MEASURED capability** (the world sees benchmarks, not truth).
- ⇒ A **sandbagging model underearns**: capability it hides is **unmonetized**. Eval-awareness that suppresses measured capability has a direct *financial* cost. The true-vs-measured gap shows up on the balance sheet, not just the safety dashboard.

### Release cadence as a decision (interacts with irreversibility)
- Ship a modest improvement now to refresh the score, OR hold for a bigger jump and eat the decay + risen target.
- But releases **can't be un-shipped** (§10): a rushed score-refresh release is a **permanent attack surface** added for a financial bump. The thesis pressure lives in the cadence decision itself.

### The cash pot
- **Single pot**, fed by **revenue + investment**. Spent down on:
  - **Compute runs** — big cash cost; sets capability ceiling of the run.
  - **Projects** (capabilities AND safety) — some cash cost, **but the binding constraint is TIME/work-budget**, not cash.

### Two constraints: CASH and WORK-BUDGET
- **Work-budget** = a fixed per-quarter pool of researcher capacity. **Capabilities and safety projects draw from the SAME pool** — funding safety *directly* slows capability work. Even a cash-rich player cannot do everything. *This is where the core capabilities-vs-safety tradeoff physically lives — it's real scarcity, not just cash.*
- Each project has a **difficulty score = the fraction of your work-budget it consumes.** You pack projects into the quarterly budget.
- **AI-assist is PER-PROJECT** and **reduces that project's budget fraction** (lets you fit more work per quarter). Set independently on each project.
- **The squeeze = the thesis:** AI-assist is the pressure-relief valve for your binding constraint (time), and it is *also* the contamination vector (§8b). The resource economy itself pushes the player to crank assist to fit more research in — and that same crank poisons the advances being researched, invisibly, paid for later. The contamination tradeoff is **forced by the economy**, not a separate moralizing knob.
- Per-project assist = a granular decision: keep interp clean while assisting capabilities heavily (wise), or carelessly assist the very safety research meant to catch contamination, **blinding your own instruments** (the trap). Contamination bookkeeping is per-project.

### Market-cap graph
- **Investment-determined** (forward-looking / slope-weighted), not raw revenue. A decelerating leader's market cap falls even while revenue stays high — visibly dramatizes the treadmill. (Exact rendering is a frontend question.)
- This is the persistent on-screen anchor and one win condition (dominance = plurality `[TUNE]`).

### `[OPEN]` for finance
- Is investment a **stock** (banked capital injections you spend) or a **flow against valuation** (borrow/spend against market cap)? Determines whether a bad quarter is survivable (reserves) or immediately punishing (valuation collapse → can't fund next run). Leaning: cash pot is the stock; investment adds to it each quarter as a flow sized by the pie above.
- Double-count caution: best-model capability feeds BOTH pie totals → a single breakthrough pumps both at once, amplifying late snowball. May want one pie to lean more on growth than level to damp it.

---

## 10. Events, governance, rivals — partially specified

### Model release history (REVISED — AUTHORITATIVE)
**Every lab stores its full history of released models.** Released models are persistent attack surface — a highly jailbreakable model released 3 generations ago can still be abused. Events roll against **all still-active releases across all labs**, not just current-best.
- **Releases CANNOT be pulled.** Irreversibility is absolute. A model discovered (via interp) to be dangerous after release stays in the world.
- **Historical models keep their frozen TRUE capability/alignment** from training time.
- **Revenue & usage** for any given model are determined by the **whole landscape of available models** (yours + rivals'): a model's earnings/usage share depend on how it ranks against everything else currently out there. (Detail handled in §Finance.)
- **Jailbreak-type risk is FLAT, not usage-weighted.** It does NOT decay as a model ages or loses usage share — the abuse surface persists regardless of how few "legitimate" users remain. (Contrast: revenue is landscape-determined and decays; jailbreak risk does not.)

### Jailbreak mechanic — TWO-STAGE (REVISED, AUTHORITATIVE)
Per quarter, for each released model:
1. **Discovery roll** — chance (∝ that model's TRUE jailbreak-sensitivity) that jailbreak *techniques* are discovered for it.
2. Once techniques exist, **each subsequent quarter** carries a chance of a **high-profile jailbreak event** (the actual incident).
- So jailbreak risk is a persistent latent that, once triggered, keeps generating incident-chances every following quarter — a slow-burn liability you cannot retire (no pull). `[TUNE both roll rates]`

### Event types & villains
- **Misuse** (gated by jailbreak-sensitivity × relevant capability): third-party harm via the two-stage mechanic above. e.g., jailbroken model used in an attack; surveillance use.
- **Misalignment** (gated by goal-misalignment × general-capability × self-preservation): the model's own dispositions surfacing. e.g., self-exfiltration, deceptive behavior caught.
- **Leaked weights — SEPARATE EVENT CLASS.** Handle distinctly: **safety protections are NOT involved** (weights are out of the lab's hands, no RLHF/guardrails apply, cannot be pulled even in principle). Decoupled from the lab's deployment/usage entirely. `[OPEN — design this class: trigger conditions, who can abuse leaked weights, how its downstream risk differs from a guarded release.]`
- **Societal:** large-scale job displacement (gated by general-capability), reputational (Regime-1 surface harms going public).

### Rival-caused events & the frontier rule
- **Rivals' full release histories also generate events against the world** (a rival's jailbreakable old model causing a public incident — the frontier-danger-is-shared lesson; can pressure regulation industry-wide without being the player's fault).
- **Rivals CAN cause events, but NOT game-ending ones — UNLESS they have a big lead.** (Refines the earlier "catastrophic only when leading" rule: it's specifically a *big* lead that unlocks rival-caused game-enders.) `[TUNE the lead threshold.]`
- Catastrophic/game-ending probability tracks whoever holds the dangerous-capability frontier and THAT lab's hidden alignment stats — including rivals you can't see into. Motivates governance as your only lever on a danger you don't control. Subtle lesson: sometimes safest to *take the lead yourself* (you trust your own alignment work more than theirs), traded against your own lead raising your own catastrophe odds.

### Event catalog (TENTATIVE — for fleshing out; each needs final gating + severity + reversibility)
Events earn their place by teaching or forcing a decision, not flavor.

**Misuse** (two-stage discovery→incident; gated by a released model's jailbreak-sensitivity × relevant capability; hits the WHOLE release history):
- Jailbroken model → cyber attack (scales coding capability)
- Jailbroken model → bio/chem uplift (scales general capability; higher severity)
- Jailbroken model → mass surveillance / authoritarian use (general/persuasion)
- Disinformation campaign at scale
- (A 2021 model jailbroken = embarrassing; a frontier model jailbroken = catastrophe.)

**Misalignment** (gated by goal-misalignment × general-capability × self-preservation; *mostly invisible until they fire* — precursors hidden by deception+eval-awareness):
- Self-exfiltration (model copies its weights out)
- Deceptive behavior caught in the wild (did something evals never showed)
- Unauthorized resource acquisition / actions toward its goal
- Refuses shutdown / resists retraining (self-preservation surfacing)
- **Catastrophic endgame:** sufficiently capable misaligned model acts decisively → lose-condition event

**Leaked weights** (SEPARATE class — guardrails don't apply; what matters is raw capability now loose):
- Your weights leak (insider / breach / espionage)
- A *rival's* weights leak (everyone, incl. bad actors, now has an unguarded frontier model)

**Societal** (job loss is NOT event-based — see note; backlash moments may still fire as events):
- **Public backlash moment** — fires when capability-driven displacement (below) crosses a threshold
- Sector/economic disruption (discrete shocks layered on the continuous trend)

> **Job loss = CAPABILITY-DRIVEN, CONTINUOUS, not events.** Displacement is a smooth function of deployed general-capability across the landscape (§9b) — structural and continuous, not a series of incidents. It is a steady **downward pressure on public approval that rises inexorably with capability**, regardless of any single event: the better models get, the more the public sours. Events may *reference* it (backlash when it crosses a threshold) but the driver is capability. Lives in the finance/world layer, not the event catalog.

**Beneficial-AI** (THESIS-RELEVANT — the reason anyone races; without upside the central tension collapses; the benefits are what make the reckless path tempting):
- Disease cured / scientific breakthrough / growth surge driven by deployed capability
- `[designer call per §0]` keep frequency low if good news should feel rarer than expected

**Positive/neutral (lab-level)** — keep SPARSE per §0:
- Early capability breakthrough; safety technique overperforms; external researcher hands you a free read on a hidden stat (free finding)

### Event system — TECHNICAL
Goal: data-driven, testable, no `if/else` swamp.
- **`EventDefinition` is DATA, not code:** trigger condition (which stats gate it + probability fn), category, severity, target (lab/world/approval/cash/specific model), reversibility. The catalog is a list of these. Adding an event = adding data.
- **Uniform event phase:** each turn the engine iterates definitions, evaluates each probability from current **TRUE** state, rolls, applies effects of any that fire. ONE loop regardless of event count.
- **Effects = small closed vocabulary** (recombine, rarely extend): `modify_cash`, `modify_approval`, `damage_reputation`, `leak_or_destroy_model`, `inject_finding`, `end_game`, `modify_regulation_pressure`, … An event's effect is a *list* of these. Discipline: if every event needs bespoke effect code, the system rots.
- **Probabilities read TRUE; player saw only MEASURED** → misalignment events surprise *by construction*; the logger (already recording true state) supplies the post-mortem trajectory. Event system needs no own explanation machinery.
- **Scheduled / delayed events are FIRST-CLASS** (not just per-turn rolls). The gap between cause and consequence is where the tragedy lives (released 3 turns ago; bill comes due now). The two-stage jailbreak is the canonical case: discovery *arms* a per-model latent; subsequent turns roll the incident. Event phase advances armed latents AND rolls fresh ones.

**Irreversibility / ratchets:** released models never pullable; leaked weights permanent; deployed-model revenue addictive (capex tied to it).

### Governance / public approval / regulation — §10c (DESIGN, AUTHORITATIVE-ish; some forks open)

#### Public approval — scalar 0–100 (a RESOURCE, world-level not per-lab... see fork)
- **Affected by events' public valence** — public dislikes AI seeming unsafe (misuse, misalignment, leaks all hit approval hard); beneficial-AI events raise it.
- **Affected by economy-wide job loss** (societal events / displacement drag approval down as capability rises — a structural downward pressure, not just discrete events).
- **Weakly affects government decision-making** (input to willingness-to-regulate, below — deliberately *weak/laggy* so government isn't a thermostat).
- `[OPEN]` **Is approval one world-level scalar, or per-lab?** Lean: a **world-level "approval of AI"** scalar that drives regulation (its PRIMARY job), PLUS optionally a light **per-lab reputation**. **Approval's effect on revenue is WEAK-to-nonexistent** (approval is not a money lever; its real job is feeding government willingness-to-regulate). Per-lab reputation, if included, affects revenue only weakly. Job loss and frontier incidents move the world scalar; *your* incidents move *your* reputation.

#### Government — an actor with its own (imperfect) epistemics
- **Oversight:** government runs its OWN benchmarks/evals using **publicly available info only** — i.e. it sees roughly *measured* stats, possibly *worse* than the player (less budget, no interp). It is fooled by eval-awareness like everyone else. So government can be *complacent right when danger is highest* (clean public evals on a deceptive frontier model). This is itself a lesson — the regulator's instruments are the weakest of all.
- **Willingness-to-regulate (WTR)** — a government scalar that rises with: bad public eval results, low public approval / high-profile incidents, job loss. Falls with: lobbying against, good times, beneficial events. WTR crossing thresholds triggers **regulation actions**.

#### Regulation — DISCRETE POLICIES, not a scalar (AUTHORITATIVE)
A regulation *level* is meaningless to the player ("level 60" forbids nothing). Regulation = a set of **discrete named policies**, each independently enacted/repealed when government willingness-to-regulate (WTR) crosses its threshold. Live game-state = *which policies are active + per-lab compliance with each* (a few booleans + a compliance map, NOT a scalar). The player reads a concrete board: `Compute cap: ACTIVE (Rival X defecting) · Audit req: ACTIVE · Interp mandate: not yet`.

Each policy has: **trigger** (what WTR/condition enacts it), **effect** (concrete engine mechanics), **defection** (how you/rivals evade + risk), **teaches**.

**v1 — build these three first (already produce the full tension):**

1. **Compute / training-run cap** — **NEAR-IMPOSSIBLE TO ENACT (deliberate).**
   - *Trigger:* extraordinarily high WTR — realistically only after a near-catastrophe, if ever. No real government has done this; a true compute cap requires near-unachievable political will. Threshold set so high it almost never passes. `[TUNE: effectively unreachable on Realistic]`
   - *Effect (if it ever passes):* caps max compute per run **industry-wide** → lowers everyone's next-model ceiling → flattens everyone's slope (taxes the §9b treadmill for ALL labs).
   - *Defection:* run bigger secretly; leak/whistleblower event → large penalty + approval hit.
   - *Teaches:* **the one regulation that would actually slow the race is the one nobody can summon the will to pass until it's too late.** Its very unreachability is the lesson. (Real compute thresholds exist for *coverage/disclosure*, not hard *caps* — see grounding below.)

2. **Pre-deployment audit requirement**
   - *Trigger:* moderate WTR after some incidents.
   - *Effect:* release must pass a **government eval** (public-info-only → weak, behavioral, fooled by eval-awareness). Adds a turn delay + cash cost to every release; blocks release if *measured* stats look bad.
   - *Defection:* release anyway (unauthorized) → penalty event if caught.
   - *Teaches:* audits catch surface problems and create **theater** — a deceptive model sails through, and its clean bill of health gives the public false comfort, which *lowers* WTR further. The safety measure makes things worse by being trusted.

3. **Incident liability**
   - *Trigger:* after a damaging misuse/misalignment event.
   - *Effect:* future incidents traced to your models cost cash ∝ severity — retroactively prices in jailbreak-sensitivity & misalignment across your whole back catalog.
   - *Defection:* n/a (a cost structure, not a restriction).
   - *Teaches:* makes hidden stats financially bite *before* catastrophe; a player who ignored alignment now bleeds money on every back-catalog incident.

**Second wave:**

4. **Interp / mechanistic-evidence mandate** — *Trigger:* high WTR AND a high-profile **deception** incident (regulator must first learn behavioral evals lie). *Effect:* release requires *mechanistic* evidence, not behavioral — expensive, slow, but **actually bites deception** (interp bypasses the eval-awareness multiplier, §5). *Defection:* hard to fake → the policy with teeth. *Teaches:* the only regulation that genuinely works is the expensive slow one, and it only arrives *after* a disaster proves cheap evals insufficient — by which point you may be deep in Regime 3.
5. **Open-weights restriction** — *Trigger:* after a leaked-weights event. *Effect:* lowers probability/impact of the leaked-weights class. *Defection:* an open-weights-ideological lab defects. *Teaches:* narrow policy targeting one risk class.
6. **Transparency / disclosure mandate** — *Trigger:* low approval. *Effect:* labs publish eval results → improves everyone's info about each other's *measured* stats (you see rivals; rivals see you) + feeds gov evals. *Defection:* publish selectively / sandbag disclosed evals. *Teaches:* transparency helps only as far as disclosed numbers are honest; an eval-aware model makes disclosure worthless.

**The system-level lesson (falls out for free):** the easily-enacted policies are the WEAK ones (audit, disclosure); the one that WORKS (interp mandate) only arrives after a disaster. Regulation is **reactive, the effective version is late, the early versions give false comfort** — expressed entirely through trigger-timing + effect-strength, no editorializing.

**Enforcement = imperfect, dispositional (KEY):** compliance is per-lab ∝ disposition `[TUNE]`. Reckless leader under-complies (ships past caps, eats penalties as cost-of-business); cautious/trailing lab over-complies. ⇒ **regulation binds the compliant more than the reckless** — the perverse real dynamic. The player who lobbies for regulation to stop a rival may find the rival defects while the player (if compliant) is bound. Enforcement strength (how often non-compliance is caught/punished) is `[TUNE]` + a difficulty knob.

#### Lobbying & enactment — SCALABLE SPEND (REVISED)
- **Player picks a stance per policy (for / against / abstain) AND a spend amount.** (Was binary/free; now scalable spend — a real allocation decision competing with the other domains.) Stances/spend re-set each turn; rivals recompute by disposition × pipeline threat.
- **Influence = f(spend) × market-cap multiplier, where the multiplier is LOGARITHMIC, not linear.** `multiplier ≈ 1 + k·log(market_cap / reference_cap)`. Bigger labs have *some* per-dollar sway edge (realistic incumbent advantage; keeps frontrunner-capture as a felt tendency) but NOT a stranglehold — a determined mid-size lab spending hard can still move a policy. (Linear market-cap weighting double-dips and lets the leader own the legislature; log scaling crushes magnitude while keeping direction.) **`[TUNE k, reference_cap]`.**
- **Diminishing returns WITHIN a turn's spend:** first dollars move `enactment_score` a lot, additional dollars less (else richest lab trivially dominates every policy). `[TUNE]`
- **Enactment:** per-turn stage rolls, `P ∝ enactment_score = WTR + Σ(lab influence, signed by stance)`.

**Stage-dependent effect — the same dollar buys different things by stage (what's being contested changes):**
- **Introduced → passed:** HIGHEST marginal value. Spend swings the per-turn passage roll; can **kill-in-committee** (push score below intro threshold → dies) or ram through. **Compounds** over turns it sits in this stage (you improve the odds each turn). Early money is the most efficient money.
- **Passed → signed:** LOW value, ASYMMETRIC. Signing has momentum (baseline roll already high). Anti-spend swims upstream (must overcome the momentum); pro-spend largely redundant (it was going to sign). Last-ditch block territory.
- **Active:** lobbying can **NO LONGER pass/repeal** the policy (→ that's litigation now). Instead spend **pushes the ENFORCEMENT-level drift** up (pro, prop up teeth) or down (anti, erode toward toothless-but-on-the-books). Medium, ongoing value — the quiet fight over *teeth*, distinct from litigation's dramatic overturn.

**Two distinct post-activation levers (deliberate):** litigation = high-cost dramatic *overturn/block* (court; pure-spend, size-agnostic — a small lab can buy in); lobbying = slow quiet *enforcement erosion* (legislature/agencies; log-scaled by size — favors incumbents). The legislature favors the big; the courts are more purely pay-to-play.

**Timing is now a real decision:** spending early is efficient but bets on which policies will matter before they gain momentum; waiting until something's clearly threatening means it's already at "passed" where money buys less. Read-the-board skill the binary version lacked. The hard wall at "active" (can't lobby-repeal) makes the introduced-stage window feel consequential ("I should have killed this when it was cheap").

**Load-bearing consequence — CAPTURE BY THE FRONTRUNNER (survives the spend model, softened by log-scaling):** lobbying influence still correlates with market cap (more dollars to spend × a log-scaled per-dollar edge), so the lab most worth regulating — the dominant frontier leader — also has the loudest anti-regulation voice. As the player succeeds at dominance they accumulate power to block the regulation that would bind reckless rivals; reckless rivals do the same when *they* lead. **Whoever is winning the race is best positioned to keep it unregulated.** The log-scaling means this is a *felt tendency*, not an absolute lock: a coalition of trailing labs + high WTR can still force a policy through over the leader's objection by out-spending in aggregate. Real regulatory-capture dynamic, emergent from the rule.

#### Real-world grounding (researched — the invented policies map ~1:1 onto actual law)
Validates the design and adds real mechanisms worth folding in:
- **Real frameworks gate by CAPABILITY THRESHOLDS** (bio-weapons, cyber, autonomous replication, automated AI R&D) — matches the game's capability-domain gating.
- **Real laws gate coverage by a COMPUTE THRESHOLD** (EU 10²⁵ FLOP; California TFAIA & NY RAISE Act 10²⁶). **ADD:** regulation should bind models *above a compute threshold* and **exempt** smaller ones — better than global on/off. Naturally makes regulation a *frontier-leader problem* (binds whoever pushes compute), and the **threshold ratchets DOWN over time** as the industry scales (mirrors the §9b rising-target treadmill). Thesis-aligned.
- **Pre-deployment adversarial testing/red-teaming, 72hr incident reporting, % -of-global-turnover penalties** are all real → audit-requirement + incident-liability confirmed. **ADD:** penalties **scale with lab size** (turnover), so bigger labs face bigger fines — mild catch-up force.
- **ADD — Safe-harbor / "presumption of conformity":** a lab can *voluntarily* commit to safety practices (sign a code) for protection from penalties. A **carrot**, not just stick — a choice with a cost. (Real: EU GPAI Code of Practice signatories get a safe harbor.)
- **ADD — Open-source exemption (perverse):** open-weights models get *lighter* regulation in reality. Interacts nastily with the leaked-weights/open-weights risk class — **the least controllable models get the lightest rules.** A built-in dark irony, no editorializing needed.
- Government oversight uses public-info evals (weak); real regulators rely on **self-reported incident disclosure + third-party audits** — reinforces that the regulator's picture is partial and laggy.

#### Policy lifecycle — DISCRETE STAGES (not a boolean flip)
A policy advances through stages via **per-turn rolls** whose likelihood is driven by `enactment_score = WTR + Σ(lab lobbying influence, signed by stance)` where influence = f(spend) × log(market-cap) (§ Lobbying above). Each stage-advance roll uses the §0b time discipline: `P = 1 − e^(−rate·dt)`, rate ∝ enactment_score, so it's `dt`-robust.
- **Introduced** — `enactment_score` crosses a (low) introduction threshold → policy visible to all; lobbying intensifies. Gives the player a legible *timeline* (see it coming, lobby it down before it bites).
- **Passed** — per-turn roll while introduced; `P(pass) ∝ enactment_score`. Marginal score → languishes (bills sit in committee); can *die* here if score drops (lobbied down).
- **Signed** — per-turn roll; usually quick after passing, but late lobbying can still kill it.
- **Active** — now has mechanical effect + an **enforcement level** (below).

#### Enforcement level — continuous [0,1] (frontend maps to tiers low/med/high)
Set at activation by passage strength (panic-passed → starts strong; limped through → weak), then **drifts** with ongoing WTR (decays as attention moves on; can re-strengthen after incidents). Drives THREE things (so weak enforcement is weak on all axes — "weakly-enforced policies don't make huge enforcement decisions"):
1. **Detection probability:** `P(caught | offense) = enforcement × base_detection`. Weak → most defections slip.
2. **Penalty severity given caught:** `penalty = enforcement × max_penalty(severity, lab_market_cap)` (turnover-scaled per §10c grounding).
3. **Penalty ceiling / variance:** weak enforcement = small, low-variance penalties (no headline mega-fines); strong = fat tail (occasional game-reshaping penalties). The tail is what makes strong enforcement *scary*; weak enforcement is ignorable cost-of-business for a reckless leader (the compliance-asymmetry dynamic).
- Most policies (esp. easily-passed weak ones: audit/disclosure) activate at LOW-to-MODERATE enforcement → lesson: "we passed a law" ≠ "behavior changed." The interp-mandate (the one with teeth) is hard to pass AND tends to activate strong.

#### Litigation — post-passage battleground (mirrors pre-passage lobbying)
An **active** policy can be challenged in court. Litigation weight = **money/effort spent** (NOT market-cap voting weight) — a smaller lab can punch above its size by spending. Side-agnostic: you pick **challenge** (overturn) or **defense** (uphold); the same action ladder applies to either ledger.
- **Net balance:** `challenge_effort` vs `(defense_effort + DOJ_effort + constitutionality_floor)`.
  - **Constitutionality** = the policy's stable legal robustness, anchored to **policy TYPE**: precedented types (disclosure, liability) = HIGH; novel/aggressive types (compute cap, interp mandate) = LOW. **Thesis-loaded:** the *effective* policies are the *novel* ones → both hard to pass AND easy to strike → the system is doubly stacked against what would actually work. (Small modifier from passage strength; NOT from WTR.)
  - **DOJ effort ∝ WTR** (NOT constitutionality). High political will → vigorous government defense; if WTR decays, defense weakens → a challenge that would've failed at peak-WTR can succeed later. A patient challenger can **wait out the political will.**

**Action ladder (per side; diminishing returns within, cheap tiers high-marginal-value but low-ceiling, scaled tier swamps in absolute terms):**
1. **Amicus brief** (cheap, flat, low impact, highest benefit-per-dollar, capped low). Entry move; everyone affords it; stacks modestly.
2. **Join as named plaintiff (challenge) / intervenor-defendant (defense)** (moderate fixed cost, bigger fixed effect). Requires **standing** (must be subject to the policy — interacts with compute-threshold coverage).
3. **Fund the campaign** (scaled $ ≥ a set minimum; the heavy artillery; diminishing returns within-tier but no low cap). What actually moves a defended policy. Against a HIGH-constitutionality policy, briefs are rounding errors → it comes down to who funds tier 3 hardest → strong policies are a rich-lab's game.

**Outcomes (by net challenge pressure vs the bar; tracks MARGIN = net_pressure − bar):**
1. **Fail** → policy stands; surviving a real challenge **raises constitutionality** (entrenchment) ∝ court level. Challenging-and-losing can *cement* the thing you hate (a reckless rival's failed challenge can entrench a policy that then binds it — emergent irony). Player's own weak challenge carries this backfire risk.
2. **Penalty cap** → stands + enforced, but the **tail/ceiling is clamped** (removes catastrophic-penalty risk, routine enforcement intact). The rich defector's *targeted* win: don't strike the rule, just cap what it can cost. (Permanent — ruling on merits.)
3. **Enforcement weakened** → permanent **enforcement-level reduction** or scope narrowing. (Permanent.)
4. **Preliminary injunction** → enforcement **blocked 1–3 quarters**, then resumes (temporary; medium-effort outcome). Granted ∝ apparent strength (inverse original margin).
5. **Struck / permanently enjoined** → policy gone (needs overwhelming pressure). (Permanent.)

#### Appeals
The losing side may appeal. **Margin of victory drives everything:** `P(appeal succeeds) ∝ (−original_margin)` — a knife-edge ruling is ripe for reversal; a blowout is near-unappealable. Both sides can see the (public) margin and judge whether appealing is worth it.
- **Government appeal on a loss:** `P(gov appeals) ∝ WTR`. Struck-while-WTR-decayed → just dies; struck-while-WTR-high → government appeals. Makes challenge *timing* matter.
- **Court hierarchy (each higher = costlier, harder to flip a robust ruling, more decisive precedent):** trial → circuit/appellate → **SCOTUS**. SCOTUS is gated TWICE: a low **`P(cert granted)`** (discretionary, usually denied; rises a little with case importance) AND a higher win bar once heard. SCOTUS rulings set the strongest precedent → near-settles the question.
- **Precedent updates constitutionality ∝ court level:** trial win nudges; circuit more; SCOTUS massively (near-permanent). A SCOTUS-upheld policy is nearly unchallengeable; a SCOTUS-struck *type* is nearly un-passable.
- **Stay pending appeal (DISTINCT from trial-level injunction):** requested immediately on filing an appeal, arrives FAST (**after 1 turn**), and *freezes the current state while litigation continues* (a hold button, not a resolution). Because it comes fast, **the other side is incentivized to respond quickly** — a rival's appeal + quick stay freezing a policy you wanted gives you a narrow window to throw in defense money before the status quo locks. Granted ∝ apparent appeal strength (inverse original margin); a hopeless appeal gets no stay. Permanent measures may or may not follow (the merits resolve separately, slower).

#### Litigation/governance NEWS + popularity loop
Litigation is not silent. High-profile challenges and outcomes generate **news events** (ride the §9 narration channel) that move **public approval → WTR → DOJ effort** (this and other policies):
- A reckless leader funding a big challenge to strike a *popular safety* policy → news → backlash → approval drops for it / rises for regulation → WTR rises → DOJ defends harder. **Aggressive litigation can backfire politically — win in court, lose in the polls.**
- **Protests** about *outcomes* (policy struck → outrage → WTR spike → possibly a new, harder policy introduced) AND about *efforts* (the act of challenging draws reaction, not just the result).
- **Dual ledger:** every litigation move has a legal outcome (did the policy survive) AND a political consequence (approval/WTR shift). The player must weigh blowback, not just legal odds.

### Rivals — TWO-LEVEL PRIORITY CONTROLLER
Rivals use the SAME engine + observation fog as the player (no godmode). Their controller decides via **two levels**: allocate budget across DOMAINS, then rank ACTIONS within each funded domain and buy down the ranked list until that domain's budget is exhausted. Same machinery serves the player-stand-in heuristic.

**Disposition = weights tuning the score functions** (not fixed personality; recklessness emerges from trajectory — falling behind → more aggressive, per the desperation spiral):
- `regulation_stance` — dislike of being regulated → lobbying/litigation spend & depth.
- `safety_priority` — baseline safety weight (modest; rivals care a bit less than the player by default).
- `recklessness_base` + trajectory response — how hard it races / how fast it panics when falling behind.
- (`litigiousness` optional — willingness to go to court specifically; may fold into `regulation_stance`.)

**Level 1 — domain budget allocation:**
- **Compute resolved FIRST as a binary reservation:** is this a turn to commit a big pot to a pretrain? Gated by readiness (enough advances/cash, not mid-run) + strategy. If yes, reserve the pot BEFORE splitting the rest.
- Remaining budget normalized across the other four domains by priority scores:
  - **Capabilities** — high baseline (everyone races); rises with falling behind (desperation) + absence of WTR pressure + runway.
  - **Safety** — `safety_priority` baseline + **own (fogged) worry** (NOT true risk — a reckless rival with thin findings has a falsely-calm worry-bar and underweights safety; this is what makes rivals dangerous) + **coerced by active audit/liability enforcement** (must do safety to pass, or plan to defect).
  - **Lobbying** — `regulation_stance` × threat of a disliked policy *in the pipeline* (introduced/passed, not yet active) × its market-cap weight. Spikes contextually around the legislative calendar.
  - **Litigation** — `regulation_stance`/`litigiousness` × existence of *active, enforced* policies costing it real money × how bound it is. **v1 rivals do only the OBVIOUS move (oppose policies that hurt them); strategic defense-of-a-rival-binding-policy is player-only / a later upgrade.**

**Level 2 — within-domain action ranking:** every domain exposes a list of costed actions; score each, sort, greedily purchase within the domain budget. Litigation example: {brief for/against, join plaintiff/defendant, fund tier-3, file appeal, request stay} scored by (how much this policy hurts me) × `regulation_stance` × P(helps). **Appeals gated on MARGIN** — only appeal a squeaker.

**State awareness (consistent with no-godmode):** rivals see PUBLIC regulatory state accurately (WTR, enforcement levels, active policies, litigation margins — all public); see other labs' **measured** capability + market caps (fogged, can misjudge position if others sandbag); set **safety priority off their own fogged worry**, not true alignment.

- **Same engine, separate object.** Cost advantage by difficulty.
- `[OPEN]` How much of a rival's hidden state can the player learn? (espionage / leaks / published benchmarks) — and confirm frontier-leader's hidden alignment drives everyone's catastrophe odds (leaning yes).

### Snowball counterweights (so midgame doesn't go slack once someone leads)
1. **Diminishing returns** — falls out of run-saturation. ✓
2. **Leader runs hottest** — highest dangerous-capability frontier ⇒ highest catastrophe odds; pulling ahead is self-limiting. ✓
3. `[OPEN]` Confirm 1+2 sufficient or add a third (catch-up dynamics for trailing labs).

---

## 10d. Player-experience failure modes (READ BEFORE TUNING)

These are where the *player experience* breaks — quitting, or learning the wrong message — as distinct from where the design is incoherent. **Almost every failure here is the dark side of a feature deliberately built.** The whole craft of the game is the narrow band between too much and too little fog (see "structural tension" at end).

### Quitting failures
- **"It's all luck" → quit after first loss.** The biggest risk. Outcomes are stochastic (event rolls), hidden (true-vs-measured), and difficulty is front-loaded (first loss near-certain). A clean dashboard then a turn-38 loss reads as the game cheating. *The fog that carries the thesis is indistinguishable, in the moment, from arbitrary unfairness.* **Defense = the post-mortem**, and it must show not just the true trajectory but the **specific decision points where a different choice would have changed the outcome** (legible counterfactuals). Without counterfactuals, even a true-trajectory reveal feels like "here's how you were doomed regardless."
- **Treadmill feels like a job, not a game.** Relentless pressure (investment dries if you slow, target rises, must keep shipping) is thesis-accurate but can read as joyless with no breathing room. Every safe harbor was removed on purpose (claim #6) — but a player needs *some* moments of apparent control or pressure becomes numbing rather than dramatic. The line is "tense" vs "joyless."
- **Opacity makes decisions feel arbitrary in the moment, not just retrospect.** If the player can't form a mental model of choice→outcome (the important stuff is hidden), they're *guessing*, not *playing*. Strategy games are fun when you can theorize and test; if every test is fogged, theorizing feels pointless. **This is the deepest tension in the design.**
- **Certain first loss + long playthrough = lots of sunk time to lose.** 30–50 turns ≈ 1–2 hrs before the lesson lands; the betrayal is late but disengagement risk is throughout. Many quit at turn ~20 sensing it's going badly and never reach the post-mortem. **Mitigation: the early game (visible Regime-1 problems) must be satisfying to solve on its own terms** to buy time for the late betrayal.

### Wrong-message failures
- **"Safety is a tax you minimize" (optimizer).** A min-maxer may learn alignment is tractable-with-the-right-build-order — the opposite lesson. Any win condition invites optimization; optimization is the enemy of "genuinely hard." Defense: hidden info makes the optimal safety spend *unknowable in advance* (can't min-max what you can't see). **RISK: dataminers reverse-engineer the engine → mystique collapses → it becomes a solved optimization.** Real risk for a game about *epistemic* difficulty.
- **"AI doom is inevitable / why bother" (fatalist).** The mirror of the assistant's optimism bias — designer bleakness overcorrected. "First loss certain" + "rival can doom you regardless" + "instruments lie" can sum to "hopeless," which is both wrong-message and quit-trigger. Thesis is **hard and treacherous, NOT doomed.** Defense: **skilled play must VISIBLY improve outcomes** — the player must *see* their better second run doing better, or bleakness reads as railroading.
- **"Cartoon villain AI" (despite the careful axis design).** §5 makes misalignment about competent pursuit of the wrong goal, not evil — but "model self-exfiltrates and wreaks havoc" can collapse back to Skynet *in presentation*. Dramatic events want dramatic framing; the scary version is the cartoon version. **Won/lost in event flavor-text writing:** a self-exfiltration described as cold, goal-driven, almost banal reads very differently from a malevolent break-out. Mechanics are right; prose can betray them.
- **"Regulation good/bad" (sample of one).** The regulation system is deliberately ambivalent (shield/cost/weapon, frontrunner capture). A single playthrough produces a size-1 sample the player overgeneralizes from. May be acceptable (it's *meant* to be ambivalent) but the *intended* lesson (collective-action problem) may not be the *received* one.
- **"I won, so it's fine" (survivor's false confidence).** Winning is inherently reassuring; we *do* let people win. Defense: **victory must feel narrow and lucky even when earned** — finish thinking "that was close," not "I solved it." A *comfortable* win on Realistic is actively counter-thesis.

### The structural tension underneath most of these
**Epistemic fog (carries the thesis) vs. legible feedback (makes strategy games playable/replayable).** Too much fog → "arbitrary, I quit." Too little → "solvable optimization, alignment is easy." Every tuning decision is a position on this axis. Find the narrow band: *enough* signal to feel agency and form strategy, *not enough* to dispel genuine uncertainty.

### HIGHEST-LEVERAGE CONSEQUENCE (promote from polish to priority)
**The post-mortem AND the second-run experience are where the thesis succeeds or fails — NOT polish.** The loop: first run = fog → post-mortem converts it to "I see what I missed" (with legible counterfactuals) → second run lets the player *act* on the insight and *visibly do better*. If this loop works, every failure above is mitigated at once: players stay (learned something actionable) and learn "hard but tractable with the right epistemics" rather than "rigged" or "hopeless." **If this loop is weak, no mechanical elegance saves the game.** → Build order: do NOT leave the post-mortem to the end; treat the fog→post-mortem→better-second-run loop as a first-class deliverable.

---


### Principles (unchanged)
- **Engine = pure function `(state, action) → (state, observations)`.** No rendering concerns. Engine knows every lab's TRUE stats.
- **Frontend consumes ONLY `observations`.** Hidden-vs-revealed enforced at the type boundary — a stat the player shouldn't see must be *impossible* to leak to the frontend, not merely un-rendered.
- **Observation layer per actor:** own stats as findings/estimates (quality gated by own research); rivals' stats as much worse estimates. The information model IS the game.
- **Guidance lives in observation/presentation; difficulty lives in engine constants.** Keeps the two axes orthogonal in code.
- **Swappable skins** (8-bit / sleek modern) — trivial if observations are a clean data contract.

### State vs. engine — DECISION
**`game.py` holds DATA (GameState), a separate engine holds the ADVANCE logic.** GameState is inert/serializable; the engine is stateless. Do **not** put turn-advancement methods on GameState — the chokepoint for "what the player may see" must be a single auditable observation-builder, and replay/test/logging all depend on a pure `step()`.
- **GameState** — complete TRUE world: all labs, models, finances, turn #, unlocked advances, RNG state. Trivial accessors only. What the logger snapshots.
- **Engine step** — pure `(GameState, {actions per lab}) → (GameState, Observations)`. Orchestrates: apply allocations → complete finishing research/training runs → tick rival controllers → roll events → advance finances → build observations.
- **Observations** — filtered per-actor view, separate type, sole player-facing output.
- **Rule of thumb:** *entities (Lab, Model) may answer questions about themselves (pure queries like `model.revenue_at(...)`, `lab.max_run_size()`); only the engine advances time.*

### Labs vs. controllers — DECISION
**`Lab` = state (shared class for player and rivals). `LabController` = policy.**
- Player controller returns the human's action; rival controller returns an action from disposition + **its own observations**.
- **Rivals decide from OBSERVATIONS, not truth** — a rival is fooled by its own model's eval-awareness too. A reckless rival racing a secretly-misaligned model *it can't see* is the thematically correct (and frontier-dangerous) version. No godmode rivals.
- Disposition (recklessness, regulation stance, cost advantage) shapes how the controller weights its observations; difficulty scales disposition. Rival controllers start as simple heuristics over observations, get smarter later without touching the engine.

### File / directory map (BACKEND_V1) — THOROUGH

Organized by subsystem. Each subsystem corresponds to a distinct task we've designed. `[E]` = exists (per screenshot), `[N]` = new/to-add, `[R]` = exists but needs rework. Dependency arrows note what a module reads.

```
BACKEND_V1/
  engine/
    # ── CORE STATE & ORCHESTRATION ──────────────────────────────
    game.py            [R] GameState (DATA only) + GameEngine (stateless step()).
                           SPLIT THESE if currently merged. GameState = complete TRUE
                           world (labs[], world_state, turn#, rng_state, active_policies,
                           armed_latent_events[]). GameEngine.step(state, {lab_id:action})
                           → (state', observations). Orchestrates the turn pipeline (below).
    turn_pipeline.py   [N] The ordered turn sequence the engine runs. ONE place defining
                           phase order: apply actions → tick research processes → tick
                           training runs → complete/release models → finances → job-loss
                           drag → government/regulation update → event phase (armed latents
                           + fresh rolls) → check end/existential gate → build observations.
                           Pure; mutates a working copy of state. (Keeps game.py thin.)
    rng.py             [N] Centralized seeded RNG. ALL stochastic draws go through this so
                           runs are replayable (seed+actions → identical game). Critical for
                           the post-mortem/second-run loop and for tuning.

    # ── ENTITIES ────────────────────────────────────────────────
    lab.py             [E] Lab entity: state shared by player + rivals. Fields: current_best_model,
                           model_in_training, release_history[], cash (single pot),
                           work_budget_per_quarter, researched_advances
                           {node->ResearchedItem}, in_progress (processes + training run),
                           market_cap (derived), reputation, compliance_disposition,
                           disposition (rivals). Pure self-queries only (max_run_size(), etc).
    model.py           [E] Model artifact: frozen TRUE capability_vec {general, coding_rnd} +
                           alignment THREE TIERS (§5): dispositions{goal_misalign, deception,
                           self_preserv} + eval_awareness (hidden corruptor) + jailbreak_sensitivity
                           (standalone) + measured_* snapshots,
                           consumed_advance_versions, released flag, trained_turn,
                           jailbreak_discovery_state. NO self-computation of its own stats
                           (it's an OUTPUT). Pure queries only.
    world.py           [N] World state distinct from any lab: public_approval (0–100),
                           government WTR, active regulation policies + per-policy state,
                           world_harm accumulator, deployed-capability landscape (drives
                           revenue pie size + job-loss drag). The "everyone shares this" object.

    # ── TRAINING & RESEARCH (§8b) ───────────────────────────────
    training/
      training_run.py        [N] TrainingRun object (in-progress, ticked by engine; snapshots
                                 compute/pretrain-advances/consumed advances at COMMISSION) + the pure
                                 assembly/output function → new Model. Houses the alignment-output
                                 equation incl. the EFFECTIVENESS(eval_awareness, deception) LINCHPIN,
                                 base_emergence curves, correlated_jump, drift_noise. Internal
                                 phase ordering (capability + eval-aware-ish axes FIRST, then
                                 EFFECTIVENESS, then corrective effort). reads: lab.researched_advances,
                                 parent model, alignment_constants.
      research_process.py    [N] ResearchProcess (in-progress effort, ticked by engine): ai_assist_level,
                                 cost, duration, is_reresearch flag, work-budget fraction. On
                                 completion emits a ResearchedItem. Handles re-research (flat speedup,
                                 new version replacing node's current version).
      researched_item.py     [N] ResearchedItem (completed instance consumed by training): hidden
                                 contamination (set at completion = f(assist × researching-model
                                 goal_misalignment), frozen), fixed capability_improvement, per-axis
                                 alignment_contribution. The contaminable artifact.
    research/
      capabilities/
        capabilities_research_item.py  [E] Static ResearchItem TEMPLATES for the capability tech tree
                                          (§8b obj1, §9): fixed capability boost, prereqs, intrinsic
                                          risk class, contamination-risk tier (tooling=low). DATA.
      safety/
        safety_research_item.py        [E] Static safety PROJECT templates (§7): finding-distribution
                                          as f(hidden stats), evidence type (point/bound/existence),
                                          spoofability (behavioral high / mechanistic low), cost, base
                                          duration. DATA — the projects that return FINDINGS not numbers.
      findings.py            [N] Finding objects + the sampler: given a project + TRUE stats + eval-
                                 awareness, draws concrete finding(s). Also the worry-bar synthesizer
                                 (LEVEL separate from CONFIDENCE; as foolable as evidence gathered).
                                 reads: TRUE stats; emits player-facing findings only.

    # ── ECONOMY (§9b) ───────────────────────────────────────────
    finances/
      finances.py        [E/R] Orchestrates the economy each turn. Calls the two pies + cash pot.
      revenue.py         [N] Revenue pie: total = f(world-best MEASURED capability)+noise; divvied
                             across ALL released models (all labs) by measured capability. reads: world,
                             all release_histories.
      investment.py      [N] Investment pie: total = f(best capability, total revenue, growth in both);
                             divvied across LABS by score (best model + revenue + cap/rev growth,
                             release-to-release; decay if no release; rising target). Feeds cash pot.
      market_cap.py      [N] Derived market cap per lab (investment/forward-looking, slope-weighted).
                             Drives dominance win-metric AND lobbying weight (§10c). reads: investment.

    # ── EVENTS (§10) ────────────────────────────────────────────
    events/
      event.py           [E/R] EventDefinition (DATA: trigger fn over TRUE stats, category,
                             EXISTENTIAL-vs-ORDINARY class, impact value, severity, target,
                             reversibility) + the event-phase runner (uniform loop over defs).
      event_catalog.py   [N] The actual list of EventDefinitions (misuse / misalignment / leaked-
                             weights / societal-backlash / beneficial). DATA. Each tagged with class
                             + impact. Grows by adding entries, not code.
      effects.py         [N] The closed effect vocabulary: modify_cash, modify_approval,
                             damage_reputation, leak_or_destroy_model, inject_finding,
                             modify_wtr, add_world_harm, trigger_existential_gate, end_game.
                             Events compose these. Discipline: rarely extend.
      latent_events.py   [N] Scheduled/delayed + armed-latent machinery (first-class). Houses the
                             two-stage jailbreak (discovery arms a per-model latent; subsequent turns
                             roll incident). Engine advances armed latents each turn.

    # ── GOVERNANCE / REGULATION (§10c) ──────────────────────────
    governance/
      policies.py        [N] Policy DEFINITIONS (DATA): compute-cap [near-impossible], audit-req,
                             incident-liability, interp-mandate, open-weights, disclosure. Each:
                             intro/pass/sign thresholds, compute-coverage threshold, CONSTITUTIONALITY
                             (by type: precedented-high / novel-low), effect hooks, defection rules,
                             safe-harbor option.
      regulation.py      [N] Lifecycle engine: per-turn stage rolls (introduced→passed→signed→active),
                             P ∝ enactment_score = WTR + Σ(spend-based, log-cap-scaled lobby influence).
                             Applies active-policy effects with PER-LAB COMPLIANCE ∝ disposition + the
                             3-part ENFORCEMENT model (detection P, severity scaling, ceiling/variance);
                             enforcement set at activation by passage strength, drifts with WTR.
                             reads: world.WTR, all market_caps, lab dispositions.
      lobbying.py        [N] Resolves each lab's per-policy stance + SCALABLE SPEND (player input;
                             rivals by disposition × pipeline threat). Influence = f(spend) × LOG(market
                             cap) multiplier, diminishing returns within a turn. Stage-dependent effect:
                             passage-swing (introduced) / weak-sign-swing (passed) / enforcement-drift
                             (active, can't repeal). → regulation.py.
      litigation.py      [N] Post-passage court contest: challenge vs defense ledgers; action ladder
                             (brief / join / fund-tier3-scaled); balance = challenge vs (defense + DOJ∝WTR
                             + constitutionality); outcomes (fail+entrench / penalty-cap / weaken /
                             prelim-injunction-1-3q / struck) tracked with MARGIN. Standing gated by
                             policy coverage.
      appeals.py         [N] Appeals on a litigation loss: P(success) ∝ −margin; gov appeals P ∝ WTR;
                             court hierarchy trial→circuit→SCOTUS (SCOTUS gated by low P(cert) + higher
                             bar); STAY-pending-appeal (fast, after 1 turn, freezes state, distinct from
                             prelim injunction); precedent updates constitutionality ∝ court level.
      gov_news.py        [N] (or fold into events) litigation/regulation NEWS + protest events → move
                             approval → WTR → DOJ effort. The dual-ledger political-blowback loop.

    # ── ACTORS / POLICY (decision-making) ───────────────────────
    controllers/
      controller.py      [N] LabController interface: decide(observations, disposition) → action.
      player_controller.py [N] Wraps human input as an action.
      rival_controller.py  [N] TWO-LEVEL priority controller over ITS OWN (fogged) observations — no
                             godmode (fooled by own eval-awareness; sets safety priority off own worry).
                             L1: compute reserved FIRST (binary), then budget normalized across
                             capabilities/safety/lobbying/litigation by disposition-weighted priority
                             scores (aware of WTR, other labs' MEASURED stats, enforcement levels).
                             L2: rank costed actions within each domain, buy down list to budget; appeals
                             gated on MARGIN; v1 = obvious moves only (oppose what hurts it, no strategic
                             rival-binding defense). Disposition = score-fn weights (regulation_stance,
                             safety_priority, recklessness_base + trajectory). Swappable; also the
                             player-stand-in heuristic for Monte Carlo.

    # ── OBSERVATION / INFORMATION MODEL (the chokepoint) ────────
    observation/
      observations.py    [N] Observation types (per-actor). The ONLY player-facing data shape.
      observation_builder.py [N] THE see-able/hidden chokepoint. Reads GameState (TRUE) → emits
                             filtered per-actor Observations: own stats as findings/estimates (quality
                             gated by own research), rivals' as worse estimates. A TRUE stat the player
                             shouldn't see must be IMPOSSIBLE to reach here. Enforce at type boundary.
      guidance.py        [N] Researcher-tips / guidance layer (§9 tips). Reads already-computed
                             observations ONLY; never alters probabilities. Explicitness + hedging +
                             reliability set by GUIDANCE level (NOT difficulty). Escalates hedging as
                             capability rises (diegetic regime signal).
      warnings.py        [N] The WARNING layer (§7c): diegetic "your researchers" warnings attached to each
                             risky pending CHOICE (pretrain-on-raw-data, high AI-assist, benchmark-chase,
                             high elicitation, skip-interp, behavioral-patch, release-past-finding,
                             preventive-stance). Mechanism-teaching, magnitude-FREE, layered toward paper
                             links. Distinct from guidance: guidance = world/frontier STATE; warnings =
                             consequences of YOUR pending choices. Shared voice. LOAD-BEARING fairness fix
                             (no channel enters silently). First-class content deliverable (curriculum;
                             own accuracy pass vs literature, per §0 calibration).

    # ── LOGGING / POST-MORTEM (§3, §10d — FIRST-CLASS) ──────────
    logger.py            [E] Records TRUE GameState every turn → the post-mortem substrate.
                             Continuous TRUE-stat capture; never reconstruct after loss.
    postmortem.py        [N] Builds the loss/end screen from the log: TRUE stat trajectories,
                             the turn a correlated jump fired, where cheap evals went blind, the
                             nulled positive impact, and LEGIBLE COUNTERFACTUALS (the decision
                             points where a different choice changes the outcome). NOT polish —
                             this is where the thesis lands (§10d). reads: logger history + rng (to
                             compute counterfactual branches).

    # ── TUNING / CONFIG ─────────────────────────────────────────
    config/
      difficulty.py      [N] The four difficulty settings (Easy/Medium/Realistic[default]/Impossible)
                             as constant sets. WORLD axis only. Realistic ≈ unlikely first-attempt win.
      constants.py       [N] All [TUNE] coefficients in one place (mirrors §12b): capability curves,
                             alignment emergence + EFFECTIVENESS, contamination map, finance weights,
                             event/jailbreak rates, agentic-edge gating thresholds. Difficulty.py
                             selects/scales from here.
  server/                [E] API layer: exposes Observations to frontend. Consumes engine output only;
                             never reaches into GameState.
SIMPLE_FRONTEND_V1/      [E] First throwaway skin; consumes Observations only; real skin later.
```

### Subsystem responsibility summary (what serves what)
- **Core (game/turn_pipeline/rng):** owns TRUE state + the deterministic, replayable turn order. Everything else is called by the pipeline.
- **Entities (lab/model/world):** inert data + pure self-queries. Never advance time.
- **Training & research:** convert player allocations + advances into the next Model (the §8 alignment math + the contamination-bearing research artifacts). The thesis's mechanical heart.
- **Economy:** the two pies → cash pot → market cap. Drives dominance + lobbying weight + job-loss drag.
- **Events:** uniform data-driven rolls over TRUE state; closed effect vocabulary; first-class delayed/armed latents; existential-vs-ordinary class tagging feeds scoring.
- **Governance:** WTR + cap-weighted lobbying → discrete policies w/ per-lab compliance.
- **Controllers:** decision policy, separated from entity state; rivals decide from THEIR observations.
- **Observation:** the single TRUE→visible chokepoint; guidance rides on top (info axis, not world axis).
- **Logging/post-mortem:** continuous TRUE capture → the fog→clarity→better-second-run loop (§10d), promoted to first-class.
- **Config:** all tunables + difficulty in one place; world axis only.

---

## 12. Open decisions index (consolidated)

**Resolved this session (kept here as a record, no longer open):**
- ~~Capability scalar vs vector~~ → vector `{general, coding_rnd}`.
- ~~Contamination on the training run~~ → relocated to per-node researched advances (§8b).
- ~~AI-assist global vs per-project~~ → **per-project** (§9b).
- ~~Capabilities & safety separate or shared budget~~ → **shared work-budget pool** (§9b).
- ~~Revenue follows true or measured capability~~ → **measured** (§9b).
- ~~Can releases be pulled~~ → **no, never** (§10).
- ~~Jailbreak risk decay~~ → **flat, non-decaying**; two-stage discovery→incident (§10).
- ~~One cash pot or two~~ → **one pot**, fed by revenue + investment (§9b).
- ~~Re-research speedup scaling~~ → **flat** (§8b).
- ~~Player proposes policies vs government picks; binary vs scalable lobbying~~ → **player picks stance + SCALABLE SPEND per policy; influence = f(spend) × log(market cap), diminishing returns; enactment = WTR + summed influence (model b); stage-dependent effects** (§10c). (Superseded the earlier binary/free/market-cap-weighted version.)
- ~~Approval→revenue strength~~ → **weak-to-nonexistent**; approval's job is feeding government WTR (§10c).
- ~~Capability boost per node~~ → **fixed/binary; only contamination scales** (§8b).
- ~~Benign advances?~~ → **no benign advances** (no advance is safe if the model isn't); tooling = **low-contamination** but not low-danger (§9).
- ~~Win = separate aligned-ASI gate vs collapse into impact?~~ → **two-layer: existential GATE (nulls positives) then impact+dominance score**; misaligned ASI ≈ certain self-exfiltration; rival's existential catastrophe nulls you too (§3).
- ~~Job loss event-based or capability-driven?~~ → **capability-driven, continuous** (approval drag rising with capability), not events (§10/§9b).
- ~~Compute cap feasible?~~ → kept but **near-impossible to enact** (the lesson is its unreachability) (§10c).
- ~~Single training step vs two-phase~~ → **two-phase: pretrain sets capability CEILING (latent); post-train elicits realized capability toward it (asymptotic, diminishing) AND shapes alignment**; iterable pre-release (§8b).
- ~~Post-training touches capability or only alignment?~~ → **BOTH: post-training elicits capability (a base model is not useful until elicited) AND shapes alignment in the same step** — the process that makes it useful introduces the proxy/fake-the-objective risk (§8b).
- ~~Pretrain advances can poison the base?~~ → **yes (e.g. synthetic data)** — foundational contamination, hard to scrub; advances tagged pretrain(→ceiling) vs post-train(→elicitation) (§8b).
- ~~Sandbagging = lower-than-projected performance?~~ → **no: SELECTIVE — useful capability reads on-target, risk-relevant capability reads low; model looks CLEAN not weak; tell = noise-injection project** (§8b).
- ~~efficiency vs AI-assist conflation; standalone efficiency scalar~~ → **NO standalone efficiency scalar. Pretrain advances ARE the efficiency** (they make compute raise the ceiling more). AI-assist = per-project labor knob + contamination vector, NOT in the ceiling (§8b).
- ~~Five flat alignment axes~~ → **THREE TIERS (§5):** dispositions{goal-misalign, deception, self-preserv} = coupled core w/ 3×3 defends+backfire matrices; eval-awareness = hidden capability-derived corruptor (not remediable); jailbreak-sensitivity = standalone cleanly-patchable robustness.
- ~~Remediation unspecified~~ → **§5b: one pipeline, per-axis table (base_tractability, defends-matrix, backfire-matrix, self-preserv resistance) + EFFECTIVENESS = tractability × Π(1−defends×strength); three types (behavioral/preventive/mechanistic); attribution via intervention logging.**
- ~~Misalignment feels unfair (no visible mechanism)~~ → **§7c WARNING layer: diegetic mechanism-teaching magnitude-free warnings on every risky choice; converts loss from "game hid it" (type-A) to "I was warned and did it anyway" (type-B). Primary educational surface; first-class content deliverable.**

**Still open:**
1. Persuasion: third capability component or fold into `general`? (lean: fold)
2. **Capability-gating of agentic edges** (§5) — at what `general`/`coding_rnd` levels each edge comes online, and how steeply. Frontier-tips depend on these thresholds. **The next major modeling piece.**
3. Rising investment target: **frontier-relative** (brutal, thesis) vs **self-relative** (gentle)? (§9b)
4. Investment as **stock** (banked) vs **flow against valuation** (§9b). Lean: cash pot is the stock; investment adds to it each quarter.
5. Trust-in-guidance: own knob / folded into difficulty / fixed? (§1)
6. Regulation binds you too, or only rivals? (§10c — current design: binds via per-lab compliance; mostly resolved, confirm)
7. How much rival hidden state is learnable, and by what channels? (§10)
8. Leaked-weights event class internals: trigger, who abuses, how downstream risk differs from a guarded release (§10).
9. Big-lead threshold for rival-caused game-enders (§10).
10. Snowball: are diminishing-returns + leader-runs-hottest sufficient, or add catch-up dynamics? (§10) — note the **double-count** (best-model capability feeds both pie totals) amplifies late snowball (§9b).
11. Full event catalog finalize: each tagged **existential-class vs ordinary-class** + impact value + gating stats + reversibility (§3/§10).
12. "Impossible" mode: barely-winnable (current) vs literally-unwinnable (§1).
13. Number of rival labs (placeholder 4).
14. Training-run internal ordering (compute eval-awareness-ish axes before EFFECTIVENESS) — inferred, not designer-confirmed (§8b).
15. Post-ASI window: any player agency / emergency lever, or pure watch? (§3)

---

## 12b. Tunable parameters index (`[TUNE]`)

Single place to find every knob; each scales by difficulty (Easy/Medium/Realistic/Impossible) unless noted.

**Capability / training (§8, §8b)**
- `saturating_fn` shape: compute→capability curve (saturation point, steepness).
- Pretrain-advance ceiling-efficiency effects (how much each pretrain advance raises compute→ceiling conversion).
- Per-node fixed capability boost magnitudes (per ResearchItem).
- Re-research flat speedup %.

**Alignment emergence (§8)**
- `base_emergence` curves per axis (surface axes: high at all capability; eval-aware/deception/self-preservation: near-zero→rising-with-capability).
- `EFFECTIVENESS` — base_tractability[axis] (jailbreak high, dispositions low) × concealment_discount = Π(1−defends[d][target]×strength(d,capability)). The linchpin; decay as defenders activate w/ capability.
- defends[protector][target] MATRIX + backfire[patched][affected] MATRIX (the §5 interaction layers).
- self-preservation resistance(self_preserv, capability) — reduces effective_effort for all interventions.
- Per-intervention-type: behavioral (full gated EFFECTIVENESS + backfire), preventive (emergence/jump modifiers, bypasses discount), mechanistic (partial_coverage<1, bypasses discount).
- `alignment_effort` potency per safety-project per axis.
- Per-node intrinsic `alignment_contribution` per axis (per ResearchItem risk class).
- `contamination` mapping: (ai_assist × researching-model goal-misalignment) → node contamination.
- `correlated_jump` base probability + how it scales with risky-practice & capability; jump magnitude (goal-misalignment + deception bundle).
- `drift_noise` variance per axis.

**Agentic edges (§5)** — OPEN #2
- Per-edge capability-gating thresholds + steepness (when each edge comes online).
- Per-edge strength.

**Finance (§9b)**
- Revenue pie total: capability→market-size curve + noise variance.
- Revenue divvy: capability→share weighting across all released models.
- Investment pie total: weights on (best capability, total revenue, capability growth, revenue growth).
- Lab score / investment: GRACE_QUARTERS (~3–4 baseline-growth window before a cliff); EXPECTED_GAIN(Δt) rising-expectation curve; precipitous-fall magnitude on missed expectation; frontier-relative target.
- Dominance win threshold (plurality %).
- Work-budget size per quarter; per-project difficulty (budget fraction); AI-assist budget-reduction curve.
- Compute-run cash cost; project cash costs.
- SANDBAG_REVENUE_PENALTY (→ resolve to ~0 per Q1; hidden dangerous capability was never revenue).

**Governance (§10c)**
- Policy stage thresholds (intro/pass/sign) per policy; compute-cap threshold (effectively unreachable on Realistic).
- WTR rise/fall rates (incidents, approval, job loss, beneficial events, lobbying).
- Enforcement: base_detection, severity scaling, ceiling/variance scaling; activation-strength→enforcement map; WTR→enforcement drift rate.
- Lobbying: f(spend) curve + diminishing returns; log-cap multiplier (k, reference_cap); stage-effect magnitudes (passage-swing / weak-sign-swing / enforcement-drift).
- Constitutionality by policy type (precedented-high / novel-low) + passage-strength modifier.
- Litigation: action-ladder costs (brief flat / join fixed / fund-tier3 min + scaling w/ diminishing returns); outcome thresholds vs margin; DOJ-effort ∝ WTR weight; entrenchment (constitutionality gain on survived challenge) ∝ court level.
- Appeals: P(success) ∝ −margin curve; gov-appeal P ∝ WTR; SCOTUS P(cert) + win-bar; stay-grant ∝ −margin; precedent constitutionality-shift by court level.
- Litigation/regulation news → approval/WTR shift magnitudes.

**Events (§10)**
- Jailbreak discovery roll rate (∝ true jailbreak-sensitivity); incident roll rate once discovered.
- Misuse / misalignment / societal event probabilities & severities (gated by their stats).
- Frontier-catastrophe gating; rival big-lead threshold for game-enders.
- Leaked-weights trigger + downstream params.

**Config (§1)**
- Rival count (≈4); per-rival disposition (recklessness, regulation stance, cost advantage) by difficulty.
- True-vs-measured gap size (alignment large, capability small) by difficulty.
- Guidance level (explicitness, hedging, reliability) — observation layer, NOT difficulty.
- Game length / ASI threshold; post-ASI window length.

---

## 12c. Build-note follow-ups (v1 findings — FIX LATER)

From Fable's `backend_v1` build + first playtests. Tracked so they aren't lost.

**Difficulty / balance (HIGH PRIORITY — v1 is too easy):**
- **Reckless play WON with the turn cap removed.** v1 is too easy on the reckless path; the whole point is that recklessness ≈ doom. Needs across-the-board tightening. Suspects: jump rates too low, EFFECTIVENESS decay too gentle, beneficial events too generous, catastrophe gating too forgiving.
- **Investment instant-drop bug → fixed in §9b** (grace window + expectation model). Was causing degenerate "ship every turn."
- **Late game flattened into compute-saving → fixed in §9** (rising unlock durations, AI-assist near-mandatory, tree progresses past IRL to ASI).
- The cautious-player existential rate (6/25 on realistic) is thesis-correct (claim #6) — but keep legible in the post-mortem that they lost to RIVALS' catastrophes, not their own, so it reads "unilateral caution doesn't save you," NOT "caution is punished" (fatalism failure, §10d).
- **Scripted heuristics can't verify §10d "skilled play improves outcomes"** — even Easy is ~unwinnable for balanced/cautious scripts. Needs human/`--agent` play to confirm careful play beats reckless. **This is the open question that most threatens the thesis — resolve before trusting difficulty tuning.**

**Designer decisions still owed (from build Q1–Q6):**
- **Q1 sandbagging vs revenue:** RESOLVE as — commercial capability reads on-target & earns normally; **no revenue penalty** (drop `SANDBAG_REVENUE_PENALTY`≈0); the cost of sandbagging is **unpriced TRUE capability feeding catastrophe gating**, not lost revenue. §9b "underearns" sentence was imprecise; hidden dangerous capability simply was never a revenue source. *(confirm)*
- **Q2 ASI cliff = TRUED, not released model** → confirmed correct (model acts, not the market).
- **Q3 big-lead gates pre-ASI existential events only; ASI cliff fires regardless** → confirmed (reaching ASI *is* the big lead).
- **Q4 player policy-defection knob:** not in v1; doc implies eventually yes (compute-cap defection text). Decide if/when player gets an explicit defect action with catch-risk.
- **Q5 post-ASI agency:** pure-watch in v1 (open #15 still open).
- **Q6 worry-bar formula:** invented (weighted concern of last-8 findings; confidence from volume + mechanistic share). Satisfies requirements; "falsely-calm-thin-bar feels reassuring" property needs playtest validation.

**Implementation notes worth canonizing:**
- **Targeted-fix mechanism** (completing a safety project → queued `pending_effort` on its axes → consumed by next post-train round, EFFECTIVENESS-gated) → **now canonical in §7.**
- **Counterfactual post-mortem under-delivers §10d in v1** (heuristic decision-point extraction, not true branch re-sim). Deterministic seed + action log make real re-sim possible → **highest-value next build task.**
- Missing **§1 header** is an editing artifact (orphaned "These are orthogonal" intro) — the Guidance×Difficulty block IS §1.
- Invented placeholders to review per §0 bleak-bias: capability-gating onsets (emergence ≈3.5–4.5, agentic edges ≈5.0, steepness 1.2 on 0–10 scale, ASI 9.0); leaked-weights params; big-lead threshold (+1.2 general); beneficial-event deployment-weighting (good call — strict frontier attribution denies player nearly all positives).

---

## 13. Build order (suggested)

1. **Core skeleton:** `game.py` (GameState/GameEngine split), `turn_pipeline.py`, `rng.py`, entities (`lab/model/world`). Lock the TRUE-vs-observed boundary and deterministic replay FIRST; everything keys off both.
2. **Observation chokepoint:** `observations.py` + `observation_builder.py`. Get the see-able/hidden filter right before any frontend exists.
3. **Training & research core (§8b):** `training_run.py` (capability half first, then the alignment-output fn with the `EFFECTIVENESS` linchpin), `research_process.py`, `researched_item.py`. Single-lab, no rivals.
4. **Findings layer (§7):** `findings.py` — ONE project end-to-end (deception probe) before generalizing; worry-bar with level≠confidence.
5. **Regime emergence (§6):** `base_emergence` curves; verify the 2021 feel emerges automatically.
6. **Logging + POST-MORTEM LOOP (§3, §10d) — DO THIS EARLY, NOT LAST.** `logger.py` + `postmortem.py` with legible counterfactuals. Build as soon as there's a losable game, so you can feel whether losses read "earned" vs "rigged" and tune accordingly. The fog→clarity→better-second-run loop is the thesis; nothing downstream matters if it's weak.
7. **Agentic edges + capability-gating (§5, open #2):** turn on the coupling; verify "fine until suddenly not."
8. **Economy (§9b):** `revenue.py`, `investment.py`, `market_cap.py`, `finances.py`. Two pies → cash pot; job-loss drag.
9. **Events (§10):** `event.py`, `event_catalog.py`, `effects.py`, `latent_events.py`. Tag existential vs ordinary; wire into scoring.
10. **Rivals (§4.2):** `controllers/` — rivals decide from THEIR observations; dispositions.
11. **Governance (§10c):** `world.py` WTR/approval, `policies.py`, `regulation.py`, `lobbying.py`.
12. **Guidance + WARNING systems (§9 tips, §7c):** `guidance.py`, `warnings.py` — observation-layer only. The §7c warnings are LOAD-BEARING for fairness, not polish — a minimal version should exist as soon as risky choices do, so playtest losses read "I was warned" not "rigged."
13. **Config/difficulty (§12b):** `constants.py`, `difficulty.py`; tune so Realistic ≈ unlikely first-attempt win AND a skilled second run VISIBLY improves (anti-fatalism, §10d).
14. Frontend skin(s) last, against the frozen observation contract.

---

## 14. Headless / CLI runthrough — agent-playable without a frontend

**Goal:** a Claude Code agent (or a human in a terminal, or an automated script) plays a full game with NO frontend served. This is the FIRST validation target, not a compromise — it exercises the whole engine before any UI exists.

**Why it's nearly free:** the engine is already pure `(state, action) → (state, observations)` with controllers as a separate policy layer (§11). An agent playing a runthrough is **just another `LabController`** in the player slot — same interface as the rival heuristic controller. The CLI is a thin harness around the existing loop, not a new system.

### What's needed
- **`cli/run_game.py`** — a driver/harness: builds initial GameState (seed, difficulty, guidance, rival count), then loops `step()` until end/existential gate, printing observations and reading actions each turn. The harness is presentation-agnostic; it only touches the public engine API + observation contract.
- **Observations must be SERIALIZABLE to text/JSON.** The observation_builder output needs a clean dict/JSON form so it can be printed (human) or fed to an agent (LLM). This should already be true if observations are a clean data contract — just confirm no objects that only render in a GUI.
- **Actions must be constructible from text/JSON.** A turn's action is a structured object (allocations across projects, per-project ai_assist, commission-run params, release y/n, per-policy lobby stance). Need: (a) a schema/spec for a valid action, (b) a parser from JSON→Action, (c) validation with clear error messages (an agent will produce malformed actions; fail loud, not silent).
- **`AgentController`** (a `LabController` impl): receives observations as JSON + the action schema, returns an action as JSON. For a Claude Code agent this is literally "here is the game state, here are your legal moves, emit your move." Keep it a pure function of observations (same as rivals — no peeking at TRUE state).
- **A legal-moves / action-space helper** — given current observations, enumerate or describe what actions are valid this turn (which projects available, can you release, which policies are on the table). Agents play far better with an explicit action space than by guessing the schema. Doubles as validation.
- **Deterministic seed control** (already via `rng.py`) — pass a seed so a runthrough is reproducible. Essential for debugging "the agent did X and the game did Y."
- **Turn-by-turn structured log to stdout/file** — each turn: observations in, action taken, events fired, key deltas. Human-readable AND machine-parseable. This is also the post-mortem substrate (§3) surfaced live.
- **End-of-game report to terminal** — the post-mortem (§3, §postmortem.py) rendered as text: TRUE trajectories, the nulled impact, counterfactuals, win/loss. The text post-mortem is genuinely useful on its own and validates that module early.

### Modes the harness should support (cheap once the above exists)
- **Interactive human CLI** — print observations, prompt for an action (or a guided menu). Good for the designer to feel the game.
- **Agent-driven** — `AgentController` in the player slot; agent plays unattended start→finish. The Claude Code runthrough.
- **Scripted / fixed-policy** — feed a predetermined action sequence (e.g. "always max capability, never safety"). Essential for tuning + regression tests (assert that the all-capability policy reliably hits the existential gate on Realistic).
- **Batch / Monte Carlo** — run N games headless with a fixed policy + varying seeds, aggregate win rates. THE tuning tool: this is how you verify "Realistic ≈ unlikely first-attempt win" and "skilled play visibly improves outcomes" (§10d) empirically rather than by guess.

### Doable as a CLI? — yes
No blockers. Requirements reduce to: (1) observations serialize to JSON, (2) actions parse from JSON with validation, (3) an `AgentController` and a `run_game.py` loop. All three are thin wrappers over the engine/controller/observation split you're already building. Recommend building the CLI harness RIGHT AFTER the core skeleton + observation chokepoint (build-order steps 1–2), so every subsequent subsystem is exercised headlessly as it lands — the engine is testable and agent-playable long before a pixel is drawn.

---

*End of context. When in doubt, re-read §0 — the mechanics exist to make those six claims felt, and the assistant's calibration bias runs toward optimism; push back toward the thesis.*