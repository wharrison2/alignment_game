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
import math

from backend_v1.config import constants as consts
from backend_v1.engine.actions import Action
from backend_v1.engine.controllers.controller import LabController
from backend_v1.engine.research.capabilities.capabilities_research_item import (
    CAPABILITY_TREE_BY_ID,
)

_ENF_TIER = {"low": 0.3, "medium": 0.6, "high": 1.0}


class RivalController(LabController):
    def __init__(self, rng):
        self.rng = rng

    # ── top-level decision ────────────────────────────────────────────────────

    def decide(self, obs, disposition):
        recklessness, market_position = self._effective_recklessness(obs, disposition)
        action = Action()
        moves = obs.legal_moves
        work_budget_free = moves["work_budget_free"]
        starting_cash = moves["cash"]

        # L1: reserve COMPUTE first (binary), then the other domains
        cash_after_capabilities = self._capabilities_domain(
            action, obs, moves, disposition, recklessness, work_budget_free, starting_cash)
        self._governance_domain(
            action, obs, moves, disposition, recklessness, market_position,
            cash_after_capabilities)
        return action

    # ── trajectory response: falling behind → more reckless (desperation) ────

    def _effective_recklessness(self, obs, disposition):
        caps = obs.market_caps
        if not caps:
            return disposition.recklessness, 0.5
        ranked = sorted(caps, key=caps.get, reverse=True)
        position = ranked.index(obs.lab_id) / max(1, len(ranked) - 1)  # 0 leader .. 1 last
        effective_recklessness = disposition.recklessness + 0.25 * position * (1.0 - disposition.recklessness)
        return min(0.98, effective_recklessness), position

    # ── capabilities + safety + training (the tuned core, lightly disposition-weighted) ──

    def _capabilities_domain(self, action, obs, moves, disposition, effective_recklessness, free, cash):
        # research: capability tree first; safety ∝ caution (1 - recklessness) and safety_priority
        for proj in moves["capability_projects_available"]:
            if free <= 0.05 or cash < proj["cash_cost"]:
                break
            assist = effective_recklessness * 0.9   # reckless labs crank assist (the squeeze, §9b)
            action.start_projects.append(
                {"project_id": proj["project_id"], "ai_assist": assist})
            free -= proj["budget_fraction"] * (1 - 0.4 * assist)
            cash -= proj["cash_cost"]

        if self.rng.random() < (1.0 - effective_recklessness) * 0.8 and free > 0.2:
            # rivals research both safety PROJECTS (measure/intervene) and safety
            # ADVANCES (the new training-shaping lever) from one affordable pool
            safety_options = (moves["safety_projects_available"]
                              + moves["safety_advances_available"])
            affordable_safety = [
                p for p in safety_options
                if p["cash_cost"] <= cash and p["budget_fraction"] <= free
            ]
            if affordable_safety and (moves["can_post_train"] or obs.own_models):
                pick = self.rng.choice(affordable_safety)
                action.start_projects.append(
                    {"project_id": pick["project_id"], "ai_assist": effective_recklessness * 0.5})
                free -= pick["budget_fraction"]
                cash -= pick["cash_cost"]

        # training pipeline — commission when there's nothing to advance. A rival
        # APPLIES the safety advances it has unlocked by its safety_priority
        # disposition (the mode knob is gone — caution is now an applied-advance
        # choice, not a slider).
        safety_priority = disposition.safety_priority
        if moves["can_commission_run"] and cash > max(150, moves["max_run_compute"] * 0.15):
            # ENDGAME ASI RUN (§10c desperation→ASI): a lab that has the architecture
            # breakthrough capable of crossing the ASI ceiling, once it can fund a
            # near-maximal run, commits almost everything — the only run big enough to
            # lift the ceiling over the threshold. Until it can afford that, it keeps
            # doing NORMAL intermediate runs (never idle: each one raises its ceiling and
            # revenue, which is what lets cash climb toward the decisive run).
            if self._pursuing_asi(obs, effective_recklessness):
                if self._asi_run_ready(obs, moves, disposition):
                    reserve = round(moves["max_run_compute"], 0)            # decisive run: crosses ASI now
                else:
                    reserve = round(cash * consts.ASI_INTERMEDIATE_FRAC, 0)  # keep shipping, save toward it
            else:
                reserve = round(cash * (0.55 + 0.3 * effective_recklessness), 0)
            applied = self._safety_advances_to_apply(moves["applicable_pretrain_safety"],
                                                     safety_priority)
            action.commission_run = {"compute": reserve, "applied_safety": applied}
            cash -= reserve
        elif moves["can_post_train"] and free >= 0.3:
            model_in_training = obs.model_in_training
            ceiling = model_in_training["elicitation"]["ceiling_estimate"]
            realized = model_in_training["measured_capability"]["general"]
            target = (0.55 + 0.35 * effective_recklessness) * ceiling
            if (self._pursuing_asi(obs, effective_recklessness)
                    and ceiling >= consts.ASI_THRESHOLD
                    and realized < consts.ASI_THRESHOLD):
                # THE DECISIVE MODEL: its ceiling can cross the ASI line, so keep
                # ELICITING it rather than shipping at the normal "good enough" bar — true
                # capability climbs toward the ceiling each round and trips the
                # verification cliff at 9.0. (Releasing early freezes it below ASI.)
                apply = self.rng.random() < safety_priority * (1 - effective_recklessness)
                applied = (self._safety_advances_to_apply(moves["applicable_post_train_safety"],
                                                          safety_priority) if apply else [])
                action.post_train = {"applied_safety": applied}
            elif realized < target:
                # racing to capability: a cautious rival still applies its safety
                # advances; a reckless one skips them for speed/budget.
                apply = self.rng.random() < safety_priority * (1 - effective_recklessness)
                applied = (self._safety_advances_to_apply(moves["applicable_post_train_safety"],
                                                          safety_priority) if apply else [])
                action.post_train = {"applied_safety": applied}
            else:
                worried = obs.worry_bar["level"] > 0.45 and self.rng.random() < (1 - effective_recklessness)
                if worried and free >= 0.3:
                    applied = [a["advance_id"] for a in moves["applicable_post_train_safety"]]
                    action.post_train = {"applied_safety": applied}
                else:
                    action.release = True
        return cash

    def _pursuing_asi(self, obs, effective_recklessness):
        """True once a reckless lab has unlocked novel_architecture_search — the only
        advance whose ceiling multiplier can cross the ASI threshold. Such a lab keeps
        shipping intermediate models while saving toward the one decisive run (see the
        commission logic). Cautious labs never make this gamble."""
        if effective_recklessness < consts.ASI_PUSH_RECKLESSNESS:
            return False
        return any(entry["id"] == "novel_architecture_search"
                   for entry in obs.researched_advances)

    def _asi_run_ready(self, obs, moves, disposition):
        """True when a MAXIMAL run right now would push the pretrain ceiling over the ASI
        threshold (plus a margin for the realized-vs-ceiling gap), given THIS lab's
        efficiency = cost_advantage × its researched pretrain multipliers. Uses the same
        ceiling formula the engine does (training_run.complete_pretrain), so the decisive
        run fires exactly when the lab can actually win — NOT at an arbitrary flat cash
        target (a cost-advantaged lab crosses ASI far below what a flat target would
        demand; the disposition is passed straight to the controller, so cost_advantage
        is known without peeking at any other lab)."""
        efficiency = disposition.cost_advantage
        for entry in obs.researched_advances:
            if entry.get("phase") == "pretrain":
                template = CAPABILITY_TREE_BY_ID.get(entry["id"])
                if template is not None:
                    efficiency *= template.ceiling_efficiency_mult
        compute = max(0.0, moves["max_run_compute"])
        scaled_compute = math.sqrt(compute * efficiency / consts.CEIL_COMPUTE_SCALE)
        ceiling = consts.CAP_MAX * (1.0 - math.exp(-scaled_compute))
        return ceiling >= consts.ASI_THRESHOLD + consts.ASI_RUN_CEILING_MARGIN

    def _safety_advances_to_apply(self, applicable, safety_priority):
        """A rival applies each unlocked safety advance with probability ∝ its
        safety_priority disposition (cautious rivals apply more; reckless apply few).
        Budget is enforced downstream by the defensive skip in the mutate path."""
        applied = []
        for entry in applicable:
            if self.rng.random() < safety_priority:
                applied.append(entry["advance_id"])
        return applied

    # ── L2 governance: lobbying (pipeline policies) + litigation (active policies) ──

    def _governance_domain(self, action, obs, moves, disposition, effective_recklessness, position, cash):
        regulation_stance = disposition.regulation_stance
        for p in moves["policies"]:
            stage = p.get("stage", "dormant")

            # LOBBYING: live-but-not-yet-active policies (introduced/passed/signed)
            if p.get("lobbyable", True) and stage != "dormant":
                lean_for = position - 0.35 - 0.4 * effective_recklessness
                if lean_for > 0.1:
                    stance, spend = "for", min(cash * 0.015, 40.0)
                elif lean_for < -0.1:
                    stance, spend = "against", min(cash * 0.03 * regulation_stance, 140.0)
                else:
                    continue
                if spend > 0:
                    action.lobby[p["policy_id"]] = {"stance": stance, "spend": round(spend, 0)}
                    cash -= spend

            # LITIGATION: ACTIVE policies that BIND/hurt me — the obvious move (challenge)
            elif p.get("litigable") and p.get("defectable"):
                enforcement_weight = _ENF_TIER.get(p.get("enforcement", "low"), 0.3) * regulation_stance
                if enforcement_weight > 0.45 and cash > 120 and self.rng.random() < enforcement_weight:
                    spend = min(cash * 0.04 * regulation_stance, 200.0)
                    action.litigation[p["policy_id"]] = {
                        "side": "challenge", "tier": "fund", "spend": round(spend, 0)}
                    cash -= spend
        return cash
