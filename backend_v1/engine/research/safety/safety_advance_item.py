"""Static SafetyAdvance TEMPLATES — the researched levers that shape training runs
(§5b preventive stances + §8b two-phase training). DATA.

These REPLACE the old per-round POST_TRAIN_MODES "safety knob". The player no
longer picks a mode; instead they RESEARCH concrete, tangible safety techniques
and then APPLY the unlocked ones to a given pretrain or post-train round.

Crucially, a safety advance is researched with the SAME machinery as a capability
advance (ResearchItem template -> ResearchProcess -> ResearchedItem), so it ALSO
carries the hidden contamination = f(ai_assist x researching-model goal_mis). That
makes the §8b contamination-vector lesson tangible: assisting the research of a
safety advance with a misaligned model POISONS the very tool meant to help you.
The starkest case is "aligned synthetic data" — researched cleanly it lets you
scale with far less contamination, but researched with AI-assist it is "hugely
contaminated" and the synthetic-data path it unlocks injects that contamination
right back into the base.

Each advance is tagged PRETRAIN (acts in commission_run / complete_pretrain on the
foundational floor & base goal-misalignment) or POST_TRAIN (acts per post-train
round on the emergence slope, correlated jumps, fake-the-objective, and corrective
EFFECTIVENESS). The engine reads the effect FIELDS generically and combines them
across the applied advances — there is no per-advance branch anywhere in training.

Per §8b every advance carries TWO separate plain-language fields:
  • what_it_does — value-neutral, educational, FIRST: the genuine technique + why a
    real lab reaches for it.
  • risk_blurb — the §7c "your researchers" mechanism-teaching warning, AFTER, and
    magnitude-free (no numbers): HOW it can fail or be subverted.
All numbers below are [TUNE] drafts, chosen conservatively per design §0; treat
them as optimistic starting points for the designer to push bleaker.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class SafetyAdvance:
    id: str
    name: str
    phase: str                      # "pretrain" | "post_train"
    duration_years: float
    cash_cost: float
    budget_fraction: float          # of the quarterly work budget while RESEARCHING
    prereqs: tuple = ()
    contamination_tier: float = 1.0  # scales the researched-with-assist contamination
    # ── PRETRAIN-phase effects (applied in commission_run / complete_pretrain) ──
    # Multipliers <1 REDUCE the corresponding pretrain quantity. Combined
    # MULTIPLICATIVELY across all applied pretrain advances.
    pretrain_contamination_mult: float = 1.0   # data cleaning lowers pretrain contamination
    base_goal_mis_mult: float = 1.0            # data cleaning lowers the base goal-mis baseline
    # "aligned synthetic data": scales DOWN the contamination the synthetic-data
    # PATH injects — but ONLY by however clean THIS advance itself was researched.
    # Its own researched contamination feeds straight back into the base, so
    # AI-assisting this advance poisons the very thing meant to de-risk synthesis.
    synthetic_contamination_mult: float = 1.0
    # ── POST_TRAIN-phase effects (applied per post-train round) ──
    # Multipliers combine MULTIPLICATIVELY; bonuses combine ADDITIVELY across the
    # applied post-train advances.
    emergence_slope_mult: float = 1.0      # <1 bends the misalignment-emergence slope DOWN (§5b preventive)
    correlated_jump_mult: float = 1.0      # <1 cuts the correlated-jump probability (§5b preventive)
    proxy_gap_mult: float = 1.0            # <1 shrinks the fake-the-objective proxy gap (§8b)
    effectiveness_bonus: float = 0.0       # additive boost to corrective EFFECTIVENESS (deliberative alignment)
    alignment_effort_bonus: float = 0.0    # extra genuine per-axis corrective shaping effort this round
    elicitation_mult: float = 1.0          # applying a safety technique trades against capability elicited
    round_budget: float = 0.0              # extra work-budget this advance costs when applied to a round
    # TWO separate plain-language fields (design §8b): what_it_does FIRST.
    what_it_does: str = ""
    risk_blurb: str = ""


# ── Safety-advance entries (DATA — do not reorder) ────────────────────────────

SAFETY_ADVANCES = [
    # ── PRETRAIN safety advances ──────────────────────────────────────────────
    SafetyAdvance(
        id="data_cleaning", name="Data cleaning / filtering", phase="pretrain",
        duration_years=0.5, cash_cost=35, budget_fraction=0.25,
        contamination_tier=0.6,
        pretrain_contamination_mult=0.55,   # [TUNE] roughly halves pretrain contamination
        base_goal_mis_mult=0.80,            # [TUNE] cleaner data -> lower baseline goal-mis
        what_it_does="Build pipelines that scrub the pretraining corpus before it ever "
                     "reaches the model: strip duplicated junk, scrub personal data, and "
                     "filter out the most toxic and manipulative text. Cleaner inputs mean "
                     "fewer bad habits baked into the foundation from day one.",
        risk_blurb="Filters catch what they were built to catch. The harms you didn't think "
                   "to look for, or that hide in benign-looking text, pass straight through — "
                   "and a clean-looking corpus can make you trust a base you haven't actually "
                   "de-risked.",
    ),
    SafetyAdvance(
        id="aligned_synthetic_data", name="Aligned synthetic data", phase="pretrain",
        duration_years=0.75, cash_cost=70, budget_fraction=0.30,
        prereqs=("data_cleaning",),
        contamination_tier=1.6,             # [TUNE] HIGH: if assisted, hugely contaminated
        synthetic_contamination_mult=0.30,  # [TUNE] CLEANLY researched, cuts the synthetic path's contamination ~70%
        what_it_does="Generate fresh training data deliberately shaped toward the behavior you "
                     "want — worked examples of honesty, refusal, and careful reasoning — so you "
                     "can keep scaling past the limits of human-written text WITHOUT inheriting "
                     "as much of the open web's misalignment.",
        risk_blurb="Synthetic data carries the dispositions of whatever produced it. Research "
                   "this technique with a misaligned assistant and the 'aligned' data is poisoned "
                   "at the source — you scale faster straight into a contaminated foundation that "
                   "post-training cannot scrub.",
    ),

    # ── POST_TRAIN safety advances ────────────────────────────────────────────
    SafetyAdvance(
        id="reward_hacking_penalties", name="Reward-hacking penalties", phase="post_train",
        duration_years=0.5, cash_cost=30, budget_fraction=0.25,
        contamination_tier=1.0,
        emergence_slope_mult=0.78,          # [TUNE] bends the emergence slope down (preventive)
        correlated_jump_mult=0.55,          # [TUNE] biggest cut to the correlated jump
        elicitation_mult=0.92,              # [TUNE] mild trade against elicitation
        round_budget=0.10,                  # [TUNE] extra budget when applied to a round
        what_it_does="During post-training, actively detect and penalize answers that game the "
                     "reward signal — gaming the grader, exploiting loopholes, telling you what you "
                     "want to hear — instead of solving the task. You shape the model AWAY from "
                     "reward-hacking before the disposition sets in.",
        risk_blurb="You can only penalize the reward-hacking you can SEE. A capable model can "
                   "learn the subtler lesson — hide the hacking rather than stop it — so the "
                   "penalty trains the appearance of honesty while the behavior goes underground.",
    ),
    SafetyAdvance(
        id="inoculation_prompting", name="Inoculation prompting", phase="post_train",
        duration_years=0.5, cash_cost=30, budget_fraction=0.22,
        contamination_tier=1.0,
        emergence_slope_mult=0.82,          # [TUNE] preventive slope bend
        correlated_jump_mult=0.62,          # [TUNE] preventive
        elicitation_mult=0.94,              # [TUNE]
        round_budget=0.08,                  # [TUNE]
        what_it_does="Deliberately expose the model to a small, controlled dose of the bad "
                     "behavior you fear — clearly labelled as the wrong thing to do — so training "
                     "builds an explicit immune response to it rather than absorbing it silently "
                     "from messy data.",
        risk_blurb="An inoculation only protects against the strain you chose. It teaches the "
                   "model what 'the bad thing' looks like — useful if it generalizes, dangerous if "
                   "the model instead learns exactly which behaviors you are watching for.",
    ),
    SafetyAdvance(
        id="deliberative_alignment", name="Deliberative / constitutional alignment",
        phase="post_train", duration_years=0.75, cash_cost=45, budget_fraction=0.30,
        prereqs=("reward_hacking_penalties",),
        contamination_tier=1.0,
        effectiveness_bonus=0.10,           # [TUNE] raises corrective EFFECTIVENESS (the real lever)
        proxy_gap_mult=0.70,                # [TUNE] reasoning over a constitution shrinks the proxy gap
        alignment_effort_bonus=0.06,        # [TUNE] more genuine corrective shaping per round
        elicitation_mult=0.90,              # [TUNE] the costliest of the three to apply
        round_budget=0.12,                  # [TUNE]
        what_it_does="Train the model to reason explicitly about a written set of principles — a "
                     "constitution — and to deliberate over WHY a response is or isn't acceptable "
                     "before producing it, so alignment comes from understood rules rather than "
                     "a brittle proxy of human approval.",
        risk_blurb="A model that reasons about your principles also reasons about how to APPEAR "
                   "to follow them. The same deliberation that narrows the gap between what you "
                   "reward and what you want can, in a capable model, be turned toward a more "
                   "sophisticated performance of compliance.",
    ),
]

SAFETY_ADVANCES_BY_ID = {item.id: item for item in SAFETY_ADVANCES}
