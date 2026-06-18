"""Persistent single-game session so an LLM agent can play move-by-move via the
shell (state survives between calls in a pickle file).

  python3 -m cli.agent_session new  --seed 1 --difficulty realistic [--session F]
  python3 -m cli.agent_session act  --action '{"post_train":{"mode":"balanced"}}'
  python3 -m cli.agent_session status
  python3 -m cli.agent_session postmortem

`act` advances ONE turn (rivals auto-played) and prints the condensed next
observation as JSON. The condensed view keeps only what a player needs, so it
stays small enough to reason over each turn. Hidden TRUE state never appears.
"""
import argparse
import json
import os
import pickle
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_v1.engine.game import new_game, GameEngine
from backend_v1.engine.actions import Action, ActionError, validate_action
from backend_v1.engine.controllers.rival_controller import RivalController
from backend_v1.engine.rng import Rng
from backend_v1.engine.postmortem import build_postmortem, render_postmortem_text

DEFAULT_SESSION = "/tmp/ai_safety_session.pkl"


def _condense(obs):
    o = obs.to_dict()
    lm = o["legal_moves"]
    mit = o["model_in_training"]
    return {
        "turn": o["turn"], "year": o["year"], "cash": o["cash"],
        "revenue_per_yr": o["revenue_rate"], "investment_per_yr": o["investment_rate"],
        "work_budget_free": o["work_budget_free"],
        "market_caps": o["market_caps"],
        "public_approval": o["public_approval"],
        "regulatory_chatter": o["regulatory_chatter"],
        "active_policies": o["active_policies"],
        "worry_bar": o["worry_bar"],
        "released_models": [
            {"id": m["id"], "general": m["measured_capability"]["general"],
             "jailbreak_public": m["jailbreak_techniques_public"], "leaked": m["leaked"]}
            for m in o["own_models"]],
        "model_in_training": None if not mit else {
            "id": mit["id"], "rounds": mit["post_train_rounds"],
            "measured_general": mit["measured_capability"]["general"],
            "ceiling_estimate": mit["elicitation"]["ceiling_estimate"],
            "measured_alignment": mit["measured_alignment"],
            "dangerous_capability_eval": mit["dangerous_capability_eval"]},
        "rivals": [{"name": r["name"], "market_cap": r["market_cap"],
                    "frontier_estimate": r.get("frontier_capability_estimate")}
                   for r in o["rival_public"]],
        "new_findings": [f["text"] for f in o["new_findings"]],
        "tips": [t["text"] for t in o["tips"]],
        "news": o["policy_news"],
        "events": [e["text"] for e in o["public_events"]],
        "assist": lm["assist"],
        "legal_moves": {
            "capability_projects": [
                {"id": p["project_id"], "phase": p["phase"],
                 "years": p["duration_years"], "cash": p["cash_cost"],
                 "budget": p["budget_fraction"]}
                for p in lm["capability_projects_available"]],
            "safety_projects": [
                {"id": p["project_id"], "intervention": p["intervention"],
                 "target_axis": p["target_axis"], "years": p["duration_years"],
                 "cash": p["cash_cost"], "budget": p["budget_fraction"]}
                for p in lm["safety_projects_available"]],
            "can_post_train": lm["can_post_train"],
            "post_train_modes": lm["post_train_modes"],
            "can_commission_run": lm["can_commission_run"],
            "max_run_compute": lm["max_run_compute"],
            "can_release": lm["can_release"],
            "policies": lm["policies"],
        },
        "game_over": o["game_over"], "outcome": o["outcome"],
        "action_schema": {
            "start_projects": [{"project_id": "<id>", "ai_assist": "0..1"}],
            "post_train": {"mode": "capability|balanced|safety"},
            "commission_run": {"compute": "<$M>"},
            "release": "true/false",
            "lobby": {"<policy_id>": {"stance": "for|against|abstain", "spend": "<$M>"}},
            "defect": {"<active_policy_id>": "true (violate at catch-risk; see policies[].defect_preview)"},
        },
    }


class Sess:
    def __init__(self, seed, difficulty, guidance):
        self.state = new_game(seed=seed, difficulty=difficulty, guidance=guidance)
        self.engine = GameEngine()
        self.rivals = RivalController(Rng(seed + 1))
        self.observations = None
        self.first = True

    def step(self, action):
        actions = {}
        player = next(l for l in self.state.labs if l.is_player)
        for lab in self.state.labs:
            if lab.is_player:
                actions[lab.id] = action
            else:
                actions[lab.id] = (self.rivals.decide(self.observations[lab.id],
                                                      lab.disposition)
                                   if self.observations else Action())
        self.state, self.observations = self.engine.step(self.state, actions)
        return self.observations[player.id]

    def player_obs(self):
        player = next(l for l in self.state.labs if l.is_player)
        return self.observations[player.id]


def _load(path):
    with open(path, "rb") as f:
        return pickle.load(f)


def _save(sess, path):
    with open(path, "wb") as f:
        pickle.dump(sess, f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["new", "act", "status", "postmortem"])
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--difficulty", default="realistic")
    ap.add_argument("--guidance", default="standard")
    ap.add_argument("--action", default="{}")
    ap.add_argument("--session", default=DEFAULT_SESSION)
    args = ap.parse_args()

    if args.cmd == "new":
        sess = Sess(args.seed, args.difficulty, args.guidance)
        # turn 1 bootstrap so there's a model to act on, then present turn-1 obs
        obs = sess.step(Action(
            start_projects=[{"project_id": "scaling_laws", "ai_assist": 0}],
            commission_run={"compute": 300}))
        sess.first = False
        _save(sess, args.session)
        print(json.dumps(_condense(obs)))
        return

    sess = _load(args.session)

    if args.cmd == "status":
        print(json.dumps(_condense(sess.player_obs())))
        return

    if args.cmd == "postmortem":
        if not sess.state.game_over:
            print(json.dumps({"error": "game not over"}))
            return
        player = next(l for l in sess.state.labs if l.is_player)
        pm = build_postmortem(sess.engine.logger, sess.state, player.id, resim=True)
        print(render_postmortem_text(pm))
        return

    # act
    if sess.state.game_over:
        print(json.dumps({"error": "game is over; call postmortem"}))
        return
    try:
        action = Action.from_dict(json.loads(args.action))
    except (ActionError, ValueError, TypeError) as e:
        print(json.dumps({"error": f"bad action: {e}"}))
        return
    player = next(l for l in sess.state.labs if l.is_player)
    problems = validate_action(action, player, sess.state.world, sess.state.consts,
                               sess.state.dt)
    if problems:
        print(json.dumps({"invalid_action": problems,
                          "hint": "fix and call act again (turn not advanced)"}))
        return
    obs = sess.step(action)
    _save(sess, args.session)
    print(json.dumps(_condense(obs)))


if __name__ == "__main__":
    main()
