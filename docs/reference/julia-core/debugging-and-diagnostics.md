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

`DiagnosticReport` groups diagnostic issues with a stable summary.

Conceptual shape:

```julia
struct DiagnosticReport
    issues
    summary
end
```

The summary should preserve counts and stage-level metadata that callers can display without parsing messages.

Useful summary fields include:

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

`diff_topology_keys` should compare explainable parts, not only digests. At minimum it should report whether the digest is the same, both digests, added or removed components, relation differences, structural-parameter differences, and a hint.

Debug bundle:

```julia
debug_bundle(plan; compiled = compiled, preflight = preflight, result = result)
```

`debug_bundle` should collect plan summaries, parameter summaries, endpoint summaries, diagnostics, topology explanations, compiled summaries, sweep summaries, and recommended next checks.

## Validation Relationship

`ValidationIssue` is the validation-specific form of a diagnostic issue, or it must be convertible to `DiagnosticIssue`.

Validation reports should keep stable codes, stages, object IDs, expected state, actual state, hints, related IDs, and metadata whenever that information is available. Human-readable messages are still useful, but they are not the only contract.

## AI Agent Debug Path

When an AI agent debugs Julia Core, it should follow this order:

1. Run the smallest failing test.
2. Call the relevant diagnostic helper.
3. Inspect structured diagnostic fields before editing code.
4. Use `explain_topology_key` or `diff_topology_keys` for sweep grouping problems.
5. Use `preflight_sweep` for sweep compile-policy problems.
6. Patch the smallest layer that owns the failing contract.
7. Re-run the specific test, then the package test.

Agents should resolve failures against the Julia Core reference contract, not against retired behavior or old implementation names.

## Caller Behavior

| Caller | Diagnostic use |
| --- | --- |
| Pluto | display reports and bundles near the failing authoring, compile, or sweep cell |
| Julia Runner | record deterministic diagnostic summaries in task logs and staged provenance |
| Tests | assert stable codes, stages, and structured fields instead of brittle message text |
| AI agents | inspect structured fields before choosing which layer to patch |

Diagnostics should not require Pluto, Backend, Electron, or task queue state.
