## Guardrails
- `docs/reference/guardrails/` is the workspace rules Source of Truth.
- Use `_agent_catalog.yml` to load only task-relevant guardrails instead of loading the full tree.
- Current architecture is Notebook Interface + Python Circuit Runtime + Electron Application Interface + Julia Compute Plane.
- The public runtime is the routine Python circuit-consumer surface; Python Backend and Julia Runner remain the Product App control/data and async compute planes, and Backend-managed TraceStore is the official Product App numeric authority.
- Retired command workflow, Python UI runtime, separate queue worker runtime, and Python in-process Julia execution have no authority over current product/runtime surfaces.
- `.agent/rules/` must be synchronized one-to-one from each guardrail file's `## Agent Rule` block whenever guardrail source changes.
