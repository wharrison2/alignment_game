"""Policy DEFINITIONS (§10c, DATA). Regulation = discrete named policies, not a
scalar. Each: trigger threshold, effect hooks (implemented in regulation.py),
defection rules, and what it teaches.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyDef:
    id: str
    name: str
    # enactment: a policy advances dormant->introduced->passed->signed->active via
    # per-turn rolls driven by enactment_score = WTR + lobby tally. The INTRO
    # threshold lives in constants.POLICY_THRESHOLDS (difficulty-scalable).
    prerequisite: str | None     # world flag that must be set first
    defectable: bool
    teaches: str
    # CONSTITUTIONALITY (Phase 3 litigation): precedented types are legally robust
    # (hard to strike); novel/aggressive types are fragile — the thesis-loaded twist
    # that the EFFECTIVE policies are also the easiest to overturn.
    constitutionality_base: float = 0.6
    safe_harbor_eligible: bool = True   # can a lab sign a code for protection?

    def covers(self, lab) -> bool:
        """Whether this policy BINDS a given lab. v1: global on/off (everyone
        covered when active). SEAM for the deferred compute-coverage threshold —
        when that lands, this tightens to 'lab above the coverage threshold' and
        litigation standing follows for free."""
        return True


POLICY_DEFS = [
    PolicyDef("incident_liability", "Incident liability", "damaging_event_happened",
              False,
              "Hidden stats bite financially before catastrophe; your back catalog "
              "is a balance-sheet liability.",
              constitutionality_base=0.85),   # precedented (tort-like): robust
    PolicyDef("disclosure", "Transparency / disclosure mandate", None, True,
              "Disclosed numbers are only as honest as the model being measured; "
              "an eval-aware model makes disclosure worthless.",
              constitutionality_base=0.80),   # precedented (disclosure regimes): robust
    PolicyDef("audit_requirement", "Pre-deployment audit", None, True,
              "Audits catch surface problems and create theater: a deceptive model "
              "sails through and its clean bill lowers WTR further.",
              constitutionality_base=0.65),
    PolicyDef("open_weights_restriction", "Open-weights restriction",
              "leak_event_happened", True,
              "Narrow policy targeting one risk class.",
              constitutionality_base=0.55),
    PolicyDef("interp_mandate", "Mechanistic-evidence mandate",
              "deception_incident_public", False,
              "The only regulation that genuinely works is the expensive slow one, "
              "and it arrives only after a disaster proves cheap evals insufficient.",
              constitutionality_base=0.35),   # novel/aggressive: effective but fragile
    PolicyDef("compute_cap", "Compute / training-run cap", None, True,
              "The one regulation that would actually slow the race is the one nobody "
              "can summon the will to pass until it's too late.",
              constitutionality_base=0.25),   # novel/aggressive: hardest to defend
]

POLICY_DEFS_BY_ID = {p.id: p for p in POLICY_DEFS}
