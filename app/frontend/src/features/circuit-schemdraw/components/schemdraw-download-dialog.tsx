"use client";

import type { ReactNode } from "react";
import { Download, FileImage, FileType2, LoaderCircle } from "lucide-react";

import { SurfaceActionButton, cx } from "@/features/shared/components/surface-kit";

type SchemdrawDownloadFormat = "svg" | "png";

export function SchemdrawDownloadDialog({
  open,
  isPendingFormat,
  onClose,
  onDownload,
}: Readonly<{
  open: boolean;
  isPendingFormat: SchemdrawDownloadFormat | null;
  onClose: () => void;
  onDownload: (format: SchemdrawDownloadFormat) => void;
}>) {
  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/75 px-4 backdrop-blur-sm">
      <div className="w-full max-w-xl rounded-[1rem] border border-border bg-card px-5 py-5 shadow-[0_24px_80px_rgba(0,0,0,0.35)]">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 inline-flex h-10 w-10 items-center justify-center rounded-full border border-primary/30 bg-primary/10 text-primary">
            <Download className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="text-base font-semibold text-foreground">Download Preview</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Save the latest adopted preview as the authoritative backend SVG or as a PNG derived
              from that same SVG.
            </p>
          </div>
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-2">
          <DownloadOptionCard
            title="SVG"
            description="Downloads the current authoritative backend preview payload directly."
            icon={<FileType2 className="h-4 w-4" />}
            isPending={isPendingFormat === "svg"}
            onClick={() => onDownload("svg")}
          />
          <DownloadOptionCard
            title="PNG"
            description="Rasterizes the same authoritative SVG preview on the frontend for sharing."
            icon={<FileImage className="h-4 w-4" />}
            isPending={isPendingFormat === "png"}
            onClick={() => onDownload("png")}
          />
        </div>

        <div className="mt-5 flex justify-end">
          <SurfaceActionButton
            shape="soft"
            onClick={onClose}
            disabled={isPendingFormat !== null}
          >
            Close
          </SurfaceActionButton>
        </div>
      </div>
    </div>
  );
}

function DownloadOptionCard({
  title,
  description,
  icon,
  isPending,
  onClick,
}: Readonly<{
  title: string;
  description: string;
  icon: ReactNode;
  isPending: boolean;
  onClick: () => void;
}>) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={isPending}
      className={cx(
        "flex cursor-pointer flex-col items-start gap-3 rounded-[0.95rem] border border-border bg-surface px-4 py-4 text-left transition hover:border-primary/30 hover:bg-primary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/25 disabled:cursor-not-allowed disabled:opacity-65",
      )}
    >
      <span className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-border bg-background text-foreground">
        {isPending ? <LoaderCircle className="h-4 w-4 animate-spin" /> : icon}
      </span>
      <div>
        <p className="text-sm font-semibold text-foreground">{title}</p>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">{description}</p>
      </div>
    </button>
  );
}
