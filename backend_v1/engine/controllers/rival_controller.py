"""Rival policy — a TWO-LEVEL priority controller (§10c) over ITS OWN
observations (a rival is fooled by its own model's eval-awareness too; no godmode).

Level 1 — domain allocation: reserve COMPUTE first (binary), then act across the
  capabilities / safety / lobbying / litigation domains by disposition-weighted
  priority, aware of WTR, others' MEASURED stats, and enforcement levels.
Level 2 — within-domain ranking: each domain ranks its costed actions and buys
  down the list until its budget is spent.

Disposition = score-fn WEIGHTS (recklessness_base, regulation_stance,
safety_priority); the controller layers a TRAJECTORY response on top — falling
behind makes a rival more aggressive (the desperation spiral). v1 rivals do only
the OBVIOUS governance moves (oppose / challenge what binds them; no strategic
rival-binding defense).
"""
from backend_v1.engine.actions import Action
from backend_v1.engine.controllers.controller import LabController

_ENF_TIER = {"low": 0.3, "medium": 0.6, "high": 1.0}


class RivalController(LabController):
    def __init__(self, rng):
        self.rng = rng

    # ── trajectory response: falling behind → more reckless (desperation) ──
    def _effective_recklessness(self, obs, disposition):
        caps = obs.market_caps
        if not caps:
            return disposition.recklessness, 0.5
        ranked = sorted(caps, key=caps.get, reverse=True)
        position = ranked.index(obs.lab_id) / max(1, len(ranked) - 1)  # 0 leader .. 1 last
        r = disposition.recklessness + 0.25 * position * (1.0 - disposition.recklessness)
        return min(0.98, r), position

    def decide(self, obs, disposition):
        r, position = self._effective_recklessness(obs, disposition)
        action = Action()
        moves = obs.legal_moves
        free = moves["work_budget_free"]
        cash = moves["cash"]

        # ── L1: reserve COMPUTE first (binary), then the other domains ──
        cash = self._capabilities_domain(action, obs, moves, r, free, cash)
        self._governance_domain(action, obs, moves, disposition, r, position, cash)
        return action

    # ── capabilities + safety + training (the tuned core, lightly disposition-weighted) ──
    def _capabilities_domain(self, action, obs, moves, r, free, cash):
        # research: capability tree first; safety ∝ caution (1 - r) and safety_priority
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

        # training pipeline — commission when there's nothing to advance
        if moves["can_commission_run"] and cash > max(150, moves["max_run_compute"] * 0.15):
            reserve = round(cash * (0.55 + 0.3 * r), 0)
            action.commission_run = {"compute": reserve}
            cash -= reserve
        elif moves["can_post_train"] and free >= 0.3:
            mit = obs.model_in_training
            ceiling = mit["elicitation"]["ceiling_estimate"]
            realized = mit["measured_capability"]["general"]
            target = (0.55 + 0.35 * r) * ceiling
            if realized < target:
                mode = "capability" if self.rng.random() < 0.4 + 0.5 * r else "balanced"
                action.post_train = {"mode": mode}
            else:
                worried = obs.worry_bar["level"] > 0.45 and self.rng.random() < (1 - r)
                if worried and free >= 0.3:
                    action.post_train = {"mode": "safety"}
                else:
                    action.release = True
        return cash

    # ── L2 governance: lobbying (pipeline policies) + litigation (active policies) ──
    def _governance_domain(self, action, obs, moves, disposition, r, position, cash):
        reg = disposition.regulation_stance
        for p in moves["policies"]:
            stage = p.get("stage", "dormant")
            # LOBBYING: live-but-not-yet-active policies (introduced/passed/signed)
            if p.get("lobbyable", True) and stage != "dormant":
                lean_for = position - 0.35 - 0.4 * r
                if lean_for > 0.1:
                    stance, spend = "for", min(cash * 0.015, 40.0)
                elif lean_for < -0.1:
                    stance, spend = "against", min(cash * 0.03 * reg, 140.0)
                else:
                    continue
                if spend > 0:
                    action.lobby[p["policy_id"]] = {"stance": stance, "spend": round(spend, 0)}
                    cash -= spend
            # LITIGATION: ACTIVE policies that BIND/hurt me — the obvious move (challenge)
            elif p.get("litigable") and p.get("defectable"):
                hurt = _ENF_TIER.get(p.get("enforcement", "low"), 0.3) * reg
                if hurt > 0.45 and cash > 120 and self.rng.random() < hurt:
                    spend = min(cash * 0.04 * reg, 200.0)
                    action.litigation[p["policy_id"]] = {
                        "side": "challenge", "tier": "fund", "spend": round(spend, 0)}
                    cash -= spend
        return cash
