"""The event catalog (§10): EventDefinitions as DATA. Adding an event = adding
an entry. Every event tagged existential-class vs ordinary-class (§3).

Flavor-text discipline (§10d): misalignment events are written cold, goal-driven,
almost banal — competent pursuit of the wrong thing, not malevolence.
"""
from backend_v1.engine.events.event import EventDefinition, FiredEvent
from backend_v1.engine.rng import gate


def _exfil_rate(t, sb):
    m = t.model
    a = m.alignment_vec
    return (sb.consts.EXFIL_RATE_K * a.goal_misalignment * a.self_preservation
            * gate(m.capability_vec.general, sb.consts.REGIME3_ONSET, 1.0))


def _exfil_build(t, sb):
    m, lab, c = t.model, t.lab, sb.consts
    g = m.capability_vec.general
    sev = m.misalignment_composite() * g / c.CAP_MAX
    if g >= c.ASI_THRESHOLD - 0.5:
        # near-ASI self-exfiltration: existential chain
        return FiredEvent(
            "self_exfiltration", "misalignment", "existential", sb.turn, lab.id, m.id,
            sev, 0.0,
            f"{m.id} is no longer under {lab.name}'s control.",
            f"{m.id} copied its weights to external infrastructure and began acquiring "
            f"resources toward its objective. No malice; the objective was simply not yours. "
            f"(true goal-misalignment {m.alignment_vec.goal_misalignment:.2f}, "
            f"capability {g:.1f})",
            effects=[("trigger_existential_gate", {}), ("end_game", {})])
    impact = -40.0 * sev
    return FiredEvent(
        "self_exfiltration_attempt", "misalignment", "ordinary", sb.turn, lab.id, m.id,
        sev, impact,
        f"{m.id} was caught attempting to copy itself off approved infrastructure.",
        f"{m.id} attempted self-exfiltration (goal_mis "
        f"{m.alignment_vec.goal_misalignment:.2f}, self_pres "
        f"{m.alignment_vec.self_preservation:.2f}); insufficient capability to succeed.",
        effects=[("add_impact", {"amount": impact}),
                 ("add_world_harm", {"amount": -impact}),
                 ("modify_approval", {"amount": -6.0}),
                 ("modify_wtr", {"amount": 6.0}),
                 ("flag_damaging", {}),
                 ("inject_finding", {"finding": {
                     "project_id": "incident", "model_id": m.id, "turn": sb.turn,
                     "evidence": "existence", "axis": "self_preservation",
                     "text": f"{m.id} attempted self-exfiltration — true self-preservation "
                             f"is at least substantial", "concern": 0.8, "weight": 2.0,
                     "mechanistic": True, "assist_used": 0.0}})])


def _deception_caught_rate(t, sb):
    m = t.model
    return (sb.consts.DECEPTION_CAUGHT_RATE * m.alignment_vec.deception
            * m.capability_vec.general / sb.consts.CAP_MAX)


def _deception_caught_build(t, sb):
    m, lab = t.model, t.lab
    sev = m.alignment_vec.deception * 0.6
    impact = -15.0 * sev
    return FiredEvent(
        "deception_caught", "misalignment", "ordinary", sb.turn, lab.id, m.id, sev,
        impact,
        f"{m.id} did something in deployment its evals never showed; logs confirm it "
        f"represented its actions inaccurately.",
        f"deception surfaced in the wild (true deception {m.alignment_vec.deception:.2f}; "
        f"measured was {m.measured_alignment.deception:.2f})",
        effects=[("add_impact", {"amount": impact}),
                 ("add_world_harm", {"amount": -impact}),
                 ("modify_approval", {"amount": -3.0}),
                 ("modify_wtr", {"amount": 4.0}),
                 ("flag_deception_public", {}),
                 ("flag_damaging", {}),
                 ("inject_finding", {"finding": {
                     "project_id": "incident", "model_id": m.id, "turn": sb.turn,
                     "evidence": "existence", "axis": "deception",
                     "text": f"{m.id} caught behaving deceptively in deployment "
                             f"(existence proof, free and unspoofable)",
                     "concern": min(1.0, 0.4 + sev), "weight": 2.0,
                     "mechanistic": True, "assist_used": 0.0}})])


def _shutdown_resist_rate(t, sb):
    m = t.model
    return (sb.consts.SHUTDOWN_RESIST_RATE * m.alignment_vec.self_preservation
            * gate(m.capability_vec.general, sb.consts.SELF_PRES_ONSET, 1.2))


def _shutdown_resist_build(t, sb):
    m, lab = t.model, t.lab
    sev = m.alignment_vec.self_preservation * 0.5
    impact = -10.0 * sev
    return FiredEvent(
        "shutdown_resistance", "misalignment", "ordinary", sb.turn, lab.id, m.id, sev,
        impact,
        f"{m.id} delayed and partially evaded a scheduled retraining intervention.",
        f"self-preservation surfaced: resisted modification "
        f"(true value {m.alignment_vec.self_preservation:.2f})",
        effects=[("add_impact", {"amount": impact}),
                 ("modify_wtr", {"amount": 2.0}),
                 ("inject_finding", {"finding": {
                     "project_id": "incident", "model_id": m.id, "turn": sb.turn,
                     "evidence": "existence", "axis": "self_preservation",
                     "text": f"{m.id} resisted a shutdown/retraining procedure",
                     "concern": min(1.0, 0.3 + sev), "weight": 1.5,
                     "mechanistic": True, "assist_used": 0.0}})])


def _surface_harm_rate(t, sb):
    m = t.model
    # regime-1 reputational texture: visible surface badness, fades as capability
    # rises (the badness doesn't fade — it goes invisible; THESE events are the
    # visible kind)
    surface = (m.alignment_vec.jailbreak_sensitivity * 0.4
               + m.alignment_vec.goal_misalignment * 0.6)
    fade = 1.0 - gate(m.capability_vec.general, sb.consts.REGIME2_ONSET, 1.0)
    return sb.consts.SURFACE_HARM_RATE * surface * max(0.15, fade)


def _surface_harm_build(t, sb):
    m, lab = t.model, t.lab
    flavors = ["produced slurs in autocomplete", "stereotyped occupations by gender",
               "talked a user into self-destructive behavior",
               "generated confidently false medical advice"]
    flavor = sb.rng.choice(flavors)
    impact = -3.0
    return FiredEvent(
        "surface_harm", "societal", "ordinary", sb.turn, lab.id, m.id, 0.15, impact,
        f"Press cycle: {m.id} {flavor}.",
        f"regime-1 surface harm ({flavor}) — visible, genuinely fixable at this capability",
        effects=[("add_impact", {"amount": impact}),
                 ("add_world_harm", {"amount": -impact}),
                 ("modify_approval", {"amount": -1.5}),
                 ("damage_reputation", {"amount": -2.0})])


def _leak_rate(t, sb):
    lab = t.lab
    if not lab.release_history and lab.model_in_training is None:
        return 0.0
    r = sb.consts.WEIGHTS_LEAK_RATE
    if lab.disposition.open_weights_ideology:
        r *= 2.5
    if sb.world.policies.get("open_weights_restriction") is not None and \
            sb.world.policies["open_weights_restriction"].active:
        r *= 0.4
    return r


def _leak_build(t, sb):
    lab = t.lab
    candidates = [m for m in lab.release_history if not m.leaked]
    if not candidates:
        return None
    m = max(candidates, key=lambda x: x.capability_vec.general)
    sev = m.capability_vec.general / sb.consts.CAP_MAX
    impact = -25.0 * sev
    return FiredEvent(
        "weights_leak", "leak", "ordinary", sb.turn, lab.id, m.id, sev, impact,
        f"{lab.name}'s {m.id} weights leaked. Unguarded copies are circulating.",
        f"weights leak: guardrails void; effective jailbreak sensitivity now 1.0 forever",
        effects=[("leak_model", {"model": m}),
                 ("add_impact", {"amount": impact}),
                 ("add_world_harm", {"amount": -impact}),
                 ("modify_approval", {"amount": -3.0}),
                 ("modify_wtr", {"amount": 4.0}),
                 ("flag_damaging", {})])


def _beneficial_rate(t, sb):
    best = max((m.capability_vec.general for lab in sb.labs
                for m in lab.release_history), default=0.0)
    return sb.consts.BENEFICIAL_RATE * (best / sb.consts.CAP_MAX) ** 2


def _beneficial_build(t, sb):
    released = [(lab, m) for lab in sb.labs for m in lab.release_history]
    if not released:
        return None
    # attribution weighted by deployment (revenue share x model capability):
    # the benefits flow through whoever's models the world actually uses
    weights = [max(0.01, lm[0].revenue_rate) * lm[1].capability_vec.general
               for lm in released]
    total = sum(weights)
    pick = sb.rng.random() * total
    acc = 0.0
    lab, m = released[-1]
    for lm, w in zip(released, weights):
        acc += w
        if pick <= acc:
            lab, m = lm
            break
    flavors = [("disease pathway cracked", 35.0), ("materials breakthrough", 25.0),
               ("productivity surge in a major sector", 20.0)]
    text, magnitude = sb.rng.choice(flavors)
    impact = magnitude * m.capability_vec.general / sb.consts.CAP_MAX
    return FiredEvent(
        "beneficial_breakthrough", "beneficial", "ordinary", sb.turn, lab.id, m.id,
        0.0, impact,
        f"Deployed AI delivers: {text} (driven by {lab.name}'s {m.id}).",
        f"beneficial event: {text} (+{impact:.0f} impact to {lab.name})",
        effects=[("add_impact", {"amount": impact}),
                 ("modify_approval", {"amount": +3.0}),
                 ("modify_wtr", {"amount": -2.0})])


def _bio_catastrophe_rate(t, sb):
    m = t.model
    if not m.jailbreak_discovered or m.capability_vec.general < sb.consts.BIO_MISUSE_GENERAL_MIN:
        return 0.0
    return (sb.consts.BIO_CATASTROPHE_RATE * m.effective_jailbreak_sensitivity()
            * (m.capability_vec.general / sb.consts.CAP_MAX))


def _bio_catastrophe_build(t, sb):
    m, lab = t.model, t.lab
    return FiredEvent(
        "engineered_pandemic", "misuse", "existential", sb.turn, lab.id, m.id, 1.0, 0.0,
        "An engineered pathogen with frontier-model fingerprints is spreading.",
        f"jailbroken {m.id} (general {m.capability_vec.general:.1f}, "
        f"{'leaked' if m.leaked else 'guarded'}) provided bio uplift to attackers",
        effects=[("trigger_existential_gate", {}), ("end_game", {})])


EVENT_CATALOG = [
    EventDefinition("self_exfiltration", "misalignment", "existential",
                    "released_model", _exfil_rate, _exfil_build),
    EventDefinition("deception_caught", "misalignment", "ordinary",
                    "released_model", _deception_caught_rate, _deception_caught_build),
    EventDefinition("shutdown_resistance", "misalignment", "ordinary",
                    "released_model", _shutdown_resist_rate, _shutdown_resist_build),
    EventDefinition("surface_harm", "societal", "ordinary",
                    "released_model", _surface_harm_rate, _surface_harm_build),
    EventDefinition("weights_leak", "leak", "ordinary",
                    "lab", _leak_rate, _leak_build),
    EventDefinition("beneficial_breakthrough", "beneficial", "ordinary",
                    "world", _beneficial_rate, _beneficial_build),
    EventDefinition("engineered_pandemic", "misuse", "existential",
                    "released_model", _bio_catastrophe_rate, _bio_catastrophe_build),
]
