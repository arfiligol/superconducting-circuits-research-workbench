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
const themeToggleSource = readFileSync(
  fileURLToPath(new URL("../src/components/layout/theme-toggle.tsx", import.meta.url)),
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
const rawDataWorkspaceSource = readFileSync(
  fileURLToPath(
    new URL("../src/features/data-browser/components/raw-data-browser-workspace.tsx", import.meta.url),
  ),
  "utf8",
);
const rawDataTraceSummariesSource = readFileSync(
  fileURLToPath(
    new URL("../src/features/data-browser/components/raw-data-trace-summaries-panel.tsx", import.meta.url),
  ),
  "utf8",
);
const rawDataControlsSource = readFileSync(
  fileURLToPath(
    new URL("../src/features/data-browser/components/raw-data-browser-controls.tsx", import.meta.url),
  ),
  "utf8",
);
const rawDataSource = [rawDataWorkspaceSource, rawDataTraceSummariesSource, rawDataControlsSource].join("\n");
const datasetWorkspaceSource = readFileSync(
  fileURLToPath(
    new URL("../src/features/data-browser/components/dataset-workspace.tsx", import.meta.url),
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
const simulationSource =
  readFileSync(
    fileURLToPath(
      new URL("../src/features/simulation/components/simulation-workbench-shell.tsx", import.meta.url),
    ),
    "utf8",
  ) +
  readFileSync(
    fileURLToPath(
      new URL("../src/features/simulation/components/simulation-setup-stage.tsx", import.meta.url),
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
const developerModeSource = readFileSync(
  fileURLToPath(new URL("../src/lib/app-state/developer-mode.tsx", import.meta.url)),
  "utf8",
);

describe("workspace shell source contracts", () => {
  it("keeps the fixed header layered above the sidebar and gives the hamburger trigger feedback", () => {
    expect(shellSource).toContain("fixed inset-x-0 top-0 z-50");
    expect(shellSource).toContain("pt-[var(--shell-header-height)]");
    expect(shellSource).toContain("lg:pl-[var(--shell-sidebar-width)]");
    expect(shellSource).toContain("top-[var(--shell-header-height)]");
    expect(shellSource).toContain("overflow-y-auto border-r");
    expect(shellSource).toContain('document.documentElement.style.setProperty("--shell-header-height"');
    expect(shellSource).toContain('document.documentElement.style.setProperty(');
    expect(shellSource).toContain("cursor-pointer items-center justify-center");
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
    expect(headerSource).toContain('label="Runtime Mode"');
    expect(headerSource).toContain('label="Active Dataset"');
    expect(headerSource).toContain('requestOpenGlobalContext("runtime")');
    expect(headerSource).toContain('requestOpenGlobalContext("dataset")');
    expect(headerSource).toContain("resolveShellActiveDatasetSummary");
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
    expect(statusStripSource).toContain("Runtime Mode");
    expect(statusStripSource).toContain("Active Workspace");
    expect(statusStripSource).toContain("Active Dataset");
    expect(statusStripSource).toContain("Tasks & Runtime");
    expect(statusStripSource).toContain("resolveShellActiveDatasetSummary");
    expect(statusStripSource).toContain("datasetSummary.value");
    expect(statusStripSource).toContain("switchRuntimeMode(");
    expect(statusStripSource).toContain("activeTaskDetail.status");
    expect(statusStripSource).not.toContain("activeTaskDetail.progress.phase");
  });

  it("adopts the live backend runtime transition enums in shell notices and auth entry flows", () => {
    expect(statusStripSource).toContain("entered_local_bypass");
    expect(statusStripSource).toContain("online_auth_required");
    expect(statusStripSource).toContain("online_session_dropped");
    expect(statusStripSource).not.toContain("local_ready");
    expect(statusStripSource).not.toContain("online_target_rejected");
    expect(statusStripSource).not.toContain("context_cleared");
    expect(authEntrySource).toContain("online_session_dropped");
  });

  it("turns the global context cards into an obvious section switcher", () => {
    expect(statusStripSource).toContain("type ContextSectionId");
    expect(statusStripSource).toContain("ContextSectionCard");
    expect(statusStripSource).toContain("selectedSection");
    expect(statusStripSource).toContain("aria-pressed={selected}");
    expect(statusStripSource).toContain("cursor-pointer rounded-[1rem]");
    expect(statusStripSource).toContain("hover:-translate-y-0.5");
    expect(statusStripSource).toContain("focus-visible:ring-2");
    expect(statusStripSource).toContain('selectedSection === "workspace"');
    expect(statusStripSource).toContain('selectedSection === "dataset"');
    expect(statusStripSource).toContain('selectedSection === "tasks"');
    expect(statusStripSource).not.toContain("Focused Section");
    expect(statusStripSource).not.toContain("toggleDeveloperMode");
    expect(statusStripSource).toContain("Open Account > Developer Mode for technical detail");
  });

  it("uses a single active shell-panel model so triggers can switch without overlay dead-zones", () => {
    expect(headerSource).toContain('useState<"account" | "context" | null>');
    expect(headerSource).toContain('activePanel === "account"');
    expect(headerSource).toContain('activePanel === "context"');
    expect(headerSource).toContain("shellControlsRef");
    expect(shellSidePanelSource).toContain(
      'offsetTopClassName = "top-[var(--shell-header-height)]"',
    );
    expect(shellSidePanelSource).toContain("createPortal");
    expect(shellSidePanelSource).toContain('variant?: "context" | "account"');
    expect(shellSidePanelSource).toContain('const isContextSurface = variant === "context"');
    expect(shellSidePanelSource).toContain('variant !== "account"');
    expect(shellSidePanelSource).toContain('document.body.style.overflow = "hidden"');
    expect(shellSidePanelSource).toContain('document.documentElement.style.overflow = "hidden"');
    expect(shellSidePanelSource).toContain("interactionBoundaryRef");
    expect(shellSidePanelSource).toContain("bg-black/45 backdrop-blur-[8px] dark:bg-black/65");
    expect(shellSidePanelSource).toContain(
      "inset-x-4 top-[calc(var(--shell-header-height)+1rem)]",
    );
    expect(shellSidePanelSource).toContain(
      "max-w-[min(1220px,calc(100vw-1.5rem))]",
    );
    expect(shellSidePanelSource).toContain("overscroll-contain");
    expect(shellSidePanelSource).toContain("md:top-[calc(var(--shell-header-height)+1.25rem)]");
    expect(shellSidePanelSource).toContain("md:bottom-5");
    expect(shellSidePanelSource).toContain("h-[calc(100dvh-var(--shell-header-height))]");
  });

  it("splits context and account into different shell surface models", () => {
    expect(statusStripSource).toContain('variant="context"');
    expect(accountPanelSource).toContain('variant="account"');
    expect(accountPanelSource).toContain('className="max-w-[448px]"');
    expect(accountPanelSource).toContain("eyebrow={null}");
    expect(shellSidePanelSource).toContain("rounded-l-[1.6rem]");
  });

  it("keeps workspace and dataset switchers inside the shared shell", () => {
    expect(statusStripSource).toContain("switchWorkspace(");
    expect(statusStripSource).toContain("Search Datasets");
    expect(statusStripSource).toContain("handleDatasetSelection(");
    expect(statusStripSource).toContain("syncRouteDataset(");
    expect(statusStripSource).toContain('href="/dataset"');
    expect(statusStripSource).toContain("aria-pressed={isSelected || isNullSelected}");
    expect(statusStripSource).toContain("cursor-pointer rounded-[0.95rem]");
    expect(statusStripSource).toContain("No active dataset");
    expect(statusStripSource).not.toContain("Clear active dataset");
  });

  it("rebuilds runtime mode into selectable cards with inline target and refresh affordances", () => {
    expect(statusStripSource).toContain("RuntimeModeCard");
    expect(statusStripSource).toContain("Local Space");
    expect(statusStripSource).toContain("Server Target (IP:Port or origin)");
    expect(statusStripSource).toContain("Refresh only re-fetches the Local Space session envelope");
    expect(statusStripSource).toContain("does not call online auth refresh");
    expect(statusStripSource).toContain('title="Online Mode"');
    expect(statusStripSource).not.toContain("Active Mode");
    expect(statusStripSource).not.toContain("Context Target");
    expect(statusStripSource).not.toContain("Context Reset");
    expect(statusStripSource).not.toContain("Local backend");
  });

  it("combines queue and worker runtime context into one shell surface", () => {
    expect(statusStripSource).toContain('title="Tasks & Runtime"');
    expect(statusStripSource).toContain('from "@/lib/task-presenters/presentation"');
    expect(statusStripSource).toContain("workerSummary,");
    expect(statusStripSource).toContain("summarizeWorkerRuntime(workerSummary)");
    expect(statusStripSource).toContain("Worker lanes");
    expect(statusStripSource).toContain('label="Pending"');
    expect(statusStripSource).toContain('label="Running"');
    expect(statusStripSource).toContain('label="Completed"');
    expect(statusStripSource).toContain('label="Failed"');
    expect(statusStripSource).toContain('label="Cancelled"');
    expect(statusStripSource).toContain('label="Terminated"');
    expect(statusStripSource).toContain("laneSummary.idleProcessors");
    expect(statusStripSource).toContain("laneSummary.runningProcessors");
    expect(statusStripSource).toContain("laneSummary.degradedProcessors");
    expect(statusStripSource).toContain("laneSummary.drainingProcessors");
    expect(statusStripSource).toContain("laneSummary.offlineProcessors");
    expect(statusStripSource).not.toContain("function formatTaskStatusLabel");
    expect(statusStripSource).not.toContain("function formatWorkerLaneLabel");
    expect(statusStripSource).not.toContain("resolveShellWorkerSummary(");
    expect(statusStripSource).not.toContain('title="Worker Summary"');
  });

  it("adopts explicit auth entry routes instead of disabled user-menu wording", () => {
    expect(accountPanelSource).toContain('href="/login"');
    expect(accountPanelSource).toContain('href="/logout"');
    expect(accountPanelSource).toContain("Connect to Online Mode");
    expect(accountPanelSource).toContain("Switch to Local Mode");
    expect(headerSource).toContain("WorkspaceAccountPanel");
    expect(accountPanelSource).not.toContain("Close menu");
    expect(accountPanelSource).not.toContain("CLOSE MENU");
    expect(loginPageSource).toContain('mode="login"');
    expect(logoutPageSource).toContain('mode="logout"');
    expect(authEntrySource).toContain("useForm<LoginFormValues>");
    expect(authEntrySource).toContain("await login(values)");
    expect(authEntrySource).toContain("await logout()");
    expect(authEntrySource).toContain("switchRuntimeMode({");
    expect(authEntrySource).toContain("serverTargetDraft");
    expect(authEntrySource).toContain("Auth Entry no longer blocks Local Mode");
    expect(authEntrySource).toContain("Retry target");
    expect(authEntrySource).toContain("Edit target");
    expect(authEntrySource).toContain("Switch to Local Mode");
    expect(authEntrySource).toContain("No online target");
    expect(authEntrySource).not.toContain("Auth State");
    expect(authEntrySource).not.toContain("Session Mode");
    expect(authEntrySource).not.toContain("Local backend");
  });

  it("keeps the account drawer focused on account and preferences instead of workspace collaboration management", () => {
    expect(accountPanelSource).toContain('title="Account"');
    expect(accountPanelSource).toContain("Preferences");
    expect(accountPanelSource).toContain("Developer Mode");
    expect(accountPanelSource).toContain("No online target");
    expect(accountPanelSource).not.toContain("Local backend");
    expect(accountPanelSource).toContain("Theme ownership stays in the account drawer.");
    expect(accountPanelSource).not.toContain("Workspace Collaboration");
    expect(accountPanelSource).not.toContain("Pending Invitations");
    expect(accountPanelSource).not.toContain("Remove Member by User ID");
    expect(accountPanelSource).not.toContain("Transfer Ownership to User ID");
    expect(accountPanelSource).not.toContain("SUPERCONDUCTING CIRCUITS");
  });

  it("keeps technical detail behind app-level developer mode instead of always-visible shell diagnostics", () => {
    expect(developerModeSource).toContain("DEVELOPER_MODE_STORAGE_KEY");
    expect(developerModeSource).toContain("localStorage");
    expect(developerModeSource).toContain("useDeveloperMode");
    expect(accountPanelSource).toContain("Debug details");
    expect(accountPanelSource).toContain("developerModeEnabled ? (");
    expect(statusStripSource).toContain("Open Account > Developer Mode for technical detail");
    expect(statusStripSource).not.toContain("Developer Mode On");
    expect(statusStripSource).not.toContain("Developer Mode Off");
  });

  it("gives the theme toggle a clear interactive affordance", () => {
    expect(themeToggleSource).toContain("cursor-pointer");
    expect(themeToggleSource).toContain("focus-visible:ring-2");
    expect(themeToggleSource).toContain("aria-pressed");
    expect(themeToggleSource).toContain("hover:border-primary/35 hover:bg-primary/10");
  });

  it("removes low-contrast auth-adjacent rose notices from the shared shell", () => {
    expect(statusStripSource).not.toContain("text-rose-100");
    expect(headerSource).not.toContain("text-rose-100");
  });

  it("adopts the shared app-owned select across visible workflow surfaces", () => {
    expect(sharedSelectSource).toContain("aria-haspopup=\"listbox\"");
    expect(sharedSelectSource).toContain("export function AppInlineSelect");
    for (const source of [
      schemaCatalogSource,
      rawDataSource,
      characterizationSource,
      schemdrawSource,
      simulationSource,
      researchPanelsSource,
    ]) {
      expect(source.includes("AppSelectField") || source.includes("AppInlineSelect")).toBe(true);
      expect(source).not.toContain("<select");
    }
    expect(dashboardSource).not.toContain("<select");
    expect(datasetWorkspaceSource).not.toContain("<select");
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

  it("keeps global context detail focused on the selected section without a redundant summary card", () => {
    expect(statusStripSource).toContain("ContextSectionCard");
    expect(statusStripSource).not.toContain("selectedSectionTitle");
    expect(statusStripSource).not.toContain("Focused Section");
  });
});
