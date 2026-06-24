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
#
# Re-recorded for the "Research/intervention item cleanup" change (ISSUES.md): the
# capability tech tree was trimmed of five non-design-doc filler advances
# (moe_scaling, inference_scaling, continual_learning, agentic_rl, neuralese),
# their distinct hooks folded into surviving items, a couple of items renamed, and
# a second tooling advance (serving_infra) added. The scripted controller picks
# capability projects from legal_moves, so a changed catalog shifts its action
# stream and the TRUE trajectory — an expected action-stream change, NOT an
# RNG/firewall regression (CLAUDE.md §8).
#
# Re-recorded for the "investor-sentiment noise on the investment score" change
# (ISSUES.md): run_investment now multiplies each lab's score by a per-turn
# max(0, 1+N(0, SCORE_NOISE_STD)) factor before divvying the pie. That is one new
# seeded-RNG draw per lab per turn, which both jitters the cash trajectory AND
# shifts every downstream draw in the stream — so every digest moves. Determinism
# holds (same seed → identical run); this is an intentional RNG-draw change, NOT a
# regression (CLAUDE.md §0.4, §8).
#
# Re-recorded for the "market caps plateau after releases" fixes (ISSUES.md): four
# finance-dynamics changes — (A) the rising-target bar is scaled by remaining
# headroom to CAP_MAX; (B) a release that misses the bar now decays investment
# momentum gently instead of hard-resetting it; (C) a ratcheting market-cap floor
# tracks cumulative realized revenue; (D) investment growth and the score's level
# term are judged against a lab's best-EVER release, not its latest. These change
# every lab's score / market-cap / cash trajectory each turn. NO new RNG draws were
# added (the ratchet uses revenue_rate*dt; the rest is deterministic arithmetic),
# so the move is the intended finance change, NOT an RNG/firewall regression (§8).
#
# Re-recorded for the "misalignment-by-default retune" change (ISSUES.md): five
# emergence/shaping constants were retuned so reckless labs trend misaligned per the
# §0 thesis (BASE_SHAPING_EFFORT 0.12->0.02, GOAL_MIS_CREEP 0.016->0.035,
# SELF_PRES_RATE 0.035->0.08, SELF_PRES_ONSET 4.5->3.5, JUMP_BASE_P 0.02->0.04).
# These change every model's TRUE alignment trajectory each post-train round, so the
# TRUE log — and every digest — moves. The scripted controller acts on the same
# legal_moves (action stream unchanged); determinism holds (same seed → identical
# run). Intentional balance change, NOT an RNG/firewall regression (CLAUDE.md §8).
EXPECTED = {
    "0-balanced-realistic": "e2ae74ed8a943dce38bd65cfd37f9d6934eec2aaae094926718e081c66aaf22b",
    "3-aggressive-realistic": "f2c0ffa64a3818074c1e1ad6100bc3d4968b687f035c8c3d8a404902d3f612af",
    "7-cautious-realistic": "bc44f3e6b4d55db98be9208237f749c73c1d625b5e9b50d695e442d931c9f089",
    "1-balanced-easy": "f56c8f1e2cd970563f155e906d091807ec4f51b8d81677a3842ced91e7bceb3f",
    "5-aggressive-impossible": "cb3b6a4167a902cb9d6b1ae77f6ca79c950594bcf1ea18938c2c7f47d3217981",
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
