# Superconducting Circuits Research Workbench

An open-source research and education workbench for superconducting quantum
circuits, connecting circuit models, simulation notebooks, measurement-oriented
data workflows, and reproducible analysis infrastructure.

This repository is an **active research workbench**. It is research-platform
first: the application, backend, Julia Runner, and TraceStore contracts are
designed for reproducible superconducting-circuit analysis. It is also
education-friendly by design: the documentation and Pluto notebooks give
students and new researchers a concrete path into the physics, modeling, and
simulation workflow.

## Why This Exists

Superconducting quantum circuits are still a fast-moving research area. A useful
toolchain needs to do more than run a single simulation. It needs to help
researchers connect:

```text
design -> simulation -> measurement -> comparison -> feedback
```

This project focuses on the analysis side of that loop. It brings together
circuit definitions, Julia simulation workflows, S/Y/Z-oriented trace analysis,
measurement and layout-simulation data, task execution, result publication, and
provenance-aware data browsing.

The goal is to make research artifacts easier to inspect, compare, reproduce,
and carry from exploratory notebooks into app-backed workflows without changing
the scientific meaning of the model.

## Who This Is For

- Researchers and quantum hardware teams working on superconducting-circuit
  design, simulation, measurement analysis, and feedback workflows.
- Students learning superconducting-circuit modeling, network response,
  notebook-based simulation, and the path from circuit definition toward
  quantum-circuit interpretation.
- Scientific tooling developers building maintainable infrastructure around
  notebooks, async compute runners, local data stores, and research provenance.

## What the Project Provides

| Area | Purpose |
| --- | --- |
| Educational docs and Pluto notebooks | Learn circuit construction, simulation experiments, sweep design, result inspection, and the physics/modeling path. |
| Julia Core | Shared scientific authoring and simulation concepts used by Pluto notebooks and the Julia Runner. |
| Application workbenches | Productized dataset, simulation, analysis, trace browsing, task monitoring, and result-view workflows. |
| Python Backend | Task lifecycle, metadata, publication, provenance, TraceStore registration, and platform data APIs. |
| Julia Runner | Async simulation, sweeps, post-processing, fitting, derived-parameter extraction, and staged result package generation. |
| TraceStore | Local Zarr-backed numeric result management for published traces and analysis results. |

## Architecture Snapshot

The current source-of-truth architecture is:

```text
Notebook Interface + Electron Application Interface + Julia Runner Compute Plane
```

The main execution and inspection tracks are:

```text
[Pluto Notebook]
    |
    | direct Julia Core research execution
    v
[Julia Core]
```

```text
[Electron Application / Simulation Workbench / Analysis Workbench]
    |
    | persisted task request
    v
[Python Backend]
    |
    | runner task envelope
    v
[Julia Runner]
    |
    | staged result.zarr + manifest.json
    v
[Python Backend Publisher]
    |
    | validated publication
    v
[TraceStore / ResultView / Raw Data Browser]
```

```text
[Python Notebook]
    |
    | read-only local/exported/canonical data inspection
    v
[Ad hoc analysis]

[Python Notebook]
    |
    | platform state changes and task submission
    v
[Python Backend APIs]
```

### Interface Responsibilities

| Interface | Responsibility |
| --- | --- |
| Pluto Notebook | Direct Julia Core research computation, interactive inspection, and exploratory plots. |
| Python Notebook | Programmable data-analysis and inspection surface; platform mutations go through Backend contracts. |
| Application Simulation Workbench | Productized simulation request builder, task monitor, and result viewer. |
| Application Analysis Workbench | Productized fitting, post-processing, comparison, and derived-parameter workflow. |
| Task / Execution Center | Cross-workbench execution history, Runner runtime status summary, task detail, and result handoff. |
| Raw Data Browser | Trace browsing, result lineage, and comparison. |
| Python Backend | Task lifecycle, metadata, publication, provenance, and TraceStore APIs. |
| Julia Runner | Async compute execution and local Zarr staging. |

Pluto is the direct research cockpit. It is not a backend task submitter in the
platform architecture. Python notebooks may inspect local data directly, but any
platform state change, task creation, publication, metadata update, or result
registration must use Backend contracts.

## Repository Layout

```text
core/
  julia/
    SuperconductingCircuitsCore/
    SuperconductingCircuitsVisualizer/
    SuperconductingCircuitsRunner/
  python/
    sc_data_contracts/
notebooks/
  pluto/
  python/
app/
  backend/
  frontend/
  desktop/
scripts/
  dev/
docs/
```

## Getting Started

### Learn Path

Use this path if you want to understand superconducting-circuit modeling and run
the notebook examples first.

- Read the docs site: <https://arfiligol.github.io/superconducting-circuits-tutorial/>
- Start with the Pluto notebooks under `notebooks/pluto/`.
- Use the Julia Core reference when you need the current authoring and compiler
  contracts: `docs/reference/julia-core/`.
- Use the physics explanations when you need the S/Y/Z, equivalent-circuit, or
  modeling context: `docs/explanation/physics/`.

### Platform Path

Use this path if you want to run the local app-backed research platform.

Install the active workspaces:

```bash
cd app/backend && uv sync
npm install --prefix app/frontend
npm install --prefix app/desktop
```

Start the local application stack:

```bash
npm run app:dev
```

Stop it with:

```bash
npm run app:stop
```

The local stack starts:

- Next.js frontend on `http://127.0.0.1:3000`
- Python Backend on `http://127.0.0.1:8000`
- Julia Runner polling the backend runner API

No separate queue service is part of the local runtime.

## Validation

Run the focused checks with:

```bash
npm run backend:test
npm run frontend:typecheck
npm run runner:test
npm run julia:test
npm run build --prefix app/desktop
```

Use targeted tests while iterating:

```bash
cd app/backend && uv run pytest tests/test_runner_api.py -q
julia --project=core/julia/SuperconductingCircuitsRunner -e 'using Pkg; Pkg.test()'
```

Build the static docs with:

```bash
./scripts/build_docs_sites.sh
```

## Development Status

This repository should be read as an active research workbench, not a
production-ready service or a released external-user platform.

Current boundaries:

- Research execution lives in Pluto notebooks and Julia Core.
- Productized simulation and analysis tasks go through the Application, Python
  Backend, and Julia Runner.
- Python Backend owns task lifecycle, metadata, publication, provenance, and
  TraceStore APIs.
- Julia Runner owns async compute execution and staged result package
  generation.
- Large numeric arrays move through local filesystem Zarr, not HTTP JSON.
- User-facing command workflows, retired Python UI runtimes, separate local
  queue workers, and Python-in-process Julia execution are not active product
  surfaces.

## Contributing

Contributions are welcome when they preserve the current architecture
boundaries: scientific logic belongs in the core and runner layers, product
state belongs in Backend contracts, and notebook workflows should either remain
explicit research workflows or be promoted through the app-backed task and
publication path.

See `docs/how-to/contributing.md` and `docs/reference/guardrails/` before
changing public contracts, architecture boundaries, documentation source of
truth, or validation workflows.

## License

MIT
