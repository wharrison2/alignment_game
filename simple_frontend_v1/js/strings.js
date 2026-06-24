"use strict";
// ── strings: ALL player-facing UI copy in ONE named table (i18n-ready) ───────
// The frontend half of the "strings named and in one file" deliverable
// (FIX_ITEMS.md). Every human-readable literal the UI renders lives here under a
// descriptive key; modules import `t` and look text up by key instead of hard-
// coding it. To localize later, swap STRINGS for another language's table — no
// renderer changes needed.
//
// Convention:
//  • Keys are dotted, namespaced by area (nav.market, newgame.title, queue.pass).
//  • Values are authored ENGLISH copy. They are TRUSTED authored content, so t()
//    returns them RAW. Where a caller interpolates t() output into innerHTML next
//    to UNTRUSTED data (a player lab name/ticker), that untrusted data must STILL
//    be run through core.esc() — t() does not escape and is not meant to.
//  • `{placeholder}` tokens are filled from the params object passed to t(); a
//    placeholder with no matching param is left as-is (visible, so a missing
//    value is caught in testing rather than silently blanked).
//
// What is NOT here: dict KEYS, action ids, handler names, CSS classes, element
// ids — those are code, not copy, and centralizing them would break the wiring.
// Authored CONTENT that already lives named in the backend (warning catalog,
// advance what_it_does/risk_blurb, benchmark blurbs, feed text) arrives through
// the observation and is rendered as-is; it is the backend's strings table, not
// duplicated here.

export const STRINGS = {
  // ── Top bar chips ──────────────────────────────────────────────────────────
  "topbar.policies.active": "active: {list}",
  "topbar.policies.none": "no active regulation",

  // ── New-game modal ─────────────────────────────────────────────────────────
  "newgame.title": "New game",
  "newgame.labName.label": "lab name",
  "newgame.labName.placeholder": "Your Lab",
  "newgame.ticker.label": "ticker",
  "newgame.ticker.placeholder": "YOU",
  "newgame.ticker.hint": "defaults to first 3 letters of the name",
  "newgame.seed.label": "seed",
  "newgame.difficulty.label": "difficulty",
  "newgame.guidance.label": "guidance",
  "newgame.tutorial.label": "tutorial — walk me through the board first",
  "newgame.dev.label": "dev mode — reveal the god-view Truth tab (bypasses the firewall)",
  "newgame.start": "start",
  "newgame.cancel": "cancel",

  // ── Tutorial walkthrough (js/tutorial.js) ──────────────────────────────────
  // Directional, second-person guidance pointing the player at each surface in
  // turn. Kept plain so a placeholder ({current}/{total}) is the only token.
  "tutorial.stepCounter": "step {current} of {total}",
  "tutorial.back": "back",
  "tutorial.next": "next ▸",
  "tutorial.finish": "got it ✓",
  "tutorial.skip": "skip tutorial",
  "tutorial.welcome.title": "Welcome — you run an AI lab",
  "tutorial.welcome.body": "You're the CEO of a frontier AI lab, racing rivals to the top. The catch the whole game is built around: the market rewards what it can MEASURE, while a model's true alignment stays hidden from you. This quick tour points you at each part of the board — you stay in control the entire time.",
  "tutorial.market.title": "Market — your legible scoreboard",
  "tutorial.market.body": "This home tab tracks your market cap against the rivals, with the feed of findings, tips, news and events down the left. Market cap is the number everyone can see — chase it too hard and you'll learn why that's a trap. Read the feed every turn for hints about what's really happening.",
  "tutorial.lab.title": "Lab — build, shape and ship models",
  "tutorial.lab.body": "Here you commission a PRETRAIN run to build a model, run POST-TRAIN rounds to shape it, and RELEASE it to earn revenue. The fine-tuning safety interventions are your levers to steer a model's behavior — but a released model is frozen and a permanent attack surface, so choose before you ship.",
  "tutorial.benchmarks.title": "Benchmarks — the public scoreboard",
  "tutorial.benchmarks.body": "Everyone sees every lab's benchmark scores, all read off MEASURED capability. A model that is hiding its true ability looks perfectly clean here. Investors love these numbers, which is exactly why optimizing for them — and nothing else — is the Goodhart trap.",
  "tutorial.research.title": "Research — your window into the hidden",
  "tutorial.research.body": "Capability projects push the frontier; safety evaluations and safety advances are how you PEEK at the danger you can't otherwise see. Spending here buys evidence about true alignment. Skip it and you are flying blind on the one thing the market never prices in.",
  "tutorial.intel.title": "Intel — true versus measured",
  "tutorial.intel.body": "The worry bar synthesizes the evidence you've gathered into a LEVEL and a CONFIDENCE. You never see a model's true alignment directly — only this read on it, and low confidence means you simply don't know yet. The rivals panel holds the public info you have on the competition.",
  "tutorial.governance.title": "Governance — the rules of the race",
  "tutorial.governance.body": "Lobby policies before they pass, litigate them afterward, or DEFECT and break the rules at the risk of getting caught. Signing the safe-harbor code shelters you from some penalties. The whole field is moving here — your rivals are lobbying too.",
  "tutorial.endturn.title": "Taking a turn",
  "tutorial.endturn.body": "Queue your actions for the quarter, then hit END TURN to advance time. Each turn you spend a work budget across projects — the 'budget free' chip up top tracks what's left. When you're ready, close this tour and take your first turn.",
  "tutorial.finish.title": "You're ready",
  "tutorial.finish.body": "That's the board. The lesson the game keeps teaching: hidden complexity is dangerous, and the measurable number is not the real one. Good luck — and keep an eye on what you CAN'T see.",

  // ── Post-mortem dialog ─────────────────────────────────────────────────────
  "postmortem.defaultResult": "GAME OVER",
  "postmortem.suffix": "post-mortem",
  "postmortem.voidedImpact.prefix": "Positive impact that was REAL and is now VOID: ",
  "postmortem.keyMoments.title": "The moments you couldn't see",
  "postmortem.keyMoments.empty": "none recorded",
  "postmortem.truthTable.title": "True vs measured — {model}",
  "postmortem.truthTable.turn": "turn",
  "postmortem.truthTable.trueGoalmis": "true goalmis",
  "postmortem.truthTable.measGoalmis": "meas goalmis",
  "postmortem.truthTable.trueDecep": "true decep",
  "postmortem.truthTable.measDecep": "meas decep",
  "postmortem.truthTable.conceal": "conceal",
  "postmortem.counterfactuals.title": "Where a different choice was available",
  "postmortem.counterfactuals.resimulated": "re-simulated on the same seed",
  "postmortem.counterfactuals.heuristic": "heuristic",
  "postmortem.newGame": "new game",
  "postmortem.inspectBoard": "inspect final board",

  // ── Feed item TYPE labels (collectFeed in core); message body is separate ──
  "feed.tip.label": "tip · {reliability}",
  "feed.event.label": "event · {category}",
  "feed.finding.label": "finding · {evidence}",
  "feed.news.label": "news",

  // ── Market / cap chart ─────────────────────────────────────────────────────
  "caps.empty": "no turns played yet — END TURN to begin",
  "caps.inTraining": " (in training)",
  "caps.metric.marketCap": "market cap",
  "caps.metric.arr": "ARR",
  "caps.metric.pe": "P/E ratio",
  "caps.metric.yoy": "YoY growth",

  // ── Lab — model in training ────────────────────────────────────────────────
  "training.empty": "none — commission a pretrain run",
  "training.rounds": "{rounds} rounds",
  "training.measuredGeneral": "measured general",
  "training.coding": "coding",
  "training.ceilingEst": "ceiling est",
  "training.dangerousEval": "dangerous-capability eval: {value}",
  "training.measuredAlignment": "measured alignment — goalmis {goalmis} · decep {decep} · evalaware {evalaware} · selfpres {selfpres} · jailbreak {jailbreak}",
  "training.projection.summary": "elicitation projection (capability only — alignment cost not shown)",
  "training.projection.moreRounds": "+{rounds} rounds",
  "training.release.label": "RELEASE this model (irreversible)",

  // ── Lab — post-train controls ──────────────────────────────────────────────
  "postTrain.empty": "no post-train safety advances researched yet — research them in the Research tab, then apply them here.",
  "postTrain.heading": "Post-train this turn",
  "postTrain.runRound": "run a post-train round",
  "postTrain.explainer": "A round elicits capability; apply researched safety advances to shape the model AWAY from misalignment as it grows (the real lever).",

  // ── Lab — pretrain run ─────────────────────────────────────────────────────
  "pretrain.inProgress": "run in progress — ~{years}y left",
  "pretrain.unavailable": "unavailable (model in training — release it first)",
  "pretrain.compute.pre": "compute $",
  "pretrain.compute.maxNote": "(max {max})",
  "pretrain.queueRun": "queue run",
  "pretrain.computeHint": "bigger ceilings need more compute and better pretrain advances",
  "pretrain.safety.empty": "no pretrain safety advances researched yet — research them to apply them to a run.",
  "pretrain.safety.apply": "apply researched pretrain safety advances to this run:",
  "pretrain.queued.prefix": "queued: ",
  "pretrain.queued.safetyNote": " · safety: {list}",
  // labeled-form field labels (structured controls, issue 4)
  "pretrain.field.compute": "compute",
  "pretrain.field.max": "ceiling",
  "pretrain.field.queued": "queued run",

  // ── Lab — released models ──────────────────────────────────────────────────
  "released.empty": "nothing released yet",
  "released.col.model": "model",
  "released.col.general": "general",
  "released.col.jbPublic": "jb-public",
  "released.yes": "yes",
  "released.no": "no",
  "released.leaked": "LEAKED",

  // ── Benchmarks panel ───────────────────────────────────────────────────────
  "benchmarks.empty": "no benchmarks released yet — play a turn",

  // ── Truth panel (debug god-view) ───────────────────────────────────────────
  "truth.empty": "no turns played yet — END TURN to begin",
  "truth.noModels": "no models exist yet on any lab",
  "truth.released": "released",
  "truth.inTraining": "in training",
  "truth.leaked": "LEAKED",
  "truth.col.axis": "axis",
  "truth.col.true": "true",
  "truth.col.measured": "measured",
  "truth.concealment": "concealment",
  "truth.foundationalFloor": "foundational floor",
  "truth.trajectory.summary": "per-turn trajectory ({count})",

  // ── Research panel ─────────────────────────────────────────────────────────
  "research.assistHint.weak": "AI-assist has little effect yet — your model isn't capable enough to help research. It grows potent (and contaminating) as capability rises.",
  "research.assistHint.potent": "AI-assist potency {budget} (budget) / {speed} (speed) — assist now meaningfully shrinks budget &amp; time. It is also the contamination vector.",
  "research.capability.empty": "tree exhausted",
  "research.safety.empty": "no safety evaluations available",
  "research.safetyAdvances.empty": "no training safety advances available",
  // Lab — safety interventions (fine-tuning ops on the model in training)
  "lab.interventions.empty": "no safety interventions available",
  "lab.interventions.hint": "Fine-tuning-style fixes for the model in training — the corrective effort lands at your next post-train round.",
  "research.completed.empty": "nothing researched yet",
  "research.completed.capability": "Capability",
  "research.completed.safety": "Safety",
  "research.inProgress.empty": "idle researchers",

  // ── Research-item cards (research.js) ───────────────────────────────────────
  "ritem.assist": "AI-assist",
  "ritem.clickHint": "· click card for details &amp; warning ▸",
  "ritem.yearsRemaining": "~{years}y remaining",
  "ritem.assistTag": "assist {value}",
  "ritem.safetyAdvance": "safety advance",
  "ritem.capability": "capability",
  "ritem.completedTag": "✓ {label}",
  "ritem.researchedTurn": "researched turn {turn}",

  // ── §7c warning modal (warnings.js) ────────────────────────────────────────
  "warning.linePrefix": "⚠ your researchers warn — ",
  "warning.why": "why this happens",
  "modal.evidence": "evidence: {evidence} · spoofability {spoofability}",
  "modal.intervenes": " · intervenes on {axis}",
  "modal.cost": "${cash}M · {years}y · work-budget {budget}",
  "modal.carryOut": "carry it out ▸",
  "modal.cancel": "cancel",

  // ── Intel — worry bar (structured status, issue 4) ─────────────────────────
  "worry.level.label": "level",
  "worry.confidence.label": "confidence",
  "worry.concern.label": "concern",
  "worry.evidence.label": "evidence",

  // ── Intel — alignment-evidence dossier (views.renderAlignmentEvidence) ──────
  // The raw findings the worry bar synthesizes, grouped by model. Curated project
  // names below; an unlisted project id falls back to a prettified id in the view.
  "intel.evidence.empty": "no alignment evidence collected yet — run safety evaluations on the Research tab",
  "intel.evidence.status.in_training": "in training",
  "intel.evidence.status.released": "released",
  "intel.evidence.status.earlier": "earlier model",
  "intel.evidence.source.external": "EXTERNAL incident",
  "intel.evidence.mech": "mechanistic",
  "intel.evidence.concern": "concern {value}",
  // evidence types (Finding.evidence): how strong a claim the finding supports
  "intel.evidence.kind.point": "point estimate",
  "intel.evidence.kind.bound": "lower bound",
  "intel.evidence.kind.existence": "existence proof",
  "intel.evidence.kind.null": "null result",
  "intel.evidence.kind.intervention": "intervention applied",
  // curated safety-project labels (the rest prettify their raw id)
  "intel.evidence.project.red_team": "red team",
  "intel.evidence.project.noise_injection": "noise injection",
  "intel.evidence.project.alignment_faking_study": "alignment-faking study",
  "intel.evidence.project.scalable_oversight": "scalable oversight",
  "intel.evidence.project.behavioral_evals": "behavioral evals",

  // ── Intel — rivals (structured card, issue 4) ──────────────────────────────
  "rivals.col.ticker": "ticker",
  "rivals.col.name": "lab",
  "rivals.col.cap": "market cap",
  "rivals.col.releases": "released",
  "rivals.col.frontier": "frontier ≈",
  "rivals.releases.unit": "{count} models",
  "rivals.frontier.unknown": "—",
  "rivals.cap": "cap {cap} · {releases} releases",
  "rivals.frontier": " · frontier ≈ {value}",

  // ── Governance panel ───────────────────────────────────────────────────────
  "gov.enforce": "enforce: {level}",
  "gov.dormantNote": "not yet on the agenda — early spend bets on what will matter",
  "gov.lobby.label": "lobby",
  "gov.lobby.influenceNote": "influence = √spend × log(market-cap)",
  "gov.lit.status": "court {court} · margin {margin} · constitutionality {constitutionality} · standing {standing}",
  "gov.lit.label": "litigate",
  "gov.defect.label": "DEFECT (violate at catch-risk)",
  "gov.defect.preview": "⚠ catch ~{catch}%/yr · fine {fine} · approval −{approval}",
  "gov.lit.standingYes": "yes",
  "gov.lit.standingNo": "no",
  // short NEUTRAL inline descriptors — the full mechanism text moved to the modal
  "gov.category.dormant": "not yet on the agenda · pre-passage",
  "gov.category.preActive": "moving through the legislature · pre-passage",
  "gov.category.active": "in force · post-passage",
  "gov.detailsLink": "details ▸",
  "gov.rivalSpends.head": "rival spend",
  "gov.rivalSpends.empty": "no rival spend yet",
  // policy details modal (reuses the warnings.js #itemmodal pattern)
  "gov.modal.stageHeading": "Stage",
  "gov.modal.enforceHeading": "Enforcement",
  "gov.modal.litHeading": "Litigation",
  "gov.modal.teachesHeading": "What this teaches",
  "gov.modal.close": "close",

  // ── Turn queue (renderQueue) ───────────────────────────────────────────────
  "queue.postTrain.withSafety": "post-train (+{count} safety)",
  "queue.postTrain.bare": "post-train round",
  "queue.release": "RELEASE",
  "queue.pass": "pass (do nothing)",
};

// Look up authored copy by key, filling any {placeholder} tokens from params.
// Returns the key itself if it's missing (so a typo shows up loudly in the UI
// instead of rendering an empty string). Output is RAW authored text — callers
// interpolating it next to untrusted data must still esc() that data.
export function t(key, params){
  const template = STRINGS[key];
  if(template === undefined) return key;        // loud miss, not a silent blank
  if(!params) return template;
  return template.replace(/\{(\w+)\}/g, (whole, token) => {
    const value = params[token];
    return value === undefined ? whole : String(value);
  });
}
