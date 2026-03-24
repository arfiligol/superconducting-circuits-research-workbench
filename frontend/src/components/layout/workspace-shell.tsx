"use client";

import { Suspense, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { Menu } from "lucide-react";

import { WorkspaceHeader } from "@/components/layout/workspace-header";
import { WorkspaceNav } from "@/components/layout/workspace-nav";

type WorkspaceShellProps = Readonly<{
  children: React.ReactNode;
}>;

export function WorkspaceShell({ children }: WorkspaceShellProps) {
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [desktopSidebarCollapsed, setDesktopSidebarCollapsed] = useState(false);
  const headerRef = useRef<HTMLElement | null>(null);
  const [shellHeaderHeight, setShellHeaderHeight] = useState(96);

  function closeSidebar() {
    setMobileSidebarOpen(false);
  }

  useEffect(() => {
    const headerElement = headerRef.current;
    if (!headerElement) {
      return;
    }

    const updateHeaderHeight = () => {
      setShellHeaderHeight(Math.ceil(headerElement.getBoundingClientRect().height));
    };

    updateHeaderHeight();

    if (typeof ResizeObserver === "undefined") {
      return;
    }

    const observer = new ResizeObserver(() => {
      updateHeaderHeight();
    });
    observer.observe(headerElement);

    return () => {
      observer.disconnect();
    };
  }, []);

  const shellChromeStyle = useMemo(
    () =>
      ({
        "--shell-header-height": `${shellHeaderHeight}px`,
        "--shell-sidebar-width": desktopSidebarCollapsed ? "0px" : "220px",
      }) as CSSProperties,
    [desktopSidebarCollapsed, shellHeaderHeight],
  );

  useEffect(() => {
    document.documentElement.style.setProperty("--shell-header-height", `${shellHeaderHeight}px`);
    document.documentElement.style.setProperty(
      "--shell-sidebar-width",
      desktopSidebarCollapsed ? "0px" : "220px",
    );

    return () => {
      document.documentElement.style.removeProperty("--shell-header-height");
      document.documentElement.style.removeProperty("--shell-sidebar-width");
    };
  }, [desktopSidebarCollapsed, shellHeaderHeight]);

  return (
    <div
      style={shellChromeStyle}
      className="min-h-screen overflow-x-hidden bg-app pt-[var(--shell-header-height)] text-foreground"
    >
      {mobileSidebarOpen ? (
        <button
          type="button"
          aria-label="Close navigation menu"
          className="fixed inset-x-0 bottom-0 top-[var(--shell-header-height)] z-30 bg-slate-950/45 lg:hidden"
          onClick={closeSidebar}
        />
      ) : null}

      <header
        ref={headerRef}
        className="fixed inset-x-0 top-0 z-50 border-b border-border/80 bg-header/95 shadow-[0_12px_32px_rgba(15,23,42,0.14)] backdrop-blur supports-[backdrop-filter]:bg-header/80"
      >
        <div className="flex min-h-[96px] items-center gap-4 px-4 py-4 md:px-6">
          <button
            type="button"
            aria-label="Toggle navigation menu"
            onClick={() => {
              if (window.innerWidth < 1024) {
                setMobileSidebarOpen((open) => !open);
                return;
              }

              setDesktopSidebarCollapsed((collapsed) => !collapsed);
            }}
            className="inline-flex h-10 w-10 cursor-pointer items-center justify-center rounded-lg border border-transparent text-primary transition hover:border-primary/35 hover:bg-primary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35 focus-visible:ring-offset-2 focus-visible:ring-offset-header"
          >
            <Menu size={18} strokeWidth={2} />
          </button>

          <Suspense fallback={<div className="min-w-0 flex-1" />}>
            <WorkspaceHeader />
          </Suspense>
        </div>
      </header>

      <div className="flex min-h-[calc(100vh-var(--shell-header-height))]">
        <aside
          className={[
            "fixed bottom-0 left-0 top-[var(--shell-header-height)] z-30 w-[220px] overflow-y-auto border-r border-border bg-sidebar px-4 py-5 transition-[transform,width,padding] duration-200 lg:w-[var(--shell-sidebar-width)] lg:translate-x-0 lg:shrink-0",
            mobileSidebarOpen ? "translate-x-0" : "-translate-x-full",
            desktopSidebarCollapsed ? "lg:w-0 lg:overflow-hidden lg:border-r-0 lg:px-0 lg:py-0" : "",
          ].join(" ")}
        >
          <WorkspaceNav onNavigate={closeSidebar} />
        </aside>

        <div className="flex min-w-0 flex-1 flex-col overflow-x-hidden bg-background transition-[padding] duration-200 lg:pl-[var(--shell-sidebar-width)]">
          <main className="flex-1 px-4 py-5 md:px-6 md:py-5">
            <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6">{children}</div>
          </main>
        </div>
      </div>
    </div>
  );
}
