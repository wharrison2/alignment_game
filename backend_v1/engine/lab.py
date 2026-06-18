"""Lab entity (design doc §4.2) — state shared by player and rivals.

Pure self-queries only; the engine advances time. Controllers (separate
objects) make decisions.
"""
from dataclasses import dataclass, field


@dataclass
class Disposition:
    """Rival disposition = WEIGHTS tuning the two-level controller's score
    functions (§10c), not a fixed personality. recklessness is the base; the
    controller layers a TRAJECTORY response on top (falling behind → more
    aggressive — the desperation spiral)."""
    recklessness: float = 0.0       # 0 cautious .. 1 reckless (the base)
    cost_advantage: float = 1.0     # multiplier on compute efficiency
    open_weights_ideology: bool = False
    regulation_stance: float = 0.5  # dislike of being regulated -> lobby/litigation spend
    safety_priority: float = 0.3    # baseline safety weight (rivals care less than player)

    @property
    def compliance(self) -> float:
        """Per-lab compliance with active policies ∝ disposition (§10c)."""
        return max(0.05, 1.0 - 0.85 * self.recklessness)


@dataclass
class Lab:
    id: str
    name: str
    is_player: bool = False
    cash: float = 0.0                       # SINGLE pot (revenue + investment)
    work_budget_per_year: float = 4.0       # quarterly pool = this * dt
    current_best_model: object | None = None     # most recent RELEASED model
    model_in_training: object | None = None      # post-train iterable, pre-release
    release_history: list = field(default_factory=list)   # permanent attack surface
    researched_advances: dict = field(default_factory=dict)  # node_id -> ResearchedItem
    in_progress: list = field(default_factory=list)        # ResearchProcess list
    training_run: object | None = None                     # pretrain in progress
    # economy
    revenue_rate: float = 0.0               # $M/yr, recomputed each turn
    investment_rate: float = 0.0
    market_cap: float = 100.0
    last_release_turn: int | None = None
    last_release_measured_general: float = 0.0
    prev_release_measured_general: float = 0.0
    # scoring (§3)
    impact_ledger: float = 0.0              # running externality integral
    impact_positives: float = 0.0           # tracked separately for the loss screen
    # governance
    reputation: float = 50.0                # light per-lab reputation (weak lever)
    lobby_stances: dict = field(default_factory=dict)  # policy_id -> last stance (display)
    active_defections: set = field(default_factory=set)  # policy_ids the player chose to defect on
    safe_harbor_signed: bool = False
    audit_pending_release: object | None = None   # model waiting on gov audit
    # disposition (rivals; player gets defaults)
    disposition: Disposition = field(default_factory=Disposition)
    # evals (§7): built passive harnesses (harness_id -> level; absent = unbuilt) and
    # in-flight build/upgrade timers ([{harness_id, target_level, years_remaining}])
    eval_harnesses: dict = field(default_factory=dict)
    eval_builds: list = field(default_factory=list)
    # bookkeeping
    model_counter: int = 0
    findings: list = field(default_factory=list)    # accumulated safety findings
    pending_effort: dict = field(default_factory=dict)  # axis -> remediation effort feed

    # ── pure queries ────────────────────────────────────────────────

    def released_models(self):
        return [m for m in self.release_history]

    def frontier_model(self):
        """Best model the lab could be judged by (released)."""
        if not self.release_history:
            return None
        return max(self.release_history, key=lambda m: m.measured_capability.general)

    def best_true_general(self) -> float:
        candidates = [m.capability_vec.general for m in self.release_history]
        if self.model_in_training is not None:
            candidates.append(self.model_in_training.capability_vec.general)
        return max(candidates, default=0.0)

    def max_run_compute(self) -> float:
        return max(0.0, self.cash * 0.9)

    def budget_committed(self, dt: float) -> float:
        """Fraction of this turn's work budget already committed to in-flight work."""
        return sum(p.budget_fraction_effective for p in self.in_progress)

    def next_model_id(self) -> str:
        self.model_counter += 1
        return f"{self.id}-M{self.model_counter}"

    def snapshot(self) -> dict:
        released_snaps = [m.snapshot() for m in self.release_history]
        in_training_snap = (
            [self.model_in_training.snapshot()] if self.model_in_training else []
        )
        advance_summary = {
            nid: {"version": item.version, "contamination": item.contamination}
            for nid, item in self.researched_advances.items()
        }
        return {
            "id": self.id,
            "name": self.name,
            "is_player": self.is_player,
            "cash": self.cash,
            "revenue_rate": self.revenue_rate,
            "investment_rate": self.investment_rate,
            "market_cap": self.market_cap,
            "impact_ledger": self.impact_ledger,
            "impact_positives": self.impact_positives,
            "reputation": self.reputation,
            "models": released_snaps + in_training_snap,
            "advances": advance_summary,
        }
