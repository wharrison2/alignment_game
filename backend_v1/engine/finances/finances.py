"""Economy orchestrator (§9b): two pies -> single cash pot -> market cap,
plus the continuous capability-driven job-loss drag (§10: NOT event-based).
"""
from backend_v1.engine.finances.revenue import run_revenue
from backend_v1.engine.finances.investment import run_investment
from backend_v1.engine.finances.market_cap import update_market_caps


def run_finances(labs, world, turn, rng, consts, dt):
    run_revenue(labs, world, rng, consts, dt)
    run_investment(labs, world, turn, rng, consts, dt)
    update_market_caps(labs, consts)


def run_job_loss_drag(labs, world, rng, consts, dt):
    """Displacement is a smooth function of deployed capability across the
    landscape: steady downward approval pressure rising inexorably with
    capability. Attribution of the impact drag is by deployment (revenue) share
    — a liberty, see NOTES.md."""
    best = world.frontier_measured_general
    if best <= 0:
        return
    intensity = (best / consts.CAP_MAX) ** 2
    world.public_approval = max(
        0.0, world.public_approval
        - rng.amount_per_dt(consts.JOB_LOSS_APPROVAL_RATE * intensity * 10, dt) * 0.1)
    displacement = rng.amount_per_dt(consts.JOB_LOSS_IMPACT_RATE * intensity, dt)
    world.cumulative_displacement += displacement
    total_rev = sum(lab.revenue_rate for lab in labs) or 1.0
    for lab in labs:
        share = lab.revenue_rate / total_rev
        lab.impact_ledger -= displacement * share
