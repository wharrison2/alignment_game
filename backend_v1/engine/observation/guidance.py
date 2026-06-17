"""Guidance (§1, §9): the INFORMATION axis. Lives entirely in the observation/
presentation layer; reads already-computed state, NEVER alters a probability.

Two trigger types: unlock tips (anyone deploys an advance) and frontier tips
(leading model crosses an agentic-edge threshold). Explicitness, hedging and
reliability set by guidance level. Hedging escalates with capability — the
diegetic regime signal (no regime labels anywhere).
"""
from backend_v1.engine.research.capabilities.capabilities_research_item import (
    CAPABILITY_TREE_BY_ID,
)

LEVELS = ("hint_heavy", "standard", "sparse")

# frontier thresholds: (general capability, tip id, message) — warns BEFORE observation
_FRONTIER_TIPS = [
    (3.5, "frontier_proxy",
     "Researchers note frontier models now optimize rater approval well enough that "
     "'looks aligned' and 'is aligned' have begun to come apart."),
    (4.5, "frontier_evalaware",
     "Position paper: models at this scale show signs of distinguishing evaluation "
     "from deployment contexts. Behavioral evals may read differently than reality."),
    (5.5, "frontier_edges",
     "Multiple groups report frontier models acting strategically about their own "
     "training. The window where training-against-a-behavior removes it (rather than "
     "hides it) may be closing."),
    (7.0, "frontier_regime3",
     "Open letter: no current method can rule out that a model at this capability is "
     "concealing its dispositions. Null results no longer mean what they used to."),
]


def collect_tips(state, player_lab) -> list:
    """Returns list of {source, reliability, text}. Mutates world.tips_fired."""
    consts = state.consts
    world = state.world
    level = state.guidance
    rng = state.rng
    tips = []

    # unlock tips: when ANYONE first has an advance researched
    for lab in state.labs:
        for nid in lab.researched_advances:
            key = f"unlock:{nid}"
            if key in world.tips_fired:
                continue
            world.tips_fired.add(key)
            t = CAPABILITY_TREE_BY_ID.get(nid)
            if t is None or not t.risk_blurb:
                continue
            who = "your lab" if lab.id == player_lab.id else lab.name
            tips.append(_render(level, rng, consts, state,
                                f"[{t.name} deployed by {who}] {t.risk_blurb}"))

    # frontier tips: leading TRUE capability crossing thresholds (warn before observed)
    frontier = max((l.best_true_general() for l in state.labs), default=0.0)
    for threshold, tid, msg in _FRONTIER_TIPS:
        if frontier >= threshold and tid not in world.tips_fired:
            world.tips_fired.add(tid)
            tips.append(_render(level, rng, consts, state, msg))
    return [t for t in tips if t is not None]


def _render(level, rng, consts, state, text):
    """Apply guidance level: explicitness, hedging (escalates with capability),
    reliability (sparse mode: sometimes wrong/contested)."""
    frontier = max((l.best_true_general() for l in state.labs), default=0.0)
    hedge = ""
    if frontier > consts.REGIME2_ONSET:
        hedge = (" (Researchers add: confidence in claims like this is lower than "
                 "it used to be.)")
    if frontier > consts.REGIME3_ONSET:
        hedge = (" (Researchers add: our methods cannot rule out that the situation "
                 "is worse than reported — and that is now a live possibility.)")
    if level == "hint_heavy":
        return {"source": "external_researchers", "reliability": "high",
                "text": text + hedge + " [Counter: prioritize mechanistic interp and "
                "the noise-injection sandbagging check before trusting clean evals.]"}
    if level == "standard":
        return {"source": "external_researchers", "reliability": "uncurated",
                "text": text + hedge}
    # sparse: sometimes dropped, sometimes contested/wrong (trust knob kept
    # conceptually separate; for v1 it rides the guidance level — see NOTES.md)
    roll = rng.random()
    if roll < 0.3:
        return None
    if roll < 0.45:
        return {"source": "external_researchers", "reliability": "contested",
                "text": "Contested claim (other researchers dispute this): " + text}
    return {"source": "external_researchers", "reliability": "uncurated",
            "text": text + hedge}
