---
aliases:
  - "安裝環境"
tags:
  - diataxis/how-to
  - status/stable
  - topic/getting-started
---

# 安裝環境

This project uses Python for the backend/control plane, Julia for compute, Next.js for the application UI, and Electron for the desktop shell.

## Requirements

Install:

- Python 3.12+
- `uv`
- Julia 1.12+
- Node.js 22+
- npm

Check versions with:

```bash
python --version
uv --version
julia --version
node --version
npm --version
```

## Install Dependencies

From the repository root:

```bash
uv sync
cd app/backend && uv sync
npm ci --prefix app/frontend
npm ci --prefix app/desktop
julia --project=core/julia/SuperconductingCircuitsCore -e 'using Pkg; Pkg.instantiate()'
julia --project=core/julia/SuperconductingCircuitsRunner -e 'using Pkg; Pkg.instantiate()'
```

## Validate

Run the retained checks:

```bash
cd app/backend && uv run pytest
npm run typecheck --prefix app/frontend
julia --project=core/julia/SuperconductingCircuitsCore -e 'using Pkg; Pkg.test()'
julia --project=core/julia/SuperconductingCircuitsRunner -e 'using Pkg; Pkg.test()'
```

## Start The Local App

Start frontend, backend, and Julia Runner:

```bash
npm run app:dev
```

Stop them with:

```bash
npm run app:stop
```

## Next Step

Read [Application Interface](../../reference/app/application-interface.md) and [Notebook Interface](../../reference/notebooks/index.md).
