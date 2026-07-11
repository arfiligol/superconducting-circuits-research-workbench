# This module owns the input and persisted-output contract for the D3 nominal
# floating-qubit loading comparison. It does not run HB, alter optimizer state,
# choose acceptance thresholds, or promote historical Layout Specs.

module D3FloatingQubitNominalComparison

using Dates
using SHA
using SuperconductingCircuitsCore

const JSON3 = SuperconductingCircuitsCore.JSON3

export COMPARISON_OUTPUT_FILES, load_floating_qubit_nominal_input,
    floating_qubit_coupling_off_frequency_hz, write_comparison_outputs

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

"""Read one private reduced-model JSON without retaining private values in source."""
function load_floating_qubit_nominal_input(path, constructor)
    input_path = abspath(String(path))
    isfile(input_path) || error("Floating-qubit nominal input does not exist: $(input_path)")
    payload = JSON3.read(read(input_path, String), Dict{String,Any})
    required_keys = Set([
        "schema_version",
        "model_id",
        "capacitance_source_id",
        "C01_fF",
        "C02_fF",
        "C12_fF",
        "Cr1_fF",
        "Cr2_fF",
        "L_J_per_junction_nH",
    ])
    Set(keys(payload)) == required_keys || error(
        "Floating-qubit nominal JSON keys must exactly match the v1 reduced-model contract.",
    )
    payload["schema_version"] == "d3-floating-qubit-nominal.v1" || error(
        "Floating-qubit nominal schema_version must be d3-floating-qubit-nominal.v1.",
    )
    model = constructor(
        model_id = payload["model_id"],
        capacitance_source_id = payload["capacitance_source_id"],
        C01_fF = payload["C01_fF"],
        C02_fF = payload["C02_fF"],
        C12_fF = payload["C12_fF"],
        Cr1_fF = payload["Cr1_fF"],
        Cr2_fF = payload["Cr2_fF"],
        L_J_per_junction_nH = payload["L_J_per_junction_nH"],
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
