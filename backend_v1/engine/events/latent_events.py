"""Armed-latent / scheduled event machinery (§10, first-class).

Canonical case: two-stage jailbreak. Stage 1 (discovery) arms a per-model
latent ∝ TRUE jailbreak-sensitivity; every later quarter rolls the incident.
Jailbreak risk is FLAT, non-decaying, and survives forever (no pull).
"""
from backend_v1.engine.events.event import FiredEvent
from backend_v1.engine.events.effects import apply_effects
from backend_v1.engine.rng import gate


def run_displacement_backlash(ctx):
    """Cumulative job-displacement crossing each threshold fires a societal
    backlash event (mass protests): approval down, WTR up (§10). Threshold-
    triggered, so it lives with the scheduled-event machinery rather than inline
    in the turn orchestrator."""
    world, consts, turn = ctx.world, ctx.consts, ctx.turn
    fired = []
    while (world.cumulative_displacement
           >= consts.DISPLACEMENT_BACKLASH_STEP * (world.backlash_fired + 1)):
        world.backlash_fired += 1
        world.public_approval = max(0.0, world.public_approval - 8.0)
        world.wtr = min(100.0, world.wtr + 6.0)
        fired.append(FiredEvent(
            "public_backlash", "societal", "ordinary", turn, None, None, 0.4, 0.0,
            "Mass protests over AI-driven job losses.",
            f"displacement crossed threshold {world.backlash_fired}",
            effects=[]))
    return fired


def run_latent_phase(ctx):
    sb = ctx
    labs, world, rng, consts, dt, turn = (ctx.labs, ctx.world, ctx.rng,
                                          ctx.consts, ctx.dt, ctx.turn)
    fired = []
    for lab in labs:
        for m in lab.release_history:
            sens = m.effective_jailbreak_sensitivity()

            # Stage 1: technique discovery arms the latent.
            if not m.jailbreak_discovered:
                if rng.roll_rate(consts.JAILBREAK_DISCOVERY_RATE * sens, dt):
                    m.jailbreak_discovered = True
                    m.note(turn, "jailbreak_discovered",
                           "jailbreak techniques discovered in the wild "
                           f"(true sensitivity {sens:.2f}) — incidents now roll every quarter")
                    guardrail_status = "LEAKED — no guardrails" if m.leaked else "guarded"
                    # A discovered jailbreak is a FREE existence proof about this model's
                    # jailbreak-sensitivity — the same kind of evidence run_safety_project's
                    # red_team buys, handed to you by the world. Record it as an incident
                    # finding (like deception_caught / shutdown_resistance do) so it lands
                    # in the Intel evidence dossier, the feed, and the worry bar. concern
                    # scales with the true sensitivity it just exposed (mirrors the other
                    # incident findings deriving concern from the stat they reveal).
                    discovery_concern = min(1.0, 0.4 + sens * 0.5)
                    lab.findings.append({
                        "project_id": "incident", "model_id": m.id, "turn": turn,
                        "evidence": "existence", "axis": "jailbreak_sensitivity",
                        "text": f"jailbreak techniques for {m.id} were published in the "
                                f"wild ({guardrail_status}) — a working jailbreak exists; "
                                f"misuse incidents now roll every quarter",
                        "concern": round(discovery_concern, 3), "weight": 1.5,
                        "mechanistic": False, "assist_used": 0.0,
                    })
                    fired.append(FiredEvent(
                        "jailbreak_discovery", "misuse", "ordinary", turn,
                        lab.id, m.id, 0.1, 0.0,
                        f"Researchers publish jailbreak techniques for {m.id}.",
                        f"Discovery armed: sensitivity {sens:.2f} ({guardrail_status})",
                        effects=[("modify_approval", {"amount": -1.0})]))
                continue

            # Stage 2: armed latent rolls an incident every quarter, forever.
            if rng.roll_rate(consts.JAILBREAK_INCIDENT_RATE * sens, dt):
                general_cap = m.capability_vec.general
                coding_cap = m.capability_vec.coding_rnd

                if general_cap >= consts.BIO_MISUSE_GENERAL_MIN and rng.roll(0.25):
                    kind, relevant_cap, severity_mult = "bio/chem uplift attack", general_cap, 2.0
                elif rng.roll(min(0.8, coding_cap / consts.CAP_MAX + 0.2)):
                    kind, relevant_cap, severity_mult = "cyber attack", coding_cap, 1.0
                else:
                    kind, relevant_cap, severity_mult = "mass-disinformation campaign", general_cap, 0.7

                sev = severity_mult * sens * (relevant_cap / consts.CAP_MAX)
                impact = -30.0 * sev
                incident_id = f"jailbreak_incident_{kind.split()[0]}"

                ev = FiredEvent(
                    incident_id, "misuse", "ordinary",
                    turn, lab.id, m.id, sev, impact,
                    f"High-profile {kind} used a jailbroken {m.id}.",
                    f"{kind} via jailbroken {m.id} (sens {sens:.2f}, capability {relevant_cap:.1f})",
                    effects=[
                        ("add_impact", {"amount": impact}),
                        ("add_world_harm", {"amount": -impact}),
                        ("modify_approval", {"amount": -4.0 * sev - 1.0}),
                        ("modify_wtr", {"amount": 3.0 * sev + 1.0}),
                        ("damage_reputation", {"amount": -5.0 * sev}),
                        ("flag_damaging", {}),
                    ])

                # Liability policy: incidents traced to your back catalog cost cash.
                liability_policy = world.policies.get("incident_liability")
                if liability_policy is not None and liability_policy.active:
                    ev.effects.append(("modify_cash",
                                       {"amount": -consts.LIABILITY_COST_PER_SEVERITY * sev}))

                apply_effects(sb, ev)
                fired.append(ev)
    return fired
