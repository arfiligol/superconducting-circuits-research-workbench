"use client";

import { useEffect, useRef, useState } from "react";

const PREVIEW_DRAWER_MIN_VISIBLE_HEIGHT = 220;
const PREVIEW_DRAWER_EXIT_HYSTERESIS = 12;

type PreviewDrawerFrame = Readonly<{
  left: number;
  top: number;
  width: number;
}> | null;

function resolvePreviewDrawerTopOffset() {
  if (typeof window === "undefined") {
    return 112;
  }

  const rawValue = getComputedStyle(document.documentElement)
    .getPropertyValue("--shell-header-height")
    .trim();
  const headerHeight = Number.parseFloat(rawValue);

  return (Number.isFinite(headerHeight) ? headerHeight : 96) + 16;
}

export function useRawDataPreviewDrawer({
  enabled,
}: Readonly<{
  enabled: boolean;
}>) {
  const traceSummariesSectionRef = useRef<HTMLElement | null>(null);
  const desktopPreviewRailRef = useRef<HTMLDivElement | null>(null);
  const [isDesktopPreviewDrawerPinned, setIsDesktopPreviewDrawerPinned] = useState(false);
  const [desktopPreviewDrawerFrame, setDesktopPreviewDrawerFrame] =
    useState<PreviewDrawerFrame>(null);

  useEffect(() => {
    if (!enabled) {
      setIsDesktopPreviewDrawerPinned(false);
      return;
    }

    let frameId = 0;

    const updatePinnedState = () => {
      frameId = 0;
      const traceSection = traceSummariesSectionRef.current;
      const previewRail = desktopPreviewRailRef.current;
      if (!traceSection || !previewRail) {
        return;
      }

      const topOffset = resolvePreviewDrawerTopOffset();
      const traceSectionRect = traceSection.getBoundingClientRect();
      const previewRailRect = previewRail.getBoundingClientRect();
      const canPin =
        traceSectionRect.bottom > topOffset + PREVIEW_DRAWER_MIN_VISIBLE_HEIGHT;
      const nextPinned = isDesktopPreviewDrawerPinned
        ? canPin && previewRailRect.top <= topOffset + PREVIEW_DRAWER_EXIT_HYSTERESIS
        : canPin && previewRailRect.top <= topOffset;

      setIsDesktopPreviewDrawerPinned((current) =>
        current === nextPinned ? current : nextPinned,
      );
      setDesktopPreviewDrawerFrame((current) => {
        const nextFrame = {
          left: previewRailRect.left,
          top: previewRailRect.top,
          width: previewRailRect.width,
        };

        if (
          current &&
          Math.abs(current.left - nextFrame.left) < 0.5 &&
          Math.abs(current.top - nextFrame.top) < 0.5 &&
          Math.abs(current.width - nextFrame.width) < 0.5
        ) {
          return current;
        }

        return nextFrame;
      });
    };

    const schedulePinnedStateUpdate = () => {
      if (frameId !== 0) {
        return;
      }

      frameId = window.requestAnimationFrame(updatePinnedState);
    };

    updatePinnedState();

    window.addEventListener("scroll", schedulePinnedStateUpdate, { passive: true });
    window.addEventListener("resize", schedulePinnedStateUpdate);

    return () => {
      if (frameId !== 0) {
        window.cancelAnimationFrame(frameId);
      }

      window.removeEventListener("scroll", schedulePinnedStateUpdate);
      window.removeEventListener("resize", schedulePinnedStateUpdate);
    };
  }, [enabled, isDesktopPreviewDrawerPinned]);

  return {
    traceSummariesSectionRef,
    desktopPreviewRailRef,
    isDesktopPreviewDrawerPinned,
    desktopPreviewDrawerFrame,
    desktopPreviewDrawerTop:
      desktopPreviewDrawerFrame === null
        ? null
        : Math.max(resolvePreviewDrawerTopOffset(), desktopPreviewDrawerFrame.top),
  };
}
