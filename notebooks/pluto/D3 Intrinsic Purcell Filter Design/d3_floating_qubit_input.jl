# This module owns the private full-Maxwell floating-qubit input reduction used
# by the current D3 optimizer and nominal validation. It does not run HB, alter
# optimizer state, choose thresholds, or persist historical comparison output.

module D3FloatingQubitInput

using LinearAlgebra
using SHA
using SuperconductingCircuitsCore

const JSON3 = SuperconductingCircuitsCore.JSON3

export load_floating_qubit_nominal_input,
    floating_qubit_coupling_off_frequency_hz, floating_qubit_physics_diagnostics,
    floating_qubit_reduction_evidence

const D3_FLOATING_QUBIT_LEGACY_SCHEMA = "d3-floating-qubit-maxwell.v1"
const D3_FLOATING_QUBIT_SCHEMA = "d3-readout-open-side-maxwell.v2"
const D3_LEGACY_READOUT_CAPACITANCE_OWNERSHIP =
    "distributed_resonator_owns_self_capacitance"
const D3_READOUT_CAPACITANCE_OWNERSHIP =
    "localized_open_side_interface_owns_reduced_readout_shunt"
const PLANCK_CONSTANT_J_S = 6.62607015e-34
const ELEMENTARY_CHARGE_C = 1.602176634e-19
const FLUX_QUANTUM_WB = 2.067833848e-15

file_sha256(path) = open(path, "r") do io
    bytes2hex(SHA.sha256(io))
end

function _required_nonempty_label(value, context)
    label = strip(String(value))
    isempty(label) && error("$(context) must be a nonempty conductor label.")
    return label
end

function _validate_open_side_region_ownership(payload)
    region = payload["region_ownership"]
    Set(keys(region)) == Set([
        "modeling_mode",
        "local_region_id",
        "readout_line_cut_plane_id",
        "distributed_readout_length_reference",
        "distributed_line_excludes_local_region",
        "electric_energy_owner",
        "magnetic_phase_treatment",
        "valid_frequency_range_hz",
        "source_artifact_sha256",
    ]) || error("Open-side region_ownership must contain exactly the v2 fields.")
    region["modeling_mode"] == "full_region_replacement" || error(
        "D3 open-side v2 currently supports only full_region_replacement.",
    )
    _required_nonempty_label(region["local_region_id"], "local_region_id")
    _required_nonempty_label(
        region["readout_line_cut_plane_id"], "readout_line_cut_plane_id",
    )
    region["distributed_readout_length_reference"] ==
        "shorted_end_to_open_side_local_cut_plane" || error(
        "Distributed readout length must stop at the declared open-side local cut plane.",
    )
    region["distributed_line_excludes_local_region"] === true || error(
        "The distributed readout must exclude the complete open-side local extraction region.",
    )
    region["electric_energy_owner"] == "this_maxwell_matrix" || error(
        "The v2 local Maxwell matrix must own the open-side electric energy.",
    )
    phase = region["magnetic_phase_treatment"]
    Set(keys(phase)) == Set([
        "mode", "evidence_id", "evaluation_frequency_hz", "max_abs_phase_error_rad",
    ]) || error("Open-side magnetic_phase_treatment must contain exactly the v2 fields.")
    phase["mode"] in (
        "negligible_with_bound",
        "restored_by_local_equivalent",
    ) || error("Unsupported open-side magnetic/phase treatment.")
    _required_nonempty_label(phase["evidence_id"], "magnetic_phase_treatment.evidence_id")
    evaluation_frequency_hz = Float64(phase["evaluation_frequency_hz"])
    isfinite(evaluation_frequency_hz) && evaluation_frequency_hz > 0 || error(
        "Open-side magnetic/phase evaluation frequency must be finite and positive.",
    )
    phase_error = Float64(phase["max_abs_phase_error_rad"])
    isfinite(phase_error) && phase_error >= 0 || error(
        "Open-side maximum phase error must be finite and nonnegative.",
    )
    validity = Float64.(collect(region["valid_frequency_range_hz"]))
    length(validity) == 2 && all(isfinite, validity) &&
        0 < validity[1] < validity[2] || error(
        "Open-side valid_frequency_range_hz must be two increasing positive bounds.",
    )
    source_sha256 = String(region["source_artifact_sha256"])
    occursin(r"^[0-9a-f]{64}$", source_sha256) || error(
        "Open-side source artifact identity must be lowercase SHA-256.",
    )
    return Dict{String,Any}(String(key) => value for (key, value) in region)
end

function _reduce_floating_coupler_pads(payload)
    schema = String(payload["schema_version"])
    labels = [_required_nonempty_label(label, "conductor_labels") for label in payload["conductor_labels"]]
    length(labels) == length(unique(labels)) || error("Full Maxwell conductor labels must be unique.")
    matrix_rows = payload["maxwell_capacitance_matrix_fF"]
    length(matrix_rows) == length(labels) || error("Maxwell matrix row count must equal conductor label count.")
    all(row -> length(row) == length(labels), matrix_rows) || error("Maxwell matrix must be square.")
    matrix_fF = reduce(vcat, (permutedims(Float64.(collect(row))) for row in matrix_rows))
    all(isfinite, matrix_fF) || error("Maxwell matrix must contain only finite capacitances.")
    isapprox(matrix_fF, transpose(matrix_fF); rtol = 1e-9, atol = 1e-9) || error(
        "Maxwell matrix must be symmetric within 1e-9 fF.",
    )

    roles = payload["role_mapping"]
    Set(keys(roles)) == Set([
        "reference_conductor", "floating_coupler_pads", "qubit_island_1",
        "qubit_island_2", "readout_attachment",
    ]) || error("Floating-qubit role_mapping must contain exactly the v1 conductor roles.")
    reference = _required_nonempty_label(roles["reference_conductor"], "reference_conductor")
    floating = [_required_nonempty_label(label, "floating_coupler_pads") for label in roles["floating_coupler_pads"]]
    length(floating) == 4 || error("D3 v1 requires exactly four floating Coupler-pad labels.")
    length(unique(floating)) == 4 || error("Floating Coupler-pad labels must be unique.")
    retained = [
        _required_nonempty_label(roles["qubit_island_1"], "qubit_island_1"),
        _required_nonempty_label(roles["qubit_island_2"], "qubit_island_2"),
        _required_nonempty_label(roles["readout_attachment"], "readout_attachment"),
    ]
    partition = vcat([reference], floating, retained)
    length(partition) == length(unique(partition)) || error("Reference, floating, and retained conductor roles must be disjoint.")
    Set(partition) == Set(labels) || error("Reference, floating, and retained roles must exhaust conductor_labels exactly.")
    ownership = String(payload["readout_self_capacitance_ownership"])
    region_ownership = if schema == D3_FLOATING_QUBIT_SCHEMA
        ownership == D3_READOUT_CAPACITANCE_OWNERSHIP || error(
            "D3 open-side v2 must assign the reduced readout shunt to the localized interface.",
        )
        _validate_open_side_region_ownership(payload)
    else
        ownership == D3_LEGACY_READOUT_CAPACITANCE_OWNERSHIP || error(
            "Legacy D3 v1 must retain its historical readout-capacitance ownership label.",
        )
        nothing
    end

    retained_indexes = [only(findall(==(label), labels)) for label in retained]
    floating_indexes = [only(findall(==(label), labels)) for label in floating]
    c_rr = matrix_fF[retained_indexes, retained_indexes]
    c_rf = matrix_fF[retained_indexes, floating_indexes]
    c_ff = matrix_fF[floating_indexes, floating_indexes]
    minimum(eigvals(Symmetric(c_ff))) > 0 || error("Floating Coupler-pad Maxwell block must be passive positive definite.")
    solved = try
        c_ff \ transpose(c_rf)
    catch exception
        error("Floating Coupler-pad Maxwell block is not solvable: $(sprint(showerror, exception))")
    end
    all(isfinite, solved) || error("Floating Coupler-pad solve produced non-finite values.")
    reduced_fF = c_rr - c_rf * solved
    isapprox(reduced_fF, transpose(reduced_fF); rtol = 1e-9, atol = 1e-9) || error(
        "Kron-reduced retained Maxwell matrix is not symmetric.",
    )
    minimum(eigvals(Symmetric(reduced_fF))) > 0 || error("Kron-reduced retained Maxwell matrix is not passive positive definite.")
    mapped = (
        C01_fF = sum(reduced_fF[1, :]),
        C02_fF = sum(reduced_fF[2, :]),
        C12_fF = -reduced_fF[1, 2],
        Cr1_fF = -reduced_fF[1, 3],
        Cr2_fF = -reduced_fF[2, 3],
        C0r_fF = schema == D3_FLOATING_QUBIT_SCHEMA ? sum(reduced_fF[3, :]) : 0.0,
    )
    all(value -> isfinite(value) && value > 0, (
        mapped.C01_fF, mapped.C02_fF, mapped.C12_fF,
        mapped.Cr1_fF, mapped.Cr2_fF,
    )) || error(
        "Kron-reduced physical coupling branches must all be finite and positive.",
    )
    mapped.C0r_fF >= 0 || error("Kron-reduced local readout shunt must be nonnegative.")
    extracted_c0r_fF = sum(reduced_fF[3, :])
    isfinite(extracted_c0r_fF) && extracted_c0r_fF > 0 || error(
        "Kron-reduced Maxwell block must contain a positive readout-to-ground shunt.",
    )
    return mapped, (
        ordered_labels = labels,
        retained_labels = retained,
        floating_labels = floating,
        reference_label = reference,
        reduced_maxwell_matrix_fF = [collect(row) for row in eachrow(reduced_fF)],
        mapped_branches_fF = mapped,
        readout_reduced_diagonal_fF = reduced_fF[3, 3],
        extracted_C0r_fF = extracted_c0r_fF,
        readout_diagonal_instantiated = schema == D3_FLOATING_QUBIT_SCHEMA,
        readout_diagonal_lowering = schema == D3_FLOATING_QUBIT_SCHEMA ?
            "C0r_equals_reduced_readout_row_sum" :
            "legacy_provenance_only_not_lowered",
        readout_self_capacitance_ownership = ownership,
        open_side_contract_status = schema == D3_FLOATING_QUBIT_SCHEMA ?
            "canonical_candidate" : "legacy_historical_only",
        input_schema = schema,
        region_ownership = region_ownership,
        reduction_method = "schur_complement_linear_solve_q_f_equals_zero",
    )
end

"""Read and reduce one private full-Maxwell input without retaining its values in source."""
function load_floating_qubit_nominal_input(
    path,
    constructor;
    require_open_side_contract = false,
)
    input_path = abspath(String(path))
    isfile(input_path) || error("Floating-qubit nominal input does not exist: $(input_path)")
    payload = JSON3.read(read(input_path, String), Dict{String,Any})
    common_keys = [
        "schema_version",
        "model_id",
        "capacitance_source_id",
        "capacitance_unit",
        "conductor_labels",
        "maxwell_capacitance_matrix_fF",
        "role_mapping",
        "readout_self_capacitance_ownership",
        "L_J_per_junction_nH",
    ]
    schema = String(payload["schema_version"])
    required_keys = Set(schema == D3_FLOATING_QUBIT_SCHEMA ?
        vcat(common_keys, ["region_ownership"]) : common_keys)
    Set(keys(payload)) == required_keys || error(
        "Floating-qubit nominal JSON keys must exactly match its declared Maxwell contract.",
    )
    schema in (D3_FLOATING_QUBIT_LEGACY_SCHEMA, D3_FLOATING_QUBIT_SCHEMA) || error(
        "Floating-qubit schema must be legacy v1 or canonical open-side v2.",
    )
    require_open_side_contract && schema != D3_FLOATING_QUBIT_SCHEMA && error(
        "open_side_contract_required: canonical D3 design requires $(D3_FLOATING_QUBIT_SCHEMA); " *
        "the v1 input is historical replay only because it omits local-region/cut-plane ownership.",
    )
    payload["capacitance_unit"] == "fF" || error("Full Maxwell capacitance unit must be fF.")
    mapped, reduction = _reduce_floating_coupler_pads(payload)
    model = constructor(
        model_id = payload["model_id"],
        capacitance_source_id = payload["capacitance_source_id"],
        C01_fF = mapped.C01_fF,
        C02_fF = mapped.C02_fF,
        C12_fF = mapped.C12_fF,
        Cr1_fF = mapped.Cr1_fF,
        Cr2_fF = mapped.Cr2_fF,
        C0r_fF = mapped.C0r_fF,
        L_J_per_junction_nH = payload["L_J_per_junction_nH"],
        electrostatic_reduction = reduction,
    )
    return (model = model, input_path = input_path, input_sha256 = file_sha256(input_path))
end

"""Return the diagonal-preserving coupling-off floating-qubit frequency.

Each removed readout coupling branch becomes one equal shunt at each endpoint,
so the qubit-island ground capacitances retain `Cr1` and `Cr2` loading.
"""
function floating_qubit_coupling_off_frequency_hz(qubit)
    c01 = Float64(qubit.C01_fF) * 1e-15
    c02 = Float64(qubit.C02_fF) * 1e-15
    c12 = Float64(qubit.C12_fF) * 1e-15
    cr1 = Float64(qubit.Cr1_fF) * 1e-15
    cr2 = Float64(qubit.Cr2_fF) * 1e-15
    cg1 = c01 + cr1
    cg2 = c02 + cr2
    effective_capacitance = c12 + cg1 * cg2 / (cg1 + cg2)
    effective_inductance = Float64(qubit.L_J_per_junction_nH) * 1e-9 / 2
    return 1 / (2π * sqrt(effective_inductance * effective_capacitance))
end

"""Return auditable linearized and first-order transmon diagnostics."""
function floating_qubit_physics_diagnostics(qubit; f01_target_hz)
    c01 = Float64(qubit.C01_fF) * 1e-15
    c02 = Float64(qubit.C02_fF) * 1e-15
    c12 = Float64(qubit.C12_fF) * 1e-15
    cr1 = Float64(qubit.Cr1_fF) * 1e-15
    cr2 = Float64(qubit.Cr2_fF) * 1e-15
    effective_capacitance_f = c12 + (c01 + cr1) * (c02 + cr2) / (c01 + cr1 + c02 + cr2)
    linearized_frequency_hz = floating_qubit_coupling_off_frequency_hz(qubit)
    ec_over_h_hz = ELEMENTARY_CHARGE_C^2 / (2 * effective_capacitance_f * PLANCK_CONSTANT_J_S)
    lj_h = Float64(qubit.L_J_per_junction_nH) * 1e-9
    total_ej_over_h_hz = 2 * (FLUX_QUANTUM_WB / (2π))^2 / (lj_h * PLANCK_CONSTANT_J_S)
    f01_hz = linearized_frequency_hz - ec_over_h_hz
    target_hz = Float64(f01_target_hz)
    isfinite(target_hz) && target_hz > 0 || error("Qubit f01 target must be finite and positive.")
    return (
        effective_differential_coupling_off_capacitance_fF = effective_capacitance_f * 1e15,
        linearized_lc_frequency_hz = linearized_frequency_hz,
        ec_over_h_hz = ec_over_h_hz,
        total_ej_over_h_hz = total_ej_over_h_hz,
        first_order_transmon_f01_hz = f01_hz,
        human_target_f01_hz = target_hz,
        first_order_transmon_f01_residual_hz = f01_hz - target_hz,
    )
end

"""Return JSON/hash-safe reduction and qubit-physics provenance."""
function floating_qubit_reduction_evidence(
    qubit;
    f01_target_hz,
    expected_L_J_per_junction_nH,
    target_contract_id,
    target_contract_sha256,
)
    reduction = qubit.electrostatic_reduction
    physics = floating_qubit_physics_diagnostics(qubit; f01_target_hz = f01_target_hz)
    expected_lj = Float64(expected_L_J_per_junction_nH)
    isfinite(expected_lj) && expected_lj > 0 || error("Canonical per-junction L_J target must be finite and positive.")
    Float64(qubit.L_J_per_junction_nH) == expected_lj || error(
        "Private floating-qubit L_J $(qubit.L_J_per_junction_nH) nH disagrees with canonical target $(expected_lj) nH per junction.",
    )
    contract_id = strip(String(target_contract_id))
    isempty(contract_id) && error("Canonical qubit target contract id must be nonempty.")
    contract_sha256 = String(target_contract_sha256)
    occursin(r"^[0-9a-f]{64}$", contract_sha256) || error("Canonical qubit target contract identity must be lowercase SHA-256.")
    return Dict(
        "schema_version" => reduction.input_schema,
        "model_id" => qubit.model_id,
        "capacitance_source_id" => qubit.capacitance_source_id,
        "topology_id" => reduction.input_schema == D3_FLOATING_QUBIT_SCHEMA ?
            "d3-open-side-local-maxwell-kron-reduced-six-branch-two-parallel-lj-v2" :
            "d3-floating-qubit-kron-reduced-five-branch-two-parallel-lj-v1",
        "ordered_labels" => reduction.ordered_labels,
        "partition" => Dict(
            "retained_labels" => reduction.retained_labels,
            "floating_labels" => reduction.floating_labels,
            "reference_label" => reduction.reference_label,
        ),
        "reduction_method" => reduction.reduction_method,
        "reduced_maxwell_matrix_fF" => reduction.reduced_maxwell_matrix_fF,
        "mapped_branches_fF" => Dict(String(name) => value for (name, value) in pairs(reduction.mapped_branches_fF)),
        "readout_reduced_diagonal_fF" => reduction.readout_reduced_diagonal_fF,
        "extracted_C0r_fF" => reduction.extracted_C0r_fF,
        "readout_diagonal_instantiated" => reduction.readout_diagonal_instantiated,
        "readout_diagonal_lowering" => reduction.readout_diagonal_lowering,
        "readout_self_capacitance_ownership" => reduction.readout_self_capacitance_ownership,
        "open_side_contract_status" => reduction.open_side_contract_status,
        "region_ownership" => reduction.region_ownership,
        "L_J_per_junction_nH" => qubit.L_J_per_junction_nH,
        "canonical_targets" => Dict(
            "target_contract_id" => contract_id,
            "target_contract_sha256" => contract_sha256,
            "qubit_transition_frequency" => Dict("value" => Float64(f01_target_hz), "unit" => "Hz"),
            "qubit_junction_inductance" => Dict("value" => expected_lj, "unit" => "nH_per_junction"),
        ),
        "physics_diagnostics" => Dict(String(name) => value for (name, value) in pairs(physics)),
    )
end

end
