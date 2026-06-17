"""Revenue pie (§9b): rewards the LEVEL. Keys off MEASURED capability.

Total market = f(best measured model in the WORLD); divvied across EVERY
released model by measured capability — old models keep a trickle, a new
frontier release cannibalizes your own back catalog, no explicit decay rule.
A sandbagging model underearns (hidden capability is unmonetized).
"""
from backend_v1.engine.research.capabilities.capabilities_research_item import (
    CAPABILITY_TREE_BY_ID,
)


def run_revenue(labs, world, rng, consts, dt):
    released = [(lab, m) for lab in labs for m in lab.release_history]
    if not released:
        for lab in labs:
            lab.revenue_rate = 0.0
        world.prev_total_revenue_rate = world.total_revenue_rate
        world.total_revenue_rate = 0.0
        return

    def monetized_general(model):
        # commercial reads on-target, but the risk-suppressed slice is unmonetized
        return max(0.05, model.measured_capability.general
                   * (1 - consts.SANDBAG_REVENUE_PENALTY * model.concealment))

    best = max(monetized_general(m) for _, m in released)
    world.frontier_measured_general = max(
        m.measured_capability.general for _, m in released)
    market = (consts.REVENUE_MAX_PER_YEAR
              * (best / consts.CAP_MAX) ** consts.REVENUE_CAP_EXP
              * max(0.0, 1 + rng.normal(0, consts.REVENUE_NOISE_STD)))

    weights = []
    for lab, m in released:
        w = monetized_general(m) ** consts.REVENUE_SHARE_EXP
        for nid in lab.researched_advances:
            t = CAPABILITY_TREE_BY_ID.get(nid)
            if t is not None and t.revenue_multiplier > 1:
                w *= t.revenue_multiplier
        weights.append(w)
    total_w = sum(weights) or 1.0

    for lab in labs:
        lab.revenue_rate = 0.0
    for (lab, m), w in zip(released, weights):
        lab.revenue_rate += market * w / total_w
    for lab in labs:
        lab.cash += rng.amount_per_dt(lab.revenue_rate, dt)
    world.prev_total_revenue_rate = world.total_revenue_rate
    world.total_revenue_rate = sum(lab.revenue_rate for lab in labs)
