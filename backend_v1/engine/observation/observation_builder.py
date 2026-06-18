"""THE see-able/hidden chokepoint (§11). Reads GameState (TRUE) -> emits
filtered per-actor Observations. Only MEASURED snapshots, findings, and public
info cross this boundary. Audit this file when wondering 'can the player see X'.
"""
from backend_v1.engine.observation.observations import Observation
from backend_v1.engine.actions import legal_moves
from backend_v1.engine.research.findings import synthesize_worry_bar


def _model_view(m, include_dangerous=True):
    """Measured-only view of a model. NO true stats, no suppression, no
    concealment, no hidden history."""
    measured_capability = {
        "general": round(m.measured_capability.general, 2),
        "coding_rnd": round(m.measured_capability.coding_rnd, 2),
    }
    measured_alignment = {
        "eval_awareness": round(m.measured_alignment.eval_awareness, 2),
        "deception": round(m.measured_alignment.deception, 2),
        "goal_misalignment": round(m.measured_alignment.goal_misalignment, 2),
        "self_preservation": round(m.measured_alignment.self_preservation, 2),
        "jailbreak_sensitivity": round(m.measured_alignment.jailbreak_sensitivity, 2),
    }
    v = {
        "id": m.id,
        "released": m.released,
        "leaked": m.leaked,
        "measured_capability": measured_capability,
        "measured_alignment": measured_alignment,
        "post_train_rounds": m.post_train_rounds,
        "jailbreak_techniques_public": m.jailbreak_discovered,
    }
    if include_dangerous:
        v["dangerous_capability_eval"] = round(m.measured_dangerous_capability, 2)
    return v


def _elicitation_projection(m, lab, consts):
    """The §8b trap in UI form: capability projection is real & roughly
    trustworthy; the alignment cost of the same rounds is NOT shown."""
    from backend_v1.engine.research.capabilities.capabilities_research_item import (
        CAPABILITY_TREE_BY_ID,
    )
    elicitation_bonuses = sum(
        CAPABILITY_TREE_BY_ID[nid].elicitation_bonus
        for nid in lab.researched_advances if nid in CAPABILITY_TREE_BY_ID)
    rate = consts.ELICIT_BASE + elicitation_bonuses

    ceiling_est = m.ceiling.general  # ceiling estimate is roughly trustworthy
    realized = m.measured_capability.general

    curve = []
    r = realized
    for rounds in range(1, 7):
        r = r + (ceiling_est - r) * rate
        curve.append({"more_rounds": rounds, "projected_general": round(r, 2)})

    return {"ceiling_estimate": round(ceiling_est, 2),
            "projection": curve,
            "note": "capability projection only — post-training also shapes "
                    "dispositions; that cost is not on this chart"}


def _chatter(wtr):
    if wtr < 15:
        return "quiet"
    if wtr < 35:
        return "rumbling"
    if wtr < 60:
        return "loud"
    return "deafening"


def _rival_public_entry(other, lab, state, consts):
    """Build the coarse public-information entry for one rival lab."""
    frontier_model = other.frontier_model()
    entry = {
        "lab_id": other.id,
        "name": other.name,
        "market_cap": round(other.market_cap, 1),
        "released_models": len(other.release_history),
    }
    if frontier_model is not None:
        # rivals' stats: much worse estimates (extra noise, applied once per
        # release and cached so the estimate doesn't dance)
        cache = lab.__dict__.setdefault("_rival_est_cache", {})
        key = (other.id, frontier_model.id)
        if key not in cache:
            noise = state.rng.normal(0, consts.RIVAL_ESTIMATE_NOISE)
            cache[key] = max(0.0, frontier_model.measured_capability.general * (1 + noise))
        entry["frontier_capability_estimate"] = round(cache[key], 2)
        entry["frontier_model_id"] = frontier_model.id
    return entry


def _in_progress_entries(lab, state):
    """Serialised view of all active projects, including any live training run."""
    active_project_entries = [
        {
            "project_id": p.template_id,
            "kind": p.kind,
            "ai_assist": p.ai_assist,
            "years_remaining_estimate": round(max(0.0, p.duration_years_remaining), 2),
        }
        for p in lab.in_progress
    ]
    training_run_entry = (
        [{"project_id": "pretrain_run", "kind": "training",
          "years_remaining_estimate": round(lab.training_run.duration_years_remaining, 2)}]
        if lab.training_run is not None else []
    )
    return active_project_entries + training_run_entry


def build_observation(state, lab, tips, policy_news, public_events,
                      new_findings) -> Observation:
    consts = state.consts

    rivals_pub = [
        _rival_public_entry(other, lab, state, consts)
        for other in state.labs
        if other.id != lab.id
    ]

    current_year = round(consts.START_YEAR + state.turn * state.dt, 2)

    work_budget_used = sum(p.budget_fraction_effective for p in lab.in_progress)
    work_budget_free = round(lab.work_budget_per_year * state.dt - work_budget_used, 3)

    mit = lab.model_in_training
    model_in_training_view = (
        {**_model_view(mit), "elicitation": _elicitation_projection(mit, lab, consts)}
        if mit is not None else None
    )

    active_policy_ids = [pid for pid, st in state.world.policies.items() if st.active]

    public_event_entries = [
        {"turn": e.turn, "category": e.category, "text": e.public_text}
        for e in public_events if e.public
    ]

    return Observation(
        lab_id=lab.id,
        turn=state.turn,
        year=current_year,
        cash=round(lab.cash, 1),
        work_budget_free=work_budget_free,
        revenue_rate=round(lab.revenue_rate, 1),
        investment_rate=round(lab.investment_rate, 1),
        market_caps={l.id: round(l.market_cap, 1) for l in state.labs},
        own_models=[_model_view(m) for m in lab.release_history],
        model_in_training=model_in_training_view,
        in_progress=_in_progress_entries(lab, state),
        new_findings=[dict(f) for f in new_findings],
        worry_bar=synthesize_worry_bar(lab.findings, state.turn, consts),
        rival_public=rivals_pub,
        public_approval=round(state.world.public_approval, 1),
        regulatory_chatter=_chatter(state.world.wtr),
        active_policies=active_policy_ids,
        policy_news=list(policy_news),
        public_events=public_event_entries,
        tips=list(tips),
        legal_moves=legal_moves(lab, state.world, consts, state.dt),
        game_over=state.game_over,
        outcome=state.outcome,
    )
