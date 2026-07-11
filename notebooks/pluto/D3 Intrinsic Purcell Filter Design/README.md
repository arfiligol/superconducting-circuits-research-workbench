# D3 Intrinsic Interferometric Purcell Filter Design

This folder owns the D3 design-process notebooks for the intrinsic
interferometric Purcell filter. The purpose is to turn Q2D CPW and MTL
cross-section data into corrected resonator lengths, an external coupling
capacitor, and simulation evidence for the final five-pair readout design.

The notebooks are meant to be read as a chain. Python owns analysis
orchestration and candidate evidence tables. Pluto reads explicit CSV inputs,
builds circuit models, runs HB, and writes solver-returned plus declared
derived/PTC traces. Human review owns promotion into design parameters or
corrections. A PTC trace is promotion evidence only when the compiled shunt row,
value, and removal intent are preserved with it.

This child folder owns workflow execution, implementation, and evidence
artifacts. The Super Repo owns the canonical [D3 Design Target](https://github.com/arfiligol/SCQ_Design/blob/main/docs/design-targets/d3-intrinsic-interferometric-purcell-filter.qmd)
and [Auditable Scientific Optimization](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/numerical-methods/auditable-scientific-optimization.qmd)
semantics. Single-notch candidate fits follow [Notch Resonator Complex S21 Fit](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/notch-resonator-complex-s21-fit.qmd),
while scalar rational diagnostics follow [Vector Fitting and Passivity](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/vector-fitting-passivity.qmd).
Terminal-basis, Maxwell, modal, and matrix-artifact rules live in
[Multiconductor RLGC Matrices: Basis, Modes, and Physical Meaning](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/transmission-lines/multiconductor-rlgc-matrix-semantics.qmd).
Raw/derived trace meaning and compensation gates live in [Port Reference
Impedance Semantics](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/simulation/port-reference-impedance-semantics.qmd)
and [Port-Termination Compensation](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/simulation/port-termination-compensation.qmd).
The child [D3 Readout-Filter S21 Fit API](../../../docs/concepts/equivalent-circuit-modeling/d3-readout-filter-s21-fit-api.md)
lists only the concrete Python/Julia entrypoints, payloads, failures, and replay
requirements.
Notebook 07 is the sole review and run entrypoint for the physical evaluator
and the bounded CMA-ES → Nelder-Mead workflow. Opening the notebook does not
start a run: execution requires an explicit call bound to the displayed
condition-manifest id and SHA-256. An `agent_proposed` or `sol_reviewed`
manifest may produce clearly labeled exploration evidence; only a
`human_approved` manifest can make promotion evaluable.

## Design Target

The final design needs one shared readout line with five filter/readout
resonator pairs. For each pair, the design variables should be tuned together:
$\omega_p$, $\omega_r$, $\omega_n$, $J$, and $\kappa_p$.

The 50 Ω shared feedline is a separate Q2D cross section. Its v1 lossless LC
extraction is $L'=383.83846\,\mathrm{nH/m}$ and
$C'=152.91443\,\mathrm{pF/m}$, giving $Z_0=50.1014\,\Omega$. It must not reuse
the selected resonator case's single-trace LC values. The source did not
supply $R'$ or $G'$; the current LC-only exploration explicitly assumes both
are zero. The 0.25 Ω impedance condition is mismatch screening only, not an
extraction-uncertainty or promotion claim.

For the resonator pair, the current screening heuristic chooses CPW cross
sections where $Z_m=\sqrt{L_m/C_m}$ is close to the uncoupled resonator-line
impedance, $Z_m \approx Z_{0,r}$. This ratio is not the general definition of
an MTL modal characteristic impedance; promotion to a design law requires the
evidence named by the canonical Knowledge node.

This makes the length design easier. For the current flip-chip case, however,
the artificial Maxwell-diagonal reference is not necessarily equal to the
single-trace impedance,
$Z_{\mathrm{diag},i}=\sqrt{L_{ii}/C^{\mathrm M}_{ii}}\ne Z_0$. This is a
mismatch diagnostic, not a coupled-line modal characteristic impedance.

That mismatch shifts the resonator frequency and must be corrected by
simulation.

## Workflow

1. Select two CPW cross sections from Q2D data.

   One cross section describes the MTL coupling window. The other describes the
   uncoupled resonator sections. A third, independent cross section owns the
   50 Ω shared feedline. The resonator selection target is
   $Z_m \approx Z_{0,r}$. The current design accepts
   $Z_{\mathrm{diag},i}\ne Z_{0,r}$, so the artificial diagonal-reference
   section can create a frequency shift.

2. Estimate and simulate loaded-bare resonator frequencies.

   Start from section delays and CPW velocities to estimate the five section
   lengths. Then simulate the Maxwell-diagonal pair: it retains both resonators and
   the actual filter-to-feedline capacitor, but uses the Maxwell diagonal
   $L_{ii},C_{ii}$ with all off-diagonal entries zero. This is the pair
   Hamiltonian reference, not a circuit made by removing the full ladder's
   physical cross capacitor. Its filter channel supplies
   $\omega_{p,\mathrm{LB}}$; its readout weak-probe sweep is extrapolated to
   zero probe capacitance for $\omega_{r,\mathrm{LB}}$.

3. Separate impedance mismatch from external loading.

   Compare a full-impedance-match reference against the real MTL-diagonal
   mismatch case. The difference measures the frequency shift caused by the
   middle $l_c$ section.

4. Sweep the external coupling capacitor.

   Sweep $C_{ext}$ from the filter resonator open end to the feedline. The
   resulting traces are candidate evidence for loading and linewidth behavior;
   they are not promoted until the fit window, isolated-notch ownership, source
   metadata, and acceptance policy have passed Human review.

5. Correct lengths and choose $C_{ext}$.

   The coupled evaluator and optimizer may generate corrected candidate values
   as exploration evidence. Only a Human-approved condition manifest can
   promote them into design parameters.

6. Tune the full pair design.

   In the full circuit, $\omega_p$, $\omega_r$, $\omega_n$, $J$, and
   $\kappa_p$ are coupled design outcomes. Adjusting lengths can keep the
   target resonator frequencies in place while tuning $J$ and $\omega_n$.

## Notebook Map

- [`../../python/01_resonator_length_estimate.py`](../../python/01_resonator_length_estimate.py)
  is the source of truth for the first delay-form length estimate. It writes
  `design_inputs/d3_selected_resonator_lengths.csv`, which the Pluto notebooks
  consume.

- [`01_bare_frequency_probe.jl`](01_bare_frequency_probe.jl)
  reads the Python length table and writes HB probe traces for mode ownership.
  Use the perturbation data to decide which peak belongs to the filter
  resonator and which belongs to the readout resonator.

- [`02_filter_frequency_loading_calibration.jl`](02_filter_frequency_loading_calibration.jl)
  reads the Python length table and produces broad filter-only HB traces. It
  preserves existing fine artifacts but no longer generates new fine windows
  from the superseded local vector-fit linewidth path. A new fine run requires
  a Human-approved per-trace center/window/step artifact.

- [`../../python/02_filter_frequency_loading_analysis.py`](../../python/02_filter_frequency_loading_analysis.py)
  is the Jupytext source for the Python evidence notebook. It reads exactly the
  90 traces named by the current fine manifest, calls the shared complex-notch
  fitter, and publishes candidate fit and residual evidence. It stops before
  bare-frequency regression, linewidth promotion, or length correction.

- [`03_full_readout_hanging_pairs.jl`](03_full_readout_hanging_pairs.jl)
  reads the Python length table and runs the final five-pair shared-readout
  circuit. Only the filter resonator open end couples capacitively to the
  readout line.

- [`../../python/03_full_readout_analysis.py`](../../python/03_full_readout_analysis.py)
  analyzes the bare-probe ownership traces and the full five-pair readout
  traces. It runs vector-fit pre-passes and the Spring2025 `S11` fit attempt. It
  does not fit `$J$` or publish `$J$` evidence.

- [`05_coupling_notch_z21_sweep.jl`](05_coupling_notch_z21_sweep.jl)
  generates fixed-spec PTC Z21 geometry sweeps over MTL coupling length and the
  common short-side correction.

- [`../../python/05_coupling_notch_z21_sweep_analysis.py`](../../python/05_coupling_notch_z21_sweep_analysis.py)
  ranks geometry seeds with notch, center, and half-Z21-peak-split screening
  diagnostics. The half split is not extracted `$J$` or promotion evidence;
  promoted `$J$` must come from the canonical complex-S21 fit.

- [`06_lc_hybrid_split_diagnostic_sweep.jl`](06_lc_hybrid_split_diagnostic_sweep.jl)
  runs the `lc` hybrid-split diagnostic sweep for the representative slot. Each
  `lc` point compensates short and open lengths, reruns the filter `C_ext`
  sweep, reruns a readout weak-probe sweep, and runs intrinsic-pair `Z21`.

- [`../../python/06_lc_hybrid_split_diagnostic_analysis.py`](../../python/06_lc_hybrid_split_diagnostic_analysis.py)
  extracts the loaded bare frequencies, applies the measured filter loading
  shift to `Z21`, and reports `half_hybrid_split_mhz` as a diagnostic. It does
  not identify half of the corrected hybrid split as $J$.

- [`d3_purcell_common.jl`](d3_purcell_common.jl)
  contains shared circuit construction helpers, Q2D case loading, and the
  small CSV reader used by the Pluto notebooks.

- [`d3_coupled_evaluator.jl`](d3_coupled_evaluator.jl)
  owns the real single-slot HB evaluation, loaded-bare references, complex-S21
  $J$ fit, independent pole cross-check, notch extraction, and physical
  rejection evidence. It reports the current model truthfully as LC-only with
  unavailable source $R'/G'$ assumed zero for exploration.

- [`d3_coupled_optimizer.jl`](d3_coupled_optimizer.jl)
  owns the generic bounded cost accounting, exact cache, CMA-ES search,
  Nelder-Mead refinement, and structured convergence/promotion outcomes. It
  does not own D3 physics or threshold decisions.

- [`07_coupled_cost_optimization.jl`](07_coupled_cost_optimization.jl)
  renders the complete hash-bound
  [`d3_condition_manifest.json`](d3_condition_manifest.json), adapts the
  evaluator evidence into the exact objective schema, and exposes the explicit
  run function. It never auto-runs when opened.

## Plot And Fit Conventions

Simulation data should be shown as markers or scatter points. Fitting results
may be shown as continuous or dashed curves. For one simulated case, use the
same color for raw data and fit; distinguish them by marker versus line style.

Vector fitting can provide a scalar pole diagnostic or independent cross-check;
it is not a fallback notch fitter or an accepted network model. The evaluator
uses the reusable calibrated complex-`$S_{21}$` API for $J$ extraction, while
Notebook 07 owns the exact metric-selection adapter and review boundary.

## Optimization Integration Boundary

The physical evaluator and optimizer are real implementation, but approval is
not inferred from successful execution. Conditions move through
`agent_proposed → sol_reviewed → human_approved`; every review is bound to the
canonical manifest hash. Proposed and Sol-reviewed conditions support explicit
exploration, and all resulting artifacts remain unapproved. Only Human approval
allows Notebook 07 to evaluate promotion.

The present exploration consumes an LC-only Q2D envelope. Missing source
$R'/G'$ values remain explicitly unavailable and are assumed zero only for the
lossless exploration model; they are not presented as extracted RLGC evidence.
Fabrication tolerance, yield, and a future true-RLGC artifact remain separate
Human review concerns rather than hidden optimizer defaults.

## Fast Failure Isolation

Run [`scripts/test/test_d3_coupled_optimizer_analytical.jl`](../../../scripts/test/test_d3_coupled_optimizer_analytical.jl)
first. It sends bounded parameters through a deterministic analytic cost with a
known optimum, a promotion-only condition, and an expected rejected region. A
passing result isolates the generic cost, cache, CMA-ES, Nelder-Mead, and
structured-outcome machinery without loading HB.

Notebook 07 then exposes two separate explicit actions. `evaluate_d3_seed_cost()`
runs one real Simulation → evaluator → metric projection → cost path without an
optimizer. `run_d3_coupled_exploration()` runs the full simulation-backed search.
This order distinguishes optimizer defects from circuit, artifact, fitting, or
adapter failures before an expensive exploration is started.
