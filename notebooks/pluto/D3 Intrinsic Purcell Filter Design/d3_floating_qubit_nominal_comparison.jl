# This module owns the private full-Maxwell floating-qubit input reduction and
# the persisted-output contract for the D3 nominal loading comparison. It does
# not run HB, alter optimizer state, choose thresholds, or promote Layout Specs.

module D3FloatingQubitNominalComparison

using Dates
using LinearAlgebra
using SHA
using SuperconductingCircuitsCore

const JSON3 = SuperconductingCircuitsCore.JSON3

export COMPARISON_OUTPUT_FILES, load_floating_qubit_nominal_input,
    floating_qubit_coupling_off_frequency_hz, floating_qubit_physics_diagnostics,
    floating_qubit_reduction_evidence, write_comparison_outputs

const D3_FLOATING_QUBIT_SCHEMA = "d3-floating-qubit-maxwell.v1"
const D3_READOUT_CAPACITANCE_OWNERSHIP = "distributed_resonator_owns_self_capacitance"
const PLANCK_CONSTANT_J_S = 6.62607015e-34
const ELEMENTARY_CHARGE_C = 1.602176634e-19
const FLUX_QUANTUM_WB = 2.067833848e-15

const COMPARISON_OUTPUT_FILES = Set([
    "status.json",
    "comparison_manifest.json",
    "model_inputs.csv",
    "model_inputs.json",
    "metric_comparison.csv",
    "metric_comparison.json",
    "s21_traces.csv",
    "extraction_details.json",
])

file_sha256(path) = open(path, "r") do io
    bytes2hex(SHA.sha256(io))
end

function json_ready(value)
    isnothing(value) && return nothing
    value isa AbstractDict && return Dict(String(key) => json_ready(item) for (key, item) in pairs(value))
    value isa NamedTuple && return Dict(String(key) => json_ready(getproperty(value, key)) for key in propertynames(value))
    value isa AbstractVector && return [json_ready(item) for item in value]
    value isa Tuple && return [json_ready(item) for item in value]
    value isa Complex && return Dict("real" => Float64(real(value)), "imag" => Float64(imag(value)))
    value isa Symbol && return String(value)
    value isa AbstractFloat && !isfinite(value) && error("Refusing to persist non-finite comparison evidence.")
    value isa DateTime && return string(value)
    return value
end

function write_json(path, value)
    open(path, "w") do io
        JSON3.write(io, json_ready(value))
        write(io, '\n')
    end
    return path
end

function csv_cell(value)
    isnothing(value) && return ""
    text = string(value)
    return occursin(r"[\",\n\r]", text) ? "\"$(replace(text, '"' => "\"\""))\"" : text
end

function write_table_csv(path, columns, rows)
    open(path, "w") do io
        println(io, join(columns, ','))
        for row in rows
            println(io, join((csv_cell(get(row, column, nothing)) for column in columns), ','))
        end
    end
    return path
end

function _required_nonempty_label(value, context)
    label = strip(String(value))
    isempty(label) && error("$(context) must be a nonempty conductor label.")
    return label
end

function _reduce_floating_coupler_pads(payload)
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
    payload["readout_self_capacitance_ownership"] == D3_READOUT_CAPACITANCE_OWNERSHIP || error(
        "Readout self-capacitance must be owned by the existing distributed resonator.",
    )

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
    )
    all(value -> isfinite(value) && value > 0, values(mapped)) || error(
        "Kron-reduced physical branch capacitances must all be finite and positive.",
    )
    return mapped, (
        ordered_labels = labels,
        retained_labels = retained,
        floating_labels = floating,
        reference_label = reference,
        reduced_maxwell_matrix_fF = [collect(row) for row in eachrow(reduced_fF)],
        mapped_branches_fF = mapped,
        readout_reduced_diagonal_fF = reduced_fF[3, 3],
        readout_diagonal_instantiated = false,
        readout_diagonal_lowering = "provenance_only_not_lowered",
        readout_self_capacitance_ownership = D3_READOUT_CAPACITANCE_OWNERSHIP,
        reduction_method = "schur_complement_linear_solve_q_f_equals_zero",
    )
end

"""Read and reduce one private full-Maxwell input without retaining its values in source."""
function load_floating_qubit_nominal_input(path, constructor)
    input_path = abspath(String(path))
    isfile(input_path) || error("Floating-qubit nominal input does not exist: $(input_path)")
    payload = JSON3.read(read(input_path, String), Dict{String,Any})
    required_keys = Set([
        "schema_version",
        "model_id",
        "capacitance_source_id",
        "capacitance_unit",
        "conductor_labels",
        "maxwell_capacitance_matrix_fF",
        "role_mapping",
        "readout_self_capacitance_ownership",
        "L_J_per_junction_nH",
    ])
    Set(keys(payload)) == required_keys || error(
        "Floating-qubit nominal JSON keys must exactly match the v1 full-Maxwell contract.",
    )
    payload["schema_version"] == D3_FLOATING_QUBIT_SCHEMA || error(
        "Floating-qubit nominal schema_version must be $(D3_FLOATING_QUBIT_SCHEMA).",
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
        "schema_version" => D3_FLOATING_QUBIT_SCHEMA,
        "model_id" => qubit.model_id,
        "capacitance_source_id" => qubit.capacitance_source_id,
        "topology_id" => "d3-floating-qubit-kron-reduced-five-branch-two-parallel-lj-v1",
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
        "readout_diagonal_instantiated" => reduction.readout_diagonal_instantiated,
        "readout_diagonal_lowering" => reduction.readout_diagonal_lowering,
        "readout_self_capacitance_ownership" => reduction.readout_self_capacitance_ownership,
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

"""Persist the exact two tables plus fresh common-grid S21 evidence."""
function write_comparison_outputs(
    output_directory;
    manifest,
    model_rows,
    metric_rows,
    frequencies_hz,
    reference_s21,
    no_qubit_s21,
    with_qubit_s21,
    extraction_details,
)
    directory = abspath(String(output_directory))
    ispath(directory) && error("Refusing to overwrite comparison output: $(directory)")
    frequencies = Float64.(collect(frequencies_hz))
    reference = ComplexF64.(collect(reference_s21))
    baseline = ComplexF64.(collect(no_qubit_s21))
    variant = ComplexF64.(collect(with_qubit_s21))
    length(frequencies) == length(reference) == length(baseline) == length(variant) || error(
        "Comparison traces must share one identical frequency grid.",
    )
    !isempty(frequencies) || error("Comparison trace grid must not be empty.")
    all(isfinite, frequencies) && all(isfinite, real.(reference)) && all(isfinite, imag.(reference)) &&
        all(isfinite, real.(baseline)) && all(isfinite, imag.(baseline)) &&
        all(isfinite, real.(variant)) && all(isfinite, imag.(variant)) || error(
            "Comparison traces must contain only finite values.",
        )

    mkpath(directory)
    paths = Dict(name => joinpath(directory, name) for name in COMPARISON_OUTPUT_FILES)
    started_at = now(UTC)
    write_json(paths["status.json"], Dict(
        "analysis_kind" => "nominal_floating_qubit_loading_comparison",
        "state" => "running",
        "started_at_utc" => started_at,
        "completed_at_utc" => nothing,
        "human_acceptance_claim" => nothing,
    ))
    try
        write_json(paths["comparison_manifest.json"], manifest)
        write_json(paths["model_inputs.json"], Dict("rows" => model_rows))
        write_table_csv(
            paths["model_inputs.csv"],
            ["id", "no_qubit", "with_qubit", "unit", "meaning", "source"],
            model_rows,
        )
        write_json(paths["metric_comparison.json"], Dict("rows" => metric_rows))
        write_table_csv(
            paths["metric_comparison.csv"],
            ["id", "no_qubit", "with_qubit", "signed_delta", "unit", "quantity_scope", "extraction"],
            metric_rows,
        )
        open(paths["s21_traces.csv"], "w") do io
            println(io, "frequency_hz,empty_feedline_s21_real,empty_feedline_s21_imag,empty_feedline_s21_abs,no_qubit_s21_real,no_qubit_s21_imag,no_qubit_s21_abs,no_qubit_normalized_s21_real,no_qubit_normalized_s21_imag,no_qubit_normalized_s21_abs,with_qubit_s21_real,with_qubit_s21_imag,with_qubit_s21_abs,with_qubit_normalized_s21_real,with_qubit_normalized_s21_imag,with_qubit_normalized_s21_abs")
            for index in eachindex(frequencies)
                r = reference[index]
                a = baseline[index]
                b = variant[index]
                an = a / r
                bn = b / r
                println(io, join((frequencies[index], real(r), imag(r), abs(r), real(a), imag(a), abs(a), real(an), imag(an), abs(an), real(b), imag(b), abs(b), real(bn), imag(bn), abs(bn)), ','))
            end
        end
        write_json(paths["extraction_details.json"], extraction_details)
        write_json(paths["status.json"], Dict(
            "analysis_kind" => "nominal_floating_qubit_loading_comparison",
            "state" => "completed",
            "started_at_utc" => started_at,
            "completed_at_utc" => now(UTC),
            "human_acceptance_claim" => nothing,
        ))
        Set(readdir(directory)) == COMPARISON_OUTPUT_FILES || error("Comparison output file set changed during execution.")
        return directory
    catch exception
        write_json(paths["status.json"], Dict(
            "analysis_kind" => "nominal_floating_qubit_loading_comparison",
            "state" => "failed",
            "started_at_utc" => started_at,
            "completed_at_utc" => now(UTC),
            "error_type" => string(typeof(exception)),
            "reason" => sprint(showerror, exception),
            "human_acceptance_claim" => nothing,
        ))
        rethrow()
    end
end

end
