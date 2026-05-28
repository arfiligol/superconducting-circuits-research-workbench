"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  isWorkspaceNavigationItemActive,
  workspaceNavigationGroups,
} from "@/lib/navigation";

function cx(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

type WorkspaceNavProps = Readonly<{
  onNavigate?: () => void;
}>;

export function WorkspaceNav({ onNavigate }: WorkspaceNavProps) {
  const pathname = usePathname();

  return (
    <div className="flex h-full flex-col gap-6">
      <div className="space-y-6">
        {workspaceNavigationGroups.map((group) => (
          <section key={group.id}>
            <div className="px-2">
              <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
                {group.label}
              </p>
            </div>

            <nav className="mt-3 space-y-1.5">
              {group.items.map((item) => {
                const active = isWorkspaceNavigationItemActive(item, pathname);

                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={onNavigate}
                    className={cx(
                      "block rounded-[0.95rem] border px-3 py-2.5 transition",
                      active
                        ? "border-primary/35 bg-primary/10 text-foreground"
                        : "border-transparent text-foreground hover:border-primary/20 hover:bg-surface hover:text-primary",
                    )}
                  >
                    <span className="block min-w-0">
                      <span className="block truncate text-[15px] font-medium">{item.label}</span>
                    </span>
                  </Link>
                );
              })}
            </nav>
          </section>
        ))}
      </div>
    </div>
  );
}
