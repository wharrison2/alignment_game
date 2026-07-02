"""trim_action_to_budget (MULTIPLAYER_DESIGN §4.4) — the forced-resolution
trimmer that runs when a multiplayer turn timer expires on a non-submitted
seat. It GREEDILY REBUILDS the action from empty, keeping each staged entry
only if the whole action still validates. Contract under test:

  1. an individually invalid/stale entry is dropped WITHOUT costing any valid
     entry in another field;
  2. when the budget binds, entries fall off newest-first within a field
     (re-added oldest-first), and projects have the lowest cross-field
     priority (re-added last);
  3. the result always passes validate_action (floor: an empty pass);
  4. the caller's Action is never mutated;
  5. never raises, even on malformed entries inside well-typed fields.

Runs on a real new_game state so validate_action sees genuine budgets:
pool = 1.0 work-budget, cash = 800 at seed 1 (asserted below so a constants
change fails loudly here rather than silently weakening the test).
"""
import unittest

from backend_v1.engine.actions import Action, trim_action_to_budget, validate_action
from backend_v1.engine.game import new_game
from backend_v1.engine.rules import budget_pool


def _fresh_lab_and_state():
    state = new_game(seed=1)
    player_lab = state.labs[0]
    return player_lab, state


# Root capability projects (no prereqs), budget fractions 0.25/0.3/0.2/0.2.
ROOT_PROJECTS = ["generative_pretraining", "rlhf", "dev_tooling", "serving_infra"]


def _project_entries(project_ids):
    return [{"project_id": pid, "ai_assist": 0.0} for pid in project_ids]


class TrimActionToBudgetTest(unittest.TestCase):

    def setUp(self):
        self.lab, self.state = _fresh_lab_and_state()
        # The scenarios below are calibrated to these scales; if a constants
        # change moves them, recalibrate the test rather than trust it silently.
        self.assertAlmostEqual(budget_pool(self.lab, self.state.dt), 1.0)
        self.assertAlmostEqual(self.lab.cash, 800.0)

    def _trim(self, action):
        return trim_action_to_budget(action, self.lab, self.state.world,
                                     self.state.consts, self.state.dt)

    def assert_valid(self, action):
        problems = validate_action(action, self.lab, self.state.world,
                                   self.state.consts, self.state.dt)
        self.assertEqual(problems, [])

    def test_work_budget_overrun_pops_newest_project_only(self):
        # All four roots fit (0.95 of 1.0); a duplicate fifth entry overruns.
        overrun = Action(start_projects=_project_entries(
            ROOT_PROJECTS + ["generative_pretraining"]))
        trimmed = self._trim(overrun)
        remaining_ids = [spec["project_id"] for spec in trimmed.start_projects]
        self.assertEqual(remaining_ids, ROOT_PROJECTS)   # newest (the dup) dropped
        self.assert_valid(trimmed)

    def test_cash_overrun_drops_last_inserted_lobby_entry(self):
        overrun = Action(lobby={
            "disclosure": {"stance": "for", "spend": 500},
            "audit_requirement": {"stance": "against", "spend": 500},
        })
        trimmed = self._trim(overrun)
        self.assertEqual(list(trimmed.lobby), ["disclosure"])   # last key dropped
        self.assert_valid(trimmed)

    def test_budget_overrun_keeps_every_entry_that_fits(self):
        # Cash: lobby is re-added first (disclosure fits, audit would overrun);
        # the projects (re-added last) all still fit both cash and work budget
        # except the duplicated fifth entry. Nothing valid is sacrificed.
        overrun = Action(
            start_projects=_project_entries(
                ROOT_PROJECTS + ["generative_pretraining"]),
            lobby={
                "disclosure": {"stance": "for", "spend": 500},
                "audit_requirement": {"stance": "against", "spend": 500},
            },
        )
        trimmed = self._trim(overrun)
        self.assertEqual([spec["project_id"] for spec in trimmed.start_projects],
                         ROOT_PROJECTS)
        self.assertEqual(list(trimmed.lobby), ["disclosure"])
        self.assert_valid(trimmed)

    def test_stale_entry_does_not_cost_valid_entries(self):
        # The pre-greedy trimmer shed whole categories until validation passed,
        # so one stale post_train (no model in training) destroyed every queued
        # project. Now the stale entry alone is dropped.
        stale_plus_valid = Action(
            start_projects=_project_entries(ROOT_PROJECTS),
            post_train={"applied_safety": []},   # stale: no model in training
        )
        trimmed = self._trim(stale_plus_valid)
        self.assertIsNone(trimmed.post_train)
        self.assertEqual([spec["project_id"] for spec in trimmed.start_projects],
                         ROOT_PROJECTS)
        self.assert_valid(trimmed)

    def test_malformed_entry_is_dropped_without_raising(self):
        # Field TYPES are guaranteed by Action.from_dict, but an ENTRY inside a
        # well-typed field can still be garbage; it must be skipped, not crash
        # the forced resolution.
        garbage_entry = Action(
            start_projects=["not-a-dict"] + _project_entries(["rlhf"]),
            litigation={"disclosure": "not-a-dict"},
        )
        trimmed = self._trim(garbage_entry)
        self.assertEqual([spec["project_id"] for spec in trimmed.start_projects],
                         ["rlhf"])   # the garbage entry itself was dropped
        self.assertEqual(trimmed.litigation, {})
        self.assert_valid(trimmed)

    def test_invalid_scalar_entries_trim_to_a_valid_pass(self):
        # release with no model in training and a defect on an unknown policy:
        # both are stale/invalid, both must be shed, ending on a valid action.
        stale = Action(release=True, defect={"no_such_policy": True})
        trimmed = self._trim(stale)
        self.assertFalse(trimmed.release)
        self.assertEqual(trimmed.defect, {})
        self.assert_valid(trimmed)

    def test_input_action_is_not_mutated(self):
        original = Action(
            start_projects=_project_entries(
                ROOT_PROJECTS + ["generative_pretraining"]),
            lobby={"disclosure": {"stance": "for", "spend": 500},
                   "audit_requirement": {"stance": "against", "spend": 500}},
            release=True,
        )
        untrimmed_ids = [spec["project_id"] for spec in original.start_projects]
        self._trim(original)
        self.assertEqual([spec["project_id"] for spec in original.start_projects],
                         untrimmed_ids)
        self.assertEqual(list(original.lobby),
                         ["disclosure", "audit_requirement"])
        self.assertTrue(original.release)

    def test_valid_action_returned_unchanged(self):
        fits = Action(start_projects=_project_entries(["rlhf"]),
                      lobby={"disclosure": {"stance": "for", "spend": 100}})
        trimmed = self._trim(fits)
        self.assertEqual([s["project_id"] for s in trimmed.start_projects],
                         ["rlhf"])
        self.assertEqual(list(trimmed.lobby), ["disclosure"])
        self.assert_valid(trimmed)


if __name__ == "__main__":
    unittest.main()
