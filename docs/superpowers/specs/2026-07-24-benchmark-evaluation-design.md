# v0.11.0 Benchmark Evaluation Layer Design

## 1. Goal and Boundaries

v0.11.0 adds an independent, synchronous, deterministic evaluation layer under
`embedded_copilot.benchmark`:

```text
BenchmarkDataset
  -> BenchmarkRunner
  -> Supervisor / Foundation Domain Agent / KnowledgeGateway
  -> BenchmarkEvaluator
  -> BenchmarkReportBuilder
  -> BenchmarkReport
```

The layer evaluates existing Foundation behavior without changing the evaluated
components. It does not modify FirmwareAgent, HardwareAgent, PCBAgent,
DebugAgent, SupervisorAgent, or KnowledgeGateway. It does not add a Runtime
Agent, LangGraph node, API route, Web UI, LLM judge, online dataset, training
data generator, model optimizer, filesystem scanner, or network client.

The package exports `BenchmarkRunner` from `embedded_copilot.benchmark`. It
does not create `embedded_copilot.agents.benchmark` and does not auto-register
anything on import.

## 2. Public Contracts

All public models inherit `ContractModel`, remain frozen, forbid extra fields,
strip string fields, stably deduplicate string lists case-insensitively, reject
NaN/Inf, and isolate nested mutable values through revalidation and deep copies
at every pipeline boundary.

```python
BenchmarkCategory = Literal[
    "routing",
    "firmware",
    "hardware",
    "pcb",
    "debug",
    "knowledge",
    "end_to_end",
]

class BenchmarkCase(ContractModel):
    id: str
    name: str
    category: BenchmarkCategory
    input: str
    expected: dict[str, object]
    metadata: dict[str, object]

class BenchmarkResult(ContractModel):
    case_id: str
    success: bool
    score: float
    metrics: dict[str, float]
    errors: list[str]
    metadata: dict[str, object]

class BenchmarkReport(ContractModel):
    name: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    average_score: float
    metrics: dict[str, float]
    results: list[BenchmarkResult]
    summary: str
    metadata: dict[str, object]
```

`BenchmarkResult.score` and every metric are in `[0, 1]`. A successful result
has no errors; a failed result has at least one fixed, safe error. A report
validates that `total_cases == passed_cases + failed_cases == len(results)`,
case IDs are unique case-insensitively, pass/fail counts agree with result
statuses, and `average_score` agrees with the result mean.

The exception hierarchy is `BenchmarkError` with
`BenchmarkDatasetError`, `BenchmarkRunError`, `BenchmarkEvaluationError`, and
`BenchmarkReportError` subclasses. Registration conflicts continue to use the
existing registry's `ValueError` behavior.

## 3. Dataset and Target Execution

`BenchmarkDataset` owns an insertion-ordered collection of cases:

```python
BenchmarkDataset(
    name: str,
    cases: Sequence[BenchmarkCase] = (),
)

BenchmarkDataset.from_json(
    payload: str | bytes | Mapping[str, object],
) -> BenchmarkDataset

add_case(case: BenchmarkCase) -> None
list_cases() -> list[BenchmarkCase]
get_case(case_id: str) -> BenchmarkCase
```

The JSON value has the exact top-level shape `{"name": str, "cases": list}`.
The package never interprets a string as a path and never reads or scans the
filesystem. Duplicate IDs are rejected case-insensitively. Add, list, and get
revalidate deep copies so caller mutation cannot change stored cases.

`BenchmarkRunner` uses explicit target injection and never creates an Agent or
Gateway:

```python
BenchmarkRunner(
    targets: Mapping[str, object],
    *,
    evaluator: BenchmarkEvaluator | None = None,
    report_builder: BenchmarkReportBuilder | None = None,
)

run(dataset: BenchmarkDataset) -> BenchmarkReport
```

The supported target keys are `SupervisorAgent`, `FirmwareAgent`,
`HardwareAgent`, `PCBAgent`, `DebugAgent`, and `KnowledgeGateway`. A runner may
receive only the subset needed by its dataset. Category routing is fixed:

- `routing` and `end_to_end` -> `SupervisorAgent`
- `firmware` -> `FirmwareAgent`
- `hardware` -> `HardwareAgent`
- `pcb` -> `PCBAgent`
- `debug` -> `DebugAgent`
- `knowledge` -> `KnowledgeGateway`

Agent targets receive a new deep-copied `AgentTask` with task ID
`benchmark:<case.id>`, task type equal to the category, requirement equal to
`case.input`, and metadata copied from the case. Knowledge targets receive a
`KnowledgeQuery`; `sources` and `top_k` are optional reserved metadata keys and
all remaining metadata becomes query metadata.

Cases execute sequentially in dataset order. Target input, returned output,
case data, and stored dataset state are revalidated and isolated. A missing
target, target exception, `AgentStatus.ERROR`, malformed result, invalid
expected contract, or evaluator exception produces a score-zero failed
`BenchmarkResult` and does not stop later cases. Running an empty or malformed
dataset, or failing to assemble a valid report, raises a safe benchmark
exception and does not return a partial report.

The runner does not execute a case twice. Determinism means repeated runs over
the same immutable dataset and deterministic injected targets produce identical
reports; tests enforce that contract.

## 4. Deterministic Evaluation

`BenchmarkEvaluator.evaluate(case: BenchmarkCase, result: object) ->
BenchmarkResult` selects a category evaluator and first revalidates the target
envelope and typed domain output. Category-specific `expected` dictionaries
forbid missing and extra keys:

| Category | Exact expected fields | Metrics |
|---|---|---|
| `routing` | `agents: list[str]` | `agent_selection_accuracy` is 1 only when the SupervisorPlan task Agent set exactly matches the expected set |
| `firmware` | `platform: str`, `components: list[str]`, `templates: list[str]` | `platform_accuracy`; `component_coverage` over `FirmwareProject.metadata.components + peripherals`; `template_coverage` over file paths |
| `hardware` | `component_keywords: list[str]`, `interfaces: list[str]`, `constraint_keywords: list[str]` | keyword coverage over component names; exact interface coverage; keyword coverage over constraints |
| `pcb` | `rules: list[str]`, `issue_ids: list[str]`, `severities: dict[str, str]` | rule coverage over passed rules and issue IDs; issue coverage; expected issue severity accuracy |
| `debug` | `error_type: str`, `finding_ids: list[str]`, `recommendation_keywords: list[str]` | exact error type accuracy; finding ID coverage; recommendation keyword coverage |
| `knowledge` | `ranked_ids: list[str]`, `sources: dict[str, str]` | retrieval hit rate; expected source accuracy; same-position ranking accuracy |
| `end_to_end` | `agents: list[str]` | exact SupervisorPlan Agent selection plus expected-Agent completion coverage from SupervisorResult |

All comparisons strip strings and compare case-insensitively. Keyword checks are
deterministic substring checks. Empty optional expectation lists or mappings
score 1 because nothing is required, but routing/end-to-end Agent lists and the
knowledge ranked ID list must be non-empty.

The metric utilities expose:

```python
AccuracyMetric.compute(expected: object, actual: object) -> float
CoverageMetric.compute(
    expected: Sequence[str],
    actual: Sequence[str],
    *,
    substring: bool = False,
) -> float
PassRateMetric.compute(passed: int, total: int) -> float
ScoreAggregator.aggregate(scores: Sequence[float]) -> float
```

All metric utilities reject invalid, negative, non-finite, or above-one values.
Each category's case score is the equal-weight arithmetic mean of its fixed
metrics. A case succeeds only if target execution and output validation succeed
and every applicable metric is exactly `1.0`. Partial matches retain their
fractional score and list each below-perfect metric using a fixed error string.
Every result metadata dictionary contains only `category` and `target_name`;
it never carries the raw case, input, expected dictionary, or target output.

`BenchmarkReportBuilder.build(name, results)` preserves result order, computes
pass/fail totals, averages case scores, and averages each metric only across
results that contain that metric. The report metrics also contain `pass_rate`,
computed from the final pass/fail counts. It adds only deterministic evaluation
mode and category counts to metadata. The fixed summary is:

```text
Benchmark '<name>' completed <total> case(s): <passed> passed, <failed> failed; average score <score:.3f>.
```

Reports never include complete Agent inputs or outputs, generated source code,
debug logs, knowledge content, traceback text, local paths, or raw exceptions.

## 5. Capability, Tests, Version, and Release

`BenchmarkCapability` is runtime-checkable. The frozen, slotted descriptor has:

```python
name = "benchmark"
agent_name = "BenchmarkRunner"
supported_targets = (
    "SupervisorAgent",
    "FirmwareAgent",
    "HardwareAgent",
    "PCBAgent",
    "DebugAgent",
)
```

KnowledgeGateway remains a non-Agent executor and is not advertised in the
Agent target tuple. Registration is explicit:

```python
register_benchmark_foundation(
    capability_registry: CapabilityRegistry,
    *,
    runner: BenchmarkRunner,
    capability: BenchmarkCapability | None = None,
) -> BenchmarkRunner
```

The function prevalidates the capability name, rejects duplicates before any
write, registers only the descriptor in `CapabilityRegistry`, and returns the
caller-owned runner. It never writes `AgentRegistry` or a global registry.

Tests under `tests/benchmark/` use TDD and cover model invariants, dataset deep
copy and JSON parsing, duplicate IDs, all seven category evaluators, score
bounds, report aggregation and summary, sequential order, repeated-run
determinism, mutation isolation, target failures and malformed outputs,
KnowledgeQuery construction, capability conflicts, and public import
compatibility. The existing 551 tests remain unchanged and passing.

Version literals in the package, Settings, Health response, `pyproject.toml`,
and their assertions move together to `0.11.0`. README gains the Benchmark
Evaluation Architecture and explicitly documents the offline, no-LLM,
no-training, no-model-optimization limits.

Release gates are, in order: Python version, focused benchmark tests, full
pytest suite, compileall, Ruff, independent code review, scope/diff/generated
artifact/secret/path audit, staged diff check, commit
`feat: add benchmark evaluation layer`, annotated tag `v0.11.0`, then
`git push origin main --tags`. Any failure stops the release and must not be
reported as complete.
