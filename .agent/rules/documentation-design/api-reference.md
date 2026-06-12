## API Reference
- Astro + Starlight owns high-level docs and Source-of-Truth narrative at `/docs/`.
- Sphinx owns Python package API reference at `/api/python/` for `sc_core`, `superconducting_circuits_analysis`, and `sc_data_contracts`.
- Documenter.jl owns Julia package API reference at `/api/julia/` for `SuperconductingCircuitsCore`, `SuperconductingCircuitsVisualizer`, `SuperconductingCircuitsRunner`, and `SuperconductingCircuitsAnalysisBridge`.
- Do not expose `app_backend` internals as public Sphinx API; backend HTTP contracts belong in Starlight owner docs and OpenAPI.
- Python docstrings use Google style parsed by Sphinx Napoleon, type hints in signatures, clear units/physics semantics, and no history or migration narrative.
- Julia docstrings use Documenter-compatible Markdown before exported public definitions; exported names must be documented or deliberately unexported.
- API docs source lives under `docs/api-reference/`; generated output goes through `build/api-reference/` and deploys under `site/dist/api/`.
- `site/src/content/docs/docs/` is generated Starlight staging and must not be edited or used as API docs source.
- Generated API sites must link back to `/docs/` and cross-link Python and Julia API sites.
