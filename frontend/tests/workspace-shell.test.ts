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
  });

  it("keeps header page identity concise while restoring the required shell identity hierarchy", () => {
    expect(headerSource).toContain("SUPERCONDUCTING CIRCUITS");
    expect(headerSource).toContain("Research Workbench");
    expect(headerSource).toContain("truncate whitespace-nowrap");
    expect(headerSource).toContain("identity.pageTitle");
    expect(headerSource).toContain("identity.sectionLabel");
    expect(headerSource).not.toContain("identity.summary");
    expect(headerSource).not.toContain("WORKSPACE SURFACE");
  });

  it("keeps the sidebar title-only without intro copy, item summaries, or duplicated shell identity", () => {
    expect(navSource).toContain("Workspace routes");
    expect(navSource).toContain("SC");
    expect(navSource).not.toContain("SUPERCONDUCTING CIRCUITS");
    expect(navSource).not.toContain("Research Workbench");
    expect(navSource).toContain("group.label");
    expect(navSource).toContain("item.label");
    expect(navSource).not.toContain("Open dashboard");
    expect(navSource).not.toContain("item.summary");
    expect(navSource).not.toContain("active route");
    expect(navSource).not.toContain("Session-backed landing and shell context.");
  });

  it("moves the secondary shell identity into the header instead of duplicating it in the sidebar", () => {
    expect(headerSource).toContain("Research Workbench");
    expect(navSource).not.toContain("Research Workbench");
  });

  it("routes the collapsed active dataset trigger through the compact shell helper", () => {
    expect(statusStripSource).toContain("resolveShellActiveDatasetSummary");
    expect(statusStripSource).toContain("datasetSummary.value");
    expect(statusStripSource).toContain("datasetSummary.badge");
    expect(statusStripSource).toContain("compact ? \"min-h-[52px] py-2.5\"");
  });

  it("keeps workspace and dataset switchers inside the shared shell", () => {
    expect(statusStripSource).toContain("switchWorkspace(");
    expect(statusStripSource).toContain("Search Datasets");
    expect(statusStripSource).toContain("handleDatasetSelection(");
    expect(statusStripSource).toContain("syncRouteDataset(");
  });

  it("adopts explicit auth entry routes instead of disabled user-menu wording", () => {
    expect(headerSource).toContain("authSummary.primaryActionHref");
    expect(headerSource).not.toContain("Account settings are not expanded");
    expect(loginPageSource).toContain('mode="login"');
    expect(logoutPageSource).toContain('mode="logout"');
    expect(authEntrySource).toContain("useForm<LoginFormValues>");
    expect(authEntrySource).toContain("await login(values)");
    expect(authEntrySource).toContain("await logout()");
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
    ]) {
      expect(source).not.toContain("text-rose-100");
      expect(source).not.toContain("text-amber-100");
    }
  });
});
