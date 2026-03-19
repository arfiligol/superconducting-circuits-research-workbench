# Frontend Shell And Auth Follow-ups TODO

This file is a planning note for upcoming Frontend Agent prompts.
It is not a Source of Truth document and must not override `docs/reference/**`.

## Scope

- Track user-requested frontend fixes that should be bundled into future Frontend Agent prompts.
- Keep visible product issues grouped by feature outcome, not by implementation layer.
- Mark doc-dependent ideas clearly so they are not implemented silently against SoT.

## TODO

### P0 Authentication-first surfaces

- [ ] Add a visible `Login` surface instead of relying on placeholder session language.
- [ ] Add a visible `Logout` flow or dedicated logout route from the user menu.
- [ ] Make the header show clear auth-aware states:
  - anonymous session
  - authenticated user
  - degraded session
- [ ] Remove placeholder-only auth wording from the user menu once real auth/session adoption lands.

### P0 Error readability and message contrast

- [ ] Fix low-contrast error banners across shared/frontend workflow surfaces.
- [ ] Replace pale error text on pale rose backgrounds with accessible contrast.
- [ ] Apply the fix consistently to repeated error banner patterns, not just one page.
- [ ] Re-check shell-level status and workflow-level loading/error surfaces in light theme.

### P1 Theme and light-surface direction

- [ ] Revisit the light-mode app background; current cool blue-gray wash is too heavy.
- [ ] Preserve the soft icon accent colors the user likes, especially the pale icon chips and subtle accent fills.
- [ ] Light mode should shift toward either:
  - a clean white base, or
  - a warmer neutral base
- [ ] The chosen light-mode background should feel like a match to the existing dark-mode mood, not a separate product.
- [ ] Avoid flattening the UI into generic white-on-white; keep depth, but with a calmer light-mode base.

### P1 Sidebar shell cleanup

- [x] Trim sidebar to title-only navigation.
- [ ] Remove duplicated shell identity between sidebar and header.
- [ ] Header should show only `SUPERCONDUCTING CIRCUITS`.
- [ ] Remove `Research Workbench` from the visible shell identity entirely.
- [ ] Keep `SUPERCONDUCTING CIRCUITS` as a single line in the header; no wrapping.
- [ ] Sidebar must not show:
  - `SC`
  - `Navigation`
  - `Workspace routes`
  - any branding card or shell-identity copy
- [ ] Sidebar should contain only:
  - group labels: `DASHBOARD`, `PIPELINE`, `CIRCUIT SIMULATION`
  - the corresponding sidebar items
- [ ] Keep the sidebar focused on concise navigation only.
- [ ] Preserve group labels and active-route clarity after the shell identity move.

### P1 Header and global context cleanup

- [ ] Reduce visual noise in the header/status area once auth/session authority is ready.
- [ ] Revisit how `Active Workspace`, `Active Dataset`, `Tasks Queue`, and worker summary are presented after backend auth/session work lands.
- [ ] Keep current header ownership unless docs are explicitly changed.
- [ ] Move heavy `Global Context / States` management out of the always-expanded header/status strip and into a right-side drawer or panel triggered from the header, once the shell contract is ready.
- [ ] Keep the header trigger compact; do not render the full global-context management surface inline across the top bar.
- [ ] If a right-side global-context drawer or panel is adopted, the trigger order on the header right side should remain:
  - user icon / account trigger first
  - global context / state trigger second

### P2 Pending docs decision

- [ ] Decide whether heavy global-context management should stay entirely in the header or move into a right-side drawer triggered from the header.
- [ ] If a right-side global-context drawer is adopted, prefer header right-cluster ordering as:
  - user icon / account trigger first
  - global context / state drawer toggle second
- [ ] If this direction changes, update docs first before implementation.

### P1 User menu behavior cleanup

- [ ] The user/account trigger should not expose full error text inline in the closed state.
- [ ] If the session is degraded or warning-worthy, show only a compact warning/error icon in the closed trigger.
- [ ] Full error details should appear only after opening the user menu or panel.
- [ ] Remove explicit `CLOSE MENU` CTA copy from the user menu.
- [ ] User menu should close automatically when:
  - clicking outside the menu
  - clicking the user icon / trigger again
- [ ] Keep the open/close behavior lightweight and app-standard; do not require a dedicated close button for this menu.

### P1 Auth entry and diagnostics density

- [ ] Login/logout/auth entry surfaces should not default to showing development-style diagnostics cards in anonymous or degraded state.
- [ ] Remove or defer right-column diagnostics like:
  - `Auth State`
  - `Workspace`
  - `Session Mode`
  when the session is not yet authenticated.
- [ ] Before login, auth entry pages should focus on:
  - the action
  - concise status
  - minimal recovery guidance
- [ ] If diagnostics are still needed for debugging, place them behind a secondary disclosure or authenticated-only context, not as default primary content.

## Prompting Notes

Future Frontend Agent prompts should include these follow-ups when they touch shell/auth work:

- Authentication-first work takes precedence over cosmetic shell polish.
- Sidebar fixes should preserve the current header/global-context boundary unless docs change.
- Error readability fixes should be bundled with shell/auth UI work when possible.
- Do not silently implement the right-drawer idea until the docs decision is explicit.
- Treat shell identity requests literally:
  - if the user asks for only one visible shell identity label, do not reintroduce a secondary one elsewhere
  - if the user asks for navigation-only sidebar, do not add monograms, helper labels, or descriptive copy
- Treat compact trigger requests literally:
  - closed user/account trigger shows status succinctly
  - detailed errors and remediation copy live inside the opened panel only
