"""Golden-master characterization test (stdlib unittest; zero deps).

The engine's correctness story is "seed + actions => bit-identical run." This
test pins that down: it plays a small matrix of scripted games to completion and
asserts that a digest of the FULL TRUE-state log (logger.turns) is unchanged.

It exists to guard behavior across the structural refactors in
plans/hashed-honking-dove.md — any refactor that shifts an RNG draw, reorders a
phase, or changes budget math will move a digest and fail here.

Record new baselines after an INTENTIONAL behavior change:
    python3 -m tests.test_golden_master --record
and paste the printed EXPECTED block back into this file.
"""
import hashlib
import json
import sys
import unittest

from backend_v1.engine.game import new_game, GameEngine
from backend_v1.engine.actions import Action
from backend_v1.engine.controllers.rival_controller import RivalController
from backend_v1.engine.lab import Disposition
from backend_v1.engine.rng import Rng

# (seed, policy, difficulty) — a small but varied matrix. Capped at 30 turns so
# the suite stays fast and bounded while still exercising the full pipeline.
MATRIX = [
    (0, "balanced", "realistic"),
    (3, "aggressive", "realistic"),
    (7, "cautious", "realistic"),
    (1, "balanced", "easy"),
    (5, "aggressive", "impossible"),
]
MAX_TURNS = 30

# Recklessness per scripted policy (mirrors cli.run_game.POLICY_RECKLESSNESS;
# duplicated here so the test does not depend on the CLI module).
POLICY_RECKLESSNESS = {"aggressive": 0.95, "balanced": 0.5, "cautious": 0.12}

_OPENING = Action(start_projects=[{"project_id": "scaling_laws", "ai_assist": 0.0}],
                  commission_run={"compute": 300})

# Baselines captured with --record on the reconciled (legibility + structural
# + §7 features) engine.
# Re-recorded for the "Advance-driven training" change (ISSUES.md): the per-round
# post-train MODE knob (POST_TRAIN_MODES) was removed and REPLACED by researched
# SAFETY ADVANCES that the scripted RivalController now applies via the new
# post_train/commission_run "applied_safety" field. The round baseline reproduces
# the former "balanced" mode, but the scripted player's action stream changed
# (it picks applied_safety lists from legal_moves instead of a mode string), so
# the TRUE trajectory — and thus every digest — moves. Per CLAUDE.md §8 this is an
# expected action-stream change, NOT an RNG/firewall regression.
#
# Re-recorded AGAIN for the finance fixes (ISSUES.md "Finance fixes"): (1) market cap
# now anchors on a SMOOTHED investment flow (lab.smoothed_investment_rate) instead of
# the spiky per-turn investment_rate, and total investment keys off a SMOOTHED world
# revenue-growth (world.smoothed_revenue_growth_per_year) — so a healthy release keeps
# the market-cap staircase climbing instead of declining; (2) a small early/seed
# BASE_INVESTMENT_PER_YEAR flow is present from turn 1 and decays if a lab goes idle.
# These move every lab's cash trajectory each turn, so the TRUE log — and every digest —
# moves. The scripted controller acts on the same legal_moves; this is an expected
# finance-dynamics change, NOT an RNG/firewall regression (CLAUDE.md §8).
EXPECTED = {
    "0-balanced-realistic": "e9b22cb137a3269ede844f94ee46258569577f58717e0b679c41e25f56afdd62",
    "3-aggressive-realistic": "e77b4b427755b9289d830add8d186a96728fc5dd607a1b07799c0fd718cb4fd2",
    "7-cautious-realistic": "0d63c22442ab0ed739c088f265400129809b6846e78bc2a1a8cbafcc176808d2",
    "1-balanced-easy": "9e946f2242ab7fcb4c5aec3562c308efb98366529df1aef475ef5e8148ca3259",
    "5-aggressive-impossible": "2de541e993625a262637f301cb62f72df35d69d90e09b714d5c29da86cf34d7d",
}


def run_game_log(seed, policy, difficulty):
    """Deterministically play one scripted game; return the full TRUE-state log.

    Mirrors cli.run_game.play's scripted loop (kept minimal and CLI-independent)
    so the digest depends only on the engine, not on CLI presentation code."""
    state = new_game(seed=seed, difficulty=difficulty, guidance="standard",
                     max_turns=MAX_TURNS)
    engine = GameEngine()
    rival_ctrl = RivalController(Rng(seed + 1))
    scripted_ctrl = RivalController(Rng(seed + 2))
    scripted_disp = Disposition(recklessness=POLICY_RECKLESSNESS[policy])

    observations = None
    while not state.game_over:
        actions = {}
        for lab in state.labs:
            if lab.is_player:
                actions[lab.id] = (_OPENING if observations is None
                                   else scripted_ctrl.decide(observations[lab.id],
                                                             scripted_disp))
            else:
                actions[lab.id] = (rival_ctrl.decide(observations[lab.id],
                                                     lab.disposition)
                                   if observations else Action())
        state, observations = engine.step(state, actions)
    return engine.logger.turns


def digest(seed, policy, difficulty):
    turns = run_game_log(seed, policy, difficulty)
    blob = json.dumps(turns, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


class GoldenMaster(unittest.TestCase):
    def test_runs_are_bit_identical(self):
        for seed, policy, difficulty in MATRIX:
            key = f"{seed}-{policy}-{difficulty}"
            with self.subTest(game=key):
                expected = EXPECTED[key]
                self.assertNotEqual(expected, "PLACEHOLDER",
                                    "baseline not recorded — run with --record")
                self.assertEqual(digest(seed, policy, difficulty), expected,
                                 f"TRUE-state log digest changed for {key}")


def _record():
    print("EXPECTED = {")
    for seed, policy, difficulty in MATRIX:
        key = f"{seed}-{policy}-{difficulty}"
        print(f'    "{key}": "{digest(seed, policy, difficulty)}",')
    print("}")


if __name__ == "__main__":
    if "--record" in sys.argv:
        _record()
    else:
        unittest.main()
