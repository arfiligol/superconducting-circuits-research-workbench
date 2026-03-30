# Qubit External Coupling Analysis

## Purpose

This sandbox folder is a self-contained audit surface for the floating-qubit external-coupling study.

The main question is:

- if the floating qubit moves from about `4.00 GHz` to about `3.95 GHz`, does the loss change in the same way when
  - the shift is created by retuning `Lq`, or
  - the shift is created by attaching the readout environment

The study compares:

1. `XY only`
2. `Readout only`
3. `XY + Readout`
4. additive expectation versus the fully coupled result

The comparison metric is:

- `Re(Ydm,in)` evaluated at the extracted floating-qubit differential-mode resonance

## Folder Structure

Everything needed by the loss-decomposition study is intentionally kept inside this folder.

```text
qubit_external_coupling_analysis/
├── README.md
├── outputs/
├── run_loss_decomposition_study/
│   ├── run_simulation.jl
│   ├── run_plots.jl
│   ├── user_editable.jl
│   ├── circuit_definition.jl
│   ├── simulation_post_processing.jl
│   └── plot_and_data_persisted_saving.jl
├── tools/
│   └── fit_readout_s21_vector_fitting.py
└── src/
    ├── QubitExternalCouplingAnalysis.jl
    ├── config_types.jl
    ├── parameter_sweeps.jl
    ├── plot_helpers.jl
    ├── circuit_builders.jl
    ├── reductions.jl
    ├── simulation_helpers.jl
    └── reusable_components/
        ├── ReusableComponents.jl
        ├── common.jl
        ├── coupled_window.jl
        ├── circuit_draft.jl
        ├── half_wave_purcell_filter.jl
        ├── quarter_wave_resonator.jl
        └── readout_line.jl
```

### Boundary Rule

- `run_loss_decomposition_study/run_simulation.jl` and `run_loss_decomposition_study/run_plots.jl` only include the runner blocks plus `src/QubitExternalCouplingAnalysis.jl`
- `src/QubitExternalCouplingAnalysis.jl` only includes files inside this folder
- the vector-fitting helper lives in `tools/`
- generated CSV outputs live in `outputs/`
- the study no longer depends on `floating_qubit_loss_study/` or `Reusable Component/` outside this folder

## File Responsibilities

- `run_loss_decomposition_study/run_simulation.jl`
  Runnable entrypoint for simulation plus persisted outputs.
- `run_loss_decomposition_study/run_plots.jl`
  Runnable entrypoint that only reads persisted outputs and redraws the plots.
- `run_loss_decomposition_study/user_editable.jl`
  All user-editable study targets, sweep axes, and plot controls.
- `run_loss_decomposition_study/circuit_definition.jl`
  Highest-level circuit assembly block for the study context and configuration transforms.
- `run_loss_decomposition_study/simulation_post_processing.jl`
  Case construction, sweeps, candidate selection, and post-processed study results.
- `run_loss_decomposition_study/plot_and_data_persisted_saving.jl`
  CSV persistence, vector-fitting helper invocation, persisted-output loading, plots, and terminal summary.
- `src/QubitExternalCouplingAnalysis.jl`
  Local module entrypoint. It assembles the self-contained analysis package for this folder.
- `src/config_types.jl`
  Units, `StudyConfig`, and config update helper.
- `src/parameter_sweeps.jl`
  Generic parameter-sweep axis types plus App-style sweep-index encode/decode helpers.
- `src/circuit_builders.jl`
  Distributed circuit construction and coupled-window translation.
- `src/reductions.jl`
  `Z -> Y`, PTC, CT, Kron reduction, and resonance extraction.
- `src/simulation_helpers.jl`
  Solver calls, case simulation, readout `S21`, and `Lq` sweep helpers.
- `src/plot_helpers.jl`
  Shared plot construction helper.
- `src/reusable_components/`
  Local copy of the distributed netlist authoring utilities needed by this study.
- `tools/fit_readout_s21_vector_fitting.py`
  Local Python helper for `scikit-rf.VectorFitting`.
- `outputs/`
  Generated CSV outputs from the latest run of the study.

## Physics Reduction

The floating qubit is always analyzed through the same reduction chain:

1. run `hbsolve(...; returnZ=true, returnS=true)`
2. convert `Z(ω)` to `Y(ω)`
3. apply PTC on qubit probe ports `P1` and `P2` only
4. apply CT on `(P1, P2, P3, P4, P5) -> (CM, DM, XY, RO_IN, RO_OUT)`
5. Kron reduce away `CM`, `XY`, `RO_IN`, and `RO_OUT`
6. keep only the differential-mode one-port admittance `Ydm,in(ω)`
7. extract the qubit resonance from the zero crossing of `Im(Ydm,in)`
8. report `Re(Ydm,in)` at that extracted resonance

The CT common-mode weights use the electric-centroid idea:

- `w1 = C_g1 + C_xy1 + C_rq1`
- `w2 = C_g2 + C_xy2 + C_rq2`
- `alpha = w1 / (w1 + w2)`
- `beta = w2 / (w1 + w2)`

`C_q` is intentionally excluded from the centroid weights because it is an internal pad-to-pad branch, not a pad-to-environment loading term.

## Study Flow

`run_loss_decomposition_study/run_simulation.jl` executes these four blocks in order:

1. `user_editable.jl`
2. `circuit_definition.jl`
3. `simulation_post_processing.jl`
4. `plot_and_data_persisted_saving.jl`

The resulting study flow is:

1. build the `XY only` baseline near `4.00 GHz`
2. sweep explicit readout candidates at the same bare baseline `Lq`:
   - coupled-window length
   - `C_rq1`
   - `C_rq2`
3. select one readout candidate using the readout-only to XY-only loss ratio
4. build the selected cases at the same bare baseline `Lq`:
   - `readout_only_selected`
   - `xy_plus_readout_shifted`
5. retune `XY only` so that its extracted qubit frequency matches `xy_plus_readout_shifted`
   - this uses a coarse `Lq` sweep first
   - then a fine `Lq` sweep around the best coarse point
6. compute the additive reference and the residual cross term
7. characterize readout-line `S21`
8. run vector fitting to extract the Purcell-filter and readout-resonator resonances
9. save outputs to `outputs/`

`run_loss_decomposition_study/run_plots.jl` reuses the same `user_editable.jl` and `plot_and_data_persisted_saving.jl`, but only:

1. loads the persisted CSV outputs
2. applies the plot controls from `user_editable.jl`
3. redraws the plots without rerunning the simulation

## Parameter Sweep Model

The readout-candidate sweep now uses a generic parameter-sweep layer modeled after the App's sweep indexing concept.

It supports:

1. single-parameter axes
2. explicit grouped parameter sets
3. difference-scale axes that preserve the average value while scaling the parameter difference

Current default readout-candidate sweep uses:

1. a single-parameter axis for coupled-window length
2. an explicit grouped axis for `(C_rq1, C_rq2)`

If you want to preserve the average readout coupling and only scale the imbalance, switch the second axis in `user_editable.jl` to `build_difference_scaled_readout_coupling_axis()`.

## Plot Controls

`user_editable.jl` now includes a `plot_controls` block.

For the candidate-sweep plot:

- `candidate_metric`
  chooses which persisted metric to plot
- `candidate_compare_axis_index`
  chooses which sweep axis becomes the plot x-axis
- `candidate_sweep_index`
  fixes the remaining sweep coordinates using the same sweep-index idea as the App
- `save_png_figures`
  is currently `false` by default; PlotlyJS display stays enabled, but PNG export is off unless you explicitly turn it on

## Plots Produced By The Runner

The plot runner displays five plots:

1. Readout-line `S21`
   - raw scatter
   - vector-fitting model line
2. readout candidate compare plot
   - selected by `plot_controls`
   - built from persisted multi-parameter sweep data
3. `Re(Ydm,in)` versus `Lq`
   - `XY only`
   - `XY + Readout`
4. `Re(Ydm,in)` versus coupled-window length
   - `XY + Readout`
5. one-point-per-case scatter
   - `XY baseline`
   - `RO only`
   - `XY + Readout`
   - `XY matched`
   - `Ideal additive`

## Run Command

From the repo root:

```bash
julia --project=. sandbox/qubit_external_coupling_analysis/run_loss_decomposition_study/run_simulation.jl
```

To redraw plots from persisted outputs only:

```bash
julia --project=. sandbox/qubit_external_coupling_analysis/run_loss_decomposition_study/run_plots.jl
```

## Outputs

After the script runs, the generated CSV files are written to:

- `sandbox/qubit_external_coupling_analysis/outputs/`

The main outputs are:

- `readout_candidate_sweep_summary.csv`
- `selected_loss_decomposition_summary.csv`
- `selected_setup_lq_sweep_summary.csv`
- `selected_coupled_window_length_sweep_summary.csv`
- `selected_readout_s21_raw.csv`
- `selected_readout_s21_vf_model.csv`
- `selected_readout_s21_vf_resonances.csv`

## Audit Guidance

If you want to audit the implementation quickly, the recommended reading order is:

1. `run_loss_decomposition_study/user_editable.jl`
2. `run_loss_decomposition_study/circuit_definition.jl`
3. `run_loss_decomposition_study/simulation_post_processing.jl`
4. `run_loss_decomposition_study/plot_and_data_persisted_saving.jl`
5. `src/parameter_sweeps.jl`
6. `src/reductions.jl`
7. `src/circuit_builders.jl`
8. `src/reusable_components/ReusableComponents.jl`
9. the specific component file under `src/reusable_components/` if you need more detail
10. `tools/fit_readout_s21_vector_fitting.py`
