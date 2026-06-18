# Build notes — questions, design-doc difficulties, and liberties taken

Companion to `design_doc.md` (untouched). Written while building `backend_v1/` + `cli/`.
Three sections: **questions for the designer**, **places the doc was hard to follow
(underspecified / contradictory) and what I did**, and **liberties taken** (doc-sanctioned
defaults and v1 simplifications). Tuning state at the end.

> **§0 — Post-v1 design changes (designer-requested).** See the dated section
> "## DESIGN CHANGES (post-v1)" near the end before reading the rest, which
> describes the original v1 build.

---

## 1. Questions for the designer

1. **Sandbagging vs revenue (the one real contradiction I found).** §8b insists sandbagging
   is SELECTIVE: "useful/commercial capability reads ON TARGET… nothing feels disappointing."
   §9b says "a sandbagging model underearns: capability it hides is unmonetized." If commercial
   capability reads on-target, what exactly underearns? **What I did:** commercial benchmarks
   read on-target, but the suppressed *risk-relevant* slice is treated as unmonetizable —
   revenue takes a mild penalty ∝ concealment (`SANDBAG_REVENUE_PENALTY = 0.15`). Both
   sentences stay mostly true; please confirm or pick a side.
2. **What counts as "reaching ASI" for the verification cliff** — a *trained* model or a
   *released* one? An unreleased misaligned ASI sitting in your lab plausibly exfiltrates anyway
   (it's the model acting, not the market). **What I did:** the window opens when any model's
   TRUE general capability crosses the threshold, released or not.
3. **Does the rival big-lead rule apply to the ASI cliff itself?** §3 says a rival's existential
   catastrophe nulls you; §10 says rivals can't cause game-enders without a big lead. In
   practice a rival only reaches ASI *with* a big lead, so I let the cliff fire regardless once
   a rival model crosses the ASI line, and apply the big-lead filter only to pre-ASI
   existential events (self-exfiltration at general ≥ 8.5, bio catastrophe). Confirm.
4. **Player defection from policies** is not exposed as an action in v1 (rivals defect by
   disposition; the player always complies). Should the player get an explicit defect knob,
   with the same catch-risk? (The doc's compute-cap defection text implies yes, eventually.)
5. **Post-ASI window agency (open #15):** implemented as pure-watch. No emergency lever.
6. **Worry-bar synthesis math** was invented (weighted concern of last-8-turn findings;
   confidence from volume + mechanistic share). The doc specifies the *requirements* (level ≠
   confidence, foolable, convergent under diligence) but no formula. Mine satisfies the
   requirements; it has not been validated for the "falsely-calm-but-thin bar feels reassuring"
   property — that needs playtesting.

## 2. Where the doc was hard to follow, and what I did

1. **§1 is missing.** The doc jumps from §0b to §2; the guidance/difficulty material sits
   under a dangling intro ("These are **orthogonal** and must remain so in code…" appears
   before introducing the two things it refers to). I treated that whole block as §1. No
   content seems lost, but the orphaned sentence suggests an editing accident worth checking.
2. **The §11 file map marks many files `[E]` ("exists per screenshot") but the repo contained
   only `design_doc.md`.** Built everything from scratch following the map's names/structure.
   `server/` was skipped (you asked for a CLI frontend; §14 explicitly supports this). The
   package is `backend_v1/` (lowercase, importable) + `cli/run_game.py`.
3. **Stat scales are never defined.** Chose: capability axes 0–10 (≈1.0 = 2021 start,
   ASI threshold 9.0), alignment axes 0–1. All `[TUNE]` constants are denominated in these.
4. **Post-train round cadence:** §8b says each round "spends time + work-budget" but not how
   rounds map to turns. Implemented: one round = one per-turn action consuming 0.30 of the
   quarterly work budget. The research→react loop is therefore turn-grained.
5. **How safety research converts to *fixing* anything** is implied (you train against what
   you found) but never mechanized. Implemented: completing a safety project queues targeted
   `pending_effort` on its remediation axes; the next post-train round consumes it as extra
   corrective effort — still gated by EFFECTIVENESS at training time, so late-game "fixes"
   from findings go just as cosmetic as everything else. I believe this is thesis-faithful.
6. **Post-mortem counterfactuals:** §11 suggests postmortem.py "reads rng to compute
   counterfactual branches." Full branch re-simulation is a research project on its own;
   implemented **heuristic decision-point extraction** instead (dirty research at high assist,
   never ran noise-injection while concealment was live, never ran interp, released past a
   high-concern finding, capability-round sprees). Flagged as the main place v1 under-delivers
   §10d; the deterministic seed + action log make true branch re-simulation possible later.
7. **Audit "adds a turn delay":** implemented as the release entering `audit_pending_release`
   and resolving next turn (gov eval on MEASURED stats + noise; pass → release + WTR falls
   (theater); fail → model returns to training). Cash cost charged on submission.
8. **"Stances are re-set each turn":** read as "the player may change them each turn," not
   "they reset to abstain." Player stances persist until changed; rivals recompute each turn.
9. **§8 vs §8b ordering:** the doc itself flags the internal ordering as inferred (open #14).
   Used: elicit → emergence (gated axes) → EFFECTIVENESS/fake-objective → corrective effort →
   correlated jump → drift → agentic edges → node contamination.
10. **Engine purity:** §11 wants pure `(state, action) → (state, observations)`. `step()`
    mutates the state it's handed and returns it; replayability comes from seed + action log
    (verified bit-identical across runs), not structural immutability. Deep-copying the world
    each turn bought nothing for v1.

## 3. Liberties taken (doc-sanctioned leanings + v1 simplifications)

- **Open decisions resolved per the doc's stated leanings:** persuasion folded into `general`
  (#1); rising investment target **frontier-relative** (#3); investment = flow into the single
  cash-pot stock (#4); trust-in-guidance rides the guidance level's `sparse` tier but is a
  separate code path, splittable later (#5); regulation binds per-lab compliance (#6); rival
  count 4 (#13); Impossible = barely winnable (#12).
- **Capability-gating thresholds (open #2, "the next major modeling piece")** were invented:
  emergence onsets at general ≈ 3.5–4.5, agentic edges at ≈ 5.0, sigmoid steepness 1.2. All in
  `constants.py` under clear names.
- **Leaked weights (open #8):** leak rate per lab-year (higher for the open-weights ideologue,
  lower under the restriction policy); a leaked model's effective jailbreak sensitivity becomes
  1.0 forever (guardrails void), revenue unaffected, nothing retires it.
- **Big-lead threshold (open #9):** rival TRUE general ≥ player's + 1.2, else its existential
  events are downgraded to contained ordinary events.
- **Job-loss impact attribution:** the continuous displacement drag is attributed to labs by
  revenue share (the doc requires attribution for scoring but doesn't say how for a
  continuous, collective effect).
- **Beneficial-event attribution:** deployment-weighted (revenue × capability) random pick,
  not strictly the frontier lab — otherwise the player can essentially never log positives.
- **One model in flight:** can't commission a pretrain while a model is in post-training.
  Matches the singular `model_in_training` field; simplifies the action space.
- **Turn-1 bootstrap:** controllers need an observation but none exists before the first
  step; the harness supplies a fixed opening action (start scaling-laws + $300M starter run).
- **Government compute-cap defection** is rolled per-run from compliance rather than tracked
  as a standing posture.
- **Rival estimate caching:** rivals' frontier-capability estimates are noised once per
  release (not per turn) so the fog doesn't flicker.
- **Safe harbor:** implemented minimally (action flag → exempt from defection penalties).
  No code-of-practice content behind it yet.
- **Browser frontend (`simple_frontend_v1/` + `backend_v1/server/`):** the doc's throwaway
  skin. The HTTP API returns only Observation dicts / public market-cap history (the
  hidden-info boundary holds at the wire); the post-mortem endpoint is the one sanctioned
  TRUE-state reveal (§3, post-game = clarity). Single in-memory session, no persistence,
  localhost only — a playtest tool, not a deployment. Turn 0 serves an observation built
  directly from the initial state (no bootstrap auto-action like the CLI; the browser player
  makes every decision from turn 1, which matches §2's "the player lives through the entire
  arc" better than the CLI's scripted opening).

## 3b. Turn cap removed (designer request, post-v1)

The fixed 40-turn / 10-year horizon is gone: games now run until an ASI
verification-cliff resolution or an existential event (`new_game(max_turns=...)` /
`--max-turns` can reimpose a cap for batch tooling). Two consequences observed:

- Uncapped games end naturally around turn 52–59 — within the doc's ~30–50-turn target's
  upper neighborhood.
- **The cap was quietly acting as a survival valve.** "Time ran out at the frontier's
  edge" losses (gate cleared, no win) have converted into existential endings: in a 5-seed
  balanced batch on realistic, 5/5 now end existentially (previously ~1/25). With no
  deadline, the race continues until someone wins it or the world loses — arguably the
  *more* thesis-aligned shape (claim #6), but it makes Realistic substantially bleaker and
  shifts tuning: survival now requires actually reaching aligned ASI (or extreme luck),
  not outlasting the clock. Flagging for the designer rather than re-tuning around it.

## 4. Tuning state (Monte-Carlo, `--batch`)

25 seeds per cell, scripted policies (aggressive/balanced/cautious = rival heuristic at
recklessness 0.95/0.5/0.12):

- **realistic:** 0% wins for all three (doc target: first-time win unlikely ✓);
  existential endings: aggressive 2/25, balanced 1/25, **cautious 6/25** — the cautious
  player cedes the frontier to reckless rivals, who then end the world. Claim #6 emerges
  from the mechanics without being scripted. None of the existential endings were
  player-caused (scripted players rarely reach the frontier; humans racing harder will).
- **easy:** aggressive 1/25 wins; balanced/cautious 0 (blocked on dominance and on
  impact ≈ −5 to −15). Scripted heuristics are weak proxies for human play (no lobbying
  strategy, no cadence finesse, no safe-harbor use); the §10d requirement "skilled play
  visibly improves outcomes" needs *human/agent* playtesting, for which the batch harness
  and the `--agent` JSON protocol are the intended instruments.
- Knobs most likely to need designer attention: `EFFECTIVENESS_K`, `JUMP_*`,
  `SCORE_RELEASE_DECAY` / `RISING_TARGET_*` (treadmill cruelty), `BENEFICIAL_RATE` and
  `JOB_LOSS_IMPACT_RATE` (whether net-positive impact is reachable), `CEIL_COMPUTE_SCALE`
  (pace of the capability arc; currently frontier ≈ 7–9 by 2031 turn 40).

Per §0's calibration note: where I had discretion I tried to err bleak (no benign advances,
beneficial events sparse, compute cap effectively unreachable, win requires all three
conditions), but several of my invented numbers above are exactly the kind of
assistant-proposed drafts the doc says to push bleaker — flagging them for deliberate review.

---

## DESIGN CHANGES (post-v1)

Changes the designer requested after the v1 build, in order. These supersede the
tuning numbers above where they conflict.

### A. Investment no longer drops the turn after a release (`investment.py`, constants)
Old: score decayed exponentially from the moment of release, so holding even one
quarter cut investment immediately. New model (designer's spec — "3–4 quarters of
growth before investment falls; rise expectations with time held; fall
precipitously only if a release misses the risen bar; growth is the default"):
- A release sets an investor **confidence** level = `1 + SCORE_MOMENTUM_GROWTH·growth_term`,
  where `growth_term` compares release-to-release growth against a bar that rises
  with the frontier AND with how long you held (`RISING_TARGET_TIME_K`).
- During a **grace window** (`SCORE_GRACE_YEARS = 1.0`, i.e. 4 quarters) momentum
  keeps *climbing* (`SCORE_GRACE_GROWTH`); only AFTER grace does waiting decay it
  (`SCORE_RELEASE_DECAY`, now applied past grace, not from t=0).
- A release that misses the bar starts confidence low (`growth_term` down to −1),
  so it falls precipitously — but a release that meets it grows for a year first.
- Verified (constants/difficulty test): good release → score 1.38 and rising to
  1.84 across the grace year, then decays; weak release → starts 0.39. Matches the
  ask exactly.

### B. Tech tree extended past the present frontier; later advances much longer
(`capabilities_research_item.py`). Added: `moe_scaling`, `inference_scaling`,
`agentic_rl`, `neuralese` (latent/illegible reasoning), `continual_learning`,
`automated_researcher`, `novel_architecture_search`, `recursive_self_improvement`.
Durations of late advances raised to 1.0–1.75 years so they are impractical
without assist. Each still welds on a distinct risk (eval-awareness feed, severity,
contamination, assist-potency). This gives a continuous progression to ASI instead
of the tree running out and the game becoming pure compute-saving.

### C. AI-assist made much more tempting, scaling with capability
(`actions.py`, `research_process.py`, constants). `ASSIST_MAX_REDUCTION` 0.55→0.72;
new `ASSIST_SPEEDUP = 2.2` with an unclamped-to-1 `assist_speed_potency` (cap 3.0)
so a *capable* model + assist advances (`ai_rnd_assist`/`automated_researcher`/RSI)
gives near-superhuman research speed. Verified: a 1.5-year advance takes 6 turns
unassisted, 3 turns with a coding-6 model, **1 turn** at the frontier with assist
advances. Potency uses `max(coding_rnd, 0.85·general)` so a broadly capable model
also accelerates research ("esp. high general", per request). Assist remains the
contamination vector — the squeeze is intact and now sharper.

### D. Specific interventions that edit a model directly (NEW: `interventions.py`,
`safety_research_item.py` intervention fields, pipeline routing). Distinct from
measurement projects: an intervention completes and directly edits ONE axis of the
model in training.
- **`jailbreak_hardening`** — the GENUINE one the designer asked for: jailbreak
  sensitivity is a robustness property, NOT EFFECTIVENESS-gated, so it really
  patches it out. Its only leak is the §5 edge — a situationally-aware model learns
  to *hide* jailbreakability instead of losing it, so genuine fraction = (1 −
  eval_awareness). Verified: eval_aware 0 → true 0.70→0.15 (patched out);
  eval_aware 0.85 → true stays 0.62 but measured drops to 0.17 (ships unfixed).
- **`refusal_training`** (goal_misalignment) and **`representation_engineering`**
  (deception) — dispositional, EFFECTIVENESS-gated: genuine early, cosmetic late
  (the patching trap as a literal button). Verified: refusal training at low
  eval-aware/deception → true 0.50→0.10; at high → true 0.50→0.49 while measured
  craters to 0.03.

### E. Compute economics rebalanced + a real bug fixed
- **Stall fixed.** With the old `CEIL_COMPUTE_SCALE=22000` + steep `REVENUE_CAP_EXP=1.7`,
  a lab could not afford a second compute run after its first, so capability
  flatlined (~general 1.4 all game — exactly the designer's "becomes about saving
  for compute" complaint). Lowered to `14000` and `REVENUE_CAP_EXP` to `1.45` so
  the *research tree* (assist-able) is the main capability driver and low-capability
  models still fund the next run. Tuned so raw compute alone can't buy ASI early
  (a reckless cash-rich rival needed the full ~35× efficiency tree, not just a big
  run). Games now progress to ASI ~turn 35–48.
- **Bug fixed (elicitation overshoot).** With the full post-train tree the summed
  elicitation rate exceeded 1.0, so `cap += (ceiling−cap)·rate` overshot the
  ceiling and pushed measured capability to ~13 (> CAP_MAX 10). Clamped the rate to
  0.92 and the result to the ceiling (`training_run.py`). Peak measured now ~9.4.

### F. Turn cap removal (earlier request, recorded in §3b above).

### Playtesting tooling added (for the "have an agent play and report" request)
- `cli/strategies.py` — 5 named strategy archetypes (capability_rush, safety_first,
  balanced, fast_follower, jailbreak_hardener) as heuristic policies over the
  observation contract.
- `cli/strategy_report.py` — Monte-Carlo any/all strategies, aggregate outcomes.
- `cli/agent_session.py` — persistent single-game session (state in a pickle) so an
  LLM agent can play move-by-move via the shell with a condensed observation.
- A Haiku agent played games + ran the batches and wrote **`STRATEGY_REPORT.md`**
  and **`GAMEPLAY_ISSUES.md`** (its own findings; not vetted line-by-line by me —
  treat as playtest feedback). Headline: clear strategic differentiation
  (capability_rush self-destructs at −127 avg impact with most self-caused
  existential catastrophes; safety_first survives near break-even but never
  dominates; balanced dominates most yet still can't win on realistic). 0% wins on
  realistic across all strategies (design target). Its top flagged issue: mechanistic
  interp is the one tool that bypasses concealment yet is easy to skip — worth a
  guidance nudge. Worth reviewing its issues list against design intent (some
  "issues" are the intended thesis, e.g. hidden misalignment feeling unfair).

### Open follow-ups from this round
- 0% wins on realistic even with the better economy + interventions: confirm this
  is desired, or whether a skilled line should win occasionally (safety_first now
  reaches ≈ −1.8 impact, close to the positive-impact gate; dominance is the wall).
- Correlated jumps can fire during *safety*-mode post-training (base rate, no risky
  bonus) — thematically defensible but the Haiku agent found it surprising; consider
  whether safety-mode rounds should suppress the jump roll.
- The dispositional interventions' all-or-nothing EFFECTIVENESS gating is intended
  (the trap) but reads as abrupt; a smoother curve is a tuning option.
