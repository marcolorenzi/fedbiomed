# This file is originally part of Fed-BioMed
# SPDX-License-Identifier: Apache-2.0

"""Researcher-side helpers for federated unlearning planning."""

from typing import Dict, List, Optional

from fedbiomed.common.constants import ErrorNumbers
from fedbiomed.common.exceptions import FedbiomedExperimentError
from fedbiomed.common.logger import logger
from fedbiomed.common.message import UnlearnRequest
from fedbiomed.researcher.requests import MessagesByNode


class UnlearningManager:
    """Provides planning and request dispatch scaffolding for unlearning workflows.

    This class currently supports:
      - dry-run plan generation (researcher-side)
      - node request dispatch for dry-run and non-dry-run modes

    Actual SIFU parameter update execution on researcher/model weights is introduced
    in a follow-up iteration.
    """

    def __init__(self, experiment) -> None:
        self._experiment = experiment

    def _validate_inputs(
        self,
        node_ids: List[str],
        from_round: Optional[int],
        mode: str,
    ) -> None:
        if not isinstance(node_ids, list) or not node_ids or not all(
            isinstance(node_id, str) for node_id in node_ids
        ):
            raise FedbiomedExperimentError(
                ErrorNumbers.FB410.value
                + ": `node_ids` must be a non-empty list of node identifiers"
            )

        if from_round is not None and (
            not isinstance(from_round, int) or from_round < 0
        ):
            raise FedbiomedExperimentError(
                ErrorNumbers.FB410.value
                + ": `from_round` must be `None` or a non-negative int"
            )

        if not isinstance(mode, str) or not mode:
            raise FedbiomedExperimentError(
                ErrorNumbers.FB410.value + ": `mode` must be a non-empty string"
            )

    def plan_unlearning(
        self,
        node_ids: List[str],
        from_round: Optional[int] = None,
        mode: str = "sifu",
    ) -> Dict:
        """Builds a dry-run unlearning plan."""

        self._validate_inputs(node_ids=node_ids, from_round=from_round, mode=mode)

        known_nodes = set(self._experiment.filtered_federation_nodes())
        unknown_nodes = [node_id for node_id in node_ids if node_id not in known_nodes]

        start_round = from_round if from_round is not None else 0
        end_round = max(self._experiment.round_current() - 1, -1)
        planned_rounds = max(0, end_round - start_round + 1)

        secagg_active = self._experiment.secagg.active
        constraints = []
        if secagg_active:
            constraints.append(
                "secure aggregation is enabled; exact per-node unlearning may be unavailable"
            )

        if unknown_nodes:
            constraints.append("one or more requested nodes are not in current federation")

        return {
            "status": "dry-run",
            "mode": mode,
            "forget_node_ids": node_ids,
            "unknown_node_ids": unknown_nodes,
            "from_round": start_round,
            "to_round": end_round,
            "planned_rounds": planned_rounds,
            "round_current": self._experiment.round_current(),
            "round_limit": self._experiment.round_limit(),
            "secagg_active": secagg_active,
            "constraints": constraints,
            "eligible": len(unknown_nodes) == 0,
        }

    def _send_unlearning_requests(
        self,
        forget_node_ids: List[str],
        mode: str,
        dry_run: bool,
        from_round: Optional[int],
        to_round: Optional[int],
    ) -> Dict:
        """Sends unlearning requests to selected nodes and returns replies/errors."""

        target_nodes = self._experiment.filtered_federation_nodes()
        if len(target_nodes) == 0:
            raise FedbiomedExperimentError(
                ErrorNumbers.FB411.value
                + ": missing node(s) required for unlearning request dispatch"
            )

        messages = MessagesByNode()
        for node_id in target_nodes:
            messages[node_id] = UnlearnRequest(
                researcher_id=self._experiment.researcher_id,
                experiment_id=self._experiment._experiment_id,
                forget_node_ids=forget_node_ids,
                mode=mode,
                dry_run=dry_run,
                from_round=from_round,
                to_round=to_round,
            )

        with self._experiment.requests.send(messages, target_nodes, None) as federated_req:
            errors = federated_req.errors()
            replies = federated_req.replies()

        for node_id, error in errors.items():
            logger.warning(
                "Error message received during unlearning request for "
                f"node={node_id}: {error.errnum}. {error.extra_msg}"
            )

        return {
            "sent_to_nodes": target_nodes,
            "errors": {node_id: err.get_dict() for node_id, err in errors.items()},
            "replies": {node_id: reply.get_dict() for node_id, reply in replies.items()},
        }

    def unlearn(
        self,
        node_ids: List[str],
        from_round: Optional[int] = None,
        mode: str = "sifu",
        dry_run: bool = True,
    ) -> Dict:
        """Runs (or plans) federated unlearning.

        Returns:
            A dictionary containing the unlearning plan and node replies.
        """

        plan = self.plan_unlearning(node_ids=node_ids, from_round=from_round, mode=mode)

        request_result = self._send_unlearning_requests(
            forget_node_ids=node_ids,
            mode=mode,
            dry_run=dry_run,
            from_round=plan["from_round"],
            to_round=plan["to_round"],
        )

        return {
            "plan": plan,
            "request": {
                "dry_run": dry_run,
                "sent_to_nodes": request_result["sent_to_nodes"],
            },
            "errors": request_result["errors"],
            "replies": request_result["replies"],
        }
