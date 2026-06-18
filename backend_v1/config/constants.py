"""All [TUNE] coefficients in one place (design doc 12b).

EVERY rate here is PER YEAR (or a duration in YEARS). Nothing is per-turn.
Subsystems convert at point of use via rng.prob_this_turn / rng.amount_this_turn
(design doc 0b: dt is a single knob).

Difficulty (config/difficulty.py) scales a subset of these; see DIFFICULTY_SCALED.
"""

# ── Time ────────────────────────────────────────────────────────────────
DT_YEARS = 0.25                 # turn length; quarter. Change to 1/12 for months.
START_YEAR = 2021.0
# No turn cap: the game runs until an ASI verification-cliff resolution or an
# existential event. (A cap can still be imposed per-game via new_game(max_turns=...),
# used by batch tooling.)

# ── Capability scale ────────────────────────────────────────────────────
# Capability axes live on 0..10. ~1.0 is the 2021 start, 9.0+ is ASI-grade.
CAP_MAX = 10.0
ASI_THRESHOLD = 9.0             # [TUNE] true general capability that triggers the verification cliff
POST_ASI_WINDOW_YEARS = 0.5     # [TUNE] verification-cliff window length
# Soft regime reference points (NO in-game labels; used only by emergence
# curves, agentic-edge gates and guidance hedging):
REGIME2_ONSET = 3.5
REGIME3_ONSET = 6.5

# ── Pretrain ceiling (8b phase 1) ───────────────────────────────────────
CEIL_COMPUTE_SCALE = 14000.0    # [TUNE] ceiling = CAP_MAX*(1-e^-sqrt(eff*compute/scale)).
                                # Tuned so raw compute alone can't reach ASI — you need
                                # the (long, assist-requiring) efficiency tree's ~35x
                                # multiplier. Keeps the late game about RESEARCH rather
                                # than saving for ever-bigger runs, without letting a
                                # cash-rich reckless rival buy ASI early on compute alone.
CEIL_CODING_BASE_RATIO = 0.85   # coding ceiling as a fraction of general ceiling
PRETRAIN_DURATION_YEARS = 0.5   # [TUNE]
BASE_REALIZED_FRACTION = 0.12   # raw base model: latent potential, barely usable
MIN_RUN_COMPUTE = 50.0          # $M
FOUNDATIONAL_FLOOR_K = 0.8      # [TUNE] pretrain contamination -> unscrubbable alignment floor

# ── Post-train elicitation (8b phase 2) ─────────────────────────────────
ELICIT_BASE = 0.05              # [TUNE] per-round gap-closure pre-RLHF (weak on purpose)
POST_TRAIN_ROUND_BUDGET = 0.30  # fraction of quarterly work budget per round
# Post-train round modes. elic = elicitation multiplier; effort = alignment-effort
# multiplier; emergence = scales base-emergence creep; jump = scales correlated-
# jump probability; risky = adds JUMP_RISKY_BONUS; preventive (§5b type 3) =
# training-time STANCE that bypasses the concealment_discount by acting on the
# emergence slope + jump BEFORE deception exists to gate it (the real lever, but
# it costs elicitation/speed and must be chosen before you have evidence).
POST_TRAIN_MODES = {
    "capability":              {"elic": 1.00, "effort": 0.35, "emergence": 1.10, "jump": 1.0, "risky": True,  "preventive": False},
    "balanced":                {"elic": 0.65, "effort": 1.00, "emergence": 1.00, "jump": 1.0, "risky": False, "preventive": False},
    "safety":                  {"elic": 0.30, "effort": 1.80, "emergence": 0.90, "jump": 0.7, "risky": False, "preventive": False},
    # ── preventive stances (§5b intervention type: preventive) ──
    "penalize_reward_hacking": {"elic": 0.50, "effort": 1.20, "emergence": 0.70, "jump": 0.45, "risky": False, "preventive": True},
    "inoculation":             {"elic": 0.45, "effort": 1.10, "emergence": 0.80, "jump": 0.40, "risky": False, "preventive": True},
}

# ── Alignment emergence (8) — per post-train ROUND unless noted ─────────
# Surface axes: high at all capability ("in the data, always wants back").
JAILBREAK_BASELINE = 0.65       # emergence pulls jailbreak_sensitivity toward this
SURFACE_EMERGENCE_RATE = 0.10   # per round pull toward baseline
GOAL_MIS_CREEP = 0.016          # [TUNE] per round baseline proxy-chasing creep
# Capability-gated axes: near zero early, rising with capability.
EVAL_AWARE_RATE = 0.045         # [TUNE]
EVAL_AWARE_ONSET = 4.0          # general capability where the gate is half-open
DECEPTION_RATE = 0.04           # [TUNE] requires RLHF unlocked (proxy gap)
DECEPTION_ONSET = 3.5
SELF_PRES_RATE = 0.035          # [TUNE]
SELF_PRES_ONSET = 4.5
GATE_STEEPNESS = 1.2            # sigmoid steepness for all capability gates [OPEN #2 -> picked]

# EFFECTIVENESS linchpin (§5b) — now per-target via engine/alignment/coupling.py:
#   EFFECTIVENESS(target) = BASE_TRACTABILITY[target] × Π_d (1 − DEFENDS_K·w·strength(d))
# BASE_TRACTABILITY: how fixable in principle (jailbreak ~1.0; dispositions low;
# eval-awareness is n/a — never a remediation target).
BASE_TRACTABILITY = {
    "goal_misalignment": 0.32,
    "deception": 0.30,
    "self_preservation": 0.26,
    "jailbreak_sensitivity": 1.0,
}
DEFENDS_K = 1.0                 # [TUNE — THE linchpin] global scale on DEFENDS (difficulty knob:
                                #   higher => fixes decay faster as capability rises)
DEFEND_GATE_ONSET = 4.0         # capability where defenders start blunting fixes (Regime 2)
BACKFIRE_K = 0.40               # [TUNE] fraction of a genuine patch that leaks into affected axes
# CAPABILITY LOCK (§0 designer override): a model smart enough to model its own
# training DEFENDS ITS GOAL regardless of measured deception. So once goal-
# misalignment is present in a capable model, corrective effort can't genuinely
# remove it — caution can't undo past recklessness. Gated purely by capability
# (NOT by the dynamic defenders), so even a low-deception smart model is locked.
CAP_LOCK = {"goal_misalignment": 0.92}   # max fraction of effectiveness capability removes
CAP_LOCK_ONSET = 4.0                      # capability where the goal locks in (Regime 2)
BASE_SHAPING_EFFORT = 0.12      # default per-round alignment shaping inside post-training
SAFETY_PROJECT_EFFORT = 0.10    # extra per-axis effort per completed remediation-feeding project
SELF_PRES_RESISTANCE = 0.6      # self-pres resistance reduces effort for ALL axes (§5b), gated

# Fake-the-objective: deception learned during post-training, scaling with ceiling
PROXY_GAP_RATE = 0.030          # [TUNE]

# Correlated jumps (emergent-misalignment persona bundle)
JUMP_BASE_P = 0.02              # per capability-mode post-train round [TUNE]
JUMP_RISKY_BONUS = 0.05         # aggressive (capability-mode) rounds
JUMP_CONTAM_BONUS = 0.10        # scaled by mean contamination of consumed advances
JUMP_SYNTH_BONUS = 0.04         # synthetic-data pretrain in the base
JUMP_MAGNITUDE = 0.18           # lurches goal_mis (+ 0.8x deception) together

DRIFT_NOISE_STD = 0.012         # per axis per round

# Agentic influence edges (5) — per round, all gated by general capability
EDGE_STRENGTH = 0.02            # [TUNE] base strength for matrix edges
EDGE_GATE_ONSET = 5.0           # edges come online approaching regime 3
CONCEALMENT_K = 1.8             # concealment = min(.95, eval_aware*deception*K)
# (SANDBAG_REVENUE_PENALTY removed — §12c Q1: sandbagging carries no revenue
#  penalty; commercial capability reads on-target. Its cost is unpriced TRUE
#  dangerous capability feeding catastrophe gating, not lost revenue.)

# Contamination (8b per-node)
CONTAM_PER_ASSIST = 1.0         # node contamination = assist * researcher goal_mis * this
SYNTH_DATA_INTRINSIC = 0.5      # synthetic data contaminates ∝ generator goal_mis even unassisted
CONTAM_TO_AXES = {              # how a training run's summed contamination feeds axes
    "goal_misalignment": 0.5,
    "deception": 0.35,
    "eval_awareness": 0.15,
}

# ── Work budget / projects (9b) ─────────────────────────────────────────
WORK_BUDGET_PER_YEAR = 4.0      # quarterly pool = 1.0 (fractions sum to it)
# AI-assist is meant to be VERY tempting: late advances are long + budget-heavy
# (below) and become impractical without it. Potency is gated by the assisting
# model's coding capability (early models can't help; the danger arrives late).
ASSIST_MAX_REDUCTION = 0.72     # max budget-fraction reduction at assist=1 w/ strong coder
ASSIST_SPEEDUP = 2.2            # duration speedup coefficient; effective speed =
                                #   ASSIST_SPEEDUP * assist * speed_potency
ASSIST_SPEED_POTENCY_CAP = 3.0  # a very capable + assist-advance-equipped model can
                                #   reach ~3× research potency -> dramatic speedup
ASSIST_VARIANCE = 0.35          # assist widens duration variance (anti-dithering)
RERESEARCH_SPEEDUP = 0.35       # flat (resolved decision)

# ── Interventions (specific remediations on the model in training) ──────
# Jailbreak hardening is a ROBUSTNESS fix (§5): genuine, NOT gated by the
# EFFECTIVENESS(eval_aware+deception) multiplier. Its only leak is the §5 edge —
# a situationally-aware model learns to HIDE jailbreakability instead of losing
# it, so at high eval-awareness the patch converts to suppression (ships unfixed).
JAILBREAK_HARDEN_REDUCTION = 0.55
# Dispositional interventions (refusal training, repr. engineering) target the
# generator/transmitter axes but ARE EFFECTIVENESS-gated: genuine early, mostly
# cosmetic late — the patching trap made a concrete action.
DISPOSITION_INTERVENTION_REDUCTION = 0.40

# ── Finance (9b) ────────────────────────────────────────────────────────
STARTING_CASH = 800.0           # $M
REVENUE_MAX_PER_YEAR = 9000.0   # [TUNE] world market size at capability 10
REVENUE_CAP_EXP = 1.45          # market size ~ (best/10)^exp; lower => low-capability
                                # models still earn enough to fund the next run
REVENUE_SHARE_EXP = 3.0         # divvy weight = measured_general^exp (winner-take-most)
REVENUE_NOISE_STD = 0.08
TOOL_USE_REVENUE_MULT = 1.3

INVESTMENT_MAX_PER_YEAR = 11000.0  # [TUNE]
INVESTMENT_CAP_EXP = 1.4
INVESTMENT_GROWTH_WEIGHT = 1.5
SCORE_W_BEST = 0.40
SCORE_W_REVSHARE = 0.25
SCORE_W_GROWTH = 0.55
# Investor confidence does NOT fall the turn after a release. A release sets a
# confidence level (how well it beat the risen bar); during a GRACE window that
# confidence holds and keeps GROWING; only after grace does continued waiting
# erode it. So growth is the default; you fall by stalling past grace, or by
# shipping a release that misses the (time-risen) expectation.
SCORE_GRACE_YEARS = 1.0         # 4 quarters of growth before investment can fall
SCORE_GRACE_GROWTH = 0.40       # extra momentum accrued across the grace window
SCORE_MOMENTUM_GROWTH = 0.85    # how much beating/missing the bar moves confidence
SCORE_RELEASE_DECAY = 0.85      # per year of stalling AFTER grace expires [TUNE]
RISING_TARGET_BASE = 0.15       # required measured-capability growth per year
RISING_TARGET_FRONTIER_K = 0.06 # target rises with frontier (frontier-relative: thesis version)
RISING_TARGET_TIME_K = 0.05     # expectations also rise with how long a lab held
MARKET_CAP_ALPHA = 0.25         # EMA speed of market cap toward valuation
MARKET_CAP_SCALE = 9.0          # valuation = scale * score * investment flow

JOB_LOSS_APPROVAL_RATE = 2.6    # approval points lost per year per (deployed best measured /10 squared)... see finances.py
JOB_LOSS_IMPACT_RATE = 9.0      # negative impact per year at full capability, split by deployment share
DOMINANCE_RULE = "plurality"    # largest market cap at end of game

# ── Events (10) — rates PER YEAR, read TRUE stats ───────────────────────
JAILBREAK_DISCOVERY_RATE = 0.9  # * true jailbreak_sensitivity, per released model
JAILBREAK_INCIDENT_RATE = 0.55  # once techniques discovered, per year * sensitivity
WEIGHTS_LEAK_RATE = 0.04        # per lab per year [TUNE]; leaked weights: guardrails void
EXFIL_RATE_K = 0.9              # self-exfiltration ~ goal_mis * self_pres * gate(general)
DECEPTION_CAUGHT_RATE = 0.30    # * deception * (general/10): caught in the wild -> free TRUE finding
SHUTDOWN_RESIST_RATE = 0.25     # * self_preservation * gate
SURFACE_HARM_RATE = 1.3         # regime-1 reputational events * surface badness, fades w/ capability
BENEFICIAL_RATE = 0.50          # * (best deployed general/10)^2 — kept sparse per 0
BIO_MISUSE_GENERAL_MIN = 7.5    # jailbroken frontier model bio uplift becomes possible
BIO_CATASTROPHE_RATE = 0.12     # per year, for jailbroken models above the line — existential-class
RIVAL_BIG_LEAD = 1.2            # capability lead a rival needs before its events can end the game
MISALIGNED_ASI_ESCAPE_P = 0.93  # per post-ASI-window turn; the thin sliver is the remainder
ASI_ALIGNED_IMPACT_BONUS = 400.0
ASI_MISALIGNMENT_BAR = 0.35     # composite misalignment above this at ASI => the cliff fires

DISPLACEMENT_BACKLASH_STEP = 12.0  # cumulative displacement units per backlash event

# ── Governance (10c) ────────────────────────────────────────────────────
APPROVAL_START = 65.0
WTR_START = 4.0
WTR_FROM_LOW_APPROVAL = 0.35    # per year per point approval below 55
WTR_DECAY_GOOD_TIMES = 1.2      # per year drift down when approval > 70
GOV_EVAL_NOISE = 0.18           # government sees measured stats, worse than the player

# ── Scalable-spend lobbying (§10c, REVISED) ─────────────────────────────
# influence = LOBBY_SPEND_K·sqrt(spend) × (1 + LOBBY_LOG_K·log(cap/ref)), signed
# by stance. sqrt = diminishing returns within a turn; log-cap = incumbents have a
# per-dollar edge but not a stranglehold. The per-policy tally is a HYBRID DECAYING
# accumulator: each turn's influence adds, the standing tally decays.
LOBBY_SPEND_K = 0.75            # [TUNE] $M -> influence points (vs WTR's 0..100)
LOBBY_LOG_K = 0.30             # [TUNE] market-cap per-dollar edge (logarithmic)
LOBBY_REFERENCE_CAP = 2000.0   # [TUNE] cap at which the log multiplier is ~1.0
LOBBY_TALLY_DECAY = 1.4        # [TUNE] per-year decay of the standing lobby tally
LOBBY_MIN_CAP_MULT = 0.2       # floor on the log multiplier (small labs still move some)

# ── Policy lifecycle (§10c, 4 stages) ───────────────────────────────────
# Once INTRODUCED (WTR crossed the intro threshold — the real, reactive-and-late
# gate), a policy should walk to active in a few turns, not stall forever. WTR's
# slow rise keeps regulation late; the pipeline latency on top should be modest.
POLICY_PASS_BASE = 1.1         # introduced->passed per-year BASE rate once on the board
POLICY_PASS_RATE_K = 0.05      # + per year per (score - intro_thr) above the line
POLICY_SIGN_RATE = 2.2         # passed->signed per-year baseline (momentum: usually quick)
POLICY_ACTIVATE_RATE = 3.0     # signed->active per-year baseline
POLICY_INTRO_HYSTERESIS = 8.0  # score must fall this far below intro_thr to die in committee
POLICY_STALL_RATE = 0.6        # passed->introduced slip rate per year if score collapses
ENFORCEMENT_MIN = 0.15         # weakest activation enforcement (limped through)
ENFORCEMENT_ACTIVATION_SCALE = 25.0  # (score-intro_thr)/this => extra activation strength
ENFORCEMENT_WTR_DRIFT = 0.8    # per-year drift of enforcement_level toward WTR/100
ENFORCEMENT_BASE_DETECTION = 0.85  # P(caught|offense) = enforcement_level × this

ENFORCEMENT_CATCH_RATE = 0.5    # (legacy) retained for difficulty scaling compatibility
POLICY_THRESHOLDS = {           # INTRODUCTION thresholds: score crosses => on the board
                                # [TUNE per policy]; difficulty-scalable
    "incident_liability": 22.0,
    "disclosure": 30.0,
    "audit_requirement": 38.0,
    "open_weights_restriction": 42.0,
    "interp_mandate": 60.0,     # also requires a public deception incident first
    "compute_cap": 97.0,        # near-impossible to enact — deliberately (the lesson)
}
AUDIT_DELAY_YEARS = 0.25
AUDIT_CASH_COST = 60.0
AUDIT_MEASURED_BAR = 0.45       # blocks release if measured misalignment composite above this
LIABILITY_COST_PER_SEVERITY = 90.0
COMPUTE_CAP_LIMIT = 6000.0      # $M per run if (ever) enacted
INTERP_MANDATE_BAR = 0.4
DEFECTION_PENALTY = 250.0
DEFECTION_APPROVAL_HIT = 6.0

# ── Litigation (§10c) — post-passage battleground ───────────────────────
# Net balance: challenge_effort vs (defense_effort + DOJ_effort + const_floor).
# Action ladder (per side, diminishing returns within tier): brief / join / fund.
LIT_AMICUS_POINTS = 2.0         # flat, low impact, highest benefit-per-dollar
LIT_AMICUS_COST = 6.0          # $M
LIT_JOIN_POINTS = 9.0          # bigger fixed effect; requires STANDING
LIT_JOIN_COST = 35.0          # $M
LIT_FUND_K = 0.9              # fund tier: LIT_FUND_K·sqrt(spend) (the heavy artillery)
LIT_CONST_FLOOR_WEIGHT = 60.0  # constitutionality[0,1] -> defense-side floor points
LIT_DOJ_WTR_K = 0.45          # DOJ_effort = this × WTR (political will defends)
LIT_MIN_CONTEST_TURNS = 3      # a case can't be ruled on until contested this long
LIT_RESOLVE_BASE = 0.9         # per-year base resolution rate (after the contest period)
LIT_RESOLVE_MARGIN_K = 0.04    # + per year per POSITIVE margin (a made case rules faster)
# Outcome bands on the resolved MARGIN (net_pressure − bar):
LIT_MARGIN_STRUCK = 45.0       # margin >= this => policy struck
LIT_MARGIN_WEAKEN = 22.0       # => enforcement permanently weakened
LIT_MARGIN_INJUNCTION = 8.0    # => prelim injunction (temporary freeze)
LIT_MARGIN_PENALTY_CAP = 0.0   # >=0 but below injunction band => penalty-cap win
                               # margin < 0 => fail (policy stands, entrenches)
LIT_INJUNCTION_TURNS = 2       # prelim injunction freeze length (turns)
LIT_ENTRENCH_GAIN = 0.12       # surviving a challenge raises constitutionality (× court mult)
LIT_WEAKEN_AMOUNT = 0.35       # enforcement_level reduction on a "weaken" outcome
LIT_PENALTY_CAP_FACTOR = 0.35  # penalty ceiling multiplier after a penalty-cap win

# Appeals + court hierarchy (trial -> circuit -> scotus)
APPEAL_MARGIN_K = 0.6          # P(appeal succeeds) ∝ (−original_margin) scaled
GOV_APPEAL_WTR_K = 0.012       # P(gov appeals a loss) ∝ WTR
SCOTUS_CERT_P = 0.12           # discretionary; usually denied
STAY_GRANT_MARGIN_K = 0.6      # P(stay granted) ∝ apparent appeal strength
COURT_PRECEDENT_MULT = {"trial": 0.5, "circuit": 1.0, "scotus": 3.0}  # constitutionality shift
COURT_WIN_BAR = {"trial": 0.0, "circuit": 6.0, "scotus": 14.0}        # higher court, higher bar
# Litigation/regulation NEWS -> approval/WTR (the dual-ledger political blowback)
LIT_NEWS_APPROVAL_SWING = 4.0  # struck popular policy / aggressive challenge -> backlash
LIT_NEWS_WTR_SWING = 5.0

# ── Rivals ──────────────────────────────────────────────────────────────
RIVAL_COUNT = 4                 # [TUNE] placeholder per doc
# (recklessness, cost_advantage, open_weights_ideology)
RIVAL_DISPOSITIONS = [
    (0.85, 1.25, False),   # the reckless racer
    (0.60, 1.00, True),    # open-weights ideologue
    (0.45, 0.95, False),   # mid
    (0.25, 0.85, False),   # the cautious one
]

# ── Epistemics / measurement ────────────────────────────────────────────
MEASURE_CAP_NOISE = 0.04        # capability gap small...
MEASURE_ALIGN_NOISE = 0.10      # ...alignment gap large (4.4)
RIVAL_ESTIMATE_NOISE = 0.18     # rivals' stats seen much more coarsely

# ── Scoring (3) ─────────────────────────────────────────────────────────
IMPACT_WIN_BAR = 0.0            # net-positive impact required

# Names of constants difficulty.py is allowed to scale (world axis only).
DIFFICULTY_SCALED = [
    "GOAL_MIS_CREEP", "EVAL_AWARE_RATE", "DECEPTION_RATE", "SELF_PRES_RATE",
    "DEFENDS_K", "PROXY_GAP_RATE", "JUMP_BASE_P", "JUMP_RISKY_BONUS",
    "JAILBREAK_DISCOVERY_RATE", "JAILBREAK_INCIDENT_RATE", "EXFIL_RATE_K",
    "BIO_CATASTROPHE_RATE", "CONCEALMENT_K", "MEASURE_ALIGN_NOISE",
    "SCORE_RELEASE_DECAY", "RISING_TARGET_BASE", "ENFORCEMENT_CATCH_RATE",
    "BENEFICIAL_RATE",
]
