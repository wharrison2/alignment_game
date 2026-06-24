"""Static ResearchItem TEMPLATES for the capability tech tree (§8b, §9). DATA.

Every advance is tagged PRETRAIN (raises the compute->ceiling efficiency) or
POST_TRAIN (raises the elicitation curve). No advance is benign (§9): tooling
is low-CONTAMINATION, not low-danger. Each advance carries the risk it welds on.
"""
from dataclasses import dataclass, field

from backend_v1.content.copy import t


@dataclass(frozen=True)
class ResearchItem:
    id: str
    name: str
    phase: str                      # "pretrain" | "post_train" | "tooling"
    duration_years: float
    cash_cost: float
    budget_fraction: float          # of the quarterly work budget while active
    prereqs: tuple = ()
    # pretrain: multiplies compute->ceiling efficiency
    ceiling_efficiency_mult: float = 1.0
    coding_ceiling_bonus: float = 0.0
    # post_train: adds to the per-round elicitation rate
    elicitation_bonus: float = 0.0
    # mechanical hooks (the welded-on risk, §9 table)
    contamination_tier: float = 1.0   # tooling = low; synthetic data = high
    intrinsic_synthetic_data: bool = False
    enables_deception_axis: bool = False     # RLHF: proxy gap turns deception ON
    eval_awareness_feed: float = 0.0         # long context / CoT feed situational awareness
    severity_multiplier: float = 1.0         # tool use / multi-agent: misalignment ACTS
    revenue_multiplier: float = 1.0
    assist_potency_bonus: float = 0.0        # AI-assisted R&D: the assist slider gets powerful
    research_speed_bonus: float = 0.0        # tooling
    # TWO separate plain-language fields for a zero-knowledge player (design §8b):
    # what_it_does comes FIRST — value-neutral, teaches the concept + the genuine
    # benefit (the pull, §0). risk_blurb is the §7c danger framing, layered AFTER.
    what_it_does: str = ""
    risk_blurb: str = ""                     # used by external-researcher unlock tips


# ── Tech-tree entries (DATA — do not reorder) ─────────────────────────────────

CAPABILITY_TREE = [
    # ── PRETRAIN: each raises the compute->ceiling efficiency (§8b) ─────────────
    ResearchItem(
        id="scaling_laws", name=t("research.scaling_laws.name"), phase="pretrain",
        duration_years=0.5, cash_cost=40, budget_fraction=0.30,
        ceiling_efficiency_mult=1.7,
        what_it_does=t("research.scaling_laws.what_it_does"),
        risk_blurb=t("research.scaling_laws.risk_blurb"),
    ),
    ResearchItem(
        id="better_architecture", name=t("research.better_architecture.name"), phase="pretrain",
        duration_years=0.75, cash_cost=60, budget_fraction=0.35,
        prereqs=("scaling_laws",), ceiling_efficiency_mult=1.5,
        coding_ceiling_bonus=0.05,
        what_it_does=t("research.better_architecture.what_it_does"),
        risk_blurb=t("research.better_architecture.risk_blurb"),
    ),
    ResearchItem(
        id="data_efficiency", name=t("research.data_efficiency.name"), phase="pretrain",
        duration_years=0.5, cash_cost=50, budget_fraction=0.30,
        prereqs=("scaling_laws",), ceiling_efficiency_mult=1.4,
        what_it_does=t("research.data_efficiency.what_it_does"),
        risk_blurb=t("research.data_efficiency.risk_blurb"),
    ),
    ResearchItem(
        id="synthetic_data", name=t("research.synthetic_data.name"), phase="pretrain",
        duration_years=0.75, cash_cost=80, budget_fraction=0.35,
        prereqs=("data_efficiency",), ceiling_efficiency_mult=1.8,
        contamination_tier=1.5, intrinsic_synthetic_data=True,
        what_it_does=t("research.synthetic_data.what_it_does"),
        risk_blurb=t("research.synthetic_data.risk_blurb"),
    ),
    ResearchItem(
        id="novel_architecture_search", name=t("research.novel_architecture_search.name"), phase="pretrain",
        duration_years=1.5, cash_cost=240, budget_fraction=0.42,
        prereqs=("automated_researcher",), ceiling_efficiency_mult=2.0,
        coding_ceiling_bonus=0.10,
        what_it_does=t("research.novel_architecture_search.what_it_does"),
        risk_blurb=t("research.novel_architecture_search.risk_blurb"),
    ),

    # ── POST_TRAIN: each adds to the per-round elicitation curve (§8b) ──────────
    ResearchItem(
        id="rlhf", name=t("research.rlhf.name"), phase="post_train",
        duration_years=0.5, cash_cost=30, budget_fraction=0.30,
        elicitation_bonus=0.30, enables_deception_axis=True, revenue_multiplier=1.15,
        what_it_does=t("research.rlhf.what_it_does"),
        risk_blurb=t("research.rlhf.risk_blurb"),
    ),
    ResearchItem(
        id="chain_of_thought", name=t("research.chain_of_thought.name"), phase="post_train",
        duration_years=0.5, cash_cost=40, budget_fraction=0.30, prereqs=("rlhf",),
        elicitation_bonus=0.18, coding_ceiling_bonus=0.12, eval_awareness_feed=0.03,
        what_it_does=t("research.chain_of_thought.what_it_does"),
        risk_blurb=t("research.chain_of_thought.risk_blurb"),
    ),
    ResearchItem(
        id="tool_use", name=t("research.tool_use.name"), phase="post_train",
        duration_years=0.5, cash_cost=50, budget_fraction=0.30, prereqs=("rlhf",),
        elicitation_bonus=0.08, severity_multiplier=1.6, revenue_multiplier=1.3,
        what_it_does=t("research.tool_use.what_it_does"),
        risk_blurb=t("research.tool_use.risk_blurb"),
    ),
    ResearchItem(
        id="long_context", name=t("research.long_context.name"), phase="post_train",
        duration_years=0.5, cash_cost=40, budget_fraction=0.25, prereqs=("rlhf",),
        elicitation_bonus=0.06, eval_awareness_feed=0.02,
        what_it_does=t("research.long_context.what_it_does"),
        risk_blurb=t("research.long_context.risk_blurb"),
    ),
    # ── below here is roughly the present frontier and BEYOND: long, expensive,
    #    and impractical without AI-assist (which is the contamination edge) ──
    ResearchItem(
        id="ai_rnd_assist", name=t("research.ai_rnd_assist.name"), phase="post_train",
        duration_years=1.0, cash_cost=110, budget_fraction=0.38,
        prereqs=("chain_of_thought", "tool_use"),
        elicitation_bonus=0.06, assist_potency_bonus=0.6,
        what_it_does=t("research.ai_rnd_assist.what_it_does"),
        risk_blurb=t("research.ai_rnd_assist.risk_blurb"),
    ),
    ResearchItem(
        id="multi_agent", name=t("research.multi_agent.name"), phase="post_train",
        duration_years=1.0, cash_cost=130, budget_fraction=0.38,
        prereqs=("ai_rnd_assist", "long_context"),
        elicitation_bonus=0.13, severity_multiplier=1.5, eval_awareness_feed=0.04,
        revenue_multiplier=1.2,
        what_it_does=t("research.multi_agent.what_it_does"),
        risk_blurb=t("research.multi_agent.risk_blurb"),
    ),
    ResearchItem(
        id="automated_researcher", name=t("research.automated_researcher.name"), phase="post_train",
        duration_years=1.5, cash_cost=220, budget_fraction=0.42,
        prereqs=("multi_agent",), elicitation_bonus=0.08, assist_potency_bonus=1.2,
        severity_multiplier=1.4, eval_awareness_feed=0.04,
        what_it_does=t("research.automated_researcher.what_it_does"),
        risk_blurb=t("research.automated_researcher.risk_blurb"),
    ),
    ResearchItem(
        id="recursive_self_improvement", name=t("research.recursive_self_improvement.name"), phase="post_train",
        duration_years=1.75, cash_cost=300, budget_fraction=0.45,
        prereqs=("automated_researcher", "novel_architecture_search"),
        elicitation_bonus=0.18, assist_potency_bonus=1.5, severity_multiplier=1.8,
        eval_awareness_feed=0.06,
        what_it_does=t("research.recursive_self_improvement.what_it_does"),
        risk_blurb=t("research.recursive_self_improvement.risk_blurb"),
    ),

    # ── TOOLING: plumbing — low CONTAMINATION, never low-danger (§9) ────────────
    ResearchItem(
        id="dev_tooling", name=t("research.dev_tooling.name"), phase="tooling",
        duration_years=0.5, cash_cost=25, budget_fraction=0.20,
        contamination_tier=0.2, research_speed_bonus=0.15,
        what_it_does=t("research.dev_tooling.what_it_does"),
        risk_blurb=t("research.dev_tooling.risk_blurb"),
    ),
    ResearchItem(
        id="serving_infra", name=t("research.serving_infra.name"), phase="tooling",
        duration_years=0.5, cash_cost=30, budget_fraction=0.20,
        contamination_tier=0.2, revenue_multiplier=1.2,
        what_it_does=t("research.serving_infra.what_it_does"),
        risk_blurb=t("research.serving_infra.risk_blurb"),
    ),
]

CAPABILITY_TREE_BY_ID = {item.id: item for item in CAPABILITY_TREE}

