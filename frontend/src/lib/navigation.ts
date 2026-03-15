import type { LucideIcon } from "lucide-react";
import {
  ActivitySquare,
  Binary,
  CircuitBoard,
  Database,
  FilePenLine,
  LayoutDashboard,
} from "lucide-react";

export type WorkspaceNavigationItem = Readonly<{
  href: string;
  label: string;
  group: "dashboard" | "pipeline" | "circuit-workbench";
  pageTitle?: string;
  icon: LucideIcon;
  aliases?: readonly string[];
}>;

export const workspaceNavigation: readonly WorkspaceNavigationItem[] = [
  {
    href: "/dashboard",
    label: "Dashboard",
    pageTitle: "Dashboard",
    group: "dashboard",
    icon: LayoutDashboard,
    aliases: ["/"],
  },
  {
    href: "/raw-data",
    label: "Raw Data",
    pageTitle: "Raw Data Browser",
    group: "pipeline",
    icon: Database,
    aliases: ["/data-browser"],
  },
  {
    href: "/schemas",
    label: "Schemas",
    pageTitle: "Schemas",
    group: "circuit-workbench",
    icon: FilePenLine,
  },
  {
    href: "/circuit-schemdraw",
    label: "Schemdraw",
    group: "circuit-workbench",
    icon: CircuitBoard,
  },
  {
    href: "/circuit-simulation",
    label: "Simulation",
    pageTitle: "Circuit Simulation",
    group: "circuit-workbench",
    icon: ActivitySquare,
  },
  {
    href: "/characterization",
    label: "Characterization",
    group: "pipeline",
    icon: Binary,
    aliases: ["/analysis"],
  },
] as const;
export type WorkspaceNavigationGroup = Readonly<{
  id: WorkspaceNavigationItem["group"];
  label: string;
  items: readonly WorkspaceNavigationItem[];
}>;

export const workspaceNavigationGroups: readonly WorkspaceNavigationGroup[] = [
  {
    id: "dashboard",
    label: "Dashboard",
    items: workspaceNavigation.filter((item) => item.group === "dashboard"),
  },
  {
    id: "pipeline",
    label: "Pipeline",
    items: workspaceNavigation.filter((item) => item.group === "pipeline"),
  },
  {
    id: "circuit-workbench",
    label: "Circuit Simulation",
    items: workspaceNavigation.filter((item) => item.group === "circuit-workbench"),
  },
] as const;

export type WorkspaceNavigationMatch = Readonly<{
  item: WorkspaceNavigationItem;
  group: WorkspaceNavigationGroup;
}>;

type WorkspacePageIdentity = Readonly<{
  href: string;
  sectionLabel: string;
  pageTitle: string;
}>;

const workspacePageIdentities: readonly WorkspacePageIdentity[] = [
  {
    href: "/dashboard",
    sectionLabel: "Dashboard",
    pageTitle: "Dashboard",
  },
  {
    href: "/raw-data",
    sectionLabel: "Pipeline",
    pageTitle: "Raw Data Browser",
  },
  {
    href: "/data-browser",
    sectionLabel: "Pipeline",
    pageTitle: "Raw Data Browser",
  },
  {
    href: "/schemas",
    sectionLabel: "Circuit Simulation",
    pageTitle: "Schemas",
  },
  {
    href: "/circuit-definition-editor",
    sectionLabel: "Circuit Simulation",
    pageTitle: "Schema Editor",
  },
  {
    href: "/circuit-schemdraw",
    sectionLabel: "Circuit Simulation",
    pageTitle: "Schemdraw",
  },
  {
    href: "/circuit-simulation",
    sectionLabel: "Circuit Simulation",
    pageTitle: "Circuit Simulation",
  },
  {
    href: "/characterization",
    sectionLabel: "Pipeline",
    pageTitle: "Characterization",
  },
] as const;

function matchesWorkspacePath(pathname: string, path: string) {
  return pathname === path || pathname.startsWith(`${path}/`);
}

export function isWorkspaceNavigationItemActive(
  item: WorkspaceNavigationItem,
  pathname: string | null | undefined,
) {
  if (!pathname) {
    return false;
  }

  return [item.href, ...(item.aliases ?? [])].some((path) => matchesWorkspacePath(pathname, path));
}

export function resolveWorkspaceNavigationMatch(
  pathname: string | null | undefined,
): WorkspaceNavigationMatch | null {
  if (!pathname) {
    return null;
  }

  const item =
    workspaceNavigation.find((candidate) => isWorkspaceNavigationItemActive(candidate, pathname)) ??
    null;

  if (!item) {
    return null;
  }

  const group =
    workspaceNavigationGroups.find((candidate) => candidate.id === item.group) ?? null;

  if (!group) {
    return null;
  }

  return {
    item,
    group,
  };
}

export function resolveWorkspacePageIdentity(pathname: string | null | undefined) {
  if (!pathname) {
    return {
      sectionLabel: "Workspace",
      pageTitle: "Overview",
    } as const;
  }

  const directMatch =
    workspacePageIdentities.find((item) => matchesWorkspacePath(pathname, item.href)) ?? null;
  if (directMatch) {
    return {
      sectionLabel: directMatch.sectionLabel,
      pageTitle: directMatch.pageTitle,
    } as const;
  }

  const match = resolveWorkspaceNavigationMatch(pathname);
  if (!match) {
    return {
      sectionLabel: "Workspace",
      pageTitle: "Overview",
    } as const;
  }

  return {
    sectionLabel: match.group.label,
    pageTitle: match.item.pageTitle ?? match.item.label,
  } as const;
}
