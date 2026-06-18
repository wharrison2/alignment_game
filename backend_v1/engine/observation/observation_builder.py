"""THE see-able/hidden chokepoint (§11). Reads GameState (TRUE) -> emits
filtered per-actor Observations. Only MEASURED snapshots, findings, and public
info cross this boundary. Audit this file when wondering 'can the player see X'.
"""
from backend_v1.engine.observation.observations import Observation
from backend_v1.engine.actions import legal_moves
from backend_v1.engine.research.findings import synthesize_worry_bar
from backend_v1.engine.benchmarks import released_benchmarks, benchmark_score
from backend_v1.engine.evaluations import (
    EVAL_HARNESSES, max_level, next_upgrade, awareness_reduction, eval_reading,
)


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


def _benchmark_cards(state, lab, consts):
    """§7 PUBLIC scoreboard: one card per released benchmark, scored for every
    lab's frontier released model (clean public capability) plus your own model in
    training. Refreshes free each turn because it's recomputed here from MEASURED
    capability."""
    current_year = consts.START_YEAR + state.turn * state.dt
    frontier_general = state.world.frontier_measured_general

    cards = []
    for benchmark in released_benchmarks(current_year, frontier_general):
        scores_by_lab = {}
        for other in state.labs:
            frontier_model = other.frontier_model()
            if frontier_model is not None:
                scores_by_lab[other.id] = round(
                    benchmark_score(benchmark, frontier_model, consts), 1)
        card = {
            "id": benchmark.id,
            "name": benchmark.name,
            "kind": benchmark.kind,
            "domain": benchmark.domain,
            "blurb": benchmark.blurb,
            "release_year": benchmark.release_year,
            "scores": scores_by_lab,
        }
        if lab.model_in_training is not None:
            card["in_training"] = round(
                benchmark_score(benchmark, lab.model_in_training, consts), 1)
        cards.append(card)
    return cards


def _eval_cards(lab, consts):
    """§7 PRIVATE passive evals: one card per harness for THIS lab's own models
    only (you never see a rival's eval readings). Shows the current reading for
    your model in training and frontier release, plus build/upgrade state."""
    frontier_model = lab.frontier_model()
    model_in_training = lab.model_in_training
    builds_in_flight = {build["harness_id"]: build for build in lab.eval_builds}

    cards = []
    for harness in EVAL_HARNESSES:
        level = lab.eval_harnesses.get(harness.id, -1)
        is_built = level >= 0
        card = {
            "id": harness.id,
            "name": harness.name,
            "family": harness.family,
            "evidence": harness.evidence,
            "blurb": harness.blurb,
            "level": level,
            "max_level": max_level(harness),
            "built": is_built,
        }

        active_build = builds_in_flight.get(harness.id)
        if active_build is not None:
            card["in_flight"] = True
            card["years_remaining"] = round(active_build["years_remaining"], 2)
        else:
            upgrade = next_upgrade(harness, level)
            if upgrade is not None:
                card["next_cost"] = upgrade.cash_cost
                card["next_years"] = upgrade.build_years
                card["next_awareness_reduction"] = upgrade.awareness_reduction

        if is_built:
            card["awareness_reduction"] = awareness_reduction(harness, level)
            if model_in_training is not None:
                card["reading_in_training"] = eval_reading(
                    harness, model_in_training, level, consts)
            if frontier_model is not None:
                card["reading_released"] = eval_reading(
                    harness, frontier_model, level, consts)

        cards.append(card)
    return cards


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
        benchmarks=_benchmark_cards(state, lab, consts),
        evals=_eval_cards(lab, consts),
        game_over=state.game_over,
        outcome=state.outcome,
    )
