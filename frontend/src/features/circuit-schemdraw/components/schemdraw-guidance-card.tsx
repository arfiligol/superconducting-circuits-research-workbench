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
            Writing Rules
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
            These are the minimum rules for source that this page, the backend, and AI assistants
            can inspect reliably.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-[11px]">
          <SurfaceTag tone="default">Page rules</SurfaceTag>
          <SurfaceTag tone="primary">Backend checked</SurfaceTag>
        </div>
      </div>

      <div className="mt-4 space-y-3">
        <GuidanceItem
          icon={<FileCode2 className="h-4 w-4" />}
          label="Required"
          title="Define `build_drawing(relation)`"
          detail="The backend validates this entrypoint and calls it when you render from this page."
        />
        <GuidanceItem
          icon={<Bot className="h-4 w-4" />}
          label="Required"
          title="Return `schemdraw.Drawing`"
          detail="Keep the main output explicit instead of hiding success behind save-only side effects or opaque wrappers."
        />
        <GuidanceItem
          icon={<ShieldCheck className="h-4 w-4" />}
          label="Prefer"
          title="Keep imports and drawing flow easy to scan"
          detail="Show the main elements, labels, and connections clearly so both humans and AI can follow the circuit-building flow."
        />
        <GuidanceItem
          icon={<Bot className="h-4 w-4" />}
          label="Prefer"
          title="Avoid opaque helper magic"
          detail="Do not bury the render path behind deep indirection, dynamic code generation, or helpers that hide what gets drawn."
        />
        <GuidanceItem
          icon={<ShieldCheck className="h-4 w-4" />}
          label="Required"
          title="Treat backend render as final authority"
          detail="Local editor cues are draft-only. Syntax validity and the adopted preview are decided by the backend response."
        />
      </div>
    </section>
  );
}

function GuidanceItem({
  icon,
  label,
  title,
  detail,
}: Readonly<{
  icon: ReactNode;
  label: "Required" | "Prefer";
  title: string;
  detail: string;
}>) {
  return (
    <div className="rounded-[0.95rem] border border-border bg-surface px-4 py-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div className="flex min-w-0 gap-3">
          <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-border bg-background text-foreground">
            {icon}
          </span>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-foreground">{title}</p>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{detail}</p>
          </div>
        </div>
        <SurfaceTag tone={label === "Required" ? "primary" : "default"}>{label}</SurfaceTag>
      </div>
    </div>
  );
}
