"""Litigation (§10c) — the post-passage battleground that mirrors pre-passage
lobbying. An ACTIVE policy can be challenged in court; litigation weight is
money/effort spent (NOT market-cap voting weight), so a smaller lab can punch
above its size.

    net balance = challenge_effort vs (defense_effort + DOJ_effort + const_floor)
    MARGIN = challenge_effort − (defense_effort + DOJ_effort + const_floor)

DOJ_effort ∝ WTR (political will defends — a patient challenger can wait out the
will). Constitutionality is anchored to policy TYPE: precedented types are robust,
novel/aggressive ones (interp mandate, compute cap) are fragile — the thesis twist
that the EFFECTIVE policies are also the easiest to strike.

Contributions are applied as labs act (see apply_litigation_action, called from the
action phase); resolution happens in the governance phase (resolve_litigation).
Appeals / stays / the court hierarchy live in appeals.py.
"""
import math
from dataclasses import dataclass, field

from backend_v1.engine.governance.policies import POLICY_DEFS_BY_ID
from backend_v1.engine.governance import gov_news
from types import SimpleNamespace


@dataclass
class LitigationCase:
    policy_id: str
    court_level: str = "trial"          # trial -> circuit -> scotus
    opened_turn: int | None = None      # first turn a challenge was funded
    challenge_effort: float = 0.0
    defense_effort: float = 0.0
    last_margin: float | None = None    # public (both sides see it)
    status: str = "open"                # open -> appealed -> closed
    injunction_turns_left: int = 0      # prelim injunction freeze (temporary)
    stay_active: bool = False           # stay pending appeal freezes the status quo
    appeal_by: str | None = None        # "challenge" | "defense" (the appellant)
    fresh_challenge: float = 0.0        # challenge effort added THIS turn (for backlash)
    fresh_challenger: str | None = None  # lab id of the loudest fresh challenger
    used_amicus: set = field(default_factory=set)   # lab ids (cap once/case)
    used_join: set = field(default_factory=set)
    challengers: set = field(default_factory=set)
    defenders: set = field(default_factory=set)
    history: list = field(default_factory=list)

    def note(self, turn, text):
        self.history.append({"turn": turn, "text": text})


def get_case(world, policy_id) -> LitigationCase | None:
    st = world.policies.get(policy_id)
    return st.litigation if st is not None else None


def _ensure_case(world, policy_id) -> LitigationCase:
    st = world.policies[policy_id]
    if st.litigation is None:
        st.litigation = LitigationCase(policy_id=policy_id)
    return st.litigation


def apply_litigation_action(world, lab, policy_id, spec, consts):
    """Apply ONE lab's litigation move this turn (deducts cash, accrues effort).
    Returns (ok, message). Only valid against an ACTIVE policy the lab has standing
    to contest. spec = {side, tier, spend}."""
    st = world.policies.get(policy_id)
    if st is None or not st.active:
        return False, f"{policy_id}: not an active policy to litigate"
    pdef = POLICY_DEFS_BY_ID[policy_id]
    side = spec.get("side", "challenge")
    if side not in ("challenge", "defense"):
        return False, f"{policy_id}: side must be challenge/defense"
    tier = spec.get("tier", "amicus")
    case = _ensure_case(world, policy_id)

    if tier == "amicus":
        if lab.id in case.used_amicus:
            return False, f"{policy_id}: already filed an amicus brief"
        cost, points = consts.LIT_AMICUS_COST, consts.LIT_AMICUS_POINTS
        if lab.cash < cost:
            return False, f"{policy_id}: not enough cash for amicus"
        case.used_amicus.add(lab.id)
    elif tier == "join":
        if not pdef.covers(lab):
            return False, f"{policy_id}: no standing (not subject to this policy)"
        if lab.id in case.used_join:
            return False, f"{policy_id}: already joined this case"
        cost, points = consts.LIT_JOIN_COST, consts.LIT_JOIN_POINTS
        if lab.cash < cost:
            return False, f"{policy_id}: not enough cash to join"
        case.used_join.add(lab.id)
    elif tier == "fund":
        spend = max(0.0, float(spec.get("spend", 0.0) or 0.0))
        cost = min(spend, lab.cash)
        if cost <= 0:
            return False, f"{policy_id}: fund tier needs spend"
        points = consts.LIT_FUND_K * math.sqrt(cost)   # diminishing returns within tier
    else:
        return False, f"{policy_id}: tier must be amicus/join/fund"

    lab.cash -= cost
    if side == "challenge":
        case.challenge_effort += points
        case.challengers.add(lab.id)
        case.fresh_challenge += points
        case.fresh_challenger = lab.id
    else:
        case.defense_effort += points
        case.defenders.add(lab.id)
    return True, f"{lab.name} {side} {pdef.name} ({tier})"


def _doj_effort(world, consts):
    return consts.LIT_DOJ_WTR_K * world.wtr


def _bar(world, st, consts):
    return (st.litigation.defense_effort + _doj_effort(world, consts)
            + consts.LIT_CONST_FLOOR_WEIGHT * st.constitutionality)


def resolve_litigation(labs, world, flags, rng, consts, dt, turn):
    """Governance-phase pass: tick injunctions, resolve open cases by MARGIN,
    run appeals/precedent, emit news. Returns (events, news_lines)."""
    from backend_v1.engine.governance import appeals as appeals_mod
    events, news = [], []
    sb = SimpleNamespace(labs=labs, labs_by_id={l.id: l for l in labs},
                         world=world, flags=flags, rng=rng, consts=consts,
                         dt=dt, turn=turn)
    for pid, st in world.policies.items():
        case = st.litigation
        if case is None or case.status == "closed":
            continue
        # the ACT of aggressively challenging draws political backlash (dual ledger)
        if case.fresh_challenge > 0:
            ev = gov_news.challenge_backlash(sb, POLICY_DEFS_BY_ID[pid].name,
                                             case.fresh_challenge, case.fresh_challenger)
            if ev is not None:
                events.append(ev)
            case.fresh_challenge = 0.0
            case.fresh_challenger = None
        # tick a live preliminary injunction (temporary freeze of enforcement)
        if case.injunction_turns_left > 0:
            case.injunction_turns_left -= 1
            if case.injunction_turns_left == 0:
                news.append(f"Preliminary injunction on {POLICY_DEFS_BY_ID[pid].name} "
                            f"expired; enforcement resumes.")
            continue
        if case.challenge_effort <= 0:    # nobody is actually challenging
            continue
        if case.opened_turn is None:
            case.opened_turn = turn

        margin = case.challenge_effort - _bar(world, st, consts)
        case.last_margin = margin
        # a real case takes time: don't rule until the contest has run a few turns
        # (lets a determined challenger fund the campaign to overcome a defended rule)
        if turn - case.opened_turn < consts.LIT_MIN_CONTEST_TURNS:
            continue
        # A case lingers while the challenger is still building it (negative margin),
        # giving sustained funding time to accumulate; only once the challenge has
        # MADE its case (margin climbing toward / past the bar) does the court move
        # to rule. (Hopeless challenges fizzle at the slow base rate.)
        rate = consts.LIT_RESOLVE_BASE + consts.LIT_RESOLVE_MARGIN_K * max(0.0, margin)
        if not rng.roll_rate(rate, dt):
            continue

        outcome, ev, nz = _apply_outcome(sb, st, case, margin, appeals_mod)
        events += ev
        news += nz
    return events, news


def _apply_outcome(sb, st, case, margin, appeals_mod):
    """Map the resolved MARGIN to an outcome; apply permanent/temporary effects;
    handle entrenchment, precedent, and appeals. Returns (outcome, events, news)."""
    consts, world, turn = sb.consts, sb.world, sb.turn
    pdef = POLICY_DEFS_BY_ID[case.policy_id]
    name = pdef.name
    events, news = [], []
    court_mult = consts.COURT_PRECEDENT_MULT[case.court_level]
    win_bar = consts.COURT_WIN_BAR[case.court_level]
    eff_margin = margin - win_bar   # higher courts demand a bigger margin to overturn

    if eff_margin >= consts.LIT_MARGIN_STRUCK:
        outcome = "struck"
        st.stage = "struck"
        st.enforcement_level = 0.0
        case.note(turn, f"{name} STRUCK at {case.court_level} (margin {margin:+.0f})")
        news.append(f"COURT: {name} struck down ({case.court_level}).")
        # a struck POPULAR safety policy enrages the public -> WTR spike
        events.append(gov_news.news_event(sb, "policy_struck", name,
                                          approval=-consts.LIT_NEWS_APPROVAL_SWING,
                                          wtr=+consts.LIT_NEWS_WTR_SWING))
    elif eff_margin >= consts.LIT_MARGIN_WEAKEN:
        outcome = "weakened"
        st.enforcement_level = max(0.0, st.enforcement_level - consts.LIT_WEAKEN_AMOUNT)
        case.note(turn, f"{name} enforcement weakened (margin {margin:+.0f})")
        news.append(f"COURT: {name} enforcement permanently narrowed.")
    elif eff_margin >= consts.LIT_MARGIN_INJUNCTION:
        outcome = "injunction"
        case.injunction_turns_left = consts.LIT_INJUNCTION_TURNS
        case.note(turn, f"{name} preliminarily enjoined {consts.LIT_INJUNCTION_TURNS}q")
        news.append(f"COURT: {name} preliminarily enjoined for "
                    f"{consts.LIT_INJUNCTION_TURNS} quarters.")
    elif eff_margin >= consts.LIT_MARGIN_PENALTY_CAP:
        outcome = "penalty_cap"
        st.penalty_cap = consts.LIT_PENALTY_CAP_FACTOR
        case.note(turn, f"{name} penalty ceiling capped (margin {margin:+.0f})")
        news.append(f"COURT: {name} stands, but its maximum penalty is capped.")
    else:
        outcome = "fail"
        # a higher court rejecting the challenge REINSTATES a provisionally-struck policy
        if st.stage == "struck":
            st.stage = "active"
            st.enforcement_level = max(st.enforcement_level, consts.ENFORCEMENT_MIN)
            news.append(f"COURT: {name} REINSTATED on appeal.")
        # surviving a real challenge ENTRENCHES the policy ∝ court level
        st.constitutionality = min(1.0, st.constitutionality
                                   + consts.LIT_ENTRENCH_GAIN * court_mult)
        case.note(turn, f"{name} survived challenge; entrenched (margin {margin:+.0f})")
        news.append(f"COURT: challenge to {name} failed; the rule is now better "
                    f"established.")

    # ── appeals: the losing side may appeal (P ∝ −margin); precedent by court ──
    appealed = appeals_mod.maybe_appeal(sb, st, case, outcome, margin)
    if appealed:
        news.append(f"APPEAL filed on {name} → escalated to {case.court_level}.")
    else:
        case.status = "closed"
        # final precedent updates constitutionality by court level
        appeals_mod.apply_precedent(st, case, outcome, consts)
    return outcome, events, news
