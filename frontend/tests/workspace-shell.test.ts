import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const shellSource = readFileSync(
  fileURLToPath(new URL("../src/components/layout/workspace-shell.tsx", import.meta.url)),
  "utf8",
);
const headerSource = readFileSync(
  fileURLToPath(new URL("../src/components/layout/workspace-header.tsx", import.meta.url)),
  "utf8",
);
const navSource = readFileSync(
  fileURLToPath(new URL("../src/components/layout/workspace-nav.tsx", import.meta.url)),
  "utf8",
);
const authEntrySource = readFileSync(
  fileURLToPath(new URL("../src/components/layout/auth-entry-surface.tsx", import.meta.url)),
  "utf8",
);
const sharedSelectSource = readFileSync(
  fileURLToPath(new URL("../src/features/shared/components/app-select.tsx", import.meta.url)),
  "utf8",
);
const statusStripSource = readFileSync(
  fileURLToPath(new URL("../src/components/layout/workspace-status-strip.tsx", import.meta.url)),
  "utf8",
);
const accountPanelSource = readFileSync(
  fileURLToPath(new URL("../src/components/layout/workspace-account-panel.tsx", import.meta.url)),
  "utf8",
);
const shellSidePanelSource = readFileSync(
  fileURLToPath(new URL("../src/components/layout/shell-side-panel.tsx", import.meta.url)),
  "utf8",
);
const schemaCatalogSource = readFileSync(
  fileURLToPath(
    new URL(
      "../src/features/circuit-definition-editor/components/circuit-definition-catalog-workspace.tsx",
      import.meta.url,
    ),
  ),
  "utf8",
);
const rawDataSource = readFileSync(
  fileURLToPath(
    new URL("../src/features/data-browser/components/raw-data-browser-workspace.tsx", import.meta.url),
  ),
  "utf8",
);
const dashboardSource = readFileSync(
  fileURLToPath(
    new URL("../src/features/data-browser/components/dashboard-workspace.tsx", import.meta.url),
  ),
  "utf8",
);
const characterizationSource = readFileSync(
  fileURLToPath(
    new URL("../src/features/characterization/components/characterization-workspace.tsx", import.meta.url),
  ),
  "utf8",
);
const schemdrawSource = readFileSync(
  fileURLToPath(
    new URL("../src/features/circuit-schemdraw/components/circuit-schemdraw-workspace.tsx", import.meta.url),
  ),
  "utf8",
);
const researchPanelsSource = readFileSync(
  fileURLToPath(
    new URL("../src/features/shared/components/research-workflow-panels.tsx", import.meta.url),
  ),
  "utf8",
);
const loginPageSource = readFileSync(
  fileURLToPath(new URL("../src/app/login/page.tsx", import.meta.url)),
  "utf8",
);
const logoutPageSource = readFileSync(
  fileURLToPath(new URL("../src/app/logout/page.tsx", import.meta.url)),
  "utf8",
);

describe("workspace shell source contracts", () => {
  it("keeps the sticky header layered above the sidebar and gives the hamburger trigger feedback", () => {
    expect(shellSource).toContain("sticky top-0 z-50");
    expect(shellSource).toContain("z-30 w-[220px]");
    expect(shellSource).toContain("hover:border-primary/35 hover:bg-primary/10");
    expect(shellSource).toContain("focus-visible:ring-2");
    expect(shellSource).not.toContain("<WorkspaceStatusStrip compact");
  });

  it("keeps header page identity concise while restoring the required shell identity hierarchy", () => {
    expect(headerSource).toContain("SUPERCONDUCTING CIRCUITS");
    expect(headerSource).not.toContain("Research Workbench");
    expect(headerSource).toContain("truncate whitespace-nowrap");
    expect(headerSource).toContain("identity.pageTitle");
    expect(headerSource).toContain("identity.sectionLabel");
    expect(headerSource).not.toContain("identity.summary");
    expect(headerSource).not.toContain("WORKSPACE SURFACE");
  });

  it("keeps the sidebar title-only without intro copy, helper labels, or duplicated shell identity", () => {
    expect(navSource).not.toContain("Workspace routes");
    expect(navSource).not.toContain("SC");
    expect(navSource).not.toContain("SUPERCONDUCTING CIRCUITS");
    expect(navSource).not.toContain("Research Workbench");
    expect(navSource).toContain("group.label");
    expect(navSource).toContain("item.label");
    expect(navSource).not.toContain("Open dashboard");
    expect(navSource).not.toContain("item.summary");
    expect(navSource).not.toContain("active route");
    expect(navSource).not.toContain("Session-backed landing and shell context.");
  });

  it("keeps the shell identity only in the header and not in the sidebar", () => {
    expect(headerSource).toContain("SUPERCONDUCTING CIRCUITS");
    expect(navSource).not.toContain("SUPERCONDUCTING CIRCUITS");
    expect(navSource).not.toContain("Research Workbench");
  });

  it("routes the global context through the right-side drawer instead of an always-visible top strip", () => {
    expect(statusStripSource).toContain("ShellSidePanel");
    expect(statusStripSource).toContain('title="Global Context"');
    expect(statusStripSource).toContain('variant="context"');
    expect(statusStripSource).toContain("Active Workspace");
    expect(statusStripSource).toContain("Active Dataset");
    expect(statusStripSource).toContain("Tasks Queue");
    expect(statusStripSource).toContain("Worker Summary");
    expect(statusStripSource).toContain("resolveShellActiveDatasetSummary");
    expect(statusStripSource).toContain("datasetSummary.value");
    expect(statusStripSource).toContain("Global context");
  });

  it("uses a single active shell-panel model so triggers can switch without overlay dead-zones", () => {
    expect(headerSource).toContain('useState<"account" | "context" | null>');
    expect(headerSource).toContain('activePanel === "account"');
    expect(headerSource).toContain('activePanel === "context"');
    expect(headerSource).toContain("shellControlsRef");
    expect(shellSidePanelSource).toContain('offsetTopClassName = "top-[74px]"');
    expect(shellSidePanelSource).toContain("createPortal");
    expect(shellSidePanelSource).toContain('variant?: "context" | "account"');
    expect(shellSidePanelSource).toContain('const isContextSurface = variant === "context"');
    expect(shellSidePanelSource).toContain('variant !== "account"');
    expect(shellSidePanelSource).toContain("interactionBoundaryRef");
    expect(shellSidePanelSource).toContain("inset-x-4 top-[calc(74px+1rem)]");
    expect(shellSidePanelSource).toContain("h-[calc(100dvh-74px)]");
  });

  it("splits context and account into different shell surface models", () => {
    expect(statusStripSource).toContain('variant="context"');
    expect(accountPanelSource).toContain('variant="account"');
    expect(accountPanelSource).toContain('className="max-w-[440px]"');
  });

  it("keeps workspace and dataset switchers inside the shared shell", () => {
    expect(statusStripSource).toContain("switchWorkspace(");
    expect(statusStripSource).toContain("Search Datasets");
    expect(statusStripSource).toContain("handleDatasetSelection(");
    expect(statusStripSource).toContain("syncRouteDataset(");
  });

  it("adopts explicit auth entry routes instead of disabled user-menu wording", () => {
    expect(accountPanelSource).toContain("authSummary.primaryActionHref");
    expect(headerSource).toContain("WorkspaceAccountPanel");
    expect(accountPanelSource).not.toContain("Close menu");
    expect(accountPanelSource).not.toContain("CLOSE MENU");
    expect(loginPageSource).toContain('mode="login"');
    expect(logoutPageSource).toContain('mode="logout"');
    expect(authEntrySource).toContain("useForm<LoginFormValues>");
    expect(authEntrySource).toContain("await login(values)");
    expect(authEntrySource).toContain("await logout()");
    expect(authEntrySource).not.toContain("Auth State");
    expect(authEntrySource).not.toContain("Session Mode");
  });

  it("removes low-contrast auth-adjacent rose notices from the shared shell", () => {
    expect(statusStripSource).not.toContain("text-rose-100");
    expect(headerSource).not.toContain("text-rose-100");
  });

  it("adopts the shared app-owned select across visible workflow surfaces", () => {
    expect(sharedSelectSource).toContain("aria-haspopup=\"listbox\"");
    for (const source of [
      schemaCatalogSource,
      rawDataSource,
      dashboardSource,
      characterizationSource,
      schemdrawSource,
      researchPanelsSource,
    ]) {
      expect(source).toContain("AppSelectField");
      expect(source).not.toContain("<select");
    }
  });

  it("keeps touched workflow surfaces off pale-on-pale rose warnings", () => {
    for (const source of [
      schemaCatalogSource,
      schemdrawSource,
      characterizationSource,
      statusStripSource,
      accountPanelSource,
    ]) {
      expect(source).not.toContain("text-rose-100");
      expect(source).not.toContain("text-amber-100");
    }
  });
});
