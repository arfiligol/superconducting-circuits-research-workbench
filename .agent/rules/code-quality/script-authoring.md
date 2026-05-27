## Script Authoring
- CLI is no longer an active product surface.
- Do not add new Typer commands, CLI package entrypoints, or user-facing CLI docs.
- Keep only `scripts/` helpers for dev/build/test/maintenance.
- Put helpers under `scripts/dev/`, `scripts/build/`, `scripts/test/`, or `scripts/maintenance/`.
- Scripts may orchestrate commands but must not own business workflow logic.
- Real workflow logic must live in app backend services, Julia Core, Julia Runner, or explicit contract packages.
