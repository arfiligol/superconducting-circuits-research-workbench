## Project Basics
- Project Basics defines the mission, scope, technology stack and structure of the platform.
- Any changes that affect overall collaboration and architectural consistency must first update this area.
- The current public introduction site direction is Astro; the product app UI direction is Next.js, the API direction is FastAPI, the compute plane direction is Julia Runner, and the Notebook is a research cockpit.
- The backend's responsibility boundaries and internal blueprint are defined by `backend-architecture.md`.
- The old command workflow, retired Python UI runtime, separate queue worker runtime and Python in-process Julia runtime are not part of the product contract and should no longer be the default landing point for new features.
