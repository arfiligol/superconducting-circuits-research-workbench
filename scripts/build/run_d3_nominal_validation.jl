# This CLI independently reproduces one persisted D3 optimizer candidate in a
# fresh Julia process and a fresh physical evaluator. It accepts only an
# immutable optimizer run directory, evaluates its layout_specs.json candidate
# exactly once with trace capture, and writes the exact-six nominal-validation
# artifact contract. It does not implement tolerance sweeps or Human approval.

import Pkg
Pkg.activate(joinpath(first(DEPOT_PATH), "environments", "v1.12"); io = devnull)

const WORKBENCH_ROOT = normpath(joinpath(@__DIR__, "..", ".."))
const WORKSPACE_ROOT = dirname(WORKBENCH_ROOT)
const D3_NOTEBOOK_ROOT = joinpath(WORKBENCH_ROOT, "notebooks", "pluto", "D3 Intrinsic Purcell Filter Design")
const BRIDGE_PYTHON = joinpath(WORKBENCH_ROOT, ".venv", "bin", "python")
if !haskey(ENV, "JULIA_PYTHONCALL_EXE") && isfile(BRIDGE_PYTHON) && (uperm(BRIDGE_PYTHON) & 0o111 != 0)
    ENV["JULIA_PYTHONCALL_EXE"] = BRIDGE_PYTHON
end
!haskey(ENV, "JULIA_CONDAPKG_BACKEND") && (ENV["JULIA_CONDAPKG_BACKEND"] = "Null")

using LinearAlgebra
using SuperconductingCircuitsAnalysisBridge
using SuperconductingCircuitsCore

const JSON3 = SuperconductingCircuitsCore.JSON3
include(joinpath(WORKBENCH_ROOT, "notebooks", "pluto", "includes", "hb_example_helpers.jl"))
const zero_mode_s = HBExampleHelpers.zero_mode_s
include(joinpath(D3_NOTEBOOK_ROOT, "d3_purcell_common.jl"))
include(joinpath(D3_NOTEBOOK_ROOT, "d3_floating_qubit_nominal_comparison.jl"))
using .D3FloatingQubitNominalComparison
include(joinpath(D3_NOTEBOOK_ROOT, "d3_coupled_evaluator.jl"))
include(joinpath(D3_NOTEBOOK_ROOT, "d3_nominal_validation.jl"))
using .D3NominalValidation

function workspace_path(relative_path)
    path = String(relative_path)
    isabspath(path) && error("D3 config paths must be workspace-relative: $(path)")
    components = splitpath(path)
    any(==(".."), components) && error("D3 config paths must not contain '..': $(path)")
    resolved = normpath(joinpath(WORKSPACE_ROOT, components...))
    workspace_relative(resolved, WORKSPACE_ROOT)
    return resolved
end

function physical_evaluator_factory(preflight, config, conditions)
    seed_path = workspace_path(joinpath(String(config["design_csv_workspace_root"]), String(config["design_csv_filename"])))
    designs = read_design_csv(seed_path; case_id = preflight.selection.case_id)
    matching_designs = [
        row for row in designs
        if String(row.id) == preflight.selection.source_row_id &&
            String(row.target_set_id) == preflight.selection.target_set_id &&
            row.slot_target_ghz == preflight.selection.slot_target_ghz
    ]
    length(matching_designs) == 1 || error("Persisted optimizer selection must resolve to exactly one current seed row.")
    seed_design = only(matching_designs)
    case_path = workspace_path(config["orpen_case_json_workspace_path"])
    matching_cases = [case for case in load_orpen_cases(case_path) if String(case.id) == preflight.selection.case_id]
    length(matching_cases) == 1 || error("Persisted optimizer selection must resolve to exactly one current Q2D case.")
    selected_case = only(matching_cases)
    feedline = load_d3_feedline_rlgc(config)
    qubit_input = load_floating_qubit_nominal_input(
        workspace_path(config["floating_qubit_nominal_workspace_path"]),
        D3FloatingQubitNominal,
    )
    target_path = workspace_path(config["target_contract"]["workspace_relative_path"])
    target = JSON3.read(read(target_path, String), Dict{String,Any})
    target_sha256 = file_sha256(target_path)
    target_sha256 == config["target_contract"]["expected_sha256"] || error("Current canonical target bytes disagree with the optimizer snapshot.")
    f01_record = target["targets"]["qubit_transition_frequency"]
    lj_record = target["targets"]["qubit_junction_inductance"]
    f01_record["unit"] == "GHz" || error("Canonical qubit transition target must use GHz.")
    lj_record["unit"] == "nH_per_junction" || error("Canonical qubit junction target must use nH_per_junction.")
    Int(lj_record["parallel_junction_count"]) == 2 || error("Canonical D3 qubit target must declare two parallel junctions.")
    f01_target_hz = Float64(f01_record["value"]) * 1e9
    expected_lj_nH = Float64(lj_record["value"])

    evaluator_kwargs = Dict(Symbol(key) => value for (key, value) in conditions["evaluator_settings"])
    evaluator_settings = D3SlotEvaluationSettings(; evaluator_kwargs...)
    h = conditions["hb_settings"]
    hb_settings = D3HBSettings(
        Float64(h["section_length_um"]) * D3_METERS_PER_UM,
        h["port_resistance_ohm"],
        h["pump_frequency_hz"],
        h["pump_current_a"],
        h["n_pump_harmonics"],
        h["n_modulation_harmonics"],
        Dict{Symbol,Any}(:nbatches => h["nbatches"], :iterations => h["iterations"], :ftol => h["ftol"]),
    )
    require_feedline_port_match(feedline, hb_settings)

    return () -> begin
        evaluator = D3SlotEvaluator(
            selected_case,
            seed_design,
            feedline,
            hb_settings,
            evaluator_settings,
            qubit_input.model,
            qubit_input.input_sha256,
            floating_qubit_coupling_off_frequency_hz(qubit_input.model);
            qubit_f01_target_hz = f01_target_hz,
            expected_L_J_per_junction_nH = expected_lj_nH,
            qubit_target_contract_id = target["target_id"],
            qubit_target_contract_sha256 = target_sha256,
            journal_path = nothing,
        )
        return candidate_records -> begin
            candidate_by_id = Dict(String(item["id"]) => Float64(item["value"]) for item in candidate_records)
            candidate = NamedTuple{Tuple(Symbol.(VARIABLE_IDS))}(Tuple(candidate_by_id[id] for id in VARIABLE_IDS))
            return evaluate_d3_slot(evaluator, candidate; capture_traces = true)
        end
    end
end

function main(arguments)
    length(arguments) == 1 || error("Usage: julia scripts/build/run_d3_nominal_validation.jl <persisted_optimizer_run_directory>")
    optimizer_run = abspath(arguments[1])
    preflight = preflight_optimizer_run(optimizer_run)
    preflight.is_current || error("Legacy optimizer runs are preflight-only; nominal execution requires a current per-Slot manifest.")
    config_snapshot_path = joinpath(optimizer_run, "config_snapshot.json")
    config = preflight.config_snapshot
    conditions_path = workspace_path(preflight.consumed_inventory["optimizer_conditions"]["path"])
    conditions = JSON3.read(read(conditions_path, String), Dict{String,Any})
    target_path = workspace_path(config["target_contract"]["workspace_relative_path"])
    q2d_path = workspace_path(config["orpen_case_json_workspace_path"])
    seed_path = workspace_path(joinpath(String(config["design_csv_workspace_root"]), String(config["design_csv_filename"])))
    runtime_path = joinpath(D3_NOTEBOOK_ROOT, "d3_nominal_validation.jl")
    source_paths = Dict(
        "target" => target_path,
        "conditions" => conditions_path,
        "config_snapshot" => config_snapshot_path,
        "q2d" => q2d_path,
        "seed" => seed_path,
        "common" => workspace_path(preflight.consumed_inventory["d3_purcell_common"]["path"]),
        "evaluator" => workspace_path(preflight.consumed_inventory["d3_coupled_evaluator"]["path"]),
        "semantic_hash" => workspace_path(preflight.consumed_inventory["d3_semantic_hash"]["path"]),
        "qubit_input" => workspace_path(config["floating_qubit_nominal_workspace_path"]),
        "qubit_input_loader" => workspace_path(preflight.consumed_inventory["d3_floating_qubit_input_loader"]["path"]),
        "runner" => @__FILE__,
        "nominal_runtime" => runtime_path,
    )
    output_root = joinpath(WORKBENCH_ROOT, "build", "research", "d3_nominal_validation_v1")
    result = run_nominal_validation(
        optimizer_run;
        output_root = output_root,
        source_paths = source_paths,
        workspace_root = WORKSPACE_ROOT,
        evaluator_factory = physical_evaluator_factory(preflight, config, conditions),
        fresh_process = true,
        fresh_evaluator = true,
    )
    println(result.run_directory)
    return nothing
end

main(ARGS)
