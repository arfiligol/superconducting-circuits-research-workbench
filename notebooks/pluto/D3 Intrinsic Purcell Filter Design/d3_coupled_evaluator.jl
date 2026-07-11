# This file owns the physical single-slot evaluator used by the D3 coupled
# optimizer. It rebuilds and solves the real HB circuits for every geometry,
# extracts loaded-bare references, fits complex S21 for J, and returns physical
# evidence records. It does not own optimization algorithms, target
# values, fabrication tolerances, or multi-slot acceptance.
# Canonical D3 target and review contract:
# https://github.com/arfiligol/SCQ_Design/blob/main/docs/design-targets/d3-intrinsic-interferometric-purcell-filter.qmd
# Canonical MTL basis, Maxwell lowering, and matrix-artifact eligibility:
# https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/transmission-lines/multiconductor-rlgc-matrix-semantics.qmd
# Canonical fitting semantics:
# https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/notch-resonator-complex-s21-fit.qmd
# https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/resonator-decay-linewidth-and-quality-factor.qmd
# https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/vector-fitting-passivity.qmd
# https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/readout/readout-filter-s21-j-fit.qmd
# Canonical observable and mode-layer semantics:
# https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/readout/loaded-bare-readout-filter-references.qmd
# https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/readout/bare-vs-hybridized-readout-filter-modes.qmd
# https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/simulation/port-reference-impedance-semantics.qmd
# https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/simulation/port-termination-compensation.qmd

import SHA

struct D3CandidateRejected <: Exception
	code::String
	reason::String
	details
end

Base.showerror(io::IO, error::D3CandidateRejected) = print(io, error.reason)

function reject_d3_candidate(code, reason; details = nothing)
	code_value = strip(String(code))
	message = strip(String(reason))
	occursin(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$", code_value) ||
		error("D3 candidate rejection requires a stable lowercase machine code.")
	isempty(message) && error("D3 candidate rejection requires a reason.")
	throw(D3CandidateRejected(code_value, message, details))
end

struct D3SlotEvaluationSettings
	frequency_step_hz::Float64
	feedline_length_um::Float64
	loaded_bare_half_width_hz::Float64
	loaded_bare_ownership_half_width_hz::Float64
	max_filter_anchor_distance_hz::Float64
	min_filter_assignment_margin_hz::Float64
	pair_trace_half_width_hz::Float64
	pair_fit_half_width_hz::Float64
	pair_background_inner_half_width_hz::Float64
	notch_half_width_hz::Float64
	readout_probe_capacitances_fF::Vector{Float64}
	min_readout_frequency_extrapolation_r2::Float64
	min_readout_linewidth_extrapolation_r2::Float64
	max_notch_abs_im_z21_ohm::Float64
	j_bounds_hz::Tuple{Float64,Float64}
	j_seeds_hz::Vector{Float64}
	linear_ls_rcond::Float64
	least_squares_max_nfev::Int
	least_squares_ftol::Float64
	least_squares_xtol::Float64
	least_squares_gtol::Float64
	least_squares_diff_step::Float64
	min_successful_seed_count::Int
	min_successful_seed_fraction::Float64
	near_optimal_mse_ratio::Float64
	near_optimal_mse_absolute_tolerance::Float64
	min_winning_seed_count::Int
	channel_calibration_fit_half_width_hz::Float64
	channel_calibration_background_inner_half_width_hz::Float64
	min_channel_calibration_complex_r2::Float64
	min_channel_calibration_abs_r2::Float64
	max_channel_calibration_phase_rmse_rad::Float64
	min_reference_magnitude::Float64
	min_phase_magnitude::Float64
	min_complex_r2::Float64
	min_abs_r2::Float64
	max_phase_rmse_rad::Float64
	min_normalized_bound_margin::Float64
	max_seed_spread_hz::Float64
	vector_bg_poles::Int
	vector_min_q::Float64
	max_vector_rms_error::Float64
	max_vector_pole_disagreement_hz::Float64
	max_pair_pole_center_offset_hz::Float64

	function D3SlotEvaluationSettings(;
		frequency_step_hz,
		feedline_length_um,
		loaded_bare_half_width_hz,
		loaded_bare_ownership_half_width_hz,
		max_filter_anchor_distance_hz,
		min_filter_assignment_margin_hz,
		pair_trace_half_width_hz,
		pair_fit_half_width_hz,
		pair_background_inner_half_width_hz,
		notch_half_width_hz,
		readout_probe_capacitances_fF,
		min_readout_frequency_extrapolation_r2,
		min_readout_linewidth_extrapolation_r2,
		max_notch_abs_im_z21_ohm,
		j_bounds_hz,
		j_seeds_hz,
		linear_ls_rcond,
		least_squares_max_nfev,
		least_squares_ftol,
		least_squares_xtol,
		least_squares_gtol,
		least_squares_diff_step,
		min_successful_seed_count,
		min_successful_seed_fraction,
		near_optimal_mse_ratio,
		near_optimal_mse_absolute_tolerance,
		min_winning_seed_count,
		channel_calibration_fit_half_width_hz,
		channel_calibration_background_inner_half_width_hz,
		min_channel_calibration_complex_r2,
		min_channel_calibration_abs_r2,
		max_channel_calibration_phase_rmse_rad,
		min_reference_magnitude,
		min_phase_magnitude,
		min_complex_r2,
		min_abs_r2,
		max_phase_rmse_rad,
		min_normalized_bound_margin,
		max_seed_spread_hz,
		vector_bg_poles,
		vector_min_q,
		max_vector_rms_error,
		max_vector_pole_disagreement_hz,
		max_pair_pole_center_offset_hz,
	)
		strictly_positive_values = Float64[
			frequency_step_hz,
			feedline_length_um,
			loaded_bare_half_width_hz,
			pair_trace_half_width_hz,
			pair_fit_half_width_hz,
			pair_background_inner_half_width_hz,
			notch_half_width_hz,
			min_reference_magnitude,
		]
		all(value -> isfinite(value) && value > 0, strictly_positive_values) ||
			error("D3 scan widths, step, feedline length, and reference division floor must be finite and positive.")
		nonnegative_gate_values = Float64[
			loaded_bare_ownership_half_width_hz,
			max_filter_anchor_distance_hz,
			min_filter_assignment_margin_hz,
			max_notch_abs_im_z21_ohm,
			max_seed_spread_hz,
			vector_min_q,
			max_vector_rms_error,
			max_vector_pole_disagreement_hz,
			max_pair_pole_center_offset_hz,
		]
		all(value -> isfinite(value) && value >= 0, nonnegative_gate_values) ||
			error("D3 max/min gates that admit exact equality must be finite and non-negative.")
		loaded_bare_ownership_half_width_hz <= loaded_bare_half_width_hz ||
			error("Loaded-bare ownership window must fit inside its scan.")
		pair_fit_half_width_hz < pair_background_inner_half_width_hz < pair_trace_half_width_hz ||
			error("D3 pair windows must satisfy fit < background inner edge < trace half width.")
		0 < channel_calibration_fit_half_width_hz < channel_calibration_background_inner_half_width_hz < loaded_bare_half_width_hz ||
			error("D3 channel-calibration windows must satisfy fit < background inner edge < loaded-bare scan half width.")
		probe_caps = Float64.(collect(readout_probe_capacitances_fF))
		length(probe_caps) >= 4 || error("Quadratic readout extrapolation requires at least four probe capacitances.")
		all(value -> isfinite(value) && value > 0, probe_caps) ||
			error("Readout probe capacitances must be finite and positive.")
		length(unique(probe_caps)) == length(probe_caps) ||
			error("Readout probe capacitances must be unique.")
		bounds = Tuple(Float64.(collect(j_bounds_hz)))
		length(bounds) == 2 || error("J bounds must contain exactly two values.")
		0 < bounds[1] < bounds[2] || error("J bounds must be strictly positive and ordered.")
		seeds = Float64.(collect(j_seeds_hz))
		!isempty(seeds) || error("At least one J seed is required.")
		length(unique(seeds)) == length(seeds) || error("J seeds must be unique.")
		all(seed -> bounds[1] <= seed <= bounds[2], seeds) ||
			error("Every J seed must lie inside the J bounds.")
		max_nfev = Int(least_squares_max_nfev)
		max_nfev > 0 || error("D3 least_squares_max_nfev must be positive.")
		ls_rcond = Float64(linear_ls_rcond)
		isfinite(ls_rcond) && ls_rcond >= 0 ||
			error("D3 linear_ls_rcond must be finite and non-negative.")
		least_squares_conditions = Float64[
			least_squares_ftol,
			least_squares_xtol,
			least_squares_gtol,
			least_squares_diff_step,
		]
		all(value -> isfinite(value) && value > 0, least_squares_conditions) ||
			error("D3 least-squares convergence and finite-difference conditions must be finite and positive.")
		minimum_success_count = Int(min_successful_seed_count)
		minimum_winning_count = Int(min_winning_seed_count)
		minimum_success_count >= 1 || error("D3 min_successful_seed_count must be positive.")
		minimum_winning_count >= 1 || error("D3 min_winning_seed_count must be positive.")
		minimum_success_count >= minimum_winning_count ||
			error("D3 min_successful_seed_count must not be smaller than min_winning_seed_count.")
		total_starts = length(seeds)
		minimum_success_count <= total_starts ||
			error("D3 min_successful_seed_count exceeds the declared seed grid.")
		minimum_winning_count <= total_starts ||
			error("D3 min_winning_seed_count exceeds the declared seed grid.")
		minimum_success_fraction = Float64(min_successful_seed_fraction)
		0 < minimum_success_fraction <= 1 ||
			error("D3 min_successful_seed_fraction must lie in (0, 1].")
		mse_ratio = Float64(near_optimal_mse_ratio)
		isfinite(mse_ratio) && mse_ratio >= 1 ||
			error("D3 near_optimal_mse_ratio must be finite and at least one.")
		mse_absolute_tolerance = Float64(near_optimal_mse_absolute_tolerance)
		isfinite(mse_absolute_tolerance) && mse_absolute_tolerance >= 0 ||
			error("D3 near_optimal_mse_absolute_tolerance must be finite and non-negative.")
		r2_values = Float64[
			min_readout_frequency_extrapolation_r2,
			min_readout_linewidth_extrapolation_r2,
			min_channel_calibration_complex_r2,
			min_channel_calibration_abs_r2,
			min_complex_r2,
			min_abs_r2,
		]
		all(value -> isfinite(value) && value <= 1, r2_values) ||
			error("D3 R2 gates must be finite and at most one.")
		nonnegative_values = Float64[
			max_channel_calibration_phase_rmse_rad,
			max_phase_rmse_rad,
			min_normalized_bound_margin,
		]
		all(value -> isfinite(value) && value >= 0, nonnegative_values) ||
			error("D3 phase and bound gates must be finite and non-negative.")
		min_normalized_bound_margin < 0.5 ||
			error("D3 normalized bound margin must be less than 0.5.")
		phase_magnitude_floor = Float64(min_phase_magnitude)
		isfinite(phase_magnitude_floor) && phase_magnitude_floor >= 0 ||
			error("D3 min_phase_magnitude must be finite and non-negative.")
		Int(vector_bg_poles) >= 0 || error("Vector-fit background pole count must be non-negative.")
		return new(
			Float64(frequency_step_hz),
			Float64(feedline_length_um),
			Float64(loaded_bare_half_width_hz),
			Float64(loaded_bare_ownership_half_width_hz),
			Float64(max_filter_anchor_distance_hz),
			Float64(min_filter_assignment_margin_hz),
			Float64(pair_trace_half_width_hz),
			Float64(pair_fit_half_width_hz),
			Float64(pair_background_inner_half_width_hz),
			Float64(notch_half_width_hz),
			probe_caps,
			Float64(min_readout_frequency_extrapolation_r2),
			Float64(min_readout_linewidth_extrapolation_r2),
			Float64(max_notch_abs_im_z21_ohm),
			(bounds[1], bounds[2]),
			seeds,
			ls_rcond,
			max_nfev,
			least_squares_conditions[1],
			least_squares_conditions[2],
			least_squares_conditions[3],
			least_squares_conditions[4],
			minimum_success_count,
			minimum_success_fraction,
			mse_ratio,
			mse_absolute_tolerance,
			minimum_winning_count,
			Float64(channel_calibration_fit_half_width_hz),
			Float64(channel_calibration_background_inner_half_width_hz),
			Float64(min_channel_calibration_complex_r2),
			Float64(min_channel_calibration_abs_r2),
			Float64(max_channel_calibration_phase_rmse_rad),
			Float64(min_reference_magnitude),
			phase_magnitude_floor,
			Float64(min_complex_r2),
			Float64(min_abs_r2),
			Float64(max_phase_rmse_rad),
			Float64(min_normalized_bound_margin),
			Float64(max_seed_spread_hz),
			Int(vector_bg_poles),
			Float64(vector_min_q),
			Float64(max_vector_rms_error),
			Float64(max_vector_pole_disagreement_hz),
			Float64(max_pair_pole_center_offset_hz),
		)
	end
end

mutable struct D3SlotEvaluator
	case
	seed_design
	feedline::D3FeedlineRLGC
	hb_settings::D3HBSettings
	settings::D3SlotEvaluationSettings
	reference_cache::Dict{String,Vector{ComplexF64}}
	records::Dict{Tuple,Any}
	journal_path::Union{Nothing,String}
end

function D3SlotEvaluator(case, seed_design, feedline, hb_settings, settings; journal_path)
	selected_journal_path = isnothing(journal_path) ? nothing : String(journal_path)
	if !isnothing(selected_journal_path)
		isfile(selected_journal_path) && error("Refusing to overwrite D3 evaluator journal: $(selected_journal_path)")
		mkpath(dirname(selected_journal_path))
	end
	return D3SlotEvaluator(
		case,
		seed_design,
		feedline,
		hb_settings,
		settings,
		Dict{String,Vector{ComplexF64}}(),
		Dict{Tuple,Any}(),
		selected_journal_path,
	)
end

function _candidate_design(seed_design, candidate)
	values = Float64[
		candidate.lc_um,
		candidate.lp_short_um,
		candidate.lr_short_um,
		candidate.lp_open_um,
		candidate.lr_open_um,
		candidate.filter_to_line_capacitance_fF,
	]
	all(isfinite, values) || error("Candidate geometry contains a non-finite value.")
	all(>(0.0), values) || reject_d3_candidate(
		"candidate.nonpositive_geometry",
		"Candidate geometry and capacitance must be positive.";
		details = (values = values,),
	)
	lc_um, lp_short_um, lr_short_um, lp_open_um, lr_open_um, capacitance_fF = values
	return merge(
		seed_design,
		(
			id = Symbol("$(seed_design.id)__optimizer_candidate"),
			lc_um = lc_um,
			lp_short_um = lp_short_um,
			lr_short_um = lr_short_um,
			lp_open_um = lp_open_um,
			lr_open_um = lr_open_um,
			lp_total_um = lp_short_um + lc_um + lp_open_um,
			lr_total_um = lr_short_um + lc_um + lr_open_um,
			notch_length_um = lp_short_um + lc_um + lr_short_um,
			filter_to_line_capacitance_fF = capacitance_fF,
		),
	)
end

function _candidate_identity(candidate)
	return join(("$(name)=$(repr(getproperty(candidate, name)))" for name in propertynames(candidate)), "|")
end

function _slot_frequency_grid(slot_hz, half_width_hz, step_hz)
	return frequency_range_with_step(slot_hz - half_width_hz, slot_hz + half_width_hz, step_hz)
end

const D3_INTRINSIC_WIDE_MARGIN_HZ = 500.0e6

"""
	_intrinsic_wide_capture_grid(design, notch_target_hz, filter_loaded_bare_hz, step_hz)

Build the wide intrinsic-PTC grid used only for final trace capture. The lower
bound exposes the notch neighborhood, while the design-wide scan stop is the
declared conservative upper bound for the no-Cext intrinsic resonator region.
"""
function _intrinsic_wide_capture_grid(design, notch_target_hz, filter_loaded_bare_hz, step_hz)
	values = Float64[
		notch_target_hz,
		filter_loaded_bare_hz,
		step_hz,
		design.scan_stop_ghz,
	]
	all(isfinite, values) || error("Wide intrinsic capture range inputs must be finite.")
	values[3] > 0 || error("Wide intrinsic capture frequency step must be positive.")

	start_hz = values[1] - D3_INTRINSIC_WIDE_MARGIN_HZ
	stop_hz = values[4] * D3_HZ_PER_GHZ
	required_minimum_stop_hz = values[2] + D3_INTRINSIC_WIDE_MARGIN_HZ
	start_hz > 0 || error("Wide intrinsic capture start must remain positive.")
	stop_hz >= required_minimum_stop_hz || error(
		"Design scan_stop_ghz must cover filter loaded-bare plus 500 MHz for wide intrinsic final capture.",
	)
	stop_hz > start_hz || error("Wide intrinsic capture stop must exceed its start.")

	frequencies_hz = frequency_range_with_step(start_hz, stop_hz, values[3])
	return (
		frequencies_hz = frequencies_hz,
		range_provenance = (
			contract_id = "d3-intrinsic-wide-final-capture-v1",
			scope = "final_capture_only",
			start_hz = start_hz,
			stop_hz = stop_hz,
			frequency_step_hz = values[3],
			notch_target_hz = values[1],
			start_margin_below_notch_hz = D3_INTRINSIC_WIDE_MARGIN_HZ,
			filter_loaded_bare_hz = values[2],
			required_minimum_stop_hz = required_minimum_stop_hz,
			declared_design_scan_stop_ghz = values[4],
			stop_role = "conservative_no_cext_intrinsic_resonator_upper_bound",
		),
	)
end

"""
    _frequency_grid_sha256(frequencies_hz)

Hash the complete ordered Float64 grid by its exact IEEE-754 bit patterns. The
versioned text framing makes length and element boundaries unambiguous while
remaining independent of host byte order or numeric display formatting.
"""
function _frequency_grid_sha256(frequencies_hz)
	frequencies = Float64.(collect(frequencies_hz))
	!isempty(frequencies) || error("A D3 frequency grid must not be empty.")
	all(isfinite, frequencies) || error("A D3 frequency grid must contain only finite Float64 values.")
	payload = string(
		"d3-frequency-grid-float64-bits-v1|count=",
		length(frequencies),
		"|",
		join(bitstring.(frequencies), "|"),
	)
	return bytes2hex(SHA.sha256(payload))
end

function _d3_trace_identity(
	case_id,
	design_id,
	candidate_identity,
	loaded_grid_sha256,
	pair_grid_sha256,
)
	for (label, hash) in (
		("loaded", loaded_grid_sha256),
		("pair", pair_grid_sha256),
	)
		occursin(r"^[0-9a-f]{64}$", String(hash)) ||
			error("$(label) frequency-grid identity must be a lowercase SHA-256 digest.")
	end
	identity = String(candidate_identity)
	design = String(design_id)
	case = String(case_id)
	return (
		reference_contract_id = "d3-reference-contract|case=$(case)|$(identity)",
		filter_loaded_bare_reference_id = "d3-filter-loaded-bare|grid_sha256=$(loaded_grid_sha256)|design=$(design)|$(identity)",
		readout_loaded_bare_reference_id = "d3-readout-loaded-bare-zero-probe|grid_sha256=$(loaded_grid_sha256)|design=$(design)|$(identity)",
		filter_only_trace_id = "d3-filter-only-hb|grid_sha256=$(loaded_grid_sha256)|design=$(design)|$(identity)",
		loaded_empty_feedline_trace_id = "d3-empty-feedline-hb|grid_sha256=$(loaded_grid_sha256)|case=$(case)",
		calibration_id = "d3-filter-channel|grid_sha256=$(loaded_grid_sha256)|case=$(case)|$(identity)",
		pair_measured_trace_id = "d3-single-pair-hb|grid_sha256=$(pair_grid_sha256)|design=$(design)|$(identity)",
		pair_empty_feedline_trace_id = "d3-empty-feedline-hb|grid_sha256=$(pair_grid_sha256)|case=$(case)",
		pair_assignment_id = "$(design)|grid_sha256=$(pair_grid_sha256)|$(identity)",
	)
end

function _reference_trace!(evaluator, frequencies_hz)
	key = _frequency_grid_sha256(frequencies_hz)
	return get!(evaluator.reference_cache, key) do
		coupling_position_m = evaluator.settings.feedline_length_um * D3_METERS_PER_UM / 2
		plan = build_feedline_reference_plan(
			evaluator.feedline;
			feedline_length_um = evaluator.settings.feedline_length_um,
			breakpoints_m = [coupling_position_m],
			hb_settings = evaluator.hb_settings,
		)
		hb = run_sparameter_hb(plan, frequencies_hz; hb_settings = evaluator.hb_settings)
		hb.hb_intent_ok || error("Empty-feedline HB intent validation failed.")
		ComplexF64.(hb.s21)
	end
end

function _run_candidate_hb(
	evaluator,
	circuit_plan,
	frequencies_hz,
	stage_label;
	compensate_port_indices = (),
	removal_intent::Union{Nothing,Symbol} = nothing,
)
	try
		return run_sparameter_hb(
			circuit_plan,
			frequencies_hz;
			hb_settings = evaluator.hb_settings,
			compensate_port_indices = compensate_port_indices,
			removal_intent = removal_intent,
		)
	catch exception
		exception isa HBSolverNumericalError || rethrow()
		@error "$(stage_label) HB numerical solve failed" exception = (exception, catch_backtrace())
		rethrow()
	end
end

function _normalized_s21(frequencies_hz, measured_s21, reference_s21, minimum_reference)
	length(frequencies_hz) == length(measured_s21) == length(reference_s21) ||
		error("HB and reference traces must have identical lengths.")
	all(isfinite, real.(measured_s21)) && all(isfinite, imag.(measured_s21)) ||
		error("HB S21 contains a non-finite value.")
	minimum(abs.(reference_s21)) >= minimum_reference ||
		error("Empty-feedline reference artifact falls below the configured magnitude floor.")
	return ComplexF64.(measured_s21) ./ reference_s21
end

function _require_vector_fit(result, expected_count, label, settings)
	get(result, "status", "missing") == "success" ||
		error("$(label) vector-fit execution failed: $(get(result, "reason", "unstated reason"))")
	resonances = get(result, "resonances", Any[])
	length(resonances) == expected_count ||
		reject_d3_candidate(
			"vector.resonance_count",
			"$(label) vector fit returned $(length(resonances)) resonances; expected $(expected_count).";
			details = (observed_count = length(resonances), expected_count = expected_count),
		)
	artifacts = get(result, "artifacts", Any[])
	isempty(artifacts) || reject_d3_candidate(
		"vector.unowned_artifact_poles",
		"$(label) vector fit returned unowned artifact poles.";
		details = (artifacts = artifacts,),
	)
	rms_error = get(get(result, "metrics", Dict()), "rms_error", nothing)
	rms_error isa Real && isfinite(rms_error) ||
		error("$(label) successful vector-fit payload has no finite RMS error.")
	Float64(rms_error) <= settings.max_vector_rms_error ||
		reject_d3_candidate(
			"vector.rms_gate",
			"$(label) vector-fit RMS error exceeds the configured gate.";
			details = (
				observed_rms_error = Float64(rms_error),
				max_vector_rms_error = settings.max_vector_rms_error,
			),
		)
	return sort(resonances; by = resonance -> Float64(resonance["fr_hz"]))
end

function _loaded_mode_from_vector_resonance(
	resonance,
	slot_hz,
	label,
	settings;
	require_slot_ownership,
	vector_rms_error,
)
	frequency_hz = Float64(resonance["fr_hz"])
	isfinite(frequency_hz) || error("$(label) vector-fit frequency is non-finite.")
	bandwidth_hz = resonance["bandwidth_hz"]
	bandwidth_hz isa Real && isfinite(bandwidth_hz) ||
		error("$(label) successful vector-fit payload has no finite loaded linewidth.")
	bandwidth_hz > 0 ||
		reject_d3_candidate(
			"vector.loaded_linewidth",
			"$(label) loaded linewidth is non-positive.";
			details = (bandwidth_hz = bandwidth_hz,),
		)
	(!require_slot_ownership || abs(frequency_hz - slot_hz) <= settings.loaded_bare_ownership_half_width_hz) ||
		reject_d3_candidate(
			"loaded_bare.ownership_window",
			"$(label) resonance lies outside its loaded-bare ownership window.";
			details = (
				frequency_hz = frequency_hz,
				slot_hz = slot_hz,
				ownership_half_width_hz = settings.loaded_bare_ownership_half_width_hz,
			),
		)
	return (
		frequency_hz = frequency_hz,
		bandwidth_hz = Float64(bandwidth_hz),
		vector_rms_error = Float64(vector_rms_error),
		pole_real = resonance["pole_real"],
		pole_imag = resonance["pole_imag"],
	)
end

function _fit_single_loaded_mode(
	frequencies_hz,
	normalized_s21,
	slot_hz,
	label,
	settings;
	require_slot_ownership,
)
	result = fit_vector_s21(
		frequencies_hz,
		normalized_s21;
		n_resonators = 1,
		bg_poles = settings.vector_bg_poles,
		min_q = settings.vector_min_q,
		restrict_to_input_span = true,
	)
	resonance = only(_require_vector_fit(result, 1, label, settings))
	return _loaded_mode_from_vector_resonance(
		resonance,
		slot_hz,
		label,
		settings;
		require_slot_ownership = require_slot_ownership,
		vector_rms_error = result["metrics"]["rms_error"],
	)
end

function _fit_readout_probe_loaded_mode(
	frequencies_hz,
	normalized_s21,
	slot_hz,
	filter_frequency_hz,
	label,
	settings,
)
	# The selected filter loading remains present in every finite readout probe.
	# Assign the filter feature only by closeness to its independent reference;
	# frequency sign/order is not a mode identity.
	result = fit_vector_s21(
		frequencies_hz,
		normalized_s21;
		n_resonators = 2,
		bg_poles = settings.vector_bg_poles,
		min_q = settings.vector_min_q,
		restrict_to_input_span = true,
	)
	resonances = _require_vector_fit(result, 2, label, settings)
	pole_frequencies_hz = Float64[resonance["fr_hz"] for resonance in resonances]
	anchor_distances_hz = abs.(pole_frequencies_hz .- filter_frequency_hz)
	filter_index = argmin(anchor_distances_hz)
	readout_index = filter_index == 1 ? 2 : 1
	filter_anchor_distance_hz = anchor_distances_hz[filter_index]
	assignment_margin_hz = anchor_distances_hz[readout_index] - filter_anchor_distance_hz
	filter_anchor_distance_hz <= settings.max_filter_anchor_distance_hz ||
		reject_d3_candidate(
			"mode_assignment.filter_anchor_distance",
			"$(label) nearest pole is too far from the independent filter reference.";
			details = (
				filter_loaded_bare_hz = filter_frequency_hz,
				vector_poles_hz = pole_frequencies_hz,
				filter_anchor_distance_hz = filter_anchor_distance_hz,
				max_filter_anchor_distance_hz = settings.max_filter_anchor_distance_hz,
			),
		)
	assignment_margin_hz >= settings.min_filter_assignment_margin_hz ||
		reject_d3_candidate(
			"mode_assignment.ambiguous_filter_anchor",
			"$(label) pole assignment margin is too small to distinguish filter and readout.";
		details = (
			filter_loaded_bare_hz = filter_frequency_hz,
			vector_poles_hz = pole_frequencies_hz,
			anchor_distances_hz = anchor_distances_hz,
			assignment_margin_hz = assignment_margin_hz,
			min_filter_assignment_margin_hz = settings.min_filter_assignment_margin_hz,
		),
		)
	filter_probe_mode = _loaded_mode_from_vector_resonance(
		resonances[filter_index],
		slot_hz,
		"$(label) assigned filter pole",
		settings;
		require_slot_ownership = true,
		vector_rms_error = result["metrics"]["rms_error"],
	)
	readout_mode = _loaded_mode_from_vector_resonance(
		resonances[readout_index],
		slot_hz,
		"$(label) assigned readout pole",
		settings;
		require_slot_ownership = false,
		vector_rms_error = result["metrics"]["rms_error"],
	)
	return merge(readout_mode, (
		assignment = (
			filter_reference_hz = filter_frequency_hz,
			vector_poles_hz = pole_frequencies_hz,
			filter_pole_index = filter_index,
			readout_pole_index = readout_index,
			filter_anchor_distance_hz = filter_anchor_distance_hz,
			assignment_margin_hz = assignment_margin_hz,
			filter_probe_mode = filter_probe_mode,
		),
	))
end

function _quadratic_zero_intercept(x_values, y_values, minimum_r2, label, rejection_code)
	x = Float64.(collect(x_values))
	y = Float64.(collect(y_values))
	length(x) == length(y) >= 4 || error("$(label) quadratic extrapolation requires matching arrays with at least four values.")
	all(isfinite, x) && all(isfinite, y) || error("$(label) quadratic extrapolation inputs must be finite.")
	matrix = hcat(ones(length(x)), x, x .^ 2)
	rank_value = rank(matrix)
	rank_value == 3 || error("$(label) extrapolation matrix is rank deficient.")
	coefficients = matrix \ y
	all(isfinite, coefficients) || error("$(label) extrapolation coefficients are non-finite.")
	fitted = matrix * coefficients
	residuals = fitted - y
	sse = sum(abs2, residuals)
	centered = sum(abs2, y .- sum(y) / length(y))
	centered > 0 || reject_d3_candidate(
		"$(rejection_code).r2_undefined",
		"$(label) extrapolation R2 is undefined.";
		details = (x_values = x, y_values = y),
	)
	r2 = 1 - sse / centered
	isfinite(r2) || error("$(label) extrapolation produced a non-finite R2.")
	r2 >= minimum_r2 || reject_d3_candidate(
		"$(rejection_code).r2_gate",
		"$(label) extrapolation R2 $(r2) is below $(minimum_r2).";
		details = (observed_r2 = r2, minimum_r2 = minimum_r2),
	)
	return (
		x_values = x,
		y_values = y,
		coefficients = (
			intercept = Float64(coefficients[1]),
			linear_per_fF = Float64(coefficients[2]),
			quadratic_per_fF2 = Float64(coefficients[3]),
		),
		fitted_y_values = Float64.(fitted),
		residual_y_values = Float64.(residuals),
		rmse = sqrt(sse / length(y)),
		rank = rank_value,
		intercept = Float64(coefficients[1]),
		r2 = Float64(r2),
	)
end

function _zero_constrained_linewidth_fit(x_values, y_values, minimum_r2, label, rejection_code)
	x = Float64.(collect(x_values))
	y = Float64.(collect(y_values))
	length(x) == length(y) >= 4 || error("$(label) zero-constrained extrapolation requires matching arrays with at least four values.")
	all(isfinite, x) && all(isfinite, y) || error("$(label) zero-constrained extrapolation inputs must be finite.")
	matrix = hcat(x .^ 2, x .^ 4)
	rank_value = rank(matrix)
	rank_value == 2 || error("$(label) zero-constrained extrapolation matrix is rank deficient.")
	coefficients = matrix \ y
	all(isfinite, coefficients) || error("$(label) zero-constrained extrapolation coefficients are non-finite.")
	fitted = matrix * coefficients
	all(isfinite, fitted) || error("$(label) zero-constrained fitted values are non-finite.")
	residuals = fitted - y
	sse = sum(abs2, residuals)
	centered = sum(abs2, y .- sum(y) / length(y))
	centered > 0 || reject_d3_candidate(
		"$(rejection_code).r2_undefined",
		"$(label) zero-constrained extrapolation R2 is undefined.";
		details = (
			x_values = x,
			y_values = y,
			fitted_y_values = Float64.(fitted),
			residual_y_values = Float64.(residuals),
		),
	)
	r2 = 1 - sse / centered
	isfinite(r2) || error("$(label) zero-constrained extrapolation produced a non-finite R2.")
	r2 >= minimum_r2 || reject_d3_candidate(
		"$(rejection_code).r2_gate",
		"$(label) zero-constrained extrapolation R2 $(r2) is below $(minimum_r2).";
		details = (
			observed_r2 = r2,
			minimum_r2 = minimum_r2,
			x_values = x,
			y_values = y,
			fitted_y_values = Float64.(fitted),
			residual_y_values = Float64.(residuals),
		),
	)
	return (
		x_values = x,
		y_values = y,
		coefficients = (
			quadratic_per_fF2 = Float64(coefficients[1]),
			quartic_per_fF4 = Float64(coefficients[2]),
		),
		fitted_y_values = Float64.(fitted),
		residual_y_values = Float64.(residuals),
		rmse = sqrt(sse / length(y)),
		rank = rank_value,
		intercept = 0.0,
		r2 = Float64(r2),
	)
end

function _owned_notch_zero(frequencies_hz, signed_imag_z21, target_hz, half_width_hz, maximum_value)
	indexes = findall(abs.(frequencies_hz .- target_hz) .<= half_width_hz)
	length(indexes) >= 3 || reject_d3_candidate(
		"notch.insufficient_samples",
		"Notch window contains fewer than three HB samples.";
		details = (sample_count = length(indexes),),
	)
	local_values = Float64.(signed_imag_z21[indexes])
	all(isfinite, local_values) ||
		error("Notch observable contains an invalid value.")
	roots = NamedTuple[]
	for local_index in 1:(length(indexes) - 1)
		y_left = local_values[local_index]
		y_right = local_values[local_index + 1]
		if y_left == 0
			push!(roots, (frequency_hz = frequencies_hz[indexes[local_index]], sampled_abs_im_z21_ohm = 0.0))
		elseif y_right == 0
			continue
		elseif signbit(y_left) != signbit(y_right)
			x_left = frequencies_hz[indexes[local_index]]
			x_right = frequencies_hz[indexes[local_index + 1]]
			root_hz = x_left - y_left * (x_right - x_left) / (y_right - y_left)
			push!(roots, (
				frequency_hz = Float64(root_hz),
				sampled_abs_im_z21_ohm = min(abs(y_left), abs(y_right)),
			))
		end
	end
	local_values[end] == 0 && push!(roots, (
		frequency_hz = frequencies_hz[indexes[end]],
		sampled_abs_im_z21_ohm = 0.0,
	))
	length(roots) == 1 || reject_d3_candidate(
		"notch.zero_crossing_count",
		"Notch window must contain exactly one Im(Z21 PTC) zero crossing; found $(length(roots)).";
		details = (roots = roots,),
	)
	notch = only(roots)
	notch.sampled_abs_im_z21_ohm <= maximum_value ||
		reject_d3_candidate(
			"notch.sampled_magnitude_gate",
			"Notch sampled |Im(Z21 PTC)| $(notch.sampled_abs_im_z21_ohm) Ohm exceeds $(maximum_value) Ohm.";
			details = (
				observed_abs_im_z21_ohm = notch.sampled_abs_im_z21_ohm,
				max_abs_im_z21_ohm = maximum_value,
			),
		)
	return notch
end

function _d3_plain_data(value)
	value isa AbstractDict && return Dict(String(key) => _d3_plain_data(item) for (key, item) in pairs(value))
	value isa NamedTuple && return NamedTuple{propertynames(value)}(Tuple(_d3_plain_data(item) for item in values(value)))
	value isa AbstractVector && return [_d3_plain_data(item) for item in value]
	value isa Tuple && return tuple((_d3_plain_data(item) for item in value)...)
	return value
end

function _compact_j_fit(result)
	return _d3_plain_data(Dict(
		"schema" => result["schema"],
		"fit_method" => result["fit_method"],
		"fit_domain" => result["fit_domain"],
		"status" => result["status"],
		"failure_codes" => result["failure_codes"],
		"failure_reasons" => result["failure_reasons"],
		"params" => get(result, "params", nothing),
		"background" => get(result, "background", nothing),
		"metrics" => get(result, "metrics", nothing),
		"diagnostics" => get(result, "diagnostics", nothing),
		"derived_poles" => get(result, "derived_poles", nothing),
		"model_convention" => result["model_convention"],
		"fit_window_hz" => result["fit_window_hz"],
		"background_windows_hz" => result["background_windows_hz"],
		"fixed_references" => result["fixed_references"],
		"channel_calibration" => result["channel_calibration"],
		"search" => result["search"],
		"algorithm" => result["algorithm"],
		"gates" => result["gates"],
		"normalization" => result["normalization"],
		"provenance" => result["provenance"],
	))
end

function _compact_channel_calibration(result)
	return _d3_plain_data(Dict(
		"schema" => result["schema"],
		"fit_method" => result["fit_method"],
		"fit_domain" => result["fit_domain"],
		"status" => result["status"],
		"failure_codes" => result["failure_codes"],
		"failure_reasons" => result["failure_reasons"],
		"params" => get(result, "params", nothing),
		"background" => get(result, "background", nothing),
		"metrics" => get(result, "metrics", nothing),
		"diagnostics" => get(result, "diagnostics", nothing),
		"model_convention" => result["model_convention"],
		"fit_window_hz" => result["fit_window_hz"],
		"background_windows_hz" => result["background_windows_hz"],
		"fixed_references" => result["fixed_references"],
		"algorithm" => result["algorithm"],
		"gates" => result["gates"],
		"normalization" => result["normalization"],
		"calibration_id" => result["calibration_id"],
		"calibration_summary_sha256" => get(result, "calibration_summary_sha256", nothing),
		"provenance" => result["provenance"],
	))
end

function _journal_d3_evaluation!(evaluator, candidate, record)
	isnothing(evaluator.journal_path) && return nothing
	payload = if record.status === :valid
		_d3_plain_data((
			candidate = candidate,
			status = "valid",
			metrics = record.metrics,
			diagnostics = record.diagnostics,
		))
	elseif record.status === :rejected
		_d3_plain_data((
			candidate = candidate,
			status = "rejected",
			code = record.code,
			reason = record.reason,
			details = record.details,
		))
	else
		error("Unsupported D3 evaluation record status $(record.status).")
	end
	open(evaluator.journal_path, "a") do io
		println(io, JSON3.write(payload))
	end
	return nothing
end

function evaluate_d3_slot(evaluator::D3SlotEvaluator, candidate; capture_traces = false)
	key = Tuple(candidate)
	try
		design = _candidate_design(evaluator.seed_design, candidate)
		settings = evaluator.settings
		slot_hz = Float64(design.slot_target_ghz) * D3_HZ_PER_GHZ
		notch_target_hz = Float64(design.notch_target_ghz) * D3_HZ_PER_GHZ
		candidate_identity = _candidate_identity(candidate)

		loaded_frequencies_hz = _slot_frequency_grid(
			slot_hz,
			settings.loaded_bare_half_width_hz,
			settings.frequency_step_hz,
		)
		loaded_grid_sha256 = _frequency_grid_sha256(loaded_frequencies_hz)
		pair_frequencies_hz = _slot_frequency_grid(
			slot_hz,
			settings.pair_trace_half_width_hz,
			settings.frequency_step_hz,
		)
		pair_grid_sha256 = _frequency_grid_sha256(pair_frequencies_hz)
		trace_identity = _d3_trace_identity(
			evaluator.case.id,
			design.id,
			candidate_identity,
			loaded_grid_sha256,
			pair_grid_sha256,
		)
		reference_contract_id = trace_identity.reference_contract_id
		filter_loaded_bare_reference_id = trace_identity.filter_loaded_bare_reference_id
		readout_loaded_bare_reference_id = trace_identity.readout_loaded_bare_reference_id
		filter_only_trace_id = trace_identity.filter_only_trace_id
		loaded_empty_feedline_trace_id = trace_identity.loaded_empty_feedline_trace_id
		calibration_id = trace_identity.calibration_id
		pair_measured_trace_id = trace_identity.pair_measured_trace_id
		pair_empty_feedline_trace_id = trace_identity.pair_empty_feedline_trace_id
		loaded_reference = _reference_trace!(evaluator, loaded_frequencies_hz)
		filter_plan = build_maxwell_diagonal_pair_feedline_plan(
			evaluator.case,
			design;
			filter_capacitance_fF = design.filter_to_line_capacitance_fF,
			feedline_length_um = settings.feedline_length_um,
			feedline = evaluator.feedline,
			hb_settings = evaluator.hb_settings,
		)
		filter_hb = _run_candidate_hb(
			evaluator,
			filter_plan,
			loaded_frequencies_hz,
			"Maxwell-diagonal pair filter loaded-bare",
		)
		filter_normalized = _normalized_s21(
			loaded_frequencies_hz,
			filter_hb.s21,
			loaded_reference,
			settings.min_reference_magnitude,
		)
		filter_mode = _fit_single_loaded_mode(
			loaded_frequencies_hz,
			filter_normalized,
			slot_hz,
			"Maxwell-diagonal pair filter loaded-bare",
			settings,
			require_slot_ownership = true,
		)
		port_plane = "JosephsonCircuits external ports, 50 Ohm reference"
		channel_calibration_provenance = Dict(
			"calibration_id" => calibration_id,
			"reference_contract_id" => reference_contract_id,
			"filter_only_trace_id" => filter_only_trace_id,
			"empty_feedline_trace_id" => loaded_empty_feedline_trace_id,
			"filter_loaded_bare_reference_id" => filter_loaded_bare_reference_id,
			"loaded_bare_reference_topology" => "maxwell_diagonal_lc_with_zeroed_offdiagonal_entries",
			"quantity_scope" => "lc_only",
			"port_plane" => port_plane,
			"feedline_source" => evaluator.feedline.source,
			"feedline_lc_derived_zo_ohm" => evaluator.feedline.zo_ohm,
			"feedline_target_zo_ohm" => evaluator.feedline.target_impedance_ohm,
			"feedline_r_per_m_ohm" => evaluator.feedline.r_per_m_ohm,
			"feedline_g_per_m_s" => evaluator.feedline.g_per_m_s,
			"feedline_r_status" => evaluator.feedline.r_status,
			"feedline_g_status" => evaluator.feedline.g_status,
			"feedline_loss_assumption" => evaluator.feedline.loss_assumption,
			"feedline_max_abs_impedance_error_ohm" => evaluator.feedline.max_abs_impedance_error_ohm,
			"feedline_max_abs_impedance_error_role" => evaluator.feedline.max_abs_impedance_error_role,
		)
		calibration_fit_half_width_hz = settings.channel_calibration_fit_half_width_hz
		calibration_background_inner_hz = settings.channel_calibration_background_inner_half_width_hz
		channel_calibration = calibrate_d3_channel_residue_s21(
			loaded_frequencies_hz,
			filter_hb.s21,
			loaded_reference;
			phasor_convention = "exp_plus_iomega_t",
			fit_window_hz = [
				filter_mode.frequency_hz - calibration_fit_half_width_hz,
				filter_mode.frequency_hz + calibration_fit_half_width_hz,
			],
			background_windows_hz = [
				[first(loaded_frequencies_hz), filter_mode.frequency_hz - calibration_background_inner_hz],
				[filter_mode.frequency_hz + calibration_background_inner_hz, last(loaded_frequencies_hz)],
			],
			fp_hz = filter_mode.frequency_hz,
			filter_loaded_linewidth_hz = filter_mode.bandwidth_hz,
			linear_ls_rcond = settings.linear_ls_rcond,
			min_reference_magnitude = settings.min_reference_magnitude,
			min_complex_r2 = settings.min_channel_calibration_complex_r2,
			min_abs_r2 = settings.min_channel_calibration_abs_r2,
			max_phase_rmse_rad = settings.max_channel_calibration_phase_rmse_rad,
			min_phase_magnitude = settings.min_phase_magnitude,
			provenance = channel_calibration_provenance,
		)
		channel_calibration["status"] == "success" || reject_d3_candidate(
			"channel_calibration.fit_gate",
			"Filter-only complex channel calibration rejected candidate: $(join(channel_calibration["failure_reasons"], "; ")).";
			details = (channel_calibration = _compact_channel_calibration(channel_calibration),),
		)
		readout_modes = Any[]
		readout_captures = Any[]
		for capacitance_fF in settings.readout_probe_capacitances_fF
			readout_probe_trace_id = "d3-readout-probe-hb|grid_sha256=$(loaded_grid_sha256)|capacitance_fF=$(bitstring(capacitance_fF))|design=$(design.id)|$(candidate_identity)"
			readout_plan = build_maxwell_diagonal_pair_feedline_plan(
				evaluator.case,
				design;
				filter_capacitance_fF = design.filter_to_line_capacitance_fF,
				readout_probe_capacitance_fF = capacitance_fF,
				feedline_length_um = settings.feedline_length_um,
				feedline = evaluator.feedline,
				hb_settings = evaluator.hb_settings,
			)
			readout_hb = _run_candidate_hb(
				evaluator,
				readout_plan,
				loaded_frequencies_hz,
				"Maxwell-diagonal pair readout loaded-bare probe $(capacitance_fF) fF",
			)
			readout_normalized = _normalized_s21(
				loaded_frequencies_hz,
				readout_hb.s21,
				loaded_reference,
				settings.min_reference_magnitude,
			)
			readout_mode = _fit_readout_probe_loaded_mode(
				loaded_frequencies_hz,
				readout_normalized,
				slot_hz,
				filter_mode.frequency_hz,
				"Maxwell-diagonal pair readout loaded-bare probe $(capacitance_fF) fF",
				settings,
			)
			push!(readout_modes, merge(readout_mode, (
				frequency_grid_sha256 = loaded_grid_sha256,
				measured_trace_id = readout_probe_trace_id,
				reference_trace_id = loaded_empty_feedline_trace_id,
			)))
			capture_traces && push!(readout_captures, (
				capacitance_fF = capacitance_fF,
				frequency_grid_sha256 = loaded_grid_sha256,
				measured_trace_id = readout_probe_trace_id,
				reference_trace_id = loaded_empty_feedline_trace_id,
				frequencies_hz = loaded_frequencies_hz,
				s21 = ComplexF64.(readout_hb.s21),
				reference_s21 = loaded_reference,
			))
		end
		readout_frequency_fit = _quadratic_zero_intercept(
			settings.readout_probe_capacitances_fF,
			[mode.frequency_hz for mode in readout_modes],
			settings.min_readout_frequency_extrapolation_r2,
			"readout weak-probe frequency",
			"readout_extrapolation.frequency",
		)
		readout_linewidth_fit = _zero_constrained_linewidth_fit(
			settings.readout_probe_capacitances_fF,
			[mode.bandwidth_hz for mode in readout_modes],
			settings.min_readout_linewidth_extrapolation_r2,
			"readout weak-probe total loaded linewidth",
			"readout_extrapolation.linewidth",
		)
		readout_frequency_hz = readout_frequency_fit.intercept
		readout_loaded_linewidth_hz = readout_linewidth_fit.intercept
		abs(readout_frequency_hz - slot_hz) <= settings.loaded_bare_ownership_half_width_hz ||
			reject_d3_candidate(
				"loaded_bare.readout_ownership_window",
				"Readout zero-probe frequency intercept lies outside its loaded-bare ownership window.";
				details = (
					readout_frequency_hz = readout_frequency_hz,
					slot_hz = slot_hz,
					ownership_half_width_hz = settings.loaded_bare_ownership_half_width_hz,
				),
			)
		readout_loaded_linewidth_hz == 0.0 || error(
			"Lossless Maxwell-diagonal readout zero-probe linewidth must be exactly zero.",
		)
		pair_reference = _reference_trace!(evaluator, pair_frequencies_hz)
		pair_plan = build_single_pair_feedline_plan(
			evaluator.case,
			design;
			capacitance_fF = design.filter_to_line_capacitance_fF,
			feedline_length_um = settings.feedline_length_um,
			feedline = evaluator.feedline,
			hb_settings = evaluator.hb_settings,
		)
		pair_hb = _run_candidate_hb(
			evaluator,
			pair_plan,
			pair_frequencies_hz,
			"isolated pair",
		)
		pair_normalized = _normalized_s21(
			pair_frequencies_hz,
			pair_hb.s21,
			pair_reference,
			settings.min_reference_magnitude,
		)
		fit_window = [slot_hz - settings.pair_fit_half_width_hz, slot_hz + settings.pair_fit_half_width_hz]
		background_windows = [
			[slot_hz - settings.pair_trace_half_width_hz, slot_hz - settings.pair_background_inner_half_width_hz],
			[slot_hz + settings.pair_background_inner_half_width_hz, slot_hz + settings.pair_trace_half_width_hz],
		]
		filter_loaded_linewidth_hz = filter_mode.bandwidth_hz
		j_fit = fit_d3_through_line_s21(
			pair_frequencies_hz,
			pair_hb.s21,
			pair_reference;
			phasor_convention = "exp_plus_iomega_t",
			fit_window_hz = fit_window,
			background_windows_hz = background_windows,
			fp_hz = filter_mode.frequency_hz,
			fr_hz = readout_frequency_hz,
			filter_loaded_linewidth_hz = filter_loaded_linewidth_hz,
			readout_loaded_linewidth_hz = readout_loaded_linewidth_hz,
			channel_calibration = channel_calibration,
			j_bounds_hz = collect(settings.j_bounds_hz),
			j_seeds_hz = settings.j_seeds_hz,
			linear_ls_rcond = settings.linear_ls_rcond,
			least_squares_max_nfev = settings.least_squares_max_nfev,
			least_squares_ftol = settings.least_squares_ftol,
			least_squares_xtol = settings.least_squares_xtol,
			least_squares_gtol = settings.least_squares_gtol,
			least_squares_diff_step = settings.least_squares_diff_step,
			min_successful_seed_count = settings.min_successful_seed_count,
			min_successful_seed_fraction = settings.min_successful_seed_fraction,
			near_optimal_mse_ratio = settings.near_optimal_mse_ratio,
			near_optimal_mse_absolute_tolerance = settings.near_optimal_mse_absolute_tolerance,
			min_winning_seed_count = settings.min_winning_seed_count,
			min_reference_magnitude = settings.min_reference_magnitude,
			min_complex_r2 = settings.min_complex_r2,
			min_abs_r2 = settings.min_abs_r2,
			max_phase_rmse_rad = settings.max_phase_rmse_rad,
			min_phase_magnitude = settings.min_phase_magnitude,
			min_normalized_bound_margin = settings.min_normalized_bound_margin,
			max_seed_spread_hz = settings.max_seed_spread_hz,
			provenance = Dict(
				"reference_contract_id" => reference_contract_id,
				"measured_trace_id" => pair_measured_trace_id,
				"empty_feedline_trace_id" => pair_empty_feedline_trace_id,
				"filter_loaded_bare_reference_id" => filter_loaded_bare_reference_id,
				"readout_loaded_bare_reference_id" => readout_loaded_bare_reference_id,
				"loaded_bare_reference_topology" => "maxwell_diagonal_lc_with_zeroed_offdiagonal_entries",
				"quantity_scope" => "lc_only",
				"pair_assignment_id" => trace_identity.pair_assignment_id,
				"port_plane" => port_plane,
				"feedline_source" => evaluator.feedline.source,
				"feedline_lc_derived_zo_ohm" => evaluator.feedline.zo_ohm,
				"feedline_target_zo_ohm" => evaluator.feedline.target_impedance_ohm,
				"feedline_r_per_m_ohm" => evaluator.feedline.r_per_m_ohm,
				"feedline_g_per_m_s" => evaluator.feedline.g_per_m_s,
				"feedline_r_status" => evaluator.feedline.r_status,
				"feedline_g_status" => evaluator.feedline.g_status,
				"feedline_loss_assumption" => evaluator.feedline.loss_assumption,
				"feedline_max_abs_impedance_error_ohm" => evaluator.feedline.max_abs_impedance_error_ohm,
				"feedline_max_abs_impedance_error_role" => evaluator.feedline.max_abs_impedance_error_role,
			),
		)
		j_fit["status"] == "success" || reject_d3_candidate(
			"j_fit.fit_gate",
			"Complex S21 J fit rejected candidate: $(join(j_fit["failure_reasons"], "; ")).";
			details = (
				filter_loaded_bare_hz = filter_mode.frequency_hz,
				filter_loaded_linewidth_hz = filter_mode.bandwidth_hz,
				readout_loaded_bare_hz = readout_frequency_hz,
				readout_loaded_linewidth_hz = readout_loaded_linewidth_hz,
				loaded_bare_center_hz = (filter_mode.frequency_hz + readout_frequency_hz) / 2,
				j_fit = _compact_j_fit(j_fit),
			),
		)

		pair_fit_mask = abs.(pair_frequencies_hz .- slot_hz) .<= settings.pair_fit_half_width_hz
		pair_vector_result = fit_vector_s21(
			pair_frequencies_hz[pair_fit_mask],
			pair_normalized[pair_fit_mask];
			n_resonators = 2,
			bg_poles = settings.vector_bg_poles,
			min_q = settings.vector_min_q,
			restrict_to_input_span = true,
		)
		pair_vector_modes = _require_vector_fit(pair_vector_result, 2, "paired pole cross-check", settings)
		vector_poles_hz = sort(Float64[mode["fr_hz"] for mode in pair_vector_modes])
		model_poles_hz = sort(Float64[pole["frequency_hz"] for pole in j_fit["derived_poles"]])
		maximum(abs.(vector_poles_hz .- model_poles_hz)) <= settings.max_vector_pole_disagreement_hz ||
			reject_d3_candidate(
				"vector.pole_disagreement_gate",
				"Complex J-fit poles disagree with independent vector-fit poles.";
				details = (
					vector_poles_hz = vector_poles_hz,
					model_poles_hz = model_poles_hz,
					max_vector_pole_disagreement_hz = settings.max_vector_pole_disagreement_hz,
				),
			)
		loaded_bare_center_hz = (filter_mode.frequency_hz + readout_frequency_hz) / 2
		model_paired_pole_center_hz = sum(model_poles_hz) / 2
		isapprox(model_paired_pole_center_hz, loaded_bare_center_hz; atol = 1.0e-6, rtol = 0.0) ||
			error("J-only two-mode poles must preserve the loaded-bare center.")
		vector_paired_pole_center_hz = sum(vector_poles_hz) / 2
		pair_pole_center_offset_hz = vector_paired_pole_center_hz - loaded_bare_center_hz
		abs(pair_pole_center_offset_hz) <= settings.max_pair_pole_center_offset_hz ||
			reject_d3_candidate(
			"vector.pair_center_offset_gate",
			"Paired vector-pole center differs from Maxwell-diagonal loaded-bare center by $(pair_pole_center_offset_hz) Hz.";
			details = (
				loaded_bare_center_hz = loaded_bare_center_hz,
				vector_paired_pole_center_hz = vector_paired_pole_center_hz,
				pair_pole_center_offset_hz = pair_pole_center_offset_hz,
			),
		)

		notch_frequencies_hz = _slot_frequency_grid(
			notch_target_hz,
			settings.notch_half_width_hz,
			settings.frequency_step_hz,
		)
		intrinsic_plan = build_intrinsic_pair_plan(
			evaluator.case,
			design;
			hb_settings = evaluator.hb_settings,
		)
		intrinsic_hb = _run_candidate_hb(
			evaluator,
			intrinsic_plan,
			notch_frequencies_hz,
			"intrinsic notch";
			compensate_port_indices = (1, 2),
			removal_intent = :intrinsic_pair_probe_scaffold,
		)
		notch = _owned_notch_zero(
			notch_frequencies_hz,
			imag.(intrinsic_hb.z21_ptc),
			notch_target_hz,
			settings.notch_half_width_hz,
			settings.max_notch_abs_im_z21_ohm,
		)
		intrinsic_wide_trace = if capture_traces
			wide_capture = _intrinsic_wide_capture_grid(
				design,
				notch_target_hz,
				filter_mode.frequency_hz,
				settings.frequency_step_hz,
			)
			wide_hb = _run_candidate_hb(
				evaluator,
				intrinsic_plan,
				wide_capture.frequencies_hz,
				"intrinsic wide final capture";
				compensate_port_indices = (1, 2),
				removal_intent = :intrinsic_pair_probe_scaffold,
			)
			(
				frequency_grid_sha256 = _frequency_grid_sha256(wide_capture.frequencies_hz),
				frequencies_hz = wide_capture.frequencies_hz,
				z21_ptc = ComplexF64.(wide_hb.z21_ptc),
				range_provenance = wide_capture.range_provenance,
			)
		else
			nothing
		end

		metrics = (
			filter_loaded_bare_hz = filter_mode.frequency_hz,
			readout_loaded_bare_hz = readout_frequency_hz,
			readout_minus_filter_detuning_hz = readout_frequency_hz - filter_mode.frequency_hz,
			loaded_bare_center_hz = loaded_bare_center_hz,
			model_paired_pole_center_hz = model_paired_pole_center_hz,
			vector_paired_pole_center_hz = vector_paired_pole_center_hz,
			pair_pole_center_offset_hz = pair_pole_center_offset_hz,
			notch_hz = notch.frequency_hz,
			filter_loaded_linewidth_hz = filter_loaded_linewidth_hz,
			j_hz = Float64(j_fit["params"]["j_hz"]),
		)
		diagnostics = (
			status = "success",
			design = design,
			filter_loaded_bare = filter_mode,
			readout_probe_modes = readout_modes,
			readout_zero_probe_frequency_fit = readout_frequency_fit,
			readout_zero_probe_linewidth_fit = readout_linewidth_fit,
			readout_loaded_linewidth_hz = readout_loaded_linewidth_hz,
			reference_contract_id = reference_contract_id,
			filter_loaded_bare_reference_id = filter_loaded_bare_reference_id,
			readout_loaded_bare_reference_id = readout_loaded_bare_reference_id,
			loaded_frequency_grid_sha256 = loaded_grid_sha256,
			pair_frequency_grid_sha256 = pair_grid_sha256,
			channel_calibration = _compact_channel_calibration(channel_calibration),
			j_fit = _compact_j_fit(j_fit),
			vector_crosscheck_poles_hz = vector_poles_hz,
			notch = notch,
		)
		j_fit_trace = j_fit["fit_trace"]
		traces = capture_traces ? (
			filter = (
				frequency_grid_sha256 = loaded_grid_sha256,
				measured_trace_id = filter_only_trace_id,
				reference_trace_id = loaded_empty_feedline_trace_id,
				frequencies_hz = loaded_frequencies_hz,
				s21 = ComplexF64.(filter_hb.s21),
				reference_s21 = loaded_reference,
			),
			readout_probes = readout_captures,
			pair = (
				frequency_grid_sha256 = pair_grid_sha256,
				measured_trace_id = pair_measured_trace_id,
				reference_trace_id = pair_empty_feedline_trace_id,
				frequencies_hz = pair_frequencies_hz,
				s21 = ComplexF64.(pair_hb.s21),
				reference_s21 = pair_reference,
				fit_frequencies_hz = Float64.(j_fit_trace["frequency_hz"]),
				fit_normalized_s21 = ComplexF64.(
					Float64.(j_fit_trace["normalized_s21_real"]) .+
					im .* Float64.(j_fit_trace["normalized_s21_imag"]),
				),
				fitted_s21 = ComplexF64.(
					Float64.(j_fit_trace["fitted_s21_real"]) .+
					im .* Float64.(j_fit_trace["fitted_s21_imag"]),
				),
			),
			intrinsic = (
				frequencies_hz = notch_frequencies_hz,
				z21_ptc = ComplexF64.(intrinsic_hb.z21_ptc),
			),
			intrinsic_wide = intrinsic_wide_trace,
		) : nothing
		record = (
			status = :valid,
			metrics = metrics,
			diagnostics = diagnostics,
			traces = traces,
		)
		evaluator.records[key] = record
		_journal_d3_evaluation!(evaluator, candidate, record)
		return record
	catch exception
		if exception isa D3CandidateRejected
			record = (
				status = :rejected,
				code = exception.code,
				reason = exception.reason,
				details = exception.details,
			)
			evaluator.records[key] = record
			_journal_d3_evaluation!(evaluator, candidate, record)
			return record
		end
		rethrow()
	end
end
