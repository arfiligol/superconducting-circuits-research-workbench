## Execution & Verification
- Define workspace baselines for build, lint, type-check, test, and CI.
- Branch, worktree, PR, merge, synchronization, and cleanup mechanics route through `Branch & Worktree Flow` to the active host delivery profile.
- When changing the code, give priority to checks directly related to the touched area.
- The workspace delivery baseline includes five verification lines: app/frontend, app/backend, Julia Runner, desktop, and docs.
- Task scope, verification depth, and internal-worker coordination must remain inside the resolved owner boundary.
