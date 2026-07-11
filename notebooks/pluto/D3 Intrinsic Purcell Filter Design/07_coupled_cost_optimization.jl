### A Pluto.jl notebook ###
# v1.0.2

#> [frontmatter]
#> title = "07 D3 Coupled Cost Optimization"
#> tags = ["pluto", "d3", "purcell-filter", "optimization", "human-decision"]
#> description = "Hash-bound D3 physical evaluation and CMA-ES to Nelder-Mead exploration workflow."

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
					Base.PkgId(
						Base.UUID("6e696c72-6542-2067-7265-42206c756150"),
						"AbstractPlutoDingetjes",
					),
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
	include(joinpath(@__DIR__, "..", "includes", "hb_example_helpers.jl"))
	zero_mode_s = HBExampleHelpers.zero_mode_s
	include(joinpath(@__DIR__, "d3_purcell_common.jl"))
	include(joinpath(@__DIR__, "d3_coupled_evaluator.jl"))
	include(joinpath(@__DIR__, "d3_coupled_optimizer.jl"))
	using .D3CoupledOptimizer
end

# ╔═╡ a5df7804-e15d-4f5a-b319-4df0eabff5c4
md"""
# 07 D3 Coupled Cost Optimization

This notebook is the sole review and explicit run surface for the real D3
single-slot evaluator and bounded CMA-ES → Nelder-Mead workflow. Opening it
validates the complete condition manifest and every consumed source hash, but
does **not** run HB, create a run directory, or write an artifact.

Review the canonical [D3 Design Target](https://github.com/arfiligol/SCQ_Design/blob/main/docs/design-targets/d3-intrinsic-interferometric-purcell-filter.qmd),
[Readout-Filter S21 J Fit](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/readout/readout-filter-s21-j-fit.qmd),
[Auditable Scientific Optimization](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/numerical-methods/auditable-scientific-optimization.qmd),
and [Multiconductor RLGC Matrices](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/transmission-lines/multiconductor-rlgc-matrix-semantics.qmd)
before approving execution.
"""

# ╔═╡ fc66b3bc-83ed-4816-b1fe-d5ca8132bdd5
begin
	const D3_MANIFEST_SCHEMA = "d3-condition-manifest.v1"
	const D3_MANIFEST_PATH = joinpath(@__DIR__, "d3_condition_manifest.json")
	const D3_WORKSPACE_ROOT = normpath(joinpath(@__DIR__, "..", "..", "..", ".."))
	const D3_TOP_LEVEL_KEYS = Set([
		"schema_version",
		"contract",
		"contract_sha256",
		"sol_review",
		"human_review",
	])
	const D3_REVIEW_KEYS = Set([
		"status",
		"reviewer_role",
		"reviewer_identity",
		"reviewed_at_utc",
		"rationale",
		"evidence",
		"approved_contract_sha256",
	])
	const D3_CONTRACT_KEYS = Set([
		"manifest_id", "proposal", "purpose", "status", "governance", "scope",
		"evidence_catalog", "design_selection", "variables", "evaluator_settings",
		"hb_settings", "metric_contract", "optimization", "feedline", "input_artifacts",
		"closure_conditions", "outputs", "consumed_files", "conflicts",
	])
	const D3_CONSUMED_FILE_IDS = [
		"d3_design_config", "d3_purcell_common", "d3_coupled_evaluator",
		"d3_coupled_optimizer", "notebook07", "seed_csv", "orpen_case_json",
	]
	const D3_OUTPUT_IDS = [
		"output_root", "status_path", "condition_manifest_snapshot_path", "config_snapshot_path",
		"hash_inventory_path", "evaluation_journal_path", "optimization_result_path",
		"layout_specs_path", "final_diagnostics_path",
	]

	function d3_require_exact_keys(value, expected, label)
		value isa AbstractDict || error("$(label) must be a JSON object.")
		actual = Set(String.(keys(value)))
		actual == expected || error(
			"$(label) keys must be exactly $(sort!(collect(expected))); received $(sort!(collect(actual))).",
		)
		return nothing
	end

	function d3_canonical_json(value)
		if value isa AbstractDict
			keys_in_order = sort!(String.(collect(keys(value))))
			return "{" * join(
				(JSON3.write(key) * ":" * d3_canonical_json(value[key]) for key in keys_in_order),
				",",
			) * "}"
		elseif value isa AbstractVector
			return "[" * join((d3_canonical_json(item) for item in value), ",") * "]"
		elseif value isa AbstractFloat
			isfinite(value) || error("Canonical JSON forbids non-finite numbers.")
			encoded = JSON3.write(value)
			occursin('e', encoded) || return encoded
			mantissa, exponent = split(encoded, 'e'; limit = 2)
			endswith(mantissa, ".0") && (mantissa = first(mantissa, length(mantissa) - 2))
			sign = startswith(exponent, '-') ? "-" : "+"
			digits = startswith(exponent, "-") || startswith(exponent, "+") ? exponent[2:end] : exponent
			return mantissa * "e" * sign * lpad(digits, 2, '0')
		end
		return JSON3.write(value)
	end

	d3_sha256_hex(bytes) = bytes2hex(SHA.sha256(bytes))
	d3_file_sha256(path) = open(path, "r") do io
		bytes2hex(SHA.sha256(io))
	end

	function d3_workspace_path(relative_path)
		path = String(relative_path)
		isabspath(path) && error("Consumed paths must be workspace-relative: $(path)")
		resolved = normpath(joinpath(D3_WORKSPACE_ROOT, split(path, '/')...))
		relative = relpath(resolved, D3_WORKSPACE_ROOT)
		relative_components = splitpath(relative)
		starts_with_workspace = !isabspath(relative) &&
			(isempty(relative_components) || first(relative_components) != "..")
		starts_with_workspace || error("Consumed path escapes the workspace: $(path)")
		return resolved
	end

	function d3_validate_review_block(review, role, allowed_states)
		d3_require_exact_keys(review, D3_REVIEW_KEYS, "$(role) review")
		status = String(review["status"])
		status in allowed_states || error("Unsupported $(role) review status $(repr(status)).")
		reviewer_role = review["reviewer_role"]
		reviewer_role isa AbstractString && !isempty(strip(reviewer_role)) ||
			error("$(role) reviewer_role must be non-empty.")
		return status
	end

	function d3_validate_manifest()
		isfile(D3_MANIFEST_PATH) || error("Missing D3 condition manifest: $(D3_MANIFEST_PATH)")
		manifest = JSON3.read(read(D3_MANIFEST_PATH, String), Dict{String,Any})
		d3_require_exact_keys(manifest, D3_TOP_LEVEL_KEYS, "D3 condition manifest")
		manifest["schema_version"] == D3_MANIFEST_SCHEMA || error(
			"D3 condition manifest schema must be $(D3_MANIFEST_SCHEMA).",
		)
		contract = manifest["contract"]
		d3_require_exact_keys(contract, D3_CONTRACT_KEYS, "D3 condition contract")
		canonical_payload = Dict(
			"schema_version" => manifest["schema_version"],
			"contract" => contract,
		)
		observed_contract_sha256 = d3_sha256_hex(codeunits(d3_canonical_json(canonical_payload)))
		expected_contract_sha256 = String(manifest["contract_sha256"])
		observed_contract_sha256 == expected_contract_sha256 || error(
			"D3 canonical contract SHA-256 mismatch: expected $(expected_contract_sha256), observed $(observed_contract_sha256).",
		)

		sol_status = d3_validate_review_block(manifest["sol_review"], "Sol", ("pending", "sol_reviewed"))
		human_status = d3_validate_review_block(manifest["human_review"], "Human", ("awaiting", "human_approved"))
		for (role, review, pending_state) in (
			("Sol", manifest["sol_review"], "pending"),
			("Human", manifest["human_review"], "awaiting"),
		)
			if review["status"] == pending_state
				all(isnothing(review[key]) for key in (
					"reviewer_identity",
					"reviewed_at_utc",
					"rationale",
					"evidence",
					"approved_contract_sha256",
				)) || error("Pending $(role) review must not contain approval evidence.")
			else
				all(!isnothing(review[key]) for key in (
					"reviewer_identity",
					"reviewed_at_utc",
					"rationale",
					"evidence",
					"approved_contract_sha256",
				)) || error("Completed $(role) review must contain identity, date, rationale, evidence, and hash.")
				review["approved_contract_sha256"] == expected_contract_sha256 || error(
					"$(role) review does not approve the current contract SHA-256.",
				)
			end
		end
		human_status == "human_approved" && sol_status != "sol_reviewed" && error(
			"Human approval requires a Sol-reviewed current contract.",
		)
		approval_status = human_status == "human_approved" ? "human_approved" :
			sol_status == "sol_reviewed" ? "sol_reviewed" : "agent_proposed"

		consumed_files = contract["consumed_files"]
		consumed_files isa AbstractVector && length(consumed_files) == 7 || error(
			"D3 contract must declare exactly seven consumed files.",
		)
		String[item["id"] for item in consumed_files] == D3_CONSUMED_FILE_IDS || error(
			"D3 consumed-file ids/order must be exactly $(D3_CONSUMED_FILE_IDS).",
		)
		hash_inventory = map(consumed_files) do item
			expected = String(item["value"])
			occursin(r"^[0-9a-f]{64}$", expected) || error(
				"Consumed file $(item["id"]) has an invalid SHA-256.",
			)
			path = d3_workspace_path(item["path"])
			isfile(path) || error("Missing consumed file $(item["id"]): $(path)")
			observed = d3_file_sha256(path)
			observed == expected || error(
				"Consumed file $(item["id"]) SHA-256 mismatch: expected $(expected), observed $(observed).",
			)
			(id = String(item["id"]), path = path, expected_sha256 = expected, observed_sha256 = observed)
		end
		output_ids = String[item["id"] for item in contract["outputs"]]
		output_ids == D3_OUTPUT_IDS || error("D3 output ids/order must be exactly $(D3_OUTPUT_IDS).")
		output_names = String[item["value"] for item in contract["outputs"][2:end]]
		length(unique(output_names)) == 8 || error("D3 run-relative output filenames must be unique.")
		input_artifacts = contract["input_artifacts"]
		eligibility_records = [item for item in input_artifacts if haskey(item, "promotion_eligible")]
		!isempty(eligibility_records) || error("D3 input artifacts must declare promotion eligibility.")
		promotion_eligible = all(Bool(item["promotion_eligible"]) for item in eligibility_records)
		approval_status == "human_approved" && !promotion_eligible && error(
			"Human approval is invalid while the declared LC-only artifact is promotion-ineligible.",
		)
		return (
			manifest = manifest,
			contract = contract,
			canonical_contract_sha256 = observed_contract_sha256,
			approval_status = approval_status,
			promotion_eligible = promotion_eligible,
			hash_inventory = hash_inventory,
		)
	end

	d3_manifest_context = d3_validate_manifest()
end

# ╔═╡ 80577edb-d4e3-481b-8649-b637324ad624
begin
	const D3_VARIABLE_IDS = [
		"lc_um",
		"lp_short_um",
		"lr_short_um",
		"lp_open_um",
		"lr_open_um",
		"filter_to_line_capacitance_fF",
	]
	const D3_EVALUATOR_FIELD_IDS = [
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
	]
	const D3_OPTIMIZER_METRIC_IDS = [
		"filter_loaded_bare_hz",
		"readout_loaded_bare_hz",
		"notch_hz",
		"filter_loaded_linewidth_hz",
		"j_hz",
		"readout_minus_filter_detuning_hz",
	]

	function d3_records_by_id(records, expected_ids, label)
		records isa AbstractVector || error("$(label) must be an array.")
		ids = String[item["id"] for item in records]
		ids == expected_ids || error("$(label) ids/order must be exactly $(expected_ids); received $(ids).")
		length(unique(ids)) == length(ids) || error("$(label) ids must be unique.")
		evidence_catalog_ids = Set(String(item["id"]) for item in d3_manifest_context.contract["evidence_catalog"])
		for item in records
			for key in ("id", "value", "unit", "rationale", "evidence", "status")
				haskey(item, key) || error("$(label) item $(item["id"]) is missing $(key).")
			end
			item["evidence"] isa AbstractVector && !isempty(item["evidence"]) || error(
				"$(label) item $(item["id"]) requires evidence.",
			)
			String(item["status"]) == "agent_proposed" || error(
				"$(label) item $(item["id"]) must retain agent_proposed condition status; reviews live in the review blocks.",
			)
			!isempty(strip(String(item["rationale"]))) || error("$(label) item $(item["id"]) requires a rationale.")
			all(String(reference) in evidence_catalog_ids for reference in item["evidence"]) || error(
				"$(label) item $(item["id"]) references unknown evidence.",
			)
		end
		return Dict(String(item["id"]) => item for item in records)
	end

	d3_value(records, id) = records[id]["value"]

	function d3_require_equal(actual, expected, label)
		equal = if actual isa Real && expected isa Real
			Float64(actual) == Float64(expected)
		elseif actual isa Symbol && expected isa AbstractString
			String(actual) == expected
		elseif actual isa AbstractString && expected isa Symbol
			actual == String(expected)
		else
			actual == expected
		end
		equal || error("$(label) must equal manifest value $(repr(expected)); observed $(repr(actual)).")
		return nothing
	end

	function d3_build_runtime(manifest_context)
		contract = manifest_context.contract
		variables_by_id = d3_records_by_id(contract["variables"], D3_VARIABLE_IDS, "variables")
		evaluator_ids = [
			"frequency_step_hz", "feedline_length_um", "loaded_bare_half_width_hz",
			"loaded_bare_ownership_half_width_hz", "max_filter_anchor_distance_hz",
			"min_filter_assignment_margin_hz", "pair_trace_half_width_hz",
			"pair_fit_half_width_hz", "pair_background_inner_half_width_hz",
			"notch_half_width_hz", "readout_probe_capacitances_fF",
			"min_readout_frequency_extrapolation_r2", "min_readout_linewidth_extrapolation_r2",
			"max_notch_abs_im_z21_ohm", "j_bounds_hz", "j_seeds_hz", "linear_ls_rcond",
			"least_squares_max_nfev", "least_squares_ftol", "least_squares_xtol",
			"least_squares_gtol", "least_squares_diff_step", "min_successful_seed_count",
			"min_successful_seed_fraction", "near_optimal_mse_ratio",
			"near_optimal_mse_absolute_tolerance", "min_winning_seed_count",
			"channel_calibration_fit_half_width_hz",
			"channel_calibration_background_inner_half_width_hz",
			"min_channel_calibration_complex_r2", "min_channel_calibration_abs_r2",
			"max_channel_calibration_phase_rmse_rad", "min_reference_magnitude",
			"min_phase_magnitude", "min_complex_r2", "min_abs_r2", "max_phase_rmse_rad",
			"min_normalized_bound_margin", "max_seed_spread_hz", "vector_bg_poles",
			"vector_min_q", "max_vector_rms_error", "max_vector_pole_disagreement_hz",
			"max_pair_pole_center_offset_hz",
		]
		evaluator_by_id = d3_records_by_id(contract["evaluator_settings"], evaluator_ids, "evaluator_settings")
		hb_ids = [
			"section_length_um", "port_resistance_ohm", "pump_frequency_hz", "pump_current_a",
			"n_pump_harmonics", "n_modulation_harmonics", "nbatches", "iterations", "ftol",
		]
		hb_by_id = d3_records_by_id(contract["hb_settings"], hb_ids, "hb_settings")

		metric_contract = contract["metric_contract"]
		String.(metric_contract["evaluator_return_fields"]) == D3_EVALUATOR_FIELD_IDS || error(
			"Evaluator return-field contract does not match the physical evaluator.",
		)
		String.(metric_contract["optimizer_metric_fields"]) == D3_OPTIMIZER_METRIC_IDS || error(
			"Optimizer metric adapter must select exactly six declared fields.",
		)
		metric_by_id = d3_records_by_id(metric_contract["metric_specs"], D3_OPTIMIZER_METRIC_IDS, "metric_specs")
		all(String(metric_by_id[id]["evaluator_field"]) == id for id in D3_OPTIMIZER_METRIC_IDS) || error(
			"Every optimizer metric must name its identically named evaluator field.",
		)

		optimization = contract["optimization"]
		initial_seed_by_id = d3_records_by_id(
			optimization["initial_seed"],
			["evaluation_budget"],
			"optimization.initial_seed",
		)
		d3_require_equal(d3_value(initial_seed_by_id, "evaluation_budget"), 1, "initial-seed evaluation budget")
		cma_ids = ["seed", "sigma", "popsize", "maxiter", "maxfevals", "ftol", "xtol"]
		nm_ids = [
			"maxiter",
			"maxfevals",
			"ftol",
			"xtol",
			"rejection_carrier_cost",
			"simplex_logit_offset",
			"simplex_logit_multiplier",
		]
		promotion_ids = ["max_cost", "max_abs_normalized_residual", "required_review_state", "required_local_stage"]
		cma_by_id = d3_records_by_id(optimization["cma"], cma_ids, "optimization.cma")
		nm_by_id = d3_records_by_id(optimization["nelder_mead"], nm_ids, "optimization.nelder_mead")
		promotion_by_id = d3_records_by_id(optimization["promotion"], promotion_ids, "optimization.promotion")
		d3_require_equal(d3_value(promotion_by_id, "required_review_state"), "human_approved", "required_review_state")
		d3_require_equal(d3_value(promotion_by_id, "required_local_stage"), "converged", "required_local_stage")

		variable_specs = [
			VariableSpec(
				Symbol(id),
				String(variables_by_id[id]["unit"]),
				variables_by_id[id]["lower_bound"],
				variables_by_id[id]["upper_bound"],
			) for id in D3_VARIABLE_IDS
		]
		initial_candidate = NamedTuple{Tuple(Symbol.(D3_VARIABLE_IDS))}(
			Tuple(Float64(d3_value(variables_by_id, id)) for id in D3_VARIABLE_IDS),
		)
		metric_specs = [
			MetricSpec(
				Symbol(id),
				d3_value(metric_by_id, id),
				metric_by_id[id]["scale"],
				metric_by_id[id]["weight"],
			) for id in D3_OPTIMIZER_METRIC_IDS
		]
		evaluator_settings = D3SlotEvaluationSettings(
			frequency_step_hz = d3_value(evaluator_by_id, "frequency_step_hz"),
			feedline_length_um = d3_value(evaluator_by_id, "feedline_length_um"),
			loaded_bare_half_width_hz = d3_value(evaluator_by_id, "loaded_bare_half_width_hz"),
			loaded_bare_ownership_half_width_hz = d3_value(evaluator_by_id, "loaded_bare_ownership_half_width_hz"),
			max_filter_anchor_distance_hz = d3_value(evaluator_by_id, "max_filter_anchor_distance_hz"),
			min_filter_assignment_margin_hz = d3_value(evaluator_by_id, "min_filter_assignment_margin_hz"),
			pair_trace_half_width_hz = d3_value(evaluator_by_id, "pair_trace_half_width_hz"),
			pair_fit_half_width_hz = d3_value(evaluator_by_id, "pair_fit_half_width_hz"),
			pair_background_inner_half_width_hz = d3_value(evaluator_by_id, "pair_background_inner_half_width_hz"),
			notch_half_width_hz = d3_value(evaluator_by_id, "notch_half_width_hz"),
			readout_probe_capacitances_fF = d3_value(evaluator_by_id, "readout_probe_capacitances_fF"),
			min_readout_frequency_extrapolation_r2 = d3_value(evaluator_by_id, "min_readout_frequency_extrapolation_r2"),
			min_readout_linewidth_extrapolation_r2 = d3_value(evaluator_by_id, "min_readout_linewidth_extrapolation_r2"),
			max_notch_abs_im_z21_ohm = d3_value(evaluator_by_id, "max_notch_abs_im_z21_ohm"),
			j_bounds_hz = d3_value(evaluator_by_id, "j_bounds_hz"),
			j_seeds_hz = d3_value(evaluator_by_id, "j_seeds_hz"),
			linear_ls_rcond = d3_value(evaluator_by_id, "linear_ls_rcond"),
			least_squares_max_nfev = d3_value(evaluator_by_id, "least_squares_max_nfev"),
			least_squares_ftol = d3_value(evaluator_by_id, "least_squares_ftol"),
			least_squares_xtol = d3_value(evaluator_by_id, "least_squares_xtol"),
			least_squares_gtol = d3_value(evaluator_by_id, "least_squares_gtol"),
			least_squares_diff_step = d3_value(evaluator_by_id, "least_squares_diff_step"),
			min_successful_seed_count = d3_value(evaluator_by_id, "min_successful_seed_count"),
			min_successful_seed_fraction = d3_value(evaluator_by_id, "min_successful_seed_fraction"),
			near_optimal_mse_ratio = d3_value(evaluator_by_id, "near_optimal_mse_ratio"),
			near_optimal_mse_absolute_tolerance = d3_value(evaluator_by_id, "near_optimal_mse_absolute_tolerance"),
			min_winning_seed_count = d3_value(evaluator_by_id, "min_winning_seed_count"),
			channel_calibration_fit_half_width_hz = d3_value(evaluator_by_id, "channel_calibration_fit_half_width_hz"),
			channel_calibration_background_inner_half_width_hz = d3_value(evaluator_by_id, "channel_calibration_background_inner_half_width_hz"),
			min_channel_calibration_complex_r2 = d3_value(evaluator_by_id, "min_channel_calibration_complex_r2"),
			min_channel_calibration_abs_r2 = d3_value(evaluator_by_id, "min_channel_calibration_abs_r2"),
			max_channel_calibration_phase_rmse_rad = d3_value(evaluator_by_id, "max_channel_calibration_phase_rmse_rad"),
			min_reference_magnitude = d3_value(evaluator_by_id, "min_reference_magnitude"),
			min_phase_magnitude = d3_value(evaluator_by_id, "min_phase_magnitude"),
			min_complex_r2 = d3_value(evaluator_by_id, "min_complex_r2"),
			min_abs_r2 = d3_value(evaluator_by_id, "min_abs_r2"),
			max_phase_rmse_rad = d3_value(evaluator_by_id, "max_phase_rmse_rad"),
			min_normalized_bound_margin = d3_value(evaluator_by_id, "min_normalized_bound_margin"),
			max_seed_spread_hz = d3_value(evaluator_by_id, "max_seed_spread_hz"),
			vector_bg_poles = d3_value(evaluator_by_id, "vector_bg_poles"),
			vector_min_q = d3_value(evaluator_by_id, "vector_min_q"),
			max_vector_rms_error = d3_value(evaluator_by_id, "max_vector_rms_error"),
			max_vector_pole_disagreement_hz = d3_value(evaluator_by_id, "max_vector_pole_disagreement_hz"),
			max_pair_pole_center_offset_hz = d3_value(evaluator_by_id, "max_pair_pole_center_offset_hz"),
		)
		hb_settings = D3HBSettings(
			Float64(d3_value(hb_by_id, "section_length_um")) * D3_METERS_PER_UM,
			d3_value(hb_by_id, "port_resistance_ohm"),
			d3_value(hb_by_id, "pump_frequency_hz"),
			d3_value(hb_by_id, "pump_current_a"),
			d3_value(hb_by_id, "n_pump_harmonics"),
			d3_value(hb_by_id, "n_modulation_harmonics"),
			Dict{Symbol,Any}(
				:nbatches => d3_value(hb_by_id, "nbatches"),
				:iterations => d3_value(hb_by_id, "iterations"),
				:ftol => d3_value(hb_by_id, "ftol"),
			),
		)
		cma_settings = CMASettings(
			seed = d3_value(cma_by_id, "seed"), sigma = d3_value(cma_by_id, "sigma"),
			popsize = d3_value(cma_by_id, "popsize"), maxiter = d3_value(cma_by_id, "maxiter"),
			maxfevals = d3_value(cma_by_id, "maxfevals"), ftol = d3_value(cma_by_id, "ftol"),
			xtol = d3_value(cma_by_id, "xtol"),
		)
		nm_settings = NelderMeadSettings(
			maxiter = d3_value(nm_by_id, "maxiter"), maxfevals = d3_value(nm_by_id, "maxfevals"),
			ftol = d3_value(nm_by_id, "ftol"), xtol = d3_value(nm_by_id, "xtol"),
			rejection_carrier_cost = d3_value(nm_by_id, "rejection_carrier_cost"),
			simplex_logit_offset = d3_value(nm_by_id, "simplex_logit_offset"),
			simplex_logit_multiplier = d3_value(nm_by_id, "simplex_logit_multiplier"),
		)
		promotion_settings = PromotionSettings(
			max_cost = d3_value(promotion_by_id, "max_cost"),
			max_abs_normalized_residual = d3_value(promotion_by_id, "max_abs_normalized_residual"),
		)

		input_by_id = d3_records_by_id(contract["input_artifacts"], ["optimizer_seed_csv", "orpen_height7_lc_matrix_case"], "input_artifacts")
		seed_path = d3_workspace_path(input_by_id["optimizer_seed_csv"]["path"])
		case_path = d3_workspace_path(input_by_id["orpen_height7_lc_matrix_case"]["path"])
		source_row = contract["design_selection"]["source_row"]["value"]
		case_id = String(contract["scope"]["selected_case_id"])
		designs = read_design_csv(seed_path; case_id = case_id)
		matching_designs = [row for row in designs if String(row.id) == String(source_row["row_id"])]
		length(matching_designs) == 1 || error("The manifest seed row must exist exactly once in the hash-bound CSV.")
		seed_design = only(matching_designs)
		for name in (:case_id, :target_set_id, :slot_target_ghz, :notch_target_ghz, :lr_open_um,
			:lr_short_um, :lc_um, :lp_short_um, :lp_open_um, :lr_total_um, :lp_total_um,
			:notch_length_um, :filter_to_line_capacitance_fF)
			d3_require_equal(getproperty(seed_design, name), source_row[String(name)], "seed row $(name)")
		end
		cases = load_orpen_cases(case_path)
		matching_cases = [case for case in cases if case.id == Symbol(case_id)]
		length(matching_cases) == 1 || error("The manifest OrPen case must exist exactly once.")
		selected_case = only(matching_cases)

		config = load_d3_design_config()
		d3_require_equal(config["selected_case_id"], case_id, "config selected_case_id")
		d3_require_equal(config["slot_targets_ghz"], contract["design_selection"]["configured_slot_grid"]["value"], "configured slot grid")
		feedline = load_d3_feedline_rlgc(config)
		feedline_value = contract["feedline"]["value"]
		for (actual, key) in (
			(feedline.source, "source"), (feedline.extraction_frequency_hz, "extraction_frequency_hz"),
			(feedline.l_per_m_h, "l_per_m_h"), (feedline.c_per_m_f, "c_per_m_f"),
			(feedline.target_impedance_ohm, "target_impedance_ohm"),
			(feedline.zo_ohm, "extracted_lc_impedance_ohm"),
			(feedline.max_abs_impedance_error_ohm, "max_abs_impedance_error_ohm"),
		)
			d3_require_equal(actual, feedline_value[key], "feedline $(key)")
		end
		d3_require_equal(feedline.r_per_m_ohm, feedline_value["r_per_m_ohm"]["runtime_value"], "feedline assumed R")
		d3_require_equal(feedline.g_per_m_s, feedline_value["g_per_m_s"]["runtime_value"], "feedline assumed G")

		return (
			manifest_context = manifest_context, variables_by_id = variables_by_id,
			evaluator_by_id = evaluator_by_id, hb_by_id = hb_by_id, metric_by_id = metric_by_id,
			variable_specs = variable_specs, initial_candidate = initial_candidate,
			metric_specs = metric_specs, evaluator_settings = evaluator_settings,
			hb_settings = hb_settings, cma_settings = cma_settings, nm_settings = nm_settings,
			promotion_settings = promotion_settings, selected_case = selected_case,
			seed_design = seed_design, feedline = feedline, config = config,
		)
	end

	d3_runtime_context = d3_build_runtime(d3_manifest_context)
end

# ╔═╡ 5cf81fe5-e47b-4850-a661-b2548f5488d4
begin
	function d3_new_evaluator(runtime; journal_path)
		return D3SlotEvaluator(
			runtime.selected_case,
			runtime.seed_design,
			runtime.feedline,
			runtime.hb_settings,
			runtime.evaluator_settings;
			journal_path = journal_path,
		)
	end

	function d3_optimizer_evaluation(record, runtime)
		if record.status === :rejected
			return RejectedEvaluation(record.code, record.reason, record.details)
		end
		record.status === :valid || error("Unsupported physical evaluator status $(record.status).")
		propertynames(record.metrics) == Tuple(Symbol.(D3_EVALUATOR_FIELD_IDS)) || error(
			"Physical evaluator must return the exact ten-field manifest contract.",
		)
		names = Tuple(Symbol.(D3_OPTIMIZER_METRIC_IDS))
		selected = NamedTuple{names}(Tuple(getproperty(record.metrics, name) for name in names))
		propertynames(selected) == names || error("D3 optimizer adapter did not select exactly six fields.")
		return ValidEvaluation(selected)
	end

	"""Run one real seed simulation and cost calculation without invoking an optimizer or writing files."""
	function evaluate_d3_seed_cost()
		runtime = d3_runtime_context
		evaluator = d3_new_evaluator(runtime; journal_path = nothing)
		record = evaluate_d3_slot(evaluator, runtime.initial_candidate; capture_traces = false)
		evaluation = d3_optimizer_evaluation(record, runtime)
		breakdown = evaluation isa ValidEvaluation ? cost_breakdown(runtime.metric_specs, evaluation) : nothing
		return (
			status = record.status,
			approval_status = runtime.manifest_context.approval_status,
			contract_sha256 = runtime.manifest_context.canonical_contract_sha256,
			candidate = runtime.initial_candidate,
			evaluation = evaluation,
			cost_breakdown = breakdown,
			physical_record = record,
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
		value isa AbstractFloat && !isfinite(value) && error("Refusing to persist non-finite numeric evidence.")
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
		isempty(valid_records) && return nothing
		return valid_records[argmin(record.cost for record in valid_records)]
	end

	function d3_layout_specs(runtime, result, best_record)
		outcome_label = string(result.promotion.state)
		artifact_approval = runtime.manifest_context.approval_status == "human_approved" ?
			"promotion_evaluable" : "unapproved_exploration"
		isnothing(best_record) && return Dict(
			"state" => "no_valid_candidate",
			"outcome_label" => outcome_label,
			"artifact_approval" => artifact_approval,
			"source_seed_id" => String(runtime.seed_design.id),
			"condition_manifest_sha256" => runtime.manifest_context.canonical_contract_sha256,
			"review_state" => runtime.manifest_context.approval_status,
		)
		return Dict(
			"state" => "best_valid_candidate",
			"outcome_label" => outcome_label,
			"artifact_approval" => artifact_approval,
			"source_seed_id" => String(runtime.seed_design.id),
			"condition_manifest_sha256" => runtime.manifest_context.canonical_contract_sha256,
			"review_state" => runtime.manifest_context.approval_status,
			"candidate_record_id" => best_record.record_id,
			"variables" => [
				Dict(
					"id" => String(spec.name),
					"value" => getproperty(best_record.candidate, spec.name),
					"unit" => spec.unit,
				) for spec in runtime.variable_specs
			],
			"cost" => best_record.cost,
			"breakdown" => best_record.breakdown,
		)
	end

	"""Run the real hash-bound CMA-ES → Nelder-Mead exploration and persist only declared artifacts."""
	function run_d3_coupled_exploration()
		manifest_context = d3_validate_manifest()
		runtime = d3_build_runtime(manifest_context)
		outputs = d3_records_by_id(runtime.manifest_context.contract["outputs"], D3_OUTPUT_IDS, "outputs")
		output_root = d3_workspace_path(d3_value(outputs, "output_root"))
		manifest_id = String(runtime.manifest_context.contract["manifest_id"])
		occursin(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$", manifest_id) || error("Manifest id is not a safe run-id component.")
		run_id = Dates.format(now(UTC), dateformat"yyyymmddTHHMMSSsssZ") * "__" *
			manifest_id * "__" * first(runtime.manifest_context.canonical_contract_sha256, 12)
		run_directory = joinpath(output_root, run_id)
		ispath(run_directory) && error("Refusing to overwrite D3 exploration run: $(run_directory)")
		mkpath(run_directory)
		paths = Dict(id => joinpath(run_directory, String(d3_value(outputs, id))) for id in D3_OUTPUT_IDS[2:end])
		artifact_approval = runtime.manifest_context.approval_status == "human_approved" ?
			"promotion_evaluable" : "unapproved_exploration"
		started_at = now(UTC)
		write(paths["condition_manifest_snapshot_path"], read(D3_MANIFEST_PATH))
		d3_write_json(paths["config_snapshot_path"], runtime.config)
		d3_write_json(paths["hash_inventory_path"], (
			contract_sha256 = runtime.manifest_context.canonical_contract_sha256,
			files = runtime.manifest_context.hash_inventory,
		))
		d3_write_json(paths["status_path"], (
			state = "running", artifact_approval = artifact_approval,
			started_at_utc = started_at, completed_at_utc = nothing,
			contract_sha256 = runtime.manifest_context.canonical_contract_sha256,
		))
		expected_files = Set(String(d3_value(outputs, id)) for id in D3_OUTPUT_IDS[2:end])
		try
			evaluator = d3_new_evaluator(runtime; journal_path = paths["evaluation_journal_path"])
			optimizer_evaluator = candidate -> d3_optimizer_evaluation(
				evaluate_d3_slot(evaluator, candidate; capture_traces = false),
				runtime,
			)
			result = optimize_d3(
				optimizer_evaluator,
				runtime.variable_specs,
				runtime.metric_specs,
				runtime.initial_candidate,
				runtime.cma_settings,
				runtime.nm_settings,
				runtime.promotion_settings;
				condition_manifest_id = runtime.manifest_context.contract["manifest_id"],
				condition_manifest_sha256 = runtime.manifest_context.canonical_contract_sha256,
				condition_manifest_approval_status = runtime.manifest_context.approval_status,
			)
			best_record = d3_best_record(result)
			final_capture = if isnothing(best_record)
				(state = :no_valid_candidate, record = nothing)
			else
				record = evaluate_d3_slot(evaluator, best_record.candidate; capture_traces = true)
				record.status === :valid || error("Best valid candidate failed final physical reproduction.")
				(state = :captured, record = record)
			end
			d3_write_json(paths["optimization_result_path"], result)
			d3_write_json(paths["final_diagnostics_path"], final_capture)
			d3_write_json(paths["layout_specs_path"], d3_layout_specs(runtime, result, best_record))
			completed_at = now(UTC)
			d3_write_json(paths["status_path"], (
				state = "completed", artifact_approval = artifact_approval,
				started_at_utc = started_at, completed_at_utc = completed_at,
				contract_sha256 = runtime.manifest_context.canonical_contract_sha256,
				cma_state = result.cma.state, nelder_mead_state = result.nelder_mead.state,
				promotion_state = result.promotion.state,
			))
			Set(readdir(run_directory)) == expected_files || error("Run directory does not contain exactly the declared output files.")
			return (run_directory = run_directory, result = result, final_capture = final_capture)
		catch exception
			failure = (state = "failed", error_type = string(typeof(exception)), reason = sprint(showerror, exception))
			isfile(paths["evaluation_journal_path"]) || open(paths["evaluation_journal_path"], "w") do _ end
			isfile(paths["optimization_result_path"]) || d3_write_json(paths["optimization_result_path"], failure)
			isfile(paths["final_diagnostics_path"]) || d3_write_json(paths["final_diagnostics_path"], failure)
			isfile(paths["layout_specs_path"]) || d3_write_json(paths["layout_specs_path"], merge(failure, (
				source_seed_id = String(runtime.seed_design.id),
				condition_manifest_sha256 = runtime.manifest_context.canonical_contract_sha256,
				review_state = runtime.manifest_context.approval_status,
				artifact_approval = artifact_approval,
			)))
			d3_write_json(paths["status_path"], merge(failure, (
				artifact_approval = artifact_approval, started_at_utc = started_at,
				completed_at_utc = now(UTC), contract_sha256 = runtime.manifest_context.canonical_contract_sha256,
			)))
			Set(readdir(run_directory)) == expected_files || error("Failed run directory does not contain exactly the declared output files.")
			rethrow()
		end
	end
end

# ╔═╡ 0a33bd48-c02f-4c12-b4ed-0d31fe1cc6d8
TableOfContents()

# ╔═╡ b144ce59-d130-4d23-a5fe-1e42af2dd7e9
begin
	function d3_markdown_text(value)
		text = value isa AbstractString ? String(value) : JSON3.write(value)
		return replace(replace(text, "|" => "\\|"), '\n' => ' ')
	end

	function d3_condition_table(title, records)
		lines = [
			"## $(title)",
			"",
			"| Condition | Value | Unit | State | Comparator | Why | Evidence |",
			"|---|---:|---|---|---|---|---|",
		]
		for item in records
			push!(lines, join([
				"`$(d3_markdown_text(item["id"]))`",
				d3_markdown_text(item["value"]),
				d3_markdown_text(item["unit"]),
				d3_markdown_text(item["status"]),
				d3_markdown_text(get(item, "comparator", "—")),
				d3_markdown_text(item["rationale"]),
				d3_markdown_text(join(String.(item["evidence"]), ", ")),
			], " | ") |> row -> "| $(row) |")
		end
		return Markdown.parse(join(lines, "\n"))
	end

	function d3_seed_result_markdown(result)
		isnothing(result) && return md"Click **Run one seed evaluation** to execute one real, write-free physical evaluation."
		if result.status === :rejected
			return Markdown.parse("""
			## Seed evaluation result

			**Physically rejected** — `$(result.evaluation.code)`: $(result.evaluation.reason)
			""")
		end
		rows = [
			"## Seed evaluation result",
			"",
			"Contract: `$(result.contract_sha256)`  ",
			"Review state: **$(result.approval_status)**  ",
			"Total normalized squared cost: **$(result.cost_breakdown.total)**",
			"",
			"| Metric | Observed | Target | Scale | Weight | Residual | Contribution |",
			"|---|---:|---:|---:|---:|---:|---:|",
		]
		for metric in result.cost_breakdown.metrics
			push!(rows, "| `$(metric.name)` | $(metric.observed) | $(metric.target) | $(metric.scale) | $(metric.weight) | $(metric.normalized_residual) | $(metric.contribution) |")
		end
		return Markdown.parse(join(rows, "\n"))
	end

	function d3_exploration_result_markdown(result)
		isnothing(result) && return md"Click **Run full exploration** only after reviewing every condition below."
		return Markdown.parse("""
		## Exploration result

		Run directory: `$(result.run_directory)`<br>
		CMA-ES: **$(result.result.cma.state)**<br>
		Handoff: **$(result.result.handoff.state)**<br>
		Nelder-Mead: **$(result.result.nelder_mead.state)**<br>
		Promotion: **$(result.result.promotion.state)**
		""")
	end
end

# ╔═╡ c255df6a-e241-4e34-b60f-2f53bf3ee8fa
md"""
## Bound contract

- Manifest: **$(d3_manifest_context.contract["manifest_id"])**
- Canonical SHA-256: `$(d3_manifest_context.canonical_contract_sha256)`
- Effective review state: **$(d3_manifest_context.approval_status)**
- Artifact promotion eligible: **$(d3_manifest_context.promotion_eligible)**
- Execution scope: **$(d3_manifest_context.contract["scope"]["value"])**

An `agent_proposed` or `sol_reviewed` run is always written as
**unapproved exploration**. Only a current, hash-bound Human approval can make
promotion evaluable, and this notebook rejects Human approval while the input
artifact remains LC-only and promotion-ineligible.
"""

# ╔═╡ d366e07b-f352-4f45-c710-3064c04ff90b
d3_condition_table("Six physical design variables", d3_manifest_context.contract["variables"])

# ╔═╡ e477f18c-0463-4056-d821-4175d1500a1c
d3_condition_table("Five cost objectives plus one promotion-only condition", d3_manifest_context.contract["metric_contract"]["metric_specs"])

# ╔═╡ f588029d-1574-4167-e932-5286e2611b2d
begin
	evaluator_conditions = d3_manifest_context.contract["evaluator_settings"]
	d3_condition_table("Simulation, scan, assignment, and seed conditions", evaluator_conditions[1:16])
end

# ╔═╡ 069913ae-2685-4278-fa43-6397f3722c3e
d3_condition_table("Fit quality, extrapolation, and cross-check conditions", evaluator_conditions[17:end])

# ╔═╡ 17aa24bf-3796-4389-0b54-74a804833d4f
d3_condition_table("Harmonic-balance execution conditions", d3_manifest_context.contract["hb_settings"])

# ╔═╡ 28bb35c0-48a7-449a-1c65-85b915944e50
begin
	optimization_conditions = vcat(
		d3_manifest_context.contract["optimization"]["initial_seed"],
		d3_manifest_context.contract["optimization"]["cma"],
		d3_manifest_context.contract["optimization"]["nelder_mead"],
		d3_manifest_context.contract["optimization"]["promotion"],
	)
	d3_condition_table("CMA-ES, Nelder-Mead, and promotion conditions", optimization_conditions)
end

# ╔═╡ 39cc46d1-59b8-45ab-2d76-96ca26a55f61
d3_condition_table("Declared design conflicts requiring review", d3_manifest_context.contract["conflicts"])

# ╔═╡ 4add57e2-6ac9-46bc-3e87-a7db37b66072
d3_condition_table("Future five-pair closure conditions (not run here)", d3_manifest_context.contract["closure_conditions"])

# ╔═╡ 5bee68f3-7bda-47cd-4f98-b8ec48c77183
md"""
## Explicit execution

The first button runs one real seed `Simulation → evaluator → cost` path and
writes nothing. The second button runs the full manifest-bound CMA-ES →
Nelder-Mead exploration and writes exactly the declared run artifacts,
including `layout_specs.json`. Neither path runs when this notebook opens.
"""

# ╔═╡ 6cff7904-8ceb-48de-50a9-c9fd59d88294
@bind d3_seed_evaluation_click Button("Run one seed evaluation (no writes)")

# ╔═╡ 7d008a15-9dfc-49ef-61ba-da0e6ae993a5
d3_seed_evaluation_result = d3_seed_evaluation_click isa Integer && d3_seed_evaluation_click > 0 ?
	evaluate_d3_seed_cost() : nothing

# ╔═╡ 8e119b26-ae0d-4af0-72cb-eb1f7bfa04b6
d3_seed_result_markdown(d3_seed_evaluation_result)

# ╔═╡ 9f22ac37-bf1e-4b01-83dc-fc208c0b15c7
@bind d3_exploration_click Button("Run full CMA-ES → Nelder-Mead exploration")

# ╔═╡ a033bd48-c02f-4c12-94ed-0d319d1c26d8
d3_exploration_result = d3_exploration_click isa Integer && d3_exploration_click > 0 ?
	run_d3_coupled_exploration() : nothing

# ╔═╡ b144ce59-d130-4d23-95fe-1e429e2d37e9
d3_exploration_result_markdown(d3_exploration_result)

# ╔═╡ Cell order:
# ╟─a5df7804-e15d-4f5a-b319-4df0eabff5c4
# ╟─956db29c-afb0-471c-93f7-fc434f660064
# ╠═fc66b3bc-83ed-4816-b1fe-d5ca8132bdd5
# ╠═80577edb-d4e3-481b-8649-b637324ad624
# ╠═5cf81fe5-e47b-4850-a661-b2548f5488d4
# ╠═0a33bd48-c02f-4c12-b4ed-0d31fe1cc6d8
# ╠═b144ce59-d130-4d23-a5fe-1e42af2dd7e9
# ╟─c255df6a-e241-4e34-b60f-2f53bf3ee8fa
# ╟─d366e07b-f352-4f45-c710-3064c04ff90b
# ╟─e477f18c-0463-4056-d821-4175d1500a1c
# ╟─f588029d-1574-4167-e932-5286e2611b2d
# ╟─069913ae-2685-4278-fa43-6397f3722c3e
# ╟─17aa24bf-3796-4389-0b54-74a804833d4f
# ╟─28bb35c0-48a7-449a-1c65-85b915944e50
# ╟─39cc46d1-59b8-45ab-2d76-96ca26a55f61
# ╟─4add57e2-6ac9-46bc-3e87-a7db37b66072
# ╟─5bee68f3-7bda-47cd-4f98-b8ec48c77183
# ╠═6cff7904-8ceb-48de-50a9-c9fd59d88294
# ╠═7d008a15-9dfc-49ef-61ba-da0e6ae993a5
# ╟─8e119b26-ae0d-4af0-72cb-eb1f7bfa04b6
# ╠═9f22ac37-bf1e-4b01-83dc-fc208c0b15c7
# ╠═a033bd48-c02f-4c12-94ed-0d319d1c26d8
# ╟─b144ce59-d130-4d23-95fe-1e429e2d37e9
