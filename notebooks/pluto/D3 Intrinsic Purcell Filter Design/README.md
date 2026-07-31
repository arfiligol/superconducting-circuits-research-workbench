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
- `d3_resonator_input.jl` validates the Human-selected continuous-upper-ground
  public Q2D input at `(w,s,d,h)=(3,3,3,8) um`. Both physical stages reject
  any other wrapper SHA, geometry, matrices, or coupling orientation and bind
  the numerical section length into a shared fixed-line identity.
- `d3_stage_models.jl` accepts exactly
  `(lr_open,lr_short,lc,lp_open,lp_short,u_IDC)` for both Stage 2 and Stage 3.
  Stage 2 response-matches the five lengths to read-only
  `(Cr,Lr,Cp,Lp,Cn,Ln)` before building the finite Equivalent Circuit; Stage 3
  retains the same coordinates in the distributed model.
- `d3_exact_n_response.jl` owns the CONVERGING Finite-Order Port-Response
  Model execution and linewidth/notch extraction operators. Stage 1 defines
  their physics and contracts; it does not own an independent numerical
  target operator.
- `d3_stage_objectives.jl` owns one revision-7 Stage-2 objective and one
  independent revision-7 Stage-3 objective. Matrix-space and open-response
  operands are provenance groups inside each joint objective, not Cost A/B/C.
- `d3_coupled_optimizer.jl` owns the reusable bounded CMA-ES-only numerical
  search. It does not own circuit parameters, topology, or multi-start
  orchestration.

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
Procedure. This is intentional. Stage 2 now has the physical coordinate and
response-match interface but still needs a new CMA-ES route over the accepted
length bounds; the response map therefore emits no synthetic all-length
`in_domain` gate. Stage 3 remains halted. The catalog stays fail-closed until
both candidate evaluators supply every required extraction receipt end to end.

The removed interactive optimizer and its parameter/config files must not be
restored. A future optimizer entry point must call `d3_stage_models.jl` and
`d3_stage_objectives.jl` directly.

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
