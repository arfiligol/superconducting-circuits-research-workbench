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

const D3_FLOATING_QUBIT_SCHEMA = "d3-readout-open-side-maxwell.v2"
const D3_RETAINED_QUBIT_GAP_SWEEP_SCHEMA =
    "d3-retained-qubit-readout-maxwell-gap-sweep.v1"
const D3_NAMED_GROUND_QUBIT_GAP_SWEEP_SCHEMA =
    "d3-retained-qubit-readout-named-ground-gap-sweep.v2"
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

function _retained_matrix_from_branches(branches)
    matrix_fF = zeros(Float64, 3, 3)
    matrix_fF[1, 1] = branches.C01_fF + branches.C12_fF + branches.Cr1_fF
    matrix_fF[2, 2] = branches.C02_fF + branches.C12_fF + branches.Cr2_fF
    matrix_fF[3, 3] = branches.C0r_fF + branches.Cr1_fF + branches.Cr2_fF
    matrix_fF[1, 2] = matrix_fF[2, 1] = -branches.C12_fF
    matrix_fF[1, 3] = matrix_fF[3, 1] = -branches.Cr1_fF
    matrix_fF[2, 3] = matrix_fF[3, 2] = -branches.Cr2_fF
    return matrix_fF
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
    ]) || error("Floating-qubit role_mapping must contain exactly the open-side conductor roles.")
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
    schema == D3_FLOATING_QUBIT_SCHEMA || error(
        "D3 floating-qubit input requires the open-side Maxwell schema.",
    )
    ownership == D3_READOUT_CAPACITANCE_OWNERSHIP || error(
        "D3 open-side v2 must assign the reduced readout shunt to the localized interface.",
    )
    region_ownership = _validate_open_side_region_ownership(payload)

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
        C0r_fF = sum(reduced_fF[3, :]),
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
        readout_diagonal_instantiated = true,
        readout_diagonal_lowering = "C0r_equals_reduced_readout_row_sum",
        readout_self_capacitance_ownership = ownership,
        open_side_contract_status = "canonical_candidate",
        input_schema = schema,
        region_ownership = region_ownership,
        reduction_method = "schur_complement_linear_solve_q_f_equals_zero",
    )
end

function _named_ground_maxwell_mapping(matrix_rows, labels, roles)
    ordered_labels = [
        _required_nonempty_label(label, "conductor_labels") for label in labels
    ]
    length(ordered_labels) == 4 &&
        length(unique(ordered_labels)) == 4 || error(
        "Retained Q3D input must contain exactly four unique conductor labels.",
    )
    Set(keys(roles)) == Set([
        "reference_conductor", "qubit_island_1", "qubit_island_2",
        "readout_attachment",
    ]) || error("Retained Q3D role_mapping must contain exactly four conductor roles.")
    reference = _required_nonempty_label(
        roles["reference_conductor"], "reference_conductor",
    )
    retained_labels = [
        _required_nonempty_label(roles["qubit_island_1"], "qubit_island_1"),
        _required_nonempty_label(roles["qubit_island_2"], "qubit_island_2"),
        _required_nonempty_label(roles["readout_attachment"], "readout_attachment"),
    ]
    Set(vcat([reference], retained_labels)) == Set(ordered_labels) || error(
        "Retained Q3D roles must exhaust conductor_labels exactly.",
    )
    length(matrix_rows) == 4 && all(row -> length(row) == 4, matrix_rows) || error(
        "Retained Q3D Maxwell matrix must be 4-by-4.",
    )
    matrix_fF = reduce(
        vcat, (permutedims(Float64.(collect(row))) for row in matrix_rows),
    )
    all(isfinite, matrix_fF) || error(
        "Retained Q3D Maxwell matrix must contain only finite capacitances.",
    )
    isapprox(matrix_fF, transpose(matrix_fF); rtol = 1e-9, atol = 1e-9) || error(
        "Retained Q3D Maxwell matrix must be symmetric within 1e-9 fF.",
    )
    all(
        matrix_fF[row, column] <= 1e-9
        for row in axes(matrix_fF, 1), column in axes(matrix_fF, 2)
        if row != column
    ) || error("Retained Q3D Maxwell off-diagonal entries must be nonpositive.")
    minimum(eigvals(Symmetric(matrix_fF))) > 0 || error(
        "Retained Q3D Maxwell matrix must be passive positive definite.",
    )
    reference_index = only(findall(==(reference), ordered_labels))
    retained_indexes = [
        only(findall(==(label), ordered_labels)) for label in retained_labels
    ]
    retained_raw_fF = matrix_fF[retained_indexes, retained_indexes]
    outer_reference_residual_fF = vec(sum(matrix_fF; dims=2))[retained_indexes]
    mapped = (
        C01_fF = -matrix_fF[reference_index, retained_indexes[1]],
        C02_fF = -matrix_fF[reference_index, retained_indexes[2]],
        C12_fF = -retained_raw_fF[1, 2],
        Cr1_fF = -retained_raw_fF[1, 3],
        Cr2_fF = -retained_raw_fF[2, 3],
        C0r_fF = -matrix_fF[reference_index, retained_indexes[3]],
    )
    all(value -> isfinite(value) && value > 0, values(mapped)) || error(
        "Retained Q3D physical branch capacitances must be finite and positive.",
    )
    modeled_retained_fF =
        retained_raw_fF - Diagonal(outer_reference_residual_fF)
    reconstructed_fF = _retained_matrix_from_branches(mapped)
    isapprox(
        reconstructed_fF,
        modeled_retained_fF;
        rtol = 1e-12,
        atol = 1e-10,
    ) || error(
        "Named-GND Q3D branches must reconstruct the retained principal block " *
        "after excluding its signed outer-reference row sums.",
    )
    minimum(eigvals(Symmetric(modeled_retained_fF))) > 0 || error(
        "Named-GND modeled retained matrix must be passive positive definite.",
    )
    return mapped, modeled_retained_fF, retained_raw_fF,
        outer_reference_residual_fF, (
        ordered_labels = ordered_labels,
        retained_labels = retained_labels,
        reference_label = reference,
    )
end

function _validate_retained_region_ownership(payload)
    region = payload["region_ownership"]
    Set(keys(region)) == Set([
        "modeling_mode",
        "local_region_id",
        "readout_line_cut_plane_id",
        "distributed_readout_length_reference",
        "distributed_line_excludes_local_capacitance",
        "electric_energy_owner",
        "magnetic_model",
    ]) || error("Retained Q3D region_ownership fields are invalid.")
    region["modeling_mode"] == "electrostatic_local_interface_replacement" || error(
        "Retained Q3D input must replace one electrostatic local interface.",
    )
    _required_nonempty_label(region["local_region_id"], "local_region_id")
    _required_nonempty_label(
        region["readout_line_cut_plane_id"], "readout_line_cut_plane_id",
    )
    region["distributed_readout_length_reference"] ==
        "shorted_end_to_open_side_local_cut_plane" || error(
        "Distributed readout length must stop at the Q3D local cut plane.",
    )
    region["distributed_line_excludes_local_capacitance"] === true || error(
        "Distributed readout length must exclude the retained Q3D local capacitance.",
    )
    region["electric_energy_owner"] == "named_ground_pairwise_projection" || error(
        "Retained Q3D input must assign modeled electric energy to the named-GND projection.",
    )
    region["magnetic_model"] == "not_supplied_by_q3d_capacitance_input" || error(
        "Q3D capacitance input must not claim a magnetic model.",
    )
    return Dict{String,Any}(String(key) => value for (key, value) in region)
end

function _load_retained_gap_sweep(payload, constructor; gap_um)
    Set(keys(payload)) == Set([
        "schema_version",
        "model_id",
        "capacitance_source_id",
        "capacitance_unit",
        "gap_unit",
        "nominal_gap_um",
        "valid_gap_range_um",
        "conductor_labels",
        "role_mapping",
        "readout_self_capacitance_ownership",
        "model_projection",
        "region_ownership",
        "evaluation_policy",
        "source_artifact",
        "samples",
        "fit",
        "L_J_per_junction_nH",
    ]) || error("Retained Q3D gap-sweep JSON fields do not match its v2 contract.")
    payload["capacitance_unit"] == "fF" || error(
        "Retained Q3D capacitance unit must be fF.",
    )
    payload["gap_unit"] == "um" || error("Retained Q3D gap unit must be um.")
    payload["readout_self_capacitance_ownership"] ==
        "localized_open_side_interface_owns_named_ground_readout_shunt" || error(
        "Retained Q3D C0r must be the explicitly named GND-to-readout branch.",
    )
    payload["evaluation_policy"] ==
        "nominal_gap_uses_raw_q3d_sample__other_in_range_gaps_use_reciprocal_gap_fit" ||
        error("Retained Q3D gap evaluation policy is invalid.")
    region_ownership = _validate_retained_region_ownership(payload)
    projection = payload["model_projection"]
    Set(keys(projection)) == Set([
        "policy",
        "named_ground_conductor",
        "retained_matrix_rule",
        "outer_reference_residual_circuit_use",
        "outer_reference_residual_evidence_use",
    ]) || error("Retained Q3D model_projection fields are invalid.")
    projection["policy"] == "named_GND_pairwise_branches_only" &&
        projection["named_ground_conductor"] == "GND" &&
        projection["retained_matrix_rule"] ==
            "raw_retained_principal_block_minus_diagonal_of_signed_retained_full_matrix_row_sums" &&
        projection["outer_reference_residual_circuit_use"] == "excluded" &&
        projection["outer_reference_residual_evidence_use"] == "report_only" ||
        error("Retained Q3D named-GND projection policy is invalid.")
    source = payload["source_artifact"]
    Set(keys(source)) == Set(["kind", "filename", "sha256"]) || error(
        "Retained Q3D source_artifact fields are invalid.",
    )
    source["kind"] == "q3d_capacitance_matrix_gap_sweep_xlsx" || error(
        "Retained capacitance sweep source must be Q3D XLSX.",
    )
    _required_nonempty_label(source["filename"], "source_artifact.filename")
    occursin(r"^[0-9a-f]{64}$", String(source["sha256"])) || error(
        "Retained Q3D source artifact must carry a lowercase SHA-256.",
    )

    labels = collect(payload["conductor_labels"])
    roles = payload["role_mapping"]
    samples = payload["samples"]
    length(samples) >= 3 || error("Retained Q3D reciprocal-gap fit requires at least three samples.")
    sample_records = NamedTuple[]
    for sample in samples
        Set(keys(sample)) == Set([
            "gap_um",
            "maxwell_capacitance_matrix_fF",
            "physical_branches_fF",
            "outer_reference_residual_fF",
        ]) || error("Retained Q3D sample fields are invalid.")
        sample_gap = Float64(sample["gap_um"])
        isfinite(sample_gap) && sample_gap > 0 || error(
            "Retained Q3D sample gap must be finite and positive.",
        )
        mapped, retained_fF, raw_retained_fF, outer_residual_fF, partition =
            _named_ground_maxwell_mapping(
            sample["maxwell_capacitance_matrix_fF"], labels, roles,
        )
        branches = sample["physical_branches_fF"]
        Set(keys(branches)) == Set(String.(propertynames(mapped))) || error(
            "Retained Q3D sample physical branch fields are invalid.",
        )
        all(name -> isapprox(
            Float64(branches[String(name)]), getproperty(mapped, name);
            rtol = 1e-12, atol = 1e-10,
        ), propertynames(mapped)) || error(
            "Retained Q3D stored branch values disagree with the Maxwell matrix.",
        )
        stored_outer = sample["outer_reference_residual_fF"]
        Set(keys(stored_outer)) == Set([
            "Q1_L_fF",
            "Q1_R_fF",
            "Q1_read_fF",
        ]) || error("Retained Q3D outer-reference residual fields are invalid.")
        all(
            isapprox(
                Float64(stored_outer[name]),
                outer_residual_fF[index];
                rtol=1e-12,
                atol=1e-10,
            )
            for (index, name) in enumerate(
                ("Q1_L_fF", "Q1_R_fF", "Q1_read_fF"),
            )
        ) || error(
            "Retained Q3D outer-reference residual evidence disagrees with the raw matrix.",
        )
        push!(sample_records, (
            gap_um = sample_gap,
            mapped = mapped,
            retained_fF = retained_fF,
            raw_retained_fF = raw_retained_fF,
            outer_reference_residual_fF = outer_residual_fF,
            partition = partition,
        ))
    end
    sample_gaps = [sample.gap_um for sample in sample_records]
    length(unique(sample_gaps)) == length(sample_gaps) || error(
        "Retained Q3D sample gaps must be unique.",
    )
    issorted(sample_gaps) || error("Retained Q3D samples must be sorted by gap.")
    declared_range = Float64.(collect(payload["valid_gap_range_um"]))
    length(declared_range) == 2 &&
        declared_range == [first(sample_gaps), last(sample_gaps)] || error(
        "Retained Q3D valid gap range must equal the sample bounds.",
    )
    nominal_gap = Float64(payload["nominal_gap_um"])
    count(==(nominal_gap), sample_gaps) == 1 || error(
        "Retained Q3D nominal gap must identify exactly one raw sample.",
    )
    selected_gap = gap_um === nothing ? nominal_gap : Float64(gap_um)
    isfinite(selected_gap) &&
        declared_range[1] <= selected_gap <= declared_range[2] || error(
        "Requested Q3D gap must lie inside the declared fit range.",
    )

    fit = payload["fit"]
    Set(keys(fit)) == Set([
        "model", "basis", "least_squares_rank", "design_matrix_condition_number",
        "branch_fits", "validation",
    ]) || error("Retained Q3D reciprocal-gap fit fields are invalid.")
    fit["model"] == "a_plus_b_over_h_plus_c_over_h_squared" || error(
        "Retained Q3D fit must use a+b/h+c/h^2.",
    )
    collect(fit["basis"]) == ["1", "1/h_um", "1/h_um^2"] || error(
        "Retained Q3D fit basis is invalid.",
    )
    Int(fit["least_squares_rank"]) == 3 || error(
        "Retained Q3D fit must have rank three.",
    )
    condition_number = Float64(fit["design_matrix_condition_number"])
    isfinite(condition_number) && condition_number > 0 || error(
        "Retained Q3D fit condition number must be finite and positive.",
    )
    branch_fits = fit["branch_fits"]
    Set(keys(branch_fits)) == Set(String.(propertynames(first(sample_records).mapped))) ||
        error("Retained Q3D fit must contain exactly the six physical branches.")
    design_matrix = hcat(
        ones(Float64, length(sample_gaps)),
        1.0 ./ sample_gaps,
        1.0 ./ sample_gaps .^ 2,
    )
    rank(design_matrix) == 3 || error(
        "Retained Q3D reciprocal-gap sample basis must have rank three.",
    )
    coefficients = Dict{Symbol,Vector{Float64}}()
    for branch_name in propertynames(first(sample_records).mapped)
        branch_fit = branch_fits[String(branch_name)]
        Set(keys(branch_fit)) == Set([
            "coefficients_fF", "rms_residual_fF", "max_abs_residual_fF",
            "max_abs_relative_residual",
            "max_abs_leave_one_out_relative_residual",
        ]) || error("Retained Q3D branch-fit fields are invalid.")
        branch_coefficients = Float64.(collect(branch_fit["coefficients_fF"]))
        length(branch_coefficients) == 3 && all(isfinite, branch_coefficients) || error(
            "Retained Q3D branch fit must contain three finite coefficients.",
        )
        predicted = [
            branch_coefficients[1] + branch_coefficients[2] / sample.gap_um +
                branch_coefficients[3] / sample.gap_um^2
            for sample in sample_records
        ]
        actual = [getproperty(sample.mapped, branch_name) for sample in sample_records]
        recomputed_coefficients = design_matrix \ actual
        isapprox(
            branch_coefficients, recomputed_coefficients; rtol = 1e-10, atol = 1e-10,
        ) || error(
            "Retained Q3D serialized coefficients disagree with an independent least-squares solve.",
        )
        residual = predicted .- actual
        rms = sqrt(sum(abs2, residual) / length(residual))
        max_abs = maximum(abs, residual)
        max_abs_relative = maximum(abs.(residual) ./ actual)
        leave_one_out_relative = Float64[]
        for omitted_index in eachindex(sample_records)
            retained_indices = [
                index for index in eachindex(sample_records) if index != omitted_index
            ]
            leave_one_out_coefficients =
                design_matrix[retained_indices, :] \ actual[retained_indices]
            prediction = dot(
                design_matrix[omitted_index, :],
                leave_one_out_coefficients,
            )
            push!(
                leave_one_out_relative,
                abs(prediction - actual[omitted_index]) / actual[omitted_index],
            )
        end
        max_abs_leave_one_out_relative = maximum(leave_one_out_relative)
        isapprox(rms, Float64(branch_fit["rms_residual_fF"]); rtol = 1e-10, atol = 1e-12) &&
            isapprox(max_abs, Float64(branch_fit["max_abs_residual_fF"]);
                rtol = 1e-10, atol = 1e-12) &&
            isapprox(
                max_abs_relative,
                Float64(branch_fit["max_abs_relative_residual"]);
                rtol = 1e-10,
                atol = 1e-14,
            ) &&
            isapprox(
                max_abs_leave_one_out_relative,
                Float64(branch_fit["max_abs_leave_one_out_relative_residual"]);
                rtol = 1e-10,
                atol = 1e-14,
            ) || error(
            "Retained Q3D branch-fit residual evidence is inconsistent.",
        )
        coefficients[branch_name] = branch_coefficients
    end
    validation = fit["validation"]
    Set(keys(validation)) == Set([
        "gap_grid_start_um", "gap_grid_stop_um", "gap_grid_step_um",
        "gap_grid_count", "all_branches_positive",
        "all_retained_matrices_positive_definite", "minimum_branch_fF",
        "minimum_retained_eigenvalue_fF",
    ]) || error("Retained Q3D fit-validation fields are invalid.")
    validation["all_branches_positive"] === true &&
        validation["all_retained_matrices_positive_definite"] === true || error(
        "Retained Q3D fit-validation positivity gates must pass.",
    )
    validation_start = Float64(validation["gap_grid_start_um"])
    validation_stop = Float64(validation["gap_grid_stop_um"])
    validation_step = Float64(validation["gap_grid_step_um"])
    validation_count = Int(validation["gap_grid_count"])
    validation_start == declared_range[1] &&
        validation_stop == declared_range[2] &&
        validation_step == 0.1 &&
        validation_count == 51 || error(
        "Retained Q3D fit validation must cover the declared range at 0.1 um.",
    )
    validation_gaps = collect(range(
        validation_start,
        validation_stop;
        length = validation_count,
    ))
    minimum_branch_fF = Inf
    minimum_retained_eigenvalue_fF = Inf
    branch_names = propertynames(first(sample_records).mapped)
    for validation_gap in validation_gaps
        branches = NamedTuple{Tuple(branch_names)}(Tuple(
            coefficients[name][1] + coefficients[name][2] / validation_gap +
                coefficients[name][3] / validation_gap^2
            for name in branch_names
        ))
        minimum_branch_fF = min(minimum_branch_fF, minimum(values(branches)))
        validation_matrix = _retained_matrix_from_branches(branches)
        minimum_retained_eigenvalue_fF = min(
            minimum_retained_eigenvalue_fF,
            minimum(eigvals(Symmetric(validation_matrix))),
        )
    end
    minimum_branch_fF > 0 && minimum_retained_eigenvalue_fF > 0 || error(
        "Retained Q3D fit violates positivity on the 0.1 um validation grid.",
    )
    isapprox(
        minimum_branch_fF,
        Float64(validation["minimum_branch_fF"]);
        rtol = 1e-10,
        atol = 1e-12,
    ) && isapprox(
        minimum_retained_eigenvalue_fF,
        Float64(validation["minimum_retained_eigenvalue_fF"]);
        rtol = 1e-10,
        atol = 1e-12,
    ) || error("Retained Q3D fit-validation minima are inconsistent.")

    nominal_raw = selected_gap == nominal_gap
    selected = if nominal_raw
        only(filter(sample -> sample.gap_um == nominal_gap, sample_records)).mapped
    else
        NamedTuple{Tuple(propertynames(first(sample_records).mapped))}(Tuple(
            coefficients[name][1] + coefficients[name][2] / selected_gap +
                coefficients[name][3] / selected_gap^2
            for name in propertynames(first(sample_records).mapped)
        ))
    end
    all(value -> isfinite(value) && value > 0, values(selected)) || error(
        "Evaluated retained Q3D branch capacitances must be finite and positive.",
    )
    retained_fF = _retained_matrix_from_branches(selected)
    minimum(eigvals(Symmetric(retained_fF))) > 0 || error(
        "Evaluated retained Q3D Maxwell block must be passive positive definite.",
    )
    partition = first(sample_records).partition
    reduction = (
        ordered_labels = partition.ordered_labels,
        retained_labels = partition.retained_labels,
        floating_labels = String[],
        reference_label = partition.reference_label,
        reduced_maxwell_matrix_fF = [collect(row) for row in eachrow(retained_fF)],
        mapped_branches_fF = selected,
        readout_reduced_diagonal_fF = retained_fF[3, 3],
        extracted_C0r_fF = selected.C0r_fF,
        readout_diagonal_instantiated = true,
        readout_diagonal_lowering =
            "C0r_equals_negative_named_GND_readout_off_diagonal",
        readout_self_capacitance_ownership =
            String(payload["readout_self_capacitance_ownership"]),
        open_side_contract_status = "accepted_named_ground_gap_sweep_v2",
        input_schema = D3_NAMED_GROUND_QUBIT_GAP_SWEEP_SCHEMA,
        region_ownership = region_ownership,
        reduction_method =
            "named_GND_pairwise_projection_outer_reference_residual_excluded",
        model_projection = Dict{String,Any}(
            String(key) => value for (key, value) in projection
        ),
        outer_reference_residual_samples_fF = [
            Dict(
                "gap_um" => sample.gap_um,
                "Q1_L_fF" => sample.outer_reference_residual_fF[1],
                "Q1_R_fF" => sample.outer_reference_residual_fF[2],
                "Q1_read_fF" => sample.outer_reference_residual_fF[3],
            )
            for sample in sample_records
        ],
        selected_outer_reference_residual_fF = nominal_raw ?
            only(
                filter(sample -> sample.gap_um == nominal_gap, sample_records),
            ).outer_reference_residual_fF : nothing,
        evaluation_gap_um = selected_gap,
        evaluation_source = nominal_raw ?
            "raw_q3d_nominal_sample" : "reciprocal_gap_formula_fit",
        valid_gap_range_um = declared_range,
        source_artifact = Dict{String,Any}(
            String(key) => value for (key, value) in source
        ),
        fit = Dict{String,Any}(String(key) => value for (key, value) in fit),
        fit_sha256 = bytes2hex(SHA.sha256(codeunits(JSON3.write(fit)))),
    )
    model = constructor(
        model_id = payload["model_id"],
        capacitance_source_id = payload["capacitance_source_id"],
        C01_fF = selected.C01_fF,
        C02_fF = selected.C02_fF,
        C12_fF = selected.C12_fF,
        Cr1_fF = selected.Cr1_fF,
        Cr2_fF = selected.Cr2_fF,
        C0r_fF = selected.C0r_fF,
        L_J_per_junction_nH = payload["L_J_per_junction_nH"],
        electrostatic_reduction = reduction,
    )
    return model
end

"""Read and reduce one private full-Maxwell input without retaining its values in source."""
function load_floating_qubit_nominal_input(
    path,
    constructor;
    require_open_side_contract = false,
    gap_um = nothing,
)
    input_path = abspath(String(path))
    isfile(input_path) || error("Floating-qubit nominal input does not exist: $(input_path)")
    payload = JSON3.read(read(input_path, String), Dict{String,Any})
    schema = String(payload["schema_version"])
    if schema == D3_NAMED_GROUND_QUBIT_GAP_SWEEP_SCHEMA
        model = _load_retained_gap_sweep(payload, constructor; gap_um=gap_um)
        return (
            model=model,
            input_path=input_path,
            input_sha256=file_sha256(input_path),
        )
    end
    if schema == D3_RETAINED_QUBIT_GAP_SWEEP_SCHEMA
        error(
            "named_GND_projection_required: the direct-retained row-sum " *
            "lowering includes outer-reference residuals and is not eligible " *
            "for the current D3 Same-Die target.",
        )
    end
    gap_um === nothing || error(
        "Explicit gap evaluation requires $(D3_NAMED_GROUND_QUBIT_GAP_SWEEP_SCHEMA).",
    )
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
    schema == D3_FLOATING_QUBIT_SCHEMA || error(
        "Floating-qubit schema is not supported.",
    )
    required_keys = Set(vcat(common_keys, ["region_ownership"]))
    Set(keys(payload)) == required_keys || error(
        "Floating-qubit nominal JSON keys must exactly match its declared Maxwell contract.",
    )
    require_open_side_contract isa Bool || error(
        "require_open_side_contract must be Boolean.",
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
    evidence = Dict(
        "schema_version" => reduction.input_schema,
        "model_id" => qubit.model_id,
        "capacitance_source_id" => qubit.capacitance_source_id,
        "topology_id" => reduction.input_schema == D3_NAMED_GROUND_QUBIT_GAP_SWEEP_SCHEMA ?
            "d3-opposite-face-qubit-named-ground-six-branch-two-parallel-lj-v2" :
            "d3-open-side-local-maxwell-kron-reduced-six-branch-two-parallel-lj-v2",
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
    if reduction.input_schema == D3_NAMED_GROUND_QUBIT_GAP_SWEEP_SCHEMA
        evidence["gap_evaluation"] = Dict(
            "gap_um" => reduction.evaluation_gap_um,
            "evaluation_source" => reduction.evaluation_source,
            "valid_gap_range_um" => reduction.valid_gap_range_um,
            "source_artifact" => reduction.source_artifact,
            "fit_model" => reduction.fit["model"],
            "fit_sha256" => reduction.fit_sha256,
            "outer_reference_residual_circuit_use" => "excluded",
            "outer_reference_residual_evidence_use" => "report_only",
            "outer_reference_residual_samples_fF" =>
                reduction.outer_reference_residual_samples_fF,
            "selected_outer_reference_residual_fF" =>
                reduction.selected_outer_reference_residual_fF,
        )
    end
    return evidence
end

end
