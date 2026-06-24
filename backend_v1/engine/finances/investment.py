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


def _lab_is_active(lab):
    """Active = the lab is doing something the early/seed market can bet on: it has
    shipped a model, OR it has research / pretraining / a post-train model in flight.
    An inactive lab (idle, nothing in progress, never shipped) sees its seed
    investment decay toward zero (§9b: the default is growth, idleness is punished)."""
    has_shipped = len(lab.release_history) > 0
    has_work_in_progress = (len(lab.in_progress) > 0
                            or lab.training_run is not None
                            or lab.model_in_training is not None)
    return has_shipped or has_work_in_progress


def update_base_investment(lab, consts, dt):
    """Advance the lab's seed/base investment flow by one turn (§9b early investment).

    Early-stage capital bets on the field/team before any release, so every lab starts
    with a small base flow. It HOLDS at the base level while the lab is active and
    DECAYS toward zero if the lab goes idle for a few quarters. Stored on the lab so it
    is a persistent accumulator (one step per turn), not recomputed from scratch."""
    if _lab_is_active(lab):
        lab.base_investment_rate = consts.BASE_INVESTMENT_PER_YEAR
    else:
        lab.base_investment_rate *= math.exp(-consts.BASE_INVESTMENT_DECAY_PER_YEAR * dt)


def run_investment(labs, world, turn, rng, consts, dt):
    if world.total_revenue_rate > 0 and world.prev_total_revenue_rate > 0:
        single_turn_growth = (world.total_revenue_rate / world.prev_total_revenue_rate - 1) / dt
    else:
        single_turn_growth = 0.0
    # §9b: investment rewards the SLOPE between releases, not an instantaneous spike.
    # The single-turn ratio whipsaws (huge the turn a new model enters the pie, negative
    # the next), so feed the pie a SMOOTHED growth instead — this is what previously flung
    # total investment, and the cap keyed off it, up then down after every release.
    world.smoothed_revenue_growth_per_year += consts.REVENUE_GROWTH_SMOOTHING_ALPHA * (
        single_turn_growth - world.smoothed_revenue_growth_per_year)
    smoothed_revenue_growth = world.smoothed_revenue_growth_per_year

    frontier_capability = world.frontier_measured_general
    capability_fraction = frontier_capability / consts.CAP_MAX
    growth_multiplier = max(0.2, 1 + consts.INVESTMENT_GROWTH_WEIGHT * smoothed_revenue_growth)
    total_investment = (consts.INVESTMENT_MAX_PER_YEAR
                        * capability_fraction ** consts.INVESTMENT_CAP_EXP
                        * growth_multiplier)

    # advance each lab's persistent confidence momentum AND its seed investment by one
    # turn, THEN score.
    for lab in labs:
        update_investment_momentum(lab, world, turn, consts, dt)
        update_base_investment(lab, consts, dt)

    scores = {lab.id: lab_score(lab, world, consts) for lab in labs}
    scores_sum = sum(scores.values()) or 1.0

    for lab in labs:
        score_share_investment = total_investment * scores[lab.id] / scores_sum
        # the seed/base flow is ADDED on top of the score-divvied pie: it is present
        # from turn 1 (when the score-pie is still ~0) and tapers as real investment
        # takes over. It is each lab's own seed money, not a share of the pie.
        lab.investment_rate = score_share_investment + lab.base_investment_rate
        lab.cash += rng.amount_per_dt(lab.investment_rate, dt)
        lab.last_score = scores[lab.id]
