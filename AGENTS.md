# Circuit Workbench Agent Entry

Circuit Workbench is a tool repository. The host Project or Super Repo owns
research goals, Design Targets, reusable domain knowledge and conventions,
Human acceptance, and project decision history.

Before project-semantic work, read
[`docs/project-context.mdx`](docs/project-context.mdx).

- If the host Project is readable, follow its nearest agent instructions and
  owner documents before using Workbench APIs, workflows, or artifacts.
- If the host Project is unavailable, continue context-independent install,
  API, and diagnostic work. Ask the Human only for research semantics required
  by the current task, and stop before inventing missing goals, conventions, or
  acceptance criteria.
- Keep reusable physics and project decisions in their host owners. Workbench
  owns its tool behavior, APIs, schemas, Julia Core catalog implementation,
  and artifact contracts. External Component Libraries and project Plan
  Builders remain with their declared owners.
- Load only task-relevant rules from
  [`docs/reference/guardrails/_agent_catalog.yml`](docs/reference/guardrails/_agent_catalog.yml);
  `.agent/rules/` contains the extracted Agent Rule mirrors.
- Preserve the lifecycle state set by the owning contract. Only the Human can
  accept new semantics.

SCQ_Design is the current host example, not a required repository layout.
