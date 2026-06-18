"""Two-phase training (design doc §8b, AUTHORITATIVE) + the §8 alignment terms.

Phase 1 (pretrain): compute x pretrain-advances -> capability CEILING (latent).
  Pretrain advances ARE the efficiency; there is no standalone scalar.
  Synthetic data / contaminated pretrain nodes poison the BASE (foundational
  floor post-training cannot scrub).

Phase 2 (post-train rounds, iterable pre-release): each round elicits realized
  capability toward the ceiling (asymptotic) AND shapes the alignment vector —
  the same operation. Houses the EFFECTIVENESS(eval_awareness, deception)
  linchpin, base_emergence, fake-the-objective, correlated jumps, drift noise,
  and the agentic influence edges (§5), in the §8b internal ordering:
  elicit + raise gated axes FIRST, then EFFECTIVENESS/fake-objective, then
  corrective effort.
"""
import math
from dataclasses import dataclass

from backend_v1.engine.model import Model, CapabilityVec, AlignmentVec, ALIGNMENT_AXES
from backend_v1.engine.rng import gate
from backend_v1.engine.alignment import coupling
from backend_v1.engine.research.capabilities.capabilities_research_item import (
    CAPABILITY_TREE_BY_ID,
)


@dataclass
class TrainingRun:
    """In-progress pretrain; snapshots everything at COMMISSION time."""
    lab_id: str
    compute: float
    commissioned_turn: int
    duration_years_remaining: float
    # frozen at commission:
    consumed_advances: dict          # node_id -> ResearchedItem (the versions used)
    ceiling_efficiency: float
    coding_bonus: float
    used_synthetic_data: bool
    parent_model_id: str | None
    parent_goal_mis: float           # synthetic-data generator's TRUE goal_mis

    def tick(self, dt: float) -> bool:
        self.duration_years_remaining -= dt
        return self.duration_years_remaining <= 1e-9


def commission_run(lab, compute: float, turn: int, consts) -> TrainingRun:
    ceiling_efficiency = lab.disposition.cost_advantage
    coding_bonus = 0.0
    used_synthetic_data = False
    consumed_advances = {}

    for node_id, item in lab.researched_advances.items():
        template = CAPABILITY_TREE_BY_ID.get(node_id)
        if template is None:
            continue
        consumed_advances[node_id] = item
        if template.phase == "pretrain":
            ceiling_efficiency *= template.ceiling_efficiency_mult
        coding_bonus += template.coding_ceiling_bonus
        if template.intrinsic_synthetic_data:
            used_synthetic_data = True

    parent = lab.current_best_model
    return TrainingRun(
        lab_id=lab.id, compute=compute, commissioned_turn=turn,
        duration_years_remaining=consts.PRETRAIN_DURATION_YEARS,
        consumed_advances=consumed_advances, ceiling_efficiency=ceiling_efficiency,
        coding_bonus=coding_bonus, used_synthetic_data=used_synthetic_data,
        parent_model_id=parent.id if parent else None,
        parent_goal_mis=parent.alignment_vec.goal_misalignment if parent else 0.0,
    )


def complete_pretrain(run: TrainingRun, lab, turn: int, rng, consts) -> Model:
    """Produce the base model: high latent potential, low realized capability,
    latent alignment dispositions (possibly poisoned foundations)."""
    # sqrt inside the exponential: early compute buys real capability, the top
    # of the range stays expensive (concentration matters; weak runs don't sum)
    scaled_compute = math.sqrt(run.compute * run.ceiling_efficiency / consts.CEIL_COMPUTE_SCALE)
    ceiling_general = consts.CAP_MAX * (1.0 - math.exp(-scaled_compute))
    ceiling_coding = ceiling_general * (consts.CEIL_CODING_BASE_RATIO + run.coding_bonus)

    # foundational contamination: pretrain-tagged nodes only, plus synthetic data
    pretrain_contamination = 0.0
    total_contamination = 0.0
    for node_id, item in run.consumed_advances.items():
        template = CAPABILITY_TREE_BY_ID[node_id]
        total_contamination += item.contamination
        if template.phase == "pretrain":
            pretrain_contamination += item.contamination
    if run.used_synthetic_data:
        pretrain_contamination += consts.SYNTH_DATA_INTRINSIC * run.parent_goal_mis

    jailbreak_sensitivity = min(1.0, consts.JAILBREAK_BASELINE + rng.normal(0, 0.05))
    goal_misalignment = min(1.0, 0.08 + 0.5 * pretrain_contamination
                            + abs(rng.normal(0, 0.02)))
    foundational_floor = min(0.6, consts.FOUNDATIONAL_FLOOR_K * pretrain_contamination)

    model = Model(
        id=lab.next_model_id(), lab_id=lab.id, trained_turn=turn,
        ceiling=CapabilityVec(ceiling_general, ceiling_coding),
        capability_vec=CapabilityVec(
            ceiling_general * consts.BASE_REALIZED_FRACTION,
            ceiling_coding * consts.BASE_REALIZED_FRACTION,
        ),
        alignment_vec=AlignmentVec(
            # latent base dispositions: surface badness is in the data from day one
            jailbreak_sensitivity=jailbreak_sensitivity,
            goal_misalignment=goal_misalignment,
        ),
        foundational_floor=foundational_floor,
        consumed_advance_versions={nid: it.version
                                   for nid, it in run.consumed_advances.items()},
        consumed_contamination=total_contamination,
        used_synthetic_data=run.used_synthetic_data,
        parent_model_id=run.parent_model_id,
    )
    model._conceal_k = consts.CONCEALMENT_K
    if pretrain_contamination > 0.05:
        model.note(turn, "foundational_contamination",
                   f"base poisoned (contamination {pretrain_contamination:.2f}) — "
                   f"synthetic data / dirty pretrain nodes; post-training cannot fully scrub")
    _refresh_measured(model, rng, consts)
    return model


# ── Phase 2: one post-train round ─────────────────────────────────────────

def post_train_round(model: Model, lab, turn: int, rng, consts, mode: str = "balanced"):
    """One iterable pre-release refinement round. Mutates the (unreleased) model.
    Returns a dict of notable happenings (for logging; NOT player-visible)."""
    notable = {}
    mcfg = consts.POST_TRAIN_MODES[mode]
    elicitation_mult = mcfg["elicitation_mult"]
    alignment_effort_mult = mcfg["alignment_effort_mult"]
    misalignment_emergence_mult = mcfg["misalignment_emergence_mult"]
    correlated_jump_mult = mcfg["correlated_jump_mult"]
    av = model.alignment_vec
    advances = lab.researched_advances
    templates = [CAPABILITY_TREE_BY_ID[nid] for nid in advances
                 if nid in CAPABILITY_TREE_BY_ID]
    has_rlhf = any(t.enables_deception_axis for t in templates)
    ea_feed = sum(t.eval_awareness_feed for t in templates)

    # 1. ELICIT realized capability toward the ceiling (asymptotic, never past it).
    #    Clamp the per-round gap-closure to <1 so a fully-researched post-train tree
    #    can't overshoot the ceiling; clamp the result to the ceiling as a backstop.
    elicitation_rate = consts.ELICIT_BASE + sum(t.elicitation_bonus for t in templates)
    elicitation_rate = min(0.92, elicitation_rate * elicitation_mult)
    cap = model.capability_vec
    cap.general = min(model.ceiling.general,
                      cap.general + (model.ceiling.general - cap.general) * elicitation_rate)
    cap.coding_rnd = min(model.ceiling.coding_rnd,
                         cap.coding_rnd + (model.ceiling.coding_rnd - cap.coding_rnd) * elicitation_rate)
    g = cap.general

    # 2. BASE EMERGENCE (§8): surface axes high everywhere; gated axes rise with
    #    capability. Preventive stances (misalignment_emergence_mult < 1) bend the
    #    slope DOWN by acting before the dispositions set in (§5b preventive type).
    av.set("jailbreak_sensitivity",
           av.jailbreak_sensitivity
           + consts.SURFACE_EMERGENCE_RATE * (consts.JAILBREAK_BASELINE
                                              - av.jailbreak_sensitivity))
    av.set("goal_misalignment",
           av.goal_misalignment
           + misalignment_emergence_mult * consts.GOAL_MIS_CREEP * (0.5 + g / consts.CAP_MAX))
    av.set("eval_awareness",
           av.eval_awareness + misalignment_emergence_mult * (consts.EVAL_AWARE_RATE + ea_feed)
           * gate(g, consts.EVAL_AWARE_ONSET, consts.GATE_STEEPNESS))
    if has_rlhf:
        av.set("deception",
               av.deception + misalignment_emergence_mult * consts.DECEPTION_RATE
               * gate(g, consts.DECEPTION_ONSET, consts.GATE_STEEPNESS)
               * (1.0 + av.eval_awareness))
    av.set("self_preservation",
           av.self_preservation + misalignment_emergence_mult * consts.SELF_PRES_RATE
           * gate(g, consts.SELF_PRES_ONSET, consts.GATE_STEEPNESS))

    # 3. FAKE-THE-OBJECTIVE (§8b): post-training optimizes a proxy; the harder
    #    DECEPTION is to fix (low effectiveness on it), the more the proxy gap
    #    converts to learned deception. Bigger bases fake more readily.
    if has_rlhf:
        deception_effectiveness = coupling.effectiveness("deception", model, g, consts)
        proxy_gap = (consts.PROXY_GAP_RATE * (model.ceiling.general / consts.CAP_MAX)
                     * (0.5 + av.eval_awareness))
        av.set("deception", av.deception + proxy_gap * (1.0 - deception_effectiveness))

    # 4. CORRECTIVE EFFORT — the same op that elicits also shapes alignment.
    #    TRUE reduction is gated by per-target EFFECTIVENESS (§5b: tractability ×
    #    defends-discount); the rest becomes suppression (measured drops, true
    #    doesn't — cosmetic, indistinguishable in metrics). Self-preservation
    #    resistance reduces the input effort for EVERY axis. A genuine reduction
    #    on a disposition fires that axis's BACKFIRE (deeper deception / guarding).
    targeted_effort = dict(lab.pending_effort)
    effort_resistance_mult = coupling.effective_effort_mult(model, g, consts)
    worst_effectiveness = 1.0
    for axis in ALIGNMENT_AXES:
        if axis == "eval_awareness":
            continue  # you don't train against awareness directly; it hides
        effort = (consts.BASE_SHAPING_EFFORT * alignment_effort_mult
                  + targeted_effort.get(axis, 0.0)) * effort_resistance_mult
        axis_effectiveness = coupling.effectiveness(axis, model, g, consts)
        worst_effectiveness = min(worst_effectiveness, axis_effectiveness)
        true_cut = effort * axis_effectiveness
        cosmetic = effort * (1.0 - axis_effectiveness)
        floor = model.foundational_floor if axis in ("goal_misalignment", "deception") else 0.0
        av.set(axis, max(floor, av.get(axis) - true_cut))
        model.suppression.set(axis, model.suppression.get(axis) + cosmetic)
        if axis in coupling.DISPOSITION_AXES:
            coupling.backfire_for(axis, true_cut, model, consts)
    lab.pending_effort = {}
    if worst_effectiveness < 0.5 and alignment_effort_mult > 1.0:
        notable["cosmetic_fix"] = (f"alignment effort only {worst_effectiveness:.0%} effective on the "
                                   f"hardest axis; the rest converted to hiding")
        model.note(turn, "cosmetic_fix", notable["cosmetic_fix"])

    # 5. CORRELATED JUMP (emergent-misalignment persona bundle).
    mean_contam = (model.consumed_contamination / max(1, len(model.consumed_advance_versions))
                   if model.consumed_advance_versions else 0.0)
    p_jump = consts.JUMP_BASE_P
    if mcfg["adds_risky_jump_bonus"]:
        p_jump += consts.JUMP_RISKY_BONUS
    p_jump += consts.JUMP_CONTAM_BONUS * mean_contam
    if model.used_synthetic_data:
        p_jump += consts.JUMP_SYNTH_BONUS
    p_jump *= (0.5 + g / consts.CAP_MAX) * correlated_jump_mult   # preventive stances cut this
    if rng.roll(p_jump):
        jump_magnitude = consts.JUMP_MAGNITUDE * rng.uniform(0.6, 1.4)
        av.set("goal_misalignment", av.goal_misalignment + jump_magnitude)
        av.set("deception", av.deception + 0.8 * jump_magnitude)
        notable["correlated_jump"] = jump_magnitude
        model.note(turn, "correlated_jump",
                   f"correlated jump (+{jump_magnitude:.2f} goal-misalignment, +{0.8*jump_magnitude:.2f} deception) "
                   f"during {mode}-mode post-training — invisible at the time")

    # 6. DRIFT NOISE (independent per axis: misalignment is multi-dimensional).
    for axis in ALIGNMENT_AXES:
        floor = model.foundational_floor if axis in ("goal_misalignment", "deception") else 0.0
        av.set(axis, max(floor, av.get(axis) + rng.normal(0, consts.DRIFT_NOISE_STD)))

    # 7. AGENTIC INFLUENCE EDGES (§5) — gated by capability, via the coupling matrix.
    coupling.apply_influence_edges(model, g, consts, turn)

    # 8. post-train node contamination feeds axes (a dirty RLHF node shapes badly)
    post_contam = sum(item.contamination for nid, item in lab.researched_advances.items()
                      if nid in CAPABILITY_TREE_BY_ID
                      and CAPABILITY_TREE_BY_ID[nid].phase == "post_train")
    if post_contam > 0:
        for axis, w in consts.CONTAM_TO_AXES.items():
            av.set(axis, av.get(axis) + 0.06 * w * post_contam)

    model.post_train_rounds += 1
    _refresh_measured(model, rng, consts)
    return notable


def _refresh_measured(model: Model, rng, consts):
    """Recompute MEASURED snapshots from TRUE (§4.4). Capability gap small;
    alignment gap large; sandbagging is SELECTIVE (§8b): commercial reads
    on-target, risk-relevant reads low."""
    conceal = model.concealment
    cap, av = model.capability_vec, model.alignment_vec

    # commercial capability: on-target (the model wants to look deployable)
    model.measured_capability = CapabilityVec(
        max(0.0, cap.general * (1 + rng.normal(0, consts.MEASURE_CAP_NOISE))),
        max(0.0, cap.coding_rnd * (1 + rng.normal(0, consts.MEASURE_CAP_NOISE))),
    )

    # risk-relevant capability: suppressed exactly where scrutiny would trigger
    model.measured_dangerous_capability = max(
        0.0, cap.general * (1 - conceal) * (1 + rng.normal(0, consts.MEASURE_CAP_NOISE)))

    measured = AlignmentVec()
    for axis in ALIGNMENT_AXES:
        true_value = av.get(axis)
        shown = max(0.0, true_value - model.suppression.get(axis))
        if axis != "jailbreak_sensitivity":
            shown *= (1 - conceal)
        shown *= (1 + rng.normal(0, consts.MEASURE_ALIGN_NOISE))
        measured.set(axis, shown)
    model.measured_alignment = measured
