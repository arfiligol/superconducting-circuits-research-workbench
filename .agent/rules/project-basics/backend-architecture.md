## Backend Architecture
- Treat backend as a headless application backend, not just a thin CRUD API.
- Keep API handlers limited to parsing, auth, service invocation, response mapping, and transport error translation.
- Keep service errors framework-agnostic; FastAPI-specific exceptions belong in the API layer.
- Keep persistence, TraceStore, Runner protocol, and publication adapters in infrastructure/services.
- Python Backend is the control plane + data plane; it must not execute heavy Julia simulation or analysis in process.
- Julia Runner is the compute plane; it writes local staging Zarr packages and reports manifest locators.
- Backend owns official TraceStore publication and must validate Runner output before creating TraceBatchRecord / TraceRecord metadata.
- No large ND arrays over HTTP/JSON; use Zarr for numeric trace payloads and HTTP only for control/status/manifest/summaries/slices.
- Do not let frontend state, Electron concerns, or transport-only display state leak into backend services or domain.
