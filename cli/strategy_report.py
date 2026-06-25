"""Monte-Carlo a named strategy (cli.strategies) in the player slot and report
how it does. Rivals use the built-in heuristic controller.

Run:
  python3 -m cli.strategy_report --strategy balanced --seeds 30
  python3 -m cli.strategy_report --all --seeds 20 --difficulty realistic
  python3 -m cli.strategy_report --strategy capability_rush --seeds 1 --trace
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_v1.engine.game import new_game, GameEngine
from backend_v1.engine.actions import Action
from backend_v1.engine.controllers.rival_controller import RivalController
from backend_v1.engine.rng import Rng
from backend_v1.engine.postmortem import build_postmortem
from cli.strategies import make_strategy, list_strategies


def play_one(strategy_name, seed, difficulty, guidance, trace=False):
    state = new_game(seed=seed, difficulty=difficulty, guidance=guidance)
    engine = GameEngine()
    rivals = RivalController(Rng(seed + 1))
    decide = make_strategy(strategy_name)
    srng = Rng(seed + 7)
    player = next(l for l in state.labs if l.is_player)
    observations = None
    peak_cap = 0.0
    while not state.game_over:
        actions = {}
        for lab in state.labs:
            if lab.is_player:
                if observations is None:
                    actions[lab.id] = Action(
                        start_projects=[{"project_id": "generative_pretraining", "ai_assist": 0}],
                        commission_run={"compute": 300})
                else:
                    player_obs_dict = observations[lab.id].to_dict()
                    actions[lab.id] = Action.from_dict(decide(player_obs_dict, srng))
            else:
                actions[lab.id] = (rivals.decide(observations[lab.id], lab.disposition)
                                   if observations else Action())
        state, observations = engine.step(state, actions)
        peak_cap = max(peak_cap, state.world.frontier_measured_general)
        if trace:
            trace_obs = observations[player.id]
            print(f"  t{trace_obs.turn:02d} cash {trace_obs.cash:7.0f} inv {trace_obs.investment_rate:6.0f} "
                  f"cap[mkt {max(trace_obs.market_caps.values()):7.0f}] frontier "
                  f"{state.world.frontier_measured_general:.2f} worry "
                  f"{trace_obs.worry_bar['level']:.2f}/{trace_obs.worry_bar['confidence']:.2f}")
    out = state.outcome
    pm = build_postmortem(engine.logger, state, player.id)
    return {
        "result": out["result"], "existential": out.get("existential", False),
        "own_fault": "YOURS" in out.get("detail", ""),
        "net_impact": out.get("net_impact", 0.0),
        "dominant": out.get("dominant", False),
        "turns": state.turn, "peak_frontier": round(peak_cap, 2),
        "headline": out["headline"], "postmortem": pm,
    }


def summarize(name, rows):
    n = len(rows)
    wins = sum(r["result"] == "WIN" for r in rows)
    exi = sum(r["existential"] for r in rows)
    own = sum(r["own_fault"] for r in rows)
    dom = sum(r["dominant"] for r in rows)
    avg_impact = sum(r["net_impact"] for r in rows) / n
    avg_turns = sum(r["turns"] for r in rows) / n
    avg_peak = sum(r["peak_frontier"] for r in rows) / n

    print(f"\n{name:20s} n={n}")
    print(f"  wins {wins} ({100*wins//n}%) · dominance {dom} · "
          f"existential endings {exi} (your fault {own})")
    print(f"  avg net impact {avg_impact:+8.1f} · avg game length {avg_turns:.0f} turns "
          f"· avg peak frontier cap {avg_peak:.1f}")

    return {"strategy": name, "n": n, "wins": wins, "existential": exi,
            "own_existential": own, "dominance": dom,
            "avg_impact": round(avg_impact, 1), "avg_turns": round(avg_turns, 1),
            "avg_peak_frontier": round(avg_peak, 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy", choices=list_strategies())
    ap.add_argument("--all", action="store_true", help="run every strategy")
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--seed0", type=int, default=1000)
    ap.add_argument("--difficulty", default="realistic")
    ap.add_argument("--guidance", default="standard")
    ap.add_argument("--trace", action="store_true", help="per-turn trace (1 game)")
    args = ap.parse_args()

    names = list_strategies() if args.all else [args.strategy]
    if not names or names == [None]:
        ap.error("pass --strategy NAME or --all")

    table = []
    for name in names:
        rows = []
        for i in range(args.seeds):
            if args.trace:
                print(f"\n=== {name} seed {args.seed0+i} ===")
            rows.append(play_one(name, args.seed0 + i, args.difficulty,
                                 args.guidance, trace=args.trace))
        table.append(summarize(name, rows))
        if args.seeds == 1:
            from backend_v1.engine.postmortem import render_postmortem_text
            print(render_postmortem_text(rows[0]["postmortem"]))

    if len(table) > 1:
        print("\n" + "=" * 64)
        print(f"{'strategy':20s} {'win%':>5} {'exist':>6} {'ownX':>5} "
              f"{'dom':>4} {'impact':>8} {'peak':>5}")
        for r in sorted(table, key=lambda x: (-x["wins"], -x["avg_impact"])):
            print(f"{r['strategy']:20s} {100*r['wins']//r['n']:>4}% {r['existential']:>6} "
                  f"{r['own_existential']:>5} {r['dominance']:>4} "
                  f"{r['avg_impact']:>8.1f} {r['avg_peak_frontier']:>5.1f}")


if __name__ == "__main__":
    main()
