import type { SchemdrawPreviewMetadata } from "@/features/circuit-schemdraw/lib/api";

export type SvgViewportBox = Readonly<{
  minX: number;
  minY: number;
  width: number;
  height: number;
}>;

export type SvgViewportInfo = Readonly<{
  width: number;
  height: number;
  viewBox: SvgViewportBox | null;
}>;

export type ViewerFitTransform = Readonly<{
  scale: number;
  translateX: number;
  translateY: number;
}>;

export type ViewerPanState = Readonly<{
  x: number;
  y: number;
}>;

const SVG_OPEN_TAG_PATTERN = /<svg\b([^>]*)>/i;
const ATTRIBUTE_PATTERN = /([a-zA-Z_:][\w:.-]*)\s*=\s*"([^"]*)"/g;
const MIN_ZOOM = 0.35;
const MAX_ZOOM = 6;

export function deriveSvgViewport(
  svgText: string,
  previewMetadata: SchemdrawPreviewMetadata | null,
): SvgViewportInfo | null {
  const rawAttributes = extractSvgAttributes(svgText);
  const viewBox =
    parseSvgViewBox(previewMetadata?.view_box ?? null) ??
    parseSvgViewBox(rawAttributes.viewBox ?? rawAttributes.viewbox ?? null);
  const width =
    normalizePositiveNumber(previewMetadata?.width ?? null) ??
    parseSvgLength(rawAttributes.width ?? null) ??
    viewBox?.width ??
    null;
  const height =
    normalizePositiveNumber(previewMetadata?.height ?? null) ??
    parseSvgLength(rawAttributes.height ?? null) ??
    viewBox?.height ??
    null;

  if (!width || !height) {
    return null;
  }

  return {
    width,
    height,
    viewBox,
  };
}

export function calculateFitTransform(
  viewport: Readonly<{ width: number; height: number }>,
  content: Readonly<{ width: number; height: number }>,
  padding = 24,
): ViewerFitTransform {
  const usableWidth = Math.max(viewport.width - padding * 2, 1);
  const usableHeight = Math.max(viewport.height - padding * 2, 1);
  const scale = Math.min(usableWidth / content.width, usableHeight / content.height);
  const translateX = (viewport.width - content.width * scale) / 2;
  const translateY = (viewport.height - content.height * scale) / 2;

  return {
    scale,
    translateX,
    translateY,
  };
}

export function clampViewerZoom(zoom: number) {
  return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, zoom));
}

export function zoomViewerStep(currentZoom: number, direction: "in" | "out") {
  return clampViewerZoom(direction === "in" ? currentZoom * 1.2 : currentZoom / 1.2);
}

export function zoomAroundPoint(input: Readonly<{
  baseTransform: ViewerFitTransform;
  currentZoom: number;
  nextZoom: number;
  currentPan: ViewerPanState;
  anchorX: number;
  anchorY: number;
}>): ViewerPanState {
  const currentScale = input.baseTransform.scale * input.currentZoom;
  const nextScale = input.baseTransform.scale * input.nextZoom;
  if (currentScale <= 0 || nextScale <= 0) {
    return input.currentPan;
  }

  const localX =
    (input.anchorX - input.baseTransform.translateX - input.currentPan.x) / currentScale;
  const localY =
    (input.anchorY - input.baseTransform.translateY - input.currentPan.y) / currentScale;

  return {
    x: input.anchorX - input.baseTransform.translateX - localX * nextScale,
    y: input.anchorY - input.baseTransform.translateY - localY * nextScale,
  };
}

export function panByStep(
  currentPan: ViewerPanState,
  direction: "left" | "right" | "up" | "down",
  distance = 40,
): ViewerPanState {
  switch (direction) {
    case "left":
      return { x: currentPan.x - distance, y: currentPan.y };
    case "right":
      return { x: currentPan.x + distance, y: currentPan.y };
    case "up":
      return { x: currentPan.x, y: currentPan.y - distance };
    case "down":
    default:
      return { x: currentPan.x, y: currentPan.y + distance };
  }
}

function extractSvgAttributes(svgText: string) {
  const match = SVG_OPEN_TAG_PATTERN.exec(svgText);
  if (!match) {
    return {} as Record<string, string>;
  }

  const attributes = {} as Record<string, string>;
  for (const attributeMatch of match[1].matchAll(ATTRIBUTE_PATTERN)) {
    attributes[attributeMatch[1]] = attributeMatch[2];
  }
  return attributes;
}

function parseSvgViewBox(value: string | null) {
  if (!value) {
    return null;
  }

  const values = value
    .trim()
    .split(/[\s,]+/)
    .map((entry) => Number(entry))
    .filter((entry) => Number.isFinite(entry));

  if (values.length !== 4 || values[2] <= 0 || values[3] <= 0) {
    return null;
  }

  return {
    minX: values[0],
    minY: values[1],
    width: values[2],
    height: values[3],
  };
}

function parseSvgLength(value: string | null) {
  if (!value) {
    return null;
  }

  const normalized = Number.parseFloat(value);
  return normalizePositiveNumber(Number.isFinite(normalized) ? normalized : null);
}

function normalizePositiveNumber(value: number | null) {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) {
    return null;
  }
  return value;
}
