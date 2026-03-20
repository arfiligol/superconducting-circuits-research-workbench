# sc-cli

`sc-cli` is the standalone CLI package for this repository.

It owns the `sc` entrypoint and delegates real workflow logic to installable shared packages such as `sc-core`.

## Install

From the repository root:

```bash
uv sync
uv run sc --help
```

From the package directory:

```bash
cd cli
uv sync
uv run sc --help
```

## Package Layout

```text
cli/
├── pyproject.toml
├── src/sc_cli/
│   ├── app.py
│   ├── presenters.py
│   └── commands/
└── tests/
```

## Design Rules

- Commands stay thin: parse input, render output, delegate to shared packages.
- Shared scientific or workflow logic belongs in `src/core/sc_core`, not in `sc_cli`.
- Legacy `src/scripts` remains migration reference only and should not receive new workflow logic.
