"""Investment pie (§9b): rewards the SLOPE. The financial treadmill.

Growth is measured BETWEEN releases. Investor confidence does NOT collapse the
turn after a release: a release sets a confidence level (how far it beat the
risen bar), that confidence keeps GROWING through a grace window of a few
quarters, and ONLY after the grace expires does continued waiting erode it.
The bar rises with the frontier AND with how long you held (expectations climb
with time). Investment is a FLOW added to the single cash pot each turn.
"""
import math


def lab_score(lab, world, turn, consts, dt):
    frontier = max(world.frontier_measured_general, 0.5)
    best = lab.last_release_measured_general
    rev_share = (lab.revenue_rate / world.total_revenue_rate
                 if world.total_revenue_rate > 0 else 0.0)

    years_since = ((turn - lab.last_release_turn) * dt
                   if lab.last_release_turn is not None else 999)

    # How well did the LAST release do? Release-to-release growth judged against a
    # target that rises with the frontier and with how long this lab held before
    # shipping. Computed at release; static between releases.
    if lab.last_release_turn is not None and lab.prev_release_measured_general > 0:
        held = max(dt, (lab.last_release_turn - (lab.prev_release_turn or 0)) * dt)

        growth_per_year = (lab.last_release_measured_general - lab.prev_release_measured_general) / held
        target = (consts.RISING_TARGET_BASE
                  + consts.RISING_TARGET_FRONTIER_K * frontier
                  + consts.RISING_TARGET_TIME_K * held)

        # beating the bar is rewarded; MISSING it falls precipitously (down to -1)
        growth_term = max(-1.0, min(1.5, (growth_per_year - target) / max(0.05, target)))
    else:
        growth_term = 0.0      # first release: neutral, no penalty

    # Investor confidence from the last release. >1 when you met/beat expectation
    # (the common case — growth is expected most of the time), <1 when you missed.
    confidence = max(0.0, 1.0 + consts.SCORE_MOMENTUM_GROWTH * growth_term)

    if years_since <= consts.SCORE_GRACE_YEARS:
        # grace: momentum keeps building for ~3-4 quarters regardless
        ramp = 1.0 + consts.SCORE_GRACE_GROWTH * (years_since / consts.SCORE_GRACE_YEARS)
        momentum = confidence * ramp
    else:
        # past grace: NOW waiting bites — decay from the peak the grace reached
        over = years_since - consts.SCORE_GRACE_YEARS
        peak = confidence * (1.0 + consts.SCORE_GRACE_GROWTH)
        momentum = peak * math.exp(-consts.SCORE_RELEASE_DECAY * over)

    score = (consts.SCORE_W_BEST * best / consts.CAP_MAX
             + consts.SCORE_W_REVSHARE * rev_share
             + consts.SCORE_W_GROWTH * momentum)
    return max(0.0, score)


def run_investment(labs, world, turn, rng, consts, dt):
    if world.total_revenue_rate > 0 and world.prev_total_revenue_rate > 0:
        rev_growth = (world.total_revenue_rate / world.prev_total_revenue_rate - 1) / dt
    else:
        rev_growth = 0.0

    frontier_capability = world.frontier_measured_general
    capability_fraction = frontier_capability / consts.CAP_MAX
    growth_multiplier = max(0.2, 1 + consts.INVESTMENT_GROWTH_WEIGHT * rev_growth)
    total_investment = (consts.INVESTMENT_MAX_PER_YEAR
                        * capability_fraction ** consts.INVESTMENT_CAP_EXP
                        * growth_multiplier)

    scores = {lab.id: lab_score(lab, world, turn, consts, dt) for lab in labs}
    scores_sum = sum(scores.values()) or 1.0

    for lab in labs:
        lab.investment_rate = total_investment * scores[lab.id] / scores_sum
        lab.cash += rng.amount_per_dt(lab.investment_rate, dt)
        lab.last_score = scores[lab.id]
