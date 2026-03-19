import { describe, expect, it } from "vitest";

import {
  isWorkspaceNavigationItemActive,
  resolveWorkspacePageIdentity,
  workspaceNavigation,
  workspaceNavigationGroups,
} from "../src/lib/navigation";

describe("workspaceNavigation", () => {
  it("covers the canonical shell route families", () => {
    expect(workspaceNavigation).toHaveLength(9);
    expect(workspaceNavigation.map((item) => item.label)).toEqual([
      "Dashboard",
      "Dataset",
      "Tasks",
      "Data Ingestion",
      "Raw Data",
      "Schemas",
      "Schemdraw",
      "Simulation",
      "Characterization",
    ]);
  });

  it("keeps routes unique and absolute", () => {
    const hrefs = workspaceNavigation.map((item) => item.href);

    expect(new Set(hrefs).size).toBe(hrefs.length);
    expect(hrefs.every((href) => href.startsWith("/"))).toBe(true);
  });

  it("keeps the NiceGUI-style drawer grouping stable", () => {
    expect(workspaceNavigationGroups.map((group) => group.label)).toEqual([
      "Workspace",
      "Pipeline",
      "Circuit Simulation",
    ]);
    expect(workspaceNavigationGroups.map((group) => group.items.length)).toEqual([3, 3, 3]);
  });

  it("keeps the shell navigation title-only while preserving icons", () => {
    expect(workspaceNavigation.every((item) => "summary" in item)).toBe(false);
    expect(workspaceNavigation.every((item) => Boolean(item.icon))).toBe(true);
  });

  it("realigns route family and page identity for header consumers", () => {
    expect(resolveWorkspacePageIdentity("/")).toEqual({
      sectionLabel: "Workspace",
      pageTitle: "Dashboard",
    });
    expect(resolveWorkspacePageIdentity("/schemas")).toEqual({
      sectionLabel: "Circuit Simulation",
      pageTitle: "Schemas",
    });
    expect(resolveWorkspacePageIdentity("/dataset")).toEqual({
      sectionLabel: "Workspace",
      pageTitle: "Dataset",
    });
    expect(resolveWorkspacePageIdentity("/data-ingestion")).toEqual({
      sectionLabel: "Pipeline",
      pageTitle: "Data Ingestion",
    });
    expect(resolveWorkspacePageIdentity("/circuit-definition-editor")).toEqual({
      sectionLabel: "Circuit Simulation",
      pageTitle: "Schema Editor",
    });
    expect(resolveWorkspacePageIdentity("/raw-data")).toEqual({
      sectionLabel: "Pipeline",
      pageTitle: "Raw Data Browser",
    });
    expect(resolveWorkspacePageIdentity("/tasks")).toEqual({
      sectionLabel: "Workspace",
      pageTitle: "Tasks",
    });
    expect(resolveWorkspacePageIdentity(null)).toEqual({
      sectionLabel: "Workspace",
      pageTitle: "Overview",
    });
  });

  it("does not treat the schema editor route as an active alias of the schemas nav item", () => {
    const schemasNavItem = workspaceNavigation.find((item) => item.href === "/schemas");

    expect(schemasNavItem).toBeDefined();
    expect(schemasNavItem?.aliases ?? []).not.toContain("/circuit-definition-editor");
    expect(isWorkspaceNavigationItemActive(schemasNavItem!, "/schemas")).toBe(true);
    expect(isWorkspaceNavigationItemActive(schemasNavItem!, "/circuit-definition-editor")).toBe(
      false,
    );
  });

  it("treats /tasks as a primary workspace navigation item", () => {
    const tasksNavItem = workspaceNavigation.find((item) => item.href === "/tasks");

    expect(tasksNavItem).toBeDefined();
    expect(isWorkspaceNavigationItemActive(tasksNavItem!, "/tasks")).toBe(true);
  });
});
