"use client";

import type { SchemdrawPreviewMetadata } from "@/features/circuit-schemdraw/lib/api";
import { deriveSvgViewport } from "@/features/circuit-schemdraw/lib/svg-viewer";

type SchemdrawDownloadFormat = "svg" | "png";

export function buildSchemdrawPreviewFilename(input: Readonly<{
  definitionName: string | null;
  requestId: string;
  format: SchemdrawDownloadFormat;
}>) {
  const baseName = (input.definitionName ?? "schemdraw-preview")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  const safeBaseName = baseName.length > 0 ? baseName : "schemdraw-preview";

  return `${safeBaseName}-${input.requestId}.${input.format}`;
}

export function downloadSchemdrawSvg(input: Readonly<{
  svgText: string;
  filename: string;
}>) {
  const blob = new Blob([input.svgText], {
    type: "image/svg+xml;charset=utf-8",
  });
  downloadBlob(blob, input.filename);
}

export async function downloadSchemdrawPng(input: Readonly<{
  svgText: string;
  previewMetadata: SchemdrawPreviewMetadata | null;
  filename: string;
}>) {
  const viewport = deriveSvgViewport(input.svgText, input.previewMetadata);
  if (!viewport) {
    throw new Error("PNG export requires a valid SVG viewport.");
  }

  const svgBlob = new Blob([input.svgText], {
    type: "image/svg+xml;charset=utf-8",
  });
  const svgUrl = window.URL.createObjectURL(svgBlob);

  try {
    const image = await loadImage(svgUrl);
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(viewport.width));
    canvas.height = Math.max(1, Math.round(viewport.height));

    const context = canvas.getContext("2d");
    if (!context) {
      throw new Error("PNG export could not open a drawing context.");
    }

    context.clearRect(0, 0, canvas.width, canvas.height);
    context.drawImage(image, 0, 0, canvas.width, canvas.height);

    const pngBlob = await canvasToBlob(canvas);
    downloadBlob(pngBlob, input.filename);
  } finally {
    window.URL.revokeObjectURL(svgUrl);
  }
}

function downloadBlob(blob: Blob, filename: string) {
  const objectUrl = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  anchor.rel = "noopener";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(objectUrl);
}

function loadImage(src: string) {
  return new Promise<HTMLImageElement>((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("PNG export could not rasterize the SVG preview."));
    image.src = src;
  });
}

function canvasToBlob(canvas: HTMLCanvasElement) {
  return new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) {
        resolve(blob);
        return;
      }

      reject(new Error("PNG export could not generate an image blob."));
    }, "image/png");
  });
}
