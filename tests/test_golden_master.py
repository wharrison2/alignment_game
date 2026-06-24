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
#
# Re-recorded for the "playtest easing" change (ISSUES.md): GOAL_MIS_CREEP 0.035->0.030
# and RIVAL_RECKLESSNESS_MULT["realistic"] 1.0->0.9 (slower, slightly less reckless
# rivals + a touch less misalignment creep). The rival-disposition change shifts the
# rivals' action stream and the creep change shifts TRUE trajectories, so the realistic
# digests move; easy/impossible move only via the creep change. Determinism holds;
# intentional balance change, NOT an RNG/firewall regression (CLAUDE.md §8).
#
# Re-recorded for the "AI-assist inert without a model" fix (ISSUES.md): a research
# process started with no deployed model (lab.current_best_model is None) now stores
# ai_assist=0, because there is no assistant to do the labor. Previously a nonzero
# ai_assist still fed ResearchProcess.tick()'s duration-VARIANCE term even though the
# speedup/contamination were already zero — a no-op control that nonetheless jittered
# completion timing. The scripted controller requests assist before its first release,
# so those early processes now finish on different turns, shifting every downstream
# action/draw and thus every digest. NO new RNG draws (rng.normal() is still drawn
# unconditionally per process per turn); determinism holds (same seed → identical run).
# Intentional behavior fix, NOT an RNG/firewall regression (CLAUDE.md §8).
#
# Re-recorded for the "jailbreak discovery → finding" change (ISSUES.md): stage-1
# jailbreak discovery now injects an existence finding on jailbreak_sensitivity (like
# deception_caught / shutdown_resistance already do) so it surfaces in the Intel
# evidence dossier, feed, and worry bar. The added finding raises the responsible
# lab's worry-bar LEVEL, and RivalController gates a `self.rng.random()` draw on
# `worry_bar.level > 0.45` (short-circuit) — so a crossed threshold both changes the
# action and shifts that controller's own RNG stream, moving every downstream
# decision and thus every digest. No engine-RNG draw was added; determinism holds
# (same seed → identical run). Intentional behavior change, NOT a regression (§8).
#
# Re-recorded for the "creep reduction" change (ISSUES.md): GOAL_MIS_CREEP 0.030->0.025
# (more alignment margin for a clean player at the ASI cliff; still > the 0.02 baseline
# shaping, so the misalignment-by-default fix holds). Lower per-round creep shifts every
# model's TRUE alignment trajectory, so every digest moves. Determinism holds (same seed
# → identical run); intentional balance change, NOT an RNG/firewall regression (§8).
# Re-recorded for the "regulatory appetite" bump (ISSUES.md): WTR_START 4->6,
# WTR_FROM_LOW_APPROVAL 0.35->0.5, POLICY_PASS_BASE 1.1->1.4 (regulation stirs earlier,
# responds faster to harm, passes quicker). Policies enact on different turns, shifting
# the scripted rivals' lobby/litigation decisions and the WTR-driven litigation math, so
# every digest moves. Determinism holds (same seed → identical run); intentional balance
# change, NOT an RNG/firewall regression (CLAUDE.md §8).
# Re-recorded for the "AI-assist needs a model, not a RELEASED model" fix (ISSUES.md):
# assist_potency / the assist plumbing now read lab.assisting_model() (best of the
# released model AND the model in training) instead of lab.current_best_model. The
# scripted controller requests assist on projects it starts while a model is in
# training but nothing is released yet — previously inert, now active — so that pre-
# release window changes budget/duration/contamination and every downstream draw, moving
# every digest. Determinism holds (same seed → identical run); intentional behavior
# change, NOT an RNG/firewall regression (CLAUDE.md §8).
# Re-recorded for the "winnability package" (ISSUES.md "fines->valuation + winnability"):
# (1) NEW fines->valuation lever — labs accumulate fines_paid when caught defecting, and
# lab_score is discounted by fines relative to ~2yr revenue (rewards a clean+compliant
# record, devalues caught reckless defectors); (2) RIVAL_RECKLESSNESS_MULT["realistic"]
# 0.9->0.7 (slower racing so clean play keeps pace); (3) WORK_BUDGET_PER_YEAR 4.0->5.6
# (quarterly pool 1.0->1.4, eases the §9b squeeze so the clean player can juggle
# tree-research + safety + elicitation). These change every lab's score/cash trajectory;
# the fines path adds no new RNG draw (the defection/catch rolls already existed).
# Determinism holds (same seed -> identical run); intentional balance change, NOT an
# RNG/firewall regression (CLAUDE.md §8). Non-trivial verified: no-op player loses 6/6,
# reckless rival mean composite ~0.57 (>bar 6/6) — the misalignment thesis is intact.
#
# Re-recorded AGAIN for the "winnability — completing the win path" changes (ISSUES.md):
# after the fines lever a clean player could reach aligned ASI but kept losing on DOMINANCE
# and the ceiling-9 cash wall. Five more changes, each verified to keep naive play losing
# (no-op AND capability-rush both lose 6/6): (4) fines discount judged against ~2yr REVENUE
# not market cap, FINES_VALUATION_FLOOR 0.35->0.25 (a heavily-fined reckless lab actually
# drops below a clean one); (5) reg-enactment sped up (POLICY_PASS_BASE 1.4->2.6,
# LOBBY_SPEND_K 0.75->1.15, LOBBY_TALLY_DECAY 1.4->1.0) so a CLEVER early-lobbyer can force
# regs active (a naive non-lobbyer still gets dormant regs); (6) COMMISSION_COST_MULT 0.6 —
# a pretrain costs 0.6x its compute in cash, so a cash-constrained clean player can afford
# the ceiling-9 run WITHOUT banking (which had starved its releases); max_run_compute now
# cash/COST_MULT; (7) ASI_DOMINANCE_BOOST 2.5 — the world's first ALIGNED ASI re-rates its
# lab (x2.5 market cap at resolution) so reaching it first translates to the dominance win
# instead of "aligned but dominated". A clever clean+compliant+governance line now WINS
# (demonstrated by hand, seed 2: aligned ASI, +364 impact, dominant); naive play still loses.
# Determinism holds; intentional balance change, NOT an RNG/firewall regression (§8).
#
# Re-recorded AGAIN for "work budget made player-only" (ISSUES.md): the earlier
# WORK_BUDGET_PER_YEAR 4.0->5.6 bump applied to RIVALS too (it speeds their racing — wrong
# direction). Reverted: WORK_BUDGET_PER_YEAR back to 4.0 (rivals = pool 1.0, the baseline),
# and a new PLAYER_WORK_BUDGET_PER_YEAR=5.6 (pool 1.4) on the PLAYER ONLY (game.py) — the
# protagonist lab juggles capability+safety+governance and needs the headroom rivals don't.
# Rivals at 1.0 are slower, so every realistic digest moves. Determinism holds; intentional
# balance change, NOT an RNG/firewall regression (§8).
EXPECTED = {
    "0-balanced-realistic": "1dc477bc5744226966501f6f917318a46e6a04ecb62a0e2171bcfcf5f9941f1f",
    "3-aggressive-realistic": "2d323d414149aa7e126d92db93cef5b941c4cb1f7620efad72c18179f2c312bf",
    "7-cautious-realistic": "bf3ff4abce2f73ada9fb5f04655f44045179a0195cb27aa87c5468db07a024d5",
    "1-balanced-easy": "4a5ff47622fe4109b5ef5e670561951a2c06e2aa97a6c91b0c56cee37e261579",
    "5-aggressive-impossible": "649f2dc04744c0536d08fe441fd7e3bc3d55c76860da662dbaf797d2698b1045",
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
