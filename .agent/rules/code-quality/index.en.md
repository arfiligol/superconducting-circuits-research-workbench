## Code Quality
- Follow Clean Code: clear naming, small functions, single responsibility.
- UI, API, Notebook, Runner, and scripts must not each duplicate business workflows; shared rules belong in app backend services, Julia Core, Julia Runner, or explicit contract packages.
- Prefer fixing the code over adding exceptions or suppressions.
- Load sub-rules as needed: Code Style / Type Checking / Design Patterns / Script Authoring / Data Handling / Logging.
