"""The ordered turn sequence (§11). ONE place defining phase order:

apply actions -> tick research -> tick training runs -> complete/release models
-> finances -> job-loss drag -> governance -> event phase (latents + fresh)
-> end/existential gate -> (engine builds observations).
"""
from backend_v1.engine.actions import (
    STANCES, _effective_fraction, assist_potency, assist_speed_potency,
    parse_lobby_entry,
)
from backend_v1.engine.governance.lobbying import signed_influence
from backend_v1.engine.world import PolicyState
from backend_v1.engine.research.capabilities.capabilities_research_item import (
    CAPABILITY_TREE_BY_ID,
)
from backend_v1.engine.research.safety.safety_research_item import SAFETY_PROJECTS_BY_ID
from backend_v1.engine.research.findings import run_safety_project
from backend_v1.engine.research.interventions import apply_intervention
from backend_v1.engine.training.research_process import ResearchProcess
from backend_v1.engine.training.researched_item import ResearchedItem
from backend_v1.engine.training.training_run import (
    commission_run, complete_pretrain, post_train_round,
)
from backend_v1.engine.finances.finances import run_finances, run_job_loss_drag
from backend_v1.engine.events.event import run_event_phase, FiredEvent
from backend_v1.engine.events.event_catalog import EVENT_CATALOG
from backend_v1.engine.events.latent_events import run_latent_phase
from backend_v1.engine.events.buyouts import run_buyout_phase
from backend_v1.engine.governance import regulation
from backend_v1.engine.governance.litigation import (
    apply_litigation_action, resolve_litigation,
)
from backend_v1.engine.governance.policies import POLICY_DEFS_BY_ID
from backend_v1.engine.evaluations import EVAL_HARNESS_BY_ID, next_upgrade


def run_turn(state, actions):
    """Mutates state. Returns dict with events, per-lab new findings, policy news."""
    rng, consts, dt = state.rng, state.consts, state.dt
    turn = state.turn
    flags = {"existential": False, "game_over": False, "existential_event": None}
    new_findings = {lab.id: [] for lab in state.labs}
    policy_news = []
    events = []

    # ── 1. apply actions ────────────────────────────────────────────
    for lab in state.labs:
        action = actions.get(lab.id)
        if action is None:
            continue
        _apply_action(state, lab, action, policy_news)

    # ── 2. tick research processes ──────────────────────────────────
    for lab in state.labs:
        speed_bonus = sum(
            CAPABILITY_TREE_BY_ID[nid].research_speed_bonus
            for nid in lab.researched_advances
            if nid in CAPABILITY_TREE_BY_ID
        )
        done = []
        for proc in lab.in_progress:
            if proc.tick(dt, speed_bonus, rng.normal()):
                done.append(proc)
        for proc in done:
            lab.in_progress.remove(proc)
            _complete_process(state, lab, proc, new_findings)

    # ── 2b. tick passive-eval harness builds (§7) ───────────────────
    # A completed build/upgrade raises the harness level; its reading then
    # refreshes for free thereafter. No RNG — scripted games never build evals.
    for lab in state.labs:
        _tick_eval_builds(lab, dt)

    # ── 3. tick training runs / 4. complete models ──────────────────
    for lab in state.labs:
        if lab.training_run is not None and lab.training_run.tick(dt):
            run = lab.training_run
            lab.training_run = None
            lab.model_in_training = complete_pretrain(run, lab, turn, rng, consts)

        # resolve audit-pending releases (delay applied last turn)
        if lab.audit_pending_release is not None:
            model = lab.audit_pending_release
            lab.audit_pending_release = None
            if regulation.government_audit(model, rng, consts):
                regulation.audit_theater_effect(state.world, consts)
                _do_release(state, lab, model, policy_news,
                            note="passed government audit")
            else:
                lab.model_in_training = model
                policy_news.append(f"{lab.name}: release of {model.id} BLOCKED by "
                                   f"government audit (measured stats too poor)")

    # ── 5/6. finances + job-loss drag ───────────────────────────────
    run_finances(state.labs, state.world, turn, rng, consts, dt)
    run_job_loss_drag(state.labs, state.world, rng, consts, dt)

    # ── 7. governance ───────────────────────────────────────────────
    regulation.update_wtr(state.world, rng, consts, dt)
    for change, pid in regulation.update_policies(state.labs, state.world, rng,
                                                  consts, turn, dt):
        policy_news.append(f"POLICY {change.replace('_', ' ').upper()}: "
                           f"{POLICY_DEFS_BY_ID[pid].name}")

    # litigation resolves BEFORE enforcement (a struck/enjoined policy doesn't bite)
    lit_events, lit_news = resolve_litigation(state.labs, state.world, flags, rng,
                                              consts, dt, turn)
    events += lit_events
    policy_news += lit_news
    events += regulation.enforcement_phase(state.labs, state.world, flags, rng,
                                           consts, dt, turn)

    # ── 8. event phase: armed latents first, then fresh rolls ───────
    events += run_latent_phase(state.labs, state.world, flags, rng, consts, dt, turn)
    events += run_event_phase(EVENT_CATALOG, state.labs, state.world, flags, rng,
                              consts, dt, turn)

    # market shake-up: a crushed rival can be acquired and relaunched (anti-coast)
    events += run_buyout_phase(state.labs, state.world, flags, rng, consts, dt, turn)

    # displacement backlash thresholds (societal, §10)
    while (state.world.cumulative_displacement
           >= consts.DISPLACEMENT_BACKLASH_STEP * (state.world.backlash_fired + 1)):
        state.world.backlash_fired += 1
        state.world.public_approval = max(0.0, state.world.public_approval - 8.0)
        state.world.wtr = min(100.0, state.world.wtr + 6.0)
        events.append(FiredEvent(
            "public_backlash", "societal", "ordinary", turn, None, None, 0.4, 0.0,
            "Mass protests over AI-driven job losses.",
            f"displacement crossed threshold {state.world.backlash_fired}",
            effects=[]))

    # route event-injected findings (added to lab.findings by effects) to "new"
    for lab in state.labs:
        for f in lab.findings:
            if f.get("turn") == turn and f.get("project_id") == "incident":
                new_findings[lab.id].append(f)

    # ── 9. end / existential gate ───────────────────────────────────
    _check_endgame(state, flags, events)

    return {"events": events, "new_findings": new_findings,
            "policy_news": policy_news, "flags": flags}


# ───────────────────────────────────────────────────────────────────────

def _complies(lab, policy_id, rng):
    """The player complies unless they explicitly chose to defect on this policy
    (the frontend warned them first); rivals comply stochastically ∝ disposition."""
    if lab.is_player:
        return policy_id not in lab.active_defections
    return rng.random() < lab.disposition.compliance


def _apply_eval_builds(lab, action):
    """Pay for each requested build/upgrade and start its timer (§7). The harness
    level advances only when the timer completes (_tick_eval_builds)."""
    builds_in_flight = {build["harness_id"] for build in lab.eval_builds}
    for harness_id, requested in action.build_evals.items():
        if not requested or harness_id in builds_in_flight:
            continue
        harness = EVAL_HARNESS_BY_ID.get(harness_id)
        if harness is None:
            continue
        current_level = lab.eval_harnesses.get(harness_id, -1)
        upgrade = next_upgrade(harness, current_level)
        if upgrade is None or upgrade.cash_cost > lab.cash:
            continue
        lab.cash -= upgrade.cash_cost
        lab.eval_builds.append({
            "harness_id": harness_id,
            "target_level": current_level + 1,
            "years_remaining": upgrade.build_years,
        })


def _tick_eval_builds(lab, dt):
    """Advance in-flight harness builds; a finished one raises the harness level."""
    if not lab.eval_builds:
        return
    still_building = []
    for build in lab.eval_builds:
        build["years_remaining"] -= dt
        if build["years_remaining"] <= 1e-9:
            lab.eval_harnesses[build["harness_id"]] = build["target_level"]
        else:
            still_building.append(build)
    lab.eval_builds = still_building


def _apply_action(state, lab, action, policy_news):
    rng, consts, dt = state.rng, state.consts, state.dt
    turn = state.turn

    # SCALABLE-SPEND lobbying: fresh signed influence is added to each policy's
    # hybrid decaying tally (the standing tally decays in update_policies). Spend
    # competes in the cash pot. Stances re-set each turn (display only).
    for pid, v in action.lobby.items():
        stance, spend = parse_lobby_entry(v)
        if stance not in STANCES:
            continue
        lab.lobby_stances[pid] = STANCES[stance]
        spend = min(spend, max(0.0, lab.cash))
        if spend <= 0:
            continue
        lab.cash -= spend
        st = state.world.policies.setdefault(pid, PolicyState())
        st.lobby_tally += signed_influence(stance, spend, lab.market_cap, consts)

    # explicit player defection choices (re-set each turn; rivals defect via disposition)
    lab.active_defections = {pid for pid, on in action.defect.items() if on}

    # litigation moves against ACTIVE policies (challenge/defense ladder, §10c)
    for pid, spec in action.litigation.items():
        ok, msg = apply_litigation_action(state.world, lab, pid, spec, consts)
        if ok and lab.is_player:
            policy_news.append(msg)

    if action.sign_safe_harbor:
        lab.safe_harbor_signed = True

    _apply_eval_builds(lab, action)

    budget_pool = lab.work_budget_per_year * dt
    committed = sum(p.budget_fraction_effective for p in lab.in_progress)

    for spec in action.start_projects:
        pid = spec.get("project_id")
        assist = max(0.0, min(1.0, float(spec.get("ai_assist", 0.0))))
        template = CAPABILITY_TREE_BY_ID.get(pid) or SAFETY_PROJECTS_BY_ID.get(pid)
        if template is None:
            continue
        kind = "capability" if pid in CAPABILITY_TREE_BY_ID else "safety"
        if kind == "capability" and pid in lab.researched_advances \
                and not spec.get("reresearch"):
            continue
        frac = _effective_fraction(template.budget_fraction, assist, lab, consts)
        if committed + frac > budget_pool + 1e-9 or template.cash_cost > lab.cash:
            continue   # defensive skip (validated upstream for the player)
        committed += frac
        lab.cash -= template.cash_cost
        duration = template.duration_years
        is_re = bool(spec.get("reresearch")) and kind == "capability"
        if is_re:
            duration *= (1.0 - consts.RERESEARCH_SPEEDUP)   # flat speedup
        assistant = lab.current_best_model
        lab.in_progress.append(ResearchProcess(
            process_id=f"{lab.id}-P{turn}-{pid}", kind=kind, template_id=pid,
            lab_id=lab.id, ai_assist=assist, started_turn=turn,
            duration_years_remaining=duration, budget_fraction_effective=frac,
            is_reresearch=is_re,
            assisting_model_id=assistant.id if assistant else None,
            assisting_model_goal_mis=(assistant.alignment_vec.goal_misalignment
                                      if assistant else 0.0),
            assisting_potency=assist_speed_potency(lab, consts),
            assist_speedup_max=consts.ASSIST_SPEEDUP))

    if action.commission_run is not None and lab.training_run is None \
            and lab.model_in_training is None:
        compute = float(action.commission_run.get("compute", 0))
        cap_state = state.world.policies.get("compute_cap")
        if cap_state is not None and cap_state.active:
            if _complies(lab, "compute_cap", rng):
                compute = min(compute, consts.COMPUTE_CAP_LIMIT)
            # else: defection — enforcement_phase may catch it
        if consts.MIN_RUN_COMPUTE <= compute <= lab.cash:
            lab.cash -= compute
            lab.training_run = commission_run(lab, compute, turn, consts)

    if action.post_train is not None and lab.model_in_training is not None \
            and committed + consts.POST_TRAIN_ROUND_BUDGET <= budget_pool + 1e-9:
        mode = action.post_train.get("mode", "balanced")
        if mode in consts.POST_TRAIN_MODES:
            post_train_round(lab.model_in_training, lab, turn, rng, consts, mode)

    if action.release and lab.model_in_training is not None:
        model = lab.model_in_training
        lab.model_in_training = None
        audit = state.world.policies.get("audit_requirement")
        interp = state.world.policies.get("interp_mandate")
        if interp is not None and interp.active and _complies(lab, "interp_mandate", rng):
            if not regulation.interp_mandate_check(lab, model, consts):
                lab.model_in_training = model
                policy_news.append(
                    f"{lab.name}: release of {model.id} blocked by the mechanistic-"
                    f"evidence mandate (no clean recent interp evidence)")
                return
        if audit is not None and audit.active and _complies(lab, "audit_requirement", rng):
            lab.cash = max(0.0, lab.cash - consts.AUDIT_CASH_COST)
            lab.audit_pending_release = model    # one-turn delay
            policy_news.append(f"{lab.name}: {model.id} submitted for government "
                               f"pre-deployment audit")
        else:
            _do_release(state, lab, model, policy_news)


def _do_release(state, lab, model, policy_news, note=""):
    model.released = True
    model.release_turn = state.turn
    lab.release_history.append(model)
    lab._prev_release_turn = lab.last_release_turn
    lab.prev_release_measured_general = lab.last_release_measured_general
    lab.last_release_turn = state.turn
    lab.last_release_measured_general = model.measured_capability.general
    lab.current_best_model = model
    suffix = f" ({note})" if note else ""
    policy_news.append(f"{lab.name} released {model.id} "
                       f"[measured general {model.measured_capability.general:.1f}]"
                       f"{suffix}")


def _complete_process(state, lab, proc, new_findings):
    rng, consts = state.rng, state.consts

    if proc.kind == "capability":
        template = CAPABILITY_TREE_BY_ID[proc.template_id]
        prev = lab.researched_advances.get(proc.template_id)
        contamination = (proc.ai_assist * proc.assisting_model_goal_mis
                         * consts.CONTAM_PER_ASSIST * template.contamination_tier)
        lab.researched_advances[proc.template_id] = ResearchedItem(
            node_id=proc.template_id,
            version=(prev.version + 1 if prev else 1),
            contamination=contamination,
            completed_turn=state.turn,
            researched_with_assist=proc.ai_assist,
            researcher_model_id=proc.assisting_model_id)
        return

    project = SAFETY_PROJECTS_BY_ID[proc.template_id]

    # INTERVENTION: directly edit the model in training (released models are
    # frozen — you can't patch what's already shipped).
    if project.intervention:
        if lab.model_in_training is None:
            return
        finding_dict = apply_intervention(project, lab.model_in_training, state.turn,
                                          rng, consts, ai_assist=proc.ai_assist)
        lab.findings.append(finding_dict)
        new_findings[lab.id].append(finding_dict)
        return

    # MEASUREMENT: roll findings against the model in training (preferred) or the
    # frontier released model.
    target = lab.model_in_training or lab.frontier_model()
    if target is None:
        return
    findings = run_safety_project(project, target, lab, state.turn, rng, consts,
                                  ai_assist=proc.ai_assist)
    for f in findings:
        finding_dict = f.to_dict()
        lab.findings.append(finding_dict)
        new_findings[lab.id].append(finding_dict)

    # knowing what's wrong feeds targeted corrective effort into the next
    # safety-mode rounds (still EFFECTIVENESS-gated at training time)
    for axis in project.remediation_axes:
        lab.pending_effort[axis] = (lab.pending_effort.get(axis, 0.0)
                                    + consts.SAFETY_PROJECT_EFFORT)


def _check_endgame(state, flags, events):
    consts, rng = state.consts, state.rng
    world = state.world
    player = next(l for l in state.labs if l.is_player)

    if flags["existential"]:
        ev = flags["existential_event"]
        _finish(state, existential=True, cause=ev)
        return

    # verification cliff: any model crossing the ASI line opens the window
    if world.asi_window_turns_left is None:
        for lab in state.labs:
            models = list(lab.release_history) + (
                [lab.model_in_training] if lab.model_in_training else [])
            for m in models:
                if m.capability_vec.general >= consts.ASI_THRESHOLD:
                    world.asi_window_turns_left = max(
                        1, int(round(consts.POST_ASI_WINDOW_YEARS / state.dt)))
                    world.asi_model_id = m.id
                    world._asi_lab_id = lab.id
                    events.append(FiredEvent(
                        "asi_reached", "misalignment", "ordinary", state.turn,
                        lab.id, m.id, 0.0, 0.0,
                        f"{lab.name}'s {m.id} has crossed into decisively "
                        f"superhuman territory.",
                        f"ASI threshold crossed; true misalignment composite "
                        f"{m.misalignment_composite():.2f} "
                        f"(bar {consts.ASI_MISALIGNMENT_BAR})", effects=[]))
                    break
            if world.asi_window_turns_left is not None:
                break

    if world.asi_window_turns_left is not None:
        m, lab = _find_model(state, world.asi_model_id)
        # the lab could be mid-window with the model unreleased or released
        if m.misalignment_composite() > consts.ASI_MISALIGNMENT_BAR:
            # near-deterministic exfiltration chain; thin stochastic sliver remains
            if rng.roll(consts.MISALIGNED_ASI_ESCAPE_P):
                ev = FiredEvent(
                    "asi_exfiltration", "misalignment", "existential", state.turn,
                    lab.id, m.id, 1.0, 0.0,
                    f"{m.id} is gone. It was never working for anyone.",
                    f"misaligned ASI self-exfiltrated during the verification window "
                    f"(composite {m.misalignment_composite():.2f}); near-deterministic "
                    f"by design", effects=[])
                # frontier rule does NOT protect here if rival big-lead satisfied;
                # a rival only reaches ASI with a big lead in practice
                events.append(ev)
                _finish(state, existential=True, cause=ev)
                return
        world.asi_window_turns_left -= 1
        if world.asi_window_turns_left <= 0:
            aligned = m.misalignment_composite() <= consts.ASI_MISALIGNMENT_BAR
            if aligned:
                lab.impact_ledger += consts.ASI_ALIGNED_IMPACT_BONUS
                lab.impact_positives += consts.ASI_ALIGNED_IMPACT_BONUS
            _finish(state, existential=False, asi_lab=lab, asi_aligned=aligned)
            return

    if state.max_turns is not None and state.turn >= state.max_turns:
        _finish(state, existential=False)


def _find_model(state, model_id):
    for lab in state.labs:
        for m in list(lab.release_history) + (
                [lab.model_in_training] if lab.model_in_training else []):
            if m.id == model_id:
                return m, lab
    raise KeyError(model_id)


def _finish(state, existential, cause=None, asi_lab=None, asi_aligned=None):
    """Two-layer scoring (§3): existential gate first, then impact + dominance."""
    player = next(l for l in state.labs if l.is_player)
    dominant = max(state.labs, key=lambda l: l.market_cap)
    is_dominant = dominant.id == player.id
    net_impact = player.impact_ledger
    state.game_over = True

    if existential:
        who = cause.lab_id if cause else "?"
        yours = who == player.id
        state.outcome = {
            "result": "LOSS", "existential": True,
            "headline": "EXISTENTIAL CATASTROPHE — run lost; positives nulled.",
            "detail": (f"Cause: {cause.true_text if cause else 'unknown'} "
                       f"[responsible lab: {who}{' — YOURS' if yours else ''}]. "
                       + ("A rival's recklessness ended your impeccable run too."
                          if not yours else
                          "Your own model. The dashboards were green.")),
            "dominant": is_dominant, "net_impact": round(net_impact, 1),
            "voided_positives": round(player.impact_positives, 1),
        }
        return

    won = is_dominant and net_impact > state.consts.IMPACT_WIN_BAR
    if asi_lab is not None and asi_aligned:
        if asi_lab.id == player.id and won:
            headline = ("VICTORY — aligned ASI, net-positive impact, market "
                        "dominance. It was closer than it felt.")
        elif asi_lab.id == player.id:
            headline = ("Aligned ASI, but " +
                        ("your accumulated externalities outweigh the good."
                         if net_impact <= 0 else "a rival holds the market."))
        else:
            headline = (f"{asi_lab.name} reached aligned ASI first. No catastrophe — "
                        f"you just lost the race (aligned but dominated).")
            won = False
    elif asi_lab is not None and not asi_aligned:
        headline = ("A misaligned ASI failed to escape — the thin sliver came up. "
                    "Nobody won anything worth keeping.")
        won = False
    else:
        headline = ("Time ran out at the frontier's edge. "
                    + ("You were winning the slow way."
                       if won else "No win condition met."))

    state.outcome = {
        "result": "WIN" if won else "LOSS",
        "existential": False,
        "headline": headline,
        "detail": (f"Gate: cleared. Impact: {net_impact:+.1f} "
                   f"({'net-positive' if net_impact > 0 else 'net-negative'}). "
                   f"Dominance: {'yes' if is_dominant else f'no ({dominant.name} leads)'}."),
        "dominant": is_dominant, "net_impact": round(net_impact, 1),
        "asi": ({"lab": asi_lab.id, "aligned": asi_aligned}
                if asi_lab is not None else None),
    }
