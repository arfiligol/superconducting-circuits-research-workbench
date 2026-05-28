# Superconducting Circuits Tutorial

This repository is a notebook-first and app-backed superconducting circuits workbench. The current source of truth is the `Notebook Interface + Electron Application Interface + Julia Runner Compute Plane` architecture.

Python owns task lifecycle, metadata, publication, provenance, and TraceStore APIs. Julia owns simulation, sweeps, heavy analysis, and staged result package generation. Large numeric arrays move through local filesystem Zarr, not HTTP JSON.

## Architecture

This repository has two execution tracks.

### Research Direct Track

```text
[Pluto Notebook]
    |
    | using SuperconductingCircuitsCore
    v
[Julia Core]
    - reusable circuit construction
    - direct JosephsonCircuits.jl simulation
    - direct sweep / analysis prototyping
    - local research plots and scratch outputs
```

Pluto Notebook is the direct Julia Core research interface.
Pluto Notebook is not a Backend task submitter in the platform architecture.

### Product Async Track

```text
[Electron Application / Simulation Workbench / Python Notebook]
    |
    | POST /tasks or domain-specific Backend API
    v
[Python Backend]
    - validate dataset/design/session/request
    - create persisted task row
    - prepare local staging directory
    |
    | POST /runner/v1/tasks/claim
    v
[Julia Runner]
    - execute Julia Core / analysis work
    - write result.zarr + manifest.json under staging
    - report manifest locator
    |
    | POST /runner/v1/tasks/{id}/complete
    v
[Python Backend Publisher]
    - validate manifest and Zarr layout
    - publish into canonical TraceStore
    - create trace metadata
    |
    v
[Application Result Viewer / Raw Data Browser / Python Notebook]
```

Application Simulation Workbench is the productized simulation surface in this track. Electron Application owns the productized workflow. Python Notebook is a programmable Application client. Pluto Notebook is not a task submitter.

Python Notebook appears in this track only as a programmable Backend API client. It is not a scientific compute surface and must not directly call Julia Core as its normal workflow.

See [Simulation Interface Boundaries](docs/reference/architecture/simulation-interface-boundaries.md) for the source-of-truth split between Pluto, Python Notebook, Application Simulation Workbench, Backend, and Julia Runner.

## Interface Responsibilities

| Interface | Responsibility |
| --- | --- |
| Pluto Notebook | Direct Julia Core research computation |
| Python Notebook | Programmable Backend API client |
| Application Simulation Workbench | Productized simulation request builder, task monitor, and result viewer |
| Raw Data Browser | Trace browsing and comparison |
| Python Backend | Task lifecycle, metadata, publication, TraceStore APIs |
| Julia Runner | Async compute execution and local Zarr staging |

Application Simulation Workbench remains mandatory as the productized simulation workflow surface; Pluto is not its replacement.

## Repository Layout

```text
core/
  julia/
    SuperconductingCircuitsCore/
    SuperconductingCircuitsRunner/
  python/
    sc_data_contracts/
notebooks/
  pluto/
  python/
app/
  backend/
  frontend/
    # Application Simulation Workbench, Task Monitor, Raw Data Browser, Dataset UI
  desktop/
scripts/
  dev/
docs/
```

## Local App

Install the active workspaces first:

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

## Data Layout

Local runtime data follows this contract:

```text
data/
  metadata.db
  trace_store/
    datasets/<dataset_id>/designs/<design_id>/batches/<batch_id>.zarr/
  artifacts/
    tasks/<task_id>/manifest.json
  staging/
    tasks/<task_id>/manifest.json
    tasks/<task_id>/result.zarr/
```

`data/staging/` is temporary. `data/trace_store/` is the numeric authority after the Backend validates and publishes a Runner result.

## Documentation

The docs site uses Zensical:

```bash
./scripts/prepare_docs_locales.sh
uv run --group dev zensical serve
```

Build the static docs with:

```bash
./scripts/build_docs_sites.sh
```

## Current Boundaries

- Pluto Notebook is research direct execution.
- Backend task submission is outside the Pluto role.
- Python Notebook is a programmable Application client, not a compute cockpit.
- Application Simulation Workbench remains a first-class product surface.
- No user-facing command-line workflow surface.
- No retired Python UI runtime.
- No separate local queue worker runtime.
- No large ND arrays over HTTP/JSON.
- No cross-language complex dtype reliance; complex traces are real/imag Zarr arrays.

## License

MIT
