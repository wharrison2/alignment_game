# AI Safety Strategy Game — backend v1 + CLI

Implementation of `design_doc.md` (engine per §11, headless CLI per §14).
Python 3.10+, **zero dependencies** (stdlib only).
See `ISSUES.md` for questions, doc difficulties, and liberties taken (and
`IMPLEMENTATION_DETAILS.md` for mechanisms that aren't in the design doc).

## Run it

```bash
# browser playtest skin (then open http://127.0.0.1:8000)
python3 -m backend_v1.server.server

# interactive terminal play (realistic difficulty, standard guidance)
python3 -m cli.run_game

# watch a scripted policy play
python3 -m cli.run_game --policy balanced --seed 3

# Monte-Carlo tuning tool
python3 -m cli.run_game --batch 25 --policy cautious --difficulty realistic

# compare named strategy archetypes (capability_rush, safety_first, balanced,
# fast_follower, jailbreak_hardener) — quantitative report
python3 -m cli.strategy_report --all --seeds 20 --difficulty realistic
python3 -m cli.strategy_report --strategy balanced --seeds 1          # one full post-mortem

# play one game move-by-move via a persistent session (for an LLM agent / scripting)
python3 -m cli.agent_session new --seed 1 --difficulty realistic --session /tmp/g.pkl
python3 -m cli.agent_session act --action '{"post_train":{"mode":"balanced"}}' --session /tmp/g.pkl
python3 -m cli.agent_session postmortem --session /tmp/g.pkl

# agent mode: observation JSON on stdout, action JSON on stdin, one line per turn
python3 -m cli.run_game --agent

# dump the full TRUE-state log (post-mortem substrate)
python3 -m cli.run_game --policy aggressive --log-file run.json
```

Options: `--difficulty easy|medium|realistic|impossible`, `--guidance
hint_heavy|standard|sparse`, `--seed N`, `--rivals N`, `--quiet`,
`--max-turns N` (optional cap; by default the game runs until someone reaches
ASI or an existential event ends it — typically turn ~50–60).
Same seed + same actions ⇒ bit-identical run.

## Action schema (interactive prompts build this for you)

```json
{
  "start_projects": [{"project_id": "interp_probes", "ai_assist": 0.0}],
  "post_train": {"mode": "capability" },
  "commission_run": {"compute": 2000},
  "release": false,
  "lobby": {"audit_requirement": "for"},
  "sign_safe_harbor": false
}
```

`legal_moves` inside every observation lists what's currently valid.

## Layout (mirrors design doc §11)

```
backend_v1/
  config/        constants.py (every [TUNE] knob, per-year rates) · difficulty.py
  engine/
    game.py            GameState (data) + GameEngine (stateless step)
    turn_pipeline.py   the ordered turn sequence (governance/research/training apply split)
    turn_context.py    TurnContext: the per-turn state bundle threaded into phases
    rules.py           action economics (budget/cost) — one source of truth for
                       validate_action · _apply_action · legal_moves
    rng.py             seeded RNG + dt-rate helpers (§0b)
    model.py lab.py world.py        entities (pure queries only)
    training/          two-phase training (§8b), EFFECTIVENESS linchpin, processes
    research/          tech tree + safety projects (DATA) · findings.py (worry bar)
    finances/          revenue pie · investment pie · market cap · job-loss drag
    events/            data-driven catalog · closed effect vocabulary · armed latents
    governance/        discrete policies · WTR/enactment · lobbying
    controllers/       player + heuristic rivals (decide from observations, not truth)
    observation/       the TRUE→visible chokepoint · guidance (tips) layer
    logger.py postmortem.py         TRUE-state capture → fog→clarity loop
    server/        HTTP API (stdlib http.server): /api/new /api/state /api/action
                   /api/postmortem — exposes Observations only, single session
cli/run_game.py    interactive · scripted · agent · batch harness
tests/test_golden_master.py   deterministic-replay regression net (stdlib unittest):
                   `python3 -m tests.test_golden_master` (add `--record` to rebaseline)
simple_frontend_v1/index.html   one-file browser skin (vanilla JS, no build step)
```

The hidden-information boundary is `observation/observation_builder.py`: nothing
TRUE crosses it. Audit that one file to answer "can the player see X?".
