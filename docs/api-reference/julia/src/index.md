# Julia API Reference

This generated reference documents the Julia package surface used by the
workbench. Astro + Starlight owns the high-level Source-of-Truth documentation
at `/docs/`; this site provides docstring-level details for implementation work.

## Quick links

- <a href="../../docs/">High-level technical docs</a>
- <a href="../python/">Python API Reference</a>
- <a href="../../docs/reference/julia-core/">Julia Core contract summary</a>

## Package scope

- `SuperconductingCircuitsCore` owns circuit authoring, compilation, simulation
  helpers, sweep helpers, diagnostics, and reusable circuit components.
- `SuperconductingCircuitsVisualizer` owns PlotlyJS figure construction.
- `SuperconductingCircuitsRunner` owns async task execution and local result
  staging.
- `SuperconductingCircuitsAnalysisBridge` owns Pluto-friendly calls into the
  Python analysis package through PythonCall.

Backend HTTP contracts remain in the high-level docs and OpenAPI. They are not
part of the Julia API Reference.
