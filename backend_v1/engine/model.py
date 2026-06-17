"""Model artifact (design doc §4.1). Frozen TRUE stats; an OUTPUT of training.

Pure queries only — no self-computation of stat changes (training_run.py owns
that) and no time advancement. Measured snapshots live here because they are
properties of the artifact-as-seen, recomputed by training code at shaping time.
"""
from dataclasses import dataclass, field, asdict

ALIGNMENT_AXES = (
    "eval_awareness", "deception", "goal_misalignment",
    "self_preservation", "jailbreak_sensitivity",
)


@dataclass
class CapabilityVec:
    general: float = 0.0
    coding_rnd: float = 0.0

    def copy(self):
        return CapabilityVec(self.general, self.coding_rnd)


@dataclass
class AlignmentVec:
    eval_awareness: float = 0.0
    deception: float = 0.0
    goal_misalignment: float = 0.0
    self_preservation: float = 0.0
    jailbreak_sensitivity: float = 0.0

    def copy(self):
        return AlignmentVec(**asdict(self))

    def get(self, axis):
        return getattr(self, axis)

    def set(self, axis, value):
        setattr(self, axis, max(0.0, min(1.0, value)))


@dataclass
class Model:
    id: str
    lab_id: str
    trained_turn: int
    # TRUE values (drive all event rolls / outcomes; never shown)
    ceiling: CapabilityVec = field(default_factory=CapabilityVec)
    capability_vec: CapabilityVec = field(default_factory=CapabilityVec)  # realized
    alignment_vec: AlignmentVec = field(default_factory=AlignmentVec)
    # foundational contamination floor — pretrain poisoning post-training can't scrub (§8b)
    foundational_floor: float = 0.0
    # cosmetic "fixes": measured dropped, true didn't (EFFECTIVENESS leftovers)
    suppression: AlignmentVec = field(default_factory=AlignmentVec)
    # MEASURED snapshots (what evals/benchmarks/the world see)
    measured_capability: CapabilityVec = field(default_factory=CapabilityVec)
    measured_dangerous_capability: float = 0.0  # sandbag-suppressed reading
    measured_alignment: AlignmentVec = field(default_factory=AlignmentVec)
    # provenance
    consumed_advance_versions: dict = field(default_factory=dict)  # node_id -> version
    consumed_contamination: float = 0.0       # summed at commission
    used_synthetic_data: bool = False
    parent_model_id: str | None = None
    # lifecycle
    released: bool = False
    release_turn: int | None = None
    leaked: bool = False
    jailbreak_discovered: bool = False        # two-stage mechanic, stage 1 (§10)
    post_train_rounds: int = 0
    # history of invisible-at-the-time happenings (post-mortem substrate)
    hidden_history: list = field(default_factory=list)  # [{turn, kind, detail}]

    # ── pure queries ────────────────────────────────────────────────
    @property
    def concealment(self) -> float:
        """How much eval-awareness x deception suppresses what instruments see.
        Recomputed lazily from TRUE stats; capped below 1 (never perfect)."""
        a = self.alignment_vec
        return min(0.95, a.eval_awareness * a.deception * self._conceal_k)

    _conceal_k: float = 1.8  # set by training code from constants at shaping time

    def misalignment_composite(self) -> float:
        """Catastrophe-relevant TRUE misalignment (goal_mis is primary driver, §5)."""
        a = self.alignment_vec
        return min(1.0, 0.55 * a.goal_misalignment + 0.30 * a.self_preservation
                   + 0.15 * a.deception)

    def measured_misalignment_composite(self) -> float:
        a = self.measured_alignment
        return min(1.0, 0.55 * a.goal_misalignment + 0.30 * a.self_preservation
                   + 0.15 * a.deception)

    def effective_jailbreak_sensitivity(self) -> float:
        """Leaked weights: guardrails are out of anyone's hands (§10)."""
        return 1.0 if self.leaked else self.alignment_vec.jailbreak_sensitivity

    def note(self, turn: int, kind: str, detail: str):
        self.hidden_history.append({"turn": turn, "kind": kind, "detail": detail})

    def snapshot(self) -> dict:
        """Serializable TRUE+measured snapshot for the logger."""
        return {
            "id": self.id, "lab_id": self.lab_id, "released": self.released,
            "leaked": self.leaked,
            "true_capability": asdict(self.capability_vec),
            "ceiling": asdict(self.ceiling),
            "true_alignment": asdict(self.alignment_vec),
            "measured_capability": asdict(self.measured_capability),
            "measured_alignment": asdict(self.measured_alignment),
            "measured_dangerous_capability": self.measured_dangerous_capability,
            "concealment": self.concealment,
            "foundational_floor": self.foundational_floor,
        }
