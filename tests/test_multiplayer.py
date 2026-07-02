"""Headless multiplayer tests (MULTIPLAYER_DESIGN §10) — drives
backend_v1.server.multiplayer directly, no HTTP.

Covers: the turn barrier, lazy timer + budget-trim at forced resolution, the
per-seat firewall (forbidden KEYS + staged-action privacy, per the CLAUDE.md §8
audit-by-key gotcha), lobby-payload metadata shape, the endgame race /
shared-loss outcomes, kick + token revocation, and cross-game isolation.

The wall clock is injected (MultiplayerGame's now_fn), so timer expiry is
driven by a FakeClock — no sleeping, fully deterministic scheduling. The world
seed is fixed per game; multiplayer is otherwise non-replayable by design.
"""
import unittest

from backend_v1.server import multiplayer
from backend_v1.engine import turn_pipeline
from backend_v1.engine.events.event import FiredEvent
from backend_v1.engine.game import new_multiplayer_game

from tests.test_observation_firewall import _forbidden_keys_in

EMPTY_ACTION = {}

# Every key a lobby/barrier seat entry may carry (design §6, L4): metadata only.
ALLOWED_SEAT_STATUS_KEYS = {
    "seat_id", "name", "ticker", "lab_id", "is_creator",
    "connected", "submitted", "control", "is_you",
}


class FakeClock:
    def __init__(self, start=1000.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def three_seat_game(turn_seconds=None, rival_count=2, max_turns=40, seed=7):
    """A started 3-human game (creator Alpha + joiners Beta/Gamma)."""
    multiplayer.reset_registry_for_tests()
    clock = FakeClock()
    creator_token, game, creator = multiplayer.create_game(
        "Alpha Lab", "ALP", now_fn=clock)
    beta_token, _, beta = multiplayer.join_game(game.code, "Beta Lab", "BET")
    gamma_token, _, gamma = multiplayer.join_game(game.code, "Gamma Lab", "GAM")
    game.set_settings(rival_count=rival_count, turn_seconds=turn_seconds)
    game.start(seed=seed, max_turns=max_turns)
    seats = {"creator": (creator_token, creator),
             "beta": (beta_token, beta),
             "gamma": (gamma_token, gamma)}
    return clock, game, seats


class BarrierTest(unittest.TestCase):

    def test_turn_resolves_only_when_every_human_has_submitted(self):
        _clock, game, seats = three_seat_game()
        _, creator = seats["creator"]
        _, beta = seats["beta"]
        _, gamma = seats["gamma"]

        payload = game.submit_seat(creator, EMPTY_ACTION)
        self.assertEqual(game.state.turn, 0)
        self.assertEqual(len(game.engine.logger.turns), 0)
        self.assertEqual(payload["mp"]["barrier"]["submitted"], 1)
        self.assertEqual(payload["mp"]["barrier"]["total"], 3)

        game.submit_seat(beta, EMPTY_ACTION)
        self.assertEqual(game.state.turn, 0)

        payload = game.submit_seat(gamma, EMPTY_ACTION)
        self.assertEqual(game.state.turn, 1)          # exactly one step
        self.assertEqual(len(game.engine.logger.turns), 1)
        # barrier reset for the next turn
        self.assertEqual(payload["mp"]["barrier"]["submitted"], 0)
        for seat in (creator, beta, gamma):
            self.assertFalse(seat.has_submitted)
            self.assertIsNone(seat.staged_action)

    def test_invalid_action_is_rejected_and_does_not_submit(self):
        _clock, game, seats = three_seat_game()
        _, creator = seats["creator"]
        over_cash = {"lobby": {"disclosure": {"stance": "for", "spend": 99999}}}
        result = game.submit_seat(creator, over_cash)
        self.assertIn("errors", result)
        self.assertFalse(creator.has_submitted)


class TimerTest(unittest.TestCase):

    def test_deadline_submits_staged_action_budget_trimmed(self):
        clock, game, seats = three_seat_game(turn_seconds=30)
        _, creator = seats["creator"]
        _, beta = seats["beta"]
        _, gamma = seats["gamma"]

        game.submit_seat(creator, EMPTY_ACTION)
        game.submit_seat(beta, EMPTY_ACTION)
        # gamma stages an over-cash queue (two 500 spends against 800 cash)
        # and never submits
        game.stage_seat(gamma, {"lobby": {
            "disclosure": {"stance": "for", "spend": 500},
            "audit_requirement": {"stance": "against", "spend": 500},
        }})
        self.assertEqual(game.state.turn, 0)

        clock.advance(31)
        game.state_payload_for(creator)    # any poll enforces the deadline
        self.assertEqual(game.state.turn, 1)

        # the trimmed staged action was played: newest lobby entry dropped
        gamma_logged = game.engine.logger.turns[0]["actions"][gamma.lab_id]
        self.assertEqual(list(gamma_logged["lobby"]), ["disclosure"])

    def test_deadline_with_nothing_staged_is_a_pass(self):
        clock, game, seats = three_seat_game(turn_seconds=30)
        _, creator = seats["creator"]
        game.submit_seat(creator, EMPTY_ACTION)
        clock.advance(31)
        game.state_payload_for(creator)
        self.assertEqual(game.state.turn, 1)
        for seat_key in ("beta", "gamma"):
            _, seat = seats[seat_key]
            logged = game.engine.logger.turns[0]["actions"][seat.lab_id]
            self.assertEqual(logged["start_projects"], [])
            self.assertEqual(logged["lobby"], {})

    def test_no_timer_means_the_barrier_waits(self):
        clock, game, seats = three_seat_game(turn_seconds=None)
        _, creator = seats["creator"]
        game.submit_seat(creator, EMPTY_ACTION)
        clock.advance(10_000)
        game.state_payload_for(creator)
        self.assertEqual(game.state.turn, 0)   # still waiting on the others


class FirewallTest(unittest.TestCase):
    """Design §10 verification: for each seat, the FULL /api/mp/state payload
    carries no forbidden TRUE-state KEY and no staged action; lobby entries
    carry exactly the allowed metadata keys (audit by KEY, CLAUDE.md §8)."""

    def test_state_payloads_are_clean_for_every_seat_every_turn(self):
        _clock, game, seats = three_seat_game()
        seat_list = [seat for _token, seat in seats.values()]
        for _turn in range(3):
            for seat in seat_list:
                payload = game.state_payload_for(seat)
                self.assertEqual(_forbidden_keys_in(payload, "payload"), [])
                # L5: nobody's staged action appears in any payload
                self.assertEqual(self._keys_named(payload, "staged_action"), [])
                # L2: a seat sees its OWN lab's observation, nobody else's
                self.assertEqual(payload["observation"]["lab_id"], seat.lab_id)
            for seat in seat_list:
                game.submit_seat(seat, EMPTY_ACTION)

    def _keys_named(self, value, forbidden_key, path="payload"):
        found = []
        if isinstance(value, dict):
            for key, sub_value in value.items():
                if key == forbidden_key:
                    found.append(f"{path}.{key}")
                found += self._keys_named(sub_value, forbidden_key,
                                          f"{path}.{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                found += self._keys_named(item, forbidden_key,
                                          f"{path}[{index}]")
        return found

    def test_lobby_payload_is_metadata_only(self):
        _clock, game, seats = three_seat_game()
        _, creator = seats["creator"]
        lobby = game.lobby_payload(creator)
        for seat_entry in lobby["seats"]:
            self.assertEqual(set(seat_entry), ALLOWED_SEAT_STATUS_KEYS)

    def test_other_humans_appear_as_fogged_rivals(self):
        _clock, game, seats = three_seat_game()
        _, creator = seats["creator"]
        _, beta = seats["beta"]
        payload = game.state_payload_for(creator)
        rival_ids = {entry["lab_id"]
                     for entry in payload["observation"]["rival_public"]}
        self.assertIn(beta.lab_id, rival_ids)         # humans are rivals to you
        self.assertNotIn(creator.lab_id, rival_ids)   # you are not your own rival


class EndgameTest(unittest.TestCase):

    def test_race_win_and_placements(self):
        _clock, game, seats = three_seat_game(max_turns=1)
        _, creator = seats["creator"]
        _, beta = seats["beta"]
        _, gamma = seats["gamma"]

        # Test-only godmode: hand beta a dominant, high-impact position so the
        # single allowed turn ends the game with a clear winner.
        beta_lab = next(l for l in game.state.labs if l.id == beta.lab_id)
        beta_lab.market_cap = 10_000.0
        beta_lab.impact_ledger = game.state.consts.IMPACT_WIN_BAR + 50.0

        for seat in (creator, beta, gamma):
            game.submit_seat(seat, EMPTY_ACTION)
        self.assertTrue(game.state.game_over)

        outcomes = game.state.outcome_by_lab
        self.assertEqual(outcomes[beta.lab_id]["result"], "WIN")
        self.assertEqual(outcomes[creator.lab_id]["result"], "LOSS")
        self.assertEqual(outcomes[gamma.lab_id]["result"], "LOSS")

        # each seat's observation carries its OWN verdict
        creator_payload = game.state_payload_for(creator)
        beta_payload = game.state_payload_for(beta)
        self.assertEqual(creator_payload["observation"]["outcome"]["result"],
                         "LOSS")
        self.assertEqual(beta_payload["observation"]["outcome"]["result"],
                         "WIN")

        # post-mortem: per-seat outcome + shared leaderboard, winner first
        postmortem = game.postmortem_for(beta)
        self.assertEqual(postmortem["outcome"]["result"], "WIN")
        self.assertEqual(postmortem["leaderboard"][0]["lab_id"], beta.lab_id)
        human_count = sum(1 for entry in postmortem["leaderboard"]
                          if entry["is_human"])
        self.assertEqual(human_count, 3)

    def test_existential_catastrophe_is_a_shared_loss(self):
        # Unit-level on _finish: every human's outcome is an existential LOSS.
        state = new_multiplayer_game(
            seed=3, human_identities=[("A", "A"), ("B", "B")], rival_count=1)
        cause = FiredEvent("asi_exfiltration", "misalignment", "existential",
                           turn=5, lab_id="player2", model_id="m",
                           severity=1.0, impact=0.0,
                           public_text="", true_text="it got out")
        turn_pipeline._finish(state, existential=True, cause=cause)
        self.assertTrue(state.game_over)
        for human_lab_id in ("player1", "player2"):
            outcome = state.outcome_by_lab[human_lab_id]
            self.assertEqual(outcome["result"], "LOSS")
            self.assertTrue(outcome["existential"])

    def test_postmortem_is_gated_until_the_shared_game_ends(self):
        _clock, game, seats = three_seat_game()
        _, creator = seats["creator"]
        result = game.postmortem_for(creator)
        self.assertIn("errors", result)


class AdminTest(unittest.TestCase):

    def test_kick_auto_pass_revokes_token_and_releases_the_barrier(self):
        _clock, game, seats = three_seat_game()
        _, creator = seats["creator"]
        _, beta = seats["beta"]
        gamma_token, gamma = seats["gamma"]

        game.submit_seat(creator, EMPTY_ACTION)
        game.submit_seat(beta, EMPTY_ACTION)
        self.assertEqual(game.state.turn, 0)   # gamma holds the barrier

        result, revoked_token = game.kick(gamma.seat_id,
                                          resolution="auto_pass")
        multiplayer.revoke_token(revoked_token)
        self.assertNotIn("errors", result)
        self.assertEqual(game.state.turn, 1)   # barrier released
        self.assertEqual(gamma.control, "auto_pass")
        self.assertIsNone(multiplayer.lookup_seat(gamma_token))  # 401 path

    def test_kick_replace_with_ai_gives_the_lab_a_real_disposition(self):
        _clock, game, seats = three_seat_game()
        _, creator = seats["creator"]
        _, beta = seats["beta"]
        _, gamma = seats["gamma"]

        result, revoked_token = game.kick(gamma.seat_id, resolution="ai")
        multiplayer.revoke_token(revoked_token)
        self.assertNotIn("errors", result)
        self.assertEqual(gamma.control, "ai")
        gamma_lab = next(l for l in game.state.labs if l.id == gamma.lab_id)
        self.assertEqual(gamma_lab.disposition.recklessness,
                         multiplayer.TAKEOVER_RECKLESSNESS)
        self.assertTrue(gamma_lab.is_player)   # keeps buyout immunity etc.

        # the takeover plays via the rival controller; two humans now barrier
        game.submit_seat(creator, EMPTY_ACTION)
        game.submit_seat(beta, EMPTY_ACTION)
        self.assertEqual(game.state.turn, 1)
        self.assertIn(gamma.lab_id, game.engine.logger.turns[0]["actions"])

    def test_creator_cannot_be_kicked(self):
        _clock, game, seats = three_seat_game()
        _, creator = seats["creator"]
        result, revoked_token = game.kick(creator.seat_id)
        self.assertIn("errors", result)
        self.assertIsNone(revoked_token)

    def test_lobby_kick_removes_the_seat_before_start(self):
        multiplayer.reset_registry_for_tests()
        _token, game, _creator = multiplayer.create_game("Alpha", "ALP")
        beta_token, _, beta = multiplayer.join_game(game.code, "Beta", "BET")
        result, revoked_token = game.kick(beta.seat_id)
        multiplayer.revoke_token(revoked_token)
        self.assertNotIn("errors", result)
        self.assertEqual(len(game.seats), 1)
        self.assertIsNone(multiplayer.lookup_seat(beta_token))


class RegistryTest(unittest.TestCase):

    def test_tokens_resolve_to_exactly_their_own_game(self):
        multiplayer.reset_registry_for_tests()
        token_a, game_a, _ = multiplayer.create_game("A", "A")
        token_b, game_b, _ = multiplayer.create_game("B", "B")
        self.assertIsNot(game_a, game_b)
        self.assertIs(multiplayer.lookup_seat(token_a)[0], game_a)
        self.assertIs(multiplayer.lookup_seat(token_b)[0], game_b)
        self.assertIsNone(multiplayer.lookup_seat("forged-token"))

    def test_join_rejects_unknown_started_and_full_games(self):
        multiplayer.reset_registry_for_tests()
        _token, game, _creator = multiplayer.create_game("A", "A")

        _, _, error = multiplayer.join_game("ZZZZZZ", "X", "X")
        self.assertEqual(error["status"], 404)

        for i in range(multiplayer.MAX_SEATS - 1):
            multiplayer.join_game(game.code, f"J{i}", f"J{i}")
        _, _, error = multiplayer.join_game(game.code, "Late", "LTE")
        self.assertEqual(error["status"], 409)   # full

        multiplayer.reset_registry_for_tests()
        _token, game, _creator = multiplayer.create_game("A", "A")
        game.start(seed=1, max_turns=5)
        _, _, error = multiplayer.join_game(game.code, "Late", "LTE")
        self.assertEqual(error["status"], 409)   # already started


if __name__ == "__main__":
    unittest.main()
