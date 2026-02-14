# Strategy proposal: adding SIFU federated unlearning to Fed-BioMed

## Goal
Implement **federated unlearning** based on the SIFU paper so a researcher can request deletion of one (or many) nodes' contribution from a trained model, without retraining from scratch.

## Current Fed-BioMed integration points

### Researcher orchestration and aggregation
- The researcher-side round orchestration is in `Experiment.run_once` / `Experiment.run` and currently assumes a strictly forward training lifecycle (sample nodes -> send `TrainRequest` -> aggregate -> update global model).  
- Node communication is built in `TrainingJob.execute`, which serializes `TrainRequest` messages (including `state_id`, `round`, model `params`, and `aggregator_args`) and receives `TrainReply` values (including `params`, `state_id`, `sample_size`, `optimizer_args`, and optional secure-aggregation fields).  
- Aggregation is strategy-based through `Aggregator` subclasses (`FedAverage`, `Scaffold`, etc.), and there is already a hook to persist aggregator state via breakpoints.

### Node execution and state
- Nodes process researcher commands in `Node.on_message`, dispatching `TrainRequest` into the task queue.
- Node training is executed in `Round.run_model_training`, which can load the previous node optimizer state from `state_id` and save a new one at round end.
- Node-side persisted state currently focuses on optimizer/testing split state, not a complete unlearning artifact store.

### Persistence / replay capabilities already present
- Breakpoints can save and load global workflow state and aggregator state across rounds.
- The researcher keeps per-round `training_replies` and `aggregated_params` in memory (and can serialize through breakpoint helpers), which is useful for implementing reverse/replay logic.

## SIFU-aligned capability design

## 1) Unlearning as a first-class workflow
Add a dedicated unlearning workflow on top of `Experiment` instead of overloading `run`.

### Proposed API
- `Experiment.unlearn(node_ids: list[str], from_round: int | None = None, mode: str = "sifu")`
- `Experiment.plan_unlearning(...)` returning a dry-run plan/cost estimate.

### Why
This keeps normal FL training unchanged and isolates extra checks:
- eligibility checks (is round history sufficient? secure agg constraints?)
- audit metadata
- optional approximation mode vs exact mode

## 2) Researcher-side SIFU state manager
Create a component (e.g., `fedbiomed/researcher/unlearning/sifu_state.py`) that stores the minimum sufficient statistics per round required by SIFU.

### Minimal metadata to capture each round
- participating node set
- node weights/sample sizes
- pre-aggregation global model hash
- post-aggregation model hash
- optional cached deltas / compressed influence vectors

Use breakpoint serialization similar to existing aggregator state saving.

## 3) Message protocol extension for unlearning tasks
Introduce new message types in `fedbiomed/common/message.py`:
- `UnlearnRequest`
- `UnlearnReply`

Fields should include:
- `experiment_id`, `researcher_id`, `request_id`
- target `forget_node_ids`
- unlearning window (`from_round`, `to_round`)
- artifact mode (exact replay vs approximate SIFU stats)
- optional secure-aggregation compatibility flags

Then add node dispatch in `Node.on_message` and a dedicated node job (parallel to `Round` / preproc jobs).

## 4) Node-side unlearning artifact support
SIFU generally needs extra node-level information to undo influence efficiently.

### Node changes
- Add a small unlearning artifact interface to training plans / optimizers (e.g., per-round sufficient stats extraction).
- Persist artifacts per round in node state storage namespace, keyed by `(experiment_id, round, state_id)`.
- Add retention policy controls (TTL / max rounds / encryption-at-rest).

## 5) Aggregator adaptation layer
Implement a new aggregator (e.g., `SIFUAggregator`) or a mixin wrapping existing aggregators.

Responsibilities:
- compute/store per-round unlearning coefficients
- apply SIFU update rule to remove forgotten client contribution
- return updated global parameters without full retraining

Start with `FedAverage` compatibility first, then extend to `Scaffold` and others.

## 6) Secure aggregation compatibility strategy
Secure aggregation can prevent exact per-client contribution access. Support should be explicit:

- **Mode A (exact, no secagg)**: full SIFU where per-node stats are visible to researcher.
- **Mode B (secagg-compatible approximation)**: require nodes to emit additional masked/structured artifacts that remain privacy-preserving.
- **Mode C (fallback retraining)**: if required stats are unavailable, automatically produce a retraining plan from a selected checkpoint.

Gate unlearning requests with clear error codes when constraints are not met.

## 7) Auditability and governance
Add immutable unlearning records:
- who requested unlearning, when, and why/reference ticket
- target node ids / rounds
- model hash before/after unlearning
- validation metrics delta

Persist in researcher experiment metadata and optionally export as JSON report.

## Phased implementation plan

### Phase 0 — feasibility and paper mapping (1 sprint)
- map SIFU equations to FedAvg round math currently in `Experiment`
- define exact artifacts needed per round
- decide acceptable approximation path under secagg

### Phase 1 — scaffolding and protocol (1–2 sprints)
- add `UnlearnRequest/Reply`
- add researcher `UnlearningManager` + CLI hook
- add node task parser + no-op handler + end-to-end test plumbing

### Phase 2 — FedAvg SIFU MVP (2 sprints)
- capture/store per-round SIFU stats for FedAvg
- implement researcher-side unlearn update for single-node forget
- add regression tests comparing unlearned model vs full retrain baseline

### Phase 3 — hardening (1–2 sprints)
- multi-node forget
- checkpoint fallback logic
- audit report generation
- failure injection tests (missing artifacts, stale state_id, node offline)

### Phase 4 — advanced support
- partial secagg-compatible mode
- support additional aggregators / optimizers
- performance optimization (compressed stats, async artifact fetch)

## Recommended tests

### Unit tests
- message schema validation for unlearning request/reply
- SIFU math kernel correctness on synthetic vectors
- serialization/deserialization of unlearning artifacts and breakpoints

### Integration tests
- train N rounds, forget one node, compare with retrain-without-node reference (distance threshold)
- same with node dropout and stale state
- CLI/API flow from unlearning request to updated global model

### Security tests
- unauthorized requester cannot trigger unlearning
- no leakage of raw per-sample data in artifacts
- secure-aggregation mode enforces capability constraints

## Practical next steps for your new branch
1. Start from branch `feature/sifu-unlearning-strategy` (created).
2. Add protocol scaffolding (`UnlearnRequest/Reply`) and node dispatch stubs.
3. Add researcher `UnlearningManager` with dry-run planning only.
4. Add a benchmark script reproducing a tiny FedAvg run + forget-one-node comparison.
5. Iterate towards exact SIFU update once artifact schema is stable.

