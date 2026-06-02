import { Suspense } from "react";

import { WorkspaceShell } from "@/components/layout/workspace-shell";

type WorkspaceLayoutProps = Readonly<{
  children: React.ReactNode;
}>;

export const dynamic = "force-dynamic";

export default function WorkspaceLayout({ children }: WorkspaceLayoutProps) {
  return (
    <Suspense fallback={<div className="min-h-screen bg-app" />}>
      <WorkspaceShell>{children}</WorkspaceShell>
    </Suspense>
  );
}
