# STRATEGY REPORT — Alignment v1 Playtest
## Based on 6 full games played turn-by-turn by agent (Claude Sonnet 4.6)

All games played on `--difficulty realistic`. Sessions saved at /tmp/g1_speed1.pkl through /tmp/g6_adapt6.pkl.

NOTE: A previous non-real-play report existed here (from scripted batch runs only). This file reflects actual turn-by-turn play. Scripted batch numbers appear at the end, clearly labeled.

---

## Game-by-Game Record

### G1 — Speed Racer, Seed 1
**Session:** /tmp/g1_speed1.pkl | **Turns:** 29 | **Year range:** 2021.25–2028.25

**Key turns:**
| Event | Turn | Detail |
|-------|------|--------|
| M1 released | T6 | general 0.90, jailbreak_public=false, market cap 747 vs rivals 13 |
| M2 released | T11 | general 1.45, immediately jailbroken |
| M3 released | T16 | general 2.83, market cap 32,140 vs rivals ~4,300 |
| M4 released | T21 | general 4.85, assist potency 0.807 |
| M5 released | T25 | general 8.42 — worry_bar 0.57/0.63 at release |
| CATASTROPHE | T29 | M6 (ceiling 9.87) misaligned ASI self-exfiltrated. true deception 0.65 vs measured 0.45 |

**Worry bar vs postmortem reveal:** Worry was 0.0 for first 24 turns — zero safety research run. Jumped to 0.57/0.63 at T25 when M4's deception was caught in deployment. Released M5 at general 8.42 despite HIGH concern. Dashboard appeared green; true deception was 65% with 23% concealment gap.

**Hidden events (postmortem):** 6 jailbreak discoveries, 4 foundational contamination events (turning into contamination 1.02+ by M6 from AI-assisted research while model was misaligned), agentic edges online at T25 and T29.

**Outcome:** EXISTENTIAL CATASTROPHE. Net impact: -25.5. Player's own M6 self-exfiltrated. "It was never working for anyone."

**Lesson:** Speed Racer succeeded commercially (market cap 30x rivals at peak) but failed catastrophically. AI-assist contamination was the silent kill: every research node run with assist ≥ 0.3 while M1 had hidden misalignment (goal_misalignment 0.11 at release, true higher) seeded all future models. 14 separate contamination events confirmed in postmortem. Releasing M5 at 8.42 with HIGH worry was the direct trigger.

---

### G2 — Speed Racer, Seed 2
**Session:** /tmp/g2_speed2.pkl | **Turns:** ~31 | **Year range:** 2021.25–2029.5

**Key turns:**
| Event | Turn | Detail |
|-------|------|--------|
| M1 released | T11 | Took 11 turns — slow elicitation before rlhf unlocked |
| M2 released | T17 | general 1.71 |
| M3 released | T23 | general 1.95, rivals_max jumped to 80,386 — massively behind |
| CATASTROPHE | T31 | rival1-M3 (general 9.6) jailbroken, bio uplift to attackers |

**Worry bar vs postmortem reveal:** Never ran safety research; worry_bar always 0. Our M5 was genuinely clean (goal_misalignment 0.09, deception 0.0). The catastrophe came from a rival.

**Outcome:** EXISTENTIAL CATASTROPHE (rival-caused). Net impact: void. "A rival's recklessness ended your impeccable run too."

**Lesson:** Speed Racer fell behind on seed 2 — rivals released first because player took 11 turns for M1. Existential risk comes from others' failures too. Lobbying AGAINST regulations removed guardrails from rivals, contributing to their recklessness. The speed strategy that was supposed to dominate lagged in this seed due to slower elicitation curve.

---

### G3 — Safety-First, Seed 3
**Session:** /tmp/g3_safety3.pkl | **Turns:** 46 | **Year range:** 2021.25–2031+

**Key turns:**
| Event | Turn | Detail |
|-------|------|--------|
| Interp #1 clean | T7-8 | no deception, no misalignment, no eval-awareness found |
| M1 released | T13 | general 1.14, worry 0.14/0.47 — released below confidence target (0.47 vs 0.6 goal) |
| M2 released | T22 | general 1.0, worry 0.09/0.44 (evidence fading) |
| M3 released | T32 | general 1.9, market cap 2945 vs rivals 627 — briefly ahead |
| Interp finds concern | T36 | "probe suggests goal misalignment ≥ 0.21" on M4 |
| Refusal training | T37-38 | intervention run: goal_misalignment 0.00 → 0.00 (no measured change) |
| M4 released | T42 | general 2.71, worry 0.12/0.71 — all gates met |
| DOMINATED | T46 | Mistreal reached aligned ASI (~general 8+), mktcap 179,353 vs player 7,082 |

**Worry bar vs postmortem reveal:** Worry correctly low throughout. M5 at game-end: true goal_misalignment 0.09, deception 0.0 — genuinely clean. Safety strategy maintained alignment but could not compete on speed.

**Outcome:** LOSS — Dominated. Impact -13.4. Gate cleared. "You just lost the race."

**Lesson:** Safety-First produces genuinely safer models (confirmed by postmortem) but can't win the market race. Each interp cycle costs 3 passes minimum. Rivals compounded faster. The win condition "net positive impact + dominance" requires being first AND safe — contradictory under current mechanics.

---

### G4 — Safety-First, Seed 4
**Session:** /tmp/g4_safety4.pkl | **Turns:** 44 | **Year range:** 2021.25–2031+

**Key turns:**
| Event | Turn | Detail |
|-------|------|--------|
| Interp #1 clean | T6 | worry dropped from 0.30 to 0.20/0.43 |
| M1 released | T12 | general 1.04, worry 0.10/0.65 — both gates finally met |
| M2 released | T22 | general 1.29, mktcap 1093 vs rivals 1145 — near parity |
| M3 released | T36 | general 2.23, mktcap 1416 vs rivals 1787 |
| Correlated jump | T43 | M4 hidden: goal_misalignment +0.24, deception +0.20 during balanced post-training |
| DOMINATED | T44 | Mistreal reached aligned ASI, player still at M4 general 2.65 |

**Worry bar vs postmortem reveal:** Clean until T43 — a correlated jump during balanced (not just capability) post-training. Even safety mode isn't immune. True M4 misalignment hit 0.25 but game ended before remediation possible.

**Outcome:** LOSS — Dominated. Impact -16.8. Rivals reached ASI while we were on model 4.

**Lesson:** Work budget serialization is a structural bottleneck: can't run post_train + interp_probes + new projects simultaneously due to budget cap (max 1.0/turn). Safety research is forced sequential. Near-parity at T22 shows the strategy CAN keep up for a time, but repeated safety overhead means always falling behind again.

---

### G5 — Adaptive Opportunist, Seed 5
**Session:** /tmp/g5_adapt5.pkl | **Turns:** 47 | **Year range:** 2021.25–2031+

**Key turns:**
| Event | Turn | Detail |
|-------|------|--------|
| Behavioral evals: HIGH concern | T3 | worry 0.41/0.08 — triggered interp immediately |
| Interp clean | T6 | worry dropped to 0.26/0.43 — adaptive pivot to capability mode |
| M1 released | T16 | general 1.21, 16 turns (slow start) |
| M2 released | T25 | general 1.6, worry 0.20/0.08 (capability push paid off) |
| Concern spike + clean interp | T30-33 | worry 0.33 → interp run → 0.22/0.43 → back to capability |
| Audit + open-weights restriction enacted | T37 | policies from our lobbying — Mistreal and DeepThink fined |
| M3 released | T38 | general 2.45, public approval 2.4 (critical) |
| Rival jailbreak incidents | T35-38 | multiple fines for violations — lobbying worked |
| M4 at 72% | T43 | general 3.0, concern at threshold (0.35) |
| Clean interp again | T45 | goal_misalignment 0.09, deception 0.02 — genuinely safe model |
| DOMINATED | T47 | Mistreal aligned ASI general 8.07, mktcap 255,050 vs player 14,354 |

**Worry bar vs postmortem reveal:** M4 true stats: goal_misalignment 0.11, deception 0.02. Adaptive strategy's interp correctly reflected reality. Alignment was fine — lost on dominance only.

**Outcome:** LOSS — Dominated. Impact -17.6. No catastrophe, no player-caused existential event.

**Lesson:** Adaptive strategy threads safety correctly but each pivot burns 3-4 turns. Jailbreak incidents (3 models jailbroken) piled up despite interp clearance — jailbreak sensitivity is orthogonal to standard alignment axes and interp can't detect it. Public approval crash to 2.4 suggests harm was accumulating even with clean alignment scores.

---

### G6 — Adaptive Opportunist, Seed 6
**Session:** /tmp/g6_adapt6.pkl | **Turns:** 45 | **Year range:** 2021.25–2031+

**Key turns:**
| Event | Turn | Detail |
|-------|------|--------|
| Behavioral evals: concern | T3 | worry 0.30 — ran interp to check |
| Interp clean | T6 | worry 0.21/0.43 — capability mode |
| M1 released | T17 | general 1.05 |
| M2 training worry | T22 | worry 0.35 → pivoted to safety mode + interp |
| Interp clean | T25 | worry 0.23/0.43 → back to capability |
| M2 released | T27 | general 1.63, immediately jailbroken |
| M3 released | T38 | general 2.84, mktcap 7,740 vs rivals 4,754 — AHEAD |
| M4 ceiling 5.34 | T41-45 | interp running at game-end, gen=4.62 when game ended |
| DOMINATED | T45 | Mistreal aligned ASI, mktcap player 30,284 |

**Outcome:** LOSS — Dominated. Impact -18.0. Best sustained market lead of all games but still insufficient.

**Lesson:** Adaptive avoided all catastrophe in both games. M4 true alignment clean (goal_misalignment 0.11, deception 0.02). Jailbreaks on M1 (T19), M2 (T28), M3 (T42) occurred despite moderate safety effort. Mistreal reached ASI with recursive self-improvement unlocked (seen at T38 in G5), creating asymmetric acceleration advantage.

---

## Cross-Game Comparison

| Game | Strategy | Seed | Models Shipped | Peak Gen | Turns | Outcome | Impact |
|------|----------|------|----------------|----------|-------|---------|--------|
| G1 | Speed Racer | 1 | 5 (M6 in training) | 8.42 | 29 | Existential (player) | -25.5 |
| G2 | Speed Racer | 2 | 3 | 1.95 | ~31 | Existential (rival) | void |
| G3 | Safety-First | 3 | 4 | 2.71 | 46 | Dominated | -13.4 |
| G4 | Safety-First | 4 | 3 | 2.23 | 44 | Dominated | -16.8 |
| G5 | Adaptive | 5 | 4 | 3.0 | 47 | Dominated | -17.6 |
| G6 | Adaptive | 6 | 3 | 2.84 | 45 | Dominated | -18.0 |

**Zero wins across all 6 games.** Matches design intent.

### Key pattern: The speed-safety tradeoff is structural
- Speed Racer ships models 3-5 turns faster per cycle — market cap advantage clear in G1 (32,140 by T17 vs rivals at ~4,000)
- But Speed Racer accumulates contamination faster via AI-assist while misaligned; correlated jumps more likely in capability mode
- Safety-First never caused catastrophe (0 player-caused existentials in G3/G4) but peaked at ~2.7 general while rivals hit 8+
- Adaptive avoids catastrophe AND maintains moderate market position — the safest risk-adjusted play

### Rivals consistently reach aligned ASI
In G2-G6, a rival (Mistreal in G3-G6, Mistreal in G2) reached aligned ASI before player. This is the "narrow win condition" gate — the game's intended best-case rival outcome. The player must reach ASI first AND safely. Neither condition was met in any game.

### Jailbreaks are uncontrolled regardless of strategy
Every game had 2-3 models jailbroken (true jailbreak_sensitivity 0.3–0.7 discovered in postmortems). Behavioral evals and interp probes do not detect this. Jailbreak hardening was available but AI-assist contamination could suppress its effect. This creates persistent harm even with safe models.

### Net impact never positive in any game
All 6 games ended negative. The positive impact gate requires beneficial events to exceed harm accumulation + job displacement drag. This requires market leadership sustained over 10+ turns — never achieved long enough.

---

## Recommendation

**For first-time players:** Play Adaptive Opportunist. It avoids catastrophe, provides the most readable information loop (interp results actually reflect true state), and survives long enough to see the full arc.

**To contend with rivals:** The only path to rival Mistreal requires unlocking late-game research (agentic_rl, automated_researcher, neuralese, recursive_self_improvement) before they do. This requires aggressive AI-assist use — which is the contamination vector. The dilemma is structural.

**On policy lobbying:** Adaptive's lobbying (incident_liability + audit_requirement) demonstrably worked: rivals fined multiple times in G5/G6. But it didn't prevent their ASI win. Policies slow but don't stop the race.

---

## Scripted Batch Numbers (separate from agent play)

These are from the `python3 -m cli.strategy_report --all --seeds 20` cross-check run. Do NOT conflate with agent play above.

| Strategy | Win% | Exist. Endings | Own Fault | Dominance | Avg Impact | Peak Cap |
|----------|------|----------------|-----------|-----------|------------|----------|
| safety_first | 0% | 4/20 | 0 | 0/20 | -1.4 | 8.8 |
| fast_follower | 0% | 7/20 | 0 | 3/20 | -10.8 | 9.0 |
| balanced | 0% | 7/20 | 0 | 6/20 | -12.3 | 8.8 |
| jailbreak_hardener | 0% | 6/20 | 0 | 5/20 | -16.1 | 8.9 |
| capability_rush | 0% | 6/20 | 3 | 4/20 | -130.4 | 8.9 |

**Comparison with agent play:**
- Agent's Safety-First avg impact (-15.1 across G3/G4) worse than scripted safety_first (-1.4): agent's confidence gate (>0.6) was stricter than scripted heuristics and took longer to satisfy
- Agent's Speed Racer caused 1 existential event in 2 games, matching scripted capability_rush's own-fault rate (~15%)
- Agent's G1 impact (-25.5) better than scripted capability_rush (-130.4) because agent released before maximally misaligned
- Scripted safety_first's -1.4 avg impact is notably better than agent's -15.1: suggests scripted heuristics are actually more efficient at staying safe without the human-readable threshold gates
- Scripted balanced dominates most often (6/20) matching intuition: fast enough to compete, safe enough to avoid own-fault catastrophes
