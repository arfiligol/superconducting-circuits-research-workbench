# PF6FQ Thesis External-Coupling Analysis

This sandbox is the single thesis-analysis folder for PF6FQ external-coupling work.

It keeps the existing Ansys admittance resonance extraction together with the new
Q3D capacitance-matrix post-processing and Q3D + JosephsonCircuits.jl XY-line
comparison workflow. Thesis-specific glue stays in this folder; reusable simulation
and port-matrix operations are called from the existing `core` API.

## Scope

- Q0-Q2 XY external coupling from raw Q3D matrix exports.
- Existing Q0-Q2 admittance sweeps for `XY`, `Readout`, and `XY_and_Readout`.
- Thesis-facing CSV tables and figures only; this folder is not an SC-Tutorial App
  ingestion surface yet.

## Raw Data

The canonical raw-data source for new work is:

```text
data/raw/layout_simulation/PF6FQ/
```

The copied `raw/` folder is retained so the original admittance extraction notebook
continues to run in isolation. New Q3D processing reads the `Q*_XY_Q3D_C_Matrix.m`
files directly from `data/raw/layout_simulation/PF6FQ/`.

## Notebooks

- `notebooks/01_admittance_resonance_extraction.ipynb`
  extracts admittance zero crossings and selected qubit-like resonance branches.
- `notebooks/02_q3d_capacitance_postprocess.ipynb`
  parses Q3D `capMatrix` exports, normalizes units, and computes thesis capacitance
  reductions.
- `notebooks/03_q3d_jc_comparison_figures.ipynb`
  combines admittance extraction, Q3D capacitance tables, and Q3D+JC simulation
  outputs into thesis-facing comparison figures/tables.

## Python/Core Runner

Run a one-case smoke simulation first:

```bash
uv run python sandbox/thesis_pf6fq_external_coupling_analysis/run_q3d_xy_simulation.py --smoke
```

Run the full Q0-Q2 XY sweep:

```bash
uv run python sandbox/thesis_pf6fq_external_coupling_analysis/run_q3d_xy_simulation.py
```

The runner follows the thesis chain:

1. parse Q3D `capMatrix`
2. build a floating qubit + XY-line circuit
3. run JosephsonCircuits through existing `core.simulation` APIs
4. build the port-space admittance sweep through existing core post-processing
5. apply qubit-probe PTC
6. apply weighted CT
7. Kron reduce to the differential qubit mode
8. extract `Im[Yeff]=0`
9. compute `Gamma_XY = Re[Yeff] / Ceff,q` and `T1_XY = 1 / Gamma_XY`

Notebook comparison tables also compute a Layout-vs-Circuit diagnostic T1 with a
common resonance-fit capacitance. Because notebook `L_jun` is the per-junction
inductance and the qubit branch has two equal junctions in parallel, the LC fit uses
`f = 1 / (2*pi*sqrt((Ls + L_jun/2) * Ceff))`. The Q3D-reduced `Ceff,q` remains a
separate capacitance-reduction reference.

## Outputs

Generated files are grouped under:

```text
outputs/
├── raw/
├── figures/
└── tables/
```

Main expected files:

- `outputs/raw/all_admittance_zero_crossings.csv`
- `outputs/raw/selected_qubit_resonances.csv`
- `outputs/raw/q0_re_yin_nearest_selected_match.csv`
- `outputs/raw/q3d_capacitance_parameters.csv`
- `outputs/raw/q3d_jc_xy_reduced_observables.csv`
- `outputs/raw/q3d_jc_xy_reduced_y_traces.csv`
- `outputs/tables/selected_qubit_resonance_summary_wide.csv`
- `outputs/tables/thesis_q3d_capacitance_summary.csv`
- `outputs/tables/thesis_q3d_vs_hfss_frequency_comparison.csv`
- `outputs/figures/*.png`

## Modeling Notes

- Q3D `.m` matrices are interpreted in the fixed terminal order
  `(Ground, Pad1, Pad2, XY_Line)`.
- `capMatrix` is the source of truth. `spicecapMatrix`, when present, is audit-only.
- Branch capacitances are read from Maxwell off-diagonal entries by sign convention:
  `Cij = -capMatrix[i, j]`.
- The large XY-to-ground term is retained as a diagnostic/sensitivity value and is not
  injected into the JosephsonCircuits XY-line model by default, to avoid double-counting
  line capacitance.
