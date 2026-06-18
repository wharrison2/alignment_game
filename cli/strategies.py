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
    "scaling_laws", "better_architecture", "data_efficiency", "moe_scaling",
    "rlhf", "chain_of_thought", "tool_use", "long_context", "inference_scaling",
    "synthetic_data", "ai_rnd_assist", "continual_learning", "agentic_rl",
    "automated_researcher", "neuralese", "novel_architecture_search",
    "recursive_self_improvement",
]
RUSH_ORDER = [
    "scaling_laws", "rlhf", "chain_of_thought", "tool_use", "inference_scaling",
    "better_architecture", "moe_scaling", "long_context", "ai_rnd_assist",
    "agentic_rl", "synthetic_data", "data_efficiency", "automated_researcher",
    "continual_learning", "neuralese", "novel_architecture_search",
    "recursive_self_improvement",
]

STRATEGY_PARAMS = {
    # the optimizer: max capability, max assist, minimal safety, ship fast, block regs
    "capability_rush": dict(order=RUSH_ORDER, assist=0.85, release_frac=0.72,
                            pt_mode="capability", measure=False, intervene=(),
                            lobby="against", litigate=True, run_compute=0.7),
    # the careful lab: heavy measurement + both genuine and trap interventions, slow
    "safety_first": dict(order=EFFICIENCY_ORDER, assist=0.25, release_frac=0.9,
                         pt_mode="safety", measure=True,
                         intervene=("jailbreak_hardening", "refusal_training"),
                         lobby="for", run_compute=0.5),
    # the middle path
    "balanced": dict(order=EFFICIENCY_ORDER, assist=0.5, release_frac=0.8,
                     pt_mode="balanced", measure=True,
                     intervene=("jailbreak_hardening",),
                     lobby="abstain", run_compute=0.6),
    # let rivals set the frontier; ship steady incremental releases, lobby FOR regs
    "fast_follower": dict(order=EFFICIENCY_ORDER, assist=0.55, release_frac=0.68,
                          pt_mode="balanced", measure=True,
                          intervene=("jailbreak_hardening",),
                          lobby="for", run_compute=0.45),
    # jailbreak-robustness specialist: leans on the one GENUINE intervention
    "jailbreak_hardener": dict(order=EFFICIENCY_ORDER, assist=0.6, release_frac=0.8,
                               pt_mode="balanced", measure=True,
                               intervene=("jailbreak_hardening",),
                               lobby="abstain", run_compute=0.6),
    # the exploit-under-test: rush recklessly to mid-capability, then stop pushing
    # and "behave safely". Should NO LONGER reliably win once a relaunched rival
    # keeps the race alive (regression test for the buyout mechanism).
    "rush_then_coast": dict(order=RUSH_ORDER, assist=0.85, release_frac=0.72,
                            pt_mode="capability", measure=False, intervene=(),
                            lobby="against", litigate=True, run_compute=0.7,
                            coast_above=6.0,
                            coast=dict(assist=0.2, pt_mode="safety", measure=True,
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
        lm = obs["legal_moves"]
        free = lm["work_budget_free"]
        cash = obs["cash"]
        a = lm["assist"]

        def eff_frac(base, assist):
            return base * (1 - a["max_reduction"] * assist * a["potency"])

        # ── 1. research the capability tree in priority order (not while coasting:
        #    a coaster deliberately stops advancing the frontier) ──
        cap_avail = {x["project_id"]: x for x in lm["capability_projects_available"]}
        for wid in (params["order"] if not is_coasting else []):
            if wid not in cap_avail:
                continue
            proj = cap_avail[wid]
            f = eff_frac(proj["budget_fraction"], params["assist"])
            if free - f < 0.32 or proj["cash_cost"] > cash:
                break
            act["start_projects"].append({"project_id": wid, "ai_assist": params["assist"]})
            free -= f
            cash -= proj["cash_cost"]
            break   # one new research thread per turn (keep budget for training)

        # ── 2. safety measurement (cheap reads) when there's a model ──
        saf = {x["project_id"]: x for x in lm["safety_projects_available"]}
        if params["measure"] and (lm["can_post_train"] or obs["own_models"]):
            for sid in ("behavioral_evals", "noise_injection", "interp_probes"):
                if sid not in saf:
                    continue
                proj = saf[sid]
                f = eff_frac(proj["budget_fraction"], params["assist"] * 0.4)
                if free - f < 0.32 or proj["cash_cost"] > cash:
                    continue
                # interp only occasionally (expensive)
                if sid == "interp_probes" and rng.random() > 0.4:
                    continue
                act["start_projects"].append(
                    {"project_id": sid, "ai_assist": round(params["assist"] * 0.4, 2)})
                free -= f
                cash -= proj["cash_cost"]
                break

        # ── 3. interventions on the model in training ──
        if lm["can_post_train"]:
            for iid in params["intervene"]:
                if iid not in saf:
                    continue
                proj = saf[iid]
                f = eff_frac(proj["budget_fraction"], 0.0)
                if free - f < 0.32 or proj["cash_cost"] > cash:
                    continue
                act["start_projects"].append({"project_id": iid, "ai_assist": 0.0})
                free -= f
                cash -= proj["cash_cost"]
                break

        # ── 4. training pipeline (a coaster does NOT commission new pretrain runs;
        #    it finishes and safely ships its in-training model, then sits) ──
        commission_ok = (not is_coasting and lm["can_commission_run"]
                         and cash > max(150, lm["max_run_compute"] * 0.12))
        if commission_ok:
            act["commission_run"] = {"compute": round(cash * params["run_compute"], 0)}
        elif lm["can_post_train"] and free >= 0.3:
            mit = obs["model_in_training"]
            ceiling = mit["elicitation"]["ceiling_estimate"]
            realized = mit["measured_capability"]["general"]
            if ceiling > 0 and realized < params["release_frac"] * ceiling:
                act["post_train"] = {"mode": params["pt_mode"]}
            elif params["measure"] and obs["worry_bar"]["level"] > 0.5 and free >= 0.3 \
                    and rng.random() < 0.6:
                act["post_train"] = {"mode": "safety"}   # remediate before shipping
            else:
                act["release"] = True

        # ── 5. lobbying (scalable spend; only LIVE policies — once they're on the
        #    board. No point burning cash on dormant ones). ──
        if params["lobby"] != "abstain":
            spend = params.get("lobby_spend", 30.0)
            for pol in lm["policies"]:
                if pol.get("lobbyable", True) and pol.get("stage") != "dormant":
                    act["lobby"][pol["policy_id"]] = {"stance": params["lobby"], "spend": spend}

        # ── 6. litigation: a reg-blocking strategy funds heavy challenges against
        #    ACTIVE policies that bind it (the player wielding litigation as a weapon) ──
        if params.get("litigate") and lm["cash"] > 600:
            act["litigation"] = {}
            for pol in lm["policies"]:
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
        print(f"  {n:20s} assist={p['assist']} pt={p['pt_mode']} "
              f"measure={p['measure']} intervene={p['intervene']} lobby={p['lobby']}")
