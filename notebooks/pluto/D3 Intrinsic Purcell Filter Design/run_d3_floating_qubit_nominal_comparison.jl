# This CLI freshly compares one frozen historical D3 Layout Specs input with
# and without a reduced linearized floating qubit. It writes comparison
# evidence only; it never calls the optimizer, changes its cost function, or
# claims Final Validation or Human acceptance.

import Pkg
Pkg.activate(joinpath(first(DEPOT_PATH), "environments", "v1.12"); io = devnull)

const WORKBENCH_ROOT = normpath(joinpath(@__DIR__, "..", "..", ".."))
const WORKSPACE_ROOT = dirname(WORKBENCH_ROOT)
const BRIDGE_PYTHON = joinpath(WORKBENCH_ROOT, ".venv", "bin", "python")
if !haskey(ENV, "JULIA_PYTHONCALL_EXE") && isfile(BRIDGE_PYTHON) && (uperm(BRIDGE_PYTHON) & 0o111 != 0)
    ENV["JULIA_PYTHONCALL_EXE"] = BRIDGE_PYTHON
end
!haskey(ENV, "JULIA_CONDAPKG_BACKEND") && (ENV["JULIA_CONDAPKG_BACKEND"] = "Null")

using LinearAlgebra
using SHA
using SuperconductingCircuitsAnalysisBridge
using SuperconductingCircuitsCore

const JSON3 = SuperconductingCircuitsCore.JSON3
include(joinpath(WORKBENCH_ROOT, "notebooks", "pluto", "includes", "hb_example_helpers.jl"))
const zero_mode_s = HBExampleHelpers.zero_mode_s
include(joinpath(@__DIR__, "d3_purcell_common.jl"))
include(joinpath(@__DIR__, "d3_coupled_evaluator.jl"))
include(joinpath(@__DIR__, "d3_nominal_validation.jl"))
include(joinpath(@__DIR__, "d3_floating_qubit_nominal_comparison.jl"))
using .D3NominalValidation
using .D3FloatingQubitNominalComparison

raw_file_sha256(path) = open(path, "r") do io
    bytes2hex(SHA.sha256(io))
end

function listed_values(records)
    records isa AbstractVector || error("Historical comparison requires list-valued persisted settings.")
    values = Dict{Symbol,Any}()
    for record in records
        id = Symbol(record["id"])
        haskey(values, id) && error("Persisted settings contain duplicate id $(id).")
        values[id] = record["value"]
    end
    return values
end

function inventory_source_path(preflight, id)
    item = get(preflight.consumed_inventory, String(id), nothing)
    isnothing(item) && error("Persisted optimizer inventory is missing $(id).")
    declared = String(item["path"])
    path = isabspath(declared) ? normpath(declared) : normpath(joinpath(WORKSPACE_ROOT, declared))
    isfile(path) || error("Persisted $(id) source is missing: $(path)")
    raw_file_sha256(path) == item["sha256"] || error("Persisted $(id) source changed since the frozen Layout Specs run.")
    return path
end

function historical_design(preflight)
    preflight.is_current && error(
        "This comparison CLI currently accepts the frozen historical-exploration D3 run contract only; use the independent nominal workflow for current-schema promotion evidence.",
    )
    source = preflight.optimizer_contract["design_selection"]["source_row"]["value"]
    source_values = Dict{Symbol,Any}(Symbol(key) => value for (key, value) in pairs(source))
    source_values[:id] = Symbol(source["row_id"])
    seed = (; source_values...)
    candidate_by_id = Dict(String(item["id"]) => Float64(item["value"]) for item in preflight.candidate_records)
    candidate = NamedTuple{Tuple(Symbol.(VARIABLE_IDS))}(Tuple(candidate_by_id[id] for id in VARIABLE_IDS))
    return _candidate_design(seed, candidate)
end

function assigned_pair_modes(resonances, filter_anchor_hz; label, max_filter_anchor_distance_hz)
    frequencies = Float64[mode["fr_hz"] for mode in resonances]
    filter_index = argmin(abs.(frequencies .- filter_anchor_hz))
    filter_distance = abs(frequencies[filter_index] - filter_anchor_hz)
    filter_distance <= max_filter_anchor_distance_hz || error(
        "$(label) cannot assign a filter-like pole within the persisted anchor-distance gate.",
    )
    remaining = [index for index in eachindex(resonances) if index != filter_index]
    return (filter = resonances[filter_index], remaining = resonances[remaining], filter_anchor_distance_hz = filter_distance)
end

metric_row(id, no_qubit, with_qubit, unit, scope, extraction; delta = nothing) = Dict(
    "id" => id,
    "no_qubit" => no_qubit,
    "with_qubit" => with_qubit,
    "signed_delta" => isnothing(delta) && !isnothing(no_qubit) && !isnothing(with_qubit) ? with_qubit - no_qubit : delta,
    "unit" => unit,
    "quantity_scope" => scope,
    "extraction" => extraction,
)

model_row(id, no_qubit, with_qubit, unit, meaning, source) = Dict(
    "id" => id,
    "no_qubit" => no_qubit,
    "with_qubit" => with_qubit,
    "unit" => unit,
    "meaning" => meaning,
    "source" => source,
)

function main(arguments)
    length(arguments) == 3 || error(
        "Usage: julia --startup-file=no notebooks/pluto/D3\\ Intrinsic\\ Purcell\\ Filter\\ Design/run_d3_floating_qubit_nominal_comparison.jl <frozen_optimizer_run_directory> <private_floating_qubit_json> <new_output_directory>",
    )
    optimizer_run = abspath(arguments[1])
    qubit_input = load_floating_qubit_nominal_input(arguments[2], D3FloatingQubitNominal)
    output_directory = abspath(arguments[3])
    preflight = preflight_optimizer_run(optimizer_run)
    design = historical_design(preflight)
    contract = preflight.optimizer_contract
	 target_path = inventory_source_path(preflight, "target_contract")
	 target = JSON3.read(read(target_path, String), Dict{String,Any})
	 target_sha256 = raw_file_sha256(target_path)
	 f01_record = target["targets"]["qubit_transition_frequency"]
	 lj_record = target["targets"]["qubit_junction_inductance"]
	 f01_record["unit"] == "GHz" || error("Frozen qubit transition target must use GHz.")
	 lj_record["unit"] == "nH_per_junction" || error("Frozen qubit junction target must use nH_per_junction.")
	 Int(lj_record["parallel_junction_count"]) == 2 || error("Frozen D3 qubit target must declare two parallel junctions.")
	 f01_target_hz = Float64(f01_record["value"]) * 1e9
	 expected_lj_nH = Float64(lj_record["value"])

    q2d_path = inventory_source_path(preflight, "orpen_case_json")
    matching_cases = [case for case in load_orpen_cases(q2d_path) if String(case.id) == preflight.selection.case_id]
    length(matching_cases) == 1 || error("Frozen Layout Specs must resolve to exactly one persisted Q2D case.")
    selected_case = only(matching_cases)
    feedline = load_d3_feedline_rlgc(preflight.config_snapshot)

    evaluator_values = listed_values(contract["evaluator_settings"])
    get!(evaluator_values, :qubit_local_half_width_hz, 100e6)
    get!(evaluator_values, :max_qubit_anchor_distance_hz, 50e6)
    get!(evaluator_values, :min_g_extrapolation_r2, 0.9999)
    evaluator_settings = D3SlotEvaluationSettings(; evaluator_values...)
    hb_values = listed_values(contract["hb_settings"])
    hb_settings = D3HBSettings(
        Float64(hb_values[:section_length_um]) * D3_METERS_PER_UM,
        hb_values[:port_resistance_ohm],
        hb_values[:pump_frequency_hz],
        hb_values[:pump_current_a],
        hb_values[:n_pump_harmonics],
        hb_values[:n_modulation_harmonics],
        Dict{Symbol,Any}(
            :nbatches => hb_values[:nbatches],
            :iterations => hb_values[:iterations],
            :ftol => hb_values[:ftol],
        ),
    )
    require_feedline_port_match(feedline, hb_settings)
    slot_hz = Float64(design.slot_target_ghz) * D3_HZ_PER_GHZ
    isolated_qubit_hz = floating_qubit_coupling_off_frequency_hz(qubit_input.model)
    evaluator = D3SlotEvaluator(
        selected_case,
        design,
        feedline,
        hb_settings,
        evaluator_settings,
        qubit_input.model,
        qubit_input.input_sha256,
        isolated_qubit_hz;
		qubit_f01_target_hz = f01_target_hz,
		expected_L_J_per_junction_nH = expected_lj_nH,
		qubit_target_contract_id = target["target_id"],
		qubit_target_contract_sha256 = target_sha256,
        journal_path = nothing,
    )
    half_width_hz = evaluator_settings.pair_trace_half_width_hz
    start_hz = min(slot_hz, isolated_qubit_hz) - half_width_hz
    stop_hz = max(slot_hz, isolated_qubit_hz) + half_width_hz
    start_hz > 0 || error("Floating-qubit comparison scan start must remain positive.")
    frequencies_hz = frequency_range_with_step(start_hz, stop_hz, evaluator_settings.frequency_step_hz)
    grid_sha256 = _frequency_grid_sha256(frequencies_hz)
    reference_s21 = _reference_trace!(evaluator, frequencies_hz)

    baseline_plan = build_single_pair_feedline_plan(
        selected_case,
        design;
        capacitance_fF = design.filter_to_line_capacitance_fF,
        feedline_length_um = evaluator_settings.feedline_length_um,
        feedline = feedline,
        hb_settings = hb_settings,
    )
    variant_plan = build_single_pair_feedline_plan(
        selected_case,
        design;
        capacitance_fF = design.filter_to_line_capacitance_fF,
        feedline_length_um = evaluator_settings.feedline_length_um,
        feedline = feedline,
        hb_settings = hb_settings,
        floating_qubit_nominal = qubit_input.model,
    )
    baseline_hb = _run_candidate_hb(evaluator, baseline_plan, frequencies_hz, "no-qubit floating-load comparison")
    variant_hb = _run_candidate_hb(evaluator, variant_plan, frequencies_hz, "with-qubit floating-load comparison")
    baseline_normalized = _normalized_s21(frequencies_hz, baseline_hb.s21, reference_s21, evaluator_settings.min_reference_magnitude)
    variant_normalized = _normalized_s21(frequencies_hz, variant_hb.s21, reference_s21, evaluator_settings.min_reference_magnitude)

    filter_plan = build_maxwell_diagonal_pair_feedline_plan(
        selected_case,
        design;
        filter_capacitance_fF = design.filter_to_line_capacitance_fF,
        feedline_length_um = evaluator_settings.feedline_length_um,
        feedline = feedline,
        hb_settings = hb_settings,
    )
    filter_hb = _run_candidate_hb(evaluator, filter_plan, frequencies_hz, "fresh filter loaded-bare comparison anchor")
    filter_normalized = _normalized_s21(frequencies_hz, filter_hb.s21, reference_s21, evaluator_settings.min_reference_magnitude)
    filter_anchor = _fit_single_loaded_mode(
        frequencies_hz,
        filter_normalized,
        slot_hz,
        "fresh filter loaded-bare comparison anchor",
        evaluator_settings;
        require_slot_ownership = true,
    )

    baseline_fit = fit_vector_s21(
        frequencies_hz,
        baseline_normalized;
        n_resonators = 2,
        bg_poles = evaluator_settings.vector_bg_poles,
        min_q = evaluator_settings.vector_min_q,
        restrict_to_input_span = true,
    )
    variant_fit = fit_vector_s21(
        frequencies_hz,
        variant_normalized;
        n_resonators = 3,
        bg_poles = evaluator_settings.vector_bg_poles,
        min_q = evaluator_settings.vector_min_q,
        restrict_to_input_span = true,
    )
    baseline_modes = _require_vector_fit(baseline_fit, 2, "no-qubit paired feedline response", evaluator_settings)
    variant_modes = _require_vector_fit(variant_fit, 3, "with-qubit paired feedline response", evaluator_settings)
    baseline_assignment = assigned_pair_modes(
        baseline_modes,
        filter_anchor.frequency_hz;
        label = "No-qubit paired response",
        max_filter_anchor_distance_hz = evaluator_settings.max_filter_anchor_distance_hz,
    )
    variant_assignment = assigned_pair_modes(
        variant_modes,
        filter_anchor.frequency_hz;
        label = "With-qubit paired response",
        max_filter_anchor_distance_hz = evaluator_settings.max_filter_anchor_distance_hz,
    )
    baseline_readout = only(baseline_assignment.remaining)
    variant_remaining = variant_assignment.remaining
    readout_reference_hz = Float64(baseline_readout["fr_hz"])
    nearest_index = argmin(abs.(Float64[mode["fr_hz"] for mode in variant_remaining] .- readout_reference_hz))
    variant_readout_nearest = variant_remaining[nearest_index]
    variant_additional = variant_remaining[nearest_index == 1 ? 2 : 1]

    baseline_min_index = argmin(abs.(baseline_normalized))
    variant_min_index = argmin(abs.(variant_normalized))
    trace_difference = variant_normalized .- baseline_normalized
    metric_rows = [
        metric_row("filter_loaded_bare_reference_frequency_hz", filter_anchor.frequency_hz, filter_anchor.frequency_hz, "Hz", "loaded_bare_reference", "fresh Maxwell-diagonal filter-only vector fit"),
        metric_row("paired_filter_like_pole_frequency_hz", Float64(baseline_assignment.filter["fr_hz"]), Float64(variant_assignment.filter["fr_hz"]), "Hz", "paired_hybridized", "nearest pole to the fresh filter loaded-bare anchor"),
        metric_row("paired_filter_like_pole_bandwidth_hz", Float64(baseline_assignment.filter["bandwidth_hz"]), Float64(variant_assignment.filter["bandwidth_hz"]), "Hz", "paired_hybridized", "vector-fit pole bandwidth after filter-anchor assignment"),
        metric_row("paired_readout_response_nearest_pole_frequency_hz", readout_reference_hz, Float64(variant_readout_nearest["fr_hz"]), "Hz", "paired_hybridized_proximity_diagnostic", "with-qubit pole nearest to the no-qubit readout-associated paired pole; not a bare-mode ownership claim"),
        metric_row("paired_readout_response_nearest_pole_bandwidth_hz", Float64(baseline_readout["bandwidth_hz"]), Float64(variant_readout_nearest["bandwidth_hz"]), "Hz", "paired_hybridized_proximity_diagnostic", "bandwidth of the same proximity-selected paired pole; not a bare-mode ownership claim"),
        metric_row("paired_additional_qubit_hybrid_pole_frequency_hz", nothing, Float64(variant_additional["fr_hz"]), "Hz", "paired_hybridized", "third with-qubit vector-fit pole; no no-qubit counterpart", delta = nothing),
        metric_row("paired_additional_qubit_hybrid_pole_bandwidth_hz", nothing, Float64(variant_additional["bandwidth_hz"]), "Hz", "paired_hybridized", "third with-qubit vector-fit pole bandwidth; no no-qubit counterpart", delta = nothing),
        metric_row("normalized_feedline_s21_minimum_frequency_hz", frequencies_hz[baseline_min_index], frequencies_hz[variant_min_index], "Hz", "paired_feedline_response", "common-grid global minimum of normalized |S21|"),
        metric_row("normalized_feedline_s21_minimum_magnitude", abs(baseline_normalized[baseline_min_index]), abs(variant_normalized[variant_min_index]), "ratio", "paired_feedline_response", "common-grid global minimum of normalized |S21|"),
        metric_row("normalized_feedline_s21_rms_complex_change", 0.0, sqrt(sum(abs2, trace_difference) / length(trace_difference)), "ratio", "paired_feedline_response_difference", "RMS complex difference on the identical grid"),
        metric_row("normalized_feedline_s21_maximum_complex_change", 0.0, maximum(abs.(trace_difference)), "ratio", "paired_feedline_response_difference", "maximum pointwise complex difference on the identical grid"),
    ]

    qubit = qubit_input.model
    model_rows = [
        model_row("layout_specs_raw_sha256", preflight.layout_raw_sha256, preflight.layout_raw_sha256, "sha256", "same frozen Layout Specs bytes", "historical optimizer run"),
        model_row("config_snapshot_raw_sha256", preflight.config_snapshot_sha256, preflight.config_snapshot_sha256, "sha256", "same persisted feedline configuration", "historical optimizer run"),
        model_row("q2d_artifact_sha256", preflight.consumed_inventory["orpen_case_json"]["sha256"], preflight.consumed_inventory["orpen_case_json"]["sha256"], "sha256", "same Q2D matrix artifact", q2d_path),
        model_row("frequency_grid_sha256", grid_sha256, grid_sha256, "sha256", "same ordered Float64 frequency grid", "fresh comparison"),
        model_row("frequency_start_hz", first(frequencies_hz), first(frequencies_hz), "Hz", "common scan lower bound", "derived from slot and isolated qubit estimate"),
        model_row("frequency_stop_hz", last(frequencies_hz), last(frequencies_hz), "Hz", "common scan upper bound", "derived from slot and isolated qubit estimate"),
        model_row("frequency_step_hz", evaluator_settings.frequency_step_hz, evaluator_settings.frequency_step_hz, "Hz", "persisted solver frequency step", "historical condition manifest"),
        model_row("floating_qubit_model_id", nothing, qubit.model_id, "id", "reduced nominal model identity", qubit_input.input_path),
        model_row("C01", nothing, qubit.C01_fF, "fF", "qubit island 1 to ground", qubit.capacitance_source_id),
        model_row("C02", nothing, qubit.C02_fF, "fF", "qubit island 2 to ground", qubit.capacitance_source_id),
        model_row("C12", nothing, qubit.C12_fF, "fF", "mutual capacitance between qubit islands", qubit.capacitance_source_id),
        model_row("Cr1", nothing, qubit.Cr1_fF, "fF", "readout_open_tail to qubit island 1", qubit.capacitance_source_id),
        model_row("Cr2", nothing, qubit.Cr2_fF, "fF", "readout_open_tail to qubit island 2", qubit.capacitance_source_id),
        model_row("L_J_per_junction", nothing, qubit.L_J_per_junction_nH, "nH", "each of two identical parallel small-signal Josephson branches", qubit_input.input_path),
        model_row("isolated_reduced_qubit_frequency_estimate", nothing, isolated_qubit_hz, "Hz", "LC estimate used only to include the qubit feature in the common scan", "Kron-reduced five-branch model"),
        model_row("floating_coupler_pad_reduction", "not_applicable", qubit.electrostatic_reduction.reduction_method, "method", "exactly four disconnected Coupler pads eliminated with Q_f=0", qubit.capacitance_source_id),
        model_row("readout_reduced_diagonal_instantiated", "not_applicable", qubit.electrostatic_reduction.readout_diagonal_instantiated, "boolean", "false because the distributed resonator owns readout self-capacitance", qubit.capacitance_source_id),
    ]
    for item in preflight.candidate_records
        push!(model_rows, model_row(
            "layout_$(item["id"])",
            item["value"],
            item["value"],
            item["unit"],
            "identical frozen Layout Specs variable",
            "layout_specs.json",
        ))
    end
    for (id, unit) in [
        (:section_length_um, "um"),
        (:port_resistance_ohm, "ohm"),
        (:pump_frequency_hz, "Hz"),
        (:pump_current_a, "A"),
        (:n_pump_harmonics, "count"),
        (:n_modulation_harmonics, "count"),
        (:nbatches, "count"),
        (:iterations, "count"),
        (:ftol, "ratio"),
    ]
        push!(model_rows, model_row(
            "hb_$(id)",
            hb_values[id],
            hb_values[id],
            unit,
            "identical persisted HB solver setting",
            "historical condition manifest",
        ))
    end

    manifest = Dict(
        "schema_version" => "d3-floating-qubit-loading-comparison.v1",
        "analysis_kind" => "nominal_floating_qubit_loading_comparison",
        "evidence_role" => "historical_exploration_layout_input",
        "final_validation_claim" => false,
        "human_acceptance_claim" => nothing,
        "optimizer_or_cost_function_modified" => false,
        "source_optimizer" => Dict(
            "run_id" => preflight.source_run_id,
            "run_directory" => preflight.run_directory,
            "optimizer_schema_version" => preflight.schema_version,
            "optimizer_contract_sha256" => preflight.optimizer_contract_sha256,
            "layout_specs_raw_sha256" => preflight.layout_raw_sha256,
            "config_snapshot_raw_sha256" => preflight.config_snapshot_sha256,
            "candidate_id" => preflight.candidate_id,
            "candidate_sha256" => preflight.candidate_sha256,
        ),
        "floating_qubit_input" => Dict(
            "path" => qubit_input.input_path,
            "raw_sha256" => qubit_input.input_sha256,
            "model_id" => qubit.model_id,
            "capacitance_source_id" => qubit.capacitance_source_id,
            "reduction" => floating_qubit_reduction_evidence(
				qubit;
				f01_target_hz = f01_target_hz,
				expected_L_J_per_junction_nH = expected_lj_nH,
				target_contract_id = target["target_id"],
				target_contract_sha256 = target_sha256,
			),
        ),
        "common_execution" => Dict(
            "fresh_no_qubit_solve" => true,
            "fresh_with_qubit_solve" => true,
            "identical_layout_specs" => true,
            "identical_q2d_and_feedline" => true,
            "identical_frequency_grid" => true,
            "identical_solver_settings" => true,
            "frequency_grid_sha256" => grid_sha256,
            "frequency_point_count" => length(frequencies_hz),
            "readout_attachment_node" => "readout_open_tail",
            "parallel_josephson_branch_count" => 2,
        ),
        "current_source_hashes" => Dict(
            "common" => raw_file_sha256(joinpath(@__DIR__, "d3_purcell_common.jl")),
            "evaluator_helpers" => raw_file_sha256(joinpath(@__DIR__, "d3_coupled_evaluator.jl")),
            "comparison_contract" => raw_file_sha256(joinpath(@__DIR__, "d3_floating_qubit_nominal_comparison.jl")),
            "comparison_runner" => raw_file_sha256(@__FILE__),
        ),
    )
    extraction_details = Dict(
        "filter_loaded_bare_reference" => filter_anchor,
        "no_qubit_vector_fit" => baseline_fit,
        "with_qubit_vector_fit" => variant_fit,
        "mode_assignment" => Dict(
            "filter_anchor_hz" => filter_anchor.frequency_hz,
            "no_qubit_filter_anchor_distance_hz" => baseline_assignment.filter_anchor_distance_hz,
            "with_qubit_filter_anchor_distance_hz" => variant_assignment.filter_anchor_distance_hz,
            "readout_response_rule" => "nearest_with_qubit_remaining_pole_to_no_qubit_readout_associated_paired_pole",
            "readout_response_is_bare_mode_ownership_claim" => false,
        ),
    )
    result = write_comparison_outputs(
        output_directory;
        manifest = manifest,
        model_rows = model_rows,
        metric_rows = metric_rows,
        frequencies_hz = frequencies_hz,
        reference_s21 = reference_s21,
        no_qubit_s21 = baseline_hb.s21,
        with_qubit_s21 = variant_hb.s21,
        extraction_details = extraction_details,
    )
    println(result)
    return nothing
end

abspath(PROGRAM_FILE) == abspath(@__FILE__) && main(ARGS)
