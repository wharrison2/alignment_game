"""Firewall audit (stdlib unittest; zero deps) — the §2 true/measured boundary.

The observation builder is the ONE chokepoint that crosses the hidden/observed
boundary (CLAUDE.md §2). This test plays a scripted game far enough that the
player has COMPLETED research advances and a model in training, then walks the
FULL player observation dict (including legal_moves) and asserts that no hidden
TRUE-state KEY ever crosses.

Per CLAUDE.md §8: audit by KEY, not by substring. Grepping the JSON for "true"
or "concealment" gives false positives (JSON booleans serialize as `true`; the
word "concealment" appears in player-facing prose). The real firewall question is
whether a forbidden KEY is present anywhere in the structure.
"""
import unittest

from backend_v1.engine.game import new_game, GameEngine
from backend_v1.engine.actions import Action
from backend_v1.engine.controllers.rival_controller import RivalController
from backend_v1.engine.lab import Disposition
from backend_v1.engine.rng import Rng

# Keys that must NEVER cross the observation boundary. These are TRUE / hidden
# state: the unfiltered alignment & capability vectors, the §5b concealment, the
# foundational floor and suppression, the post-mortem-only hidden history, and the
# §8b ResearchedItem secrets (contamination + who/how it was researched).
FORBIDDEN_KEYS = {
    "true_alignment",
    "true_capability",
    "concealment",
    "foundational_floor",
    "suppression",
    "hidden_history",
    "contamination",
    "researcher_model_id",
    "researched_with_assist",
}

MAX_TURNS = 30
SCRIPTED_RECKLESSNESS = 0.5   # "balanced" — researches advances AND trains a model


def _forbidden_keys_in(value, path="observation"):
    """Walk a nested dict/list structure and return the path of any forbidden KEY
    found (empty list = clean). We check KEYS only: a value that happens to equal a
    forbidden word is fine; a KEY that names hidden state is the leak."""
    leaks = []
    if isinstance(value, dict):
        for key, sub_value in value.items():
            if key in FORBIDDEN_KEYS:
                leaks.append(f"{path}.{key}")
            leaks += _forbidden_keys_in(sub_value, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            leaks += _forbidden_keys_in(item, f"{path}[{index}]")
    return leaks


def _play_player_observations(seed):
    """Play a scripted balanced game to completion; collect the player's observation
    each turn so the audit sees the boundary at every game state (idle, researching,
    training, released, game-over)."""
    state = new_game(seed=seed, difficulty="realistic", guidance="standard",
                     max_turns=MAX_TURNS)
    engine = GameEngine()
    rival_ctrl = RivalController(Rng(seed + 1))
    scripted_ctrl = RivalController(Rng(seed + 2))
    scripted_disp = Disposition(recklessness=SCRIPTED_RECKLESSNESS)
    opening = Action(start_projects=[{"project_id": "generative_pretraining", "ai_assist": 0.0}],
                     commission_run={"compute": 300})

    player_observations = []
    observations = None
    while not state.game_over:
        actions = {}
        for lab in state.labs:
            if lab.is_player:
                actions[lab.id] = (opening if observations is None
                                   else scripted_ctrl.decide(observations[lab.id],
                                                             scripted_disp))
            else:
                actions[lab.id] = (rival_ctrl.decide(observations[lab.id],
                                                     lab.disposition)
                                   if observations else Action())
        state, observations = engine.step(state, actions)
        player_lab = next(lab for lab in state.labs if lab.is_player)
        player_observations.append(observations[player_lab.id].to_dict())
    return player_observations


class ObservationFirewall(unittest.TestCase):
    def test_no_forbidden_key_crosses_the_boundary(self):
        for seed in (0, 3, 7):
            player_observations = _play_player_observations(seed)
            self.assertTrue(player_observations, "no observations produced")
            for turn_index, observation in enumerate(player_observations):
                leaks = _forbidden_keys_in(observation, f"obs[seed{seed}/t{turn_index}]")
                self.assertEqual(
                    leaks, [],
                    f"firewall leak: forbidden key(s) crossed the boundary: {leaks}")

    def test_researched_advances_emit_only_non_secret_fields(self):
        """The Part-1 addition: completed advances cross as read-only cards. Assert
        the per-advance payload carries ONLY the allow-listed non-secret fields."""
        allowed_fields = {"id", "name", "version", "phase", "kind",
                          "what_it_does", "completed_turn"}
        saw_a_completed_advance = False
        for observation in _play_player_observations(seed=0):
            for advance in observation["researched_advances"]:
                saw_a_completed_advance = True
                extra_fields = set(advance) - allowed_fields
                self.assertEqual(
                    extra_fields, set(),
                    f"researched-advance card leaked extra field(s): {extra_fields}")
        self.assertTrue(saw_a_completed_advance,
                        "scripted game completed no advances — test never exercised "
                        "the researched_advances path")


if __name__ == "__main__":
    unittest.main()
