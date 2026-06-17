"""Regulation engine (§10c): WTR dynamics, enactment (WTR + cap-weighted lobby,
model b), per-lab compliance ∝ disposition, policy effects, gov audits.

Government sees roughly MEASURED stats with extra noise — fooled by
eval-awareness like everyone else, complacent right when danger is highest.
"""
from backend_v1.engine.governance.policies import POLICY_DEFS
from backend_v1.engine.governance.lobbying import lobby_term
from backend_v1.engine.world import PolicyState
from backend_v1.engine.events.event import FiredEvent
from backend_v1.engine.events.effects import apply_effects
from types import SimpleNamespace


def update_wtr(world, rng, consts, dt):
    if world.public_approval < 55:
        world.wtr += rng.amount_per_dt(
            consts.WTR_FROM_LOW_APPROVAL * (55 - world.public_approval), dt)
    elif world.public_approval > 70:
        world.wtr -= rng.amount_per_dt(consts.WTR_DECAY_GOOD_TIMES, dt)
    world.wtr = max(0.0, min(100.0, world.wtr))


def update_policies(labs, world, rng, consts, turn):
    """Enact/repeal each policy when score = WTR + lobby crosses its threshold."""
    changes = []
    for pdef in POLICY_DEFS:
        st = world.policies.setdefault(pdef.id, PolicyState())
        if pdef.prerequisite is not None:
            st.prerequisite_met = bool(getattr(world, pdef.prerequisite))
            if not st.prerequisite_met:
                continue
        score = world.wtr + lobby_term(labs, pdef.id, consts.LOBBY_WEIGHT)
        threshold = consts.POLICY_THRESHOLDS[pdef.id]
        if not st.active and score >= threshold:
            st.active, st.enacted_turn = True, turn
            changes.append(("enacted", pdef.id))
        elif st.active and score < threshold - 12:   # hysteresis on repeal
            st.active = False
            changes.append(("repealed", pdef.id))
    return changes


def government_audit(model, rng, consts) -> bool:
    """Public-info-only behavioral eval: passes unless MEASURED misalignment
    looks bad. A deceptive model sails through (theater)."""
    noisy = (model.measured_misalignment_composite()
             + rng.normal(0, consts.GOV_EVAL_NOISE))
    return noisy < consts.AUDIT_MEASURED_BAR


def audit_theater_effect(world, consts):
    """A clean bill of health gives the public false comfort -> WTR falls."""
    world.wtr = max(0.0, world.wtr - 1.5)


def interp_mandate_check(lab, model, consts) -> bool:
    """Release requires recent mechanistic evidence below the bar. Hard to fake."""
    mech = [f for f in lab.findings
            if f.get("mechanistic") and f.get("model_id") == model.id]
    if not mech:
        return False   # no interp evidence at all -> blocked
    worst = max(f["concern"] for f in mech)
    return worst < consts.INTERP_MANDATE_BAR


def enforcement_phase(labs, world, flags, rng, consts, dt, turn):
    """Defection detection: each active, defectable policy; a non-compliant lab
    risks getting caught. Regulation binds the compliant more than the reckless."""
    fired = []
    sb = SimpleNamespace(labs=labs, labs_by_id={l.id: l for l in labs},
                         world=world, flags=flags, rng=rng, consts=consts,
                         dt=dt, turn=turn)
    for pdef in POLICY_DEFS:
        st = world.policies.get(pdef.id)
        if st is None or not st.active or not pdef.defectable:
            continue
        for lab in labs:
            if lab.safe_harbor_signed:
                continue
            defecting = rng.random() > lab.disposition.compliance
            if defecting and getattr(lab, f"_defected_{pdef.id}", False) is False:
                setattr(lab, f"_defected_{pdef.id}", True)
            if getattr(lab, f"_defected_{pdef.id}", False) and \
                    rng.roll_rate(consts.ENFORCEMENT_CATCH_RATE, dt):
                setattr(lab, f"_defected_{pdef.id}", False)
                ev = FiredEvent(
                    "defection_caught", "societal", "ordinary", turn, lab.id, None,
                    0.3, -5.0,
                    f"{lab.name} caught violating {pdef.name}; fined.",
                    f"defection from {pdef.id} caught (compliance "
                    f"{lab.disposition.compliance:.2f})",
                    effects=[("modify_cash", {"amount": -consts.DEFECTION_PENALTY}),
                             ("add_impact", {"amount": -5.0}),
                             ("modify_approval",
                              {"amount": -consts.DEFECTION_APPROVAL_HIT}),
                             ("modify_wtr", {"amount": 2.0})])
                apply_effects(sb, ev)
                fired.append(ev)
    return fired
