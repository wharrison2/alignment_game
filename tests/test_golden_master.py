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

_OPENING = Action(start_projects=[{"project_id": "generative_pretraining", "ai_assist": 0.0}],
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
# Re-recorded for the plain-language copy pass (ISSUES.md): only ONE digest moved,
# 5-aggressive-impossible, because the event.buyout.public flavor text was reworded
# (it is the one edited string that lands in the TRUE-state log; a buyout only fires
# in that scripted game). All other digests are unchanged. Pure copy reword, no
# mechanics/RNG change; intentional, determinism holds (stable across PYTHONHASHSEED).
# Re-recorded for the "pretrain tree revision" change (ISSUES.md): generative_pretraining
# was added as the root pretrain advance (now the turn-1 opening move), scaling_laws was
# split/renamed to larger_datasets, better_architecture->mixture_of_experts,
# data_efficiency->compute_optimal_scaling, with reworked prereqs and ceiling mults. The
# scripted controller opens with generative_pretraining and picks capability projects from
# the changed catalog, so its action stream and the TRUE trajectory move — an expected
# action-stream change, NOT an RNG/firewall regression (CLAUDE.md §8).
# Re-recorded AGAIN for the "assist/delegation revision" change (ISSUES.md): research_speed_bonus
# removed (dev_tooling now grants assist_potency instead); ai_rnd_assist deleted and its potency
# redistributed onto chain_of_thought/tool_use/long_context (+0.07 each) and multi_agent (+0.30,
# +0.06 elicitation), with multi_agent's prereqs rewired; automated_researcher and
# recursive_self_improvement reclassified to a "delegation" phase with raised contamination_tier.
# These change the scripted action stream (build orders) and the TRUE trajectory — expected
# action-stream change, NOT an RNG/firewall regression (CLAUDE.md §8).
# Re-recorded for the "delegation contamination refinement" change (ISSUES.md): self_preservation
# added to CONTAM_TO_AXES (so all AI-assisted research reproduces it; weights redistributed but
# sum held at 1.0), and the delegation advances (automated_researcher, recursive_self_improvement)
# stripped of elicitation_bonus + eval_awareness_feed (now pure potency + contamination). These
# shift every deep-tree TRUE trajectory; no new RNG draws, determinism holds; firewall green.
# Re-recorded for the "delegation dependency cleanup" change (ISSUES.md): the endgame was rewired
# into a linear chain multi_agent→automated_researcher→recursive_self_improvement→
# novel_architecture_search (novel-arch now gated by RSI; RSI no longer requires novel-arch), and
# the cli/strategies build orders reordered to match. Changes the scripted action stream and the
# deep-tree TRUE trajectory — expected action-stream change, NOT an RNG/firewall regression (§8).
# Re-recorded for the "ASI gate" retune (ISSUES.md): the human-reachable pretrain efficiency tree
# was weakened (~6.4x → ~3.5x) and CEIL_COMPUTE_SCALE raised 14000→20000 so the no-delegation
# ceiling plateaus below the ASI threshold at realistic compute; novel_architecture_search bumped
# to the decisive ×3.0 (delegation-gated); and the late path lengthened (multi_agent/automated_
# researcher/recursive_self_improvement/novel-arch durations up). Shifts every TRUE capability
# trajectory; deterministic, firewall green — expected balance retune, not a regression (§8).
# Re-recorded for the "disclosure defection" change (ISSUES.md): the disclosure mandate became a
# real, defectable policy. Withholding is caught with CERTAINTY (no detection roll) and fined every
# turn (DEFECTION_PENALTY × enforcement × size × dt), via a new enforcement_phase branch. Only ONE
# digest moved, 5-aggressive-impossible — the only scripted game where WTR rises enough for
# disclosure to activate; there a rival's stochastic withholding now SKIPS the per-policy catch roll
# (shifting RNG order) and emits per-turn defection_caught events into the TRUE log (7 of them).
# The other four games never activate disclosure, so their digests are unchanged. Expected behavior
# change, determinism holds, firewall green — NOT an RNG/firewall regression (CLAUDE.md §8).
# Re-recorded again for the "interp-mandate recency window" change (ISSUES.md): interp_mandate_check
# now counts only mechanistic evidence from the last INTERP_MANDATE_RECENCY_YEARS (2 quarters) and
# goes with the MOST RECENT reading, not the worst-ever — so an old bad probe no longer vetoes a
# release forever. Only 5-aggressive-impossible moved: it is the only scripted game where interp_mandate
# both activates AND a release's gating outcome flips under the recency rule, shifting the TRUE
# trajectory. The check uses no RNG (call order unchanged), so this is a pure gating-outcome change.
# The other four games never bind on interp_mandate, so their digests are unchanged.
EXPECTED = {
    "0-balanced-realistic": "fefc9177d9e7a6325ae43d1f8e9043f63c1130a69f64743eff1bd507dfcc8520",
    "3-aggressive-realistic": "282b2a2e000ce53f75567baa93d08353fe6e9be0fdb71a2ec45297297eaaf334",
    "7-cautious-realistic": "d4a0b5f4ed2cdb5a61b5d62c8f5b8ba994f2098e2d4ba2f2c8104b737fc3f751",
    "1-balanced-easy": "2d27a8f8d1caaf0beb351e5bc5b9170d8a4df413ffeeb4a0e43e79823262defe",
    "5-aggressive-impossible": "fe38eae1015fc176b5178a1952c871f5d62e196a31b6f8416c01dbcd6726b545",
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
