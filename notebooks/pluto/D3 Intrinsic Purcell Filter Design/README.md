# D3 Intrinsic Interferometric Purcell Filter Design

This folder owns the D3 simulation, optimization, and evidence workflow. It
turns Q2D CPW/MTL inputs and a floating-qubit capacitance artifact into six
Layout variables, full-$\mathcal T_{\mathrm{QRP}}$ response evidence, and
Human-reviewable validation artifacts.

The Super Repo owns the canonical [D3 Same-Die Design Target](https://github.com/arfiligol/SCQ_Design/blob/main/docs/design-targets/d3-intrinsic-interferometric-purcell-filter.qmd),
[separate D3 Split-Die Design Target](https://github.com/arfiligol/SCQ_Design/blob/main/docs/design-targets/d3-split-die-intrinsic-interferometric-purcell-filter.qmd),
[Exact-N Port-Anchored Chain Realizations](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/exact-n-port-anchored-chain-realizations.qmd),
[Full Qubit--Readout--Filter Complex Response Fit](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/worked-examples/d3-full-qrp-complex-response-fit.qmd),
[Full QRP Node Flux to Bare Coordinates](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/worked-examples/d3-full-qrp-node-flux-to-bare-coordinates.qmd),
[Bare, Coupling-On Diagonal, and Hybridized Modes](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/readout/bare-vs-hybridized-readout-filter-modes.qmd),
and [Auditable Scientific Optimization](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/numerical-methods/auditable-scientific-optimization.qmd)
semantics. This Workbench owns circuit construction, execution, fitting APIs,
optimizer integration, and artifacts. The [D3 Full-QRP Response Fit API](../../../docs/concepts/equivalent-circuit-modeling/d3-readout-filter-s21-fit-api.md)
documents the concrete implementation boundary.

The current forward-search artifacts and Exact-Six explorer in this folder
belong to the **Same-Die** Target: both resonator traces are on `D0/top` in the
current evidence. They must not be used as Split-Die closure evidence.

## Design target

The final Design Target has exactly six positive-weight
$\mathcal T_{\mathrm{QRP}}$ quantities:

| Metric | Source |
| --- | --- |
| `system_c_filter_loaded_bare_hz` | Pointwise full-QRP circuit-to-Hamiltonian map with complex-response closure |
| `system_c_readout_loaded_bare_hz` | Pointwise full-QRP circuit-to-Hamiltonian map with complex-response closure |
| `system_c_intrinsic_notch_hz` | Full-QRP PTC complex-$Z_{21}$ zero |
| `system_c_filter_loaded_bare_external_linewidth_hz` | Transformed port map with full-QRP open-response closure |
| `system_c_j_hz` | Full-QRP $h_{rp}$ with complex-response closure |
| `system_c_g_hz` | Full-QRP $h_{qr}$ at nominal $L_J$ with complex-response closure |

`system_c_readout_minus_filter_loaded_bare_detuning_hz` has zero weight. It is
a Human promotion condition and never becomes a hidden optimizer preference.
The fitted qubit diagonal curve and three hybridized poles are required review
evidence, not additional Layout objectives.

The Layout result contains exactly six variables:

- `lc_um`
- `lp_short_um`
- `lr_short_um`
- `lp_open_um`
- `lr_open_um`
- `filter_to_line_capacitance_fF`

The last value is the finite physical filter-to-feedline $C_{\mathrm{ext}}$.
The artificial weak observation hook uses `c_probe_capacitances_fF`, represents
$C_{\mathrm{probe}}$, and is extrapolated to zero. These capacitances have
different physical roles.

The probe list is strictly increasing and contains at least five positive
values. The first readout probe uses the Slot target as its scan anchor; every
later probe centers a fresh 300 MHz continuation interval on the preceding
accepted coupling-off pole. Coupling-off, coupling-on, and empty-feedline HB
share that probe's exact grid and grid SHA. Coupling-off and coupling-on mode
ownership independently continue from their preceding accepted pole, with no
nearest-frequency or out-of-span fallback.

The `system_c_*` strings are retained runtime compatibility keys. They do not
define a basis or establish final authority by themselves.

## Model ownership

The evaluator uses four non-aliased evidence groups:

| Group | Circuit | Role |
| --- | --- | --- |
| Coupling-off reference | Declared terminal-shunt fixture | Off-reference windows, poles, and reduced initial values |
| $\mathcal T_{\mathrm{QR}}$ (`System A`) | Qubit + readout + feedline | Initial q/r curves, coupling estimate, and response diagnostics |
| $\mathcal T_{\mathrm{RP}}$ (`System B`) | Readout + filter + feedline | Initial r/p curves, $J$, filter linewidth, and response diagnostics |
| $\mathcal T_{\mathrm{QRP}}$ (`System C`) | Qubit + readout + filter + feedline | Final topology; authority requires the pointwise circuit, Hamiltonian, port, and response maps |

$\mathcal T_{\mathrm{QR}}$, $\mathcal T_{\mathrm{RP}}$, and coupling-off
estimates seed and bound the full-QRP fit. They never populate final metric
fields, because removing a mode or changing coupling topology changes the
capacitance inverse, self terms, normalization, and resulting bare basis.

The full physical $\mathcal T_{\mathrm{QRP}}$ fixture keeps all coupling
branches present and
sweeps only the per-junction $L_J$. Every trace owns a union of local frequency
windows, an empty-feedline reference on that exact grid, and matching candidate,
topology, reference-contract, and port-plane identities. The final model must
derive $\mathbf h(L_J)$ and the port/direct maps pointwise from the same full
circuit parameter set, then constrain them with the joint complex response.

Before final metrics may reach the Cost Function:

- response quality, seed, bound, identifiability, and stability gates pass;
- the signed direct qubit--filter alternative reports `passed`; and
- residue-qualified bright full-QRP and Vector-Fit poles agree
  bidirectionally in count, frequency, and total linewidth.

The intrinsic notch is independently refined as a full physical
$\mathcal T_{\mathrm{QRP}}$ PTC
$Z_{21}$ complex zero. Scan samples only discover signed brackets; fresh HB/PTC
evaluations own the final root and Re/Im/complex residual gates.

## Current runtime stop gate

The current `d3_system_c_s21_lj_sweep_fit.v4` implementation still fits seven
reduced coefficients, imposes a scalar LC qubit curve and fixed-participation
$L_J^{-1/4}$ coupling laws, and observes the response through a filter-only
port projection. It does not yet execute the pointwise
`theta_circ -> C_bare,K_bare -> h,Delta,K_port,D_port -> S21` map required by
the canonical contract. Its outputs are reduced-runtime estimates and may be
used for initialization, plots, and migration comparisons, but they may not
publish the six final Cost operands even when the current numerical gates pass.

## Inputs

- The canonical target JSON supplies Slot targets and target identities.
- `d3_design_config.json` selects the Q2D artifacts and fixed design inputs.
- `d3_optimizer_conditions.json` is the reviewed
  `d3-optimizer-conditions.v7` condition manifest shared by every Slot.
- `design_inputs/d3_selected_resonator_lengths.csv` supplies one seed row per
  Slot.
- The configured private open-side input supplies the labeled Maxwell
  capacitance matrix, cut-plane/region ledger, and per-junction $L_J$ input.

The canonical `d3-readout-open-side-maxwell.v2` loader fixes the reference
conductor and eliminates exactly the four disconnected Coupler pads by Schur
complement. It retains the qubit islands and readout terminal and maps the
reduced matrix to
$C_{01},C_{02},C_{12},C_{r1},C_{r2},C_{0r}$. The complete local block owns
the open-side electric energy; the distributed readout stops at the declared
cut plane and excludes that local region. The old
`d3-floating-qubit-maxwell.v1` input remains historical-replay-only because it
discarded $C_{0r}$ without a cut-plane ledger.

The machine-readable input shape is
[`contracts/d3-readout-open-side-maxwell.v2.schema.json`](contracts/d3-readout-open-side-maxwell.v2.schema.json).

The v1 distributed model is lossless LC because the source provides no
$R'$/$G'$. Artifacts record those terms as unavailable and assumed zero; they
do not claim extracted distributed loss.

## Notebook and module map

- [`00_exact_six_s21_target_explorer.jl`](00_exact_six_s21_target_explorer.jl)
  interactively explores every independent Same-Die Exact-Six parameter with a
  Pluto Slider, renders raw/calibrated complex-$S_{21}$ magnitude and phase,
  and downloads a candidate analytical-target snapshot for the four-node
  handoff. It has no synthetic input fallback.
- [`../../python/01_resonator_length_estimate.py`](../../python/01_resonator_length_estimate.py)
  creates the delay-form seed-length table consumed by Pluto.
- [`01_coupled_pair_frequency_probe.jl`](01_coupled_pair_frequency_probe.jl) produces
  component-response mode-ownership evidence.
- [`02_filter_frequency_loading_calibration.jl`](02_filter_frequency_loading_calibration.jl)
  produces broad filter-loading and impedance-mismatch seed traces.
- [`03_full_readout_hanging_pairs.jl`](03_full_readout_hanging_pairs.jl) and
  [`../../python/03_full_readout_analysis.py`](../../python/03_full_readout_analysis.py)
  provide screening-only shared-feedline diagnostics; their local mode
  associations do not enter Cost or own final full-QRP modes.
- [`05_coupling_notch_z21_sweep.jl`](05_coupling_notch_z21_sweep.jl) and
  [`../../python/05_coupling_notch_z21_sweep_analysis.py`](../../python/05_coupling_notch_z21_sweep_analysis.py)
  provide geometry and notch seed diagnostics.
- [`06_lc_hybrid_split_diagnostic_sweep.jl`](06_lc_hybrid_split_diagnostic_sweep.jl)
  and [`../../python/06_lc_hybrid_split_diagnostic_analysis.py`](../../python/06_lc_hybrid_split_diagnostic_analysis.py)
  provide coupling-length screening diagnostics.
- [`d3_purcell_common.jl`](d3_purcell_common.jl) owns shared D3 circuit
  construction and input loading.
- [`d3_procedure_catalog.v1.json`](d3_procedure_catalog.v1.json) maps a
  topology/goal requirement to an executable Procedure, required paths,
  preflight checks, stages, and expected artifacts.
- [`../../../scripts/build/d3_design_platform.py`](../../../scripts/build/d3_design_platform.py)
  resolves that catalog, prints a no-write execution plan, runs the exact
  stages on request, and writes a SHA-bound Procedure receipt.
- [`d3_coupled_evaluator.jl`](d3_coupled_evaluator.jl) owns physical HB,
  the current reduced full-QRP fitting path, checks, notch extraction, and
  compatibility metric projection.
- [`d3_coupled_optimizer.jl`](d3_coupled_optimizer.jl) owns bounded cost,
  caching, CMA-ES, Nelder--Mead, and structured outcomes. It owns no D3 physics
  or threshold decisions.
- [`07_coupled_cost_optimization.jl`](07_coupled_cost_optimization.jl) is the
  sole interactive evaluation and optimization entrypoint.
- [`../../python/08_d3_design_review.py`](../../python/08_d3_design_review.py)
  is the editable Jupytext source for the read-only Human review notebook; its
  generated `.ipynb` mirror uses Plotly and `nbformat` at runtime.

## Resolve a Procedure

List the currently declared Procedures:

```bash
python scripts/build/d3_design_platform.py list
```

A request contains exactly `schema_version`, `topology`, `goal`, and `paths`.
Use `plan REQUEST.json` to resolve and preflight it without creating outputs;
use `run REQUEST.json` only after the plan is understood. The canonical
forward-design route refuses a legacy qubit input or an initializer whose
readout length is not referenced to the open-side local cut plane.
The request shape is
[`contracts/d3-design-procedure-request.v1.schema.json`](contracts/d3-design-procedure-request.v1.schema.json).

## Legacy interactive optimizer

1. Start Pluto and open `07_coupled_cost_optimization.jl`.
2. Select one unfinished or rejected Slot.
3. Inspect its target, seed row, bounds, conditions identity, and execution
   identity.
4. Click **Evaluate selected seed — no writes** to run one complete
   Simulation → extraction → metric → Cost path.
5. Click **Run selected Slot optimization** only after the single evaluation is
   physically understandable.
6. Review the persisted optimizer result and frozen `layout_specs.json` in
   Notebook 08.

Opening the notebook or changing the Slot selector does not start a run.
Completed evidence is view-only and is not silently rerun.

## Optimizer to validation handoff

1. Notebook 07 persists the optimizer evidence and selected Layout Specs.
2. The selected `layout_specs.json` freezes the six Layout variables; the
   optimizer directory remains immutable.
3. A fresh process evaluates that frozen candidate once with trace capture and
   without optimizer/cache state:

   ```bash
   julia --startup-file=no scripts/build/run_d3_nominal_validation.jl <optimizer_run_directory>
   ```

4. Notebook 08 reads the fresh artifact, displays parameter tables and response
   plots, and ends with the frozen Layout Specs.
5. Human review owns acceptance. Fabrication tolerance remains a separate final
   check outside the Cost Function.

Conditions may be Sol-reviewed for execution, but promotion requires
`human_approved`. A successful optimizer or evaluator run does not imply
physical acceptance.

## Plot and fit conventions

Plot simulation samples as markers and fitted responses as lines. Use the same
color for the same physical case, changing marker/line style to distinguish
data from fit. Every plot and table must name its circuit system, observable,
mode layer, and estimator.

Scalar Vector Fitting may own an eligible, uniquely continued response-pole
frequency and total linewidth after its sampling/refinement gates. In the
full-QRP topology it is parallel bright-pole evidence against the poles derived
from the fitted physical model. It never owns the bare decomposition, the
intrinsic notch, $g$, $G$, or $J$.

## Fast failure isolation

Run
[`scripts/test/test_d3_coupled_optimizer_analytical.jl`](../../../scripts/test/test_d3_coupled_optimizer_analytical.jl)
to verify the generic cost/cache/CMA-ES/Nelder--Mead path without HB. Then use
Notebook 07's one-seed action to isolate the real circuit and extraction path
before spending a full optimization budget.
