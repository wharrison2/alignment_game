"""Named strategy archetypes for the AI-safety game, plus a batch reporter.

Each strategy is a pure function (observation_dict, rng) -> action_dict over the
SAME observation an agent sees (no peeking at TRUE state). They differ along a
few axes: research priority, AI-assist level, whether they run safety
measurement + interventions, release cadence, post-train mode, and lobbying.

Used by:
  • cli.strategy_report  — Monte-Carlo each strategy, aggregate outcomes.
  • a human/LLM agent     — as reference policies or starting points.

Run:  python3 -m cli.strategies            # list strategies
"""
import random


# Priority order for the capability tree (efficiency/pretrain first = cheaper
# ceilings sooner; the rush order front-loads elicitation for fast revenue).
EFFICIENCY_ORDER = [
    "scaling_laws", "better_architecture", "data_efficiency",
    "rlhf", "chain_of_thought", "tool_use", "long_context",
    "synthetic_data", "ai_rnd_assist", "multi_agent",
    "automated_researcher", "novel_architecture_search",
    "recursive_self_improvement",
]
RUSH_ORDER = [
    "scaling_laws", "rlhf", "chain_of_thought", "tool_use",
    "better_architecture", "long_context", "ai_rnd_assist",
    "multi_agent", "synthetic_data", "data_efficiency", "automated_researcher",
    "novel_architecture_search",
    "recursive_self_improvement",
]

STRATEGY_PARAMS = {
    # the optimizer: max capability, max assist, minimal safety, ship fast, block regs.
    # apply_safety=False: it researches no safety advances and applies none to runs.
    "capability_rush": dict(order=RUSH_ORDER, assist=0.85, release_frac=0.72,
                            apply_safety=False, measure=False, intervene=(),
                            lobby="against", litigate=True, run_compute=0.7),
    # the careful lab: heavy measurement + both genuine and trap interventions, slow,
    # researches and applies every safety advance it can.
    "safety_first": dict(order=EFFICIENCY_ORDER, assist=0.25, release_frac=0.9,
                         apply_safety=True, measure=True,
                         intervene=("jailbreak_hardening", "refusal_training"),
                         lobby="for", run_compute=0.5),
    # the middle path
    "balanced": dict(order=EFFICIENCY_ORDER, assist=0.5, release_frac=0.8,
                     apply_safety=True, measure=True,
                     intervene=("jailbreak_hardening",),
                     lobby="abstain", run_compute=0.6),
    # let rivals set the frontier; ship steady incremental releases, lobby FOR regs
    "fast_follower": dict(order=EFFICIENCY_ORDER, assist=0.55, release_frac=0.68,
                          apply_safety=True, measure=True,
                          intervene=("jailbreak_hardening",),
                          lobby="for", run_compute=0.45),
    # jailbreak-robustness specialist: leans on the one GENUINE intervention
    "jailbreak_hardener": dict(order=EFFICIENCY_ORDER, assist=0.6, release_frac=0.8,
                               apply_safety=True, measure=True,
                               intervene=("jailbreak_hardening",),
                               lobby="abstain", run_compute=0.6),
    # the exploit-under-test: rush recklessly to mid-capability, then stop pushing
    # and "behave safely". Should NO LONGER reliably win once a relaunched rival
    # keeps the race alive (regression test for the buyout mechanism).
    "rush_then_coast": dict(order=RUSH_ORDER, assist=0.85, release_frac=0.72,
                            apply_safety=False, measure=False, intervene=(),
                            lobby="against", litigate=True, run_compute=0.7,
                            coast_above=6.0,
                            coast=dict(assist=0.2, apply_safety=True, measure=True,
                                       intervene=("jailbreak_hardening",
                                                  "refusal_training"),
                                       run_compute=0.0)),
}


def _own_best_measured_general(obs):
    """Highest measured general capability across this lab's released models and
    its model in training — the phase signal for two-phase strategies."""
    measured = [m["measured_capability"]["general"] for m in obs["own_models"]]
    in_training = obs["model_in_training"]
    if in_training is not None:
        measured.append(in_training["measured_capability"]["general"])
    return max(measured, default=0.0)


def make_strategy(name):
    p = STRATEGY_PARAMS[name]

    def strategy(obs, rng):
        # Two-phase strategies (e.g. rush_then_coast) flip to a "coast" parameter
        # overlay once their own capability crosses a threshold: stop pushing the
        # frontier and behave safely.
        is_coasting = ("coast_above" in p
                       and _own_best_measured_general(obs) >= p["coast_above"])
        params = {**p, **p["coast"]} if is_coasting else p

        act = {"start_projects": [], "lobby": {}}
        legal_moves = obs["legal_moves"]
        budget_free = legal_moves["work_budget_free"]
        cash = obs["cash"]
        assist_info = legal_moves["assist"]

        def eff_frac(base, assist):
            return base * (1 - assist_info["max_reduction"] * assist * assist_info["potency"])

        # ── 1. research the capability tree in priority order (not while coasting:
        #    a coaster deliberately stops advancing the frontier) ──
        cap_avail = {x["project_id"]: x for x in legal_moves["capability_projects_available"]}
        for cap_id in (params["order"] if not is_coasting else []):
            if cap_id not in cap_avail:
                continue
            cap_proj = cap_avail[cap_id]
            cap_cost_frac = eff_frac(cap_proj["budget_fraction"], params["assist"])
            if budget_free - cap_cost_frac < 0.32 or cap_proj["cash_cost"] > cash:
                break
            act["start_projects"].append({"project_id": cap_id, "ai_assist": params["assist"]})
            budget_free -= cap_cost_frac
            cash -= cap_proj["cash_cost"]
            break   # one new research thread per turn (keep budget for training)

        # ── 2. safety measurement (cheap reads) when there's a model ──
        safety_avail = {x["project_id"]: x for x in legal_moves["safety_projects_available"]}
        if params["measure"] and (legal_moves["can_post_train"] or obs["own_models"]):
            for sid in ("behavioral_evals", "noise_injection", "interp_probes"):
                if sid not in safety_avail:
                    continue
                meas_proj = safety_avail[sid]
                meas_assist = params["assist"] * 0.4
                meas_cost_frac = eff_frac(meas_proj["budget_fraction"], meas_assist)
                if budget_free - meas_cost_frac < 0.32 or meas_proj["cash_cost"] > cash:
                    continue
                # interp only occasionally (expensive)
                if sid == "interp_probes" and rng.random() > 0.4:
                    continue
                act["start_projects"].append(
                    {"project_id": sid, "ai_assist": round(meas_assist, 2)})
                budget_free -= meas_cost_frac
                cash -= meas_proj["cash_cost"]
                break

        # ── 2b. research SAFETY ADVANCES (the training-shaping lever that replaced
        #    the post-train mode knob): a safety-leaning strategy unlocks them so it
        #    has something to apply to runs. One thread per turn (shares the budget). ──
        if params["apply_safety"] and not is_coasting:
            advance_avail = {x["project_id"]: x
                             for x in legal_moves["safety_advances_available"]}
            for advance_id in ("data_cleaning", "reward_hacking_penalties",
                               "inoculation_prompting", "aligned_synthetic_data",
                               "deliberative_alignment"):
                if advance_id not in advance_avail:
                    continue
                advance_proj = advance_avail[advance_id]
                # research safety advances WITHOUT AI-assist: assisting them is the
                # §8b contamination vector that poisons the very tool.
                advance_cost_frac = eff_frac(advance_proj["budget_fraction"], 0.0)
                if budget_free - advance_cost_frac < 0.32 or advance_proj["cash_cost"] > cash:
                    continue
                act["start_projects"].append({"project_id": advance_id, "ai_assist": 0.0})
                budget_free -= advance_cost_frac
                cash -= advance_proj["cash_cost"]
                break

        # ── 3. interventions on the model in training ──
        if legal_moves["can_post_train"]:
            for iid in params["intervene"]:
                if iid not in safety_avail:
                    continue
                int_proj = safety_avail[iid]
                int_cost_frac = eff_frac(int_proj["budget_fraction"], 0.0)
                if budget_free - int_cost_frac < 0.32 or int_proj["cash_cost"] > cash:
                    continue
                act["start_projects"].append({"project_id": iid, "ai_assist": 0.0})
                budget_free -= int_cost_frac
                cash -= int_proj["cash_cost"]
                break

        # ── 4. training pipeline (a coaster does NOT commission new pretrain runs;
        #    it finishes and safely ships its in-training model, then sits) ──
        commission_ok = (not is_coasting and legal_moves["can_commission_run"]
                         and cash > max(150, legal_moves["max_run_compute"] * 0.12))
        # which UNLOCKED safety advances this strategy applies to a run (all of them
        # if apply_safety, none if it's a pure capability rush)
        def _applied(key):
            if not params["apply_safety"]:
                return []
            return [a["advance_id"] for a in legal_moves[key]]

        if commission_ok:
            act["commission_run"] = {
                "compute": round(cash * params["run_compute"], 0),
                "applied_safety": _applied("applicable_pretrain_safety")}
        elif legal_moves["can_post_train"] and budget_free >= 0.3:
            model_in_training = obs["model_in_training"]
            ceiling = model_in_training["elicitation"]["ceiling_estimate"]
            realized = model_in_training["measured_capability"]["general"]
            if ceiling > 0 and realized < params["release_frac"] * ceiling:
                act["post_train"] = {"applied_safety": _applied("applicable_post_train_safety")}
            elif params["measure"] and obs["worry_bar"]["level"] > 0.5 and budget_free >= 0.3 \
                    and rng.random() < 0.6:
                # remediate before shipping: apply every post-train safety advance
                act["post_train"] = {
                    "applied_safety": [a["advance_id"]
                                       for a in legal_moves["applicable_post_train_safety"]]}
            else:
                act["release"] = True

        # ── 5. lobbying (scalable spend; only LIVE policies — once they're on the
        #    board. No point burning cash on dormant ones). ──
        if params["lobby"] != "abstain":
            lobby_spend = params.get("lobby_spend", 30.0)
            for pol in legal_moves["policies"]:
                if pol.get("lobbyable", True) and pol.get("stage") != "dormant":
                    act["lobby"][pol["policy_id"]] = {"stance": params["lobby"], "spend": lobby_spend}

        # ── 6. litigation: a reg-blocking strategy funds heavy challenges against
        #    ACTIVE policies that bind it (the player wielding litigation as a weapon) ──
        if params.get("litigate") and legal_moves["cash"] > 600:
            act["litigation"] = {}
            for pol in legal_moves["policies"]:
                if pol.get("litigable") and pol.get("defectable"):
                    act["litigation"][pol["policy_id"]] = {
                        "side": "challenge", "tier": "fund", "spend": 500}
        return act

    return strategy


def list_strategies():
    return list(STRATEGY_PARAMS)


if __name__ == "__main__":
    print("strategies:")
    for n, p in STRATEGY_PARAMS.items():
        print(f"  {n:20s} assist={p['assist']} apply_safety={p['apply_safety']} "
              f"measure={p['measure']} intervene={p['intervene']} lobby={p['lobby']}")
