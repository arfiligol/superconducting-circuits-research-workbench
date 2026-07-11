# This module owns the persisted-run contract for one independent nominal D3
# validation. It never selects an optimizer-history candidate, never falls back
# to final_diagnostics.json, and never implements tolerance perturbations. The
# CLI supplies the fresh physical evaluator; tests may inject a synthetic
# evaluator to exercise the artifact contract without HB.

module D3NominalValidation

using Dates
using SHA
using SuperconductingCircuitsCore

const JSON3 = SuperconductingCircuitsCore.JSON3
include(joinpath(@__DIR__, "d3_semantic_hash.jl"))
using .D3SemanticHash

export OPTIMIZER_OUTPUT_FILES, VALIDATION_OUTPUT_FILES, VARIABLE_IDS,
    preflight_optimizer_run, require_nominal_variation, run_nominal_validation,
    workspace_relative, semantic_value_sha256, SEMANTIC_HASH_FRAMING

const OPTIMIZER_OUTPUT_FILES = Set([
    "status.json",
    "condition_manifest.json",
    "config_snapshot.json",
    "hash_inventory.json",
    "evaluations.jsonl",
    "optimization_result.json",
    "layout_specs.json",
    "final_diagnostics.json",
])
const VALIDATION_OUTPUT_FILES = Set([
    "status.json",
    "validation_manifest.json",
    "layout_specs_snapshot.json",
    "hash_inventory.json",
    "nominal_evaluation.json",
    "validation_summary.json",
])
const VARIABLE_IDS = [
    "lc_um",
    "lp_short_um",
    "lr_short_um",
    "lp_open_um",
    "lr_open_um",
    "filter_to_line_capacitance_fF",
]
const VARIABLE_UNITS = Dict(
    "lc_um" => "um",
    "lp_short_um" => "um",
    "lr_short_um" => "um",
    "lp_open_um" => "um",
    "lr_open_um" => "um",
    "filter_to_line_capacitance_fF" => "fF",
)
const EVALUATOR_METRIC_IDS = [
    "filter_loaded_bare_hz",
    "readout_loaded_bare_hz",
    "readout_minus_filter_detuning_hz",
    "loaded_bare_center_hz",
    "model_paired_pole_center_hz",
    "vector_paired_pole_center_hz",
    "pair_pole_center_offset_hz",
    "notch_hz",
    "filter_loaded_linewidth_hz",
    "j_hz",
    "g_hz",
]

file_sha256(path) = open(path, "r") do io
    bytes2hex(SHA.sha256(io))
end
is_sha256(value) = value isa AbstractString && occursin(r"^[0-9a-f]{64}$", value)

function workspace_relative(path, workspace_root)
    root = abspath(String(workspace_root))
    absolute = abspath(String(path))
    relative = relpath(absolute, root)
    components = splitpath(relative)
    (!isabspath(relative) && (isempty(components) || first(components) != "..")) || error(
        "Validation source path must stay inside the workspace: $(path)",
    )
    return replace(relative, '\\' => '/')
end

function json_ready(value)
    isnothing(value) && return nothing
    value isa AbstractDict && return Dict(String(key) => json_ready(item) for (key, item) in pairs(value))
    value isa NamedTuple && return Dict(String(key) => json_ready(getproperty(value, key)) for key in propertynames(value))
    value isa AbstractVector && return [json_ready(item) for item in value]
    value isa Tuple && return [json_ready(item) for item in value]
    value isa Complex && return Dict("real" => Float64(real(value)), "imag" => Float64(imag(value)))
    value isa Symbol && return String(value)
    value isa AbstractFloat && !isfinite(value) && error("Refusing to persist non-finite validation evidence.")
    value isa DateTime && return string(value)
    if isstructtype(typeof(value)) && !(value isa AbstractString) && !(value isa Number)
        return Dict(String(name) => json_ready(getfield(value, name)) for name in fieldnames(typeof(value)))
    end
    return value
end

function write_json(path, value)
    open(path, "w") do io
        JSON3.write(io, json_ready(value))
        write(io, '\n')
    end
    return path
end

function require_nominal_variation(variation)
    isempty(variation) || error("D3 nominal validation does not implement perturbations; nonempty variation is unsupported.")
    return nothing
end

function source_selection(contract)
    if haskey(contract, "selection")
        selection = contract["selection"]
        source_row = selection["source_row"]
        return (
            case_id = String(selection["case_id"]),
            target_set_id = String(selection["target_set_id"]),
            slot_target_ghz = Float64(selection["slot_target_ghz"]),
            source_row_id = String(source_row["id"]),
        )
    end
    scope = contract["scope"]
    source_row = contract["design_selection"]["source_row"]["value"]
    return (
        case_id = String(scope["selected_case_id"]),
        target_set_id = String(source_row["target_set_id"]),
        slot_target_ghz = Float64(scope["slot_target_hz"]) / 1e9,
        source_row_id = String(source_row["row_id"]),
    )
end

function normalized_inventory(records)
    result = Dict{String,Dict{String,Any}}()
    for item in records
        id = String(item["id"])
        haskey(result, id) && error("Optimizer hash inventory contains duplicate id $(id).")
        hash = if haskey(item, "sha256")
            String(item["sha256"])
        elseif haskey(item, "observed_sha256")
            String(item["observed_sha256"])
        else
            error("Optimizer hash inventory item $(id) has no observed SHA-256.")
        end
        is_sha256(hash) || error("Optimizer hash inventory item $(id) has an invalid SHA-256.")
        haskey(item, "expected_sha256") && String(item["expected_sha256"]) != hash && error(
            "Optimizer hash inventory item $(id) has inconsistent expected and observed hashes.",
        )
        result[id] = Dict("path" => String(item["path"]), "sha256" => hash)
    end
    return result
end

"""Validate a persisted optimizer run without consulting in-memory state."""
function preflight_optimizer_run(run_directory)
    run_path = abspath(String(run_directory))
    isdir(run_path) || error("Optimizer run directory does not exist: $(run_path)")
    Set(readdir(run_path)) == OPTIMIZER_OUTPUT_FILES || error("Optimizer run must contain exactly the declared eight files.")

    status = JSON3.read(read(joinpath(run_path, "status.json"), String), Dict{String,Any})
    get(status, "state", nothing) == "completed" || error("Nominal validation requires a completed optimizer run.")
    layout_path = joinpath(run_path, "layout_specs.json")
    layout = JSON3.read(read(layout_path, String), Dict{String,Any})
    get(layout, "state", nothing) == "best_valid_candidate" || error("layout_specs.json must contain a best_valid_candidate.")
    variables = get(layout, "variables", nothing)
    variables isa AbstractVector || error("layout_specs.json variables must be an array.")
    String[item["id"] for item in variables] == VARIABLE_IDS || error("Layout variable ids/order do not match the D3 candidate contract.")
    for item in variables
        id = String(item["id"])
        String(item["unit"]) == VARIABLE_UNITS[id] || error("Layout variable $(id) has the wrong unit.")
        value = Float64(item["value"])
        isfinite(value) || error("Layout variable $(id) must be finite.")
    end
    candidate_records = [Dict("id" => String(item["id"]), "value" => Float64(item["value"]), "unit" => String(item["unit"])) for item in variables]
    candidate_sha = semantic_value_sha256(candidate_records)
    candidate_id = String(get(layout, "candidate_record_id", ""))
    isempty(candidate_id) && error("layout_specs.json must bind a candidate_record_id.")

    manifest = JSON3.read(read(joinpath(run_path, "condition_manifest.json"), String), Dict{String,Any})
    contract = manifest["contract"]
    schema = String(get(manifest, "schema_version", "d3-condition-manifest.v1"))
    current = schema == "d3-slot-execution-manifest.v1"
    declared_hash = String(current ? get(manifest, "execution_sha256", "") : get(manifest, "contract_sha256", ""))
    is_sha256(declared_hash) || error("Optimizer manifest identity must be a nonempty lowercase SHA-256.")
    if current
        get(manifest, "semantic_hash_framing", nothing) == SEMANTIC_HASH_FRAMING || error("Current optimizer manifest uses the wrong semantic hash framing.")
        observed_hash = semantic_value_sha256(Dict(
            "schema_version" => schema,
            "semantic_hash_framing" => SEMANTIC_HASH_FRAMING,
            "contract" => contract,
        ))
        observed_hash == declared_hash || error("Current optimizer execution SHA-256 does not match its canonical manifest payload.")
    end
    optimizer_result_path = joinpath(run_path, "optimization_result.json")
    optimizer_result = JSON3.read(read(optimizer_result_path, String), Dict{String,Any})
    optimizer_id = String(get(contract, "manifest_id", get(optimizer_result, "condition_manifest_id", "")))
    isempty(optimizer_id) && error("Optimizer identity is missing.")
    String(get(optimizer_result, "condition_manifest_id", "")) == optimizer_id || error(
        "Optimizer result id disagrees with the persisted manifest.",
    )
    status_hash = String(current ? get(status, "execution_sha256", "") : get(status, "contract_sha256", ""))
    result_hash = String(get(optimizer_result, "condition_manifest_sha256", ""))
    layout_hash = String(get(layout, "condition_manifest_sha256", ""))
    all(==(declared_hash), (status_hash, result_hash, layout_hash)) || error(
        "Optimizer manifest/status/result/layout identities are inconsistent.",
    )
    suffix_match = match(r"__([0-9a-f]{12})$", basename(run_path))
    !isnothing(suffix_match) && suffix_match.captures[1] != first(declared_hash, 12) && error(
        "Optimizer run-directory suffix disagrees with its persisted identity.",
    )
    hash_inventory_payload = JSON3.read(read(joinpath(run_path, "hash_inventory.json"), String), Dict{String,Any})
    inventory_identity = String(current ? get(hash_inventory_payload, "execution_sha256", "") : get(hash_inventory_payload, "contract_sha256", ""))
    inventory_identity == declared_hash || error("Optimizer hash inventory identity is inconsistent.")
    consumed_inventory = normalized_inventory(hash_inventory_payload["files"])
    if current
        declared_consumed = normalized_inventory(contract["consumed_files"])
        declared_consumed == consumed_inventory || error("Optimizer manifest and hash inventory consumed-file identities differ.")
    end
    config_snapshot_path = joinpath(run_path, "config_snapshot.json")
    config_snapshot_sha = file_sha256(config_snapshot_path)
    if current
        expected_config_snapshot_sha = String(get(hash_inventory_payload, "config_snapshot_sha256", ""))
        is_sha256(expected_config_snapshot_sha) || error("Current optimizer inventory must bind config_snapshot.json SHA-256.")
        expected_config_snapshot_sha == config_snapshot_sha || error("Persisted optimizer config snapshot was modified after execution.")
    end
    config_snapshot = JSON3.read(read(config_snapshot_path, String), Dict{String,Any})
    if current
        final_diagnostics = JSON3.read(read(joinpath(run_path, "final_diagnostics.json"), String), Dict{String,Any})
        get(final_diagnostics, "analysis_kind", nothing) == "optimizer_internal_final_reproduction" || error(
            "Current optimizer final diagnostics must identify optimizer-internal final reproduction.",
        )
        get(final_diagnostics, "independent_validation", nothing) === false || error(
            "Current optimizer final diagnostics must not claim independent validation.",
        )
        for key in ("execution_sha256", "condition_manifest_sha256")
            haskey(final_diagnostics, key) && String(final_diagnostics[key]) != declared_hash && error(
                "Current optimizer final diagnostics $(key) is inconsistent.",
            )
        end
    end
    optimizer_identity = Dict(
        "optimizer_id" => optimizer_id,
        "condition_manifest_sha256" => declared_hash,
        "optimization_result_sha256" => file_sha256(optimizer_result_path),
    )
    selection = source_selection(contract)
    return (
        run_directory = run_path,
        source_run_id = basename(run_path),
        schema_version = schema,
        is_current = current,
        optimizer_contract_sha256 = declared_hash,
        optimizer_id = optimizer_id,
        optimizer_identity = optimizer_identity,
        optimizer_identity_sha256 = semantic_value_sha256(optimizer_identity),
        selection = selection,
        layout = layout,
        layout_raw_sha256 = file_sha256(layout_path),
        candidate_records = candidate_records,
        candidate_sha256 = candidate_sha,
        candidate_id = candidate_id,
        config_snapshot = config_snapshot,
        config_snapshot_sha256 = config_snapshot_sha,
        consumed_inventory = consumed_inventory,
        optimizer_contract = contract,
    )
end

function metric_value(metrics, id)
    if metrics isa AbstractDict
        haskey(metrics, id) || error("Nominal evaluator is missing metric $(id).")
        return Float64(metrics[id])
    end
    name = Symbol(id)
    hasproperty(metrics, name) || error("Nominal evaluator is missing metric $(id).")
    return Float64(getproperty(metrics, name))
end

function target_values(target, slot_ghz)
    targets = target["targets"]
    return Dict(
        "filter_loaded_bare_hz" => (Float64(slot_ghz) * 1e3 + Float64(targets["filter_loaded_bare_offset"]["value"])) * 1e6,
        "readout_loaded_bare_hz" => (Float64(slot_ghz) * 1e3 + Float64(targets["readout_loaded_bare_offset"]["value"])) * 1e6,
        "notch_hz" => Float64(targets["interference_notch_frequency"]["value"]) * 1e9,
        "filter_loaded_linewidth_hz" => Float64(targets["filter_loaded_bare_linewidth"]["value"]) * 1e6,
        "j_hz" => Float64(targets["readout_filter_exchange_coupling"]["value"]) * 1e6,
        "g_hz" => Float64(targets["qubit_readout_coupling"]["value"]) * 1e6,
        "readout_minus_filter_detuning_hz" => Float64(targets["readout_minus_filter_detuning"]["value"]) * 1e6,
    )
end

function objective_operands(record, target, conditions, slot_ghz)
    status = getproperty(record, :status)
    status === :valid || error("Independent nominal evaluation must return valid physical evidence; received $(status).")
    metrics = getproperty(record, :metrics)
    actual_ids = metrics isa AbstractDict ? Set(String.(keys(metrics))) : Set(String.(propertynames(metrics)))
    actual_ids == Set(EVALUATOR_METRIC_IDS) || error("Nominal evaluator metric contract changed.")
    targets = target_values(target, slot_ghz)
    specs = conditions["metric_specs"]
    objective_ids = [id for id in keys(specs) if Float64(specs[id]["weight"]) > 0]
    sort!(objective_ids)
    return [
        begin
            observed = metric_value(metrics, id)
            target_value = Float64(targets[id])
            scale = Float64(specs[id]["scale"])
            Dict(
                "id" => id,
                "unit" => "Hz",
                "target" => target_value,
                "observed" => observed,
                "scale" => scale,
                "normalized_residual" => (observed - target_value) / scale,
            )
        end
        for id in objective_ids
    ]
end

function resolve_declared_path(relative_path, workspace_root)
    path = String(relative_path)
    isabspath(path) && error("Persisted optimizer path must be workspace-relative: $(path)")
    components = splitpath(path)
    any(==(".."), components) && error("Persisted optimizer path must not contain '..': $(path)")
    resolved = normpath(joinpath(workspace_root, components...))
    workspace_relative(resolved, workspace_root)
    return resolved
end

function bind_current_sources(preflight, source_paths, workspace_root)
    preflight.is_current || error("Nominal execution requires the current per-Slot optimizer manifest; legacy runs are preflight-only.")
    required_sources = Set([
        "target", "conditions", "config_snapshot", "q2d", "seed",
        "common", "evaluator", "semantic_hash", "qubit_input", "qubit_input_loader",
        "runner", "nominal_runtime",
    ])
    Set(String.(keys(source_paths))) == required_sources || error("Nominal validation source hash inventory is not exact.")
    for path in values(source_paths)
        isfile(path) || error("Nominal validation source file is missing: $(path)")
        workspace_relative(path, workspace_root)
    end

    config = preflight.config_snapshot
    target_path = resolve_declared_path(config["target_contract"]["workspace_relative_path"], workspace_root)
    q2d_path = resolve_declared_path(config["orpen_case_json_workspace_path"], workspace_root)
    seed_path = resolve_declared_path(joinpath(String(config["design_csv_workspace_root"]), String(config["design_csv_filename"])), workspace_root)
    qubit_path = resolve_declared_path(config["floating_qubit_nominal_workspace_path"], workspace_root)
    inventory = preflight.consumed_inventory
    for id in ("target_contract", "optimizer_conditions", "seed_csv", "orpen_case_json", "d3_purcell_common", "d3_coupled_evaluator", "d3_semantic_hash", "floating_qubit_nominal", "d3_floating_qubit_input_loader")
        haskey(inventory, id) || error("Persisted optimizer inventory is missing $(id).")
    end
    conditions_path = resolve_declared_path(inventory["optimizer_conditions"]["path"], workspace_root)
    common_path = resolve_declared_path(inventory["d3_purcell_common"]["path"], workspace_root)
    evaluator_path = resolve_declared_path(inventory["d3_coupled_evaluator"]["path"], workspace_root)
    semantic_hash_path = resolve_declared_path(inventory["d3_semantic_hash"]["path"], workspace_root)
    qubit_loader_path = resolve_declared_path(inventory["d3_floating_qubit_input_loader"]["path"], workspace_root)
    expected_paths = Dict(
        "target" => target_path,
        "conditions" => conditions_path,
        "config_snapshot" => joinpath(preflight.run_directory, "config_snapshot.json"),
        "q2d" => q2d_path,
        "seed" => seed_path,
        "common" => common_path,
        "evaluator" => evaluator_path,
        "semantic_hash" => semantic_hash_path,
        "qubit_input" => qubit_path,
        "qubit_input_loader" => qubit_loader_path,
    )
    for (id, expected_path) in expected_paths
        abspath(source_paths[id]) == abspath(expected_path) || error("Nominal source $(id) does not match the persisted optimizer selection.")
    end

    contract = preflight.optimizer_contract
    target_sha = file_sha256(target_path)
    target_sha == String(config["target_contract"]["expected_sha256"]) || error("Persisted config target hash does not match the selected target file.")
    target_sha == String(contract["target_contract"]["sha256"]) || error("Per-Slot manifest target hash does not match the selected target file.")
    target_sha == inventory["target_contract"]["sha256"] || error("Optimizer inventory target hash is inconsistent.")

    conditions = JSON3.read(read(conditions_path, String), Dict{String,Any})
    get(contract["optimizer_conditions"], "hash_framing", nothing) == SEMANTIC_HASH_FRAMING || error("Per-Slot manifest conditions identity uses the wrong semantic hash framing.")
    get(conditions["sol_review"], "hash_framing", nothing) == SEMANTIC_HASH_FRAMING || error("Generic conditions review metadata uses the wrong semantic hash framing.")
    conditions_contract = Dict(key => value for (key, value) in conditions if key != "sol_review")
    conditions_contract_sha = semantic_value_sha256(conditions_contract)
    conditions_contract_sha == String(contract["optimizer_conditions"]["sha256"]) || error("Per-Slot manifest conditions hash does not match the selected generic conditions.")
    file_sha256(conditions_path) == inventory["optimizer_conditions"]["sha256"] || error("Optimizer inventory conditions file hash is inconsistent.")
    file_sha256(q2d_path) == inventory["orpen_case_json"]["sha256"] || error("Persisted Q2D source hash is inconsistent.")
    file_sha256(seed_path) == inventory["seed_csv"]["sha256"] || error("Persisted optimizer seed source hash is inconsistent.")
    file_sha256(common_path) == inventory["d3_purcell_common"]["sha256"] || error("Persisted common-runtime source hash is inconsistent.")
    file_sha256(evaluator_path) == inventory["d3_coupled_evaluator"]["sha256"] || error("Persisted evaluator source hash is inconsistent.")
    file_sha256(semantic_hash_path) == inventory["d3_semantic_hash"]["sha256"] || error("Persisted semantic-hash source identity is inconsistent.")
    qubit_sha = file_sha256(qubit_path)
    qubit_sha == inventory["floating_qubit_nominal"]["sha256"] || error("Persisted floating-qubit input hash is inconsistent.")
    file_sha256(qubit_loader_path) == inventory["d3_floating_qubit_input_loader"]["sha256"] || error("Persisted floating-qubit loader source hash is inconsistent.")
    target = JSON3.read(read(target_path, String), Dict{String,Any})
    f01_record = target["targets"]["qubit_transition_frequency"]
    lj_record = target["targets"]["qubit_junction_inductance"]
    f01_record["unit"] == "GHz" || error("Canonical qubit transition target must use GHz.")
    lj_record["unit"] == "nH_per_junction" || error("Canonical qubit junction target must use nH_per_junction.")
    Int(lj_record["parallel_junction_count"]) == 2 || error("Canonical D3 qubit target must declare two parallel junctions.")
    f01_target_hz = Float64(f01_record["value"]) * 1e9
    expected_lj_nH = Float64(lj_record["value"])
    qubit_payload = JSON3.read(read(qubit_path, String), Dict{String,Any})
    qubit_contract = contract["floating_qubit_nominal"]
    qubit_sha == String(qubit_contract["input_sha256"]) || error("Floating-qubit manifest identity disagrees with the selected private input bytes.")
    String(qubit_payload["model_id"]) == String(qubit_contract["model_id"]) || error("Floating-qubit model identity disagrees with the selected private input.")
    qubit_payload["schema_version"] == qubit_contract["schema_version"] == "d3-floating-qubit-maxwell.v1" || error("Floating-qubit full-Maxwell schema is inconsistent.")
    qubit_payload["readout_self_capacitance_ownership"] == qubit_contract["readout_self_capacitance_ownership"] == "distributed_resonator_owns_self_capacitance" || error("Floating-qubit readout self-capacitance ownership is inconsistent.")
    qubit_contract["readout_diagonal_instantiated"] === false || error("Reduced readout diagonal must not be instantiated.")
    Float64(qubit_payload["L_J_per_junction_nH"]) == Float64(qubit_contract["L_J_per_junction_nH"]) == expected_lj_nH || error("Floating-qubit junction inductance disagrees with the canonical target.")
    qubit_targets = qubit_contract["canonical_targets"]
    qubit_targets["target_contract_id"] == target["target_id"] || error("Floating-qubit target contract id is inconsistent.")
    qubit_targets["target_contract_sha256"] == target_sha || error("Floating-qubit target contract SHA-256 is inconsistent.")
    Float64(qubit_targets["qubit_transition_frequency"]["value"]) == f01_target_hz || error("Floating-qubit f01 target is inconsistent.")
    Float64(qubit_targets["qubit_junction_inductance"]["value"]) == expected_lj_nH || error("Floating-qubit L_J target is inconsistent.")
    file_sha256(source_paths["config_snapshot"]) == preflight.config_snapshot_sha256 || error("Persisted config snapshot hash is inconsistent.")
    return (
        target = target,
        conditions = conditions,
        target_sha256 = target_sha,
        conditions_contract_sha256 = conditions_contract_sha,
        floating_qubit_input_sha256 = qubit_sha,
        floating_qubit_model_id = String(qubit_payload["model_id"]),
    )
end

function completed_duplicate(output_root, validation_contract_sha256)
    isdir(output_root) || return nothing
    for name in readdir(output_root)
        directory = joinpath(output_root, name)
        isdir(directory) || continue
        files = Set(readdir(directory))
        likely_duplicate = occursin("__nominal__", name) || !isempty(intersect(files, VALIDATION_OUTPUT_FILES))
        files == VALIDATION_OUTPUT_FILES || (likely_duplicate ? error("Malformed likely-matching nominal validation $(directory): expected exact-six files.") : continue)
        try
            status = JSON3.read(read(joinpath(directory, "status.json"), String), Dict{String,Any})
            manifest = JSON3.read(read(joinpath(directory, "validation_manifest.json"), String), Dict{String,Any})
            if get(status, "state", nothing) == "completed" && manifest["validation_contract_sha256"] == validation_contract_sha256
                return directory
            end
        catch exception
            likely_duplicate && error("Malformed likely-matching nominal validation $(directory): $(sprint(showerror, exception))")
        end
    end
    return nothing
end

"""Run one nominal evaluator call and persist the immutable exact-six contract."""
function run_nominal_validation(
    optimizer_run_directory;
    output_root,
    source_paths,
    workspace_root,
    evaluator_factory,
    fresh_process,
    fresh_evaluator,
    variation = Dict{String,Any}(),
)
    require_nominal_variation(variation)
    fresh_process === true || error("Production nominal validation requires a fresh Julia process.")
    fresh_evaluator === true || error("Production nominal validation requires a fresh D3SlotEvaluator.")
    preflight = preflight_optimizer_run(optimizer_run_directory)
    bound = bind_current_sources(preflight, source_paths, workspace_root)
    source_hashes = [
        Dict(
            "id" => id,
            "path" => workspace_relative(path, workspace_root),
            "sha256" => file_sha256(path),
        )
        for (id, path) in sort!(collect(source_paths); by = pair -> first(pair))
    ]
    source_hash_by_id = Dict(item["id"] => item["sha256"] for item in source_hashes)
    contract = Dict(
        "analysis_kind" => "nominal",
        "source_optimizer" => Dict(
            "run_id" => preflight.source_run_id,
            "run_directory" => workspace_relative(preflight.run_directory, workspace_root),
            "optimizer_id" => preflight.optimizer_id,
            "optimizer_contract_sha256" => preflight.optimizer_contract_sha256,
            "optimizer_identity_sha256" => preflight.optimizer_identity_sha256,
            "layout_specs_raw_sha256" => preflight.layout_raw_sha256,
            "candidate_id" => preflight.candidate_id,
            "candidate_sha256" => preflight.candidate_sha256,
        ),
        "bound_identities" => Dict(
            "target_sha256" => bound.target_sha256,
            "conditions_contract_sha256" => bound.conditions_contract_sha256,
            "conditions_file_sha256" => source_hash_by_id["conditions"],
            "config_snapshot_sha256" => preflight.config_snapshot_sha256,
            "q2d_sha256" => source_hash_by_id["q2d"],
            "seed_sha256" => source_hash_by_id["seed"],
            "floating_qubit_input_sha256" => bound.floating_qubit_input_sha256,
            "floating_qubit_loader_sha256" => source_hash_by_id["qubit_input_loader"],
            "floating_qubit_model_id" => bound.floating_qubit_model_id,
            "layout_specs_raw_sha256" => preflight.layout_raw_sha256,
            "candidate_sha256" => preflight.candidate_sha256,
            "optimizer_identity_sha256" => preflight.optimizer_identity_sha256,
        ),
        "selection" => Dict(
            "case_id" => preflight.selection.case_id,
            "target_set_id" => preflight.selection.target_set_id,
            "slot_target_ghz" => preflight.selection.slot_target_ghz,
        ),
        "execution" => Dict(
            "fresh_process" => true,
            "fresh_evaluator" => true,
            "capture_traces" => true,
            "optimizer_cache_allowed" => false,
            "evaluation_budget" => 1,
        ),
        "variation" => Dict("kind" => "none", "parameters" => Any[]),
        "source_hashes" => source_hashes,
    )
    validation_hash = semantic_value_sha256(Dict(
        "schema_version" => "d3-nominal-validation-manifest.v1",
        "semantic_hash_framing" => SEMANTIC_HASH_FRAMING,
        "contract" => contract,
    ))
    manifest = Dict(
        "schema_version" => "d3-nominal-validation-manifest.v1",
        "semantic_hash_framing" => SEMANTIC_HASH_FRAMING,
        "validation_contract_sha256" => validation_hash,
        "contract" => contract,
    )
    duplicate = completed_duplicate(String(output_root), validation_hash)
    isnothing(duplicate) || error("Completed nominal validation already exists for this exact contract and is view-only: $(duplicate)")

    mkpath(output_root)
    safe_source = replace(preflight.source_run_id, r"[^A-Za-z0-9._-]" => "-")
    run_id = Dates.format(now(UTC), dateformat"yyyymmddTHHMMSSsssZ") * "__nominal__" * safe_source * "__" * first(preflight.candidate_sha256, 12)
    run_directory = joinpath(output_root, run_id)
    ispath(run_directory) && error("Refusing to overwrite nominal validation run: $(run_directory)")
    mkpath(run_directory)
    paths = Dict(name => joinpath(run_directory, name) for name in VALIDATION_OUTPUT_FILES)
    started_at = now(UTC)
    write_json(paths["validation_manifest.json"], manifest)
    write_json(paths["layout_specs_snapshot.json"], Dict(
        "validation_contract_sha256" => validation_hash,
        "layout_specs_raw_sha256" => preflight.layout_raw_sha256,
        "layout_specs" => preflight.layout,
    ))
    write_json(paths["hash_inventory.json"], Dict("validation_contract_sha256" => validation_hash, "files" => source_hashes))
    write_json(paths["status.json"], Dict(
        "validation_contract_sha256" => validation_hash,
        "analysis_kind" => "nominal",
        "state" => "running",
        "started_at_utc" => started_at,
        "completed_at_utc" => nothing,
        "artifact_role" => "view_only_validation",
    ))
    try
        candidate_evaluator = evaluator_factory()
        evaluation_count = 0
        evaluation_count += 1
        record = candidate_evaluator(preflight.candidate_records)
        evaluation_count == 1 || error("Nominal validation must evaluate exactly once.")
        operands = objective_operands(record, bound.target, bound.conditions, preflight.selection.slot_target_ghz)
        write_json(paths["nominal_evaluation.json"], Dict(
            "validation_contract_sha256" => validation_hash,
            "analysis_kind" => "nominal",
            "independent_validation" => true,
            "evaluation_count" => evaluation_count,
            "variation" => Dict("kind" => "none", "parameters" => Any[]),
            "record" => record,
        ))
        write_json(paths["validation_summary.json"], Dict(
            "validation_contract_sha256" => validation_hash,
            "analysis_kind" => "nominal",
            "human_acceptance_claim" => nothing,
            "objective_operands" => operands,
        ))
        write_json(paths["status.json"], Dict(
            "validation_contract_sha256" => validation_hash,
            "analysis_kind" => "nominal",
            "state" => "completed",
            "started_at_utc" => started_at,
            "completed_at_utc" => now(UTC),
            "artifact_role" => "view_only_validation",
        ))
        Set(readdir(run_directory)) == VALIDATION_OUTPUT_FILES || error("Nominal validation run must contain exactly six files.")
        return (run_directory = run_directory, validation_contract_sha256 = validation_hash, evaluation = record)
    catch exception
        failure = Dict(
            "validation_contract_sha256" => validation_hash,
            "analysis_kind" => "nominal",
            "state" => "failed",
            "error_type" => string(typeof(exception)),
            "reason" => sprint(showerror, exception),
        )
        isfile(paths["nominal_evaluation.json"]) || write_json(paths["nominal_evaluation.json"], failure)
        isfile(paths["validation_summary.json"]) || write_json(paths["validation_summary.json"], failure)
        write_json(paths["status.json"], merge(failure, Dict(
            "started_at_utc" => started_at,
            "completed_at_utc" => now(UTC),
            "artifact_role" => "view_only_validation",
        )))
        Set(readdir(run_directory)) == VALIDATION_OUTPUT_FILES || error("Failed nominal validation run must contain exactly six files.")
        rethrow()
    end
end

end
