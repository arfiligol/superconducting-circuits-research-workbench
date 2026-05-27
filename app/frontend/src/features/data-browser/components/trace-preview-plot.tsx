"use client";

import { useMemo, type CSSProperties, type ComponentType } from "react";
import dynamic from "next/dynamic";
import { useTheme } from "next-themes";

type PlotComponentProps = Readonly<{
  data: readonly Record<string, unknown>[];
  layout: Record<string, unknown>;
  config: Record<string, unknown>;
  className?: string;
  style?: CSSProperties;
  useResizeHandler?: boolean;
}>;

const Plot = dynamic<PlotComponentProps>(
  () => import("react-plotly.js").then((module) => module.default as ComponentType<PlotComponentProps>),
  {
    ssr: false,
  },
);

type TracePreviewPlotProps = Readonly<{
  x: readonly number[];
  y: readonly number[];
  xLabel: string;
  yLabel: string;
  title: string;
}>;

export function TracePreviewPlot({
  x,
  y,
  xLabel,
  yLabel,
  title,
}: TracePreviewPlotProps) {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme !== "light";
  const axisColor = isDark ? "#e7edf6" : "#0f172a";
  const gridColor = isDark ? "rgba(148, 163, 184, 0.22)" : "rgba(148, 163, 184, 0.18)";
  const lineColor = isDark ? "rgba(148, 163, 184, 0.42)" : "rgba(148, 163, 184, 0.3)";
  const layout = useMemo(
    () => ({
      title: undefined,
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      margin: { t: 18, r: 18, b: 52, l: 58 },
      xaxis: {
        title: {
          text: xLabel,
          standoff: 16,
          font: { color: axisColor },
        },
        tickfont: {
          color: axisColor,
        },
        zeroline: false,
        gridcolor: gridColor,
        linecolor: lineColor,
        tickcolor: lineColor,
        automargin: true,
      },
      yaxis: {
        title: {
          text: yLabel,
          standoff: 14,
          font: { color: axisColor },
        },
        tickfont: {
          color: axisColor,
        },
        zeroline: false,
        gridcolor: gridColor,
        linecolor: lineColor,
        tickcolor: lineColor,
        automargin: true,
      },
      font: {
        color: axisColor,
      },
    }),
    [axisColor, gridColor, lineColor, xLabel, yLabel],
  );

  return (
    <div className="overflow-hidden rounded-[0.95rem] border border-border/80 bg-background">
      <Plot
        data={[
          {
            type: "scatter",
            mode: "lines+markers",
            x,
            y,
            line: {
              color: "#2563eb",
              width: 2.5,
            },
            marker: {
              color: "#1d4ed8",
              size: 5,
            },
            hovertemplate: `${xLabel}: %{x}<br>${yLabel}: %{y}<extra>${title}</extra>`,
          },
        ]}
        layout={layout}
        config={{
          displaylogo: false,
          responsive: true,
          modeBarButtonsToRemove: [
            "select2d",
            "lasso2d",
            "autoScale2d",
            "toggleSpikelines",
          ],
        }}
        className="h-[340px] w-full"
        style={{ width: "100%", height: "340px" }}
        useResizeHandler
      />
    </div>
  );
}
