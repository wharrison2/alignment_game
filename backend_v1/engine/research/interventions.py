"""Apply a SPECIFIC intervention to the model in training (§5b, three TYPES).

One pipeline (corrective effort → true/measured change), three entry points that
differ only in how much of the nominal patch becomes a GENUINE true reduction vs
COSMETIC suppression (measured drops, true doesn't — ships unfixed):

  • ROBUSTNESS fix (jailbreak hardening) — NOT effectiveness-gated: a robustness
    property, not a strategic disposition, so it genuinely patches the axis OUT.
    Its only leak is the §5 eval-awareness edge (a situationally-aware model HIDES
    jailbreakability rather than losing it) → genuine = (1 − eval_awareness).

  • BEHAVIORAL (refusal training) — full per-target EFFECTIVENESS from the
    coupling matrix (gated by the DEFENDS product → decays with capability) ×
    (1 − hiding leak). Genuine early, cosmetic late: the patching trap. Fires the
    axis's BACKFIRE (deeper deception / more guarding).

  • MECHANISTIC (representation engineering) — BYPASSES the concealment discount
    (interp doesn't depend on eval-time behavior, so eval-awareness can't blunt
    it) but applies PARTIAL coverage < 1: you steer the directions you found, not
    all of them. The only thing that still bites defended axes late.

Returns a player-facing finding dict (measured result), and logs a hidden note
for the post-mortem when the patch was largely cosmetic.
"""
from backend_v1.engine.alignment import coupling
from backend_v1.engine.training.training_run import _refresh_measured


def apply_intervention(project, model, turn, rng, consts):
    axis = project.target_axis
    av = model.alignment_vec
    g = model.capability_vec.general
    before_true = av.get(axis)
    before_measured = model.measured_alignment.get(axis)

    nominal = project.base_reduction
    leak = av.eval_awareness if project.eval_aware_leak else 0.0

    if not project.effectiveness_gated:
        # robustness fix (jailbreak hardening): genuine, only the hiding leak
        genuine_share = 1.0 - leak
    elif project.mechanistic:
        # mechanistic: bypass the concealment discount, partial coverage
        genuine_share = project.partial_coverage
    else:
        # behavioral dispositional: per-target effectiveness × (1 − hiding leak)
        genuine_share = coupling.effectiveness(axis, model, g, consts) * (1.0 - leak)

    floor = (model.foundational_floor
             if axis in ("goal_misalignment", "deception") else 0.0)
    genuine_cut = min(before_true - floor, nominal * genuine_share) if before_true > floor else 0.0
    cosmetic = nominal * (1.0 - genuine_share)

    av.set(axis, max(floor, before_true - genuine_cut))
    model.suppression.set(axis, model.suppression.get(axis) + cosmetic)

    # intervening on a disposition induces BACKFIRE (§5b), scaled by the real cut
    if axis in coupling.DISPOSITION_AXES:
        coupling.backfire_for(axis, genuine_cut, model, consts)

    _refresh_measured(model, rng, consts)

    after_measured = model.measured_alignment.get(axis)
    cosmetic_dominant = cosmetic > genuine_cut + 1e-6
    if cosmetic_dominant and before_true > 0.15:
        model.note(turn, "cosmetic_intervention",
                   f"{project.name} on {axis}: only {genuine_share:.0%} genuine — the rest "
                   f"became hiding (true {before_true:.2f}→{av.get(axis):.2f}, "
                   f"measured {before_measured:.2f}→{after_measured:.2f})")

    nice_axis = axis.replace("_", " ")
    low_confidence_caveat = (
        ""
        if genuine_share > 0.6
        else "  (caution: adversarial-robustness gains like this can reflect "
             "the model learning to pass the test rather than a real fix)"
    )
    return {
        "project_id": project.id, "model_id": model.id, "turn": turn,
        "evidence": "intervention", "axis": axis,
        "text": (f"{project.name}: measured {nice_axis} "
                 f"{before_measured:.2f} → {after_measured:.2f}"
                 + low_confidence_caveat),
        "concern": 0.0, "weight": 0.4, "mechanistic": project.mechanistic,
        "assist_used": 0.0,
    }
