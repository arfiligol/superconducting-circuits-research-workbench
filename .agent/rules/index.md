## Guardrails
- `docs/reference/guardrails/` is the workspace rules Source of Truth.
- Use `_agent_catalog.yml` to load only task-relevant guardrails instead of loading the full tree.
- Current architecture is Notebook Interface + Electron Application Interface + Julia Runner Compute Plane.
- Python Backend is the control/data plane; Julia Runner is the compute plane; Backend-managed TraceStore is the official numeric authority.
- Legacy command workflow, retired Python UI runtime, separate queue worker runtime, and Python in-process Julia execution are migration evidence, not active product/runtime surfaces.
- `.agent/rules/` must be synchronized one-to-one from each guardrail file's `## Agent Rule` block whenever guardrail source changes.
