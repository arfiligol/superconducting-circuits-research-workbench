# D3 Intrinsic Interferometric Purcell Filter

The host Design Target owns the physics and optimization semantics:

- `SCQ_Design/docs/design-targets/d3-intrinsic-interferometric-purcell-filter.qmd`
- `SCQ_Design/docs/design-targets/contracts/d3-same-face-resonators-opposite-face-qubit-j5-k20-gap8.v1.json`

## Current implementation

- `d3_circuit_plans.jl` builds the Equivalent, Hybridized, linewidth-$L_A$,
  and intrinsic-pair-notch Circuit Plans.
- `d3_idc_input.jl` validates one provenance-bearing private EM mapping and
  always returns all three IDC capacitances. No canonical mapping artifact is
  currently committed in this public repository.
- `d3_resonator_input.jl` first validates one sealed material-aware-v4 Q2D
  authority generically, then binds the accepted Rev10 consumer to the exact
  W7/S6/D3/H8 artifact. Both physical stages retain its bytes, material/source
  authority, geometry, raw Maxwell matrices, coupling orientation, and section
  lengths in one Fixed-line V2 identity. The 50 µm structural ceiling is not a
  spatial-grid eligibility receipt.
- `d3_stage_models.jl` accepts exactly
  `(lr_open,lr_short,lc,lp_open,lp_short,u_IDC)` for both Stage 2 and Stage 3.
  Stage 2 response-matches the five lengths to read-only
  `(Cr,Lr,Cp,Lp,Cn,Ln)` before building the finite Equivalent Circuit; Stage 3
  retains the same coordinates in the distributed model.
- `d3_exact_n_response.jl` owns the CONVERGING Finite-Order Port-Response
  Model execution and linewidth/notch extraction operators. Stage 1 defines
  their physics and contracts; it does not own an independent numerical
  target operator. Its public quantity views explicitly distinguish raw node
  fluxes, reduced physically anchored coordinates, their impedance-normalized
  oscillator representation, the fully hybridized closed normal-mode spectrum,
  and matched-open response poles.
- `d3_stage_objectives.jl` owns one revision-9 Stage-2 objective and one
  independent revision-9 Stage-3 objective. Matrix-space and open-response
  operands are provenance groups inside each joint objective, not Cost A/B/C.
- `d3_coupled_optimizer.jl` owns the reusable bounded CMA-ES-only numerical
  search. It does not own circuit parameters, topology, or multi-start
  orchestration.
- `d3_qubit_admittance.jl` derives the weighted floating-qubit differential
  admittance from the same compiled seven-node model. Its Direct route uses
  unloaded nodal current injection; its independent HB route removes only the
  temporary qL/qR probe-port shunts proven by the compiled-netlist evidence.
- `d3_stage2_result.jl` selects one optimizer incumbent, re-evaluates Direct,
  Exact-12, HB, objective, and qubit-admittance quantities from that same
  physical foundation, and transactionally publishes the six canonical Run
  artifacts. The Run specification records Q2D artifact identity, physical
  bounds, exact CMA seed/sigma/population/budgets/tolerances, and initial mean;
  the summary also retains the evaluator-owned temporary CPW/MTL reference
  topology, section discretization, root/slope settings and numerical evidence
  used to resolve `(Cr,Lr,Cp,Lp,Cn,Ln)`. Publication cross-checks them against
  the winner and foundation. It owns publication and identity checks, not
  optimization or circuit physics.
- `notebooks/python/d3_stage2_candidate_review_report.py` accepts only those
  six canonical artifacts and renders the private Human-review report. It
  rejects legacy summaries, incomplete Length-to-LC extraction evidence, and
  any replacement trace supplied outside the Run folder.

## Coordinate-, representation-, and response-explicit quantity contract

The implementation does not publish an unqualified `effective frequency`.
Every frequency or coupling identifies its coordinate basis, canonical
representation, and response boundary:

| View | Construction | Meaning |
| --- | --- | --- |
| Raw physical node fluxes | Circuit Plan and compiled seven-node matrices | Pre-transform circuit coordinates. |
| Reduced physically anchored flux-charge coordinates | Topology-declared transform followed by neutral common-charge `7 -> 6` reduction | `(q,r,p,f1,fc,f2)` is the physical coordinate basis used by `C`, `K`, and the Hamiltonian. |
| Anchored bare-coordinate oscillator representation | Apply `Z_i = sqrt((C^-1)_ii/K_ii)` independently to each reduced QRP-on coordinate, with no coordinate rotation; use the closed conservative block | The same anchored directions expressed through `(a_i,a_i^dagger)`. `h_ii/2pi` owns the anchored-bare frequencies; `h_rp/2pi` and `Delta` remain explicit report quantities. |
| Matched-open q+feedline-downfolded anchored-coordinate dynamic-effective representation | Attach the matched ports to the exact second-order six-coordinate QRP-on operator, retain `(r,p)`, and Schur-eliminate `(q,f1,fc,f2)` without diagonalizing the retained pair | Owns the Stage-2 `r/p` diagonal roots and residue-normalized complex exchange. The qubit remains through its linearized self-energy; ports are boundary self-energies, not coordinates. |
| Fully hybridized closed normal-mode spectrum | Solve `K u = omega^2 C u` for the complete QRP-on closed conservative model | Owns the closed normal-mode frequencies. The exported quantity view is a spectrum, not a reusable basis transformation. |
| Matched-open port poles | Attach the declared external ports to the QRP-on model and solve the exact open generator | Owns response-pole frequencies and linewidths under `ext,on`. These poles are not another Hamiltonian basis. |

`d3_numerical_cqed_handoff` documents the anchored normalization and returns
`h` and `Delta` together under `anchored_bare_hamiltonian`.  Exact-12 is an
invertible response representation of the same `C/K` dynamics, not a fit.
`d3_stage2_quantity_views` assembles the coordinate-, representation-, and
response-explicit Human-review surface. A Stage-2 Run must persist that exact
`foundation.quantity_views` record with the winning candidate; reconstructing
a second response-equivalent circuit from a legacy summary is not accepted
report provenance. `d3_stage2_quantity_review_payload` converts that winning
foundation into the JSON-ready, summary-SHA-bound report artifact.

The anchored-bare coefficients, closed spectrum, and matched-open poles are
reported without redefining the accepted revision-9 Stage-2 objective. That
objective retains its explicitly qualified `q+feedline -> r/p` downfolded
frequency and exchange operands. Their common source is the exact second-order
open dynamic stiffness, equivalently the complete doubled non-RWA
`h` and `Delta` dynamics: no `h`-only approximation precedes the Schur reduction.
The complex exchange is the effective off-diagonal at the two diagonal roots'
midpoint divided by their derivative-residue normalization; its coherent real
part enters the objective, while its magnitude and dissipative imaginary part
remain report quantities. HB replay remains independent closure evidence. A
future Finite-Order Port-Response scalar-formula parameter fitter must remain
separate evidence with fixed basis, normalization, sparsity, and port
conventions; no fitted trace is fabricated by the current report.

This V1 is state-independent. The full model still retains `q`, and the
Full-QRP linewidth sum still follows the assigned `q/r/p` poles, but the
dynamic-effective `r/p` block eliminates the linearized qubit only after its
self-energy is included. Qubit-state-conditioned susceptibility, dispersive
shifts, and `S21` require a later contract that retains `q` until that
state-dependent response is defined.

The IDC has one supported representation:

```text
u_IDC
  -> (C_pG_IDC, C_f_cG_IDC, C_pf_c_IDC)
  -> three-branch IDC Reusable Component
  -> Circuit Plan
  -> compiled solver circuit
```

Missing mapping provenance, a missing branch, a nonpositive capacitance, or an
out-of-domain geometry is a hard error.

The six LC values remain legal free variables only inside the explicitly named
response-equivalent fitter/Explorer. They are never Stage-2 optimizer
coordinates or fabrication witnesses. The former free-LC CMA-ES runner and
its receipt builder were removed when this ownership error was corrected.

## Execution status

`d3_procedure_catalog.v1.json` currently contains no executable optimizer
Procedure. This is intentional. Stage 2 now has the physical candidate,
response-match, objective, single-winner re-evaluation, and canonical artifact
publication interfaces, but no cataloged caller yet owns the accepted length
bounds, CMA-ES Run manifest, and evaluator callbacks end to end. The response
map therefore emits no synthetic all-length `in_domain` gate. Stage 3 remains
halted. The catalog stays fail-closed until a project-owned caller supplies
those decisions and every required extraction receipt.

The removed interactive optimizer and its parameter/config files must not be
restored. A future optimizer entry point must call `d3_stage_models.jl` and
`d3_stage_objectives.jl` directly, then hand its `OptimizationResult` to
`evaluate_stage2_winner` and `write_stage2_result`.

One canonical Stage-2 Run folder contains exactly:

```text
summary.json
history.json
s21.csv
linear-quantities.json
qubit-admittance.csv
qubit-admittance-receipt.json
```

`linear-quantities.json` and the qubit receipt are SHA-bound to the same
`summary.json`; all three carry the same four-part compiled-model identity and
complete revision-9 objective authority. The summary also hashes the history,
S21, and qubit-admittance files, and records the complete evaluator-owned
Length-to-LC response-match evidence rather than recomputing it in the report.
Its Q2D report snapshot is derived from the persisted normalized fixed-line
identity; publication and report loading both rehash that canonical identity
and reject any elementwise snapshot mismatch.
The folder is renamed into place only after all six files are complete; the
report rejects extra files or any hash, authority, Q2D identity, extraction
evidence, or model-identity mismatch. Report generation is then:

```bash
uv run python notebooks/python/d3_stage2_candidate_review_report.py \
  --run-directory <canonical-stage2-run> \
  --output-directory <private-report-output>
```

## Human-review report representation

One `report.png` is the complete Stage-2 candidate-review surface. Its fixed
reading order is:

1. Direct C/K, Exact-12, independent HB, and scalar VF-of-Direct `S21`, their
   complex residuals, and the weighted-qubit `Re(Y)` / linearized Purcell `T1`;
2. best objective cost versus valid candidate evaluation;
3. all revision-9 objective operands as target, actual, scale, residual, gate,
   and physical meaning, followed only by the Schur-extracted and scalar-VF
   comparison values;
4. fabrication lengths and IDC finger length, resolved Equivalent LC values,
   effective qubit capacitance, and floating-qubit transform;
5. Q2D setup, single-line CPW RLGC/propagation, the raw ordered MTL L/C
   matrices, and the complete Length-to-LC extraction audit;
6. report-only anchored-bare, fully hybridized closed, and matched-open views;
7. source identity, reduction boundaries, numerical closure, and optimizer
   provenance.

`notebooks/python/human_reviewable_simulation_report.py` owns the shared
`REPORT_RENDER_CONFIG` for image width, typography, spacing, table sizing, and
semantic curve colors. The D3 producer owns the plotted quantities, units,
labels, and fixed section order. Missing evidence is rendered explicitly as
`NOT_AVAILABLE`; the renderer never consults an unbound external file. The
current artifact carries requested/resolved/applied/read-back Silicon-11.9
authority, while loss tangent and conductivity remain non-authoritative and
unavailable; the report preserves that distinction.

The converging V1 review artifact remains PNG. A later PDF export should render
the same fixed sections as separate logical pages and merge those pages; it
must not turn this vertically continuous report into one oversized PDF page.

## Validation

```bash
julia --project=core/julia/SuperconductingCircuitsCore \
  scripts/build/export_d3_schematic_exports.jl --check

uv run --project core/python/circuit_libraries \
  python scripts/build/render_circuit_drawings.py --check \
  --diagram circuit_plan.d3_intrinsic_purcell_equivalent \
  --diagram circuit_plan.d3_intrinsic_purcell_hybridized \
  --diagram circuit_plan.d3_linewidth_la_equivalent \
  --diagram circuit_plan.d3_linewidth_la_hybridized \
  --diagram circuit_plan.d3_intrinsic_pair_notch_equivalent \
  --diagram circuit_plan.d3_intrinsic_pair_notch_hybridized

uv run python scripts/build/d3_design_platform.py list
```

The last command must print `[]` until the complete three-branch Stage
evaluators are connected.
