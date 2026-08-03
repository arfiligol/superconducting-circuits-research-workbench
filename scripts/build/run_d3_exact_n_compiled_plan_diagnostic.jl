# Produce a non-promotable five-slot Exact-N diagnostic from the canonical
# Equivalent CircuitPlan. The IDC triplet is explicit because no accepted
# geometry-to-three-capacitance map exists yet. This runner must not be used as
# a Stage-2 optimizer or design-result producer.

using Printf
using SHA
using SuperconductingCircuitsCore

const JSON3 = SuperconductingCircuitsCore.JSON3

const WORKBENCH_ROOT = normpath(joinpath(@__DIR__, "..", ".."))
const WORKSPACE_ROOT = normpath(joinpath(WORKBENCH_ROOT, ".."))
const D3_NOTEBOOK_DIR = joinpath(
    WORKBENCH_ROOT,
    "notebooks",
    "pluto",
    "D3 Intrinsic Purcell Filter Design",
)

include(joinpath(D3_NOTEBOOK_DIR, "d3_circuit_plans.jl"))
include(joinpath(D3_NOTEBOOK_DIR, "d3_exact_n_response.jl"))

const D3_CIRCUIT_PLAN_SOURCE = joinpath(D3_NOTEBOOK_DIR, "d3_circuit_plans.jl")
const D3_EXACT_N_SOURCE = joinpath(D3_NOTEBOOK_DIR, "d3_exact_n_response.jl")
const D3_DIAGNOSTIC_RUNNER_SOURCE = abspath(@__FILE__)

_matrix_rows(matrix) = [collect(row) for row in eachrow(matrix)]

function _complex_matrix_record(matrix)
    values = Matrix{ComplexF64}(matrix)
    return Dict(
        "real" => _matrix_rows(real.(values)),
        "imag" => _matrix_rows(imag.(values)),
    )
end

function _usage()
    return """
    usage:
      julia scripts/build/run_d3_exact_n_compiled_plan_diagnostic.jl \\
        OUTPUT_DIRECTORY C_PG_FF C_FCG_FF C_PFC_FF

    The three IDC values are explicit topology-diagnostic inputs in fF. They
    are not a replacement for the required u_IDC -> three-branch EM mapping.
    """
end

length(ARGS) == 4 || error(_usage())
output_directory = abspath(ARGS[1])
idc_fF = (
    cpg=parse(Float64, ARGS[2]),
    cfcg=parse(Float64, ARGS[3]),
    cpfc=parse(Float64, ARGS[4]),
)
all(value -> isfinite(value) && value > 0, values(idc_fF)) || error(
    "Explicit diagnostic IDC branches must be finite and positive.",
)

search_evidence_path = joinpath(
    WORKBENCH_ROOT,
    "build",
    "research",
    "d3_forward_circuit_validation_v2",
    "d3-forward-circuit-run.v2.search-evidence.json",
)
qubit_input_path = joinpath(
    WORKBENCH_ROOT,
    "build",
    "private_inputs",
    "d3_retained_qubit_gap_sweep.json",
)
isfile(search_evidence_path) || error(
    "Missing legacy element-seed evidence: $(search_evidence_path)",
)
isfile(qubit_input_path) || error(
    "Missing retained Q3D gap input: $(qubit_input_path)",
)

search_evidence = JSON3.read(read(search_evidence_path, String), Dict{String,Any})
search_evidence["schema_version"] == "d3-forward-design-search-evidence.v1" ||
    error("Legacy element-seed evidence schema is incompatible.")
search_evidence["status"] == "complete" ||
    error("Legacy element-seed evidence must be complete.")
selected_candidates = Dict(
    Float64(candidate["slot_hz"]) => candidate
    for candidate in search_evidence["candidates"]
    if candidate["selected"] === true
)
slot_hz = sort(collect(keys(selected_candidates)))
slot_hz == [5.52e9, 5.76e9, 6.00e9, 6.24e9, 6.48e9] || error(
    "Legacy element-seed evidence does not cover the canonical five slots.",
)

qubit_input = JSON3.read(read(qubit_input_path, String), Dict{String,Any})
qubit_input["schema_version"] ==
    "d3-retained-qubit-readout-maxwell-gap-sweep.v1" ||
    error("Retained Q3D gap input schema is incompatible.")
nominal_samples = [
    sample for sample in qubit_input["samples"]
    if Float64(sample["gap_um"]) == 8.0
]
length(nominal_samples) == 1 ||
    error("Retained Q3D gap input must contain exactly one raw 8 um sample.")
qubit = only(nominal_samples)["physical_branches_fF"]
lj_per_junction_h = Float64(qubit_input["L_J_per_junction_nH"]) * 1e-9

mkpath(output_directory)
diagnostic_id = basename(output_directory)
csv_path = joinpath(output_directory, "diagnostic-exact-n-s21.csv")
summary_path = joinpath(output_directory, "diagnostic-exact-n-summary.json")

summary_slots = Any[]
open(csv_path, "w") do io
    println(
        io,
        "artifact_status,diagnostic_id,idc_authority,element_seed_authority,slot_hz,representation,frequency_hz,s21_real,s21_imag,s21_magnitude,s21_db,residual_to_direct_real,residual_to_direct_imag,residual_to_direct_magnitude",
    )
    for slot in slot_hz
        candidate = selected_candidates[slot]
        parameters = candidate["parameters"]
        built = build_d3_intrinsic_purcell_equivalent_circuit_plan(
            id="d3-exact-n-diagnostic-$(Int(round(slot)))",
            idc_filter_ground_capacitance_f=idc_fF.cpg * 1e-15,
            idc_feedline_ground_capacitance_f=idc_fF.cfcg * 1e-15,
            idc_mutual_capacitance_f=idc_fF.cpfc * 1e-15,
            readout_capacitance_f=
                Float64(parameters["response_match_Cr_f"]),
            readout_inductance_h=
                Float64(parameters["response_match_Lr_h"]),
            filter_capacitance_f=
                Float64(parameters["response_match_Cp_f"]),
            filter_inductance_h=
                Float64(parameters["response_match_Lp_h"]),
            bridge_capacitance_f=
                Float64(parameters["response_match_Cn_f"]),
            bridge_inductance_h=
                Float64(parameters["response_match_Ln_h"]),
            c0r_f=Float64(qubit["C0r_fF"]) * 1e-15,
            c01_f=Float64(qubit["C01_fF"]) * 1e-15,
            c02_f=Float64(qubit["C02_fF"]) * 1e-15,
            c12_qubit_f=Float64(qubit["C12_fF"]) * 1e-15,
            cr1_f=Float64(qubit["Cr1_fF"]) * 1e-15,
            cr2_f=Float64(qubit["Cr2_fF"]) * 1e-15,
            l_j_per_junction_h=lj_per_junction_h,
        )
        model = d3_exact_n_compiled_model(built)
        cqed = d3_numerical_cqed_handoff(model)
        matrix_metrics = d3_stage2_matrix_metrics(
            model;
            cqed_handoff=cqed,
        )
        frequencies = collect(range(
            slot - 0.45e9,
            slot + 0.45e9;
            step=0.1e6,
        ))
        closure = d3_exact_n_response_closure(
            model,
            frequencies;
            cqed_handoff=cqed,
        )
        trace = closure.direct
        for (representation, values) in (
            (:direct_equivalent, closure.direct.s21),
            (:exact_doubled_12, closure.analytical.exact.s21),
        )
            for (frequency, value, direct_value) in zip(
                trace.frequency_hz,
                values,
                closure.direct.s21,
            )
                magnitude = abs(value)
                residual = value - direct_value
                @printf(
                    io,
                    "diagnostic_not_promotable,%s,explicit_topology_diagnostic_only,legacy_response_matched_seed_only,%.1f,%s,%.1f,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g\n",
                    diagnostic_id,
                    slot,
                    String(representation),
                    frequency,
                    real(value),
                    imag(value),
                    magnitude,
                    20 * log10(max(magnitude, floatmin(Float64))),
                    real(residual),
                    imag(residual),
                    abs(residual),
                )
            end
        end
        push!(
            summary_slots,
            Dict(
                "slot_hz" => slot,
                "legacy_seed_candidate_id" => candidate["candidate_id"],
                "equivalent_parameters" => Dict(
                    "Cr_f" => Float64(parameters["response_match_Cr_f"]),
                    "Lr_h" => Float64(parameters["response_match_Lr_h"]),
                    "Cp_f" => Float64(parameters["response_match_Cp_f"]),
                    "Lp_h" => Float64(parameters["response_match_Lp_h"]),
                    "Cn_f" => Float64(parameters["response_match_Cn_f"]),
                    "Ln_h" => Float64(parameters["response_match_Ln_h"]),
                ),
                "coordinate_order" => string.(model.coordinate_order),
                "physical_node_order" => model.physical_node_order,
                "physical_node_capacitance_matrix_f" => _matrix_rows(
                    model.conservative_nodal_model.capacitance[
                        model.compiled_to_physical_permutation,
                        model.compiled_to_physical_permutation,
                    ],
                ),
                "physical_node_inverse_inductance_matrix_h_inv" => _matrix_rows(
                    model.conservative_nodal_model.inverse_inductance[
                        model.compiled_to_physical_permutation,
                        model.compiled_to_physical_permutation,
                    ],
                ),
                "node_to_local_transform" =>
                    _matrix_rows(model.node_to_local_transform),
                "common_charge_reduction" => Dict(
                    string(key) => value
                    for (key, value) in pairs(model.common_charge_reduction)
                ),
                "capacitance_matrix_f" => _matrix_rows(model.capacitance),
                "inverse_capacitance_matrix_f_inv" =>
                    _matrix_rows(cqed.legendre.inverse_capacitance_f_inv),
                "inverse_inductance_matrix_h_inv" =>
                    _matrix_rows(model.inverse_inductance),
                "number_conserving_matrix_rad_s" =>
                    _matrix_rows(
                        cqed.anchored_bare_hamiltonian.number_conserving_matrix_rad_s,
                    ),
                "pairing_matrix_rad_s" =>
                    _matrix_rows(cqed.exact.pairing_matrix_rad_s),
                "exact_doubled_matrix_rad_s" =>
                    _matrix_rows(cqed.exact.doubled_matrix_rad_s),
                "port_selector" => _matrix_rows(model.selector),
                "port_maps" => Dict(
                    "direct_scattering" => _complex_matrix_record(
                        cqed.port_response.direct_scattering,
                    ),
                    "exact_open_generator_per_s" => _complex_matrix_record(
                        cqed.port_response.exact.open_generator_per_s,
                    ),
                    "exact_drive_per_s" => _complex_matrix_record(
                        cqed.port_response.exact.drive_per_s,
                    ),
                    "exact_observation" => _complex_matrix_record(
                        cqed.port_response.exact.observation,
                    ),
                ),
                "analytical_closure" => Dict(
                    "exact_status" => String(closure.exact_closure_status),
                    "max_abs_exact_scattering" =>
                        closure.residuals.max_abs_exact_scattering,
                    "max_abs_exact_s21" =>
                        closure.residuals.max_abs_exact_s21,
                    "exact_max_unitarity_defect" =>
                        closure.analytical.passivity.exact_max_unitarity_defect,
                    "structural_free_mode_count" =>
                        cqed.exact.structural_free_mode_count,
                ),
                "matrix_metrics" => Dict(
                    "operand_authority" =>
                        String(matrix_metrics.operand_authority),
                    "metrics" => Dict(
                        "fr_circuit_h_rr_pre_downfold_report_only_hz" =>
                            matrix_metrics.fr_circuit_h_rr_pre_downfold_report_only_hz,
                        "fp_circuit_h_pp_pre_downfold_report_only_hz" =>
                            matrix_metrics.fp_circuit_h_pp_pre_downfold_report_only_hz,
                        "J_circuit_h_rp_pre_downfold_report_only_hz" =>
                            matrix_metrics.J_circuit_h_rp_pre_downfold_report_only_hz,
                        "fq_circuit_h_qq_pre_downfold_report_only_hz" =>
                            matrix_metrics.fq_circuit_h_qq_pre_downfold_report_only_hz,
                    ),
                ),
                "cqed_hashes" => Dict(
                    string(key) => value for (key, value) in pairs(cqed.hashes)
                ),
                "cqed_source_model_identity" => Dict(
                    string(key) => value
                    for (key, value) in pairs(cqed.source_model_identity)
                ),
                "open_poles" => [
                    Dict(
                        "frequency_real_hz" => real(pole),
                        "frequency_imag_hz" => imag(pole),
                        "linewidth_hz" => trace.poles.linewidths_hz[index],
                    )
                    for (index, pole) in enumerate(trace.poles.frequencies_hz)
                ],
                "provenance" => Dict(
                    string(key) => value
                    for (key, value) in pairs(model.provenance)
                ),
            ),
        )
    end
end

summary = Dict(
    "schema_version" => "d3-exact-n-compiled-plan-diagnostic.v3",
    "diagnostic_id" => diagnostic_id,
    "status" => "diagnostic_not_promotable",
    "reason" =>
        "Exact-N implementation validation with legacy direct-retained-row-sum qubit projection and legacy LC seeds, before accepted IDC mapping and Stage-2 optimization",
    "model_authority" =>
        "canonical Equivalent CircuitPlan -> compiled netlist -> Exact-7 -> neutral-qubit Exact-6 -> Exact-12 analytical port maps",
    "idc_input" => Dict(
        "authority" => "explicit_topology_diagnostic_only",
        "C_pG_IDC_fF" => idc_fF.cpg,
        "C_fcG_IDC_fF" => idc_fF.cfcg,
        "C_pfc_IDC_fF" => idc_fF.cpfc,
    ),
    "qubit_input" => Dict(
        "schema_version" => qubit_input["schema_version"],
        "source_sha256" => qubit_input["source_artifact"]["sha256"],
        "gap_um" => 8.0,
        "sample_policy" => "raw_q3d_sample",
        "projection_authority" => "legacy_direct_retained_row_sum",
        "promotion_eligible" => false,
        "branches_fF" => qubit,
        "L_J_per_junction_nH" => qubit_input["L_J_per_junction_nH"],
    ),
    "element_seed_authority" =>
        "legacy response-matched values used only to exercise the corrected Exact-N path",
    "implementation_sources" => [
        Dict(
            "path" => relpath(path, WORKBENCH_ROOT),
            "sha256" => bytes2hex(SHA.sha256(read(path))),
        )
        for path in (
            D3_CIRCUIT_PLAN_SOURCE,
            D3_EXACT_N_SOURCE,
            D3_DIAGNOSTIC_RUNNER_SOURCE,
        )
    ],
    "slots" => summary_slots,
)
open(summary_path, "w") do io
    JSON3.pretty(io, summary)
    println(io)
end

println(summary_path)
println(csv_path)
