---
aliases:
  - Julia Core Diagnostics
  - Agent Debug Path
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/julia-core
status: stable
owner: docs-team
audience: contributor
scope: Machine-readable diagnostics and agent-friendly debug path for Julia Core authoring, compilation, and sweeps.
version: v1.0.0
last_updated: 2026-05-28
updated_by: codex
---

# Debugging and Diagnostics

Diagnostics are first-class Julia Core objects. They let Pluto users, Julia Runner tasks, tests, and AI coding agents inspect failures through stable structured fields instead of guessing from free-form error strings.

Diagnostics complement validation and inspection helpers. Validation decides whether a plan, compile, or sweep is acceptable. Diagnostics explain what failed, where it failed, what was expected, what was observed, and what to inspect next.

## Diagnostic Principles

Diagnostics must be:

- machine-readable;
- stable enough for tests and AI agents;
- linked to CircuitPlan object IDs, not private target netlist row names;
- stage-aware;
- able to explain expected vs actual state;
- able to provide next-step hints;
- safe to display in Pluto;
- deterministic enough for Runner logs and CI.

## Diagnostic Stages

Every diagnostic issue should identify the pipeline stage that produced it.

| Stage | Meaning |
| --- | --- |
| `:authoring` | plan construction, component IDs, parameter metadata, and local authoring shape |
| `:endpoint_resolution` | endpoint lookup, default-line resolution, line taps, spans, and aliases |
| `:relation_validation` | relation endpoint category checks and duplicate relation IDs |
| `:parameter_classification` | declared role, effective role, and sweep-facing metadata checks |
| `:topology_key` | topology-key construction, compile-equivalence grouping, and key comparison |
| `:compile_validation` | complete-plan readiness before target lowering |
| `:compile_lowering` | target-specific lowering into `JosephsonCompiledCircuit` |
| `:sweep_preflight` | sweep axis expansion, grouping, compile estimates, and executor planning |
| `:sweep_execution` | per-point sweep execution, compile cache use, and point status |
| `:simulation` | solver execution and simulation-level warnings or failures |
| `:postprocess` | analysis, fitting, result extraction, and summarization |

## DiagnosticIssue

`DiagnosticIssue` is the common structured issue shape for authoring, compiler, sweep, and simulation diagnostics.

Conceptual shape:

```julia
DiagnosticIssue(
    severity,
    code,
    message,
    path;
    stage,
    object_id,
    expected,
    actual,
    hint,
    related_ids,
    metadata,
)
```

| Field | Purpose |
| --- | --- |
| `severity` | `:error`, `:warning`, or `:info` |
| `code` | stable machine-readable issue code |
| `message` | concise human-readable explanation |
| `path` | structured path to the plan, relation, endpoint, parameter, or sweep object |
| `stage` | diagnostic stage symbol |
| `object_id` | primary CircuitPlan object ID when available |
| `expected` | expected type, category, role, value range, or state |
| `actual` | observed type, category, role, value, or state |
| `hint` | next step for the user or agent |
| `related_ids` | other component, relation, endpoint, or parameter IDs involved |
| `metadata` | additional machine-readable context for tests, Runner logs, or agent debugging |

## DiagnosticReport

`DiagnosticReport` groups diagnostic issues with a report-level stage and a stable summary.
The report contract is `stage`, `issues`, and `summary`.

Conceptual shape:

```julia
struct DiagnosticReport
    stage
    issues
    summary
end
```

`stage` is the primary diagnostic stage for the report. Individual issues may carry more specific stages, but the report-level stage lets agents, tests, Pluto, and Runner logs quickly route the report without parsing summary fields or issue messages.

Expected report-level stages include:

| API | Report stage |
| --- | --- |
| `diagnose_plan(plan)` | `:authoring` |
| `diagnose_compile(plan)` | `:compile_validation` or `:compile_lowering` |
| `diagnose_sweep(build_plan, sweep)` | `:sweep_preflight` |

The summary should preserve counts and stage-level metadata that callers can display without parsing messages.

Useful summary fields include:

- report stage;
- issue counts by severity;
- component, endpoint, relation, and parameter counts;
- topology group counts;
- estimated compiles and simulations;
- executor and compile policy;
- compile readiness status;
- recommended next checks.

## DebugBundle

`DebugBundle` is the portable debug snapshot for a plan, compiled circuit, sweep preflight, or sweep result. It should remain plain Julia data so Pluto, Runner logs, tests, and AI agents can inspect it without a UI dependency.

Conceptual contents:

```text
plan_summary
parameter_summary
endpoint_summary
authoring_diagnostics
compile_diagnostics
diagnostic_stages
topology_explanation
compiled_summary
preflight_summary
sweep_result_summary
recommended_next_checks
```

Use a bundle when one helper call should collect the state needed to debug a failed notebook cell, Runner task, CI test, or agent edit.

## Debug API

The diagnostics API should be callable from ordinary Julia scripts, Pluto notebooks, and Runner task code.

Plan diagnostics:

```julia
report = diagnose_plan(plan)
```

`diagnose_plan` should include authoring validation output, component counts, relation counts, endpoint counts, parameter counts, duplicate IDs, unresolved endpoints, duplicate relation IDs, and parameter-owner issues.

Compile diagnostics:

```julia
report = diagnose_compile(plan)
```

`diagnose_compile` should include compile-ready validation, topology-key summary when available, compile readiness status, compiler warnings when compilation succeeds, and structured compile failure issues when compilation fails.

Sweep diagnostics:

```julia
report = diagnose_sweep(build_plan, sweep)
```

`diagnose_sweep` should include sweep preflight output when available, axis count, topology group count, estimated compiles, estimated simulations, executor, classification warnings, and structured preflight failure issues.

Topology-key diagnostics:

```julia
explain_topology_key(plan)
explain_topology_key(compiled)

diff_topology_keys(plan_a, plan_b)
```

`explain_topology_key` should show the digest, components included, relations included, line taps included, line spans included, structural parameters included, numeric parameters excluded, and the underlying summary.

## Structured Topology Diff

`diff_topology_keys(plan_a, plan_b)` should compare structured topology categories, not only raw digests or opaque `repr` strings.

The returned diff should preserve stable categories so AI agents can tell whether a topology mismatch comes from components, relation topology, line taps, line spans, or structural parameters.

Required fields:

| Field | Meaning |
| --- | --- |
| `same_digest` | whether both plans share the same topology digest |
| `digest_a` | topology digest for the first plan |
| `digest_b` | topology digest for the second plan |
| `added_components` | components present only in the second plan |
| `removed_components` | components present only in the first plan |
| `added_relations` | relation topology present only in the second plan |
| `removed_relations` | relation topology present only in the first plan |
| `changed_relations` | relation IDs or structural relation entries that exist in both plans but differ |
| `added_line_taps` | line taps present only in the second plan |
| `removed_line_taps` | line taps present only in the first plan |
| `changed_line_taps` | matching line tap references whose positions or structural identity changed |
| `added_line_spans` | line spans present only in the second plan |
| `removed_line_spans` | line spans present only in the first plan |
| `changed_line_spans` | matching line span references whose start, stop, or structural identity changed |
| `added_structural_parameters` | structural parameters present only in the second plan |
| `removed_structural_parameters` | structural parameters present only in the first plan |
| `changed_structural_parameters` | matching structural parameters whose topology-relevant metadata changed |
| `ignored_numeric_parameters` | numeric, drive, or analysis parameters excluded from topology comparison |
| `hint` | next diagnostic step or explanation of the mismatch |

Numeric-only changes should not create topology differences. If two plans differ only by numeric parameter values or numeric-only metadata, `same_digest` should remain true, topology-change fields should stay empty, and `ignored_numeric_parameters` should identify the excluded parameter set.

Debug bundle:

```julia
debug_bundle(plan; compiled = compiled, preflight = preflight, result = result)
```

`debug_bundle` should collect plan summaries, parameter summaries, endpoint summaries, diagnostics, report-level diagnostic stages, topology explanations, compiled summaries, sweep summaries, and recommended next checks.

## Validation Relationship

`ValidationIssue` is the validation-specific form of a diagnostic issue, or it must be convertible to `DiagnosticIssue`.

Validation reports should keep stable codes, stages, object IDs, expected state, actual state, hints, related IDs, and metadata whenever that information is available. Human-readable messages are still useful, but they are not the only contract.

## AI Agent Debug Path

When an AI agent debugs Julia Core, it should follow this order:

1. Run the smallest failing test.
2. Call the relevant diagnostic helper.
3. Inspect structured diagnostic fields before editing code.
4. Use `explain_topology_key` or `diff_topology_keys` for sweep grouping problems.
5. For topology mismatch, call `diff_topology_keys(plan_a, plan_b)` and inspect structured fields before editing compiler or sweep code.
6. Use `preflight_sweep` for sweep compile-policy problems.
7. Patch the smallest layer that owns the failing contract.
8. Re-run the specific test, then the package test.

Agents should resolve failures against the Julia Core reference contract, not against retired behavior or old implementation names.

## Caller Behavior

| Caller | Diagnostic use |
| --- | --- |
| Pluto | display reports and bundles near the failing authoring, compile, or sweep cell |
| Julia Runner | record deterministic diagnostic summaries in task logs and staged provenance |
| Tests | assert stable codes, stages, and structured fields instead of brittle message text |
| AI agents | inspect structured fields before choosing which layer to patch |

Diagnostics should not require Pluto, Backend, Electron, or task queue state.
