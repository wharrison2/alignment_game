# CLAUDE.md — Development guide

**Scope.** This file is the *how we build* layer. `design_doc.md` is the authoritative *what we build* (mechanics, thesis, the model). This file holds development procedures and code standards that don't belong in the design doc. When the two conflict on *what* the game does, the design doc wins; on *how the code is written*, this file wins.

**Audience.** Human engineers and AI coding agents (Claude Code / "Fable"). Read both this and `design_doc.md` before starting work. Don't read any other .md files unless you specifically need to.

**The `.md` files, and which to trust:**
- `design_doc.md` — authoritative *what we build* (mechanics, thesis, the model).
- `CLAUDE.md` (this) — authoritative *how we build* (procedures, code standards).
- `ISSUES.md` — **active** build-notes companion (see §5): contradictions found, liberties taken, decisions made. Write to it; trust it.
- `IMPLEMENTATION_DETAILS.md` — descriptive catalog of subsystems/fields/structures that exist in the **code** but aren't in the design doc (e.g. the buyout mechanic, the eval-harness build/upgrade economy, `turn_context.py`/`rules.py`). Not authoritative — the design doc still wins on intent; this just keeps the gap discoverable. Keep it current when you add an undocumented mechanism.
- `README.md` — useful **run / entry-point reference** (the server plus the CLI tools: `cli.run_game`, `cli.strategy_report`, `cli.agent_session`, batch tuning). Good for *running* things headlessly; its "see `NOTES.md`" pointer is stale (that role is now `ISSUES.md`).
- `NOTES.md`, `GAMEPLAY_ISSUES.md`, `PLAYBOOK.md`, `STRATEGY_REPORT.md` — historical records from previous tasks. **Not authoritative**; read only if you're chasing the history of a specific decision.
- `STRATEGY_LEARNINGS.md` — distilled strategic/balance findings from a full turn-by-turn playtest (the trilemma, the winning line, the traps, how reckless/cautious rivals behave). **Not authoritative** (the design doc wins on intent), but the best record of how the game *actually plays* under the current tuning. Read it before balance work or before claiming a strategy works.

---

## 0. Prime directives

1. **The design doc is the source of truth.** Don't silently deviate. If a mechanic is underspecified, contradictory, or you had to invent something to ship, **write it down in ISSUES.md** (see §5, Build notes) — don't bury the decision in code.
2. **Legibility over cleverness, everywhere.** This codebase is read far more than it's written, by people (and agents) who weren't here for the conversation that produced it. Optimize every line for the next reader's comprehension, not for brevity or elegance. A longer, obvious version beats a shorter, clever one — always.
3. **The hidden/observed boundary is sacred.** A TRUE stat the player shouldn't see must be *impossible* to reach the frontend, not merely unrendered. Treat any code that could leak true state through the observation layer as a bug of the highest severity. (See design doc §11.)
4. **Determinism is a feature.** All randomness goes through the seeded RNG. Same seed + same actions ⇒ bit-identical game. This underpins replay, the post-mortem counterfactuals, and Monte-Carlo tuning. Never call a raw RNG or wall-clock-seeded random anywhere.
5. **No raw per-turn numbers.** Everything time-related is stored per-unit-time and scaled by `dt` at point of use (design doc §0b). Writing a literal per-turn probability or per-turn rate is a bug.

---

## 1. Code legibility

The core standard. Default to the version a tired human reads correctly at 2am.

### Naming
- **Descriptive, unabbreviated names.** `eval_awareness`, not `ea`. `concealment_discount`, not `cd` or `disc`. `expected_capability_gain`, not `ecg`. The cost of typing a long name is paid once; the cost of decoding a short one is paid by every reader forever.
- **Names state meaning, not type or mechanics.** `released_models`, not `model_list`. `quarters_until_release`, not `counter`. `is_sandbagging`, not `flag`.
- **Domain vocabulary matches the design doc exactly.** If the doc says "elicitation," the code says `elicitation`, not `extraction` or `unlocking`. One term per concept, the doc's term, everywhere. A reader should be able to grep a design-doc word and find the code.
- **Booleans read as assertions:** `is_released`, `has_active_litigation`, `can_commission_pretrain`. Avoid negatives in names (`is_not_ready` → prefer `is_ready` and negate at use).
- **Units in the name when ambiguous:** `duration_years`, `budget_fraction`, `penalty_usd`, `rate_per_year`. Especially given §0b's per-time discipline — a bare `duration` is a latent bug. If you're creating a constant without a true unit, give a sense of the scale and what it means.

### Functions
- **Human-readable, single-purpose functions.** A function does one nameable thing and its name says what. If the honest name needs "and," split it.
- **Short enough to hold in your head.** If a function doesn't fit on a screen, that's a smell — extract named helpers. Length isn't the rule; *number of things happening* is.
- **No big one-liners.** Do not chain comprehensions, ternaries, and calls into a single dense expression to save lines. Unpack it. A nested comprehension with a conditional and a function call is three ideas pretending to be one.
- **Name your intermediates.** Every meaningful sub-result gets a variable with a descriptive name, even if used once — *especially* if used once. The name is free documentation of *what this value is*.
  - Bad: `return base * (1 - sum(d[p][t] * strength(p, cap) for p in defenders))`
  - Good:
    ```python
    concealment_discount = 1.0
    for protector_axis in defender_axes:
        defense_weight = defends[protector_axis][target_axis]
        protector_strength = strength(protector_axis, capability)
        concealment_discount *= (1 - defense_weight * protector_strength)
    effectiveness = base_tractability[target_axis] * concealment_discount
    return effectiveness
    ```
  The good version is longer and that is the point: each line names a concept from the design doc (§5b), so a reader maps code to mechanic without decoding.
- **Early returns over nested conditionals.** Guard clauses at the top; keep the main path unindented.
- **Arguments: few and named.** More than ~4 positional args ⇒ pass a small struct/dataclass. Call sites should read as prose: `commission_pretrain(compute=..., advances=...)`, not `commission_pretrain(x, y, z, True, 0.3)`. No bare booleans/numbers at call sites — name them or use enums.

### Expressions and control flow
- **One idea per line.** If a line does two things, split it.
- **No magic numbers.** Every tunable lives in the constants module (design doc §12b), named. A literal `0.15` in logic is a bug waiting to be un-findable; `SANDBAG_REVENUE_PENALTY` is greppable and tunable.
- **Prefer explicit over implicit.** No relying on truthiness of empty collections where `len(x) == 0` is clearer; no clever short-circuit side effects.
- **Comments explain WHY, not WHAT.** The code says what (because it's legible). Comments capture intent, the design-doc rationale, the non-obvious constraint. Mirror the design doc's own "why not that" standard (§0): a comment that restates the line is noise; one that says *why this is gated by eval-awareness* is gold. Cite the design-doc section: `# patching trap: defended axis → discount→0, effort goes to measured only (design §5b)`. 

### Structure
- **Match the design doc's subsystem layout** (§11 file map). One subsystem per module; don't smear an entity's logic across files.
- **Entities answer questions about themselves; only the engine advances time** (design doc §11). Pure self-queries on `Lab`/`Model` are fine; turn-advancement is never a method on a state object.
- **Data-driven over branchy.** Catalogs (events, policies, advances, research items) are *data* the engine iterates uniformly, not `if/elif` chains. Adding content = adding a row, not a branch (design doc §10 event system, §10c policies).

---

## 2. The true/measured discipline (project-specific, non-negotiable)

The whole game is an information model; the code must make the see-able/hidden split structural, not conventional.

- **Separate types for TRUE state and OBSERVATIONS.** Don't hand a frontend (or an agent controller, or a rival controller) a `Model` with true stats and trust it not to look. Build an `Observation` that *cannot contain* what mustn't be seen.
- **One chokepoint** (`observation_builder`) reads true state and emits observations. It is the only place that crosses the boundary. Audit it like security code.
- **Rivals and the player both consume observations, never truth.** A rival controller reaching into true `Model` stats is the same bug as a frontend leak (design doc §10c rivals: no godmode).
- **Name variables for which side they're on:** `true_deception` vs `measured_deception`, never bare `deception` in code that could touch either. Ambiguity here is how leaks happen.
- **Guidance and warnings read observations only** (design doc §7c, §9) — never true state, never probabilities. They are presentation over already-computed observable values.

---

## 3. Working with randomness, time, and tuning

- **All stochastic draws** go through the seeded RNG module. A roll is `prob_this_turn(rate_per_year)` → `1 - e^(-rate*dt)`; an accumulator is `amount_this_turn(rate_per_year)` → `rate*dt` (design doc §0b). Don't reimplement these inline.
- **Tunables live in `constants.py`, denominated per the documented scales** (capability 0–10, alignment 0–1, durations in years, rates per year). `difficulty.py` selects/scales from there. A number that affects balance and isn't in the constants module is misplaced.
- **Tag invented/placeholder numbers.** Where the design doc left a value `[TUNE]` and you had to pick one to ship, name it clearly and note it in build notes (§5). Per design-doc §0, assistant-chosen balance numbers skew optimistic — they are drafts for the designer to push bleaker, not settled values.
- **Make new behavior testable headlessly.** Every subsystem should be exercisable via the CLI/batch harness (design doc §14) without a frontend. If you can't drive it from a scripted action, the interface is wrong.

---

## 4. Attribution & logging (the post-mortem depends on it)

- **Log TRUE state every turn, continuously** — never reconstruct after a loss (design doc §3, §10d).
- **Stamp causal attribution at the moment it's known**, not later. An event records the responsible lab + model when it rolls (design doc §0b attribution). An intervention records type/target/true-vs-measured-effect/which backfires fired, when it resolves (design doc §5b). The post-mortem reads these logs; it does not re-derive causation.
- **Structured log entries, not printf strings.** The post-mortem and the CLI report both consume the log; it needs to be data, not prose.

---

## 5. Build notes — write down what the doc didn't tell you

Maintain ISSUES.md (companion to the design doc, like the v1 one). When you:
- hit a **contradiction or underspecification** in the design doc → note it as a question for the designer, and what you did in the interim;
- **invent** a mechanism/number/structure the doc didn't specify → note it as a liberty taken, flagged for review (especially balance numbers, per §0 calibration);
- make an **implementation choice** with design consequences → note it.

The standard: a reader of ISSUES.md can reconstruct every place the code's behavior is *your* decision rather than the doc's. Don't make the designer diff code to find where you improvised.

Write a new header for each new task you are assigned, and sub-headers if you see fit. Write your decisions beneath it. Don't interfere with issue notes from previous sessions.

---

## 6. What to do when unsure

- **Underspecified mechanic:** implement the simplest version consistent with the thesis (design doc §0), flag it in ISSUES.md, keep going. Don't block.
- **Two readings of the doc:** pick the one that better serves the thesis claims (§0), note the fork.
- **Tempted to add scope** (a system the doc doesn't mention): don't, unless it's required to make a specified mechanic work. Note the temptation in ISSUES.md instead.
- **A change would touch the hidden/observed boundary, the RNG/determinism, or the time discipline:** stop and be careful — these are the load-bearing invariants. A mistake here is silent and corrosive. Note these decisions in ISSUES.md

---

## 7. Tone of the artifact itself

The game teaches; the code should too. A new contributor reading a subsystem should be able to learn *the mechanic* from the code, because the names are the design doc's names, the intermediates are the design doc's concepts, and the comments cite the design doc's reasoning. Legible code here is not just hygiene — it keeps the implementation honest to a design whose whole point is that hidden complexity is dangerous.

---

## 8. Running it & verifying changes

The design doc describes *what* exists, not *how to run or check it*. The operational facts:

- **Run the game:** `python3 -m backend_v1.server.server [--port 8000]`, then open the printed URL. Single in-memory session, stdlib only, no dependencies to install.
- **Determinism test:** `python3 -m unittest tests.test_golden_master`. It hashes the full TRUE-state log of a small matrix of scripted games — any change that shifts an RNG draw, reorders a phase, or alters budget / legal-move logic the scripted controller follows will move a digest and fail. After an **intentional** behavior change, re-record with `python3 -m tests.test_golden_master --record` and paste the printed `EXPECTED` block back into the test (note *why* in the comment above it). A digest change you did **not** intend is a regression — find the cause before re-recording, don't paper over it.
- **No JavaScript runtime in this environment** (no `node`/`deno`/`bun`). The frontend cannot be executed or unit-tested here. Verify frontend edits **statically**: brace/paren/bracket balance per file; every inline `on*="NAME("` handler name is exposed on `window` in `js/main.js`; every `import {X}` resolves to a matching `export`; then serve and `curl` the modules for `200 text/javascript`. For actual behavior, hand the user a short browser smoke-test — **don't claim runtime verification you couldn't perform.**

### Two verification gotchas that otherwise cost real time

- **Auditing the firewall: do NOT grep the observation JSON for substrings like `true` or `concealment`.** Both give false positives — JSON serializes booleans as lowercase `true` (e.g. `"released": true`), and the word "concealment" legitimately appears in *player-facing prose* (the interp-probe blurb explains the "concealment discount"). To check for a real leak, walk the observation dict and assert no **key** is in the forbidden set — `true_alignment`, `true_capability`, `concealment`, `foundational_floor`, `suppression`, `hidden_history`. The firewall is about keys/values crossing `observation_builder`, not words appearing in text.
- **The golden-master digest can move when you change `legal_moves` or `validate_action` — even though it hashes the TRUE log, not the observation.** The test's scripted "player" is driven by `RivalController.decide()`, which picks its actions from `legal_moves`. Narrow what's offered or legal and the controller's action stream changes → the TRUE trajectory changes → the digest moves. For an intentional change that's expected (re-record per §8); it is **not** a sign the RNG or firewall broke. Confirm the cause is the action-stream change before re-recording.

---

## 9. Frontend architecture — `simple_frontend_v1`

The design doc treats the frontend as a thin skin; this is how it is actually built. Vanilla **ES modules, no build step**, served by the Python server through a `/js/` static route (`server._static`, with a path-traversal guard).

- `index.html` — shell only: markup + CSS + `<script type="module" src="js/main.js">`.
- `js/core.js` — shared mutable game state as **live-binding `let` exports** (`OBS`, `NAMES`, `HIST`, `FEED`, `TRUTH`, `pending`). **Only `core` reassigns them** (in `apply`/`freshPending`/`resetFeed`); every other module reads them and mutates their *contents*. Also holds `api`, the formatting/budget helpers, the constants, and the **render bus** (`setRender`/`setOnGameOver`).
- `js/views.js` — every panel renderer and the inline-handler functions they generate.
- `js/warnings.js` — the §7c per-item "explain it, then carry it out" modal.
- `js/main.js` — the master `render()`, overlays, bootstrap, the dev-mode gate, and the **single place** inline-handler functions are attached to `window`.

Conventions when editing the frontend:
1. **Any function referenced from generated-HTML `onclick=`/`onchange=`/`oninput=` must be added to `main.js`'s `Object.assign(window, {...})`.** Miss it and the control silently does nothing (and with no JS runtime here, §8, you won't catch it without a browser).
2. **To re-render from a view handler, call the bussed `render` imported from `core`** — never import `main` from a view (that's a module cycle). Don't reassign `OBS`/`pending` outside `core`.
3. **The Truth tab is god-view/debug and dev-gated** — hidden unless the player ticks "dev mode" in the new-game modal (`setDevMode` in `main.js`). It is served from a **separate `/api/truth` endpoint**, never folded into the player observation. Keep it that way: §2's true/measured discipline applies to it in full.

**Where the §7c warnings live:** authored as **backend data** in `backend_v1/engine/observation/warnings.py` (catalog + item-to-warning mapping), served inside `legal_moves.warnings`, and rendered by `js/warnings.js`. The current catalog copy is a **DRAFT** awaiting the design-doc §7c/§0 accuracy review — read the `ACCURACY FLAGS` block at the top of that file before treating any warning line (or paper citation) as final.