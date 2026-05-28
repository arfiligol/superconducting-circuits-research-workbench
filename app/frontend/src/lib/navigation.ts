export type WorkspaceNavigationItem = Readonly<{
  href: string;
  label: string;
  group: "workspace" | "data" | "design-assets";
  pageTitle?: string;
  aliases?: readonly string[];
}>;

export const workspaceNavigation: readonly WorkspaceNavigationItem[] = [
  {
    href: "/dashboard",
    label: "Dashboard",
    pageTitle: "Dashboard",
    group: "workspace",
    aliases: ["/"],
  },
  {
    href: "/dataset",
    label: "Dataset",
    pageTitle: "Dataset",
    group: "workspace",
  },
  {
    href: "/tasks",
    label: "Tasks",
    pageTitle: "Tasks",
    group: "workspace",
  },
  {
    href: "/data-ingestion",
    label: "Data Ingestion",
    pageTitle: "Data Ingestion",
    group: "data",
  },
  {
    href: "/raw-data",
    label: "Raw Data",
    pageTitle: "Raw Data Browser",
    group: "data",
    aliases: ["/data-browser"],
  },
  {
    href: "/schemas",
    label: "Design Assets",
    pageTitle: "Design Assets",
    group: "design-assets",
  },
] as const;
export type WorkspaceNavigationGroup = Readonly<{
  id: WorkspaceNavigationItem["group"];
  label: string;
  items: readonly WorkspaceNavigationItem[];
}>;

export const workspaceNavigationGroups: readonly WorkspaceNavigationGroup[] = [
  {
    id: "workspace",
    label: "Workspace",
    items: workspaceNavigation.filter((item) => item.group === "workspace"),
  },
  {
    id: "data",
    label: "Data",
    items: workspaceNavigation.filter((item) => item.group === "data"),
  },
  {
    id: "design-assets",
    label: "Design Assets",
    items: workspaceNavigation.filter((item) => item.group === "design-assets"),
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
    sectionLabel: "Workspace",
    pageTitle: "Dashboard",
  },
  {
    href: "/dataset",
    sectionLabel: "Workspace",
    pageTitle: "Dataset",
  },
  {
    href: "/data-ingestion",
    sectionLabel: "Data",
    pageTitle: "Data Ingestion",
  },
  {
    href: "/raw-data",
    sectionLabel: "Data",
    pageTitle: "Raw Data Browser",
  },
  {
    href: "/data-browser",
    sectionLabel: "Data",
    pageTitle: "Raw Data Browser",
  },
  {
    href: "/schemas",
    sectionLabel: "Design Assets",
    pageTitle: "Design Assets",
  },
  {
    href: "/circuit-definition-editor",
    sectionLabel: "Design Assets",
    pageTitle: "Schema Editor",
  },
  {
    href: "/tasks",
    sectionLabel: "Workspace",
    pageTitle: "Tasks",
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
