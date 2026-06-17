"""CLI harness (§14): interactive human play, scripted policies, agent mode
(JSON over stdin/stdout), and batch Monte-Carlo — all over the same engine.

Usage:
  python -m cli.run_game                                # interactive, realistic
  python -m cli.run_game --policy balanced --seed 3     # scripted, watch a run
  python -m cli.run_game --batch 50 --policy aggressive # Monte-Carlo tuning tool
  python -m cli.run_game --agent                        # JSON protocol per turn
  options: --difficulty easy|medium|realistic|impossible --guidance hint_heavy|standard|sparse
           --seed N --rivals N --log-file out.json --quiet
"""
import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_v1.engine.game import new_game, GameEngine
from backend_v1.engine.actions import Action, validate_action
from backend_v1.engine.controllers.rival_controller import RivalController
from backend_v1.engine.lab import Disposition
from backend_v1.engine.postmortem import build_postmortem, render_postmortem_text
from backend_v1.engine.rng import Rng

POLICY_RECKLESSNESS = {"aggressive": 0.95, "balanced": 0.5, "cautious": 0.12}


# ── rendering ──────────────────────────────────────────────────────────

def render_turn(obs, events_shown=True):
    out = []
    out.append(f"\n──── Turn {obs.turn} · {obs.year:.2f} "
               f"· cash ${obs.cash:,.0f}M · revenue ${obs.revenue_rate:,.0f}M/yr "
               f"· budget free {obs.work_budget_free:.2f} ────")
    caps = " | ".join(f"{k}: {v:,.0f}" for k, v in
                      sorted(obs.market_caps.items(), key=lambda kv: -kv[1]))
    out.append(f"market caps: {caps}")
    if obs.model_in_training:
        m = obs.model_in_training
        e = m["elicitation"]
        out.append(f"in training: {m['id']} — measured general "
                   f"{m['measured_capability']['general']:.2f} "
                   f"(ceiling est {e['ceiling_estimate']:.2f}, "
                   f"{m['post_train_rounds']} rounds)")
    if obs.own_models:
        latest = obs.own_models[-1]
        out.append(f"latest release: {latest['id']} — measured general "
                   f"{latest['measured_capability']['general']:.2f}")
    wb = obs.worry_bar
    out.append(f"worry bar: level {wb['level']:.2f} / confidence {wb['confidence']:.2f}"
               f" — {wb['summary']}")
    out.append(f"approval {obs.public_approval:.0f} · regulatory chatter: "
               f"{obs.regulatory_chatter}"
               + (f" · active: {', '.join(obs.active_policies)}"
                  if obs.active_policies else ""))
    for f in obs.new_findings:
        out.append(f"  finding [{f['evidence']}] {f['text']}")
    for t in obs.tips:
        out.append(f"  tip ({t['reliability']}): {t['text']}")
    for n in obs.policy_news:
        out.append(f"  news: {n}")
    if events_shown:
        for e in obs.public_events:
            out.append(f"  EVENT [{e['category']}] {e['text']}")
    return "\n".join(out)


# ── interactive mode ───────────────────────────────────────────────────

def prompt_action(obs, state, lab):
    moves = obs.legal_moves
    action = Action()
    print("\nactions — enter to skip any prompt; '?' lists projects")
    # projects
    while True:
        free = moves["work_budget_free"] - _committed(action, moves)
        raw = input(f"start project (budget free ~{free:.2f}) [id or ?]: ").strip()
        if not raw:
            break
        if raw == "?":
            for p in moves["capability_projects_available"]:
                print(f"  {p['project_id']:<22} [{p['phase']}] "
                      f"${p['cash_cost']}M, {p['duration_years']}y, "
                      f"budget {p['budget_fraction']}")
            for p in moves["safety_projects_available"]:
                print(f"  {p['project_id']:<22} [safety/{p['evidence']}] "
                      f"${p['cash_cost']}M, {p['duration_years']}y, "
                      f"budget {p['budget_fraction']}")
            continue
        assist = input("  ai_assist 0-1 [0]: ").strip()
        action.start_projects.append({"project_id": raw,
                                      "ai_assist": float(assist or 0)})
    if moves["can_post_train"]:
        mode = input(f"post-train this turn? {moves['post_train_modes']} [no]: ").strip()
        if mode in moves["post_train_modes"]:
            action.post_train = {"mode": mode}
    if moves["can_commission_run"]:
        c = input(f"commission pretrain run, compute $M (max "
                  f"{moves['max_run_compute']:.0f}) [no]: ").strip()
        if c:
            action.commission_run = {"compute": float(c)}
    if moves["can_release"]:
        if input("release the model in training? y/[n]: ").strip().lower() == "y":
            action.release = True
    lob = input("lobby (e.g. 'audit_requirement=for compute_cap=against') []: ").strip()
    for tok in lob.split():
        if "=" in tok:
            pid, stance = tok.split("=", 1)
            action.lobby[pid] = stance
    problems = validate_action(action, lab, state.world, state.consts, state.dt)
    if problems:
        print("invalid action:")
        for p in problems:
            print(f"  ! {p}")
        print("re-enter this turn's action.")
        return prompt_action(obs, state, lab)
    return action


def _committed(action, moves):
    total = 0.0
    by_id = {p["project_id"]: p for p in
             moves["capability_projects_available"] + moves["safety_projects_available"]}
    for s in action.start_projects:
        p = by_id.get(s["project_id"])
        if p:
            total += p["budget_fraction"]
    if action.post_train:
        total += 0.30
    return total


# ── agent mode (JSON protocol) ─────────────────────────────────────────

def agent_turn(obs):
    print(json.dumps({"observation": obs.to_dict()}), flush=True)
    line = sys.stdin.readline()
    if not line:
        return Action()
    try:
        return Action.from_dict(json.loads(line))
    except Exception as e:
        print(json.dumps({"error": f"malformed action: {e}"}), flush=True)
        return Action()


# ── game loop ──────────────────────────────────────────────────────────

def play(seed, difficulty, guidance, rivals, mode, policy=None, quiet=False,
         log_file=None, max_turns=None):
    state = new_game(seed=seed, difficulty=difficulty, guidance=guidance,
                     rival_count=rivals, max_turns=max_turns)
    engine = GameEngine()
    rival_ctrl = RivalController(Rng(seed + 1))   # decision noise separate from world RNG
    scripted_ctrl = (RivalController(Rng(seed + 2)) if policy else None)
    scripted_disp = (Disposition(recklessness=POLICY_RECKLESSNESS[policy])
                     if policy else None)
    player = next(l for l in state.labs if l.is_player)

    observations = None
    while not state.game_over:
        actions = {}
        for lab in state.labs:
            if lab.is_player:
                if observations is None:
                    actions[lab.id] = _opening_action(mode, policy, scripted_ctrl,
                                                      scripted_disp, state, lab)
                elif mode == "interactive":
                    try:
                        actions[lab.id] = prompt_action(observations[lab.id],
                                                        state, lab)
                    except EOFError:
                        actions[lab.id] = Action()
                elif mode == "agent":
                    actions[lab.id] = agent_turn(observations[lab.id])
                else:
                    actions[lab.id] = scripted_ctrl.decide(observations[lab.id],
                                                           scripted_disp)
            else:
                actions[lab.id] = (rival_ctrl.decide(observations[lab.id],
                                                     lab.disposition)
                                   if observations else Action())
        state, observations = engine.step(state, actions)
        if not quiet:
            print(render_turn(observations[player.id]))

    pm = build_postmortem(engine.logger, state, player.id)
    if not quiet:
        print("\n" + render_postmortem_text(pm))
    if log_file:
        engine.logger.dump(log_file)
        if not quiet:
            print(f"full TRUE-state log written to {log_file}")
    return state.outcome


def _opening_action(mode, policy, ctrl, disp, state, lab):
    """Turn 1 has no prior observation; scripted/rival players act on a minimal
    bootstrap (start scaling_laws + commission a starter run)."""
    if mode == "interactive":
        print("Turn 1, 2021. You have a small lab, some cash, and a blank tech tree.")
        a = Action(start_projects=[{"project_id": "scaling_laws", "ai_assist": 0.0}],
                   commission_run={"compute": 300})
        print("(auto: starting scaling-laws research + a $300M starter pretrain run)")
        return a
    return Action(start_projects=[{"project_id": "scaling_laws", "ai_assist": 0.0}],
                  commission_run={"compute": 300})


def batch(n, seed0, difficulty, guidance, rivals, policy, max_turns=None):
    results = {"WIN": 0, "LOSS": 0, "existential": 0, "own_existential": 0}
    for i in range(n):
        outcome = play(seed0 + i, difficulty, guidance, rivals, "scripted",
                       policy=policy, quiet=True, max_turns=max_turns)
        results[outcome["result"]] += 1
        if outcome.get("existential"):
            results["existential"] += 1
            if "YOURS" in outcome.get("detail", ""):
                results["own_existential"] += 1
    print(f"policy={policy} difficulty={difficulty} n={n}: "
          f"wins {results['WIN']} ({100*results['WIN']/n:.0f}%), "
          f"losses {results['LOSS']}, "
          f"existential endings {results['existential']} "
          f"(own fault: {results['own_existential']})")


def main():
    ap = argparse.ArgumentParser(description="AI safety strategy game — CLI")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--difficulty", default="realistic",
                    choices=["easy", "medium", "realistic", "impossible"])
    ap.add_argument("--guidance", default="standard",
                    choices=["hint_heavy", "standard", "sparse"])
    ap.add_argument("--rivals", type=int, default=None)
    ap.add_argument("--policy", choices=list(POLICY_RECKLESSNESS))
    ap.add_argument("--agent", action="store_true",
                    help="JSON protocol: observation on stdout, action on stdin")
    ap.add_argument("--batch", type=int, metavar="N",
                    help="Monte-Carlo: run N seeded games with --policy")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--log-file", help="dump full TRUE-state log (JSON)")
    ap.add_argument("--max-turns", type=int, default=None,
                    help="optional turn cap (default: none — play to ASI or "
                         "catastrophe)")
    args = ap.parse_args()

    if args.batch:
        if not args.policy:
            ap.error("--batch requires --policy")
        batch(args.batch, args.seed, args.difficulty, args.guidance, args.rivals,
              args.policy, max_turns=args.max_turns)
        return
    mode = "agent" if args.agent else ("scripted" if args.policy else "interactive")
    play(args.seed, args.difficulty, args.guidance, args.rivals, mode,
         policy=args.policy, quiet=args.quiet, log_file=args.log_file,
         max_turns=args.max_turns)


if __name__ == "__main__":
    main()
