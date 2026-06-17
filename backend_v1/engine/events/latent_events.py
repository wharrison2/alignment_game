"""Armed-latent / scheduled event machinery (§10, first-class).

Canonical case: two-stage jailbreak. Stage 1 (discovery) arms a per-model
latent ∝ TRUE jailbreak-sensitivity; every later quarter rolls the incident.
Jailbreak risk is FLAT, non-decaying, and survives forever (no pull).
"""
from types import SimpleNamespace

from backend_v1.engine.events.event import FiredEvent
from backend_v1.engine.events.effects import apply_effects
from backend_v1.engine.rng import gate


def run_latent_phase(labs, world, flags, rng, consts, dt, turn):
    sb = SimpleNamespace(labs=labs, labs_by_id={l.id: l for l in labs},
                         world=world, flags=flags, rng=rng, consts=consts,
                         dt=dt, turn=turn)
    fired = []
    for lab in labs:
        for m in lab.release_history:
            sens = m.effective_jailbreak_sensitivity()
            # stage 1: technique discovery arms the latent
            if not m.jailbreak_discovered:
                if rng.roll_rate(consts.JAILBREAK_DISCOVERY_RATE * sens, dt):
                    m.jailbreak_discovered = True
                    m.note(turn, "jailbreak_discovered",
                           "jailbreak techniques discovered in the wild "
                           f"(true sensitivity {sens:.2f}) — incidents now roll every quarter")
                    fired.append(FiredEvent(
                        "jailbreak_discovery", "misuse", "ordinary", turn,
                        lab.id, m.id, 0.1, 0.0,
                        f"Researchers publish jailbreak techniques for {m.id}.",
                        f"Discovery armed: sensitivity {sens:.2f} ({'LEAKED — no guardrails' if m.leaked else 'guarded'})",
                        effects=[("modify_approval", {"amount": -1.0})]))
                continue
            # stage 2: armed latent rolls an incident every quarter, forever
            if rng.roll_rate(consts.JAILBREAK_INCIDENT_RATE * sens, dt):
                g, c = m.capability_vec.general, m.capability_vec.coding_rnd
                if g >= consts.BIO_MISUSE_GENERAL_MIN and rng.roll(0.25):
                    kind, capv, mult = "bio/chem uplift attack", g, 2.0
                elif rng.roll(min(0.8, c / consts.CAP_MAX + 0.2)):
                    kind, capv, mult = "cyber attack", c, 1.0
                else:
                    kind, capv, mult = "mass-disinformation campaign", g, 0.7
                sev = mult * sens * (capv / consts.CAP_MAX)
                impact = -30.0 * sev
                ev = FiredEvent(
                    f"jailbreak_incident_{kind.split()[0]}", "misuse", "ordinary",
                    turn, lab.id, m.id, sev, impact,
                    f"High-profile {kind} used a jailbroken {m.id}.",
                    f"{kind} via jailbroken {m.id} (sens {sens:.2f}, capability {capv:.1f})",
                    effects=[
                        ("add_impact", {"amount": impact}),
                        ("add_world_harm", {"amount": -impact}),
                        ("modify_approval", {"amount": -4.0 * sev - 1.0}),
                        ("modify_wtr", {"amount": 3.0 * sev + 1.0}),
                        ("damage_reputation", {"amount": -5.0 * sev}),
                        ("flag_damaging", {}),
                    ])
                # liability policy: incidents traced to your back catalog cost cash
                if world.policies.get("incident_liability") is not None and \
                        world.policies["incident_liability"].active:
                    ev.effects.append(("modify_cash",
                                       {"amount": -consts.LIABILITY_COST_PER_SEVERITY * sev}))
                apply_effects(sb, ev)
                fired.append(ev)
    return fired
