"use client";

import type { CSSProperties, ComponentType } from "react";
import dynamic from "next/dynamic";

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
            hovertemplate: `%{x}<br>%{y}<extra>${title}</extra>`,
          },
        ]}
        layout={{
          title: undefined,
          paper_bgcolor: "rgba(0,0,0,0)",
          plot_bgcolor: "rgba(0,0,0,0)",
          margin: { t: 18, r: 18, b: 52, l: 58 },
          xaxis: {
            title: xLabel,
            zeroline: false,
            gridcolor: "rgba(148, 163, 184, 0.18)",
            linecolor: "rgba(148, 163, 184, 0.3)",
          },
          yaxis: {
            title: yLabel,
            zeroline: false,
            gridcolor: "rgba(148, 163, 184, 0.18)",
            linecolor: "rgba(148, 163, 184, 0.3)",
          },
          font: {
            color: "#0f172a",
          },
        }}
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
