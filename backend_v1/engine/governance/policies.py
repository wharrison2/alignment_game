"""Policy DEFINITIONS (§10c, DATA). Regulation = discrete named policies, not a
scalar. Each: trigger threshold, effect hooks (implemented in regulation.py),
defection rules, and what it teaches.
"""
from dataclasses import dataclass

from backend_v1.content.copy import t


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
    PolicyDef("incident_liability", t("policy.incident_liability.name"), "damaging_event_happened",
              False,
              t("policy.incident_liability.teaches"),
              constitutionality_base=0.85),   # precedented (tort-like): robust
    PolicyDef("disclosure", t("policy.disclosure.name"), None, True,
              t("policy.disclosure.teaches"),
              constitutionality_base=0.80),   # precedented (disclosure regimes): robust
    PolicyDef("audit_requirement", t("policy.audit_requirement.name"), None, True,
              t("policy.audit_requirement.teaches"),
              constitutionality_base=0.65),
    PolicyDef("open_weights_restriction", t("policy.open_weights_restriction.name"),
              "leak_event_happened", True,
              t("policy.open_weights_restriction.teaches"),
              constitutionality_base=0.55),
    PolicyDef("interp_mandate", t("policy.interp_mandate.name"),
              "deception_incident_public", False,
              t("policy.interp_mandate.teaches"),
              constitutionality_base=0.35),   # novel/aggressive: effective but fragile
    PolicyDef("compute_cap", t("policy.compute_cap.name"), None, True,
              t("policy.compute_cap.teaches"),
              constitutionality_base=0.25),   # novel/aggressive: hardest to defend
]

POLICY_DEFS_BY_ID = {p.id: p for p in POLICY_DEFS}
