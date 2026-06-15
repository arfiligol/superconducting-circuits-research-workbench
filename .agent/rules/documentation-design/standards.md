## Documentation Standards
- **Docs IA**: `/docs/` uses reader/task-first navigation: Docs Home, Start Here, Workflows, Concepts, Reference, Contribute & Govern.
- **Diataxis**: Tutorials / How-to / Reference / Explanation remains writing discipline and `diataxis/*` metadata; it is not the first-level sidebar structure.
- **Placement**: onboarding goes to `docs/start/`; task execution goes to `docs/workflows/`; mental models go to `docs/concepts/`; stable contracts and lookup surfaces go to `docs/reference/`; contribution and governance entrypoints go to `docs/contribute/` plus relevant `docs/reference/**` pages.
- **Frontmatter**: aliases, tags, status, owner, audience, scope, version, last_updated, updated_by
- **Language**: editable docs source is English-only; do not add CJK text outside generated/staging output.
- **owner/updated_by**: `team` or `team/person`; the name must be in the contributors registry
- **Tags**: `diataxis/*`, `audience/*`, `sot/*`, `topic/*`
- **SoT**: Authoritative document mark `sot/true`
- **No vague time**: Disable "future/subsequent/upcoming", etc., please write a clear date
