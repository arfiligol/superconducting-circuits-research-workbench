# D3 Intrinsic Interferometric Purcell Filter

The host project owns the target quantities and their physical meaning:

- `SCQ_Design/docs/design-targets/d3-intrinsic-interferometric-purcell-filter.qmd`
- `SCQ_Design/docs/design-targets/contracts/d3-same-face-resonators-opposite-face-qubit-j5-k20-gap8.v1.json`

Workbench owns the current D3 implementation described below. Historical
implementations remain available through Git history, not as parallel runtime
authorities.

## Current search path

`d3_circuit_plans.jl` builds the distributed/lumped hybridized CircuitPlan.
The public optimizer candidate has exactly five coordinates:

```text
(lr_open_m, l_short_m, lc_m, lp_open_m, u_IDC)
```

The compiler expands `l_short_m` into equal internal `lr_short_m` and
`lp_short_m` fields. Those internal fields are not independently variable.

`d3_rev10_models.jl` binds the sealed Q2D/Q3D/IDC/feedline inputs, freezes one
fixed-node topology, injects each candidate's numerical C/K values, and evaluates
one complete-complement R=(r,p) targeted Schur model. Its current public path is:

```text
bind_d3_direct_hybridized_inputs
  -> d3_direct_hybridized_grid_plan
  -> build_d3_targeted_schur_objective_context
  -> d3_direct_cared_outputs
  -> d3_rev10_targeted_schur_metrics
```

The cared output contains the anchored-bare complex diagonal roots and their
per-member linewidths, the linewidth sum, residue-normalized midpoint exchange,
and the intrinsic-pair cofactor notch. It does not run a global Full-QRP pole
assignment, build an Equivalent candidate, fit a response, or evaluate the
Objective. Expected candidate/numerical failures throw
`D3TargetedSchurNotEvaluable`; programming/API errors propagate.

`d3_rev10_objective.jl` owns the sole current Objective. For each ordered slot
5.6, 5.7, 5.8, 5.9, 6.0, or 6.1 GHz it evaluates:

```text
cost = sum(abs2, (100r_r, 100r_p, 100r_n, 10r_J, 10r_kappa))
```

where every `r` is a signed relative residual. The five operands are
`f_r`, `f_p`, `f_n`, `|Re J|`, and `kappa_r + kappa_p`.
Participation is absent and deferred to a future fully hybridized-pole
analysis.

`d3_coupled_optimizer.jl` provides the deterministic CMA-ES mechanics.
`d3_rev10_slot_search.v1.json` binds the current six-slot diagnostic search,
and `d3_rev10_slot_search.jl` runs one selected slot using the shared metrics
and Objective. Search candidates use the fixed N context; only the selected
winner receives the Human-accepted N to 2N adjacent-change check over the same
five quantities.

## Supporting calculations

- `d3_exact_n_response.jl` owns exact C/K/G response operators, targeted
  diagonal-root/J/notch/linewidth extraction, port response, and optional
  downstream Hamiltonian/cQED diagnostics. Those optional diagnostics are not
  Objective operands.

## Source constraints

The IDC runtime is interpolation-only on its declared inclusive source support.
Missing provenance, an incomplete three-branch IDC mapping, nonpositive
capacitance, or out-of-support `u_IDC` fails before circuit construction.
All fixed-input and targeted-context identities are persisted with results.

## Run one slot

```bash
JULIA_NUM_THREADS=16 OPENBLAS_NUM_THREADS=1 \
julia --project=core/julia/SuperconductingCircuitsCore \
  "notebooks/pluto/D3 Intrinsic Purcell Filter Design/d3_rev10_slot_search.jl" \
  --slot-ghz 5.6 \
  --q3d-input <q3d-input.json> \
  --idc-input <idc-input.json> \
  --output-dir <new-output-directory>
```

Use `--dry-run` to validate identities/context without creating evidence, or
`--single-point` to evaluate the declared slot seed once.

## Focused validation

```bash
julia scripts/test/test_d3_rev10_targeted_schur.jl
julia scripts/test/test_d3_rev10_objective.jl
julia scripts/test/test_d3_complete_complement_rp_operator.jl
julia scripts/test/test_d3_coupled_optimizer_analytical.jl
```
