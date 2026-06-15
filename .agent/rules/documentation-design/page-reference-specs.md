## Page Reference Specs
- **Type**: App frontend page technical documents must be written as Page Reference Spec, not requirements documents, prose or implementation notes
- **Diataxis**: This type of file belongs to `Reference`
- **Now-only**: Only write the current official page contract; do not write the old version/legacy/migration history
- **Title alignment**: Files `title` and H1 must be aligned sidebar / nav label first; route is also written in frontmatter `route` and body identity
- **Observed input**: The page context, screenshot collection, and existing UI inventory extracted by other Agents can only be used as input materials and cannot be directly used as official specs.
- **Normalization**: Input materials must be reorganized into 8 fixed blocks; `Unknown from current page context` must not be left directly in the official SoT
- **Current product wins**: If the current product requires task management, result recovery, research workflow and other capabilities, the official spec must be included and is not restricted by the old screen.
- **Fixed sections**: must contain 8 sections:
 1. Purpose
 2. User Goal
 3. Layout Structure
 4. Component Inventory
 5. Data & State Contract
 6. Interaction Flows
 7. Visual Rules
 8. Acceptance Checklist
- **Optional sections**: `Related Contracts`, `Runtime Notes` are added only when needed
- **Focus**: Write page purpose, layout, components, state, flows, acceptance first; do not write framework details first
- **Do not include**: framework implementation details, repository/service class name, pixel-level CSS, historical background
- **Naming**: New pages use `docs/app/frontend/pages/<route-name>.md` first and align with Product App sidebar IA
