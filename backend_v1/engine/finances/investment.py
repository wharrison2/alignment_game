"""Investment pie (§9b): rewards the SLOPE. The financial treadmill.

Growth is measured BETWEEN releases. Investor confidence does NOT collapse the
turn after a release: a release sets a confidence level (how far it beat the
risen bar), that confidence keeps GROWING through a grace window of a few
quarters, and ONLY after the grace expires does continued waiting erode it.
The bar rises with the frontier AND with how long you held (expectations climb
with time). Investment is a FLOW added to the single cash pot each turn.

Momentum is a PERSISTENT per-lab accumulator (`lab.investment_momentum`),
evolved one step per turn — NOT recomputed from scratch off "quarters since the
last release." The earlier stateless version keyed the grace ramp off
`years_since`, which reset to zero at every release: a release that BEAT its bar
still threw away the grace momentum it had accrued, so the market cap dropped at
each release (the "slanted staircase"). Carrying momentum across releases makes
a beat continuous (no drop) and reserves the cliff for a MISS or for sitting
past the grace window — exactly the §9b intent ("default state is growth; the
cliff is the exception").
"""
import math


def _release_growth_term(lab, world, consts, dt):
    """How well the LAST release beat its risen bar, in [-1, 1.5]. Release-to-
    release capability growth judged against a target that rises with the frontier
    and with how long this lab held before shipping. 0 on a lab's first release."""
    if lab.last_release_turn is None or lab.prev_release_measured_general <= 0:
        return 0.0      # first release: neutral, no penalty
    frontier = max(world.frontier_measured_general, 0.5)
    held = max(dt, (lab.last_release_turn - (lab.prev_release_turn or 0)) * dt)
    growth_per_year = (lab.last_release_measured_general
                       - lab.prev_release_measured_general) / held
    target = (consts.RISING_TARGET_BASE
              + consts.RISING_TARGET_FRONTIER_K * frontier
              + consts.RISING_TARGET_TIME_K * held)
    # beating the bar is rewarded; MISSING it falls precipitously (down to -1)
    return max(-1.0, min(1.5, (growth_per_year - target) / max(0.05, target)))


def update_investment_momentum(lab, world, turn, consts, dt):
    """Advance the persistent investor-confidence momentum by ONE turn.

    - On the turn of a release: the release injects a confidence level from how it
      beat its bar. A BEAT (growth_term >= 0) never lowers momentum — it carries
      the accrued slope forward (continuity, the staircase fix). A MISS resets
      momentum down to that (sub-1) confidence — the precipitous cliff (§9b).
    - Within the grace window with no release: momentum keeps GROWING at a baseline
      rate (the market stays patient and assumes a big release is coming).
    - Past the grace window with no release: waiting finally bites and momentum
      decays.
    """
    if lab.last_release_turn is None:
        return                      # nothing shipped yet; momentum stays at 0

    released_this_turn = (lab.last_release_turn == turn)
    if released_this_turn:
        growth_term = _release_growth_term(lab, world, consts, dt)
        confidence = max(0.0, 1.0 + consts.SCORE_MOMENTUM_GROWTH * growth_term)
        if growth_term >= 0.0:
            lab.investment_momentum = max(confidence, lab.investment_momentum)
        else:
            lab.investment_momentum = confidence
        return

    years_since = (turn - lab.last_release_turn) * dt
    if years_since <= consts.SCORE_GRACE_YEARS:
        grace_growth_per_year = consts.SCORE_GRACE_GROWTH / consts.SCORE_GRACE_YEARS
        lab.investment_momentum += grace_growth_per_year * dt
    else:
        lab.investment_momentum *= math.exp(-consts.SCORE_RELEASE_DECAY * dt)


def lab_score(lab, world, consts):
    best = lab.last_release_measured_general
    rev_share = (lab.revenue_rate / world.total_revenue_rate
                 if world.total_revenue_rate > 0 else 0.0)
    score = (consts.SCORE_W_BEST * best / consts.CAP_MAX
             + consts.SCORE_W_REVSHARE * rev_share
             + consts.SCORE_W_GROWTH * lab.investment_momentum)
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

    # advance each lab's persistent confidence momentum by one turn, THEN score.
    for lab in labs:
        update_investment_momentum(lab, world, turn, consts, dt)

    scores = {lab.id: lab_score(lab, world, consts) for lab in labs}
    scores_sum = sum(scores.values()) or 1.0

    for lab in labs:
        lab.investment_rate = total_investment * scores[lab.id] / scores_sum
        lab.cash += rng.amount_per_dt(lab.investment_rate, dt)
        lab.last_score = scores[lab.id]
