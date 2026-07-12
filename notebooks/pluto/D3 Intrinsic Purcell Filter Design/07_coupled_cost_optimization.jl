### A Pluto.jl notebook ###
# v1.0.2

#> [frontmatter]
#> title = "07 D3 Multi-Slot Cost Optimization"
#> tags = ["pluto", "d3", "purcell-filter", "optimization", "human-decision"]
#> description = "Select, preview, evaluate, and optimize one canonical D3 slot without rerunning completed evidence."

using Markdown
using InteractiveUtils

# ╔═╡ 956db29c-afb0-471c-93f7-fc434f660064
begin
	import Pkg
	Pkg.activate(joinpath(first(DEPOT_PATH), "environments", "v1.12"); io = devnull)

	using Dates
	using LinearAlgebra
	using PlutoUI
	using SHA
	workbench_root = normpath(joinpath(@__DIR__, "..", "..", ".."))
	bridge_python = joinpath(workbench_root, ".venv", "bin", "python")
	if !haskey(ENV, "JULIA_PYTHONCALL_EXE") && isfile(bridge_python) && (uperm(bridge_python) & 0o111 != 0)
		ENV["JULIA_PYTHONCALL_EXE"] = bridge_python
	end
	!haskey(ENV, "JULIA_CONDAPKG_BACKEND") && (ENV["JULIA_CONDAPKG_BACKEND"] = "Null")
	using SuperconductingCircuitsAnalysisBridge
	using SuperconductingCircuitsCore

	macro bind(def, element)
		quote
			local initial_value = try
				Base.loaded_modules[
					Base.PkgId(Base.UUID("6e696c72-6542-2067-7265-42206c756150"), "AbstractPlutoDingetjes"),
				].Bonds.initial_value
			catch
				_ -> missing
			end
			local element_value = $(esc(element))
			global $(esc(def)) = Core.applicable(Base.get, element_value) ?
				Base.get(element_value) : initial_value(element_value)
			element_value
		end
	end

	JSON3 = SuperconductingCircuitsCore.JSON3
	include(joinpath(@__DIR__, "d3_semantic_hash.jl"))
	using .D3SemanticHash
	include(joinpath(@__DIR__, "..", "includes", "hb_example_helpers.jl"))
	zero_mode_s = HBExampleHelpers.zero_mode_s
	include(joinpath(@__DIR__, "d3_purcell_common.jl"))
	include(joinpath(@__DIR__, "d3_floating_qubit_nominal_comparison.jl"))
	using .D3FloatingQubitNominalComparison
	include(joinpath(@__DIR__, "d3_coupled_evaluator.jl"))
	include(joinpath(@__DIR__, "d3_coupled_optimizer.jl"))
	using .D3CoupledOptimizer
end

# ╔═╡ a5df7804-e15d-4f5a-b319-4df0eabff5c4
md"""
# 07 D3 Multi-Slot Cost Optimization

This is the user interface for the five canonical D3 slots. It reads the
[machine-readable Design Target](https://github.com/arfiligol/SCQ_Design/blob/main/docs/design-targets/contracts/d3-intrinsic-interferometric-purcell-filter.v1.json),
selects exactly one matching CSV seed row, derives slot-specific targets and
bounds, and builds the execution manifest automatically.

Opening the notebook or changing the selector never runs HB and never writes an
artifact. Only completed, target-satisfying evidence that declares the current
v4 extraction contract and has matching execution/fingerprint identities is
read-only. Historical evidence remains viewable but cannot block a fresh v4
run. Failed Slots may be retried. Human promotion remains impossible while the
current LC artifact says `promotion_eligible=false`.
"""

# ╔═╡ fc66b3bc-83ed-4816-b1fe-d5ca8132bdd5
begin
	const D3_WORKSPACE_ROOT = normpath(joinpath(@__DIR__, "..", "..", "..", ".."))
	const D3_CONFIG_PATH = joinpath(@__DIR__, "d3_design_config.json")
	const D3_CONDITIONS_PATH = joinpath(@__DIR__, "d3_optimizer_conditions.json")
	const D3_VARIABLE_IDS = [
		"lc_um", "lp_short_um", "lr_short_um", "lp_open_um", "lr_open_um",
		"filter_to_line_capacitance_fF",
	]
	const D3_EVALUATOR_FIELD_IDS = [
		"filter_loaded_bare_hz", "readout_loaded_bare_hz",
		"readout_minus_filter_detuning_hz", "loaded_bare_center_hz",
		"model_paired_pole_center_hz", "vector_paired_pole_center_hz",
		"pair_pole_center_offset_hz", "notch_hz", "filter_loaded_linewidth_hz", "j_hz",
		"g_hz",
	]
	const D3_OPTIMIZER_METRIC_IDS = [
		"filter_loaded_bare_hz", "readout_loaded_bare_hz", "notch_hz",
		"filter_loaded_linewidth_hz", "j_hz", "readout_minus_filter_detuning_hz",
		"g_hz",
	]
	const D3_OUTPUT_FILES = Set([
		"status.json", "condition_manifest.json", "config_snapshot.json", "hash_inventory.json",
		"evaluations.jsonl", "optimization_result.json", "layout_specs.json", "final_diagnostics.json",
	])
	const D3_CURRENT_EXTRACTION_CONTRACT =
		"d3-three-circuit-model-dark-mode-aware-physical-vs-reduced-eligibility.v4"
	d3_sha256(value) = semantic_value_sha256(value)
	d3_file_sha256(path) = open(path, "r") do io
		bytes2hex(SHA.sha256(io))
	end

	function d3_workspace_path(relative_path)
		path = String(relative_path)
		isabspath(path) && error("D3 paths must be workspace-relative: $(path)")
		resolved = normpath(joinpath(D3_WORKSPACE_ROOT, split(path, '/')...))
		starts_with_workspace = !startswith(relpath(resolved, D3_WORKSPACE_ROOT), "..")
		starts_with_workspace || error("D3 path escapes the workspace: $(path)")
		return resolved
	end

	function d3_load_contracts()
		config = JSON3.read(read(D3_CONFIG_PATH, String), Dict{String,Any})
		conditions = JSON3.read(read(D3_CONDITIONS_PATH, String), Dict{String,Any})
		conditions["schema_version"] == "d3-optimizer-conditions.v1" || error("Unsupported D3 optimizer conditions schema.")
		String.(conditions["variable_order"]) == D3_VARIABLE_IDS || error("D3 variable order changed without an evaluator contract update.")
		Set(String.(keys(conditions["metric_specs"]))) == Set(D3_OPTIMIZER_METRIC_IDS) || error("D3 metric set is not exact.")
		Set(String.(conditions["outputs"]["filenames"])) == D3_OUTPUT_FILES || error("Generic conditions must declare the exact eight D3 output filenames.")
		String(conditions["outputs"]["output_root"]) == String(config["output_root_workspace_path"]) || error("Generic conditions and implementation config must bind the same output root.")
		Int(conditions["optimization"]["initial_seed_evaluation_budget"]) == 1 || error("D3 seed-only evaluation budget must be exactly one.")

		target_reference = config["target_contract"]
		target_path = d3_workspace_path(target_reference["workspace_relative_path"])
		isfile(target_path) || error("Missing canonical D3 target JSON: $(target_path)")
		target_sha = d3_file_sha256(target_path)
		target_sha == target_reference["expected_sha256"] || error(
			"Canonical D3 target changed. An agent must review the new target and update the config hash; users do not edit hashes.",
		)
		target = JSON3.read(read(target_path, String), Dict{String,Any})
		target["target_id"] == target_reference["expected_target_id"] || error("D3 target id mismatch.")
		target["revision"] == target_reference["expected_revision"] || error("D3 target revision mismatch.")
		conditions_review = conditions["sol_review"]
		conditions_review["status"] in ("pending", "sol_reviewed") || error("Unsupported conditions review state.")
		get(conditions_review, "hash_framing", nothing) == SEMANTIC_HASH_FRAMING || error("D3 conditions review must name the semantic hash framing.")
		conditions_contract = Dict(key => value for (key, value) in conditions if key != "sol_review")
		conditions_sha = d3_sha256(conditions_contract)
		if conditions_review["status"] == "sol_reviewed"
			conditions_review["hash_framing"] == SEMANTIC_HASH_FRAMING || error("Sol review uses the wrong semantic hash framing.")
			conditions_review["approved_conditions_sha256"] == conditions_sha || error(
				"Sol review does not bind the current generic conditions contract.",
			)
		end
		return (
			config = config, target = target, conditions = conditions,
			target_path = target_path, target_sha256 = target_sha,
			conditions_sha256 = conditions_sha,
		)
	end

	d3_contracts = d3_load_contracts()
end

# ╔═╡ 7b915116-d455-4cb3-bb06-1577aee8f7cd
begin
	function d3_qubit_targets(target)
		targets = target["targets"]
		f01_record = targets["qubit_transition_frequency"]
		lj_record = targets["qubit_junction_inductance"]
		f01_record["unit"] == "GHz" || error("Canonical qubit transition target must use GHz.")
		lj_record["unit"] == "nH_per_junction" || error("Canonical qubit junction-inductance target must use nH_per_junction.")
		Int(lj_record["parallel_junction_count"]) == 2 || error("D3 floating qubit requires the canonical two-parallel-junction target.")
		f01_hz = Float64(f01_record["value"]) * 1e9
		lj_nH = Float64(lj_record["value"])
		isfinite(f01_hz) && f01_hz > 0 || error("Canonical qubit transition target must be finite and positive.")
		isfinite(lj_nH) && lj_nH > 0 || error("Canonical per-junction L_J target must be finite and positive.")
		return (f01_hz = f01_hz, L_J_per_junction_nH = lj_nH)
	end

	function d3_target_values(target, slot_ghz)
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

	function d3_seed_inputs(contracts)
		config = contracts.config
		seed_path = d3_workspace_path(joinpath(
			String(config["design_csv_workspace_root"]), String(config["design_csv_filename"]),
		))
		case_path = d3_workspace_path(config["orpen_case_json_workspace_path"])
		case_id = String(config["selected_case_id"])
		target_set_id = String(config["target_set_id"])
		designs = [row for row in read_design_csv(seed_path; case_id = case_id) if String(row.target_set_id) == target_set_id]
		slots = Float64.(contracts.target["targets"]["slot_frequencies"]["values"])
		length(designs) == length(slots) || error("The selected case/target-set must contain exactly the configured five Slot rows.")
		[row.slot_target_ghz for row in designs] == slots || error("CSV Slot rows must exactly match the canonical ordered Slot grid.")
		cases = [case for case in load_orpen_cases(case_path) if case.id == Symbol(case_id)]
		length(cases) == 1 || error("The configured OrPen case must exist exactly once.")
		qubit_path = d3_workspace_path(config["floating_qubit_nominal_workspace_path"])
		qubit_input = load_floating_qubit_nominal_input(qubit_path, D3FloatingQubitNominal)
		qubit_targets = d3_qubit_targets(contracts.target)
		qubit_input.model.L_J_per_junction_nH == qubit_targets.L_J_per_junction_nH || error(
			"Private floating-qubit L_J disagrees with the canonical per-junction target.",
		)
		return (
			seed_path = seed_path, case_path = case_path, case_id = case_id,
			target_set_id = target_set_id, designs = designs, slots = slots,
			selected_case = only(cases), csv_sha256 = d3_file_sha256(seed_path),
			case_sha256 = d3_file_sha256(case_path),
			qubit_input = qubit_input, qubit_targets = qubit_targets,
		)
	end

	d3_seed_catalog = d3_seed_inputs(d3_contracts)
end

# ╔═╡ 18ae5d34-a03c-4557-a80d-bdb458f04fa9
begin
	function d3_run_identity(run_directory)
		files = Set(readdir(run_directory))
		likely_d3_run = occursin("d3-coupled-optimization", basename(run_directory)) || !isempty(intersect(files, D3_OUTPUT_FILES))
		files == D3_OUTPUT_FILES || (likely_d3_run ? error("Malformed likely-matching D3 run $(run_directory): expected exact-eight files, observed $(sort!(collect(files))).") : return nothing)
		try
			status = JSON3.read(read(joinpath(run_directory, "status.json"), String), Dict{String,Any})
			manifest = JSON3.read(read(joinpath(run_directory, "condition_manifest.json"), String), Dict{String,Any})
			contract = manifest["contract"]
			if haskey(contract, "selection")
				selection = contract["selection"]
				slot_ghz = Float64(selection["slot_target_ghz"])
				case_id = String(selection["case_id"])
				target_set_id = String(selection["target_set_id"])
				fingerprint = get(contract, "execution_fingerprint_sha256", nothing)
			else
				scope = contract["scope"]
				source = contract["design_selection"]["source_row"]["value"]
				slot_ghz = Float64(scope["slot_target_hz"]) / 1e9
				case_id = String(scope["selected_case_id"])
				target_set_id = String(source["target_set_id"])
				fingerprint = nothing
			end
			return (
				directory = run_directory, status = status, manifest = manifest,
				slot_ghz = slot_ghz, case_id = case_id, target_set_id = target_set_id,
				execution_sha256 = get(manifest, "execution_sha256", nothing),
				fingerprint = fingerprint,
			)
		catch exception
			likely_d3_run && error("Malformed likely-matching D3 run $(run_directory): $(sprint(showerror, exception))")
			return nothing
		end
	end

	function d3_execution_fingerprint(contracts, catalog, slot_ghz)
		source_row = select_d3_source_row(
			catalog.seed_path;
			case_id = catalog.case_id,
			target_set_id = catalog.target_set_id,
			slot_target_ghz = slot_ghz,
		)
		return d3_sha256(Dict(
			"target_id" => contracts.target["target_id"],
			"target_revision" => contracts.target["revision"],
			"target_sha256" => contracts.target_sha256,
			"conditions_sha256" => contracts.conditions_sha256,
			"case_id" => catalog.case_id,
			"target_set_id" => catalog.target_set_id,
			"slot_target_ghz" => Float64(slot_ghz),
			"source_row_sha256" => d3_sha256(source_row),
			"source_csv_sha256" => catalog.csv_sha256,
			"orpen_case_sha256" => catalog.case_sha256,
			"floating_qubit_input_sha256" => catalog.qubit_input.input_sha256,
			"floating_qubit_model_id" => catalog.qubit_input.model.model_id,
		))
	end

	function d3_declared_execution_fingerprint(contract)
		try
			target = contract["target_contract"]
			conditions = contract["optimizer_conditions"]
			selection = contract["selection"]
			qubit = contract["floating_qubit_nominal"]
			inventory = Dict(String(row["id"]) => row for row in contract["consumed_files"])
			return d3_sha256(Dict(
				"target_id" => target["target_id"],
				"target_revision" => target["revision"],
				"target_sha256" => target["sha256"],
				"conditions_sha256" => conditions["sha256"],
				"case_id" => selection["case_id"],
				"target_set_id" => selection["target_set_id"],
				"slot_target_ghz" => Float64(selection["slot_target_ghz"]),
				"source_row_sha256" => selection["source_row_sha256"],
				"source_csv_sha256" => selection["source_csv_sha256"],
				"orpen_case_sha256" => inventory["orpen_case_json"]["expected_sha256"],
				"floating_qubit_input_sha256" => qubit["input_sha256"],
				"floating_qubit_model_id" => qubit["model_id"],
			))
		catch
			return nothing
		end
	end

	function d3_current_run_identity_matches(run, expected_fingerprint)
		manifest = run.manifest
		status = run.status
		get(manifest, "schema_version", nothing) == "d3-slot-execution-manifest.v1" || return false
		get(manifest, "semantic_hash_framing", nothing) == SEMANTIC_HASH_FRAMING || return false
		execution_sha256 = get(manifest, "execution_sha256", nothing)
		execution_sha256 isa AbstractString || return false
		payload = Dict(String(key) => value for (key, value) in manifest if key != "execution_sha256")
		d3_sha256(payload) == execution_sha256 || return false
		get(status, "execution_sha256", nothing) == execution_sha256 || return false
		contract = get(manifest, "contract", nothing)
		contract isa AbstractDict || return false
		fingerprint = get(contract, "execution_fingerprint_sha256", nothing)
		fingerprint isa AbstractString || return false
		d3_declared_execution_fingerprint(contract) == fingerprint || return false
		fingerprint == expected_fingerprint || return false
		get(status, "execution_fingerprint_sha256", nothing) == fingerprint || return false
		return run.execution_sha256 == execution_sha256 && run.fingerprint == fingerprint
	end

	function d3_target_satisfying(run, target, conditions, expected_fingerprint)
		get(run.status, "state", nothing) == "completed" || return false
		d3_current_run_identity_matches(run, expected_fingerprint) || return false
		diagnostics = try
			JSON3.read(read(joinpath(run.directory, "final_diagnostics.json"), String), Dict{String,Any})
		catch
			return false
		end
		get(diagnostics, "state", nothing) == "captured" || return false
		record = get(diagnostics, "record", nothing)
		record isa AbstractDict || return false
		record_diagnostics = get(record, "diagnostics", nothing)
		record_diagnostics isa AbstractDict || return false
		get(record_diagnostics, "extraction_contract", nothing) == D3_CURRENT_EXTRACTION_CONTRACT || return false
		metrics = get(record, "metrics", nothing)
		metrics isa AbstractDict || return false
		targets = d3_target_values(target, run.slot_ghz)
		metric_specs = conditions["metric_specs"]
		cost = 0.0
		max_residual = 0.0
		for id in D3_OPTIMIZER_METRIC_IDS
			haskey(metrics, id) || return false
			residual = abs((Float64(metrics[id]) - targets[id]) / Float64(metric_specs[id]["scale"]))
			max_residual = max(max_residual, residual)
			cost += Float64(metric_specs[id]["weight"]) * residual^2
		end
		promotion = conditions["optimization"]["promotion"]
		return cost <= Float64(promotion["max_cost"]) && max_residual <= Float64(promotion["max_abs_normalized_residual"])
	end

	function d3_discover_slots(contracts, catalog; discovered_runs = nothing)
		runs = if isnothing(discovered_runs)
			output_root = d3_workspace_path(contracts.config["output_root_workspace_path"])
			isdir(output_root) ? filter(!isnothing, [
				d3_run_identity(path) for path in (joinpath(output_root, name) for name in readdir(output_root)) if isdir(path)
			]) : Any[]
		else
			collect(discovered_runs)
		end
		return map(catalog.slots) do slot
			slot_runs = [run for run in runs if run.case_id == catalog.case_id && run.target_set_id == catalog.target_set_id && run.slot_ghz == slot]
			expected_fingerprint = d3_execution_fingerprint(contracts, catalog, slot)
			satisfying = [
				run for run in slot_runs
				if d3_target_satisfying(run, contracts.target, contracts.conditions, expected_fingerprint)
			]
			ambiguous = length(satisfying) > 1
			failed = count(run -> get(run.status, "state", nothing) == "failed", slot_runs)
			if ambiguous
				(slot_ghz = slot, state = "ambiguous_completed_runs", target_satisfying = true,
					nelder_mead = "ambiguous", approval = "unapproved", reusable = false,
					rerun_blocked = true, run_directory = nothing, failed_attempts = failed)
			elseif length(satisfying) == 1
				run = only(satisfying)
				layout = JSON3.read(read(joinpath(run.directory, "layout_specs.json"), String), Dict{String,Any})
				(slot_ghz = slot, state = "completed", target_satisfying = true,
					nelder_mead = String(get(run.status, "nelder_mead_state", "unknown")),
					approval = String(get(layout, "artifact_approval", "unapproved_exploration")),
					reusable = true, rerun_blocked = true, run_directory = run.directory,
					failed_attempts = failed)
			elseif failed > 0
				(slot_ghz = slot, state = "failed_retryable", target_satisfying = false,
					nelder_mead = "not_available", approval = "unapproved", reusable = false,
					rerun_blocked = false, run_directory = nothing, failed_attempts = failed)
			else
				(slot_ghz = slot, state = "unfinished", target_satisfying = false,
					nelder_mead = "not_run", approval = "unapproved", reusable = false,
					rerun_blocked = false, run_directory = nothing, failed_attempts = 0)
			end
		end
	end

	d3_slot_status = d3_discover_slots(d3_contracts, d3_seed_catalog)
	first_runnable = findfirst(row -> !row.rerun_blocked, d3_slot_status)
	d3_default_slot = isnothing(first_runnable) ? first(d3_seed_catalog.slots) : d3_slot_status[first_runnable].slot_ghz
end

# ╔═╡ 1a7f5502-afad-4918-8d2e-ef8fa809fae2
begin
	rows = [
		"## Slot status", "",
		"| Slot (GHz) | State | Target satisfying | Nelder–Mead | Approval | Reusable | Rerun |",
		"|---:|---|---|---|---|---|---|",
	]
	for row in d3_slot_status
		push!(rows, "| $(row.slot_ghz) | $(row.state) | $(row.target_satisfying) | $(row.nelder_mead) | $(row.approval) | $(row.reusable ? "view-only" : "no") | $(row.rerun_blocked ? "blocked" : "available") |")
	end
	Markdown.parse(join(rows, "\n"))
end

# ╔═╡ b7cf1620-a484-4cb8-9711-c6d6783d4e44
@bind d3_selected_slot Select(d3_seed_catalog.slots; default = d3_default_slot)

# ╔═╡ 80577edb-d4e3-481b-8649-b637324ad624
begin
	function d3_bound(seed, policy)
		lower = max(Float64(seed) - Float64(policy["seed_minus"]), Float64(get(policy, "floor", -Inf)))
		upper = min(Float64(seed) + Float64(policy["seed_plus"]), Float64(get(policy, "ceiling", Inf)))
		lower < Float64(seed) < upper || error("Seed-relative bounds do not contain the selected seed.")
		return lower, upper
	end

	function d3_build_runtime(contracts, catalog, slot_ghz)
		designs = [row for row in catalog.designs if row.slot_target_ghz == Float64(slot_ghz)]
		length(designs) == 1 || error("Selected Slot must map to exactly one typed seed row.")
		seed_design = only(designs)
		source_row = select_d3_source_row(
			catalog.seed_path; case_id = catalog.case_id,
			target_set_id = catalog.target_set_id, slot_target_ghz = slot_ghz,
		)
		String(seed_design.id) == source_row["id"] || error("Typed seed and full source row identities differ.")
		target_values = d3_target_values(contracts.target, slot_ghz)
		isapprox(parse(Float64, source_row["target_bare_filter_ghz"]) * 1e9, target_values["filter_loaded_bare_hz"]; atol = 1.0) || error("CSV filter target disagrees with canonical Design Target.")
		isapprox(parse(Float64, source_row["target_bare_readout_ghz"]) * 1e9, target_values["readout_loaded_bare_hz"]; atol = 1.0) || error("CSV readout target disagrees with canonical Design Target.")
		isapprox(parse(Float64, source_row["notch_target_ghz"]) * 1e9, target_values["notch_hz"]; atol = 1.0) || error("CSV notch target disagrees with canonical Design Target.")
		isapprox(parse(Float64, source_row["predicted_kappa_over_2pi_mhz"]) * 1e6, target_values["filter_loaded_linewidth_hz"]; atol = 1.0) || error("CSV kappa target disagrees with canonical Design Target.")
		isapprox(parse(Float64, source_row["detuning_target_mhz"]) * 1e6, target_values["readout_minus_filter_detuning_hz"]; atol = 1.0) || error("CSV detuning target disagrees with canonical Design Target.")

		seed_values = Dict(id => Float64(getproperty(seed_design, Symbol(id))) for id in D3_VARIABLE_IDS)
		policies = contracts.conditions["variable_bound_policy"]
		variable_records = map(D3_VARIABLE_IDS) do id
			lower, upper = d3_bound(seed_values[id], policies[id])
			Dict("id" => id, "value" => seed_values[id], "unit" => policies[id]["unit"],
				"lower_bound" => lower, "upper_bound" => upper, "status" => "agent_proposed")
		end
		variable_specs = [VariableSpec(Symbol(record["id"]), record["unit"], record["lower_bound"], record["upper_bound"]) for record in variable_records]
		initial_candidate = NamedTuple{Tuple(Symbol.(D3_VARIABLE_IDS))}(Tuple(seed_values[id] for id in D3_VARIABLE_IDS))
		metric_specs = [
			MetricSpec(Symbol(id), target_values[id], contracts.conditions["metric_specs"][id]["scale"], contracts.conditions["metric_specs"][id]["weight"])
			for id in D3_OPTIMIZER_METRIC_IDS
		]

		e = contracts.conditions["evaluator_settings"]
		evaluator_settings = D3SlotEvaluationSettings(
			frequency_step_hz = e["frequency_step_hz"], feedline_length_um = e["feedline_length_um"],
			loaded_bare_half_width_hz = e["loaded_bare_half_width_hz"], loaded_bare_ownership_half_width_hz = e["loaded_bare_ownership_half_width_hz"],
			max_filter_anchor_distance_hz = e["max_filter_anchor_distance_hz"], min_filter_assignment_margin_hz = e["min_filter_assignment_margin_hz"],
			pair_trace_half_width_hz = e["pair_trace_half_width_hz"], pair_fit_half_width_hz = e["pair_fit_half_width_hz"],
			pair_background_inner_half_width_hz = e["pair_background_inner_half_width_hz"], notch_half_width_hz = e["notch_half_width_hz"],
			min_notch_assignment_margin_hz = e["min_notch_assignment_margin_hz"],
			readout_probe_capacitances_fF = e["readout_probe_capacitances_fF"], min_readout_frequency_extrapolation_r2 = e["min_readout_frequency_extrapolation_r2"],
			min_readout_linewidth_extrapolation_r2 = e["min_readout_linewidth_extrapolation_r2"], max_notch_abs_im_z21_ohm = e["max_notch_abs_im_z21_ohm"],
			qubit_local_half_width_hz = e["qubit_local_half_width_hz"], max_qubit_anchor_distance_hz = e["max_qubit_anchor_distance_hz"],
			min_g_extrapolation_r2 = e["min_g_extrapolation_r2"],
			j_bounds_hz = e["j_bounds_hz"], j_seeds_hz = e["j_seeds_hz"], linear_ls_rcond = e["linear_ls_rcond"],
			least_squares_max_nfev = e["least_squares_max_nfev"], least_squares_ftol = e["least_squares_ftol"], least_squares_xtol = e["least_squares_xtol"],
			least_squares_gtol = e["least_squares_gtol"], least_squares_diff_step = e["least_squares_diff_step"],
			min_successful_seed_count = e["min_successful_seed_count"], min_successful_seed_fraction = e["min_successful_seed_fraction"],
			near_optimal_mse_ratio = e["near_optimal_mse_ratio"], near_optimal_mse_absolute_tolerance = e["near_optimal_mse_absolute_tolerance"],
			min_winning_seed_count = e["min_winning_seed_count"], channel_calibration_fit_half_width_hz = e["channel_calibration_fit_half_width_hz"],
			channel_calibration_background_inner_half_width_hz = e["channel_calibration_background_inner_half_width_hz"],
			min_channel_calibration_complex_r2 = e["min_channel_calibration_complex_r2"], min_channel_calibration_abs_r2 = e["min_channel_calibration_abs_r2"],
			max_channel_calibration_phase_rmse_rad = e["max_channel_calibration_phase_rmse_rad"], min_reference_magnitude = e["min_reference_magnitude"],
			min_phase_magnitude = e["min_phase_magnitude"], min_complex_r2 = e["min_complex_r2"], min_abs_r2 = e["min_abs_r2"],
			max_phase_rmse_rad = e["max_phase_rmse_rad"], min_normalized_bound_margin = e["min_normalized_bound_margin"], max_seed_spread_hz = e["max_seed_spread_hz"],
			vector_bg_poles = e["vector_bg_poles"], vector_min_q = e["vector_min_q"], max_vector_rms_error = e["max_vector_rms_error"],
			max_vector_pole_disagreement_hz = e["max_vector_pole_disagreement_hz"], max_pair_pole_center_offset_hz = e["max_pair_pole_center_offset_hz"],
		)
		h = contracts.conditions["hb_settings"]
		hb_settings = D3HBSettings(
			Float64(h["section_length_um"]) * D3_METERS_PER_UM, h["port_resistance_ohm"], h["pump_frequency_hz"], h["pump_current_a"],
			h["n_pump_harmonics"], h["n_modulation_harmonics"], Dict{Symbol,Any}(:nbatches => h["nbatches"], :iterations => h["iterations"], :ftol => h["ftol"]),
		)
		feedline = load_d3_feedline_rlgc(contracts.config)
		require_feedline_port_match(feedline, hb_settings)
		slot_index = only(findall(==(Float64(slot_ghz)), catalog.slots))
		cma = contracts.conditions["optimization"]["cma"]
		nm = contracts.conditions["optimization"]["nelder_mead"]
		promotion = contracts.conditions["optimization"]["promotion"]
		cma_settings = CMASettings(seed = Int(cma["base_seed"]) + slot_index - 1, sigma = cma["sigma"], popsize = cma["popsize"], maxiter = cma["maxiter"], maxfevals = cma["maxfevals"], ftol = cma["ftol"], xtol = cma["xtol"])
		nm_settings = NelderMeadSettings(maxiter = nm["maxiter"], maxfevals = nm["maxfevals"], ftol = nm["ftol"], xtol = nm["xtol"], rejection_carrier_cost = nm["rejection_carrier_cost"], simplex_logit_offset = nm["simplex_logit_offset"], simplex_logit_multiplier = nm["simplex_logit_multiplier"])
		promotion_settings = PromotionSettings(max_cost = promotion["max_cost"], max_abs_normalized_residual = promotion["max_abs_normalized_residual"])

		row_sha = d3_sha256(source_row)
		fingerprint = d3_execution_fingerprint(contracts, catalog, slot_ghz)
		consumed_paths = Dict(
			"target_contract" => contracts.target_path, "optimizer_conditions" => D3_CONDITIONS_PATH,
			"design_config" => D3_CONFIG_PATH, "d3_purcell_common" => joinpath(@__DIR__, "d3_purcell_common.jl"),
			"d3_semantic_hash" => joinpath(@__DIR__, "d3_semantic_hash.jl"),
			"d3_coupled_evaluator" => joinpath(@__DIR__, "d3_coupled_evaluator.jl"),
			"d3_coupled_optimizer" => joinpath(@__DIR__, "d3_coupled_optimizer.jl"),
			"d3_floating_qubit_input_loader" => joinpath(@__DIR__, "d3_floating_qubit_nominal_comparison.jl"),
			"floating_qubit_nominal" => catalog.qubit_input.input_path,
			"notebook07" => @__FILE__, "seed_csv" => catalog.seed_path, "orpen_case_json" => catalog.case_path,
		)
		hash_inventory = [begin
			sha = d3_file_sha256(path)
			Dict(
				"id" => id,
				"path" => relpath(path, D3_WORKSPACE_ROOT),
				"expected_sha256" => sha,
				"observed_sha256" => sha,
			)
		end for (id, path) in sort!(collect(consumed_paths); by = pair -> first(pair))]
		metric_records = [Dict("id" => id, "value" => target_values[id], "unit" => "Hz", "scale" => contracts.conditions["metric_specs"][id]["scale"], "weight" => contracts.conditions["metric_specs"][id]["weight"], "role" => contracts.conditions["metric_specs"][id]["role"], "status" => "derived_from_canonical_target") for id in D3_OPTIMIZER_METRIC_IDS]
		qubit_evidence = floating_qubit_reduction_evidence(
			catalog.qubit_input.model;
			f01_target_hz = catalog.qubit_targets.f01_hz,
			expected_L_J_per_junction_nH = catalog.qubit_targets.L_J_per_junction_nH,
			target_contract_id = contracts.target["target_id"],
			target_contract_sha256 = contracts.target_sha256,
		)
		qubit_evidence["input_sha256"] = catalog.qubit_input.input_sha256
		contract = Dict(
			"manifest_id" => "d3-coupled-optimization-slot-$(replace(string(slot_ghz), "." => "p"))ghz-v1",
			"status" => "agent_proposed", "purpose" => "single_slot_layout_search_exploration",
			"proposal" => Dict("identity" => "Codex contract-bounded implementation agent", "role" => "agent", "proposed_at_utc" => string(now(UTC))),
			"target_contract" => Dict("target_id" => contracts.target["target_id"], "revision" => contracts.target["revision"], "sha256" => contracts.target_sha256, "decision_records" => contracts.target["targets"]),
			"optimizer_conditions" => Dict("conditions_id" => contracts.conditions["conditions_id"], "sha256" => contracts.conditions_sha256, "hash_framing" => SEMANTIC_HASH_FRAMING, "sol_review" => contracts.conditions["sol_review"]),
			"selection" => Dict("case_id" => catalog.case_id, "target_set_id" => catalog.target_set_id, "slot_target_ghz" => Float64(slot_ghz), "source_row" => source_row, "source_row_sha256" => row_sha, "source_csv_sha256" => catalog.csv_sha256),
			"floating_qubit_nominal" => qubit_evidence,
			"derived_metrics" => metric_records, "derived_variables" => variable_records,
			"execution_fingerprint_sha256" => fingerprint, "consumed_files" => hash_inventory,
			"artifact_gate" => contracts.conditions["artifact_gate"], "output_filenames" => sort!(collect(D3_OUTPUT_FILES)),
		)
		payload = Dict("schema_version" => "d3-slot-execution-manifest.v1", "semantic_hash_framing" => SEMANTIC_HASH_FRAMING, "contract" => contract)
		execution_sha = d3_sha256(payload)
		manifest = merge(payload, Dict("execution_sha256" => execution_sha))
		return (
			slot_ghz = Float64(slot_ghz), seed_design = seed_design, source_row = source_row,
			selected_case = catalog.selected_case, feedline = feedline, config = contracts.config,
			variable_records = variable_records, variable_specs = variable_specs,
			initial_candidate = initial_candidate, metric_records = metric_records, metric_specs = metric_specs,
			evaluator_settings = evaluator_settings, hb_settings = hb_settings,
			cma_settings = cma_settings, nm_settings = nm_settings, promotion_settings = promotion_settings,
			initial_seed_evaluation_budget = Int(contracts.conditions["optimization"]["initial_seed_evaluation_budget"]),
			manifest = manifest, execution_sha256 = execution_sha, execution_fingerprint_sha256 = fingerprint,
			hash_inventory = hash_inventory, approval_status = "agent_proposed",
			floating_qubit_input = catalog.qubit_input,
			qubit_targets = catalog.qubit_targets,
		)
	end

	d3_runtime_context = d3_build_runtime(d3_contracts, d3_seed_catalog, d3_selected_slot)
end

# ╔═╡ 5cf81fe5-e47b-4850-a661-b2548f5488d4
begin
	function d3_new_evaluator(runtime; journal_path)
		D3SlotEvaluator(
			runtime.selected_case,
			runtime.seed_design,
			runtime.feedline,
			runtime.hb_settings,
			runtime.evaluator_settings,
			runtime.floating_qubit_input.model,
			runtime.floating_qubit_input.input_sha256,
			floating_qubit_coupling_off_frequency_hz(runtime.floating_qubit_input.model);
			qubit_f01_target_hz = runtime.qubit_targets.f01_hz,
			expected_L_J_per_junction_nH = runtime.qubit_targets.L_J_per_junction_nH,
			qubit_target_contract_id = runtime.manifest["contract"]["target_contract"]["target_id"],
			qubit_target_contract_sha256 = runtime.manifest["contract"]["target_contract"]["sha256"],
			journal_path = journal_path,
		)
	end

	function d3_optimizer_evaluation(record)
		record.status === :rejected && return RejectedEvaluation(record.code, record.reason, record.details)
		record.status === :valid || error("Unsupported physical evaluator status $(record.status).")
		propertynames(record.metrics) == Tuple(Symbol.(D3_EVALUATOR_FIELD_IDS)) || error("Physical evaluator return contract changed.")
		names = Tuple(Symbol.(D3_OPTIMIZER_METRIC_IDS))
		return ValidEvaluation(NamedTuple{names}(Tuple(getproperty(record.metrics, name) for name in names)))
	end

	function evaluate_d3_seed_cost(runtime; evaluate_candidate = nothing)
		runtime.initial_seed_evaluation_budget == 1 || error("Seed-only runtime must evaluate exactly one candidate.")
		candidate_evaluator = if isnothing(evaluate_candidate)
			evaluator = d3_new_evaluator(runtime; journal_path = nothing)
			candidate -> evaluate_d3_slot(evaluator, candidate; capture_traces = false)
		else
			evaluate_candidate
		end
		evaluation_count = 0
		evaluation_count += 1
		record = candidate_evaluator(runtime.initial_candidate)
		evaluation_count == runtime.initial_seed_evaluation_budget || error("Seed-only runtime violated its one-evaluation budget.")
		evaluation = d3_optimizer_evaluation(record)
		return (
			slot_ghz = runtime.slot_ghz, status = record.status, candidate = runtime.initial_candidate,
			evaluation = evaluation,
			cost_breakdown = evaluation isa ValidEvaluation ? cost_breakdown(runtime.metric_specs, evaluation) : nothing,
		)
	end

	function d3_json_ready(value)
		isnothing(value) && return nothing
		value isa AbstractDict && return Dict(String(key) => d3_json_ready(item) for (key, item) in pairs(value))
		value isa NamedTuple && return Dict(String(key) => d3_json_ready(getproperty(value, key)) for key in propertynames(value))
		value isa AbstractVector && return [d3_json_ready(item) for item in value]
		value isa Tuple && return [d3_json_ready(item) for item in value]
		value isa Complex && return Dict("real" => Float64(real(value)), "imag" => Float64(imag(value)))
		value isa Symbol && return String(value)
		value isa AbstractFloat && !isfinite(value) && error("Refusing to persist non-finite evidence.")
		value isa DateTime && return string(value)
		if isstructtype(typeof(value)) && !(value isa AbstractString) && !(value isa Number)
			return Dict(String(name) => d3_json_ready(getfield(value, name)) for name in fieldnames(typeof(value)))
		end
		return value
	end

	function d3_write_json(path, value)
		open(path, "w") do io
			JSON3.write(io, d3_json_ready(value))
			write(io, '\n')
		end
		return path
	end

	function d3_best_record(result)
		valid_records = [record for record in result.history if !isnothing(record.cost)]
		isempty(valid_records) ? nothing : valid_records[argmin(record.cost for record in valid_records)]
	end

	function d3_layout_specs(runtime, result, best_record)
		base = Dict(
			"state" => isnothing(best_record) ? "no_valid_candidate" : "best_valid_candidate",
			"outcome_label" => string(result.promotion.state), "artifact_approval" => "unapproved_exploration",
			"source_seed_id" => String(runtime.seed_design.id), "condition_manifest_sha256" => runtime.execution_sha256,
			"review_state" => runtime.approval_status, "slot_target_ghz" => runtime.slot_ghz,
		)
		isnothing(best_record) && return base
		return merge(base, Dict(
			"candidate_record_id" => best_record.record_id,
			"variables" => [Dict("id" => String(spec.name), "value" => getproperty(best_record.candidate, spec.name), "unit" => spec.unit) for spec in runtime.variable_specs],
			"cost" => best_record.cost, "breakdown" => best_record.breakdown,
		))
	end

	function d3_require_slot_runnable(slot_ghz; discovered_runs = nothing)
		fresh = only(
			row for row in d3_discover_slots(
				d3_contracts,
				d3_seed_catalog;
				discovered_runs = discovered_runs,
			) if row.slot_ghz == Float64(slot_ghz)
		)
		fresh.rerun_blocked && error("Slot $(slot_ghz) GHz already has completed matching evidence or an ambiguity; rerun blocked.")
		return nothing
	end

	function run_d3_slot_optimization(runtime)
		d3_require_slot_runnable(runtime.slot_ghz)
		output_root = d3_workspace_path(runtime.config["output_root_workspace_path"])
		manifest_id = runtime.manifest["contract"]["manifest_id"]
		run_id = Dates.format(now(UTC), dateformat"yyyymmddTHHMMSSsssZ") * "__" * manifest_id * "__" * first(runtime.execution_sha256, 12)
		run_directory = joinpath(output_root, run_id)
		ispath(run_directory) && error("Refusing to overwrite D3 run: $(run_directory)")
		mkpath(run_directory)
		paths = Dict(name => joinpath(run_directory, name) for name in D3_OUTPUT_FILES)
		started_at = now(UTC)
		d3_write_json(paths["condition_manifest.json"], runtime.manifest)
		d3_write_json(paths["config_snapshot.json"], runtime.config)
		d3_write_json(paths["hash_inventory.json"], Dict(
			"execution_sha256" => runtime.execution_sha256,
			"config_snapshot_sha256" => d3_file_sha256(paths["config_snapshot.json"]),
			"files" => runtime.hash_inventory,
		))
		d3_write_json(paths["status.json"], Dict("state" => "running", "slot_target_ghz" => runtime.slot_ghz, "execution_sha256" => runtime.execution_sha256, "execution_fingerprint_sha256" => runtime.execution_fingerprint_sha256, "started_at_utc" => started_at, "artifact_approval" => "unapproved_exploration"))
		try
			evaluator = d3_new_evaluator(runtime; journal_path = paths["evaluations.jsonl"])
			result = optimize_d3(
				candidate -> d3_optimizer_evaluation(evaluate_d3_slot(evaluator, candidate; capture_traces = false)),
				runtime.variable_specs, runtime.metric_specs, runtime.initial_candidate,
				runtime.cma_settings, runtime.nm_settings, runtime.promotion_settings;
				condition_manifest_id = manifest_id, condition_manifest_sha256 = runtime.execution_sha256,
				condition_manifest_approval_status = runtime.approval_status,
			)
			best_record = d3_best_record(result)
			d3_write_json(paths["optimization_result.json"], result)
			d3_write_json(paths["layout_specs.json"], d3_layout_specs(runtime, result, best_record))
			final_capture = isnothing(best_record) ? (state = :no_valid_candidate, record = nothing) : begin
				record = evaluate_d3_slot(evaluator, best_record.candidate; capture_traces = true)
				record.status === :valid || error("Best valid candidate failed final physical reproduction.")
				(state = :captured, record = record)
			end
			d3_write_json(paths["final_diagnostics.json"], merge(
				(analysis_kind = "optimizer_internal_final_reproduction", independent_validation = false),
				final_capture,
			))
			d3_write_json(paths["status.json"], Dict(
				"state" => "completed", "slot_target_ghz" => runtime.slot_ghz,
				"execution_sha256" => runtime.execution_sha256,
				"execution_fingerprint_sha256" => runtime.execution_fingerprint_sha256,
				"started_at_utc" => started_at, "completed_at_utc" => now(UTC),
				"artifact_approval" => "unapproved_exploration", "promotion_state" => result.promotion.state,
				"cma_state" => result.cma.state, "nelder_mead_state" => result.nelder_mead.state,
			))
			Set(readdir(run_directory)) == D3_OUTPUT_FILES || error("Run directory must contain exactly eight declared files.")
			return (slot_ghz = runtime.slot_ghz, run_directory = run_directory, result = result)
		catch exception
			failure = Dict("state" => "failed", "slot_target_ghz" => runtime.slot_ghz, "execution_sha256" => runtime.execution_sha256, "error_type" => string(typeof(exception)), "reason" => sprint(showerror, exception), "artifact_approval" => "unapproved_exploration", "started_at_utc" => started_at, "completed_at_utc" => now(UTC))
			isfile(paths["evaluations.jsonl"]) || open(paths["evaluations.jsonl"], "w") do _ end
			for name in ("optimization_result.json", "final_diagnostics.json", "layout_specs.json")
				isfile(paths[name]) || d3_write_json(paths[name], failure)
			end
			d3_write_json(paths["status.json"], failure)
			Set(readdir(run_directory)) == D3_OUTPUT_FILES || error("Failed run directory must contain exactly eight declared files.")
			rethrow()
		end
	end
end

# ╔═╡ 0a33bd48-c02f-4c12-b4ed-0d31fe1cc6d8
TableOfContents()

# ╔═╡ b144ce59-d130-4d23-a5fe-1e42af2dd7e9
begin
	function d3_preview(runtime)
		qubit = runtime.manifest["contract"]["floating_qubit_nominal"]
		qubit_physics = qubit["physics_diagnostics"]
		rows = [
			"## Selected Slot preview", "",
			"- Slot: **$(runtime.slot_ghz) GHz**",
			"- Seed row: `$(runtime.source_row["id"])`",
			"- Execution manifest: `$(runtime.execution_sha256)`",
			"- Per-Slot state: **agent_proposed**",
			"- Generic Sol review: **$(d3_contracts.conditions["sol_review"]["status"])**",
			"- Floating Coupler pads eliminated: **$(length(qubit["partition"]["floating_labels"]))** by `$(qubit["reduction_method"])`",
			"- Per-junction L_J: **$(qubit["L_J_per_junction_nH"]) nH**; first-order f01: **$(qubit_physics["first_order_transmon_f01_hz"] / 1e9) GHz**",
			"- Readout self-capacitance: `$(qubit["readout_self_capacitance_ownership"])`; reduced diagonal instantiated: **$(qubit["readout_diagonal_instantiated"])**",
			"", "### Derived targets", "", "| Metric | Target | Scale | Weight | Role |", "|---|---:|---:|---:|---|",
		]
		for record in runtime.metric_records
			push!(rows, "| `$(record["id"])` | $(record["value"]) Hz | $(record["scale"]) | $(record["weight"]) | $(record["role"]) |")
		end
		append!(rows, ["", "### Seed-relative variables", "", "| Variable | Seed | Lower | Upper | Unit |", "|---|---:|---:|---:|---|"])
		for record in runtime.variable_records
			push!(rows, "| `$(record["id"])` | $(record["value"]) | $(record["lower_bound"]) | $(record["upper_bound"]) | $(record["unit"]) |")
		end
		return Markdown.parse(join(rows, "\n"))
	end

	function d3_seed_result(result, selected_slot)
		(isnothing(result) || result.slot_ghz != selected_slot) && return md"Click **Evaluate selected seed — no writes** for this Slot."
		result.status === :rejected && return md"**Seed physically rejected:** `$(result.evaluation.code)` — $(result.evaluation.reason)"
		rows = ["## Seed evaluation", "", "Total cost: **$(result.cost_breakdown.total)**", "", "| Metric | Observed | Target | Residual | Contribution |", "|---|---:|---:|---:|---:|"]
		for metric in result.cost_breakdown.metrics
			push!(rows, "| `$(metric.name)` | $(metric.observed) | $(metric.target) | $(metric.normalized_residual) | $(metric.contribution) |")
		end
		Markdown.parse(join(rows, "\n"))
	end

	function d3_run_result(result, selected_slot)
		(isnothing(result) || result.slot_ghz != selected_slot) && return md"Click **Run selected Slot optimization** only after reviewing the preview."
		Markdown.parse("""
		## Optimization result

		Run directory: `$(result.run_directory)`<br>
		CMA-ES: **$(result.result.cma.state)**<br>
		Nelder–Mead: **$(result.result.nelder_mead.state)**<br>
		Promotion: **$(result.result.promotion.state)**
		""")
	end

	if !isdefined(@__MODULE__, :D3_REQUEST_COUNTS)
		const D3_REQUEST_COUNTS = Dict(:seed => 0, :run => 0)
		const D3_LAST_SEED_RESULT = Ref{Any}(nothing)
		const D3_LAST_RUN_RESULT = Ref{Any}(nothing)
	end
	function d3_take_request!(kind, click, slot)
		count = click isa Integer ? click : 0
		count > get(D3_REQUEST_COUNTS, kind, 0) || return nothing
		D3_REQUEST_COUNTS[kind] = count
		return (kind = kind, click = count, slot_ghz = Float64(slot))
	end
end

# ╔═╡ c255df6a-e241-4e34-b60f-2f53bf3ee8fa
d3_preview(d3_runtime_context)

# ╔═╡ 5bee68f3-7bda-47cd-4f98-b8ec48c77183
md"""
## Explicit execution

The first button runs one real `Simulation → evaluator → cost` path and writes
nothing. The second writes a new exact-eight-file run only for an unfinished or
failed Slot. A selector change cannot replay an old click token.
"""

# ╔═╡ 6cff7904-8ceb-48de-50a9-c9fd59d88294
@bind d3_seed_evaluation_click Button("Evaluate selected seed — no writes")

# ╔═╡ 7d008a15-9dfc-49ef-61ba-da0e6ae993a5
begin
	request = d3_take_request!(:seed, d3_seed_evaluation_click, d3_selected_slot)
	!isnothing(request) && (D3_LAST_SEED_RESULT[] = evaluate_d3_seed_cost(d3_runtime_context))
	D3_LAST_SEED_RESULT[]
end

# ╔═╡ 8e119b26-ae0d-4af0-72cb-eb1f7bfa04b6
d3_seed_result(D3_LAST_SEED_RESULT[], d3_selected_slot)

# ╔═╡ 9f22ac37-bf1e-4b01-83dc-fc208c0b15c7
@bind d3_exploration_click Button("Run selected Slot optimization")

# ╔═╡ a033bd48-c02f-4c12-94ed-0d319d1c26d8
begin
	request = d3_take_request!(:run, d3_exploration_click, d3_selected_slot)
	!isnothing(request) && (D3_LAST_RUN_RESULT[] = run_d3_slot_optimization(d3_runtime_context))
	D3_LAST_RUN_RESULT[]
end

# ╔═╡ b144ce59-d130-4d23-95fe-1e429e2d37e9
d3_run_result(D3_LAST_RUN_RESULT[], d3_selected_slot)

# ╔═╡ Cell order:
# ╟─a5df7804-e15d-4f5a-b319-4df0eabff5c4
# ╠═956db29c-afb0-471c-93f7-fc434f660064
# ╠═fc66b3bc-83ed-4816-b1fe-d5ca8132bdd5
# ╠═7b915116-d455-4cb3-bb06-1577aee8f7cd
# ╠═18ae5d34-a03c-4557-a80d-bdb458f04fa9
# ╟─1a7f5502-afad-4918-8d2e-ef8fa809fae2
# ╠═b7cf1620-a484-4cb8-9711-c6d6783d4e44
# ╠═80577edb-d4e3-481b-8649-b637324ad624
# ╠═5cf81fe5-e47b-4850-a661-b2548f5488d4
# ╠═0a33bd48-c02f-4c12-b4ed-0d31fe1cc6d8
# ╠═b144ce59-d130-4d23-a5fe-1e42af2dd7e9
# ╟─c255df6a-e241-4e34-b60f-2f53bf3ee8fa
# ╟─5bee68f3-7bda-47cd-4f98-b8ec48c77183
# ╠═6cff7904-8ceb-48de-50a9-c9fd59d88294
# ╠═7d008a15-9dfc-49ef-61ba-da0e6ae993a5
# ╟─8e119b26-ae0d-4af0-72cb-eb1f7bfa04b6
# ╠═9f22ac37-bf1e-4b01-83dc-fc208c0b15c7
# ╠═a033bd48-c02f-4c12-94ed-0d319d1c26d8
# ╟─b144ce59-d130-4d23-95fe-1e429e2d37e9
