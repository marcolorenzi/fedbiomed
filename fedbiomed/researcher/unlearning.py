# This file is originally part of Fed-BioMed
# SPDX-License-Identifier: Apache-2.0

"""Researcher-side helpers for federated unlearning planning."""

from typing import Dict, List, Optional

from fedbiomed.common.constants import ErrorNumbers
from fedbiomed.common.exceptions import FedbiomedExperimentError


class UnlearningManager:
    """Provides planning scaffolding for unlearning workflows.

    This class intentionally limits itself to dry-run planning and basic
    eligibility checks. Actual SIFU update execution is introduced in a
    follow-up iteration.
    """

    def __init__(self, experiment) -> None:
        self._experiment = experiment

    def plan_unlearning(
        self,
        node_ids: List[str],
        from_round: Optional[int] = None,
        mode: str = "sifu",
    ) -> Dict:
        """Builds a dry-run unlearning plan.

        Args:
            node_ids: IDs of nodes to forget.
            from_round: Earliest round to unlearn from. If None, starts from round 0.
            mode: Unlearning mode identifier.

        Returns:
            Dict describing the plan and basic constraints.

        Raises:
            FedbiomedExperimentError: for invalid inputs.
        """

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

    def unlearn(
        self,
        node_ids: List[str],
        from_round: Optional[int] = None,
        mode: str = "sifu",
        dry_run: bool = True,
    ) -> Dict:
        """Executes (or plans) unlearning.

        Current implementation supports dry-run planning only.
        """

        plan = self.plan_unlearning(node_ids=node_ids, from_round=from_round, mode=mode)

        if not dry_run:
            raise FedbiomedExperimentError(
                ErrorNumbers.FB601.value
                + ": SIFU unlearning execution is not implemented yet; use dry_run=True"
            )

        return plan
