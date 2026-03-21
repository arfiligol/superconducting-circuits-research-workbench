"""Shared browser-side helpers for interactive schematic previews and formatting."""

from __future__ import annotations

import json

_RUFF_WASM_WEB_URL = "https://unpkg.com/@astral-sh/ruff-wasm-web@0.15.4/ruff_wasm.js"


def shared_frontend_tooling_head_html() -> str:
    """Return shared <head> HTML for interactive SVG preview and Ruff WASM helpers."""
    return f"""
    <script>
    (() => {{
      if (window.scCircuitPreview) return;

      const previewStates = new Map();
      const MIN_ZOOM = 1.0;
      const MAX_ZOOM = 20.0;
      const ZOOM_STEP = 1.2;

      const clampZoom = (value) => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, Number(value) || 1));
      const zoomText = (value) => `${{Math.round(clampZoom(value) * 100)}}%`;

      function parseViewBox(svg) {{
        const raw = svg?.getAttribute("viewBox");
        if (raw) {{
          const parts = raw
            .trim()
            .split(/[\\s,]+/)
            .map(Number);
          if (parts.length === 4 && parts.every(Number.isFinite)) {{
            return {{ x: parts[0], y: parts[1], width: parts[2], height: parts[3] }};
          }}
        }}

        const width =
          Number(svg?.getAttribute("width")?.replace(/pt$/, "")) ||
          Number(svg?.dataset?.width) ||
          100;
        const height =
          Number(svg?.getAttribute("height")?.replace(/pt$/, "")) ||
          Number(svg?.dataset?.height) ||
          100;
        return {{ x: 0, y: 0, width, height }};
      }}

      function viewBoxToString(viewBox) {{
        return `${{viewBox.x}} ${{viewBox.y}} ${{viewBox.width}} ${{viewBox.height}}`;
      }}

      function cloneViewBox(viewBox) {{
        return {{ x: viewBox.x, y: viewBox.y, width: viewBox.width, height: viewBox.height }};
      }}

      function updateZoomLabel(state) {{
        if (!state || !state.labelId) return;
        const label = document.getElementById(state.labelId);
        if (label) label.textContent = zoomText(state.zoom);
      }}

      function syncViewportSize(state) {{
        if (!state?.svg || !state?.viewport) return;
        state.svg.style.display = "block";
        state.svg.style.width = "100%";
        state.svg.style.height = `${{Math.max(state.viewport.clientHeight || 0, 256)}}px`;
        state.svg.style.maxWidth = "none";
        state.svg.style.userSelect = "none";
        state.svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
      }}

      function syncState(state) {{
        if (!state || !state.currentViewBox || !state.sourceViewBox) {{
          if (state) {{
            state.zoom = 1;
            updateZoomLabel(state);
          }}
          return;
        }}
        state.zoom = clampZoom(state.sourceViewBox.width / state.currentViewBox.width);
        updateZoomLabel(state);
      }}

      function clampViewBoxToSource(state, candidate) {{
        const source = state.sourceViewBox;
        const width = Math.min(candidate.width, source.width);
        const height = Math.min(candidate.height, source.height);
        const minX = source.x;
        const maxX = source.x + source.width - width;
        const minY = source.y;
        const maxY = source.y + source.height - height;
        return {{
          x: Math.min(maxX, Math.max(minX, candidate.x)),
          y: Math.min(maxY, Math.max(minY, candidate.y)),
          width,
          height,
        }};
      }}

      function applyViewBox(state, viewBox) {{
        if (!state?.svg) return false;
        const nextViewBox = clampViewBoxToSource(state, viewBox);
        state.currentViewBox = nextViewBox;
        state.svg.setAttribute("viewBox", viewBoxToString(nextViewBox));
        syncState(state);
        return true;
      }}

      function getCenterRatios(state) {{
        const source = state.sourceViewBox;
        const current = state.currentViewBox || source;
        return {{
          x: ((current.x + current.width / 2) - source.x) / source.width,
          y: ((current.y + current.height / 2) - source.y) / source.height,
        }};
      }}

      function buildViewBoxForZoom(state, zoom, centerRatios) {{
        const source = state.sourceViewBox;
        const nextZoom = clampZoom(zoom);
        const width = source.width / nextZoom;
        const height = source.height / nextZoom;
        const centerX = source.x + source.width * (centerRatios?.x ?? 0.5);
        const centerY = source.y + source.height * (centerRatios?.y ?? 0.5);
        return {{
          x: centerX - width / 2,
          y: centerY - height / 2,
          width,
          height,
        }};
      }}

      function fitPreview(state) {{
        if (!state) return false;
        return applyViewBox(state, cloneViewBox(state.sourceViewBox));
      }}

      function refreshPreview(state, preserveRelative = true) {{
        if (!state) return false;
        syncViewportSize(state);
        if (!preserveRelative || !state.currentViewBox || !state.sourceViewBox) {{
          return fitPreview(state);
        }}
        const centerRatios = getCenterRatios(state);
        const nextViewBox = buildViewBoxForZoom(state, state.zoom || 1, centerRatios);
        return applyViewBox(state, nextViewBox);
      }}

      function zoomPreview(state, factor) {{
        if (!state || !state.sourceViewBox) return false;
        const centerRatios = getCenterRatios(state);
        return applyViewBox(
          state,
          buildViewBoxForZoom(state, clampZoom((state.zoom || 1) * factor), centerRatios)
        );
      }}

      function panPreviewByPixels(state, deltaX, deltaY) {{
        if (!state || !state.currentViewBox || !state.viewport) return false;
        const viewportWidth = Math.max(state.viewport.clientWidth || 0, 1);
        const viewportHeight = Math.max(state.viewport.clientHeight || 0, 1);
        const unitsPerPixelX = state.currentViewBox.width / viewportWidth;
        const unitsPerPixelY = state.currentViewBox.height / viewportHeight;
        return applyViewBox(state, {{
          x: state.currentViewBox.x + deltaX * unitsPerPixelX,
          y: state.currentViewBox.y + deltaY * unitsPerPixelY,
          width: state.currentViewBox.width,
          height: state.currentViewBox.height,
        }});
      }}

      function ensureState(rootId, labelId) {{
        const root = document.getElementById(rootId);
        if (!root) return null;

        let state = previewStates.get(rootId);
        if (state && state.root !== root) {{
          previewStates.delete(rootId);
          state = null;
        }}

        if (!state) {{
          root.innerHTML = `
            <div class="schematic-panzoom-viewport" tabindex="0">
              <div class="schematic-panzoom-host"></div>
            </div>
          `;

          const viewport = root.querySelector(".schematic-panzoom-viewport");
          const host = root.querySelector(".schematic-panzoom-host");

          state = {{
            root,
            viewport,
            host,
            svg: null,
            labelId: labelId || "",
            schemaKey: "",
            sourceViewBox: null,
            currentViewBox: null,
            zoom: 1,
            dragPointerId: null,
            dragLastX: 0,
            dragLastY: 0,
          }};

          viewport.addEventListener(
            "wheel",
            (event) => {{
              if (!state.svg) return;
              if (event.ctrlKey || event.metaKey) {{
                event.preventDefault();
                const factor = event.deltaY < 0 ? ZOOM_STEP : (1 / ZOOM_STEP);
                zoomPreview(state, factor);
                return;
              }}

              event.preventDefault();
              const deltaX = event.shiftKey && !event.deltaX ? event.deltaY : event.deltaX;
              const deltaY = event.shiftKey && !event.deltaX ? 0 : event.deltaY;
              panPreviewByPixels(state, deltaX, deltaY);
            }},
            {{ passive: false }}
          );

          viewport.addEventListener("pointerdown", (event) => {{
            if (!state.svg) return;
            state.dragPointerId = event.pointerId;
            state.dragLastX = event.clientX;
            state.dragLastY = event.clientY;
            viewport.setPointerCapture(event.pointerId);
            viewport.focus();
            viewport.dataset.dragging = "1";
          }});

          viewport.addEventListener("pointermove", (event) => {{
            if (state.dragPointerId !== event.pointerId) return;
            const deltaX = event.clientX - state.dragLastX;
            const deltaY = event.clientY - state.dragLastY;
            state.dragLastX = event.clientX;
            state.dragLastY = event.clientY;
            panPreviewByPixels(state, -deltaX, -deltaY);
          }});

          const finishDrag = (event) => {{
            if (state.dragPointerId !== event.pointerId) return;
            state.dragPointerId = null;
            viewport.dataset.dragging = "0";
            try {{
              viewport.releasePointerCapture(event.pointerId);
            }} catch (_error) {{
              // Ignore if capture already released.
            }}
          }};

          viewport.addEventListener("pointerup", finishDrag);
          viewport.addEventListener("pointercancel", finishDrag);

          viewport.addEventListener("keydown", (event) => {{
            if (!(event.ctrlKey || event.metaKey)) return;
            const key = event.key;
            if (key === "0") {{
              event.preventDefault();
              fitPreview(state);
              return;
            }}
            if (key === "+" || key === "=") {{
              event.preventDefault();
              zoomPreview(state, ZOOM_STEP);
              return;
            }}
            if (key === "-") {{
              event.preventDefault();
              zoomPreview(state, 1 / ZOOM_STEP);
            }}
          }});

          if (window.ResizeObserver) {{
            const resizeObserver = new ResizeObserver(() => {{
              if (state.svg) {{
                refreshPreview(state, true);
              }}
            }});
            resizeObserver.observe(viewport);
            state.resizeObserver = resizeObserver;
          }}

          previewStates.set(rootId, state);
        }}

        if (labelId) {{
          state.labelId = labelId;
        }}

        updateZoomLabel(state);
        return state;
      }}

      function resetPreview(state) {{
        if (!state) return false;
        return fitPreview(state);
      }}

      window.scCircuitPreview = {{
        render(payload) {{
          const state = ensureState(payload.rootId, payload.labelId);
          if (!state) return false;

          const nextSchemaKey = String(payload.schemaKey || "");
          const schemaChanged = state.schemaKey !== nextSchemaKey;
          const previousZoom = state.zoom || 1;
          const previousCenter =
            state.currentViewBox && state.sourceViewBox
              ? getCenterRatios(state)
              : {{ x: 0.5, y: 0.5 }};

          state.host.innerHTML =
            payload.svgContent ||
            payload.emptyHtml ||
            "<div class='text-muted text-sm'>No preview</div>";
          state.svg = state.host.querySelector("svg");
          state.schemaKey = nextSchemaKey;

          if (!state.svg) {{
            state.sourceViewBox = null;
            state.currentViewBox = null;
            state.zoom = 1;
            updateZoomLabel(state);
            return true;
          }}

          syncViewportSize(state);
          state.sourceViewBox = parseViewBox(state.svg);
          state.currentViewBox = cloneViewBox(state.sourceViewBox);
          state.svg.setAttribute("viewBox", viewBoxToString(state.sourceViewBox));

          if (schemaChanged) {{
            resetPreview(state);
          }} else {{
            applyViewBox(
              state,
              buildViewBoxForZoom(state, previousZoom, previousCenter)
            );
          }}
          return true;
        }},
        zoomIn(rootId) {{
          const state = ensureState(rootId, "");
          return zoomPreview(state, ZOOM_STEP);
        }},
        zoomOut(rootId) {{
          const state = ensureState(rootId, "");
          return zoomPreview(state, 1 / ZOOM_STEP);
        }},
        reset(rootId) {{
          const state = ensureState(rootId, "");
          return resetPreview(state);
        }},
      }};
    }})();

    (() => {{
      if (window.scSchemaFormatter) return;

      const ruffModuleUrl = {json.dumps(_RUFF_WASM_WEB_URL)};
      let ruffModulePromise = null;

      async function loadRuff() {{
        if (!ruffModulePromise) {{
          ruffModulePromise = import(ruffModuleUrl).then(async (mod) => {{
            await mod.default();
            return mod;
          }});
        }}
        return ruffModulePromise;
      }}

      window.scSchemaFormatter = {{
        async format(sourceText) {{
          let workspace = null;
          try {{
            const mod = await loadRuff();
            workspace = new mod.Workspace(
              {{
                "line-length": 88,
                "indent-width": 4,
                format: {{
                  "indent-style": "space",
                  "quote-style": "double",
                }},
              }},
              mod.PositionEncoding.Utf16
            );
            const formatted = workspace.format(String(sourceText || ""));
            return {{ ok: true, text: formatted }};
          }} catch (error) {{
            return {{
              ok: false,
              error: String(error && error.message ? error.message : error),
            }};
          }} finally {{
            if (workspace && typeof workspace.free === "function") {{
              workspace.free();
            }}
          }}
        }},
        attachHotkey(buttonId, scopeId) {{
          const scope = document.getElementById(scopeId);
          if (!scope || scope.dataset.schemaHotkeyBound === "1") return false;

          scope.dataset.schemaHotkeyBound = "1";
          scope.addEventListener("keydown", (event) => {{
            const wantsFormat =
              (event.ctrlKey || event.metaKey) &&
              event.shiftKey &&
              !event.altKey &&
              event.key.toLowerCase() === "f";
            if (!wantsFormat) return;

            const button = document.getElementById(buttonId);
            if (!button) return;

            event.preventDefault();
            button.click();
          }});
          return true;
        }},
      }};
    }})();
    </script>
    """


def build_schematic_preview_render_js(
    *,
    root_id: str,
    label_id: str,
    svg_content: str,
    schema_key: str,
    empty_html: str | None = None,
) -> str:
    """Build client-side render call for a schematic preview."""
    payload = {
        "rootId": root_id,
        "labelId": label_id,
        "svgContent": svg_content,
        "schemaKey": schema_key,
    }
    if empty_html is not None:
        payload["emptyHtml"] = empty_html
    return f"window.scCircuitPreview?.render({json.dumps(payload)});"


def build_schematic_preview_action_js(*, action: str, root_id: str) -> str:
    """Build client-side preview action call."""
    if action not in {"zoomIn", "zoomOut", "reset"}:
        raise ValueError(f"Unsupported preview action: {action}")
    return f"window.scCircuitPreview?.{action}({json.dumps(root_id)});"


def build_schema_formatter_js(source_text: str) -> str:
    """Build client-side Ruff WASM format call."""
    return f"return await window.scSchemaFormatter?.format({json.dumps(source_text)});"


def build_schema_formatter_hotkey_js(*, button_id: str, scope_id: str) -> str:
    """Build client-side hotkey binding call for the schema formatter."""
    return (
        f"window.scSchemaFormatter?.attachHotkey({json.dumps(button_id)}, {json.dumps(scope_id)});"
    )
