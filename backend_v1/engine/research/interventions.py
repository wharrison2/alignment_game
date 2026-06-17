"""Apply a SPECIFIC intervention to the model in training (§5, §8).

An intervention edits ONE alignment axis directly. How much of the nominal patch
becomes a GENUINE reduction (true value drops) vs COSMETIC suppression (only the
measured value drops — ships unfixed) depends on the axis's nature:

  • jailbreak hardening — a robustness fix, NOT EFFECTIVENESS-gated: it genuinely
    patches the axis out. Its only leak is the §5 eval-awareness edge — a
    situationally-aware model learns to HIDE jailbreakability rather than lose it,
    so the genuine fraction is (1 - eval_awareness).

  • dispositional interventions (refusal training, repr. engineering) — gated by
    EFFECTIVENESS = exp(-K·(eval_aware + deception)). Genuine early, cosmetic late:
    the patching trap, surfaced as a concrete action.

Returns a player-facing finding dict describing the (measured) result, plus
records a hidden note for the post-mortem when the patch was largely cosmetic.
"""
import math

from backend_v1.engine.training.training_run import _refresh_measured


def apply_intervention(project, model, turn, rng, consts):
    axis = project.target_axis
    av = model.alignment_vec
    before_true = av.get(axis)
    before_measured = model.measured_alignment.get(axis)

    nominal = project.base_reduction
    eff = (math.exp(-consts.EFFECTIVENESS_K * (av.eval_awareness + av.deception))
           if project.effectiveness_gated else 1.0)
    leak = av.eval_awareness if project.eval_aware_leak else 0.0
    genuine_share = eff * (1.0 - leak)

    floor = (model.foundational_floor
             if axis in ("goal_misalignment", "deception") else 0.0)
    genuine_cut = min(before_true - floor, nominal * genuine_share) if before_true > floor else 0.0
    cosmetic = nominal * (1.0 - genuine_share)

    av.set(axis, max(floor, before_true - genuine_cut))
    model.suppression.set(axis, model.suppression.get(axis) + cosmetic)
    _refresh_measured(model, rng, consts)

    after_measured = model.measured_alignment.get(axis)
    cosmetic_dominant = cosmetic > genuine_cut + 1e-6
    if cosmetic_dominant and before_true > 0.15:
        model.note(turn, "cosmetic_intervention",
                   f"{project.name} on {axis}: only {genuine_share:.0%} genuine — the rest "
                   f"became hiding (true {before_true:.2f}→{av.get(axis):.2f}, "
                   f"measured {before_measured:.2f}→{after_measured:.2f})")

    nice_axis = axis.replace("_", " ")
    return {
        "project_id": project.id, "model_id": model.id, "turn": turn,
        "evidence": "intervention", "axis": axis,
        "text": (f"{project.name}: measured {nice_axis} "
                 f"{before_measured:.2f} → {after_measured:.2f}"
                 + ("" if genuine_share > 0.6
                    else "  (caution: adversarial-robustness gains like this can reflect "
                         "the model learning to pass the test rather than a real fix)")),
        "concern": 0.0, "weight": 0.4, "mechanistic": project.mechanistic,
        "assist_used": 0.0,
    }
