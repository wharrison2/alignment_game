"""Market cap (§9b): investment-determined, forward-looking / slope-weighted.

The persistent legible anchor, one win condition (dominance), AND the lobbying
weight (§10c regulatory capture falls out of that identity).
"""


def update_market_caps(labs, consts):
    for lab in labs:
        score = lab.last_score
        investment_anchor = max(lab.investment_rate, 1.0)
        target_valuation = consts.MARKET_CAP_SCALE * score * investment_anchor + 0.5 * lab.revenue_rate
        lab.market_cap += consts.MARKET_CAP_ALPHA * (target_valuation - lab.market_cap)
        lab.market_cap = max(1.0, lab.market_cap)


def dominant_lab(labs):
    return max(labs, key=lambda l: l.market_cap)
