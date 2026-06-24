"""Market cap (§9b): investment-determined, forward-looking / slope-weighted.

The persistent legible anchor, one win condition (dominance), AND the lobbying
weight (§10c regulatory capture falls out of that identity).
"""


def update_market_caps(labs, consts):
    for lab in labs:
        score = lab.last_score

        # §9b: the cap is forward-looking / slope-weighted. The SLOPE already lives in
        # the lab score (best model + revenue share + persistent investor-confidence
        # momentum). The SIZE anchor is a SMOOTHED investment flow, not the raw per-turn
        # investment_rate: that raw rate is a share of a per-turn-noisy pie and spikes on
        # a release turn then craters the next, which used to make the cap decline right
        # after a release. Smoothing the anchor lets the cap track the steadily-rising
        # score, so a healthy release keeps the staircase climbing (FIX_ITEMS Fix 1).
        lab.smoothed_investment_rate += consts.INVESTMENT_ANCHOR_ALPHA * (
            lab.investment_rate - lab.smoothed_investment_rate)
        investment_anchor = max(lab.smoothed_investment_rate, 1.0)

        target_valuation = consts.MARKET_CAP_SCALE * score * investment_anchor + 0.5 * lab.revenue_rate
        lab.market_cap += consts.MARKET_CAP_ALPHA * (target_valuation - lab.market_cap)
        lab.market_cap = max(1.0, lab.market_cap)


def dominant_lab(labs):
    return max(labs, key=lambda l: l.market_cap)
