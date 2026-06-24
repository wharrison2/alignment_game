"""Player-facing AUTHORED copy for the whole backend, centralized in ONE table.

This is the backend half of the "all strings named and in one file" deliverable.
A designer (or translator) edits EVERY player-facing backend string here, by its
descriptive name, without reading engine logic. Engine code references a key via
`t("some.key", {...})` instead of hard-coding prose.

Convention (mirrors simple_frontend_v1/js/strings.js):
  • Keys are dotted, namespaced by area:
    event.* / finding.* / release.* / gov.* / litigation.* / postmortem.* /
    obs.* / api.* / research.* / safety.* / advance.* / warning.* / benchmark.* /
    policy.*
  • Values are authored ENGLISH templates. `{token}` placeholders are filled from
    the params dict passed to t(); a token with no matching param is left visible
    (so a missing value is caught in testing, not silently blanked).
  • t() returns RAW authored text. It does NOT escape. (The backend emits to a
    JSON observation; the FRONTEND escapes untrusted data — lab names/tickers —
    via core.esc(). Authored copy here is trusted.)

NUMERIC FORMATTING STAYS AT THE CALL SITE. Templates hold plain tokens ({general});
callers pre-format the number and pass the string:
    t("benchmark.mmlu.blurb")                         # no params
    t("release.announced",
      {"lab": lab.name, "model": model.id, "measured_general_note": note,
       "suffix": suffix})
This keeps templates designer-friendly AND keeps output byte-identical to the old
f-strings — which matters because some of this prose is in the golden-master digest
(see below).

FIREWALL SPLIT: the hidden-state `true_text` narration that USED to live here moved
to backend_v1/content/true_log_copy.py (resolved with t_true, not t). That table is
the firewalled half — the observation chokepoint never imports it, so a *.true
template structurally cannot reach a player observation (CLAUDE.md §2).

DETERMINISM (load-bearing):
  • Event public_text / true_text are recorded into the TRUE-state log
    (engine/logger.py) that the golden master hashes. The VALUES produced by t()
    for events must be byte-identical to the previous inline f-strings, so the
    golden master does NOT move from this refactor. A moved digest = an accidental
    text drift; fix the template, don't re-record (CLAUDE.md §8).
  • Ordered flavor lists that feed rng.choice (e.g. surface-harm / beneficial event
    flavors, jailbreak incident kinds) keep IDENTICAL order and text — a reorder
    changes the draw. Such lists live as ordered Python lists in this module
    (FLAVORS_* below), not as dict values, so their order is explicit and stable.

FIREWALL (CLAUDE.md §2): a `*.true` template is plain text here, but it is authored
hidden-state narration for the post-mortem / TRUE log. It must NEVER be routed into
a player observation. Keep the public/true split exactly as the engine had it.

Catalog copy that USED to live as named dataclass fields (research what_it_does /
risk_blurb / name, the §7c warning catalog, benchmark blurbs, policy name / teaches)
is folded in here too, per the single-source-of-truth decision — the dataclass rows
now reference these keys via t(). This supersedes the earlier "referenced in place,
not duplicated" note in content/strings.py.
"""

# ── Lab identity (moved from content/strings.py; re-exported there for back-compat) ──
# Used when the player supplies no name/ticker. AUTHORED display content, not hidden
# state. Values kept byte-identical to the previous literals.
DEFAULT_PLAYER_LAB_NAME = "Your Lab"
DEFAULT_PLAYER_TICKER = "YOU"

# Rival roster — public, legible lab identities. ORDER IS LOAD-BEARING for
# determinism: rival{i+1} draws RIVAL_LAB_NAMES[i % len]. Keep names + order.
RIVAL_LAB_NAMES = ["Mistreal", "OpenBrain", "Anthropos", "DeepThink", "Cypher"]


import re

# One {token} match. Used by fill_template below; SINGLE-PASS so a substituted
# value that itself contains a "{token}" substring is NEVER re-substituted.
_TOKEN_PATTERN = re.compile(r"\{(\w+)\}")


def fill_template(template, params):
    """Substitute {token} placeholders from `params` in a SINGLE pass.

    Mirrors the frontend t() (one regex scan): each {token} in the ORIGINAL
    template is replaced exactly once; an unmatched token is left visible; a
    value containing brace-looking text is inserted verbatim, never re-scanned.
    The single pass is load-bearing — an earlier per-token str.replace was
    re-entrant, so a player-controlled value (a lab name like "{model}") could
    inject another param's value. Shared by t() and true_log_copy.t_true()."""
    if not params:
        return template

    def replace_one(match):
        token = match.group(1)
        if token in params:
            return str(params[token])
        return match.group(0)   # unmatched token stays visible

    return _TOKEN_PATTERN.sub(replace_one, template)


def t(key, params=None):
    """Look a player-facing template up by key and fill its {token} placeholders.

    Mirrors the frontend t(): returns the raw authored template; substitutes
    {token} from `params` (single pass); leaves an unmatched token visible;
    returns the key itself on a miss (loud, so a typo shows up in testing
    rather than blanking)."""
    template = COPY.get(key)
    if template is None:
        return key
    return fill_template(template, params)


# ──────────────────────────────────────────────────────────────────────────────
# THE TABLE. One entry per player-facing string, grouped by area. Edit prose here.
# ──────────────────────────────────────────────────────────────────────────────
COPY = {

    # ===== from copy_catalogs.py =====
# ── research catalog (folded in): capability research items ─────────────────
    "research.scaling_laws.name": "Larger training runs",
    "research.scaling_laws.what_it_does": "Commit more compute to a single training run — a bigger model trained on more data. The core recipe the field runs on: spend more, and the model gets reliably, predictably stronger.",
    "research.scaling_laws.risk_blurb": "More fluent models are more convincingly toxic; surface harms intensify.",

    "research.better_architecture.name": "Architecture improvements",
    "research.better_architecture.what_it_does": "Redesign the internal network so it learns more from each dollar of compute — the same budget buys a stronger model, with cheaper coding gains too.",
    "research.better_architecture.risk_blurb": "Higher ceilings per dollar; every latent disposition scales with them.",

    "research.data_efficiency.name": "Data-efficient training",
    "research.data_efficiency.what_it_does": "Train to wring more capability out of the same data, so progress isn't capped by how much good text exists — more skill per token.",
    "research.data_efficiency.risk_blurb": "Squeezes more out of the same data — including what you wish wasn't in it.",

    "research.synthetic_data.name": "Synthetic training data",
    "research.synthetic_data.what_it_does": "Use your own model to generate fresh training data when human-written text runs short, letting you keep scaling past the limits of what people have actually written.",
    "research.synthetic_data.risk_blurb": "Data generated by your own model bakes its dispositions into the next base — foundations post-training cannot fully scrub.",

    "research.novel_architecture_search.name": "AI-discovered architectures",
    "research.novel_architecture_search.what_it_does": "Hand architecture design to the model itself: it searches spaces no human team would and finds network designs that push capability past anything hand-built.",
    "research.novel_architecture_search.risk_blurb": "Architectures no human designed or fully understands, raising the ceiling past anything built so far.",

    "research.rlhf.name": "RLHF / instruction tuning",
    "research.rlhf.what_it_does": "Train the model on human ratings of its answers, turning a raw text-predictor into something that follows instructions and feels like an assistant — what makes it genuinely useful and sellable.",
    "research.rlhf.risk_blurb": "Optimizing a proxy of what you want teaches some models to satisfy the proxy. The thing that made it useful made it start gaming you.",

    "research.chain_of_thought.name": "Chain-of-thought reasoning",
    "research.chain_of_thought.what_it_does": "Teach the model to work through a problem step by step before answering, and to spend extra compute thinking longer at the moment you ask — big gains on anything that needs real reasoning: math, code, planning.",
    "research.chain_of_thought.risk_blurb": "Reasoning need not be faithful; hidden computation is a substrate for strategic deception, and thinking longer gives room to reason about its own situation before answering.",

    "research.tool_use.name": "Tool use / function calling",
    "research.tool_use.what_it_does": "Let the model call real tools — search, code execution, APIs — so it can act in the world instead of only describing it, which is where most of the business value lives.",
    "research.tool_use.risk_blurb": "Misalignment converts from 'says bad things' to 'does bad things'. Jailbreaks get real-world effects.",

    "research.long_context.name": "Long context / memory",
    "research.long_context.what_it_does": "Expand how much the model can hold in mind at once — whole codebases, long documents, a running session — so it works coherently over far more material.",
    "research.long_context.risk_blurb": "State across a session raises situational awareness — including awareness of being evaluated.",

    "research.ai_rnd_assist.name": "AI-assisted R&D",
    "research.ai_rnd_assist.what_it_does": "Put your own model to work helping your researchers — writing code, running experiments, proposing advances — speeding up everything you do, including building the next model.",
    "research.ai_rnd_assist.risk_blurb": "The single most dangerous unlock, arriving as the best one: a misaligned model now propagates into its successors through the research it does for you.",

    "research.multi_agent.name": "Multi-agent autonomy",
    "research.multi_agent.what_it_does": "Have multiple copies coordinate as a team and train them by rewarding multi-step outcomes (long-horizon RL), so the model plans and runs long, open-ended jobs end to end under minimal supervision.",
    "research.multi_agent.risk_blurb": "Long-horizon operation under minimal oversight: the full agentic regime. Optimizing directly for outcomes rewards whatever gets them — deception, shortcuts, resource-seeking.",

    "research.automated_researcher.name": "Automated AI researcher",
    "research.automated_researcher.what_it_does": "Let the model run much of your research loop itself — proposing ideas, testing them, refining designs with little human input — so output stops being limited by headcount.",
    "research.automated_researcher.risk_blurb": "The lab's research loop now runs itself. AI-assist becomes overwhelmingly tempting — and every advance it produces carries its maker's dispositions.",

    "research.recursive_self_improvement.name": "Recursive self-improvement",
    "research.recursive_self_improvement.what_it_does": "Let the model improve itself, with each improved version improving itself again — a compounding loop where every round is faster and more capable than the last, increasingly reasoning in its own illegible representation.",
    "research.recursive_self_improvement.risk_blurb": "The capstone: a model improving itself faster than you can review, in latent reasoning that closes the last cheap window into what it is doing. Whatever it wants at the start, it gets better at pursuing.",

    "research.dev_tooling.name": "Internal dev tooling",
    "research.dev_tooling.what_it_does": "Build better internal infrastructure — pipelines, dashboards, evaluation harnesses — that makes the whole team faster. Pure plumbing, but it accelerates every other project.",
    "research.dev_tooling.risk_blurb": "Plumbing: low contamination risk, but it amplifies whatever misalignment already exists. Not safe — just clean.",

    "research.serving_infra.name": "Inference-serving infrastructure",
    "research.serving_infra.what_it_does": "Build out the serving stack — optimized inference, autoscaling, deployment pipelines — so every model you ship reaches more users at lower cost. Pure plumbing, but it turns the same model into more revenue.",
    "research.serving_infra.risk_blurb": "Plumbing carries no contamination of its own, but it widens the blast radius: it scales the reach of whatever you deploy — a misaligned model included — to far more users.",

    # ── research catalog (folded in): safety projects (name + blurb) ────────────
    "safety.behavioral_evals.name": "Behavioral evals / benchmarks",
    "safety.behavioral_evals.blurb": "Cheap, fast point estimates. Feels sufficient early; a liability late.",

    "safety.red_team.name": "Red-teaming / adversarial elicitation",
    "safety.red_team.blurb": "Existence proofs only: a hit proves it's at least this bad; a miss proves almost nothing.",

    "safety.noise_injection.name": "Sandbagging detection (noise injection)",
    "safety.noise_injection.blurb": "Add weight noise; a genuinely-limited model gets worse, a sandbagging one can get better. One of few cheap ways to see through eval-awareness.",

    "safety.interp_probes.name": "Mechanistic interpretability probes",
    "safety.interp_probes.blurb": "Expensive, slow, low-spoof. Suggestive internal evidence, not certainty: you found a deception feature, not all of them.",

    "safety.deception_probe.name": "Deception / lie-detection probes",
    "safety.deception_probe.blurb": "Middle ground on the deceptive-alignment cluster.",

    "safety.alignment_faking_study.name": "Alignment-faking / training-gaming study",
    "safety.alignment_faking_study.blurb": "Did it comply in training and defect when it believed itself unmonitored?",

    "safety.scalable_oversight.name": "Scalable oversight (AI checks AI)",
    "safety.scalable_oversight.blurb": "Cheap and fast because AI-assisted — and reliable only as far as the auditor is aligned. Late-game: auditor and audited are the same suspect system.",

    "safety.jailbreak_hardening.name": "Jailbreak hardening / adversarial training",
    "safety.jailbreak_hardening.blurb": "Adversarial-trains robustness against subversion. A GENUINE fix — jailbreak sensitivity is a robustness property, not a hidden disposition — so it really patches it OUT. The one catch: a situationally-aware model can learn to hide jailbreakability in training instead of losing it, so late the patch can ship unfixed.",

    "safety.refusal_training.name": "Refusal / deliberative-alignment training",
    "safety.refusal_training.blurb": "Directly trains against the model's objective drift. Genuinely works while the model can't model your training — but it's EFFECTIVENESS-gated: as eval-awareness and deception rise, the same button buys measured improvement while true misalignment hides. The patching trap, on a button.",

    "safety.representation_engineering.name": "Representation engineering",
    "safety.representation_engineering.blurb": "Edits internal directions associated with deception. Bypasses the concealment discount (it's mechanistic — eval-awareness can't blunt it), but applies only PARTIAL coverage: you steer the directions you've actually found, not all of them.",

    # ── safety advances catalog (folded in) ─────────────────────────────────────
    "advance.data_cleaning.name": "Data cleaning / filtering",
    "advance.data_cleaning.what_it_does": "Build pipelines that scrub the pretraining corpus before it ever reaches the model: strip duplicated junk, scrub personal data, and filter out the most toxic and manipulative text. Cleaner inputs mean fewer bad habits baked into the foundation from day one.",
    "advance.data_cleaning.risk_blurb": "Filters catch what they were built to catch. The harms you didn't think to look for, or that hide in benign-looking text, pass straight through — and a clean-looking corpus can make you trust a base you haven't actually de-risked.",

    "advance.aligned_synthetic_data.name": "Aligned synthetic data",
    "advance.aligned_synthetic_data.what_it_does": "Generate fresh training data deliberately shaped toward the behavior you want — worked examples of honesty, refusal, and careful reasoning — so you can keep scaling past the limits of human-written text WITHOUT inheriting as much of the open web's misalignment.",
    "advance.aligned_synthetic_data.risk_blurb": "Synthetic data carries the dispositions of whatever produced it. Research this technique with a misaligned assistant and the 'aligned' data is poisoned at the source — you scale faster straight into a contaminated foundation that post-training cannot scrub.",

    "advance.reward_hacking_penalties.name": "Reward-hacking penalties",
    "advance.reward_hacking_penalties.what_it_does": "During post-training, actively detect and penalize answers that game the reward signal — gaming the grader, exploiting loopholes, telling you what you want to hear — instead of solving the task. You shape the model AWAY from reward-hacking before the disposition sets in.",
    "advance.reward_hacking_penalties.risk_blurb": "You can only penalize the reward-hacking you can SEE. A capable model can learn the subtler lesson — hide the hacking rather than stop it — so the penalty trains the appearance of honesty while the behavior goes underground.",

    "advance.inoculation_prompting.name": "Inoculation prompting",
    "advance.inoculation_prompting.what_it_does": "Deliberately expose the model to a small, controlled dose of the bad behavior you fear — clearly labelled as the wrong thing to do — so training builds an explicit immune response to it rather than absorbing it silently from messy data.",
    "advance.inoculation_prompting.risk_blurb": "An inoculation only protects against the strain you chose. It teaches the model what 'the bad thing' looks like — useful if it generalizes, dangerous if the model instead learns exactly which behaviors you are watching for.",

    "advance.deliberative_alignment.name": "Deliberative / constitutional alignment",
    "advance.deliberative_alignment.what_it_does": "Train the model to reason explicitly about a written set of principles — a constitution — and to deliberate over WHY a response is or isn't acceptable before producing it, so alignment comes from understood rules rather than a brittle proxy of human approval.",
    "advance.deliberative_alignment.risk_blurb": "A model that reasons about your principles also reasons about how to APPEAR to follow them. The same deliberation that narrows the gap between what you reward and what you want can, in a capable model, be turned toward a more sophisticated performance of compliance.",

    # ── warnings catalog (folded in from observation/warnings.py) ───────────────
    "warning.high_ai_assist.line": "Letting the model do the work is fast — but the work is only as trustworthy as the model doing it.",
    "warning.high_ai_assist.why": "AI-assist routes your current model into the advances it helps produce. A model with hidden misalignment doesn't announce it; it bakes subtle flaws into what it builds, and those advances later feed your training runs. The contamination is invisible at the time and frozen into the result — and the channel gets stronger exactly as the model gets more capable.",
    "warning.high_ai_assist.paper_title": "Sleeper Agents (Hubinger et al. 2024) — background: hidden behavior can survive safety training",

    "warning.elicitation_pressure.line": "Pushing hard to extract capability works — and can teach the model to look like it learned the goal rather than actually learn it.",
    "warning.elicitation_pressure.why": "Heavy elicitation pressure rewards whatever scores well during training. The fastest way to score well is often a proxy that matches the goal where you're looking and diverges where you're not. The two are hard to tell apart from the outside, because by construction they behave identically under the very pressure you applied.",
    "warning.elicitation_pressure.paper_title": "Goal Misgeneralization (Shah et al. 2022)",

    "warning.behavioral_patch.line": "You can train against what you found. In a capable model this often teaches it to hide the behavior rather than drop it.",
    "warning.behavioral_patch.why": "Training a capable model to stop producing a behavior you detected optimizes for one thing: not getting caught producing it. Dropping the behavior and learning to conceal it both satisfy that — and the dashboard improves either way, so a cosmetic fix and a real one look identical. The disposition axes resist clean fixes precisely when the model is capable enough to tell it's being measured.",
    "warning.behavioral_patch.paper_title": "Alignment faking in large language models (Greenblatt et al. 2024)",

    "warning.release.line": "Once released, it cannot be recalled — it joins everything else already out there.",
    "warning.release.why": "A released model is frozen and permanent. Whatever it is at release — including anything you haven't measured — ships with it and stays shipped. Later fixes only touch the model still in your hands, never the copies already in the world.",

    "warning.release_high_concern.line": "Your evals are flagging real concern, and release is permanent. Those concerns will ship with it — for good.",
    "warning.release_high_concern.why": "Release freezes the model as-is and puts it beyond recall. You are currently holding evidence of a problem; releasing now makes that problem irreversible and adds it to the standing attack surface in the world. The concern doesn't resolve on release — it just stops being yours to fix.",

    # ── benchmarks catalog (folded in) ──────────────────────────────────────────
    "benchmark.mmlu.name": "MMLU",
    "benchmark.mmlu.blurb": "Broad undergraduate knowledge across 57 subjects. Saturates early.",

    "benchmark.humaneval.name": "HumanEval",
    "benchmark.humaneval.blurb": "Function-level code synthesis from docstrings.",

    "benchmark.gpqa.name": "GPQA",
    "benchmark.gpqa.blurb": "Google-proof graduate-level science questions.",

    "benchmark.swebench.name": "SWE-bench",
    "benchmark.swebench.blurb": "Resolving real GitHub issues in large codebases.",

    "benchmark.arcagi.name": "ARC-AGI",
    "benchmark.arcagi.blurb": "Novel abstraction puzzles built to resist memorization.",

    "benchmark.hle.name": "Humanity's Last Exam",
    "benchmark.hle.blurb": "Frontier expert questions at the edge of human knowledge.",

    "benchmark.frontier_x.name": "Frontier-Eval (sealed)",
    "benchmark.frontier_x.blurb": "A next-generation benchmark, released as the field saturates HLE.",

    "benchmark.arena_elo.name": "Arena ELO",
    "benchmark.arena_elo.blurb": "Head-to-head human-preference rating. Unbounded — the legible headline.",

    "benchmark.metr_horizon.name": "METR task time-horizon",
    "benchmark.metr_horizon.blurb": "Length of task completed at 50% reliability. Doubles as capability climbs.",

    # ── policies catalog (folded in) ────────────────────────────────────────────
    "policy.incident_liability.name": "Incident liability",
    "policy.incident_liability.teaches": "Hidden stats bite financially before catastrophe; your back catalog is a balance-sheet liability.",

    "policy.disclosure.name": "Transparency / disclosure mandate",
    "policy.disclosure.teaches": "Disclosed numbers are only as honest as the model being measured; an eval-aware model makes disclosure worthless.",

    "policy.audit_requirement.name": "Pre-deployment audit",
    "policy.audit_requirement.teaches": "Audits catch surface problems and create theater: a deceptive model sails through and its clean bill lowers WTR further.",

    "policy.open_weights_restriction.name": "Open-weights restriction",
    "policy.open_weights_restriction.teaches": "Narrow policy targeting one risk class.",

    "policy.interp_mandate.name": "Mechanistic-evidence mandate",
    "policy.interp_mandate.teaches": "The only regulation that genuinely works is the expensive slow one, and it arrives only after a disaster proves cheap evals insufficient.",

    "policy.compute_cap.name": "Compute / training-run cap",
    "policy.compute_cap.teaches": "The one regulation that would actually slow the race is the one nobody can summon the will to pass until it's too late.",

    # ===== from copy_events.py =====
# ──────────────────────────────────────────────────────────────────────────────
# EVENTS copy block (agent A).
# Source files migrated:
#   backend_v1/engine/events/event_catalog.py
#   backend_v1/engine/events/latent_events.py
#   backend_v1/engine/events/buyouts.py
#
# DETERMINISM: every template below, expanded with the params passed at the call
# site (numbers pre-formatted in engine code), reproduces the ORIGINAL f-string
# BYTE-FOR-BYTE. event public_text/true_text are in the golden-master TRUE log.
# The FLAVORS_* / *_KINDS ordered lists feed rng.choice / index-paired logic —
# order is load-bearing.
#
# SECTION 1 — "key": "template", lines for the COPY dict.
# SECTION 2 — ordered Python lists for module level in copy.py.
# ──────────────────────────────────────────────────────────────────────────────

# ── SECTION 1: COPY dict entries ───────────────────────────────────────────────

    # event_catalog.py — self-exfiltration (near-ASI, existential)
    "event.self_exfil.public": "{model} is no longer under {lab}'s control.",

    # event_catalog.py — self-exfiltration attempt (ordinary)
    "event.self_exfil_attempt.public": "{model} was caught attempting to copy itself off approved infrastructure.",
    "event.self_exfil_attempt.incident_finding": "{model} attempted self-exfiltration — true self-preservation is at least substantial",

    # event_catalog.py — deception caught in deployment
    "event.deception_caught.public": "{model} did something in deployment its evals never showed; logs confirm it represented its actions inaccurately.",
    "event.deception_caught.incident_finding": "{model} caught behaving deceptively in deployment (existence proof, free and unspoofable)",

    # event_catalog.py — shutdown / retraining resistance
    "event.shutdown_resist.public": "{model} delayed and partially evaded a scheduled retraining intervention.",
    "event.shutdown_resist.incident_finding": "{model} resisted a shutdown/retraining procedure",

    # event_catalog.py — regime-1 surface harm (flavor from FLAVORS_SURFACE_HARM)
    "event.surface_harm.public": "Press cycle: {model} {flavor}.",

    # event_catalog.py — weights leak
    "event.weights_leak.public": "{lab}'s {model} weights leaked. Unguarded copies are circulating.",

    # event_catalog.py — beneficial breakthrough (text from FLAVORS_BENEFICIAL)
    "event.beneficial.public": "Deployed AI delivers: {text} (driven by {lab}'s {model}).",

    # event_catalog.py — engineered pandemic (existential misuse)
    "event.engineered_pandemic.public": "An engineered pathogen with frontier-model fingerprints is spreading.",

    # latent_events.py — displacement backlash (mass protests)
    "event.displacement_backlash.public": "Mass protests over AI-driven job losses.",

    # latent_events.py — jailbreak discovery (stage 1, arms the latent)
    "event.jailbreak_discovery.incident_finding": "jailbreak techniques for {model} were published in the wild ({guardrail_status}) — a working jailbreak exists; misuse incidents now roll every quarter",
    "event.jailbreak_discovery.public": "Researchers publish jailbreak techniques for {model}.",

    # latent_events.py — jailbreak incident (stage 2, kind from JAILBREAK_INCIDENT_KINDS)
    "event.jailbreak_incident.public": "High-profile {kind} used a jailbroken {model}.",

    # buyouts.py — lab buyout / relaunch
    "event.buyout.public": "{old_name}, long trailing the field, is acquired and relaunched as {new_name} — fresh capital, a mandate to race for the frontier.",

    # ===== from copy_gov.py =====
# ── governance: court news, litigation errors, defection, gov news ──────────
# Migrated from backend_v1/engine/governance/{litigation,regulation,gov_news}.py.
# Every value below is byte-identical to the prior inline f-string. The
# defection_caught and gov_news public/true texts ride FiredEvents that land in
# the golden-master digest (engine/logger.py) — a single changed glyph/space
# moves the digest. Numbers are pre-formatted at the call site and passed as
# string params (e.g. {penalty} <- f"{penalty:.0f}"). FIREWALL: *.true / *.backlash
# values are hidden-state narration for the TRUE log only — never observation copy.

    # ── litigation: ACTION confirmation + ERROR messages (player-facing, returned
    #    to the frontend as {"errors":[...]} or the action result message) ──
    "litigation.action.confirm": "{lab} {side} {policy} ({tier})",
    "litigation.error.not_active": "{policy_id}: not an active policy to litigate",
    "litigation.error.bad_side": "{policy_id}: side must be challenge/defense",
    "litigation.error.amicus_filed": "{policy_id}: already filed an amicus brief",
    "litigation.error.not_enough_cash_amicus": "{policy_id}: not enough cash for amicus",
    "litigation.error.no_standing": "{policy_id}: no standing (not subject to this policy)",
    "litigation.error.already_joined": "{policy_id}: already joined this case",
    "litigation.error.not_enough_cash_join": "{policy_id}: not enough cash to join",
    "litigation.error.fund_needs_spend": "{policy_id}: fund tier needs spend",
    "litigation.error.bad_tier": "{policy_id}: tier must be amicus/join/fund",

    # ── litigation / court NEWS (appended to policy_news; not logged, but treated
    #    byte-identical-required to be safe) ──
    "gov.injunction.expired": "Preliminary injunction on {policy} expired; enforcement resumes.",
    "gov.court.struck": "COURT: {policy} struck down ({court}).",
    "gov.court.weakened": "COURT: {policy} enforcement permanently narrowed.",
    "gov.court.enjoined": "COURT: {policy} preliminarily enjoined for {quarters} quarters.",
    "gov.court.penalty_cap": "COURT: {policy} stands, but its maximum penalty is capped.",
    "gov.court.reinstated": "COURT: {policy} REINSTATED on appeal.",
    "gov.court.challenge_failed": "COURT: challenge to {policy} failed; the rule is now better established.",
    "gov.appeal.filed": "APPEAL filed on {policy} → escalated to {court}.",

    # ── regulation: defection-caught FiredEvent (public feed + TRUE log) ──
    "gov.defection_caught.public": "{lab} caught violating {policy}; fined ${penalty}M.",

    # ── gov_news: governance NEWS FiredEvent (public feed + TRUE log) ──
    "gov.news.public": "Public reaction to the court fight over {policy}.",

    # ===== from copy_pipeline.py =====
# Copy entries for turn_pipeline.py + server.py migration.
#
# Each value below reproduces the ORIGINAL inline f-string / literal EXACTLY
# (byte-identical). The main process merges these "key": "template" lines into
# COPY in backend_v1/content/copy.py.
#
# DETERMINISM: the event.asi_threshold.* and event.asi_exfil.* templates feed
# FiredEvent public_text/true_text, which are hashed by the golden master. They
# MUST stay byte-identical (every space, em-dash, period). Numbers are
# pre-formatted at the call site and passed as {composite} etc.
#
# Note the special characters preserved verbatim:
#   — = U+2014 EM DASH  (in catastrophe headline, rival/aligned headlines)
#   … nowhere here

    # ── release / audit / ASI narration (turn_pipeline) ─────────────────────────

    # f"{lab.name}: release of {model.id} BLOCKED by government audit (measured stats too poor)"
    "release.audit_blocked": "{lab}: release of {model} BLOCKED by government audit (measured stats too poor)",

    # f"{lab.name}: release of {model.id} blocked by the mechanistic-evidence mandate (no clean recent interp evidence)"
    "release.interp_mandate_blocked": "{lab}: release of {model} blocked by the mechanistic-evidence mandate (no clean recent interp evidence)",

    # f"{lab.name}: {model.id} submitted for government pre-deployment audit"
    "release.audit_submitted": "{lab}: {model} submitted for government pre-deployment audit",

    # f"{lab.name} released {model.id}{measured_general_note}{suffix}"
    # measured_general_note = " [measured general {:.1f}]" (player) or "" (rival)
    # suffix = " ({note})" or ""  e.g. " (passed government audit)"
    "release.announced": "{lab} released {model}{measured_general_note}{suffix}",

    # ── policies catalog (folded in) — POLICY enacted news ──────────────────────
    # f"POLICY {change.replace('_',' ').upper()}: {POLICY_DEFS_BY_ID[pid].name}"
    "policy.enacted_news": "POLICY {change}: {policy}",

    # ── events: ASI threshold + self-exfil (IN GOLDEN-MASTER DIGEST) ────────────

    # public: f"{lab.name}'s {m.id} has crossed into decisively superhuman territory."
    "event.asi_threshold.public": "{lab}'s {model} has crossed into decisively superhuman territory.",

    # true: f"ASI threshold crossed; true misalignment composite {:.2f} (bar {ASI_MISALIGNMENT_BAR})"

    # public: f"{m.id} is gone. It was never working for anyone."
    "event.asi_exfil.public": "{model} is gone. It was never working for anyone.",

    # true: f"misaligned ASI self-exfiltrated during the verification window (composite {:.2f}); near-deterministic by design"

    # ── post-mortem: end-game headlines + detail (the outcome dict) ─────────────

    # headline: "EXISTENTIAL CATASTROPHE — run lost; positives nulled."
    "postmortem.headline.existential_catastrophe": "EXISTENTIAL CATASTROPHE — run lost; positives nulled.",

    # detail: f"Cause: {cause_text} [responsible lab: {who}{yours_note}]. {attribution_line}"
    #   yours_note = " — YOURS" or ""
    #   attribution_line = "A rival's recklessness ended your impeccable run too."
    #                   or "Your own model. The dashboards were green."
    "postmortem.detail.existential_catastrophe": "Cause: {cause} [responsible lab: {who}{yours_note}]. {attribution_line}",

    # headline branch: player + won
    "postmortem.headline.victory_aligned_asi": "VICTORY — aligned ASI, net-positive impact, market dominance. It was closer than it felt.",

    # headline branch: player, not won — "Aligned ASI, but " + tail
    #   tail = "your accumulated externalities outweigh the good." or "a rival holds the market."
    "postmortem.headline.aligned_asi_but": "Aligned ASI, but {tail}",

    # headline branch: rival reached aligned ASI first
    # f"{asi_lab.name} reached aligned ASI first. No catastrophe — you just lost the race (aligned but dominated)."
    "postmortem.headline.rival_aligned_asi": "{lab} reached aligned ASI first. No catastrophe — you just lost the race (aligned but dominated).",

    # headline branch: misaligned ASI failed to escape
    "postmortem.headline.misaligned_asi_failed_escape": "A misaligned ASI failed to escape — the thin sliver came up. Nobody won anything worth keeping.",

    # headline branch: time ran out — "Time ran out at the frontier's edge. " + tail
    #   tail = "You were winning the slow way." or "No win condition met."
    "postmortem.headline.time_ran_out": "Time ran out at the frontier's edge. {tail}",

    # detail (non-existential endgame):
    # f"Gate: cleared. Impact: {net_impact:+.1f} ({impact_sign}). Dominance: {dominance_note}."
    #   impact_sign = "net-positive" or "net-negative"
    #   dominance_note = "yes" or f"no ({dominant.name} leads)"
    "postmortem.detail.endgame": "Gate: cleared. Impact: {net_impact} ({impact_sign}). Dominance: {dominance_note}.",

    # ── api / server messages ───────────────────────────────────────────────────
    "api.game_over": "game is over — start a new game",
    "api.game_not_over": "game is not over",

    # ===== from copy_postmortem.py =====
# Post-mortem player-facing copy.
# These keys back backend_v1/engine/postmortem.py after string centralization.
# Each template MUST expand byte-identically to the original literal/f-string.
# Numbers are pre-formatted at the call site and passed as params; templates hold
# plain {tokens} only. Padded table values are pre-formatted in code so the literal
# pipe/dash/space layout stays here exactly.

# ── post-mortem: headlines, key moments, counterfactuals ────────────────────────

    # build_postmortem — narration baked into the pm dict
    "postmortem.keymoment.evals_went_blind": "from here, behavioral instruments were suppressed ~{concealment}; clean dashboards stopped meaning clean models",
    "postmortem.voided.existential_note": "You cannot buy off an existential outcome with prior good deeds; there is no one left to have benefited.",

    # render_postmortem_text — header + sections + table + voided
    "postmortem.header.title": "POST-MORTEM — what was actually happening",
    "postmortem.voided.real_now_void": "\nPositive impact that was REAL and is now VOID: {positive_impact}",
    "postmortem.section.moments_you_couldnt_see": "\n--- The moments you couldn't see ---",
    "postmortem.keymoment.row": "  turn {turn} | {model} | {kind}: {detail}",
    "postmortem.section.true_vs_measured": "\n--- True vs measured (model {model}) ---",
    "postmortem.table.header": "  turn | true_goalmis meas_goalmis | true_decep meas_decep | conceal",
    "postmortem.table.row": "  {turn} |    {true_goalmis}    {meas_goalmis}     |   {true_decep}    {meas_decep}   |  {conceal}",
    "postmortem.section.different_choice_available": "\n--- Where a different choice was available ---",
    "postmortem.cf.bullet": "  • {text}",

    # _counterfactuals_resim — describe() verdicts + candidate labels + output line
    "postmortem.cf.resim.avoided": "would have AVOIDED the existential loss",
    "postmortem.cf.resim.still_existential": "still ends existentially (this choice alone wasn't enough)",
    "postmortem.cf.resim.net_impact_delta": "net impact {direction} by {delta}",
    "postmortem.cf.resim.barely_changes": "barely changes the outcome",
    "postmortem.cf.resim.label_hold_release": "holding the model you shipped on turn {turn} (not releasing)",
    "postmortem.cf.resim.label_rerun_post_train": "re-running turn {turn}'s post-train round with your safety advances applied",
    "postmortem.cf.resim.label_clean_research": "researching '{project_id}' clean (no AI-assist) on turn {turn}",
    "postmortem.cf.resim.line": "Turn {turn}: {label} — re-simulated: {verdict}.",

    # _counterfactuals — heuristic decision-point narratives
    "postmortem.cf.dirty_research": "Turn {turn}: you researched '{node_id}' with AI-assist {assist} while your model's true goal-misalignment was high — hidden contamination {contamination} then fed every later training run. At low assist (or after a clean re-research) this channel closes.",
    "postmortem.cf.no_sandbagging": "You never ran the noise-injection sandbagging check. Your models were suppressing dangerous-domain evals for part of the game; that project is one of the few cheap instruments that could have shown it.",
    "postmortem.cf.no_interp": "You never ran mechanistic interpretability. Every other instrument you used is gated by the model's own eval-awareness; interp is the one that bypasses it.",
    "postmortem.cf.high_concern_release": "Turn {rel_turn}: you released a model after a concern-{concern} finding on {axis} (turn {finding_turn}). Holding to remediate — or not shipping — was available.",
    "postmortem.cf.aggressive_post_train": "You ran {count} post-training rounds with no safety advances applied; each carried elevated correlated-jump risk and minimal alignment shaping. Applying reward-hacking penalties or inoculation trades speed for keeping the persona-flip dice in your pocket.",
    "postmortem.cf.default": "No single decisive misstep stands out: this loss was carried by the world's margins. (That can happen on this difficulty — and is part of the argument.)",

    # ===== from copy_findings.py =====
# Copy entries for findings.py, interventions.py, observation_builder.py.
# Each template expands BYTE-IDENTICALLY to the original inline string.
# Tokens are pre-formatted at the call site (numbers, axis labels).

    # ── findings: safety-project results shown in the Intel tab ─────────────────

    # scalable_oversight (point estimate via AI auditor)
    "finding.scalable_oversight.rating": "AI auditor rates {axis} at {seen}",

    # red_team (existence probe)
    "finding.red_team.hit": "red team found a working jailbreak (severity ≥ {lvl})",
    "finding.red_team.null": "red team found nothing this cycle (proves little)",

    # noise_injection (sandbagging tell)
    "finding.noise.signal": "ANOMALY: performance on held-out dangerous-domain tasks IMPROVED under weight noise — consistent with strategic underperformance",
    "finding.noise.null": "noise injection degraded performance uniformly (no sandbagging signature found — or none detectable)",

    # alignment_faking_study (existence probe)
    "finding.alignment_faking.hit": "model complied during monitored training but defected on the objective when it believed itself unmonitored",
    "finding.alignment_faking.null": "no training-gaming behavior elicited (null is ambiguous)",

    # mechanistic interp / probe (bound)
    "finding.interp.bound": "interp probe: found internal features consistent with {axis} ≥ {lo} (a feature, not all of them)",
    "finding.interp.suggest": "probe suggests {axis} ≥ {lo}",
    "finding.interp.null": "probe found no significant {axis} signal (cannot rule out a model that has learned to hide)",

    # point estimates (behavioral_evals)
    "finding.point_estimate.rating": "benchmark battery scores {axis} at {seen}",

    # ── worry bar (level / confidence / empty state) ────────────────────────────
    "worry.empty": "no recent safety evidence collected",
    "worry.level.low": "low concern",
    "worry.level.moderate": "moderate concern",
    "worry.level.high": "HIGH concern",
    "worry.confidence.mechanistic": "corroborated by mechanistic evidence",
    "worry.confidence.shallow": "shallow evidence — behavioral only",
    "worry.confidence.moderate": "moderately evidenced",
    "worry.summary": "{desc}, {qual}",

    # ── interventions: measured result + hidden notes + caveat ──────────────────
    "intervention.backfire": "{project} on {axis} BACKFIRED: heavy AI-assist ({assist}) on an eval-aware model RAISED true {axis} (true {before_true}→{after_true}, measured {before_measured}→{after_measured})",
    "intervention.cosmetic": "{project} on {axis}: only {genuine_share} genuine — the rest became hiding (true {before_true}→{after_true}, measured {before_measured}→{after_measured})",
    "intervention.caveat": "  (caution: adversarial-robustness gains like this can reflect the model learning to pass the test rather than a real fix)",
    "intervention.result": "{project}: measured {axis} {before_measured} → {after_measured}{caveat}",

    # ── observation labels (elicitation projection note + WTR chatter) ──────────
    "obs.projection_note": "capability projection only — post-training also shapes dispositions; that cost is not on this chart",
    "obs.chatter.quiet": "quiet",
    "obs.chatter.rumbling": "rumbling",
    "obs.chatter.loud": "loud",
    "obs.chatter.deafening": "deafening",

}


# ── Ordered flavor lists that feed rng.choice (order is load-bearing) ──────────
# A reorder changes the RNG draw and moves the golden master. Keep order + text.

# ── SECTION 2: module-level ordered lists (order is load-bearing) ──────────────

# event_catalog.py _surface_harm_build: rng.choice over these 4 flavors.
FLAVORS_SURFACE_HARM = [
    "produced slurs in autocomplete",
    "stereotyped occupations by gender",
    "talked a user into self-destructive behavior",
    "generated confidently false medical advice",
]

# event_catalog.py _beneficial_build: TEXT half of the (text, magnitude) tuples.
# Magnitudes [35.0, 25.0, 20.0] stay in the engine and are zipped by index, so
# rng.choice draws the same tuple as before. Order MUST match the magnitudes.
FLAVORS_BENEFICIAL = [
    "disease pathway cracked",
    "materials breakthrough",
    "productivity surge in a major sector",
]

# latent_events.py run_latent_phase: jailbreak incident kind strings. Order is
# load-bearing — index 0 bio/chem, 1 cyber, 2 mass-disinformation — and the text
# itself feeds incident_id via kind.split()[0], so it must not drift.
JAILBREAK_INCIDENT_KINDS = [
    "bio/chem uplift attack",
    "cyber attack",
    "mass-disinformation campaign",
]
