# v0.11.0 Benchmark Evaluation & Regression Layer Design

## 1. Goal and Isolation Boundary

v0.11.0 adds an independent, synchronous, offline, deterministic external
observer under `embedded_copilot.benchmark`:

```text
Synthetic BenchmarkDataset
  -> BenchmarkRunner
  -> Explicitly Injected Targets
  -> TraceCollector
  -> BenchmarkEvaluator
  -> BenchmarkReportBuilder
  -> BenchmarkReport
  -> BenchmarkBaseline / RegressionComparator
```

Benchmark only invokes, observes, and scores caller-owned targets. It never
creates or changes an Agent, calls Supervisor from an Agent, registers with
`AgentRegistry`, changes Supervisor routing, or enters a production execution
path. It does not add a Runtime Agent, LangGraph node, API route, Tool, network
client, LLM judge, training-data generator, model optimizer, filesystem scanner,
or Retriever implementation.

`import embedded_copilot.benchmark` exports only `BenchmarkRunner`. Importing
the package does not import or initialize Runtime Agents, LangGraph Workflow,
API modules, production Registries, targets, datasets, capability registration,
or the reserved CLI. Target contracts and domain output models are imported
only inside an explicit run or evaluation call. No global Runner, Dataset,
Evaluator, Registry, or target is created.

## 2. Models and Dataset

All public models inherit `ContractModel`, remain frozen, forbid extra fields,
strip contract strings, reject non-finite values, stably deduplicate string
lists case-insensitively, and isolate nested mutable values through validation
and deep copies:

- `BenchmarkCase`, `BenchmarkResult`, `BenchmarkReport`
- `TraceEvent`, `BenchmarkTrace`, `ExecutionMetrics`
- `BenchmarkBaseline`, `RegressionReport`

Result scores and report metrics are in `[0, 1]`. A successful result has no
errors; a failed result has at least one fixed safe error. Reports validate
case counts, unique case IDs, result outcomes, and the calculated average.

`BenchmarkDataset` preserves insertion order and exposes `from_json`,
`add_case`, `list_cases`, and `get_case`. JSON strings and bytes are data, never
paths. Dataset operations do not read or scan the filesystem. Duplicate IDs
are rejected case-insensitively, and stored cases cannot be changed through a
returned nested object.

`benchmark.datasets.synthetic` provides explicit Python fixtures for routing,
firmware, hardware, pcb, debug, knowledge, and end-to-end evaluation. Fixtures
contain only synthetic requests and expectations: no real document, source
code, device log, private information, credential, machine path, or online
derived content.

## 3. Runner and Trace

```python
BenchmarkRunner(
    targets,
    evaluator=None,
    trace_collector=None,
    report_builder=None,
)
```

Targets are explicitly injected. Categories map to `SupervisorAgent`,
`FirmwareAgent`, `HardwareAgent`, `PCBAgent`, `DebugAgent`, or
`KnowledgeGateway`. Agent calls receive a new deep-copied `AgentTask` with
`task_id="benchmark:<case.id>"`; knowledge calls receive a revalidated
`KnowledgeQuery`. The Runner never constructs one of those targets.

Cases run sequentially, without concurrency, retry, or duplicate execution.
A missing target, target exception, failed envelope, malformed output, invalid
expected contract, or evaluator failure becomes a score-zero safe result and
does not stop later cases. An empty/malformed Dataset or report assembly
failure rejects the run without returning a partial report.

`TraceCollector` uses an injectable monotonic clock. It observes Supervisor
call order and statuses from returned `supervisor_plan.tasks` and
`agent_results`, and derives handoffs between adjacent tasks. A handoff success
means only that both returned adjacent results are successful; it does not claim
an internal state mutation occurred. Non-Supervisor Agents produce one call
event, and KnowledgeGateway produces one knowledge-call event.

`ExecutionMetrics` records execution time, Agent call count, and knowledge call
count. Raw Trace and timing never enter BenchmarkReport, preserving repeatable
reports and hashes. Token metrics are not collected.

## 4. Deterministic Evaluation and Reporting

Expected dictionaries reject missing and extra fields:

| Category | Exact fields | Metrics |
|---|---|---|
| routing | `agents`, `capabilities` | Agent selection, capability coverage |
| firmware | `platform`, `components`, `templates` | Platform/component/template |
| hardware | `component_keywords`, `interfaces`, `constraint_keywords` | Component/interface/constraint |
| pcb | `rules`, `issue_ids`, `severities` | Rule/issue/severity |
| debug | `error_type`, `finding_ids`, `recommendation_keywords` | Error type/finding/recommendation |
| knowledge | `ranked_ids`, `sources` | Hit/source/ranking/Recall@K/MRR |
| end_to_end | `agents`, `capabilities` | Selection/capability/completion/handoff |

All comparisons strip strings and compare case-insensitively. Recall@K uses
`K=len(expected.ranked_ids)`, and MRR is the reciprocal rank of the first
expected hit. A category score is the equal-weight mean of its emitted metrics;
a case passes only when execution is valid and every metric is exactly `1.0`.

`CapabilityCoverageMetric` maps `firmware`, `hardware`, `pcb`, and `debug` to
their Foundation Agent names. It returns matched required capabilities divided
by required capabilities. Empty or unknown required capability chains fail
validation; this metric measures coverage, not order.

Report metrics average each metric only across cases that emit it, then add
`pass_rate`. Result metadata contains only `category` and `target_name`; Report
metadata contains only `evaluation_mode`, `category_counts`, and
`trace_enabled`. Inputs, raw target outputs, generated code, debug logs,
knowledge content, tracebacks, secrets, machine paths, and raw exceptions never
enter results or reports.

## 5. Baseline, Capability, CLI, and Release

`BenchmarkBaseline` contains `benchmark_version`,
`evaluated_project_version`, `schema_version`, `report_hash`, `metrics_hash`,
and the metric snapshot. `CURRENT_BASELINE_SCHEMA_VERSION` starts at `1`.
Canonical, sorted compact JSON is hashed with SHA-256. `report_hash` covers the
whole Report; `metrics_hash` covers report metrics plus average score.

Regression compares the union of baseline/current metrics with missing values
treated as zero. A delta below `-1e-12` is a regression and a delta above
`1e-12` is an improvement. A baseline whose schema version differs from the
current constant is rejected with a safe error; no implicit migration occurs.

`BenchmarkCapabilityDescriptor` advertises BenchmarkRunner and the five Agent
target names. Registration is explicit and writes only the caller's
`CapabilityRegistry`; it never accepts or writes `AgentRegistry`.

`python -m embedded_copilot.benchmark.run` is a reserved boundary. The v0.11.0
module has no import effect and returns status `2` with a fixed not-implemented
message. It defines no Dataset I/O and adds no dependency.

Tests cover all category metrics, model and Dataset invariants, mutation
isolation, sequential execution, single invocation, failure continuation,
Trace order, Baseline hashes and schema invalidation, report aggregation,
Capability conflicts, CLI behavior, import isolation, and sensitive-data
redaction. Version literals move together to `0.11.0`. Release requires focused
and full pytest, compileall, Ruff, independent review, scope and artifact audit,
staged diff validation, commit, annotated tag, and push. Any failed gate stops
the release.
