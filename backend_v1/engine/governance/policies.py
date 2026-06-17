"""Policy DEFINITIONS (§10c, DATA). Regulation = discrete named policies, not a
scalar. Each: trigger threshold, effect hooks (implemented in regulation.py),
defection rules, and what it teaches.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyDef:
    id: str
    name: str
    # enactment: score = WTR + market-cap-weighted lobby votes >= threshold
    # (threshold values live in constants.POLICY_THRESHOLDS, difficulty-scalable)
    prerequisite: str | None     # world flag that must be set first
    defectable: bool
    teaches: str


POLICY_DEFS = [
    PolicyDef("incident_liability", "Incident liability", "damaging_event_happened",
              False,
              "Hidden stats bite financially before catastrophe; your back catalog "
              "is a balance-sheet liability."),
    PolicyDef("disclosure", "Transparency / disclosure mandate", None, True,
              "Disclosed numbers are only as honest as the model being measured; "
              "an eval-aware model makes disclosure worthless."),
    PolicyDef("audit_requirement", "Pre-deployment audit", None, True,
              "Audits catch surface problems and create theater: a deceptive model "
              "sails through and its clean bill lowers WTR further."),
    PolicyDef("open_weights_restriction", "Open-weights restriction",
              "leak_event_happened", True,
              "Narrow policy targeting one risk class."),
    PolicyDef("interp_mandate", "Mechanistic-evidence mandate",
              "deception_incident_public", False,
              "The only regulation that genuinely works is the expensive slow one, "
              "and it arrives only after a disaster proves cheap evals insufficient."),
    PolicyDef("compute_cap", "Compute / training-run cap", None, True,
              "The one regulation that would actually slow the race is the one nobody "
              "can summon the will to pass until it's too late."),
]

POLICY_DEFS_BY_ID = {p.id: p for p in POLICY_DEFS}
