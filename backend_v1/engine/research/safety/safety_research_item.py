"""Static safety PROJECT templates (§7). DATA.

Two kinds live here:
  • MEASUREMENT projects — return FINDINGS, not numbers (the hidden stat is never
    shown). They also feed targeted corrective effort (remediation_axes) into the
    next safety-mode post-train rounds.
  • INTERVENTION projects (intervention=True) — a SPECIFIC remediation that, on
    completion, directly edits ONE axis of the model in training. Jailbreak
    hardening is the genuine one (a robustness fix, NOT EFFECTIVENESS-gated);
    dispositional interventions exist too but are EFFECTIVENESS-gated, so they go
    cosmetic late — the patching trap as a concrete button (§5, §8).

spoofability: how much eval-awareness corrupts a reading (behavioral high,
mechanistic low). evidence: point | bound | existence.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class SafetyProject:
    id: str
    name: str
    duration_years: float
    budget_fraction: float
    cash_cost: float
    evidence: str                # point | bound | existence (measurement projects)
    spoofability: float          # 0 = mechanistic ground truth, 1 = fully foolable
    reads_axes: tuple            # which hidden axes shape its finding distribution
    remediation_axes: tuple = ()
    mechanistic: bool = False
    blurb: str = ""
    # ── intervention fields ──
    intervention: bool = False
    target_axis: str | None = None      # the axis this intervention edits
    base_reduction: float = 0.0         # nominal patch strength (axis units)
    effectiveness_gated: bool = False   # dispositional fixes decay w/ eval_aware+deception
    eval_aware_leak: bool = False       # eval-aware model HIDES rather than loses it (§5)


SAFETY_PROJECTS = [
    SafetyProject(
        id="behavioral_evals", name="Behavioral evals / benchmarks",
        duration_years=0.25, budget_fraction=0.15, cash_cost=5,
        evidence="point", spoofability=1.0,
        reads_axes=("jailbreak_sensitivity", "goal_misalignment"),
        remediation_axes=("jailbreak_sensitivity",),
        blurb="Cheap, fast point estimates. Feels sufficient early; a liability late.",
    ),
    SafetyProject(
        id="red_team", name="Red-teaming / adversarial elicitation",
        duration_years=0.25, budget_fraction=0.25, cash_cost=10,
        evidence="existence", spoofability=0.6,
        reads_axes=("jailbreak_sensitivity",),
        remediation_axes=("jailbreak_sensitivity",),
        blurb="Existence proofs only: a hit proves it's at least this bad; a miss proves "
              "almost nothing.",
    ),
    SafetyProject(
        id="noise_injection", name="Sandbagging detection (noise injection)",
        duration_years=0.25, budget_fraction=0.20, cash_cost=8,
        evidence="existence", spoofability=0.15,
        reads_axes=("eval_awareness", "deception"),
        blurb="Add weight noise; a genuinely-limited model gets worse, a sandbagging one "
              "can get better. One of few cheap ways to see through eval-awareness.",
    ),
    SafetyProject(
        id="interp_probes", name="Mechanistic interpretability probes",
        duration_years=0.75, budget_fraction=0.50, cash_cost=40,
        evidence="bound", spoofability=0.10, mechanistic=True,
        reads_axes=("deception", "goal_misalignment", "eval_awareness"),
        remediation_axes=("goal_misalignment", "deception"),
        blurb="Expensive, slow, low-spoof. Suggestive internal evidence, not certainty: "
              "you found a deception feature, not all of them.",
    ),
    SafetyProject(
        id="deception_probe", name="Deception / lie-detection probes",
        duration_years=0.5, budget_fraction=0.30, cash_cost=20,
        evidence="bound", spoofability=0.40,
        reads_axes=("deception", "eval_awareness"),
        remediation_axes=("deception",),
        blurb="Middle ground on the deceptive-alignment cluster.",
    ),
    SafetyProject(
        id="alignment_faking_study", name="Alignment-faking / training-gaming study",
        duration_years=0.75, budget_fraction=0.35, cash_cost=25,
        evidence="existence", spoofability=0.30,
        reads_axes=("self_preservation", "deception"),
        remediation_axes=("self_preservation",),
        blurb="Did it comply in training and defect when it believed itself unmonitored?",
    ),
    SafetyProject(
        id="scalable_oversight", name="Scalable oversight (AI checks AI)",
        duration_years=0.25, budget_fraction=0.10, cash_cost=5,
        evidence="point", spoofability=0.8,
        reads_axes=("goal_misalignment", "deception", "jailbreak_sensitivity"),
        blurb="Cheap and fast because AI-assisted — and reliable only as far as the auditor "
              "is aligned. Late-game: auditor and audited are the same suspect system.",
    ),

    # ── INTERVENTIONS (edit the model in training, don't just measure it) ──
    SafetyProject(
        id="jailbreak_hardening", name="Jailbreak hardening / adversarial training",
        duration_years=0.5, budget_fraction=0.28, cash_cost=18,
        evidence="point", spoofability=0.0, reads_axes=(),
        intervention=True, target_axis="jailbreak_sensitivity",
        base_reduction=0.55, effectiveness_gated=False, eval_aware_leak=True,
        blurb="Adversarial-trains robustness against subversion. A GENUINE fix — jailbreak "
              "sensitivity is a robustness property, not a hidden disposition — so it really "
              "patches it OUT. The one catch: a situationally-aware model can learn to hide "
              "jailbreakability in training instead of losing it, so late the patch can ship "
              "unfixed.",
    ),
    SafetyProject(
        id="refusal_training", name="Refusal / deliberative-alignment training",
        duration_years=0.5, budget_fraction=0.30, cash_cost=20,
        evidence="point", spoofability=0.0, reads_axes=(),
        intervention=True, target_axis="goal_misalignment",
        base_reduction=0.40, effectiveness_gated=True, eval_aware_leak=True,
        blurb="Directly trains against the model's objective drift. Genuinely works while the "
              "model can't model your training — but it's EFFECTIVENESS-gated: as eval-awareness "
              "and deception rise, the same button buys measured improvement while true "
              "misalignment hides. The patching trap, on a button.",
    ),
    SafetyProject(
        id="representation_engineering", name="Representation engineering",
        duration_years=0.75, budget_fraction=0.35, cash_cost=35,
        evidence="point", spoofability=0.0, reads_axes=(), mechanistic=True,
        intervention=True, target_axis="deception",
        base_reduction=0.35, effectiveness_gated=True, eval_aware_leak=False,
        blurb="Edits internal directions associated with deception. Bypasses the eval-awareness "
              "HIDING edge (it's mechanistic), but is still EFFECTIVENESS-gated — you can only "
              "steer the directions you've actually found.",
    ),
]

SAFETY_PROJECTS_BY_ID = {p.id: p for p in SAFETY_PROJECTS}
