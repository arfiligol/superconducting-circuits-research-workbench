## Design Patterns
- Keep shared workflow logic in app backend services, Julia Core, Julia Runner, or explicit contract packages, not in React components, FastAPI routers, notebooks, or scripts.
- Use dependency injection or explicit factories for services, repositories, and adapters.
- Python Backend is the control/data plane and must not execute heavy simulation or analysis compute in process.
- Julia Runner is the compute plane and must not write formal metadata DB records.
- Application-triggered simulation and analysis must be asynchronous.
- API handlers should do I/O, auth, validation, service invocation, and response mapping only.
- Scripts are dev/build/test/maintenance helpers only and must not become user-facing workflow contracts.
