"""Heuristic rival policy (§11) over ITS OWN observations — a rival is fooled
by its own model's eval-awareness too. Disposition-weighted; swappable later.

Strategy shape: research the tree (capabilities first, safety ∝ caution),
commission runs when cash allows, post-train to a recklessness-dependent
fraction of ceiling, release, repeat. Lobby by race position (handled in
lobbying.py; stances filled here from the observation's market caps).
"""
from backend_v1.engine.actions import Action
from backend_v1.engine.controllers.controller import LabController


class RivalController(LabController):
    def __init__(self, rng):
        self.rng = rng

    def decide(self, obs, disposition):
        r = disposition.recklessness
        action = Action()
        moves = obs.legal_moves
        free = moves["work_budget_free"]
        cash = moves["cash"]

        # 1. research: capability tree first; cautious labs run safety projects
        for proj in moves["capability_projects_available"]:
            if free <= 0.05 or cash < proj["cash_cost"]:
                break
            assist = r * 0.9   # reckless labs crank assist (the squeeze, §9b)
            action.start_projects.append(
                {"project_id": proj["project_id"], "ai_assist": assist})
            free -= proj["budget_fraction"] * (1 - 0.4 * assist)
            cash -= proj["cash_cost"]
        if self.rng.random() < (1.0 - r) * 0.8 and free > 0.2:
            safety = [p for p in moves["safety_projects_available"]
                      if p["cash_cost"] <= cash and p["budget_fraction"] <= free]
            if safety and (moves["can_post_train"] or obs.own_models):
                pick = self.rng.choice(safety)
                action.start_projects.append(
                    {"project_id": pick["project_id"], "ai_assist": r * 0.5})
                free -= pick["budget_fraction"]
                cash -= pick["cash_cost"]

        # 2. training pipeline — commission whenever there's no model to advance
        #    and enough cash for a meaningful run (don't sit on cash and stall)
        if moves["can_commission_run"] and cash > max(150, moves["max_run_compute"] * 0.15):
            action.commission_run = {"compute": round(cash * (0.55 + 0.3 * r), 0)}
        elif moves["can_post_train"] and free >= 0.3:
            mit = obs.model_in_training
            ceiling = mit["elicitation"]["ceiling_estimate"]
            realized = mit["measured_capability"]["general"]
            target = (0.55 + 0.35 * r) * ceiling
            if realized < target:
                mode = "capability" if self.rng.random() < 0.4 + 0.5 * r else "balanced"
                action.post_train = {"mode": mode}
            else:
                # cautious labs hold to remediate if their (foolable) worry bar is high
                worried = obs.worry_bar["level"] > 0.45 and self.rng.random() < (1 - r)
                if worried and free >= 0.3:
                    action.post_train = {"mode": "safety"}
                else:
                    action.release = True

        # 3. lobbying by race position (mirrors lobbying.resolve_rival_stances;
        #    done here from PUBLIC market caps so rivals use observations only)
        caps = obs.market_caps
        ranked = sorted(caps, key=caps.get, reverse=True)
        position = ranked.index(obs.lab_id) / max(1, len(ranked) - 1)  # 0 = leader
        for pid in moves["policies_on_table"]:
            lean_for = position - 0.35 - 0.4 * r
            action.lobby[pid] = ("for" if lean_for > 0.1
                                 else "against" if lean_for < -0.1 else "abstain")
        return action
