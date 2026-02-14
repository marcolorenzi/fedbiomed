import unittest
from unittest.mock import MagicMock, patch

from fedbiomed.common.exceptions import FedbiomedExperimentError
from fedbiomed.researcher.unlearning import UnlearningManager


class DummySecagg:
    active = False


class DummyExperiment:
    def __init__(self):
        self.secagg = DummySecagg()
        self.researcher_id = "researcher-id"
        self.requests = MagicMock()
        self._experiment_id = "exp-id"

    def filtered_federation_nodes(self):
        return ["node-1", "node-2"]

    def round_current(self):
        return 3

    def round_limit(self):
        return 10


class TestUnlearningManager(unittest.TestCase):
    def setUp(self):
        self.experiment = DummyExperiment()
        self.manager = UnlearningManager(self.experiment)

    def test_plan_unlearning(self):
        plan = self.manager.plan_unlearning(["node-1"], from_round=1, mode="sifu")
        self.assertEqual(plan["from_round"], 1)
        self.assertEqual(plan["to_round"], 2)
        self.assertTrue(plan["eligible"])

    def test_plan_unlearning_with_unknown_node(self):
        plan = self.manager.plan_unlearning(["unknown"], from_round=0, mode="sifu")
        self.assertFalse(plan["eligible"])
        self.assertEqual(plan["unknown_node_ids"], ["unknown"])

    def test_plan_unlearning_invalid_inputs(self):
        with self.assertRaises(FedbiomedExperimentError):
            self.manager.plan_unlearning([], from_round=0, mode="sifu")

        with self.assertRaises(FedbiomedExperimentError):
            self.manager.plan_unlearning(["node-1"], from_round=-1, mode="sifu")

    @patch("fedbiomed.researcher.unlearning.UnlearningManager._send_unlearning_requests")
    def test_unlearn_dispatches_request(self, mock_send):
        mock_send.return_value = {
            "sent_to_nodes": ["node-1"],
            "errors": {},
            "replies": {"node-1": {"success": True}},
        }

        result = self.manager.unlearn(["node-1"], from_round=0, mode="sifu", dry_run=True)
        self.assertIn("plan", result)
        self.assertIn("replies", result)
        self.assertIn("node-1", result["replies"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
