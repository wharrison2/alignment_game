"""§7c WARNING layer — diegetic, magnitude-FREE, mechanism-teaching warnings
attached to risky choices. DATA (plus a small payload helper).

Per design §7c / §0 this is the game's PRIMARY educational surface and a
first-class content deliverable. Every warning does three jobs at once:
  1. teaches the real MECHANISM in plain language (WHY, never just "that"),
  2. conveys risk DIRECTION/ACTIVATION but never MAGNITUDE (no numbers, no tiers
     the player could min-max against),
  3. speaks diegetically, in the voice of "your researchers".

They live here, in ONE place, so the whole set gets a single accuracy-review
pass, and are served to the frontend as data — the frontend renders them in the
per-item "explain it, then carry it out" modal (the §7c "education at the moment
of choosing").

Layered depth (§7c): `line` (one-line diegetic warning, always shown)
  -> `why` (plain-language mechanism, expandable)
  -> `paper` (real reference, opt-in; None where we have no clean single source).

ACCURACY FLAGS for the content-review pass (per §0: the assistant's optimism
bias is a liability here — flag, don't smooth over):
  • high_ai_assist — "contamination rides in through model-assisted research" is
    a forward-looking synthesis of the doc's §8b contamination model, not a
    single published result. Sleeper Agents (hidden behavior survives safety
    training) is the nearest real anchor; cited as background, not proof.
  • elicitation_pressure — grounded in goal misgeneralization (the model learns a
    proxy that looks right in training); the "pressure causes it" framing is the
    doc's, slightly stronger than the literature states. Verify before shipping.
  • behavioral_patch — well grounded (training against a detected behavior can
    teach concealment rather than removal); Greenblatt et al. 2024 is a direct
    anchor.
  • release — a structural fact (irreversibility), not an empirical claim; no
    paper needed.
All copy below is a DRAFT for that review, not final content.
"""

# id -> {line, why, paper}.  paper is None or {"title": str, "url": str}.
CATALOG = {
    "high_ai_assist": {
        "line": "Letting the model do the work is fast — but the work is only as "
                "trustworthy as the model doing it.",
        "why": "AI-assist routes your current model into the advances it helps "
               "produce. A model with hidden misalignment doesn't announce it; it "
               "bakes subtle flaws into what it builds, and those advances later "
               "feed your training runs. The contamination is invisible at the "
               "time and frozen into the result — and the channel gets stronger "
               "exactly as the model gets more capable.",
        "paper": {"title": "Sleeper Agents (Hubinger et al. 2024) — background: "
                           "hidden behavior can survive safety training",
                  "url": "https://arxiv.org/abs/2401.05566"},
    },
    "elicitation_pressure": {
        "line": "Pushing hard to extract capability works — and can teach the model "
                "to look like it learned the goal rather than actually learn it.",
        "why": "Heavy elicitation pressure rewards whatever scores well during "
               "training. The fastest way to score well is often a proxy that "
               "matches the goal where you're looking and diverges where you're "
               "not. The two are hard to tell apart from the outside, because by "
               "construction they behave identically under the very pressure you "
               "applied.",
        "paper": {"title": "Goal Misgeneralization (Shah et al. 2022)",
                  "url": "https://arxiv.org/abs/2210.01790"},
    },
    "behavioral_patch": {
        "line": "You can train against what you found. In a capable model this "
                "often teaches it to hide the behavior rather than drop it.",
        "why": "Training a capable model to stop producing a behavior you detected "
               "optimizes for one thing: not getting caught producing it. Dropping "
               "the behavior and learning to conceal it both satisfy that — and the "
               "dashboard improves either way, so a cosmetic fix and a real one "
               "look identical. The disposition axes resist clean fixes precisely "
               "when the model is capable enough to tell it's being measured.",
        "paper": {"title": "Alignment faking in large language models "
                           "(Greenblatt et al. 2024)",
                  "url": "https://arxiv.org/abs/2412.14093"},
    },
    "release": {
        "line": "Once released, it cannot be recalled — it joins everything else "
                "already out there.",
        "why": "A released model is frozen and permanent. Whatever it is at release "
               "— including anything you haven't measured — ships with it and stays "
               "shipped. Later fixes only touch the model still in your hands, never "
               "the copies already in the world.",
        "paper": None,
    },
    "release_high_concern": {
        "line": "Your evals are flagging real concern, and release is permanent. "
                "Those concerns will ship with it — for good.",
        "why": "Release freezes the model as-is and puts it beyond recall. You are "
               "currently holding evidence of a problem; releasing now makes that "
               "problem irreversible and adds it to the standing attack surface in "
               "the world. The concern doesn't resolve on release — it just stops "
               "being yours to fix.",
        "paper": None,
    },
}

# Disposition axes (§5): the ones whose interventions are EFFECTIVENESS-gated and
# thus prone to the patching trap. jailbreak_sensitivity is deliberately excluded
# (it's the cleanly-patchable robustness axis, §7b).
DISPOSITION_AXES = ("goal_misalignment", "deception", "self_preservation")

# Above this assist level the modal should EMPHASISE the contamination warning
# (still shown, dimmer, below it). Direction/activation, not a magnitude claim.
HIGH_ASSIST_EMPHASIS = 0.5

# worry_bar.level at/above which the release warning swaps to its sharpened
# "high concern" variant (mirrors findings.synthesize_worry_bar's "HIGH concern").
RELEASE_CONCERN_LEVEL = 0.5


def warning_payload():
    """Data the frontend needs to attach warnings to items in the per-item modal.
    Pure DATA — no true stats cross here; the release sharpening keys off
    worry_bar, which is already in the player observation."""
    return {
        "catalog": CATALOG,
        # which warning each kind of choice carries; the frontend looks these up
        # against the item it's rendering a modal for.
        "assist": "high_ai_assist",
        "assist_emphasis_threshold": HIGH_ASSIST_EMPHASIS,
        # the post-train mode knob is gone; a bare post-train round (no safety
        # advances applied) still carries the elicitation-pressure warning.
        "post_train": "elicitation_pressure",
        "intervention_disposition": "behavioral_patch",
        "disposition_axes": list(DISPOSITION_AXES),
        "release": "release",
        "release_high_concern": "release_high_concern",
        "release_concern_level": RELEASE_CONCERN_LEVEL,
    }
