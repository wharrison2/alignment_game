"""HTTP API layer (§11 `server/`): exposes Observations to the frontend.

Consumes engine output only — the handler never reaches into GameState; every
response body is either the player's Observation dict (already filtered by the
observation chokepoint), public market-cap history from the logger, or the
post-mortem (which is allowed to reveal TRUE state, §3: post-game = clarity).

Single in-memory session (playtesting tool, not a deployment).
stdlib only. Run:  python3 -m backend_v1.server.server [--port 8000]
"""
import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from backend_v1.engine.game import new_game, GameEngine
from backend_v1.engine.actions import Action, ActionError, validate_action
from backend_v1.engine.controllers.rival_controller import RivalController
from backend_v1.engine.observation.observation_builder import build_observation
from backend_v1.engine.postmortem import build_postmortem
from backend_v1.engine.rng import Rng

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", "..", "simple_frontend_v1")


class Session:
    def __init__(self, seed=0, difficulty="realistic", guidance="standard",
                 rivals=None, max_turns=None):
        self.state = new_game(seed=seed, difficulty=difficulty, guidance=guidance,
                              rival_count=rivals, max_turns=max_turns)
        self.engine = GameEngine()
        self.rival_ctrl = RivalController(Rng(seed + 1))
        self.observations = None      # per-lab observations from the last step
        self.player = next(l for l in self.state.labs if l.is_player)

    def player_observation(self):
        if self.observations is not None:
            return self.observations[self.player.id]
        # turn 0: no step has run yet; build a fresh filtered view directly
        return build_observation(self.state, self.player, [], [], [], [])

    def caps_history(self):
        hist = []
        for t in self.engine.logger.turns:
            per_lab_caps = {l["id"]: round(l["market_cap"], 1) for l in t["labs"]}
            hist.append({"turn": t["turn"], "caps": per_lab_caps})
        return hist

    def lab_names(self):
        return {l.id: l.name for l in self.state.labs}

    def submit(self, action_dict):
        if self.state.game_over:
            return {"errors": ["game is over — start a new game"]}
        try:
            action = Action.from_dict(action_dict)
        except (ActionError, TypeError, ValueError) as e:
            return {"errors": [str(e)]}
        problems = validate_action(action, self.player, self.state.world,
                                   self.state.consts, self.state.dt)
        if problems:
            return {"errors": problems}
        is_first_turn = self.observations is None
        actions = {self.player.id: action}
        for lab in self.state.labs:
            if lab.is_player:
                continue
            if is_first_turn:
                actions[lab.id] = Action()
            else:
                actions[lab.id] = self.rival_ctrl.decide(
                    self.observations[lab.id], lab.disposition)
        self.state, self.observations = self.engine.step(self.state, actions)
        return self.state_payload()

    def state_payload(self):
        return {"observation": self.player_observation().to_dict(),
                "caps_history": self.caps_history(),
                "lab_names": self.lab_names()}

    def postmortem(self):
        if not self.state.game_over:
            return {"errors": ["game is not over"]}
        return build_postmortem(self.engine.logger, self.state, self.player.id, resim=True)


SESSION = Session()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):   # quiet
        pass

    def _json(self, payload, code=200):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode())

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            index_path = os.path.join(FRONTEND_DIR, "index.html")
            try:
                with open(index_path, "rb") as f:
                    html_body = f.read()
            except OSError:
                self._json({"errors": ["frontend not found"]}, 404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html_body)))
            self.end_headers()
            self.wfile.write(html_body)
        elif self.path == "/api/state":
            self._json(SESSION.state_payload())
        elif self.path == "/api/postmortem":
            self._json(SESSION.postmortem())
        else:
            self._json({"errors": ["not found"]}, 404)

    def do_POST(self):
        global SESSION
        try:
            body = self._read_body()
        except (json.JSONDecodeError, ValueError) as e:
            self._json({"errors": [f"bad JSON: {e}"]}, 400)
            return
        if self.path == "/api/new":
            try:
                SESSION = Session(
                    seed=int(body.get("seed", 0)),
                    difficulty=body.get("difficulty", "realistic"),
                    guidance=body.get("guidance", "standard"),
                    rivals=body.get("rivals"),
                    max_turns=body.get("max_turns"))
            except ValueError as e:
                self._json({"errors": [str(e)]}, 400)
                return
            self._json(SESSION.state_payload())
        elif self.path == "/api/action":
            result = SESSION.submit(body.get("action", {}))
            status_code = 200 if "errors" not in result else 422
            self._json(result, status_code)
        else:
            self._json({"errors": ["not found"]}, 404)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"serving on http://127.0.0.1:{args.port}  (Ctrl-C to stop)")
    server.serve_forever()


if __name__ == "__main__":
    main()
