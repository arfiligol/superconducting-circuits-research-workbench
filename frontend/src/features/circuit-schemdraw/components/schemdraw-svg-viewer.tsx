"use client";

import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type PointerEvent as ReactPointerEvent,
} from "react";
import { Maximize2, Move, RefreshCcw, ZoomIn, ZoomOut } from "lucide-react";

import type { SchemdrawPreviewMetadata } from "@/features/circuit-schemdraw/lib/api";
import {
  calculateFitTransform,
  deriveSvgViewport,
  panByStep,
  zoomAroundPoint,
  zoomViewerStep,
  type ViewerPanState,
} from "@/features/circuit-schemdraw/lib/svg-viewer";
import { cx } from "@/features/shared/components/surface-kit";

const FALLBACK_VIEWPORT = {
  width: 960,
  height: 720,
};

type ViewportSize = Readonly<{
  width: number;
  height: number;
}>;

type DragState = Readonly<{
  pointerId: number;
  originX: number;
  originY: number;
  panX: number;
  panY: number;
}>;

export function SchemdrawSvgViewer({
  svg,
  previewMetadata,
}: Readonly<{
  svg: string;
  previewMetadata: SchemdrawPreviewMetadata | null;
}>) {
  const viewerLabelId = useId();
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const [viewportSize, setViewportSize] = useState<ViewportSize>({ width: 0, height: 0 });
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState<ViewerPanState>({ x: 0, y: 0 });
  const [dragState, setDragState] = useState<DragState | null>(null);

  const svgViewport =
    useMemo(() => deriveSvgViewport(svg, previewMetadata), [previewMetadata, svg]) ??
    FALLBACK_VIEWPORT;
  const fitTransform = useMemo(() => {
    if (viewportSize.width <= 0 || viewportSize.height <= 0) {
      return calculateFitTransform(
        { width: FALLBACK_VIEWPORT.width, height: FALLBACK_VIEWPORT.height },
        svgViewport,
      );
    }

    return calculateFitTransform(viewportSize, svgViewport);
  }, [svgViewport, viewportSize]);

  useEffect(() => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
    setDragState(null);
  }, [svg]);

  useEffect(() => {
    const node = viewportRef.current;
    if (!node) {
      return;
    }

    const observer = new ResizeObserver((entries) => {
      const nextEntry = entries[0];
      if (!nextEntry) {
        return;
      }

      setViewportSize({
        width: nextEntry.contentRect.width,
        height: nextEntry.contentRect.height,
      });
    });

    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  function applyZoom(direction: "in" | "out") {
    const node = viewportRef.current;
    if (!node) {
      return;
    }

    const nextZoom = zoomViewerStep(zoom, direction);
    if (nextZoom === zoom) {
      return;
    }

    const rect = node.getBoundingClientRect();
    setPan((currentPan) =>
      zoomAroundPoint({
        baseTransform: fitTransform,
        currentZoom: zoom,
        nextZoom,
        currentPan,
        anchorX: rect.width / 2,
        anchorY: rect.height / 2,
      }),
    );
    setZoom(nextZoom);
  }

  function resetView() {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  }

  function fitToView() {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  }

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    switch (event.key) {
      case "+":
      case "=":
        event.preventDefault();
        applyZoom("in");
        return;
      case "-":
      case "_":
        event.preventDefault();
        applyZoom("out");
        return;
      case "0":
        event.preventDefault();
        resetView();
        return;
      case "f":
      case "F":
        event.preventDefault();
        fitToView();
        return;
      case "ArrowLeft":
        event.preventDefault();
        setPan((currentPan) => panByStep(currentPan, "left"));
        return;
      case "ArrowRight":
        event.preventDefault();
        setPan((currentPan) => panByStep(currentPan, "right"));
        return;
      case "ArrowUp":
        event.preventDefault();
        setPan((currentPan) => panByStep(currentPan, "up"));
        return;
      case "ArrowDown":
        event.preventDefault();
        setPan((currentPan) => panByStep(currentPan, "down"));
        return;
      default:
        return;
    }
  }

  function handlePointerDown(event: ReactPointerEvent<HTMLDivElement>) {
    if (event.button !== 0) {
      return;
    }

    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    setDragState({
      pointerId: event.pointerId,
      originX: event.clientX,
      originY: event.clientY,
      panX: pan.x,
      panY: pan.y,
    });
  }

  function handlePointerMove(event: ReactPointerEvent<HTMLDivElement>) {
    if (!dragState || dragState.pointerId !== event.pointerId) {
      return;
    }

    const deltaX = event.clientX - dragState.originX;
    const deltaY = event.clientY - dragState.originY;
    setPan({
      x: dragState.panX + deltaX,
      y: dragState.panY + deltaY,
    });
  }

  function handlePointerEnd(event: ReactPointerEvent<HTMLDivElement>) {
    if (!dragState || dragState.pointerId !== event.pointerId) {
      return;
    }

    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    setDragState(null);
  }

  const effectiveScale = fitTransform.scale * zoom;
  const transformStyle = {
    transform: `translate(${fitTransform.translateX + pan.x}px, ${fitTransform.translateY + pan.y}px) scale(${effectiveScale})`,
    transformOrigin: "0 0",
    width: `${svgViewport.width}px`,
    height: `${svgViewport.height}px`,
  } as const;

  return (
    <div className="mt-4 overflow-hidden rounded-[0.95rem] border border-border bg-white text-slate-900 shadow-[inset_0_1px_0_rgba(255,255,255,0.65)]">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200/90 bg-[linear-gradient(180deg,rgba(248,250,252,0.98),rgba(241,245,249,0.92))] px-4 py-3">
        <div className="min-w-0">
          <p id={viewerLabelId} className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-700">
            Preview viewer
          </p>
          <p className="mt-1 text-xs text-slate-600">Drag to pan. Use buttons or keyboard to inspect the SVG.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => applyZoom("out")}
            className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-700 transition hover:border-slate-400 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
          >
            <ZoomOut className="h-3.5 w-3.5" />
            Zoom out
          </button>
          <span className="rounded-full border border-slate-300 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-700">
            {Math.round(zoom * 100)}%
          </span>
          <button
            type="button"
            onClick={() => applyZoom("in")}
            className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-700 transition hover:border-slate-400 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
          >
            <ZoomIn className="h-3.5 w-3.5" />
            Zoom in
          </button>
          <button
            type="button"
            onClick={fitToView}
            className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-700 transition hover:border-slate-400 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
          >
            <Maximize2 className="h-3.5 w-3.5" />
            Fit to view
          </button>
          <button
            type="button"
            onClick={resetView}
            className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-700 transition hover:border-slate-400 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
          >
            <RefreshCcw className="h-3.5 w-3.5" />
            Reset view
          </button>
        </div>
      </div>

      <div
        ref={viewportRef}
        role="region"
        aria-labelledby={viewerLabelId}
        tabIndex={0}
        onKeyDown={handleKeyDown}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerEnd}
        onPointerCancel={handlePointerEnd}
        className={cx(
          "relative min-h-[520px] overflow-hidden bg-[radial-gradient(circle_at_top,rgba(148,163,184,0.18),transparent_42%),linear-gradient(180deg,#ffffff_0%,#f8fafc_100%)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40",
          dragState ? "cursor-grabbing" : "cursor-grab",
        )}
      >
        <div className="pointer-events-none absolute inset-x-4 bottom-4 z-10 flex items-center justify-between gap-3">
          <span className="rounded-full border border-slate-300/90 bg-white/92 px-3 py-1.5 text-[11px] font-medium text-slate-700 shadow-sm">
            <span className="inline-flex items-center gap-1.5">
              <Move className="h-3.5 w-3.5" />
              Drag to pan
            </span>
          </span>
          <span className="rounded-full border border-slate-300/90 bg-white/92 px-3 py-1.5 text-[11px] text-slate-600 shadow-sm">
            Shortcuts: +/- zoom, 0 reset, F fit, arrows pan
          </span>
        </div>

        <div className="absolute inset-0">
          <div
            className="absolute left-0 top-0 will-change-transform [&>svg]:block [&>svg]:h-full [&>svg]:w-full [&>svg]:max-w-none [&>svg]:overflow-visible"
            style={transformStyle}
            dangerouslySetInnerHTML={{ __html: svg }}
          />
        </div>
      </div>
    </div>
  );
}
