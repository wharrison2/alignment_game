"""Market cap (§9b): investment-determined, forward-looking / slope-weighted.

The persistent legible anchor, one win condition (dominance), AND the lobbying
weight (§10c regulatory capture falls out of that identity).
"""


def update_market_caps(labs, consts):
    for lab in labs:
        score = lab.last_score
        valuation = consts.MARKET_CAP_SCALE * score * max(lab.investment_rate, 1.0) \
            + 0.5 * lab.revenue_rate
        lab.market_cap += consts.MARKET_CAP_ALPHA * (valuation - lab.market_cap)
        lab.market_cap = max(1.0, lab.market_cap)


def dominant_lab(labs):
    return max(labs, key=lambda l: l.market_cap)
