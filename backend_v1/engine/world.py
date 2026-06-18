"""World state distinct from any lab (design doc §11) — the shared object.

Approval is one world-level scalar (the doc's lean, §10c) plus light per-lab
reputation living on Lab. Approval's job is feeding government WTR, not revenue.
"""
from dataclasses import dataclass, field


@dataclass
class PolicyState:
    """A policy's lifecycle state (§10c). Stages advance via per-turn rolls driven
    by enactment_score = WTR + a hybrid decaying lobby tally."""
    stage: str = "dormant"          # dormant -> introduced -> passed -> signed -> active
    intro_turn: int | None = None
    enacted_turn: int | None = None  # turn it became ACTIVE
    prerequisite_met: bool = False   # e.g. interp mandate needs a public deception incident
    enforcement_level: float = 0.0   # continuous [0,1]; set at activation, drifts with WTR
    constitutionality: float = 0.0   # legal robustness (Phase 3 litigation); set at activation
    penalty_cap: float | None = None  # litigation "penalty-cap" win clamps the penalty ceiling
    lobby_tally: float = 0.0         # hybrid decaying net signed lobby influence
    # litigation state (Phase 3) — a LitigationCase from governance/litigation.py
    litigation: object | None = None

    @property
    def active(self) -> bool:
        return self.stage == "active"


@dataclass
class World:
    public_approval: float = 65.0      # 0-100
    wtr: float = 4.0                   # government willingness-to-regulate, 0-100
    world_harm: float = 0.0            # everyone's negative events aggregate (not a win var)
    cumulative_displacement: float = 0.0
    backlash_fired: int = 0            # how many displacement thresholds already crossed
    policies: dict = field(default_factory=dict)   # policy_id -> PolicyState
    tips_fired: set = field(default_factory=set)   # unlock/frontier tips already published
    deception_incident_public: bool = False        # unlocks interp-mandate prerequisite
    leak_event_happened: bool = False              # unlocks open-weights-restriction trigger
    damaging_event_happened: bool = False          # unlocks incident-liability trigger
    # revenue-pie bookkeeping (release-to-release growth needs world revenue history)
    total_revenue_rate: float = 0.0
    prev_total_revenue_rate: float = 0.0
    frontier_measured_general: float = 0.0
    asi_window_turns_left: int | None = None       # verification cliff countdown
    asi_model_id: str | None = None
    last_buyout_turn: int | None = None            # cooldown anchor for relaunch events

    def snapshot(self) -> dict:
        return {
            "public_approval": self.public_approval, "wtr": self.wtr,
            "world_harm": self.world_harm,
            "cumulative_displacement": self.cumulative_displacement,
            "active_policies": [pid for pid, st in self.policies.items() if st.active],
            "frontier_measured_general": self.frontier_measured_general,
            "total_revenue_rate": self.total_revenue_rate,
        }
