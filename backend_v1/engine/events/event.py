"""EventDefinition as DATA + the uniform event-phase runner (§10).

Each turn: iterate definitions, evaluate per-target probability from TRUE
state, roll, apply effects. ONE loop regardless of catalog size. Probabilities
read TRUE; the player saw only MEASURED -> events surprise by construction.
Attribution is resolved AT ROLL TIME and stamped on the event object (§0b).
"""
from dataclasses import dataclass, field
from types import SimpleNamespace

from backend_v1.engine.events.effects import apply_effects


@dataclass
class EventDefinition:
    id: str
    category: str            # misuse | misalignment | leak | societal | beneficial
    klass: str               # "existential" | "ordinary"
    target: str              # "released_model" | "lab" | "world"
    rate_fn: object          # (target_obj, sb) -> per-YEAR rate (reads TRUE stats)
    build_fn: object         # (target_obj, sb) -> FiredEvent (severity, effects, text)


@dataclass
class FiredEvent:
    definition_id: str
    category: str
    klass: str
    turn: int
    lab_id: str | None       # causally-responsible lab (attribution, §0b)
    model_id: str | None
    severity: float
    impact: float
    public_text: str         # what the world/player sees
    true_text: str           # what actually happened (post-mortem)
    effects: list = field(default_factory=list)   # [(effect_name, params)]
    public: bool = True


def run_event_phase(ctx, definitions):
    """Returns list of FiredEvents. Rival existential events are suppressed
    unless the rival holds a BIG capability lead (§10 frontier rule)."""
    sb = ctx
    labs, world, flags = ctx.labs, ctx.world, ctx.flags
    rng, consts, dt, turn = ctx.rng, ctx.consts, ctx.dt, ctx.turn
    fired = []
    # The "human frontier" the §10 frontier rule compares AI rivals against:
    # the best true general across ALL human labs (solo: the player's). Chosen
    # default for multiplayer — see ISSUES.md.
    human_frontier_best = max(lab.best_true_general() for lab in ctx.human_labs)

    for d in definitions:
        if d.target == "released_model":
            targets = [(lab, m) for lab in labs for m in lab.release_history]
        elif d.target == "lab":
            targets = [(lab, None) for lab in labs]
        else:
            targets = [(None, None)]

        for lab, model in targets:
            tgt = SimpleNamespace(lab=lab, model=model)

            rate = d.rate_fn(tgt, sb)
            if rate <= 0:
                continue
            if not rng.roll_rate(rate, dt):
                continue

            ev = d.build_fn(tgt, sb)
            if ev is None:
                continue

            # frontier rule: rivals can't cause game-enders without a big lead
            rival_existential = (
                ev.klass == "existential"
                and lab is not None
                and not lab.is_player
            )
            if rival_existential:
                rival_best = lab.best_true_general()
                rival_lacks_decisive_lead = rival_best < human_frontier_best + consts.RIVAL_BIG_LEAD
                if rival_lacks_decisive_lead:
                    ev.klass = "ordinary"
                    ev.severity *= 0.5
                    ev.impact *= 0.3
                    ev.effects = [e for e in ev.effects
                                  if e[0] not in ("trigger_existential_gate", "end_game")]
                    ev.true_text += " (contained: the lab lacked a decisive lead)"

            apply_effects(sb, ev)
            fired.append(ev)
    return fired
