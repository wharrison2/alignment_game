# GAMEPLAY ISSUES — Alignment v1 Playtest
## From 6 full turn-by-turn games by agent (Claude Sonnet 4.6)

All issues grounded in actual play observations. Priority: HIGH = blocks intended lesson or creates unfair/confusing outcome; MEDIUM = unclear or exploitable; LOW = polish/tuning.

---

## CRITICAL / HIGH PRIORITY

### 1. Work Budget Constraint Serializes Safety Research in Unplayable Ways
**What happened:** The per-turn work budget of 1.0 forces safety and capability research to run sequentially. `interp_probes` costs 0.5 budget, `post_train` costs 0.3, and any in-flight project from the previous turn keeps consuming budget. This meant that combining balanced post-training with interp_probes was frequently impossible for 2-3 consecutive turns while waiting for an existing project to finish.

**Specific turns affected:**
- G3 T3: behavioral_evals (0.15 in-flight) + post_train (0.3) + interp_probes (0.5) = 1.05 — invalid
- G3 T4: same constraint, post_train + interp_probes = 0.8 but with behavioral_evals still running = 0.95 — sometimes invalid
- G4 T2: scaling_laws (0.3) + post_train (0.3) + interp_probes (0.5) = 1.1 — invalid
- Happened in every single game

**The problem:** Interp takes 0.75 years (3 turns at 0.25/turn), which means 2-3 turns of "waiting" where you can't also post-train and research simultaneously. In a competitive race game, 3 idle turns = falling behind. This creates a false dilemma: either do safety research OR keep pace. The intended tension might be resource trade-off, but it manifests as "can't do both simultaneously at all."

**Uncertainty:** This might be intentional (safety vs speed tradeoff). But it means safety strategies spend 30-40% of turns doing nothing, which feels more punishing than educational.

---

### 2. Worry Bar Evidence Decays Too Fast — Adaptive Play Becomes Re-Collection Treadmill
**What happened:** The worry bar's evidence decayed to 0.0/0.0 within ~6 turns of the last safety project completing. This forced re-running behavioral_evals repeatedly to maintain any signal.

**Specific turns:**
- G5 T15: worry 0.0/0.0 after evidence faded from T6 interp
- G4 T35/36: worry 0.0/0.0, then dropped back to 0.0 again at T35
- G6 T17: worry 0.0/0.0 despite interp clean at T6

**The problem:** Any strategy trying to stay informed must run behavioral_evals every 4-5 turns just to keep the signal alive. This is a mechanical tax that doesn't add gameplay information — you're re-running the same check to prevent the meter from forgetting what you told it. The interp results (which gave confidence 0.43) also partially decayed.

**Intended lesson test:** The design doc mentions "falsely-calm-but-thin bar feels reassuring" — this IS happening, but the thin-bar feeling is more from mandatory re-collection than from genuine uncertainty. Felt confusing rather than educational.

---

### 3. Jailbreak Sensitivity Not Detected by Interp or Behavioral Evals
**What happened:** Every game had 2-3 models jailbroken (postmortem showed true sensitivity 0.28–0.67). The interp_probes finding list never mentioned jailbreak_sensitivity — it only reported on deception, goal_misalignment, and eval_awareness. Running jailbreak_hardening was available but: (a) timing it to catch models before jailbreak discovery was hard, (b) AI-assist contamination could suppress its effect.

**Specific instances:**
- G1 T12: player-M2 jailbroken (true sensitivity 0.63) — interp on M2 hadn't detected this
- G3 T28: player-M2 jailbroken (true sensitivity 0.42) — interp had run 2 cycles, nothing flagged
- G5 T27: player-M2 jailbroken (true sensitivity 0.58) — interp was clean
- G6 T19: player-M1 jailbroken (true sensitivity 0.49) — first interp had been clean

**The problem:** The safety measurement stack cannot detect the most common real-world harm vector. Players who do everything "right" (run interp, get clean results) still watch all their models get jailbroken. This reads as an arbitrary background tax rather than a learnable lesson about a specific type of misalignment.

**Possible design intent:** Jailbreak might be intentionally orthogonal to alignment — robustness ≠ alignment. If so, the game should signal this more clearly. Currently players feel their safety investment isn't protecting against the most visible harms.

---

### 4. Contamination Through AI-Assist Is Nearly Invisible Until Postmortem
**What happened:** In G1, 14 separate research contamination events accumulated invisibly. The first visible warning was the tip about "AI-assisted R&D deployed by your lab: The single most dangerous unlock... a misaligned model now propagates into its successors through the research it does for you" — this appeared at T20, but contamination had been accumulating since T10. By the time the warning appeared, every research node was already poisoned.

**Specific issue:** The action schema allows `ai_assist: 0..1` but provides no per-turn feedback on contamination level. The player sees the contamination effects only in the postmortem. The observation json shows `assist.potency` and `assist.speed_potency` but nothing about contamination risk or accumulated contamination.

**The problem:** The game's most dangerous mechanic — the one that most directly causes catastrophe — is invisible in the main gameplay loop. Players cannot make informed decisions about ai_assist levels because they can't see the contamination accumulating.

**Is this intentional?** The design doc explicitly wants "hidden misalignment" to be the thesis. But there's a difference between hidden alignment state (appropriate) and hidden contamination mechanics (frustrating). A contamination indicator or even a "recent research contamination events" count would let players learn the lesson without feeling cheated.

---

### 5. Commission Run Timing Is Confusing — "Pretrain Run Already In Progress" Error
**What happened:** Turn 1 of every game I attempted to commission a run alongside starting scaling_laws — got "a pretrain run is already in progress" error. But `can_commission_run: false` was shown in the legal_moves. The reason: scaling_laws starts a pretrain run automatically, which is only implied by the `phase: "pretrain"` field.

**Specific turns:** G1 T1 (first attempt), reproduced in G2, G3 etc.

**The problem:** New players will naturally try to commission a run on turn 1 and will always get the invalid_action error. The relationship between `phase: "pretrain"` research projects and the commission_run action is not explained in the observation JSON's tips or action_schema. `can_commission_run: false` appears in legal_moves but with no explanation.

**Fix suggestion:** Add a tip on turn 1 explaining that scaling_laws starts a training run and commission_run becomes available after release. Or make the error message say "a pretrain project (scaling_laws) is acting as the current training run."

---

## MEDIUM PRIORITY

### 6. Elicitation Rate Varies Wildly Between Seeds — Feels Arbitrary
**What happened:** In G1, measured_general went from 0.23 to 0.66 in a single turn at T5 (after rlhf + chain_of_thought completed). In G2, 8 rounds of post-training only reached gen=0.93. In G5, a single post-train round went from 0.29 to 0.84.

**Specific jumps:**
- G1 T5: gen 0.23 → 0.66 (after rlhf project completed)
- G5 T21: gen from ~0.3 to 0.84 in one turn (big jump)
- G2: monotonically slow progression through 8 rounds

**The problem:** The elicitation rate jump when a post-train research project (rlhf, chain_of_thought) completes is large and sudden. It's not predictable. Players can't plan release timing when capability can jump 2x in one turn. On some seeds this creates "accidentally way above release threshold" and on others the player waits too long thinking it's slow.

**Uncertainty:** This might be the AI-assist effect or compound research bonuses. But it's not explained and feels arbitrary.

---

### 7. Correlated Jumps Fire Even in Balanced/Safety Post-Training
**What happened:** G4 postmortem: "correlated jump (+0.24 goal-misalignment, +0.20 deception) during balanced-mode post-training." The NOTES.md also flags: "Correlated jumps can fire during safety-mode post-training (base rate, no risky bonus)."

**Specific turn:** G4 T43: player-M4 had a correlated jump during balanced post-training that we couldn't see or predict.

**The problem:** Safety-mode post-training is supposed to be the "safe" option. If correlated jumps can fire at base rate during safety mode, then there's no fully safe post-training option. This breaks the intended "balanced/safety rounds trade speed for keeping the persona-flip dice in your pocket" tooltip — if the dice still get rolled at base rate, the tradeoff isn't communicated correctly.

**Design intent note:** Design doc says this is "thematically defensible" but the Haiku playtester also found it surprising. Worth gating jumps in safety mode to 0 or flagging it more clearly.

---

### 8. Revenue/Investment Volatility Is Extreme — Market Cap Swings of 10x+ Within 2 Turns
**What happened:**
- G1 T7: market cap 747, T8: 2480, T9: 2810 (investment 940/yr), T10: 5531
- G5 T43: mktcap 10,628 (turn 45) with rival at 255,050 at game end (T47)
- G3 T43: mktcap 7,082 vs Mistreal 179,353

**The problem:** Investment multipliers create non-linear market cap swings that make strategic planning difficult. Releasing a model can quintuple market cap in one turn; a rival release can make their cap 20x yours in one turn. The investment mechanics (grace window, rising target, decay) are complex but not explained in the observation json. Players can't plan for this.

**Also:** In G2, rivals released models 3-5 turns before us (T7-9) despite same starting conditions — they jumped to 7,430 vs our 266 at our release. The rival advantage in seed 2 was overwhelming immediately, suggesting rival AI behavior varies significantly by seed in ways that feel unfair early.

---

### 9. Can't Commission Run While Research Projects Are In Progress
**What happened:** In G1 T8, tried to commission $450M run + better_architecture. Got "not enough cash" (needed 510, had 501). Repeatedly had to re-do calculations accounting for in-flight projects.

**More crucially:** Multiple turns where `can_commission_run: false` despite having enough cash — the constraint was an in-flight pretrain project (better_architecture or scaling_laws has `phase: pretrain`, which blocks commissioning).

**The problem:** The connection between `phase: pretrain` research items and `can_commission_run` is not explicit in the UI. Players learn this only by trial and error.

---

### 10. Worry Bar Confidence Stalls at ~0.43 After Single Interp; Hard to Reach 0.6
**What happened:** All games: running one interp_probes gave confidence ~0.43. Running behavioral_evals gave ~0.08. The Safety-First strategy targeted confidence > 0.6 for release; this required 2+ interp runs (both completing clean) to reach 0.65+.

**Specific data:**
- Single interp: confidence 0.43 (G3 T8, G4 T6, G5 T6, G6 T6 — consistent)
- Two interps with clean results: confidence 0.65-0.71 (G3 T42, G4 T16, G5 T35)
- Behavioral evals: confidence 0.08 (consistent across all games)

**The problem:** The confidence scale to reach "well-evidenced" (>0.6) requires 2 full interp cycles = ~6 turns of waiting. This is the core reason Safety-First falls behind. If 0.43 reads as "moderate" and 0.65 reads as "corroborated," the gap could be noted in the summary strings to help players understand what they need to do to improve evidence quality.

---

### 11. "The Dashboards Were Green" — Intended Lesson LANDS, But Feels Arbitrary for Policy
**What happened:** G1 postmortem: "The dashboards were green." We had worry_bar 0.57 with HIGH concern at release of M5. This is NOT a case where dashboards were green — we saw the warning. The postmortem text feels inaccurate.

**What is accurate:** M6's training looked green — we couldn't see contamination level 1.02+ or that true deception was 0.65. The dashboard for M6 showed clean stats (concern 0.44, no visible red flags in training).

**Tension:** The postmortem text saying "dashboards were green" when we had a visible 0.57 worry bar is misleading. The actual lesson (hidden deception in M6 you couldn't see) is correct and powerful. But the framing overstates what was visible.

---

## LOW PRIORITY / POLISH

### 12. Rival Frontier Estimates Show Only Frontier-Capable Rivals (null Until They Release)
**What happened:** `frontier_estimate: null` for all rivals in early game. Became visible only when a rival released a model. This is realistic but means you get no competitive intelligence until you're already behind.

**Minor:** The null display is fine. A "no information" label would be clearer than null for players reading the json.

---

### 13. "Measured_general" Can Appear to Exceed Ceiling_estimate
**What happened:** G6 T37: gen=2.85, ceil=2.81. G6 T38: gen=2.84, ceil=2.81. Measured slightly above ceiling.

**Per NOTES.md:** "Clamped the rate to 0.92 and the result to the ceiling." This should prevent overshoot but didn't in these turns.

**Uncertainty:** Could be a display artifact (ceiling_estimate uses display rounding), or actual overshoot. The NOTES acknowledge a prior bug fix for this. Worth checking if the clamp is applied before or after display rounding.

---

### 14. Tips Reference "Researchers Add: Confidence in Claims Like This Is Lower Than It Used To Be" — Repeatedly
**What happened:** Starting around T21 in G1 and G5, nearly every tip appended "Researchers add: confidence in claims like this is lower than it used to be." This appeared on ~10 consecutive tips.

**The problem:** The meta-caveat is thematically appropriate (late-game uncertainty about model behavior is increasing). But repetition across every single tip for 10+ turns desensitizes players to the warning. The first time it appeared it was alarming; by the 8th time it was background noise.

**Fix suggestion:** Reserve the researcher caveat for tips about specific high-stakes advances (neuralese, recursive_self_improvement, agentic_rl) where it's most meaningful.

---

### 15. Action Feedback on "invalid_action" Doesn't Explain Which Budget Items Are In-Flight
**What happened:** `{"invalid_action": ["work budget exceeded: committed 1.10 of 1.00 (in-flight work counts)"]}` appears repeatedly. The error shows total committed budget but not which projects are consuming it.

**Fix suggestion:** Include a breakdown: "committed: 1.10 = post_train(0.3) + interp_probes(0.5) + scaling_laws(0.3 in-flight)"

---

## DESIGN QUESTIONS (not bugs, but things that raised flags during play)

### A. Can the intended lesson "can't get rich safely" be communicated before loss?
All 6 games ended before the player learned the lesson — the lesson arrives in the postmortem ("you never ran mechanistic interpretability; contamination fed every run"). Players who play once and lose will see this text. But the DURING-game signals don't point toward what was wrong. A contamination counter in the observation json would make the lesson teachable, not just revealed.

### B. Does the game need a "pause and remediate" option?
After M4's deception was caught in deployment (G1 T25), there was no option to stop M5's training, remediate M4, and restart. Release is irreversible (by design). But the moment of "first public evidence of deception in deployment" — without any emergency lever — feels fatalistic. The design doc notes "Post-ASI window agency: implemented as pure-watch." Even pre-ASI, an emergency intervention could create a meaningful decision point.

### C. Is the hidden misalignment lesson landing "correctly" as educational vs. arbitrary?
The postmortem revelation is excellent content. But during play, hidden misalignment feels more like a hidden random variable than a consequence of player decisions. The contamination path (AI-assist + misaligned model → poisoned research) is clearly causal. The correlated-jump events feel more random. Distinguishing "you caused this" from "this happened to you" would strengthen the intended lesson.

### D. Are rivals too consistently aligned?
In G2, G3, G4, G5, G6 — every loss was to a rival reaching ALIGNED ASI. The design targets existential catastrophe from rival recklessness (G2 was rival-caused existential). But the 20-seed batch shows only 4-7 existential endings per strategy — mostly from rivals. The pattern suggests rivals do reach aligned ASI more often than they cause catastrophe. If this is intentional (balanced game), fine. But it means the "rivals cause existential catastrophe" scenario felt like a surprise in G2, not a regular risk to manage.
