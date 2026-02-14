# This file is originally part of Fed-BioMed
# SPDX-License-Identifier: Apache-2.0

"""Implementation of researcher-side unlearning request job."""

from typing import Dict

from fedbiomed.common.logger import logger
from fedbiomed.common.message import ErrorMessage, UnlearnReply, UnlearnRequest
from fedbiomed.researcher.requests import MessagesByNode

from ._job import Job


class UnlearningRequestJob(Job):
    """Send an unlearning request to selected nodes and collect replies."""

    def __init__(
        self,
        experiment_id: str,
        forget_node_ids: list[str],
        from_round: int | None,
        to_round: int | None,
        mode: str,
        dry_run: bool,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._experiment_id = experiment_id
        self._forget_node_ids = forget_node_ids
        self._from_round = from_round
        self._to_round = to_round
        self._mode = mode
        self._dry_run = dry_run

    def execute(self) -> Dict[str, UnlearnReply]:
        """Executes unlearning request and returns node-wise replies."""

        messages = MessagesByNode()
        for node in self._nodes:
            messages[node] = UnlearnRequest(
                researcher_id=self._researcher_id,
                experiment_id=self._experiment_id,
                forget_node_ids=self._forget_node_ids,
                mode=self._mode,
                dry_run=self._dry_run,
                from_round=self._from_round,
                to_round=self._to_round,
            )

        with self._reqs.send(messages, self._nodes, self._policies) as federated_req:
            errors: Dict[str, ErrorMessage] = federated_req.errors()
            replies: Dict[str, UnlearnReply] = federated_req.replies()

        for node_id, error in errors.items():
            logger.warning(
                "Error message received during unlearning request: "
                f"{error.errnum}. {error.extra_msg}"
            )

        return replies
