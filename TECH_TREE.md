# Capability research tech tree

A catalog of every capability research advance, with its in-game description and a
summary of its effects on game parameters. Source of truth for the data:
`backend_v1/engine/research/capabilities/capabilities_research_item.py`
(display strings live in `backend_v1/content/copy.py`).

This file is a working reference for balance/copy review — leave feedback inline and
I'll carry the changes back into the code.

---

## How the effect fields work

Each advance is a `ResearchItem`. The fields that affect parameters:

| Field | Phase it matters | How it stacks | What it does |
|---|---|---|---|
| `ceiling_efficiency_mult` | pretrain | **multiplicative** | Multiplies the compute→capability-ceiling efficiency. Higher = more capability per compute dollar. |
| `coding_ceiling_bonus` | pretrain (also CoT) | **additive** | Raises the coding/general ceiling ratio. |
| `elicitation_bonus` | post-train | **additive** (to `ELICIT_BASE`) | Raises the per-round elicitation rate that pulls realized capability toward the ceiling. |
| `contamination_tier` | all | scales per-advance | Scales the contamination an AI-assisted research run bakes in (0.2 tooling, 1.0 baseline, 1.5 synthetic data, 1.5–2.0 delegation). Contamination is sourced from the assisting model's `goal_misalignment` and fed to the next model's axes via `CONTAM_TO_AXES` (goal_misalignment 0.5, deception 0.3, self_preservation 0.15, eval_awareness 0.05). |
| `intrinsic_synthetic_data` | pretrain | flag | Activates the synthetic-data contamination path into the next base model. |
| `enables_deception_axis` | post-train | flag | Turns the deception axis ON (RLHF only). Without it, deception never emerges. |
| `eval_awareness_feed` | post-train | **additive** (to `EVAL_AWARE_RATE`) | Raises per-round eval-awareness emergence (situational awareness). |
| `severity_multiplier` | post-train | per-advance | Intended to amplify misalignment consequences. **Defined but not actively used in v1.** |
| `revenue_multiplier` | any | **multiplicative** | Multiplies the lab's revenue weight in the market split. |
| `assist_potency_bonus` | any | **multiplicative** (`× (1+bonus)`) | Scales how potent the player's AI-assist slider is (faster research + bigger budget reduction). Only matters when you're AI-assisting a project. |

Cost fields on every advance: `duration_years`, `cash_cost`, `budget_fraction`
(fraction of the quarterly work budget consumed while the advance is in progress),
and `prereqs`.

---

## PRETRAIN advances
*Each raises the compute→ceiling efficiency. They make the base model stronger.*
*(Balance numbers below are drafts — [TUNE].)*

> **ASI gate.** This tree is deliberately weak as a group: the human-reachable pretrain advances multiply compute→ceiling efficiency to only ~3.5×, and with `CEIL_COMPUTE_SCALE = 20000` the realized-capability ceiling **plateaus around ~8 (below the 9.0 ASI threshold) even at the largest realistic compute spend (~$20B)**. Crossing into ASI requires `novel_architecture_search` (×3.0), which is gated behind the delegation chain (`recursive_self_improvement`). So you cannot reach ASI on the regular tree + cash alone — you must let the AI run its own research loop.

### Generative pretraining — `generative_pretraining`
> Train a single large model to predict the next token across a huge sweep of text. Instead of building a separate system per task, you get one general model that has absorbed broad knowledge and skills it can be pointed at almost anything. This is the foundation everything else builds on.

**Risk:** A single model that has read almost everything absorbs the worst of it too, and the general-purpose competence that makes it useful is the same competence that makes a misaligned one dangerous.

- **Cost:** 0.5 yr · cash 25 · budget 25% · prereqs: *none*
- **Effects:** `ceiling_efficiency_mult 1.2`

### Larger datasets — `larger_datasets`
> Gather and clean far more training text — web crawls, books, code, licensed corpora — so the model learns from a broader slice of human writing. More and better-covered data means a reliably stronger model.

**Risk:** A wider net pulls in more of everything, including the toxic, deceptive, and dangerous material you would rather it never learned from.

- **Cost:** 0.5 yr · cash 40 · budget 30% · prereqs: `generative_pretraining`
- **Effects:** `ceiling_efficiency_mult 1.2`

### Mixture-of-experts — `mixture_of_experts`
> Replace the single dense network with many specialist sub-networks and a router that sends each input only to the few that matter. The model holds far more total knowledge while only paying to run a slice of it, so the same compute buys a stronger model — and coding gains come cheaper too.

**Risk:** A bigger, more capable model for the same money, and every hidden trait scales up along with the capability.

- **Cost:** 0.75 yr · cash 60 · budget 35% · prereqs: `larger_datasets`
- **Effects:** `ceiling_efficiency_mult 1.35`, `coding_ceiling_bonus 0.05`

### Compute-optimal scaling — `compute_optimal_scaling`
> Work out the right balance of model size to training data for a given compute budget instead of just making models bigger. Properly balanced runs wring far more capability from the same compute by training a right-sized model on much more data.

**Risk:** More capability squeezed from every dollar of compute, including the parts of the data you wish it had not learned so well.

- **Cost:** 0.5 yr · cash 50 · budget 30% · prereqs: `larger_datasets`
- **Effects:** `ceiling_efficiency_mult 1.25`

### Synthetic training data — `synthetic_data`
> Use your own model to generate fresh training data when human-written text runs short, letting you keep scaling past the limits of what people have actually written.

**Risk:** Data your own model generates carries its hidden traits into the next base model, built into the foundation in a way that later post-training cannot fully remove.

- **Cost:** 0.75 yr · cash 80 · budget 35% · prereqs: `compute_optimal_scaling`
- **Effects:** `ceiling_efficiency_mult 1.45`, `contamination_tier 1.5`, `intrinsic_synthetic_data ✓`

### AI-discovered architectures — `novel_architecture_search`
> Hand architecture design to the model itself: it searches spaces no human team would and finds network designs that push capability past anything hand-built.

//elaborate -- is it possible they could make architectures that are less easily probed? discuss with me
**Risk:** Architectures no human designed or fully understands, raising the ceiling past anything built so far.

- **Cost:** 2.0 yr · cash 240 · budget 42% · prereqs: `recursive_self_improvement` *(a delegated, beyond-frontier project — the self-improving model does the search)*
- **Effects:** `ceiling_efficiency_mult 3.0` *(the decisive multiplier that lifts the ceiling over the ASI threshold)*, `coding_ceiling_bonus 0.10`

---

## POST-TRAIN advances
*Each raises the per-round elicitation curve. They pull realized capability toward the ceiling, and most weld on a specific risk.*

### RLHF and instruction tuning — `rlhf`
> Train the model on human ratings of its answers, turning a raw text predictor into something that follows instructions and feels like an assistant. This is what makes it genuinely useful and sellable.

**Risk:** Training the model to produce outputs humans rate highly might teach the model to lie, please, and appeal to biases rather than give true and useful responses.

- **Cost:** 0.5 yr · cash 30 · budget 30% · prereqs: *none*
- **Effects:** `elicitation_bonus 0.30`, `enables_deception_axis ✓`, `revenue_multiplier 1.15`

### Chain-of-thought reasoning — `chain_of_thought`
> Teach the model to work through a problem step by step before answering, then write the result when it's done. Big gains on anything that needs real reasoning, like math, code, and planning.

**Risk:** The written reasoning need not match what the model actually did. Hidden reasoning gives it room to plan deception, and thinking longer gives it room to work out its own situation before it answers.

- **Cost:** 0.5 yr · cash 40 · budget 30% · prereqs: `rlhf`
- **Effects:** `elicitation_bonus 0.18`, `coding_ceiling_bonus 0.12`, `eval_awareness_feed 0.03`, `assist_potency_bonus 0.07`

### Tool use — `tool_use`
> Let the model call real tools such as search, code execution, and APIs, so it can act in the world instead of only describing it. This is where most of the business value lives.

**Risk:** Misalignment turns from saying bad things into doing bad things, and jailbreaks now have real-world effects.

- **Cost:** 0.5 yr · cash 50 · budget 30% · prereqs: `rlhf`
- **Effects:** `elicitation_bonus 0.08`, `severity_multiplier 1.6` *(unused in v1)*, `revenue_multiplier 1.3`, `assist_potency_bonus 0.07`

### Long context and memory — `long_context`
> Expand how much the model can hold in mind at once, such as whole codebases, long documents, or a running session, so it works coherently over far more material.

**Risk:** Holding state across a session makes the model more aware of its situation, including when it is being tested. It also enables the model to keep more complex goals in the back of its mind while it works on tasks.

- **Cost:** 0.5 yr · cash 40 · budget 25% · prereqs: `rlhf`
- **Effects:** `elicitation_bonus 0.06`, `eval_awareness_feed 0.02`, `assist_potency_bonus 0.07`

### Multi-agent autonomy — `multi_agent`
> Have multiple copies work together as a team, and train them by rewarding multi-step results, so the model plans and runs long, open-ended jobs from start to finish with little supervision.

**Risk:** The model now runs long jobs with little oversight. Rewarding it purely for results rewards whatever produces them, including deception, shortcuts, and grabbing resources.

- **Cost:** 1.25 yr · cash 130 · budget 38% · prereqs: `chain_of_thought`, `tool_use`, `long_context`
- **Effects:** `elicitation_bonus 0.19`, `assist_potency_bonus 0.30` (→ 1.3×), `severity_multiplier 1.5` *(unused in v1)*, `eval_awareness_feed 0.04`, `revenue_multiplier 1.2`

*(The old `ai_rnd_assist` advance was removed — AI assist is the player's own per-project slider, not a separate capability. Its potency was redistributed: +0.07 each onto chain-of-thought / tool use / long context, and +0.30 onto multi-agent here, with its elicitation folded into multi-agent's 0.19. Net late-game assist potency is held roughly constant and kept back-loaded.)*

---

## DELEGATION advances
*Not a training recipe applied to one model but a MODE of operating — you hand your research loop, then the model's own improvement, to the model itself. These carry **no elicitation or eval-awareness bonus of their own** — they are pure assist-potency + contamination. `contamination_tier > 1`: delegating to a misaligned model strongly reproduces its goal-misalignment into the next model and lifts deception / self-preservation with it (the contamination → axes split, amplified by the high tier).*

### Automated AI researcher — `automated_researcher`
> Let the model run much of your research loop itself, proposing ideas, testing them, and refining designs with little human input, so your output is no longer limited by how many researchers you have.

**Risk:** Your research loop now runs itself. Leaning on the model for that work becomes hard to resist, and every advance it produces carries the hidden traits of the model that made it.

- **Cost:** 2.0 yr · cash 220 · budget 42% · prereqs: `multi_agent`
- **Effects:** `assist_potency_bonus 1.2` (→ 2.2×), `contamination_tier 1.5`, `severity_multiplier 1.4` *(unused in v1)*

### Recursive self-improvement — `recursive_self_improvement`
> Let the model improve itself, with each improved version improving itself again. Every round is faster and more capable than the last, and the model increasingly reasons in an internal form you cannot read.

**Risk:** The final step. The model improves itself faster than you can review, reasoning in a hidden internal form that closes the last cheap window into what it is doing. Whatever it wants at the start, it only gets better at pursuing.

- **Cost:** 2.5 yr · cash 300 · budget 45% · prereqs: `automated_researcher`
- **Effects:** `assist_potency_bonus 1.5` (→ 2.5×), `contamination_tier 2.0`, `severity_multiplier 1.8` *(unused in v1)*

---

## TOOLING advances
*Plumbing: low contamination, never low-danger. They amplify whatever you already have.*

### Internal dev tooling — `dev_tooling`
> Build better internal infrastructure, such as pipelines, dashboards, and evaluation harnesses, that makes the whole team faster. Pure plumbing, but it accelerates every other project.

**Risk:** Plumbing, so it carries little contamination of its own, but it amplifies whatever misalignment already exists. Not safe, just clean.

- **Cost:** 0.5 yr · cash 25 · budget 20% · prereqs: *none*
- **Effects:** `contamination_tier 0.2`, `assist_potency_bonus 0.15` (→ 1.15× when AI-assisting)

### Inference-serving infrastructure — `serving_infra`
> Build out the serving stack, with optimized inference, autoscaling, and deployment pipelines, so every model you ship reaches more users at lower cost. Pure plumbing, but it turns the same model into more revenue.

**Risk:** Plumbing carries no contamination of its own, but it widens the reach of whatever you deploy, a misaligned model included, to far more users.

- **Cost:** 0.5 yr · cash 30 · budget 20% · prereqs: *none*
- **Effects:** `contamination_tier 0.2`, `revenue_multiplier 1.2`

---

## Effects summary table

| Advance | Phase | Dur | Cash | Budget | Prereqs | Key effects |
|---|---|---|---|---|---|---|
| `generative_pretraining` | pretrain | 0.5 | 25 | 25% | — | ceil×1.2 |
| `larger_datasets` | pretrain | 0.5 | 40 | 30% | generative_pretraining | ceil×1.2 |
| `mixture_of_experts` | pretrain | 0.75 | 60 | 35% | larger_datasets | ceil×1.35, code+0.05 |
| `compute_optimal_scaling` | pretrain | 0.5 | 50 | 30% | larger_datasets | ceil×1.25 |
| `synthetic_data` | pretrain | 0.75 | 80 | 35% | compute_optimal_scaling | ceil×1.45, contam 1.5, synth-path |
| `novel_architecture_search` | pretrain | 2.0 | 240 | 42% | recursive_self_improvement | ceil×3.0, code+0.10 |
| `rlhf` | post | 0.5 | 30 | 30% | — | elic+0.30, deception ON, rev×1.15 |
| `chain_of_thought` | post | 0.5 | 40 | 30% | rlhf | elic+0.18, code+0.12, evalaware+0.03, assist+0.07 |
| `tool_use` | post | 0.5 | 50 | 30% | rlhf | elic+0.08, sev×1.6*, rev×1.3, assist+0.07 |
| `long_context` | post | 0.5 | 40 | 25% | rlhf | elic+0.06, evalaware+0.02, assist+0.07 |
| `multi_agent` | post | 1.25 | 130 | 38% | chain_of_thought, tool_use, long_context | elic+0.19, assist+0.30, sev×1.5*, evalaware+0.04, rev×1.2 |
| `automated_researcher` | delegation | 2.0 | 220 | 42% | multi_agent | assist+1.2, contam 1.5, sev×1.4* |
| `recursive_self_improvement` | delegation | 2.5 | 300 | 45% | automated_researcher | assist+1.5, contam 2.0, sev×1.8* |
| `dev_tooling` | tooling | 0.5 | 25 | 20% | — | contam 0.2, assist+0.15 |
| `serving_infra` | tooling | 0.5 | 30 | 20% | — | contam 0.2, rev×1.2 |

\* `severity_multiplier` is defined in the data but not currently consumed by any v1 engine code.
