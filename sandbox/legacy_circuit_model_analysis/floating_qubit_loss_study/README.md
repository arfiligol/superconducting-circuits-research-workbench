# Floating-Qubit Loss Study

## 1. Purpose

This sandbox studies one specific question:

- if the floating qubit moves from about `4.00 GHz` to about `3.95 GHz`, is the loss change the same when:
  - the frequency shift is created by changing the qubit inductance `Lq`
  - the frequency shift is created by attaching the readout environment

The experiment is designed to separate three effects:

1. `XY-only` loading
2. `Readout-only` loading
3. the non-additive effect that appears when `XY` and `Readout` are both present together

The quantity used for comparison is:

- `Re(Ydm,in)` at the extracted qubit resonance

This is the quantity that directly follows from the floating-qubit reduction pipeline.

---

## 2. Folder Contents

- `common.jl`
  Shared circuit-construction and analysis helpers.
- `progress_helpers.jl`
  Terminal progress helpers built on `ProgressLogging + TerminalLoggers`.
- `run_loss_decomposition_study.jl`
  Main Julia runner for the study.
- `fit_readout_s21_vector_fitting.py`
  Python helper that runs `scikit-rf.VectorFitting` on the readout-line `S21` data.
- `readout_candidate_sweep_summary.csv`
  Candidate sweep over coupled-window length and explicit `C_rq1/C_rq2`.
- `selected_loss_decomposition_summary.csv`
  Final chosen cases and additive / cross-term summary.
- `selected_setup_lq_sweep_summary.csv`
  `Re(Ydm,in)` vs `Lq` for `XY only` and `XY + Readout`.
- `selected_coupled_window_length_sweep_summary.csv`
  `Re(Ydm,in)` vs coupled-window length for `XY + Readout`.
- `selected_readout_s21_raw.csv`
  Raw readout-line `S21` / `S11` data for the selected setup.
- `selected_readout_s21_vf_model.csv`
  Vector-fitted `S21` model sampled back onto the raw frequency grid.
- `selected_readout_s21_vf_resonances.csv`
  Resonances extracted from the VF poles.

---

## 3. Circuit Topology

The study uses a five-port linearized network:

- `P1`
  qubit pad 1 probe port
- `P2`
  qubit pad 2 probe port
- `P3`
  XY environment port
- `P4`
  readout-line input port
- `P5`
  readout-line output port

The physical circuit is:

1. floating qubit
   - `C_g1` from pad 1 to ground
   - `C_g2` from pad 2 to ground
   - `C_q` between pad 1 and pad 2
   - `L_q` between pad 1 and pad 2
2. XY branch
   - `C_xy1` from XY node to qubit pad 1
   - `C_xy2` from XY node to qubit pad 2
3. readout branch
   - `Readout Line -> Purcell Filter -> Readout Line`
   - one hanging quarter-wave readout resonator is coupled to the Purcell filter through a distributed coupled window
   - the QWR open end couples to qubit pad 1 and pad 2 through `C_rq1` and `C_rq2`

Important modeling choice:

- the Purcell-filter length and QWR length are kept fixed in the current experiment
- the readout-side sweep changes:
  - `C_rq1`
  - `C_rq2`
  - coupled-window length

This follows the current design question:

- keep the Purcell-filter / readout-resonator mode frequencies approximately fixed
- change how strongly energy can leak from the qubit into the readout branch

---

## 4. Core Physics Reduction

The floating qubit is **not** characterized directly from the raw multiport `Y` matrix.
The study always uses the same reduction chain:

1. run `hbsolve(...; returnZ=true, returnS=true)`
2. convert `Z(ω)` into `Y(ω)`
3. apply PTC on the qubit probe ports only
   - subtract the artificial `50 Ohm` shunts on `P1` and `P2`
4. apply CT on the qubit-pad subspace
   - transform `(P1, P2, P3, P4, P5)` into `(CM, DM, XY, RO_IN, RO_OUT)`
5. Kron reduce away:
   - `CM`
   - `XY`
   - `RO_IN`
   - `RO_OUT`
6. keep only the `DM` port
7. define:
   - `Ydm,in(ω)` as the remaining one-port admittance

The resonance used by the study is extracted from:

- the zero crossing of `Im(Ydm,in)`

The reported loss metric is:

- `Re(Ydm,in)` evaluated at that extracted resonance frequency

This is the reason the study compares cases using single extracted points instead of arbitrary full-trace values.

---

## 5. CT Weights

The CT common-mode weights use the electric-centroid idea.

For the current implementation:

- `w1 = C_g1 + C_xy1 + C_rq1`
- `w2 = C_g2 + C_xy2 + C_rq2`

and then:

- `alpha = w1 / (w1 + w2)`
- `beta = w2 / (w1 + w2)`

Important note:

- `C_q` is intentionally excluded from the centroid weights
- `C_q` is an internal pad-to-pad qubit branch
- it is not a pad-to-ground or pad-to-external-environment loading term

---

## 6. Experiment Method

The Julia runner performs the following sequence.

### 6.1 Build the XY-only references

Two reference cases are built using only the XY environment:

1. `xy_only_baseline`
   - `C_rq1 = 0`
   - `C_rq2 = 0`
   - sweep `Lq`
   - choose the `Lq` that makes the extracted qubit resonance closest to `4.00 GHz`
2. `xy_only_matched`
   - `C_rq1 = 0`
   - `C_rq2 = 0`
   - sweep `Lq`
   - choose the `Lq` that makes the extracted qubit resonance closest to `3.95 GHz`

These two cases isolate:

- what happens when the qubit frequency is changed by retuning `Lq`, while the environment is still only XY

### 6.2 Sweep the readout-side candidates

The script then sweeps:

- explicit coupled-window lengths
- explicit `C_rq1/C_rq2` pairs

For each candidate pair:

1. build `readout_only`
   - remove the XY couplings by setting `C_xy1 = 0`, `C_xy2 = 0`
   - sweep `Lq`
   - pick the `Lq` that makes the extracted qubit resonance closest to `3.95 GHz`
2. build `full_coupled_baseline_lq`
   - keep both XY and readout present
   - keep the same bare `Lq` that was chosen for `xy_only_baseline`
3. compute:
   - `readout_only / xy_only` loss ratio
   - the full-coupled result with baseline `Lq`

The candidate-selection logic prefers:

1. a candidate whose `readout_only / xy_only` ratio falls inside the requested comparison window
2. a candidate whose readout-only extracted qubit frequency is still close to `3.95 GHz`

If no candidate satisfies both, the script relaxes the selection rule and chooses the nearest available candidate.

### 6.3 Build the final selected cases

After one readout candidate is selected, the script builds:

1. `readout_only_selected`
2. `full_coupled_baseline_lq`
3. `full_coupled_matched`
   - sweep `Lq` again
   - choose the `Lq` that makes the full-coupled extracted qubit resonance closest to `3.95 GHz`

It then reports:

- `ideal_additive_reference = G_xy_matched + G_readout_only`
- `cross_term_baseline_lq = G_full_shift - G_xy_matched - G_readout_only`
- `cross_term_matched_full = G_full_matched - G_xy_matched - G_readout_only`

where:

- `G = Re(Ydm,in)` at the extracted qubit resonance

### 6.4 Build the readout-line S21 model

For the selected full setup:

1. keep the `full_coupled_matched` configuration
2. sweep the readout line `S21` from the input readout port to the output readout port
3. write the raw complex `S21` data to CSV
4. run vector fitting with:
   - `scikit-rf.VectorFitting`
   - `2` complex resonators
   - `2` real background poles
5. reconstruct the fitted `S21` model on the same frequency grid
6. extract resonance poles
7. compute:
   - `f_r`
   - `Q_l`
   - `BW = f_r / Q_l`

Current classification rule:

- among the VF resonances that lie inside the sweep window
- the one with the larger bandwidth is labeled `Purcell filter`
- the narrower one is labeled `Readout resonator`

This follows the current design expectation for this study.

---

## 7. User-Editable Parameters

The top of `run_loss_decomposition_study.jl` is the only block you need to edit for most experiments.

### 7.1 Qubit targets

- `BASELINE_TARGET_F_GHZ`
- `MATCHED_TARGET_F_GHZ`

These set the qubit frequencies used by the reference and matched comparisons.

### 7.2 Readout-candidate selection targets

- `READOUT_RATIO_COMPARISON_TARGET`
- `READOUT_RATIO_ACCEPTABLE_MIN`
- `READOUT_RATIO_ACCEPTABLE_MAX`
- `READOUT_MATCH_TOLERANCE_GHZ`

These do **not** change the circuit directly.
They only change which candidate is considered the preferred comparison case.

### 7.3 Floating-qubit parameters

- `C_G1_F`
- `C_G2_F`
- `C_Q_F`
- `XY_C_XY1_F`
- `XY_C_XY2_F`

These define the qubit and XY branch.

### 7.4 Readout distributed structure

- `LEFT_READOUT_LENGTH_M`
- `PURCELL_FILTER_LENGTH_M`
- `RIGHT_READOUT_LENGTH_M`
- `QWR_LENGTH_M`
- `PF_COUPLING_CAP_IN_F`
- `PF_COUPLING_CAP_OUT_F`
- `PF_WINDOW_START_M`
- `QWR_WINDOW_START_M`

These are the fixed resonant-structure parameters.

### 7.5 Coupled-window sweep

- `COUPLED_WINDOW_LENGTH_CANDIDATES_M`

This is the main readout-line leakage-control sweep in the current experiment.

### 7.6 Explicit qubit-readout couplings

- `READOUT_COUPLING_CANDIDATES`

Each candidate explicitly writes:

- `C_rq1`
- `C_rq2`

No hidden global scale is applied.

### 7.7 RLGC and Q2D / modal inputs

- `COMMON_L_PER_M_H`
- `COMMON_C_PER_M_F`
- `COMMON_R_PER_M_OHM`
- `COMMON_G_PER_M_S`
- `COUPLED_WINDOW_INPUT_MODE`
- `COUPLED_WINDOW_ZEVEN_OHM`
- `COUPLED_WINDOW_ZODD_OHM`
- `COUPLED_WINDOW_NEVEN`
- `COUPLED_WINDOW_NODD`
- `Q2D_L11_PER_M_H`
- `Q2D_L22_PER_M_H`
- `Q2D_M_PER_M_H`
- `Q2D_C11_MAXWELL_PER_M_F`
- `Q2D_C22_MAXWELL_PER_M_F`
- `Q2D_C12_MAXWELL_PER_M_F`
- `Q2D_C21_MAXWELL_PER_M_F`

These define how the coupled window is built.

### 7.8 Frequency sweeps

- `QUBIT_SWEEP_START_GHZ`
- `QUBIT_SWEEP_STOP_GHZ`
- `QUBIT_SWEEP_STEP_GHZ`
- `READOUT_S21_SWEEP_START_GHZ`
- `READOUT_S21_SWEEP_STOP_GHZ`
- `READOUT_S21_SWEEP_STEP_GHZ`

These define the grids used by:

- qubit admittance extraction
- readout-line S21 fitting

### 7.9 Vector fitting configuration

- `VF_EXPECTED_RESONATORS`
- `VF_BACKGROUND_POLES`

These control the Python VF helper.

---

## 8. Plots

The current runner produces four plots.

### Plot A: `Readout Line S21 With Vector Fitting`

- scatter:
  raw `|S21|` on the readout line
- line:
  VF reconstructed model

This plot is used to inspect the Purcell-filter / readout-resonator spectral structure on the readout line.

### Plot B: `Sweep Lq: Re(Ydm,in) For Two Setups`

Compares:

- `XY only`
- `XY + Readout`

for the same `Lq` sweep.

For each point:

- x-axis:
  `Lq`
- y-axis:
  `Re(Ydm,in)` at the extracted resonance for that `Lq`
- hover:
  extracted qubit resonance frequency

This plot answers:

- how `Re(Ydm,in)` evolves with `Lq`
- whether adding the readout branch changes that `Lq -> loss` trend

### Plot C: `XY + Readout: Re(Ydm,in) vs Coupled Window Length`

For the selected `C_rq1/C_rq2` pair:

- sweep the coupled-window length
- retune `Lq` each time so the extracted qubit resonance stays near `3.95 GHz`

For each point:

- x-axis:
  coupled-window length
- y-axis:
  `Re(Ydm,in)` at the matched extracted resonance
- hover:
  extracted qubit frequency and selected `Lq`

This plot answers:

- whether the coupled-window length is actually changing qubit loss the way we expect

### Plot D: `Selected Cases: Re(Ydm,in) At Extracted Resonance`

This is a one-point-per-case summary plot.

Each point uses:

- x-axis:
  extracted qubit resonance frequency
- y-axis:
  `Re(Ydm,in)` at that resonance

The points are:

- `XY baseline`
- `XY matched`
- `RO only`
- `Full shift`
- `Full matched`

---

## 9. Current Result From The Latest Run

With the currently checked-in parameters, the script selected:

- coupled-window length: `600 um`
- coupling candidate: `C_rq1 = 100.0 fF`, `C_rq2 = 92.0 fF`

Important outcome:

- under the current constraint of keeping PF / QWR resonant lengths fixed
- and only sweeping coupled-window length plus `C_rq1/C_rq2`
- the readout-only contribution still stays very small near `3.95 GHz`

In the latest run:

- `XY-only matched`:
  - `fq ≈ 3.9559 GHz`
  - `Re(Ydm,in) ≈ 2.916e-10 S`
- `Readout-only selected`:
  - `fq ≈ 3.9498 GHz`
  - `Re(Ydm,in) ≈ 1.122e-13 S`
  - ratio vs XY-only is only about `3.8e-4`

This means:

- with PF and QWR resonant frequencies held fixed near the current readout design
- the readout branch is still too far detuned to become a large standalone loss channel at the qubit frequency

This is physically important.
It says the readout branch can still distort the full coupled behavior, but its standalone admittance sampled at the qubit resonance remains weak in this parameter region.

---

## 10. Interpretation Notes

### 10.1 Why can `XY + Readout` look strange in the `Lq` sweep?

Because the full environment is no longer a single smooth background.
The qubit is sampling a structured admittance made from:

- the XY branch
- the readout resonator branch
- the Purcell filter branch
- their interference after CT and Kron reduction

So the `XY + Readout` curve can show:

- peaks
- dips
- sharp bends
- avoided-crossing-like behavior

even when the `XY only` curve looks smooth.

### 10.2 Why is the readout-only ratio still tiny?

Because in the current constrained experiment:

- PF length is fixed
- QWR length is fixed
- only the coupled-window length and `C_rq1/C_rq2` are swept

This mainly changes:

- how strongly the readout resonator is connected to the readout line
- how strongly the QWR open end talks to the qubit pads

but it does **not** move the readout structure's own resonant frequencies toward the qubit as aggressively as changing PF/QWR lengths would.

### 10.3 What does a negative cross term mean here?

It means the full coupled loss is **not** behaving like:

`G_xy + G_readout`

The two environments are not independent additive channels in this regime.
The mode shape and admittance loading change when both are present together.

---

## 11. How To Run

From the repo root:

```bash
julia --project=. sandbox/legacy_circuit_model_analysis/floating_qubit_loss_study/run_loss_decomposition_study.jl
```

During simulation, terminal progress now uses nested `ProgressLogging + TerminalLoggers` bars:

- root study progress
  stage-level progress across the full study
- nested sweep progress
  `Lq` sweeps, readout-candidate sweeps, and coupled-window sweeps

The bar labels are intentionally updated with the current `Lq`, coupled-window length, or `C_rq` candidate so you can see which parameter-space point is being solved.

The script will keep the PlotlyJS server alive until you press Enter.

---

## 12. What To Check Next

If the `XY + Readout` curve still looks suspicious, the next diagnostics should be:

1. inspect Plot A and confirm how many readout-line resonances actually sit inside the chosen sweep window
2. compare Plot B and Plot C together
3. check whether the selected readout candidate is still too weak to be a good standalone comparison case
4. if needed, widen the explicit `C_rq1/C_rq2` candidate set further or revisit the assumption that PF/QWR resonant frequencies must remain fixed
