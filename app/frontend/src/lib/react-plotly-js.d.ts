declare module "react-plotly.js" {
  import type { ComponentType, CSSProperties } from "react";

  type PlotProps = {
    data: readonly Record<string, unknown>[];
    layout: Record<string, unknown>;
    config: Record<string, unknown>;
    className?: string;
    style?: CSSProperties;
    useResizeHandler?: boolean;
  };

  const Plot: ComponentType<PlotProps>;
  export default Plot;
}
