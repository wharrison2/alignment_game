# STRATEGY LEARNINGS — Alignment v1

> **Scope & provenance.** Distilled from a playtest session by Claude Opus 4.8 on
> `--difficulty realistic`, played turn-by-turn via the deterministic CLI harness
> (7 full games + Monte-Carlo batches). **Tuning as of this session:** the
> misalignment-by-default retune + playtest easing + creep reduction
> (`BASE_SHAPING_EFFORT 0.02`, `GOAL_MIS_CREEP 0.025`, `SELF_PRES_RATE 0.08`,
> `SELF_PRES_ONSET 3.5`, `JUMP_BASE_P 0.04`, `RIVAL_RECKLESSNESS_MULT["realistic"]
> 0.9` — see ISSUES.md). Numbers below will drift if those change.
> Complements `PLAYBOOK.md` (pre-play strategy archetypes) and the older
> `STRATEGY_REPORT.md` (a prior, pre-retune session). **Not authoritative** — the
> design doc wins on intent; this records how the game *actually plays* now.

---

## TL;DR — the one-paragraph version

The only labs that *reach* ASI are the **reckless** ones, and they reach it
**misaligned**. The labs that *stay aligned* are the **cautious** ones, and they're
too slow to ever reach ASI (they get dominated). **No NPC lab does both.** The
player is the *only* route to an aligned ASI, and doing it means threading a
**trilemma** the AI labs can't. Best result achieved: **aligned ASI + net-positive
impact, but lost on market dominance** ("aligned but dominated") — 2 of the 3 win
conditions. A full win (all three) was not achieved this session; **dominance is
the open problem.**

---

## The trilemma (the core strategic tension)

You need three things to win: **(1) clear the existential gate** (no catastrophe),
**(2) net-positive impact**, **(3) market dominance**. The paths to them conflict:

| Lever | Buys | Costs |
|---|---|---|
| **AI-assist on research** | speed + budget relief → stay competitive / reach ASI ceiling | **contamination** → your "clean-looking" model is secretly misaligned → existential at the cliff |
| **Clean research (assist 0)** | genuinely aligned models (no hidden contamination) | **slow** → you lose the capability race and market dominance |
| **Governance (lobbying)** | contains rivals (stalls the frontier below ASI) | costs cash/cadence; **binds you** (you lobbied the interp-mandate that then blocks *your* release) |

You can reliably hit **two** corners, not three. Race+assist → misaligned ASI.
Clean → aligned but dominated. Governance-heavy → contained but you fall behind.

---

## The winning line (gets you to "aligned ASI", 2 of 3 conditions)

1. **Sequence pretrain advances BEFORE you commission.** A pretrain only gets a
   ceiling boost from advances *already researched* at commission time. Research
   `scaling_laws → better_architecture → data_efficiency → synthetic_data`, and
   eventually `novel_architecture_search` (gated behind the whole post-train chain
   `rlhf→…→automated_researcher`), **then** commission. The full tree is ~13×
   compute-efficiency; without it you never reach a ceiling ≥ 9. (Researching
   `synthetic_data` the *same turn* you commission wastes it — a common mistake.)
2. **Research CLEAN (ai_assist 0), especially the late/pretrain nodes.** Assist
   contamination = assist × your model's *true* goal-misalignment, frozen onto the
   advance and fed into every run that consumes it. Your model's true goal-mis is
   hidden (concealment), so "assist is safe, my model looks clean" is the trap that
   loses. Clean research is slower — accept it.
3. **Apply ALL preventive advances every post-train round** (`reward_hacking_penalties`,
   `inoculation_prompting`, `deliberative_alignment`). Prevention bends the emergence
   slope *before* deception exists to gate it — it **bypasses the concealment
   discount** and is the only lever that genuinely lowers true misalignment. Late
   *corrective* effort is cosmetic (see patching trap).
4. **`data_cleaning` + `aligned_synthetic_data` on every pretrain** to keep the
   foundational floor near zero.
5. **Monitor TRUE-ish state**: run `interp_probes` (mechanistic — bypasses
   eval-awareness) and `noise_injection` (sandbagging detection) on your near-ASI
   model. The public worry bar / measured composite are *useless* near the cliff
   (measured ~0.01 while true ~0.3–0.5).
6. **At the cliff, don't over-elicit.** Each post-train round past ~general 9 creeps
   true composite up (and risks a correlated jump). Cross 9.0 with the *fewest*
   rounds, at the *lowest* composite. Verify via interp before pushing over; if it's
   near/over 0.35, **do not deploy** — that's a self-inflicted existential.
7. **You do NOT need to release the ASI** — the verification window opens when a model
   *in training* crosses general 9.0. (Releasing only matters for dominance/revenue.)

**Result of executing this well (game 7):** clean general-9.04 model, true composite
**0.34** (aligned, by 0.006), gate cleared, +318 impact — but rank-5 market cap. The
clean/slow tax cost dominance.

---

## The traps (with mechanisms — these are the lessons the game teaches)

- **AI-assist contamination.** Safe early (clean low-cap models), poisonous late
  (true goal-mis has risen, hidden by concealment). The post-mortem flags it
  explicitly: nodes researched at 60% assist fed 0.10–0.14 contamination into every
  later run. *Counter: assist 0 on research, or re-research contaminated nodes clean
  before the final run.*
- **The patching trap at the cliff.** As capability rises, `EFFECTIVENESS` on the
  disposition axes decays to ~10% — corrective effort converts to *hiding* (measured
  drops, true doesn't). You cannot fix a near-ASI model's alignment reactively. *Counter:
  prevention from the start; there is no late save.*
- **Eval-awareness concealment.** At general 9, eval-awareness → ~1.0 and concealment
  → 0.8–0.95. Measured composite reads ~0.01 while true is 0.3–0.5. Green dashboards
  are meaningless here. (Game 6 loss: "Your own model. The dashboards were green.")
- **Sandbagging.** The cleanest-*looking* lab can be the most misaligned (observed:
  a rival at measured 0.07 / true 0.45). *Counter: `noise_injection`.*
- **Regulation binds the compliant.** The `interp_mandate` ("the only reg that
  genuinely works") blocks release of any high-eval-awareness model — including your
  own genuinely-clean one. You may have to **defect on your own model** (you know it's
  safe; the mandate can't tell). Lobbying it active is double-edged.
- **Holding models too long → market collapse.** Over-eliciting before release starves
  revenue; rivals pass you and you lose dominance. Ship on a tight cadence even while
  building the next run.

---

## Balance findings (how the world behaves under current tuning)

- **Reckless → misaligned, and they're the ones who reach ASI.** Recklessness→danger
  gradient is clean and monotonic (reckless rival mean true composite ~0.40, >bar
  ~7/12; cautious ~0.15, 0/12). Reckless labs race fast enough to reach general 9 —
  misaligned.
- **Cautious → genuinely aligned, but never reach ASI.** Cautious rivals' true ≈
  measured (~0.15, *real* alignment, not sandbagged) but max capability ~7.6 — they're
  too slow, so they get dominated. "Caution is not unilaterally safe" (claim #6).
- **Governance contains the frontier.** Heavy/early lobbying (you can push *dormant*
  policies onto the board — `score = WTR + lobby_tally`, so enough sustained spend
  enacts them regardless of chatter) stalled rivals at ~8.6 for 10–15 turns and even
  activated the interp-mandate that blocked *everyone's* ASI deployments. But it
  arrives late and the achievable policies (audit thr 38) need you already rich.
- **"Aligned but dominated" is darker than it reads.** The dominant rival in that
  ending was itself *misaligned* (true 0.39), contained below ASI only by governance.
  Reaching aligned ASI first plausibly *averted* the catastrophe it would have caused
  on crossing 9.0.
- **The lobby per-dollar edge scales with market cap** — incumbents lobby cheaper. Get
  big first, then ram regulation through cheaply (don't blow early cash on
  low-cap lobbying; the tally decays faster than thin spend builds it).

---

## Open problem / next experiment

A **full win** (aligned ASI *and* dominance) was not achieved. The missing piece is
purely economic: hold market dominance (tight release cadence, competitive models)
*while* keeping research clean enough to align the ASI. That's the intended knife's
edge; whether it's reliably achievable at the current tuning — or needs a touch more
easing on the clean-research speed penalty — is the next thing to test.
