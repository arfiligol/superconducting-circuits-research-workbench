---
aliases:
  - PlotlyJS Figures
  - Julia Visualizer PlotlyJS Figures
  - SuperconductingCircuitsVisualizer Figures
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/julia-visualizer
  - topic/julia-core
  - topic/pluto
status: stable
owner: docs-team
audience: contributor
scope: PlotlyJS static interactive figure contract for SuperconductingCircuitsVisualizer and real HBSolveResult traces.
version: v1.0.0
last_updated: 2026-05-30
updated_by: codex
---

# PlotlyJS Figures

`SuperconductingCircuitsVisualizer` builds Pluto-facing `PlotlyJS.jl` figures from `HBSolveResult` data. A figure is a view of solver-produced traces; it is not a compute path, persistence path, or substitute result generator.

## Dependency Contract

| Package | May depend on | Must not depend on |
| --- | --- | --- |
| `SuperconductingCircuitsVisualizer` | `PlotlyJS.jl`, Julia Core result types, Base/stdlib formatting utilities | Python Backend, Electron, app frontend state, Runner task protocol |
| `SuperconductingCircuitsCore` | JosephsonCircuits and Julia scientific dependencies | `PlotlyJS.jl`, `SuperconductingCircuitsVisualizer` |
| `SuperconductingCircuitsRunner` | Julia Core and Backend Runner protocol dependencies | `PlotlyJS.jl`, `SuperconductingCircuitsVisualizer` |

This keeps plotting optional for compute packages. Pluto notebooks can load the visualizer when they need figures; Core and Runner remain usable in headless execution and CI without a plotting runtime.

## Input Contract

Visualizer functions read `HBSolveResult` values produced by Julia Core execution:

```julia
result = run_hb_problem(hb_problem)
```

The visualizer may read:

| Field | Meaning |
| --- | --- |
| `result.frequencies_hz` | Frequency axis in Hz from the solved `HBProblemSpec` |
| `result.traces[:zero_mode_s]` | Zero-mode S-parameter traces such as `S11` and `S21` |
| `result.traces[:s_parameter_mode]` | Mode-indexed S-parameter traces |
| `result.traces[:z_parameter_mode]` | Mode-indexed impedance traces |
| `result.traces[:qe_mode]` | Mode-indexed external quality-factor traces |
| `result.traces[:qeideal_mode]` | Mode-indexed ideal external quality-factor traces |
| `result.traces[:cm_mode]` | Mode-indexed coupling-matrix traces |
| `result.traces[:modes]` and `result.traces[:portnumbers]` | Metadata for labels, diagnostics, and trace selection |

Every plotted curve must come from the supplied `HBSolveResult`. The visualizer must not fabricate traces, smooth over missing solver output, or replace a failed solve with analytic or sample curves.

The public figure helpers receive a frequency vector and named numeric traces selected by the caller. A Pluto notebook usually extracts those arrays from `result.traces`, then passes them into Visualizer:

```julia
result = run_hb_problem(hb_problem)
s21 = zero_mode_s(result, 2, 1)

s_parameter_db_magnitude_figure(
    result.frequencies_hz,
    ["S21" => s21];
    title = "Readout Transmission",
    config = figure_config,
)
```

## Figure Contract

`PlotlyJS.jl` is the figure backend for Pluto examples. Figures are static interactive objects: hover, pan, zoom, legend toggles, and download controls are allowed, but figure display must not require live solver callbacks, Backend task submission, or a web application process.

The visualizer owns these figure concerns:

| Concern | Contract |
| --- | --- |
| Axis conversion | Convert `frequencies_hz` to reader-facing units such as GHz without changing the stored result |
| Magnitude traces | Compute display transforms such as `20log10(abs(x))` from real complex traces |
| Phase traces | Compute display transforms such as degrees from real complex traces |
| Real/imaginary traces | Show impedance or admittance components from real complex traces |
| Labels | Preserve trace labels such as `S11`, `S21`, or mode/port labels from `result.traces` |
| Missing traces | Fail clearly and list available families or labels |
| Solver `NaN` values | Preserve solver-returned `NaN` values as result data; do not create placeholders |

## Figure Configuration

`PlotlyFigureConfig` is the configuration object passed from Pluto notebooks or report builders into Visualizer helpers. It keeps figure style fixed by default while allowing notebook-local overrides.

| Setting family | Contract |
| --- | --- |
| Notebook display | `display_width_px` and `display_height_px` set the figure layout size shown in Pluto. |
| PNG download | `download_width_px`, `download_height_px`, `download_scale`, `download_format`, and `download_filename` configure the Plotly modebar image export. |
| Axis ranges | `x_range_ghz` and `y_range` constrain the visible range. A helper call may override either range for one figure. |
| Axis types | `x_axis_type` and `y_axis_type` accept `:linear` or `:log`. A helper call may override either type for one figure. |
| Font scaling | `font_scale` scales the thesis-style size ratios for title, axis title, tick labels, and legend. |
| Figure styling | Margins, grid visibility, legend position, line width, marker size, colors, text color, and background are config-driven. |

Example:

```julia
figure_config = PlotlyFigureConfig(
    display_width_px = 1000,
    display_height_px = 620,
    download_width_px = 1800,
    download_height_px = 1100,
    download_scale = 3,
    download_filename = "readout_line_s21",
    font_scale = 1.15,
    x_range_ghz = (4.0, 5.0),
    y_range = (-60.0, 2.0),
    x_axis_type = :linear,
    y_axis_type = :linear,
)
```

Use `plotly_display_config(config)` when a caller needs the raw PlotlyJS `PlotConfig` for modebar behavior.

Axis ranges are specified in displayed data units. For log axes, `x_range_ghz = (1.0, 100.0)` and `y_range = (1e-3, 1e3)` are accepted as positive displayed values and converted to Plotly's base-10 log range internally. A log-axis range containing `0` or negative values raises `ArgumentError`.

Log axes preserve the supplied trace values. If a plotted trace contains `0` or negative values on a log axis, the helper emits a warning with the axis, affected trace names, and non-positive point count; Plotly then omits those points from the log view.

## Public Plot Families

The package provides PlotlyJS figures for the result families used by the Pluto learning path:

| Figure family | Input data |
| --- | --- |
| `s_parameter_db_magnitude_figure` | Frequency vector and named complex S traces; plots `20log10(abs(Sij))` in dB. |
| `s_parameter_abs_magnitude_figure` | Frequency vector and named complex S traces; plots linear `abs(Sij)` with y-axis `\|Magnitude\|`. |
| `s_parameter_phase_figure` | Frequency vector and named complex S traces; plots phase with `unit = :deg` or `unit = :rad`. |
| `unwrap_phase_trace` | Complex traces or wrapped phase values; returns an explicit unwrapped phase trace before plotting. |
| `z_trace_figure` | Frequency vector and named complex Z traces; expands each trace into real and imaginary curves. |
| `z_parameter_real_figure` | Frequency vector and named complex Z traces; plots `real(Zij)` while preserving labels such as `Z11` and `Z21`. |
| `z_parameter_imaginary_figure` | Frequency vector and named complex Z traces; plots `imag(Zij)` while preserving labels such as `Z11` and `Z21`. |
| `z_parameter_abs_imaginary_figure` | Frequency vector and named complex Z traces; plots `abs(imag(Zij))` while preserving labels such as `Z11` and `Z21`. |
| `y_trace_figure` | Frequency vector and named complex Y traces; expands each trace into real and imaginary curves. |
| `multi_curve_figure` | Frequency vector and caller-transformed named numeric curves. |
| `fit_overlay_figure` | Caller-provided x values, measured values, and fitted values; renders measured markers plus a fit line. |
| `parameter_scatter_figure` | Caller-provided point sets for parameter-space or result-summary scatter plots. |

The phase figure helper does not silently unwrap phase. If a notebook wants a continuous phase trace, the notebook calls `unwrap_phase_trace` first and then plots the returned values with `multi_curve_figure`.

```julia
s21_phase_deg = unwrap_phase_trace(s21; unit = :deg)

multi_curve_figure(
    result.frequencies_hz,
    ["unwrapped phase(S21)" => s21_phase_deg];
    title = "Readout Line Phase Delay",
    yaxis_title = "Phase (deg)",
    config = figure_config,
)
```

Fitting overlays receive numeric series that have already been computed by an
analysis owner such as `core/analysis` through Julia Analysis Bridge:

```julia
fit_overlay_figure(
    fit_result["fit_curve"]["frequency_hz"],
    abs.(s21_window),
    abs.(fit_result["fit_curve"]["s21_real"] .+ im .* fit_result["fit_curve"]["s21_imag"]);
    title = "S21 Notch Fit",
    yaxis_title = "|S21|",
    config = figure_config,
)
```

Parameter-space figures receive caller-shaped point sets. The visualizer owns
marker rendering, labels, axes, and export configuration; it does not assign
physical roles or score candidate designs.

Z/Y helpers receive complex traces and own only the mechanical real/imaginary split:

```julia
z_trace_figure(
    result.frequencies_hz,
    ["Z11" => z11, "Z21" => z21];
    title = "Input And Transfer Impedance",
    config = figure_config,
)

z_parameter_imaginary_figure(
    result.frequencies_hz,
    ["Z11" => z11, "Z21" => z21, "Z12" => z12, "Z22" => z22];
    title = "Imaginary Part Of Impedance Matrix",
    config = figure_config,
)

z_parameter_abs_imaginary_figure(
    result.frequencies_hz,
    ["Z11" => z11, "Z21" => z21, "Z12" => z12, "Z22" => z22];
    title = "Absolute Imaginary Part Of Impedance Matrix",
    config = figure_config,
    y_axis_type = :log,
)

y_trace_figure(
    result.frequencies_hz,
    ["Y11" => y11];
    title = "Input Admittance",
    config = figure_config,
)
```

The caller is responsible for passing solver-produced traces. The visualizer is responsible for labels, transforms, axis configuration, display/export config, and figure construction.

## Pluto Policy

Pluto notebooks use `SuperconductingCircuitsVisualizer` for figures. They should keep plotting cells thin: select the real trace family or label, call the visualizer, and display the returned PlotlyJS figure.

`Plots.jl` is outside the Pluto example plotting contract. Notebook-specific plotting modules should not own reusable figure behavior when the behavior belongs in `SuperconductingCircuitsVisualizer`.

## Validation Signals

A correct visualizer-backed notebook has these observable properties:

| Signal | Expected result |
| --- | --- |
| Solver path | The notebook produces an `HBSolveResult` through `run_hb_problem(hb_problem)` or an equivalent Julia Core execution path |
| Trace source | Plotting cells read `result.frequencies_hz` and `result.traces` |
| Missing data | Missing trace families or labels raise explicit errors with available options |
| Dependency direction | Core and Runner package environments do not add `PlotlyJS.jl` for figure support |
| Notebook display | Figures render as PlotlyJS static interactive objects in Pluto |

## Related

- [Julia Visualizer](index.mdx)
- [Julia Core](../julia-core/index.mdx)
- [HB Simulation Intent](../julia-core/hb-simulation-intent.mdx)
- [Runner-Safe API](../julia-core/runner-safe-api.md)
- [Pluto Examples](../../workflows/pluto/pluto-examples.mdx)
