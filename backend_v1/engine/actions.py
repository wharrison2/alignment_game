"""Action schema, validation, and the legal-moves helper (§14).

A turn's action is a structured, JSON-constructible object. Validation fails
loud with clear messages (agents produce malformed actions).
"""
from dataclasses import dataclass, field

from backend_v1.engine.research.capabilities.capabilities_research_item import (
    CAPABILITY_TREE_BY_ID,
)
from backend_v1.engine.research.safety.safety_research_item import SAFETY_PROJECTS_BY_ID
from backend_v1.engine.governance.policies import POLICY_DEFS
from backend_v1.engine.observation.warnings import warning_payload
from backend_v1.engine.rules import (
    assist_potency, assist_speed_potency, effective_fraction,
    budget_pool, committed_budget,
)
from backend_v1.engine.evaluations import (
    EVAL_HARNESS_BY_ID, max_level, next_upgrade,
)


@dataclass
class Action:
    # new projects to start this turn: [{"project_id": str, "ai_assist": 0..1}]
    start_projects: list = field(default_factory=list)
    # post-train the model_in_training: None or {"mode": "capability|balanced|safety"}
    post_train: dict | None = None
    # commission a pretrain: None or {"compute": $M}
    commission_run: dict | None = None
    release: bool = False
    # SCALABLE SPEND lobbying. Each entry is either:
    #   "for" | "against" | "abstain"                 (legacy/back-compat, spend 0)
    #   {"stance": "for"|"against"|"abstain", "spend": $M}
    lobby: dict = field(default_factory=dict)
    # litigation moves (Phase 3): policy_id -> {side, tier, spend, appeal?, stay?}
    litigation: dict = field(default_factory=dict)
    # explicit policy DEFECTION (player): policy_id -> bool. Violating an active
    # policy at an enforcement catch-risk. The frontend warns before committing
    # (consequence preview is in legal_moves).
    defect: dict = field(default_factory=dict)
    sign_safe_harbor: bool = False
    # build/upgrade passive eval harnesses (§7): harness_id -> bool. Each entry
    # advances that harness ONE level (build if unbuilt, else upgrade), costing
    # cash + turns; the reading then refreshes for free.
    build_evals: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "Action":
        if not isinstance(d, dict):
            raise ActionError("action must be a JSON object")
        unknown = set(d) - {"start_projects", "post_train", "commission_run",
                            "release", "lobby", "litigation", "defect",
                            "sign_safe_harbor", "build_evals"}
        if unknown:
            raise ActionError(f"unknown action fields: {sorted(unknown)}")
        return cls(
            start_projects=d.get("start_projects", []) or [],
            post_train=d.get("post_train"),
            commission_run=d.get("commission_run"),
            release=bool(d.get("release", False)),
            lobby=d.get("lobby", {}) or {},
            litigation=d.get("litigation", {}) or {},
            defect=d.get("defect", {}) or {},
            sign_safe_harbor=bool(d.get("sign_safe_harbor", False)),
            build_evals=d.get("build_evals", {}) or {},
        )


class ActionError(ValueError):
    pass


STANCES = {"for": 1, "against": -1, "abstain": 0}
ALL_PROJECT_IDS = set(CAPABILITY_TREE_BY_ID) | set(SAFETY_PROJECTS_BY_ID)


def parse_lobby_entry(v):
    """Normalize a lobby value into (stance, spend). Accepts a bare stance string
    (legacy, back-compat, spend 0) or {"stance":..., "spend":...}."""
    if isinstance(v, str):
        return v, 0.0
    if isinstance(v, dict):
        return v.get("stance", "abstain"), max(0.0, float(v.get("spend", 0.0) or 0.0))
    return "abstain", 0.0


# assist_potency / assist_speed_potency / effective_fraction now live in
# engine/rules.py — the single source of truth for action economics (imported
# above), so validate_action, _apply_action, and legal_moves can't drift apart.


def validate_action(action: Action, lab, world, consts, dt) -> list[str]:
    """Returns a list of human-readable problems; empty list = valid."""
    problems = []
    pool = budget_pool(lab, dt)
    committed = committed_budget(lab)
    cash_needed = 0.0

    # --- start_projects ---
    for spec in action.start_projects:
        pid = spec.get("project_id")
        assist = float(spec.get("ai_assist", 0.0))

        if pid not in ALL_PROJECT_IDS:
            problems.append(f"unknown project '{pid}'")
            continue

        if not 0.0 <= assist <= 1.0:
            problems.append(f"{pid}: ai_assist must be in [0,1], got {assist}")

        if any(p.template_id == pid for p in lab.in_progress):
            problems.append(f"{pid} is already in progress")
            continue

        if pid in CAPABILITY_TREE_BY_ID:
            t = CAPABILITY_TREE_BY_ID[pid]
            if pid in lab.researched_advances and not spec.get("reresearch"):
                problems.append(f"{pid} already researched (pass \"reresearch\": true "
                                f"to redo it cleanly)")
            missing_prereqs = [q for q in t.prereqs if q not in lab.researched_advances]
            if missing_prereqs:
                problems.append(f"{pid} requires {missing_prereqs} first")
            cash_needed += t.cash_cost
            committed += effective_fraction(t.budget_fraction, assist, lab, consts)
        else:
            t = SAFETY_PROJECTS_BY_ID[pid]
            if t.intervention:
                if lab.model_in_training is None:
                    problems.append(f"{pid}: interventions edit the model in training; "
                                    f"there is none (released models are frozen)")
            elif lab.model_in_training is None and not lab.release_history:
                problems.append(f"{pid}: no model to study yet")
            cash_needed += t.cash_cost
            committed += effective_fraction(t.budget_fraction, assist, lab, consts)

    # --- post_train ---
    if action.post_train is not None:
        if lab.model_in_training is None:
            problems.append("post_train: no model in training (commission a run first)")
        else:
            mode = action.post_train.get("mode", "balanced")
            if mode not in consts.POST_TRAIN_MODES:
                problems.append(f"post_train mode must be one of "
                                f"{list(consts.POST_TRAIN_MODES)}")
            committed += consts.POST_TRAIN_ROUND_BUDGET

    # --- commission_run ---
    if action.commission_run is not None:
        if lab.training_run is not None:
            problems.append("a pretrain run is already in progress")
        elif lab.model_in_training is not None:
            problems.append("finish or release the current model before pretraining "
                            "a new one (v1 simplification — see NOTES.md)")
        else:
            compute = float(action.commission_run.get("compute", 0))
            if compute < consts.MIN_RUN_COMPUTE:
                problems.append(f"compute must be ≥ {consts.MIN_RUN_COMPUTE} ($M)")
            cap_state = world.policies.get("compute_cap")
            compute_cap_active = (
                cap_state is not None
                and cap_state.active
                and compute > consts.COMPUTE_CAP_LIMIT
                and lab.disposition.compliance > 0.5
            )
            if compute_cap_active:
                problems.append(f"compute cap active: max {consts.COMPUTE_CAP_LIMIT} "
                                f"(defect at your own risk by lowering compliance — "
                                f"rivals might)")
            cash_needed += compute

    # --- release ---
    if action.release and lab.model_in_training is None:
        problems.append("release: no model in training to release")

    # --- lobby ---
    policy_ids = {p.id for p in POLICY_DEFS}
    for pid, v in action.lobby.items():
        stance, spend = parse_lobby_entry(v)
        if pid not in policy_ids:
            problems.append(f"lobby: unknown policy '{pid}'")
        if stance not in STANCES:
            problems.append(f"lobby {pid}: stance must be for/against/abstain")
        if spend < 0:
            problems.append(f"lobby {pid}: spend must be >= 0")
        cash_needed += spend

    # --- defect ---
    for pid in action.defect:
        if pid not in policy_ids:
            problems.append(f"defect: unknown policy '{pid}'")

    # --- litigation ---
    for pid, spec in action.litigation.items():
        if pid not in policy_ids:
            problems.append(f"litigation: unknown policy '{pid}'")
            continue
        policy_state = world.policies.get(pid)
        if policy_state is None or not policy_state.active:
            problems.append(f"litigation {pid}: only ACTIVE policies can be litigated")
        side = spec.get("side", "challenge")
        if side not in ("challenge", "defense"):
            problems.append(f"litigation {pid}: side must be challenge/defense")
        tier = spec.get("tier", "amicus")
        if tier not in ("amicus", "join", "fund"):
            problems.append(f"litigation {pid}: tier must be amicus/join/fund")
        if tier == "amicus":
            cash_needed += consts.LIT_AMICUS_COST
        elif tier == "join":
            cash_needed += consts.LIT_JOIN_COST
        else:
            cash_needed += max(0.0, float(spec.get("spend", 0.0) or 0.0))

    # --- build_evals (build/upgrade passive harnesses) ---
    builds_in_flight = {b["harness_id"] for b in lab.eval_builds}
    for harness_id, requested in action.build_evals.items():
        if not requested:
            continue
        harness = EVAL_HARNESS_BY_ID.get(harness_id)
        if harness is None:
            problems.append(f"build_evals: unknown harness '{harness_id}'")
            continue
        current_level = lab.eval_harnesses.get(harness_id, -1)
        if current_level >= max_level(harness):
            problems.append(f"build_evals {harness_id}: already fully upgraded")
            continue
        if harness_id in builds_in_flight:
            problems.append(f"build_evals {harness_id}: a build is already in progress")
            continue
        cash_needed += next_upgrade(harness, current_level).cash_cost

    # --- global budget checks ---
    if committed > pool + 1e-9:
        problems.append(f"work budget exceeded: committed {committed:.2f} of "
                        f"{pool:.2f} (in-flight work counts)")
    if cash_needed > lab.cash:
        problems.append(f"not enough cash: need {cash_needed:.0f}, have {lab.cash:.0f}")

    return problems


def legal_moves(lab, world, consts, dt) -> dict:
    """Explicit action space for agents/humans (§14)."""
    pool = budget_pool(lab, dt)
    committed = committed_budget(lab)

    # projects already underway aren't offered again (they show under "in progress")
    in_progress_ids = {p.template_id for p in lab.in_progress}

    # capability projects: unlocked and prereqs met, not yet researched, not underway
    cap_avail = []
    for t in CAPABILITY_TREE_BY_ID.values():
        if t.id in lab.researched_advances or t.id in in_progress_ids:
            continue
        if all(q in lab.researched_advances for q in t.prereqs):
            cap_avail.append({"project_id": t.id, "name": t.name, "phase": t.phase,
                              "duration_years": t.duration_years,
                              "cash_cost": t.cash_cost,
                              "budget_fraction": t.budget_fraction,
                              # §8b: value-neutral "what it is" FIRST, risk framing AFTER
                              "what_it_does": t.what_it_does,
                              "risk_blurb": t.risk_blurb})

    safety_avail = [{"project_id": p.id, "name": p.name,
                     "duration_years": p.duration_years, "cash_cost": p.cash_cost,
                     "budget_fraction": p.budget_fraction, "evidence": p.evidence,
                     "spoofability": p.spoofability, "blurb": p.blurb,
                     "intervention": p.intervention,
                     "target_axis": p.target_axis}
                    for p in SAFETY_PROJECTS_BY_ID.values()
                    if p.id not in in_progress_ids]

    return {
        "work_budget_free": round(pool - committed, 3),
        "cash": round(lab.cash, 1),
        "capability_projects_available": cap_avail,
        "reresearchable_nodes": sorted(lab.researched_advances),
        "safety_projects_available": safety_avail,
        # AI-assist effect the frontend can preview (mirrors rules.effective_fraction /
        # the duration speedup): effective_budget = base*(1 - max_reduction*assist*potency)
        # and effective_years ≈ base / (1 + speedup*assist*speed_potency).
        "assist": {
            "potency": round(assist_potency(lab, consts), 3),
            "speed_potency": round(assist_speed_potency(lab, consts), 3),
            "max_reduction": consts.ASSIST_MAX_REDUCTION,
            "speedup": consts.ASSIST_SPEEDUP,
        },
        "warnings": warning_payload(),
        "can_post_train": lab.model_in_training is not None,
        "post_train_modes": list(consts.POST_TRAIN_MODES),
        "post_train_round_budget": consts.POST_TRAIN_ROUND_BUDGET,
        "can_commission_run": lab.training_run is None and lab.model_in_training is None,
        "max_run_compute": round(lab.max_run_compute(), 0),
        "can_release": lab.model_in_training is not None,
        "policies": _policy_board(lab, world, consts),
        "lobby_stances": list(STANCES),
        "eval_harnesses": _eval_harness_board(lab),
        "action_schema_example": {
            "start_projects": [{"project_id": "rlhf", "ai_assist": 0.0}],
            "post_train": {"mode": "balanced"},
            "commission_run": {"compute": 500},
            "release": False,
            "lobby": {"audit_requirement": {"stance": "against", "spend": 120}},
            "defect": {"compute_cap": True},
            "build_evals": {"dangerous_cyber": True},
        },
    }


def _eval_harness_board(lab):
    """Build/upgrade availability for the passive eval harnesses (§7): current
    level, whether a build is in flight, and the cost/time of the next level."""
    builds_in_flight = {b["harness_id"] for b in lab.eval_builds}
    board = []
    for harness in EVAL_HARNESS_BY_ID.values():
        current_level = lab.eval_harnesses.get(harness.id, -1)
        upgrade = next_upgrade(harness, current_level)
        in_flight = harness.id in builds_in_flight
        entry = {
            "harness_id": harness.id,
            "name": harness.name,
            "level": current_level,
            "max_level": max_level(harness),
            "in_flight": in_flight,
            "action": "build" if current_level < 0 else "upgrade",
        }
        if upgrade is not None and not in_flight:
            entry["next_cost"] = upgrade.cash_cost
            entry["next_years"] = upgrade.build_years
            entry["next_awareness_reduction"] = upgrade.awareness_reduction
        board.append(entry)
    return board


def _enf_tier(level):
    return "low" if level < 0.34 else "medium" if level < 0.67 else "high"


def _policy_board(lab, world, consts):
    """Public regulatory board + the per-policy DEFECT consequence preview the
    frontend needs to warn-and-confirm before the player defects (§3d)."""
    board = []
    for p in POLICY_DEFS:
        policy_state = world.policies.get(p.id)
        stage = policy_state.stage if policy_state is not None else "dormant"
        entry = {"policy_id": p.id, "name": p.name, "stage": stage,
                 "defectable": p.defectable, "teaches": p.teaches}

        if policy_state is not None and policy_state.active:
            enf = policy_state.enforcement_level
            entry["enforcement"] = _enf_tier(enf)
            entry["lobbyable"] = False   # active: lobbying only drifts enforcement
            # litigable: public court state + ladder costs (standing for join)
            entry["litigable"] = True
            entry["litigation"] = {
                "court_level": (policy_state.litigation.court_level
                                if policy_state.litigation else "trial"),
                "last_margin": (round(policy_state.litigation.last_margin, 1)
                                if policy_state.litigation
                                and policy_state.litigation.last_margin is not None
                                else None),
                "constitutionality": round(policy_state.constitutionality, 2),
                "has_standing": p.covers(lab),
                "ladder": {"amicus": consts.LIT_AMICUS_COST,
                           "join": consts.LIT_JOIN_COST, "fund": "scaled $"},
            }

            if p.defectable and p.covers(lab):
                # consequence preview (warn before committing)
                size_scale = 1.0 + max(0.0, lab.market_cap) / 4000.0
                catch_p_yr = (enf * consts.ENFORCEMENT_BASE_DETECTION
                              * consts.ENFORCEMENT_CATCH_RATE * 2.0)
                entry["defect_preview"] = {
                    "catch_prob_per_year": round(catch_p_yr, 3),
                    "penalty_if_caught": round(enf * consts.DEFECTION_PENALTY * size_scale, 0),
                    "approval_hit_if_caught": round(enf * consts.DEFECTION_APPROVAL_HIT, 1),
                }
        else:
            entry["lobbyable"] = True

        board.append(entry)
    return board
