"""GameState (DATA) + GameEngine (stateless step) — §11 decision.

GameState is the complete TRUE world; the engine orchestrates the turn
pipeline and builds per-actor observations. step() mutates the passed state in
place and returns (state, observations) — replayability comes from seed +
action log, not structural immutability (see NOTES.md).
"""
from dataclasses import dataclass, field

from backend_v1.config.difficulty import build_constants
from backend_v1.engine.rng import Rng
from backend_v1.engine.lab import Lab, Disposition
from backend_v1.engine.world import World
from backend_v1.engine.turn_pipeline import run_turn
from backend_v1.engine.logger import GameLogger
from backend_v1.engine.observation.observation_builder import build_observation
from backend_v1.engine.observation.guidance import collect_tips


@dataclass
class GameState:
    consts: object
    rng: Rng
    dt: float
    max_turns: int | None       # None = uncapped (play to ASI or catastrophe)
    labs: list
    world: World
    guidance: str = "standard"
    turn: int = 0
    game_over: bool = False
    outcome: dict | None = None
    # public record shared by all observers this turn
    last_events: list = field(default_factory=list)


def new_game(seed=0, difficulty="realistic", guidance="standard",
             rival_count=None, max_turns=None) -> GameState:
    consts = build_constants(difficulty)
    rng = Rng(seed)
    n = rival_count if rival_count is not None else consts.RIVAL_COUNT
    labs = [Lab(id="player", name="Your Lab", is_player=True,
                cash=consts.STARTING_CASH,
                work_budget_per_year=consts.WORK_BUDGET_PER_YEAR)]
    names = ["Mistreal", "OpenBrain", "Anthropos", "DeepThink", "Cypher"]
    for i in range(n):
        reck, cost, ow = consts.RIVAL_DISPOSITIONS[i % len(consts.RIVAL_DISPOSITIONS)]
        labs.append(Lab(
            id=f"rival{i+1}", name=names[i % len(names)],
            cash=consts.STARTING_CASH * rng.uniform(0.8, 1.2),
            work_budget_per_year=consts.WORK_BUDGET_PER_YEAR,
            disposition=Disposition(recklessness=reck, cost_advantage=cost,
                                    open_weights_ideology=ow)))
    world = World(public_approval=consts.APPROVAL_START, wtr=consts.WTR_START)
    return GameState(consts=consts, rng=rng, dt=consts.DT_YEARS,
                     max_turns=max_turns, labs=labs, world=world,
                     guidance=guidance)


class GameEngine:
    def __init__(self):
        self.logger = GameLogger()

    def step(self, state: GameState, actions: dict):
        """actions: {lab_id: Action}. Returns (state, {lab_id: Observation})."""
        if state.game_over:
            raise RuntimeError("game is over")
        state.turn += 1
        result = run_turn(state, actions)
        state.last_events = result["events"]
        self.logger.record(state, actions, result["events"])

        player = next(l for l in state.labs if l.is_player)
        tips = collect_tips(state, player)   # public; guidance level applies
        observations = {}
        for lab in state.labs:
            observations[lab.id] = build_observation(
                state, lab, tips if lab.is_player else [],
                result["policy_news"], result["events"],
                result["new_findings"][lab.id])
        return state, observations
