# ISSUES — build notes (companion to design_doc.md)

Per CLAUDE.md §5: contradictions/underspecifications found, liberties taken, and
implementation choices with design consequences. Newest task at the bottom.

---

## Research-item "what it does" descriptions (§8b)

Implemented the §8b requirement that each capability `ResearchItem` carry TWO
separate plain-language fields for a zero-knowledge player: a value-neutral
**WHAT IT DOES** (first) and the risk framing (after).

- **New field `what_it_does`** on `ResearchItem` (`capabilities_research_item.py`),
  placed before the existing `risk_blurb`. Surfaced through `legal_moves`
  (`capability_projects_available[*].what_it_does`) and shown FIRST in the
  frontend per-item modal, with the risk layered after.
- **Content liberty (flag for review, per §0).** I authored the `what_it_does`
  string for all 19 nodes. RLHF reuses the design doc's exemplar verbatim; the
  other 18 are mine — drafted neutral, concept-teaching, and benefit-conveying
  (the "pull"), held to the §0 WHY-not-THAT standard. These are drafts for the
  designer to tune, not settled copy.
- **Interpretation — field 2 ("how it risks").** §8b calls field 2 "the §7c
  warning." In the modal I render the node's existing per-node `risk_blurb` as
  that node-specific risk line (after `what_it_does`), followed by the GENERIC
  §7c catalog warnings from `observation/warnings.py` (e.g. `high_ai_assist`,
  emphasised as the assist slider goes high). So a capability item shows: what it
  does → its own risk → the knob-level warnings. Noting the two-granularity
  blend in case the designer wants a single authored field instead.
- **Scope.** §8b's two-field rule is written for the capability `ResearchItem`
  (the tech tree). Safety projects (§7b) already carry a neutral `blurb`, which
  the modal reuses as their "what it does"; I did NOT add a `what_it_does` field
  to `SafetyProject`. Revisit if safety projects should get a dedicated neutral
  description distinct from `blurb`.

---

## Doc↔code reconciliation audit (2026-06-18)

A pass comparing the code against `design_doc.md` and `CLAUDE.md`. CLAUDE.md
best-practice fixes were applied in code; the undocumented mechanisms were written
up in the new `IMPLEMENTATION_DETAILS.md`. The items below are for the **designer**:
contradictions and stale doc sections, with proposed revisions. The design doc was
**not** edited — these are proposals.

### A. Contradictions (design-doc section → what the code does)

- **§5 catastrophe-severity path.** Doc: severity is `goal_misalignment ×
  general_capability × self_preservation` (a product; deception merely "governs
  whether you saw it coming"). Code: `event_catalog.py` computes severity as
  `model.misalignment_composite() × general_capability / CAP_MAX`, where
  `misalignment_composite()` (`model.py`) is a **weighted sum**
  `0.55·goal_mis + 0.30·self_pres + 0.15·deception` (weights now named
  `COMPOSITE_W_*`). Two divergences: (i) sum-of-dispositions vs product, and (ii)
  **deception contributes to severity**, which §5 says it should not.
  *Proposed revision:* either update §5 to describe the realized two-step shape
  (disposition composite × capability), explicitly listing deception's weight, or
  decide the code should drop deception from the severity composite to match §5.

- **§4.3 / §9 external-researcher tips vs CLAUDE.md §2 (already fixed in code).**
  `observation/guidance.py` previously read `lab.best_true_general()` — TRUE,
  hidden, including unreleased in-training models — to time/hedge frontier tips,
  violating CLAUDE.md §2 ("guidance reads observations only"). Fixed to read
  `world.frontier_measured_general` (the public, released, benchmarked frontier,
  §7). The golden master did not move (the tested matrix uses non-sparse guidance,
  which consumes no RNG). *Proposed revision:* §4.3/§9 should state that
  frontier-proximity tips ride the **public/measured** frontier, not TRUE state.

- **§11 file map is stale (authoritative-but-wrong).** Modules missing or
  mislabeled: `events/buyouts.py` (absent), `governance/gov_news.py` (named in §10c
  prose, absent from the map), `engine/turn_context.py` and `engine/rules.py`
  (absent), and the `evaluations.py` build/upgrade harness system (under-mapped vs
  §7). *Proposed revision:* add these to the §11 map (see `IMPLEMENTATION_DETAILS.md`
  for what each does), and drop the `[E]/[N]/[R]` "per screenshot" build-status tags
  — everything is built, so they no longer carry information (see §D below).

- **README pointer (fixed directly — README is not the design doc).** `README.md`
  said "See `NOTES.md` for questions"; CLAUDE.md §0 already calls that stale. Updated
  to point at `ISSUES.md`.

### B. Note: `JOB_LOSS_APPROVAL_*` scales offset

`finances.run_job_loss_drag` multiplies the approval rate by
`JOB_LOSS_APPROVAL_INTENSITY_SCALE` (10) then by `JOB_LOSS_APPROVAL_AMOUNT_SCALE`
(0.1) — net ×1. Named for legibility but kept value-identical to preserve the golden
master; a designer may want to collapse them to a single honest coefficient.

### D. Dead-weight design-doc sections (proposed revisions)

- **§14 "Headless / CLI runthrough" — now historical.** Written entirely future-tense
  ("Why it's nearly free", "What's needed", "Doable as a CLI? — yes", the build-order
  recommendation) for a CLI that fully ships: `cli/run_game.py`,
  `cli/agent_session.py`, `cli/strategy_report.py`, `cli/strategies.py`. Every
  "What's needed" bullet and every mode (interactive / agent / scripted / batch) is
  implemented. *Proposed revision:* replace §14 with a one-line present-tense pointer
  to `README.md` (run commands) + `IMPLEMENTATION_DETAILS.md` (what actually shipped),
  or move the whole section to a "historical / design rationale" appendix.

- **§11 build-status tags.** The `[E]/[N]/[R]` "(per screenshot)" annotations on every
  module are historical scaffolding from before the build; they now mislead more than
  inform. *Proposed revision:* drop them (see §A above).

- **§12 "Resolved this session (kept as a record, no longer open)".** A record of
  settled decisions; a candidate for archiving to keep the live "open decisions"
  index scannable. Flagged lightly — designer's call, not urgent.
