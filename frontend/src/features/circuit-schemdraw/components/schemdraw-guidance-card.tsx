"use client";

import type { ReactNode } from "react";
import { Bot, FileCode2, ShieldCheck } from "lucide-react";

import { SurfaceTag } from "@/features/shared/components/surface-kit";

export function SchemdrawGuidanceCard() {
  return (
    <section className="rounded-[1rem] border border-border bg-card px-5 py-5 shadow-[0_10px_30px_rgba(0,0,0,0.08)]">
      <div className="flex flex-col gap-4 border-b border-border/80 pb-4 md:flex-row md:items-start md:justify-between">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Authoring Guidance
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
            Keep the source explicit and structurally readable. The backend is the syntax and render
            authority for this page.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-[11px]">
          <SurfaceTag tone="default">Compact guidance</SurfaceTag>
          <SurfaceTag tone="primary">Backend authority</SurfaceTag>
        </div>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <GuidanceItem
          icon={<FileCode2 className="h-4 w-4" />}
          title="Keep structure explicit"
          detail="Use clear imports, a visible build entrypoint, and readable naming so the source stays inspectable."
        />
        <GuidanceItem
          icon={<Bot className="h-4 w-4" />}
          title="Write for humans and AI"
          detail="Avoid opaque helper magic. Keep the flow easy to continue editing from the same file later."
        />
        <GuidanceItem
          icon={<ShieldCheck className="h-4 w-4" />}
          title="Trust backend validation"
          detail="Local editor cues are only draft feedback. The backend decides syntax validity and the adopted preview."
        />
      </div>
    </section>
  );
}

function GuidanceItem({
  icon,
  title,
  detail,
}: Readonly<{
  icon: ReactNode;
  title: string;
  detail: string;
}>) {
  return (
    <div className="rounded-[0.95rem] border border-border bg-surface px-4 py-4">
      <span className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-border bg-background text-foreground">
        {icon}
      </span>
      <p className="mt-3 text-sm font-semibold text-foreground">{title}</p>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">{detail}</p>
    </div>
  );
}
