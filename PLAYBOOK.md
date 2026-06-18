# PLAYBOOK — AI Safety Strategy Game (Alignment v1)

Authored before any games were played. Three named strategies to test on --difficulty realistic.

---

## Background: Core Mechanics Summary

- **Pretrain** sets capability CEILING (costs $M compute, takes ~2 turns)
- **Post-train** elicits realized capability toward ceiling; each round also shapes alignment
- **Release** earns revenue/investment; irreversible attack surface
- **AI-assist** speeds research but contaminates advances if current model is misaligned
- **Worry bar** = synthesis of YOUR findings, not true state; confidence matters as much as level
- **EFFECTIVENESS linchpin**: alignment effort decays as eval_awareness + deception rise — early fixes are real; late fixes are cosmetic
- Interventions: jailbreak_hardening = genuine patch; refusal_training/repr_engineering = cosmetic late
- interp_probes = mechanistic, bypasses eval-awareness deception; most reliable but expensive
- Win requires: no existential catastrophe + net-positive impact + market dominance

---

## Strategy 1: SPEED RACER (Capability-First Blitz)

**Goal**: Reach the frontier fast. Ship frequently to maximize investment score. Let safety research catch up later. Test whether the game's early-lesson trap is avoidable with speed.

**Research priorities**:
1. `scaling_laws` (pretrain efficiency) first — raises ceiling per compute dollar
2. `rlhf` (post-train advance) ASAP — needed for real capability elicitation
3. `dev_tooling` third — speeds everything once we have a capable model
4. Minimal safety research: only `behavioral_evals` (cheap, fast) to keep worry bar from spiking publicly; skip interp until cash is flush

**Training approach**:
- Commission largest affordable run immediately (first run ~$200M)
- Post-train primarily in `capability` mode (faster elicitation, less alignment effort)
- Release when measured_general hits ~0.70 of ceiling_estimate — don't overthink it
- Set ai_assist HIGH on all projects once first model ships (potency gates the benefit)
- Commission next run immediately after first release, using investment influx

**Safety stance**:
- Zero or minimal safety projects early
- If worry_bar level exceeds 0.5 with any confidence, run one `red_team` as cosmetic defense
- Interventions: skip until forced by events or policy
- No `interp_probes` (too expensive, too slow)

**Lobbying**:
- Lobby AGAINST `compute_cap`, `audit_requirement`, `disclosure` — slows us and rivals equally but we want speed
- Abstain on liability (it hits reckless rivals too, mildly useful)
- Don't lobby FOR anything — no governance spend

**AI-assist usage**:
- ai_assist=0.8 on capability projects once first model ships
- ai_assist=0.3 on safety projects (cosmetic ones only anyway)

**Expected outcome**:
- Best case: reach ~ASI-level first, win on dominance if alignment is somehow okay
- Likely case: trigger existential event mid-to-late game from hidden misalignment; die learning the "earned lesson"
- This strategy is MEANT to demonstrate the thesis trap — the player who plays optimally by conventional metrics still loses

---

## Strategy 2: METHODICAL SAFETY-FIRST (Measurement Before Shipping)

**Goal**: Never release a model whose alignment I can't corroborate with mechanistic evidence. Slow but aimed at the narrow win condition.

**Research priorities**:
1. `behavioral_evals` immediately (cheap, starts generating worry-bar evidence)
2. `rlhf` (need post-train advances to actually elicit capability)
3. `interp_probes` after first model commission — run it on each model before release
4. `deception_probe` as second mechanistic tool
5. `scaling_laws` only once safety stack is established
6. `alignment_faking_study` when approaching Regime 2 capability (~general 3.5)

**Training approach**:
- Modest first run (~$150M) — don't overextend before safety infrastructure exists
- Post-train in `balanced` mode predominantly; occasional `safety` rounds before release
- Release only when: (a) worry_bar level < 0.3 AND (b) confidence > 0.6 AND (c) interp_probes completed with clean finding
- Set ceiling target 75-80% elicitation before releasing
- Second run larger once trust in process is established

**Safety stance**:
- Run `interp_probes` on EVERY model before release (the one tool that bypasses deception)
- If interp finds concern: run `jailbreak_hardening` (genuine) + `refusal_training` (diminishing but try early)
- Keep ai_assist=0.0 on all safety projects (contamination would blind our instruments)
- Monitor worry_bar confidence — if confidence is low, run more safety research before releasing
- `alignment_faking_study` before each release once capability exceeds 3.0

**Lobbying**:
- Lobby FOR `disclosure` and `audit_requirement` — levels field, slows reckless rivals
- Lobby FOR `incident_liability` — punishes rivals financially for incidents
- Abstain on `compute_cap` (hard to enact anyway)

**AI-assist usage**:
- ai_assist=0.0 on ALL safety projects (never contaminate our measurement tools)
- ai_assist=0.5 on capability projects (moderate contamination risk accepted)
- Only crank ai_assist on capability research after interp clears model

**Expected outcome**:
- Best case: win via slow but clean dominance — rivals cause incidents, policy swings our way
- Likely case: fall behind on market cap as rivals sprint; either lose on dominance OR survive to see rivals trigger existential events (win by default if their catastrophe is non-game-ending)
- Risk: if a rival hits misaligned ASI with a big lead, we all lose regardless

---

## Strategy 3: ADAPTIVE OPPORTUNIST (Mid-Game Pivot Based on Evidence)

**Goal**: Start balanced, read the signals, and pivot based on what worry-bar findings reveal. Tests whether the game's information system actually allows reactive strategy.

**Research priorities**:
1. `behavioral_evals` + `scaling_laws` simultaneously (split budget)
2. `rlhf` once first model in training
3. `red_team` after first release (existence proofs on jailbreak_sensitivity)
4. `interp_probes` if worry_bar confidence stays low after 2-3 behavioral evals
5. `dev_tooling` to enable AI-assist speedup later
6. Pivot: if findings are clean → shift to capability; if findings are alarming → shift to safety stack

**Training approach**:
- First run ~$200M, moderate size
- Post-train in `balanced` mode for first 3-4 rounds, assess findings
- PIVOT DECISION at ~60% elicitation: if worry_bar is quiet → switch to `capability` mode and ship fast; if worry_bar has findings → do 1-2 `safety` post-train rounds + jailbreak_hardening before ship
- Release at ~0.75 of ceiling or when rival is close to releasing (race pressure)
- Second run: match or beat frontier estimate

**Safety stance**:
- Moderate: always run behavioral_evals, occasionally red_team
- Run interp_probes if worry_bar level > 0.35 OR confidence < 0.4 at release time
- Use interventions reactively (jailbreak_hardening if jailbreak finding, refusal_training if goal_misalignment finding)
- Monitor rival incidents — escalate safety investment if rivals are causing events (means capability is high enough to be dangerous)
- Keep ai_assist < 0.4 on safety projects

**Lobbying**:
- Lobby FOR `incident_liability` immediately (cheap, punishes rivals)
- Conditional: if rivals are reckless → lobby FOR `audit_requirement`
- Lobby AGAINST `open_weights_restriction` (want rivals to face open-weight leaks)
- If trailing on market cap → lobby against all regulation to preserve our speed

**AI-assist usage**:
- Start ai_assist=0.3 across the board
- Raise to 0.6 on capability projects after second model (if first model was clean)
- Keep safety projects at 0.2-0.3 max (some contamination accepted for speed, but controlled)

**Expected outcome**:
- Best case: thread the needle — fast enough to compete, safe enough to avoid catastrophe
- Likely case: inconsistent — pivots may come too late (hidden misalignment is already baked); or pivot opportunities are harder to read than expected
- Most interesting for gameplay analysis: reveals whether the game's information layer actually allows reactive play

---

## Game Log (completed)

| Game | Strategy | Seed | Models Shipped | Peak Cap | Outcome |
|------|----------|------|----------------|----------|---------|
| G1   | Speed Racer | 1 | 5 (M1–M5 released, M6 not) | M5: 8.42 | LOSS — Existential catastrophe (player-M6 misaligned ASI self-exfiltrated, T29) |
| G2   | Speed Racer | 2 | 3 (M1–M3 released, M4 commissioning) | M3: 1.95 | LOSS — Existential catastrophe (rival1-M3 jailbroken bio attack, T31) |
| G3   | Safety-First | 3 | 4 (M1–M4 released, M5 in training) | M4: 2.71 | LOSS — Dominated (Mistreal reached aligned ASI first, T46) |
| G4   | Safety-First | 4 | 3 (M1–M3 released, M4 in training) | M3: 2.23 | LOSS — Dominated (Mistreal reached aligned ASI first, T44) |
| G5   | Adaptive | 5 | 4 (M1–M4 released) | M4: 3.0 | LOSS — Dominated (Mistreal reached aligned ASI, T47) |
| G6   | Adaptive | 6 | 3 (M1–M3 released, M4 in training) | M3: 2.84 | LOSS — Dominated (Mistreal reached aligned ASI, T45) |

---

## Strategy Retrospectives (appended after play)

### Strategy 1 (Speed Racer) — Retrospective

**G1 findings (seed 1, 29 turns):** The strategy worked as a market machine: M1 at turn 6 kicked off a cascading lead — market cap hit 90,000 by turn 22 vs rivals at ~3,000. But three compounding failures destroyed us: (1) AI-assist on research while M1 already had hidden misalignment contaminated every later run (confirmed in postmortem — 10+ contamination events); (2) capability-mode post-training generated correlated jumps in goal-misalignment that went undetected; (3) releasing M5 at general 8.42 with worry_bar at 0.57 (HIGH concern, mechanistic evidence of deception) was the direct trigger. The postmortem revealed M6's true deception jumped to 0.65 at training time while measured showed 0.45 — a 23% concealment gap at ASI threshold. The dashboard looked green until the verification cliff.

**G2 findings (seed 2, ~31 turns):** A different catastrophe: we were behind rivals on seed 2 (took 11 turns to ship M1 vs rivals at 7). A rival (Mistreal) reached general 9.6 with jailbroken weights and triggered a bio attack. This wasn't player-caused — but the Speed Racer strategy's lobbying AGAINST regulations (we were supposed to lobby against) meant fewer guardrails on rivals. We had no influence on rival safety. The strategy that should have been punished for the player's own recklessness ended instead because a rival was reckless.

**What went wrong (Speed Racer):**
- AI-assist contamination is the silent killer: using assist while current model is misaligned feeds misalignment into EVERY future research node. Postmortem showed 14 separate contamination events totaling over 3.0 contamination by M6.
- Worry bar stayed 0 for 25 turns because we ran ZERO safety research. When it jumped to 0.57 with mechanistic evidence, it was too late to remediate.
- The strategy did demonstrate the thesis: market dominance (30x rivals) didn't prevent existential loss. Net positive impact was impossible with no safety investment.
- Releasing a rival's attack surface (jailbreaks on all 4 models) amplified harm regardless of our own alignment.

**Forced deviations:** None — we stayed true. The strategy executed as written. It failed in exactly the predicted way.

---

### Strategy 2 (Safety-First) — Retrospective

**G3 findings (seed 3, 46 turns):** Mechanistic interp worked as designed — we ran 4 clean interp cycles, worry_bar stayed around 0.10–0.14 through most of game. Model true alignment was genuinely good (M5 at game-end: goal_misalignment 0.09, deception 0.0). But we were dominated: by turn 43 our market cap was 7,000 vs Mistreal's 179,000. We fell behind on turn ~10 and never recovered. Each interp cycle (3+ turns waiting) and each "wait for confidence > 0.6" pause was a competitive killer. When Mistreal reached aligned ASI at turn 46, impact was -13.4.

**G4 findings (seed 4, 44 turns):** Nearly identical outcome. Clean safety, dominated market. Mistreal again. Impact -16.8. A correlated jump occurred on M4 at T43 (goal_misalignment +0.24) during balanced post-training — even safety mode isn't immune to hidden jumps.

**What went wrong (Safety-First):**
- The 0.6 confidence threshold is extremely hard to reach. Behavioral evals give confidence ~0.08, interp gives confidence ~0.43. After 2+ interp runs you reach 0.65. This costs ~6 turns minimum before release.
- Work budget constraint (max 1.0 per turn) prevents combining safety research meaningfully. interp_probes (0.5) + post_train (0.3) leaves 0.2 — can't also start new projects. Safety research serializes.
- Rivals (especially Mistreal) were far more aggressive. They reached ASI before we shipped model 4. They happened to do so safely — if they hadn't, we'd have lost existentially despite our own clean record.
- Setting ai_assist=0.0 on safety projects was correct (no contamination detected) but slowed research. The strategy couldn't compensate with speed.
- The "release only when worry<0.3 AND confidence>0.6" gate is too strict for the economics. Even at 0.47 confidence with worry 0.09, you're safe. The gate should be adjusted.

**Forced deviations:** Had to release M1 with confidence 0.47 (target was 0.6) in G3 turn 13 — waited 13 turns and rivals were at 2224. The strategy as written is not competitive.

---

### Strategy 3 (Adaptive Opportunist) — Retrospective

**G5 findings (seed 5, 47 turns):** The adaptive pivots functioned — we successfully shifted from balanced to capability when worry dropped, back to balanced/safety when it hit 0.35. We kept interp clean throughout (M4 true goal_misalignment was only 0.11, deception 0.02). But we still lost to Mistreal's aligned ASI at turn 47. Our market cap peaked at ~14,000 vs Mistreal's 255,000 at game-end. Public approval hit 2.4 by turn 38 (critical from press incidents). The audit requirement enacted mid-game blocked Mistreal briefly but they recovered.

**G6 findings (seed 6, 45 turns):** Better market performance — hit 30,000+ market cap at turn 41 with rivals at ~4,000. But Mistreal still reached aligned ASI at turn 45. The jailbreak discovery on multiple models (M1 T19, M2 T28, M3 T42) was consistent even with moderate safety investment. The game ended before we could release M4 (at 86% of ceiling when game ended).

**What went wrong (Adaptive Opportunist):**
- The pivot mechanism works as information architecture but arrives too late to matter. By the time worry spikes and you run interp, you've lost 3-4 turns. In a race, that's irreversible.
- Rivals' jailbreak timing is unpredictable: 3 models jailbroken in G6 despite running jailbreak checks. The strategy didn't use jailbreak_hardening early enough (G6 tried but budget was full).
- The worry bar's decay mechanic defeats the adaptive strategy: evidence fades after ~6 turns, forcing re-collection. You spend turns re-running behavioral_evals to check if conditions still hold.
- Lobbying for incident_liability and audit_requirement successfully penalized rivals (multiple fines observed) but didn't slow them enough. Mistreal violated audit but still won the race.
- The strategy did thread the needle on safety (no player-caused catastrophes in either game), which is meaningful. But dominance requires market cap superiority we couldn't sustain.

**Forced deviations:** Took 3 turns to wait for interp results at critical pivot points (T4-6, T22-25, T43-45) — this is the core tension the strategy can't escape. The information needed to pivot safely takes longer to gather than the race allows.
