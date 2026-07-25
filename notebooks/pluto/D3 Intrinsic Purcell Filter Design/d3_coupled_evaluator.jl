# This file owns the physical single-slot evaluator used by the D3 coupled
# optimizer. It rebuilds and solves the real HB circuits for every geometry,
# extracts coupling-off references, fits complex S21 for J, and returns physical
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
# https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/readout/coupling-off-readout-filter-initial-references.qmd
# https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/readout/bare-vs-hybridized-readout-filter-modes.qmd
# https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/simulation/port-reference-impedance-semantics.qmd
# https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/simulation/port-termination-compensation.qmd

import SHA
using LinearAlgebra

const D3_Z21_PTC_FACTORIZED_ENDPOINT_COMPOSITION =
	"factorized_readout_Z21_R_to_GND_C0r_plus_Cr1_plus_Cr2_qubit_dynamic_nodes_absent"
const D3_Z21_PTC_CONNECTED_ENDPOINT_COMPOSITION =
	"connected_node_preserving_Cr_homotopy"
const D3_Z21_PTC_ENDPOINT_COMPOSITION_PROVENANCE =
	"lambda0_factorized_readout_Z21_R_to_GND_C0r_plus_Cr1_plus_Cr2_qubit_dynamic_nodes_absent_lambda_positive_connected_node_preserving_Cr_homotopy"

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

function _d3_system_c_sweep_settings(value)
	value isa AbstractDict || error("system_c_s21_lj_sweep must be a mapping.")
	settings = Dict(String(key) => item for (key, item) in pairs(value))
	expected = Set([
		"q_diagonal_identification_offsets_from_slot_hz", "frequency_step_hz",
		"local_pole_half_window_hz", "affine_nuisance_wing_hz", "s21_sigma",
		"physical_seed_normalized_offsets", "physical_bounds", "nuisance_bounds",
		"numerical_tolerances", "gates", "stability_lj_subranges_1based_inclusive",
		"stability_frequency_trim_fraction", "stability_frequency_grid_stride",
		"stability_bound_inset_fraction",
		"bright_vf_min_residue_response_ratio", "max_vf_pole_disagreement_hz",
		"max_vf_linewidth_disagreement_hz",
	])
	Set(keys(settings)) == expected || error("system_c_s21_lj_sweep keys do not match the v8 contract.")
	offsets = Float64.(settings["q_diagonal_identification_offsets_from_slot_hz"])
	offsets == [-6e8, -4e8, -2e8, -1e8, 1e8, 2e8, 4e8, 6e8] || error(
		"System-C q-diagonal identification samples must symmetrically bracket the Slot from ±100 MHz through ±600 MHz without sampling the exact Slot center.",
	)
	seed_offsets = Float64.(settings["physical_seed_normalized_offsets"])
	length(seed_offsets) >= 5 && length(unique(seed_offsets)) == length(seed_offsets) || error(
		"System-C global fit requires at least five distinct physical seed offsets.",
	)
	all(value -> isfinite(value) && -1 < value < 1, seed_offsets) || error(
		"System-C physical seed offsets must be finite and strictly inside (-1, 1).",
	)
	positive = Float64[
		settings["frequency_step_hz"],
		settings["local_pole_half_window_hz"], settings["affine_nuisance_wing_hz"],
		settings["s21_sigma"], settings["bright_vf_min_residue_response_ratio"],
		settings["max_vf_pole_disagreement_hz"], settings["max_vf_linewidth_disagreement_hz"],
	]
	all(value -> isfinite(value) && value > 0, positive) || error(
		"System-C sweep frequencies, nominal L_J, S21 sigma, and VF gates must be finite and positive.",
	)
	settings["frequency_step_hz"] == 2e5 || error("System-C initial frequency step must be 200 kHz.")
	settings["local_pole_half_window_hz"] == 1e8 || error("System-C local pole half-window must be 100 MHz.")
	trim = Float64(settings["stability_frequency_trim_fraction"])
	0 < trim < 0.5 || error("System-C stability trim fraction must lie in (0, 0.5).")
	Int(settings["stability_frequency_grid_stride"]) >= 2 || error(
		"System-C stability frequency-grid stride must be at least two.",
	)
	bound_inset = Float64(settings["stability_bound_inset_fraction"])
	0 < bound_inset < 0.5 || error("System-C stability bound inset fraction must lie in (0, 0.5).")
	subranges = settings["stability_lj_subranges_1based_inclusive"]
	length(subranges) >= 2 || error("System-C stability requires overlapping lower/upper L_J subranges.")
	all(range -> length(range) == 2 && Int(range[2]) - Int(range[1]) + 1 >= 5, subranges) || error(
		"Every System-C stability L_J subrange must contain at least five traces.",
	)
	return settings
end

struct D3SlotEvaluationSettings
	frequency_step_hz::Float64
	feedline_length_um::Float64
	reference_scan_half_width_hz::Float64
	off_reference_ownership_half_width_hz::Float64
	pair_trace_half_width_hz::Float64
	pair_fit_half_width_hz::Float64
	pair_background_inner_half_width_hz::Float64
	notch_half_width_hz::Float64
	z21_ptc_zero_frequency_tolerance_hz::Float64
	z21_ptc_zero_max_iterations::Int
	max_z21_ptc_zero_abs_re_ohm::Float64
	max_z21_ptc_zero_abs_im_ohm::Float64
	max_z21_ptc_zero_abs_complex_ohm::Float64
	z21_ptc_coupling_fractions::Vector{Float64}
	z21_ptc_max_continuation_step_hz::Float64
	z21_ptc_require_same_orientation::Bool
	c_probe_capacitances_fF::Vector{Float64}
	min_readout_frequency_extrapolation_r2::Float64
	min_readout_linewidth_extrapolation_r2::Float64
	qubit_local_half_width_hz::Float64
	qubit_root_trust_half_width_hz::Float64
	min_g_extrapolation_r2::Float64
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
	vector_max_iterations::Int
	vector_min_q::Float64
	max_vector_rms_error::Float64
	max_vector_pole_disagreement_hz::Float64
	max_pair_pole_center_offset_hz::Float64
	scalar_pole_min_samples_per_linewidth::Float64
	scalar_pole_level0_sampling_safety_factor::Float64
	scalar_pole_refinement_factor::Int
	scalar_pole_min_frequency_step_hz::Float64
	scalar_pole_max_source_samples_per_level::Int
	scalar_pole_local_half_window_linewidths::Float64
	scalar_pole_min_half_window_hz::Float64
	scalar_pole_max_half_window_hz::Float64
	scalar_pole_window_scales::Vector{Float64}
	scalar_pole_bg_pole_checks::Vector{Int}
	scalar_pole_max_frequency_shift_abs_hz::Float64
	scalar_pole_max_frequency_shift_fraction::Float64
	scalar_pole_max_linewidth_shift_abs_hz::Float64
	scalar_pole_max_linewidth_shift_fraction::Float64
	scalar_pole_min_residue_response_ratio::Float64
	scalar_pole_min_nearby_separation_linewidths::Float64
	scalar_pole_max_complex_rms_error::Float64
	scalar_pole_max_local_complex_rms_error::Float64
	scalar_pole_max_abs_error::Float64
	system_c_s21_lj_sweep::Dict{String,Any}

	function D3SlotEvaluationSettings(;
		frequency_step_hz,
		feedline_length_um,
		reference_scan_half_width_hz,
		off_reference_ownership_half_width_hz,
		pair_trace_half_width_hz,
		pair_fit_half_width_hz,
		pair_background_inner_half_width_hz,
		notch_half_width_hz,
		z21_ptc_zero_frequency_tolerance_hz,
		z21_ptc_zero_max_iterations,
		max_z21_ptc_zero_abs_re_ohm,
		max_z21_ptc_zero_abs_im_ohm,
		max_z21_ptc_zero_abs_complex_ohm,
		z21_ptc_coupling_fractions,
		z21_ptc_max_continuation_step_hz,
		z21_ptc_require_same_orientation,
		c_probe_capacitances_fF,
		min_readout_frequency_extrapolation_r2,
		min_readout_linewidth_extrapolation_r2,
		qubit_local_half_width_hz,
		qubit_root_trust_half_width_hz,
		min_g_extrapolation_r2,
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
		vector_max_iterations,
		vector_min_q,
		max_vector_rms_error,
		max_vector_pole_disagreement_hz,
		max_pair_pole_center_offset_hz,
		scalar_pole_min_samples_per_linewidth,
		scalar_pole_level0_sampling_safety_factor,
		scalar_pole_refinement_factor,
		scalar_pole_min_frequency_step_hz,
		scalar_pole_max_source_samples_per_level,
		scalar_pole_local_half_window_linewidths,
		scalar_pole_min_half_window_hz,
		scalar_pole_max_half_window_hz,
		scalar_pole_window_scales,
		scalar_pole_bg_pole_checks,
		scalar_pole_max_frequency_shift_abs_hz,
		scalar_pole_max_frequency_shift_fraction,
		scalar_pole_max_linewidth_shift_abs_hz,
		scalar_pole_max_linewidth_shift_fraction,
		scalar_pole_min_residue_response_ratio,
		scalar_pole_min_nearby_separation_linewidths,
		scalar_pole_max_complex_rms_error,
		scalar_pole_max_local_complex_rms_error,
		scalar_pole_max_abs_error,
		system_c_s21_lj_sweep,
	)
		strictly_positive_values = Float64[
			frequency_step_hz,
			feedline_length_um,
			reference_scan_half_width_hz,
			qubit_local_half_width_hz,
			pair_trace_half_width_hz,
			pair_fit_half_width_hz,
			pair_background_inner_half_width_hz,
			notch_half_width_hz,
			z21_ptc_max_continuation_step_hz,
			min_reference_magnitude,
		]
		all(value -> isfinite(value) && value > 0, strictly_positive_values) ||
			error("D3 scan widths, step, feedline length, and reference division floor must be finite and positive.")
		nonnegative_gate_values = Float64[
			off_reference_ownership_half_width_hz,
			max_z21_ptc_zero_abs_re_ohm,
			max_z21_ptc_zero_abs_im_ohm,
			max_z21_ptc_zero_abs_complex_ohm,
			max_seed_spread_hz,
			vector_min_q,
			max_vector_rms_error,
			max_vector_pole_disagreement_hz,
			max_pair_pole_center_offset_hz,
			qubit_root_trust_half_width_hz,
		]
		all(value -> isfinite(value) && value >= 0, nonnegative_gate_values) ||
			error("D3 max/min gates that admit exact equality must be finite and non-negative.")
		zero_tolerance_hz = Float64(z21_ptc_zero_frequency_tolerance_hz)
		isfinite(zero_tolerance_hz) && zero_tolerance_hz > 0 ||
			error("Z21 PTC zero frequency tolerance must be finite and positive.")
		zero_max_iterations = Int(z21_ptc_zero_max_iterations)
		zero_max_iterations > 0 || error("Z21 PTC zero max iterations must be positive.")
		coupling_fractions = Float64.(collect(z21_ptc_coupling_fractions))
		coupling_fractions == [0.0, 0.25, 0.5, 0.75, 1.0] || error(
			"Z21 PTC coupling fractions must be exactly [0, 0.25, 0.5, 0.75, 1].",
		)
		z21_ptc_require_same_orientation isa Bool || error(
			"Z21 PTC same-orientation condition must be Boolean.",
		)
		off_reference_ownership_half_width_hz <= reference_scan_half_width_hz ||
			error("Off-reference ownership window must fit inside its reference scan.")
		pair_fit_half_width_hz < pair_background_inner_half_width_hz < pair_trace_half_width_hz ||
			error("D3 pair windows must satisfy fit < background inner edge < trace half width.")
		0 < channel_calibration_fit_half_width_hz < channel_calibration_background_inner_half_width_hz < reference_scan_half_width_hz ||
			error("D3 channel-calibration windows must satisfy fit < background inner edge < reference scan half width.")
		probe_capacitances = Float64.(collect(c_probe_capacitances_fF))
		length(probe_capacitances) >= 5 || error("C_probe->0 frequency extrapolation requires at least five finite positive C_probe points.")
		all(value -> isfinite(value) && value > 0, probe_capacitances) ||
			error("Observation-probe capacitances must be finite and positive.")
		all(>(0), diff(probe_capacitances)) ||
			error("Observation-probe capacitances must be strictly increasing.")
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
			min_g_extrapolation_r2,
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
		vector_max_iterations isa Integer && !(vector_max_iterations isa Bool) || error(
			"Vector-fit maximum iterations must be an integer.",
		)
		Int(vector_max_iterations) > 0 || error("Vector-fit maximum iterations must be positive.")
		scalar_positive_values = Float64[
			scalar_pole_min_samples_per_linewidth,
			scalar_pole_level0_sampling_safety_factor,
			scalar_pole_min_frequency_step_hz,
			scalar_pole_local_half_window_linewidths,
			scalar_pole_min_half_window_hz,
			scalar_pole_max_half_window_hz,
			scalar_pole_max_frequency_shift_abs_hz,
			scalar_pole_max_frequency_shift_fraction,
			scalar_pole_max_linewidth_shift_abs_hz,
			scalar_pole_max_linewidth_shift_fraction,
			scalar_pole_min_residue_response_ratio,
			scalar_pole_min_nearby_separation_linewidths,
			scalar_pole_max_complex_rms_error,
			scalar_pole_max_local_complex_rms_error,
			scalar_pole_max_abs_error,
		]
		all(value -> isfinite(value) && value > 0, scalar_positive_values) || error(
			"Scalar-pole sampling, stability, residue, and residual conditions must be finite and positive.",
		)
		Int(scalar_pole_refinement_factor) >= 2 || error(
			"Scalar-pole refinement factor must be an integer of at least two.",
		)
		scalar_source_sample_limit = Int(scalar_pole_max_source_samples_per_level)
		scalar_source_sample_limit >= 2 || error(
			"Scalar-pole source-sample limit must admit at least two samples per level.",
		)
		scalar_pole_min_half_window_hz <= scalar_pole_max_half_window_hz || error(
			"Scalar-pole local half-window bounds must be ordered.",
		)
		window_scales = Float64.(collect(scalar_pole_window_scales))
		window_scales == [0.8, 1.0, 1.2] || error(
			"Scalar-pole window scales must be exactly [0.8, 1.0, 1.2].",
		)
		bg_checks = Int.(collect(scalar_pole_bg_pole_checks))
		bg_checks == [1, 2] || error(
			"Scalar-pole background-pole checks must be exactly [1, 2].",
		)
		Int(vector_bg_poles) in bg_checks || error(
			"The nominal vector-fit background order must be present in scalar-pole stability checks.",
		)
		return new(
			Float64(frequency_step_hz),
			Float64(feedline_length_um),
			Float64(reference_scan_half_width_hz),
			Float64(off_reference_ownership_half_width_hz),
			Float64(pair_trace_half_width_hz),
			Float64(pair_fit_half_width_hz),
			Float64(pair_background_inner_half_width_hz),
			Float64(notch_half_width_hz),
			zero_tolerance_hz,
			zero_max_iterations,
			Float64(max_z21_ptc_zero_abs_re_ohm),
			Float64(max_z21_ptc_zero_abs_im_ohm),
			Float64(max_z21_ptc_zero_abs_complex_ohm),
			coupling_fractions,
			Float64(z21_ptc_max_continuation_step_hz),
			Bool(z21_ptc_require_same_orientation),
			probe_capacitances,
			Float64(min_readout_frequency_extrapolation_r2),
			Float64(min_readout_linewidth_extrapolation_r2),
			Float64(qubit_local_half_width_hz),
			Float64(qubit_root_trust_half_width_hz),
			Float64(min_g_extrapolation_r2),
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
			Int(vector_max_iterations),
			Float64(vector_min_q),
			Float64(max_vector_rms_error),
			Float64(max_vector_pole_disagreement_hz),
			Float64(max_pair_pole_center_offset_hz),
			Float64(scalar_pole_min_samples_per_linewidth),
			Float64(scalar_pole_level0_sampling_safety_factor),
			Int(scalar_pole_refinement_factor),
			Float64(scalar_pole_min_frequency_step_hz),
			scalar_source_sample_limit,
			Float64(scalar_pole_local_half_window_linewidths),
			Float64(scalar_pole_min_half_window_hz),
			Float64(scalar_pole_max_half_window_hz),
			window_scales,
			bg_checks,
			Float64(scalar_pole_max_frequency_shift_abs_hz),
			Float64(scalar_pole_max_frequency_shift_fraction),
			Float64(scalar_pole_max_linewidth_shift_abs_hz),
			Float64(scalar_pole_max_linewidth_shift_fraction),
			Float64(scalar_pole_min_residue_response_ratio),
			Float64(scalar_pole_min_nearby_separation_linewidths),
			Float64(scalar_pole_max_complex_rms_error),
			Float64(scalar_pole_max_local_complex_rms_error),
			Float64(scalar_pole_max_abs_error),
			_d3_system_c_sweep_settings(system_c_s21_lj_sweep),
		)
	end
end

function _qubit_common_coordinate_weights(qubit::D3FloatingQubitNominal, loading_state)
	state = Symbol(loading_state)
	state in (:bare_component, :off_reference) || error(
		"Qubit common-coordinate weights require bare_component or off_reference state.",
	)
	c1 = qubit.C01_fF + (state === :off_reference ? qubit.Cr1_fF : 0.0)
	c2 = qubit.C02_fF + (state === :off_reference ? qubit.Cr2_fF : 0.0)
	total = c1 + c2
	isfinite(total) && total > 0 || error("Qubit common-coordinate capacitance must be finite and positive.")
	return (alpha = c1 / total, beta = c2 / total, capacitances_fF = (c1, c2))
end

"""Build the compensated scalar differential-admittance response from an HB run."""
function _d3_differential_y_response(
	hb;
	all_ports,
	island_ports,
	alpha,
	beta,
	measurement_view,
)
	ports = Int.(collect(all_ports))
	islands = Int.(collect(island_ports))
	length(islands) == 2 && length(unique(islands)) == 2 ||
		error("Differential-Y extraction requires exactly two distinct island ports.")
	all(port -> port in ports, islands) || error("Island ports must be present in all_ports.")
	raw_y = PortMatrixPostProcessing.zero_mode_y_matrix_stack(hb.result; ports = ports)
	compensated = PortMatrixPostProcessing.apply_port_termination_compensation(
		raw_y,
		hb.compiled;
		compensate_port_indices = islands,
		removal_intent = :remove_island_observation_shunts_only,
	)
	positions = [only(findall(==(string(port)), compensated.labels)) for port in islands]
	transform = PortMatrixPostProcessing.common_differential_transform(
		length(ports), positions[1], positions[2]; alpha = alpha, beta = beta,
	)
	labels = copy(compensated.labels)
	labels[positions[1]] = "qubit_common"
	labels[positions[2]] = "qubit_differential"
	transformed = PortMatrixPostProcessing.apply_coordinate_transform(
		compensated,
		transform;
		labels = labels,
	)
	differential_index = positions[2]
	drop = [index for index in eachindex(labels) if index != differential_index]
	condition_numbers = Float64[]
	for frequency_index in axes(transformed.values, 3)
		block = transformed.values[drop, drop, frequency_index]
		condition_number = isempty(drop) ? 1.0 : cond(block)
		isfinite(condition_number) || error(
			"Differential-Y Kron eliminated block is singular at $(transformed.frequencies_hz[frequency_index]) Hz.",
		)
		push!(condition_numbers, condition_number)
	end
	reduced = PortMatrixPostProcessing.kron_reduce(transformed; keep_indices = [differential_index])
	ydiff = vec(reduced.values[1, 1, :])
	all(isfinite, real.(ydiff)) && all(isfinite, imag.(ydiff)) ||
		error("Differential-Y response contains non-finite values.")
	shunt_evidence = PortMatrixPostProcessing.compiled_port_shunt_evidence(
		hb.compiled; port_indices = islands,
	)
	return (
		frequencies_hz = Float64.(reduced.frequencies_hz),
		ydiff_siemens = ComplexF64.(ydiff),
		provenance = (
			measurement_view = String(measurement_view),
			matrix_source = "JosephsonCircuits_returnZ_zero_mode_full_matrix_then_Z_inverse",
			all_ports = ports,
			feedline_ports_retained = [port for port in ports if !(port in islands)],
			compensated_island_ports = islands,
			port_shunt_evidence = shunt_evidence,
			coordinate_transform = (
				formula = "A^-T*Y*A^-1",
				alpha = Float64(alpha),
				beta = Float64(beta),
				labels = labels,
			),
			kron = (
				kept_coordinate = "qubit_differential",
				eliminated_coordinates = labels[drop],
				eliminated_block_condition_numbers = condition_numbers,
			),
		),
	)
end

"""Select the unique positive-slope Im(Ydiff)=0 crossing in a trust interval."""
function _extract_d3_unique_positive_slope_y_root_in_trust_interval(
	frequencies_hz,
	ydiff_siemens,
	anchor_hz,
	trust_half_width_hz;
	stage_label,
)
	frequencies = Float64.(collect(frequencies_hz))
	ydiff = ComplexF64.(collect(ydiff_siemens))
	length(frequencies) == length(ydiff) && length(frequencies) >= 2 ||
		error("Differential-Y root extraction requires matching traces with at least two points.")
	all(diff(frequencies) .> 0) || error("Differential-Y frequencies must be strictly increasing.")
	all(isfinite, frequencies) && all(isfinite, real.(ydiff)) && all(isfinite, imag.(ydiff)) ||
			error("Differential-Y root extraction requires finite inputs.")
	anchor = Float64(anchor_hz)
	trust_half_width = Float64(trust_half_width_hz)
	isfinite(anchor) && isfinite(trust_half_width) && anchor > 0 && trust_half_width >= 0 ||
		error("Differential-Y root anchor and trust half-width are invalid.")
	trust_interval_hz = (anchor - trust_half_width, anchor + trust_half_width)
	candidates = NamedTuple[]
	for left_index in 1:(length(frequencies) - 1)
		right_index = left_index + 1
		y_left = imag(ydiff[left_index])
		y_right = imag(ydiff[right_index])
		(y_left == 0 || y_right == 0 || signbit(y_left) != signbit(y_right)) || continue
		delta_y = y_right - y_left
		delta_f = frequencies[right_index] - frequencies[left_index]
		delta_y == 0 && continue
		fraction = -y_left / delta_y
		0 <= fraction <= 1 || continue
		root_hz = frequencies[left_index] + fraction * delta_f
		slope_s_per_hz = delta_y / delta_f
		re_y_siemens = real(ydiff[left_index]) + fraction * (real(ydiff[right_index]) - real(ydiff[left_index]))
		any(candidate -> candidate.root_hz == root_hz, candidates) && continue
		push!(candidates, (
			left_index = left_index,
			right_index = right_index,
			bracket_hz = (frequencies[left_index], frequencies[right_index]),
			root_hz = root_hz,
			slope_s_per_hz = slope_s_per_hz,
			re_y_siemens = re_y_siemens,
			anchor_distance_hz = abs(root_hz - anchor),
			positive_slope = slope_s_per_hz > 0,
		))
	end
	positive = [candidate for candidate in candidates if candidate.positive_slope]
	in_window = [
		candidate for candidate in positive
		if trust_interval_hz[1] <= candidate.root_hz <= trust_interval_hz[2]
	]
	length(in_window) == 1 || reject_d3_candidate(
		isempty(in_window) ? "admittance.no_root_in_trust_interval" : "admittance.multiple_roots_in_trust_interval",
		isempty(in_window) ?
			"$(stage_label) has no positive-slope Im(Ydiff)=0 root in the declared trust interval." :
			"$(stage_label) has multiple positive-slope Im(Ydiff)=0 roots in the declared trust interval.";
		details = (
			anchor_hz = anchor,
			trust_half_width_hz = trust_half_width,
			trust_interval_hz = trust_interval_hz,
			all_sign_change_candidates = candidates,
			positive_slope_candidates = positive,
			in_trust_interval_candidates = in_window,
		),
	)
	selected = only(in_window)
	neighbor_start = max(1, selected.left_index - 2)
	neighbor_stop = min(length(frequencies), selected.right_index + 2)
	neighbor_indices = collect(neighbor_start:neighbor_stop)
	neighbor_frequencies = frequencies[neighbor_indices]
	neighbor_y = ydiff[neighbor_indices]
	centered_frequency_hz = neighbor_frequencies .- selected.root_hz
	linear_design = hcat(ones(length(neighbor_indices)), centered_frequency_hz)
	linear_coefficients = linear_design \ imag.(neighbor_y)
	linear_fitted = linear_design * linear_coefficients
	linear_residuals = imag.(neighbor_y) .- linear_fitted
	linear_sse = sum(abs2, linear_residuals)
	neighbor_imag_mean = sum(imag.(neighbor_y)) / length(neighbor_y)
	linear_sst = sum(abs2, imag.(neighbor_y) .- neighbor_imag_mean)
	linear_r2 = linear_sst == 0 ? (linear_sse == 0 ? 1.0 : 0.0) : 1 - linear_sse / linear_sst
	abs_y_siemens = abs.(neighbor_y)
	abs_z_ohm_from_reciprocal_y = Union{Nothing,Float64}[
		isfinite(value) && value > 0 ? 1 / value : nothing for value in abs_y_siemens
	]
	local_neighbor_diagnostic = (
		role = "neighboring_pole_and_singularity_diagnostic_not_acceptance_gate",
		indices = neighbor_indices,
		frequencies_hz = neighbor_frequencies,
		complex_y_siemens = ComplexF64.(neighbor_y),
		abs_y_siemens = Float64.(abs_y_siemens),
		abs_z_ohm_from_reciprocal_y = abs_z_ohm_from_reciprocal_y,
		im_y_linear_fit = (
			center_frequency_hz = selected.root_hz,
			intercept_siemens = Float64(linear_coefficients[1]),
			slope_s_per_hz = Float64(linear_coefficients[2]),
			fitted_im_y_siemens = Float64.(linear_fitted),
			residual_im_y_siemens = Float64.(linear_residuals),
			rmse_siemens = sqrt(linear_sse / length(linear_residuals)),
			r2 = Float64(linear_r2),
		),
	)
	return (
		frequency_hz = selected.root_hz,
		anchor_hz = anchor,
		trust_half_width_hz = trust_half_width,
		trust_interval_hz = trust_interval_hz,
		selected_bracket = selected,
		all_sign_change_candidates = candidates,
		positive_slope_candidates = positive,
		in_trust_interval_candidates = in_window,
		local_neighbor_diagnostic = local_neighbor_diagnostic,
		selection_rule = "unique_positive_slope_ImYdiff_zero_in_trust_interval",
		interpolation = "linear_within_selected_sign_change_bracket",
	)
end

const D3_SYSTEM_C_TARGET_KEYS = Set([
	"system_c_filter_loaded_bare_hz",
	"system_c_readout_loaded_bare_hz",
	"system_c_intrinsic_notch_hz",
	"system_c_filter_loaded_bare_external_linewidth_hz",
	"system_c_j_hz",
	"system_c_g_hz",
	"system_c_readout_minus_filter_loaded_bare_detuning_hz",
	"qubit_transition_frequency_hz",
	"qubit_junction_inductance_per_junction_h",
])

function _d3_system_c_target_values(value)
	value isa AbstractDict || error("System-C target injection must be a mapping.")
	targets = Dict(String(key) => Float64(item) for (key, item) in pairs(value))
	Set(keys(targets)) == D3_SYSTEM_C_TARGET_KEYS || error(
		"System-C target injection must contain the exact Revision-3 target value set.",
	)
	positive_keys = setdiff(D3_SYSTEM_C_TARGET_KEYS, Set([
		"system_c_readout_minus_filter_loaded_bare_detuning_hz",
	]))
	all(key -> isfinite(targets[key]) && targets[key] > 0, positive_keys) || error(
		"System-C frequencies, couplings, linewidth, and qubit inductance targets must be finite and positive.",
	)
	detuning_hz = targets["system_c_readout_loaded_bare_hz"] -
		targets["system_c_filter_loaded_bare_hz"]
	isapprox(
		targets["system_c_readout_minus_filter_loaded_bare_detuning_hz"],
		detuning_hz;
		atol = 1.0e-6,
		rtol = 0.0,
	) || error("System-C injected detuning must equal readout minus filter diagonal target.")
	return targets
end

mutable struct D3SlotEvaluator
	case
	seed_design
	feedline::D3FeedlineRLGC
	hb_settings::D3HBSettings
	settings::D3SlotEvaluationSettings
	floating_qubit_nominal::D3FloatingQubitNominal
	floating_qubit_input_sha256::String
	qubit_coupling_off_frequency_hz::Float64
	system_c_target_values::Dict{String,Float64}
	qubit_target_contract_id::String
	qubit_target_contract_sha256::String
	reference_cache::Dict{String,Vector{ComplexF64}}
	records::Dict{Tuple,Any}
	journal_path::Union{Nothing,String}
end

function D3SlotEvaluator(
	case,
	seed_design,
	feedline,
	hb_settings,
	settings,
	floating_qubit_nominal,
	floating_qubit_input_sha256,
	qubit_coupling_off_frequency_hz;
	system_c_target_values,
	qubit_target_contract_id,
	qubit_target_contract_sha256,
	journal_path,
)
	selected_journal_path = isnothing(journal_path) ? nothing : String(journal_path)
	if !isnothing(selected_journal_path)
		isfile(selected_journal_path) && error("Refusing to overwrite D3 evaluator journal: $(selected_journal_path)")
		mkpath(dirname(selected_journal_path))
	end
	input_sha256 = String(floating_qubit_input_sha256)
	occursin(r"^[0-9a-f]{64}$", input_sha256) || error("Floating-qubit input identity must be a lowercase SHA-256.")
	coupling_off_fqLB_hz = Float64(qubit_coupling_off_frequency_hz)
	isfinite(coupling_off_fqLB_hz) && coupling_off_fqLB_hz > 0 || error("Floating-qubit coupling-off frequency must be finite and positive.")
	target_values = _d3_system_c_target_values(system_c_target_values)
	expected_lj_nh = target_values["qubit_junction_inductance_per_junction_h"] / D3_HENRIES_PER_NH
	Float64(floating_qubit_nominal.L_J_per_junction_nH) == expected_lj_nh || error(
		"Private floating-qubit L_J disagrees with the canonical per-junction target.",
	)
	target_contract_id = strip(String(qubit_target_contract_id))
	isempty(target_contract_id) && error("Canonical qubit target contract id must be nonempty.")
	target_contract_sha256 = String(qubit_target_contract_sha256)
	occursin(r"^[0-9a-f]{64}$", target_contract_sha256) || error("Canonical qubit target contract SHA-256 is invalid.")
	return D3SlotEvaluator(
		case,
		seed_design,
		feedline,
		hb_settings,
		settings,
		floating_qubit_nominal,
		input_sha256,
		coupling_off_fqLB_hz,
		target_values,
		target_contract_id,
		target_contract_sha256,
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

"""Build one readout probe grid from the last accepted coupling-off pole."""
function _d3_readout_probe_grid(
	current_capacitance_fF,
	previous_capacitance_fF,
	previous_coupling_off_frequency_hz,
	slot_hz,
	settings,
)
	current = Float64(current_capacitance_fF)
	isfinite(current) && current > 0 || error("Current C_probe must be finite and positive.")
	if isnothing(previous_capacitance_fF)
		isnothing(previous_coupling_off_frequency_hz) || error(
			"The first C_probe cannot have a previous coupling-off pole.",
		)
	else
		previous_capacitance = Float64(previous_capacitance_fF)
		isfinite(previous_capacitance) && previous_capacitance > 0 && previous_capacitance < current ||
			error("C_probe continuation requires a smaller finite positive previous capacitance.")
		previous_frequency = Float64(previous_coupling_off_frequency_hz)
		isfinite(previous_frequency) && previous_frequency > 0 || error(
			"C_probe continuation requires a finite positive previous coupling-off pole.",
		)
	end
	anchor_hz = isnothing(previous_coupling_off_frequency_hz) ? Float64(slot_hz) :
		Float64(previous_coupling_off_frequency_hz)
	frequencies_hz = _slot_frequency_grid(
		anchor_hz,
		settings.reference_scan_half_width_hz,
		settings.frequency_step_hz,
	)
	return (
		frequencies_hz = frequencies_hz,
		frequency_grid_sha256 = _frequency_grid_sha256(frequencies_hz),
		current_capacitance_fF = current,
		previous_capacitance_fF = isnothing(previous_capacitance_fF) ? nothing : Float64(previous_capacitance_fF),
		grid_anchor_hz = anchor_hz,
		previous_coupling_off_accepted_frequency_hz = isnothing(previous_coupling_off_frequency_hz) ? nothing :
			Float64(previous_coupling_off_frequency_hz),
		observed_probe_step_fF = isnothing(previous_capacitance_fF) ? nothing :
			current - Float64(previous_capacitance_fF),
		frequency_grid_start_hz = first(frequencies_hz),
		frequency_grid_stop_hz = last(frequencies_hz),
		frequency_step_hz = maximum(diff(frequencies_hz)),
		continuation_half_width_hz = Float64(settings.reference_scan_half_width_hz),
		policy = "first_probe_slot_anchor_then_previous_accepted_coupling_off_pole",
	)
end

"""Accept a probe pole only inside its current grid and prior-pole trust interval."""
function _d3_accept_readout_probe_mode(
	mode,
	discovery_anchor_hz,
	probe_grid,
	settings;
	coupling_state,
	previous_accepted_frequency_hz,
)
	frequency_hz = Float64(mode.frequency_hz)
	anchor_hz = Float64(discovery_anchor_hz)
	grid = probe_grid.frequencies_hz
	(first(grid) <= frequency_hz <= last(grid)) || reject_d3_candidate(
		"readout_probe.outside_current_grid",
		"The sole fitted readout pole lies outside the current per-probe HB grid; out-of-span acceptance is forbidden.";
		details = (
			coupling_state = String(coupling_state),
			frequency_hz = frequency_hz,
			frequency_grid_start_hz = first(grid),
			frequency_grid_stop_hz = last(grid),
			matching_policy = "exact_one_in_current_grid_no_nearest_fallback",
		),
	)
	abs(frequency_hz - anchor_hz) <= settings.reference_scan_half_width_hz || reject_d3_candidate(
		"readout_probe.outside_continuation_interval",
		"The sole fitted readout pole lies outside the previous-pole-centered continuation interval; nearest-frequency fallback is forbidden.";
		details = (
			coupling_state = String(coupling_state),
			frequency_hz = frequency_hz,
			discovery_anchor_hz = anchor_hz,
			continuation_half_width_hz = settings.reference_scan_half_width_hz,
			matching_policy = "exact_one_in_previous_pole_centered_interval_no_nearest_fallback",
		),
	)
	return merge(mode, (
		continuation = (
			coupling_state = String(coupling_state),
			discovery_anchor_hz = anchor_hz,
			accepted_frequency_hz = frequency_hz,
			current_capacitance_fF = probe_grid.current_capacitance_fF,
			previous_capacitance_fF = probe_grid.previous_capacitance_fF,
			grid_anchor_hz = probe_grid.grid_anchor_hz,
			previous_accepted_frequency_hz = isnothing(previous_accepted_frequency_hz) ? nothing :
				Float64(previous_accepted_frequency_hz),
			observed_probe_step_fF = probe_grid.observed_probe_step_fF,
			continuation_half_width_hz = probe_grid.continuation_half_width_hz,
			frequency_grid_sha256 = probe_grid.frequency_grid_sha256,
			frequency_grid_start_hz = probe_grid.frequency_grid_start_hz,
			frequency_grid_stop_hz = probe_grid.frequency_grid_stop_hz,
			frequency_step_hz = probe_grid.frequency_step_hz,
			policy = "exact_one_eligible_pole_in_previous_pole_centered_interval_no_nearest_fallback",
		),
	))
end

function _analytic_bare_qubit_frequency_hz(qubit::D3FloatingQubitNominal)
	layers = floating_qubit_capacitance_layers(qubit)
	effective_inductance_h = qubit.L_J_per_junction_nH * D3_HENRIES_PER_NH / 2
	return 1 / (2π * sqrt(effective_inductance_h * layers.Cq_B_fF * D3_FARADS_PER_FF))
end

function _analytic_bare_resonator_frequency_hz(case, total_length_um)
	length_m = Float64(total_length_um) * D3_METERS_PER_UM
	isfinite(length_m) && length_m > 0 || error("Bare resonator analytic anchor requires a positive finite length.")
	velocity_m_per_s = 1 / sqrt(Float64(case.single_l_per_m_h) * Float64(case.single_c_per_m_f))
	isfinite(velocity_m_per_s) && velocity_m_per_s > 0 ||
		error("Bare resonator analytic anchor requires positive finite single-line L and C.")
	return velocity_m_per_s / (4 * length_m)
end

function _dedicated_frequency_grid(anchor_hz, settings; role)
	anchor = Float64(anchor_hz)
	isfinite(anchor) && anchor > 0 || error("$(role) grid anchor must be finite and positive.")
	frequencies_hz = _slot_frequency_grid(
		anchor,
		settings.reference_scan_half_width_hz,
		settings.frequency_step_hz,
	)
	first(frequencies_hz) <= anchor <= last(frequencies_hz) ||
		error("$(role) dedicated grid does not contain its analytic scan anchor.")
	return (
		role = String(role),
		analytic_scan_anchor_hz = anchor,
		anchor_role = "scan_assignment_only_not_frequency_authority",
		frequencies_hz = frequencies_hz,
		frequency_grid_sha256 = _frequency_grid_sha256(frequencies_hz),
		half_width_hz = settings.reference_scan_half_width_hz,
		frequency_step_hz = settings.frequency_step_hz,
	)
end

const D3_INTRINSIC_WIDE_MARGIN_HZ = 500.0e6

"""
	_intrinsic_wide_capture_grid(design, notch_target_hz, off_reference_filter_hz, step_hz)

Build the wide intrinsic-PTC grid used only for final trace capture. The lower
bound exposes the notch neighborhood, while the design-wide scan stop is the
declared conservative upper bound for the no-Cext intrinsic resonator region.
"""
function _intrinsic_wide_capture_grid(design, notch_target_hz, off_reference_filter_hz, step_hz)
	values = Float64[
		notch_target_hz,
		off_reference_filter_hz,
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
		"Design scan_stop_ghz must cover the off-reference filter plus 500 MHz for wide intrinsic final capture.",
	)
	stop_hz > start_hz || error("Wide intrinsic capture stop must exceed its start.")

	frequencies_hz = frequency_range_with_step(start_hz, stop_hz, values[3])
	return (
		frequencies_hz = frequencies_hz,
		range_provenance = (
			contract_id = "d3-intrinsic-wide-final-capture-v2",
			scope = "final_capture_only",
			start_hz = start_hz,
			stop_hz = stop_hz,
			frequency_step_hz = values[3],
			notch_target_hz = values[1],
			start_margin_below_notch_hz = D3_INTRINSIC_WIDE_MARGIN_HZ,
			off_reference_filter_hz = values[2],
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

"""Hash one ordered complex trace using exact Float64 bit patterns."""
function _complex_trace_sha256(kind, frequencies_hz, trace)
	frequencies = Float64.(collect(frequencies_hz))
	values = ComplexF64.(collect(trace))
	length(frequencies) == length(values) || error("D3 trace hash requires aligned frequency and response arrays.")
	!isempty(frequencies) || error("D3 trace hash requires at least one sample.")
	all(isfinite, frequencies) && all(isfinite, real.(values)) && all(isfinite, imag.(values)) ||
		error("D3 trace hash requires finite Float64 data.")
	payload = join((
		"d3-complex-trace-float64-bits-v1",
		"kind=$(String(kind))",
		"count=$(length(frequencies))",
		join((string(bitstring(frequencies[index]), ":", bitstring(real(values[index])), ":", bitstring(imag(values[index]))) for index in eachindex(frequencies)), "|"),
	), "|")
	return bytes2hex(SHA.sha256(payload))
end

"""Hash an explicit scalar-source identity rather than an in-memory plan object."""
function _scalar_source_plan_sha256(source_plan_identity)
	identity = strip(String(source_plan_identity))
	isempty(identity) && error("Scalar-pole source plan identity must be nonempty.")
	return bytes2hex(SHA.sha256("d3-scalar-pole-source-plan-v1|$(identity)"))
end

function _d3_hb_settings_identity(settings)
	optional = join(sort!(String["$(key)=$(repr(value))" for (key, value) in pairs(settings.optional_hb_kwargs)]), ",")
	return join((
		"section_length_m_bits=$(bitstring(settings.section_length_m))",
		"port_resistance_ohm_bits=$(bitstring(settings.port_resistance_ohm))",
		"pump_frequency_hz_bits=$(bitstring(settings.pump_frequency_hz))",
		"pump_current_a_bits=$(bitstring(settings.pump_current_a))",
		"n_pump_harmonics=$(settings.n_pump_harmonics)",
		"n_modulation_harmonics=$(settings.n_modulation_harmonics)",
		"optional=$(optional)",
	), ";")
end

function _scalar_pole_reject(code, label, reason; details = nothing)
	reject_d3_candidate(
		"scalar_pole.$(code)",
		"$(label) scalar-pole eligibility failed: $(reason)";
		details = details,
	)
end

"""Keep compact, JSON-safe fitter evidence when exact selection rejects.

The complete resonance, artifact, and aligned pole/residue ledgers are small
enough to retain. Sample-by-sample model and residual traces are deliberately
omitted because they do not explain selection accounting and can dominate a
rejected-candidate record.
"""
function _scalar_vf_rejection_evidence(result, label, variant)
	return (
		schema_version = "d3-scalar-vf-rejection-evidence.v1",
		label = String(label),
		variant = (
			window_scale = Float64(variant.window_scale),
			background_poles = Int(variant.background_poles),
		),
		vector_fit = (
			schema_version = get(result, "schema_version", nothing),
			status = get(result, "status", nothing),
			model = get(result, "model", nothing),
		),
		fit_settings = get(result, "fit_settings", nothing),
		requested_fit_window_hz = get(result, "requested_fit_window_hz", nothing),
		actual_fit_window_hz = get(result, "fit_window_hz", nothing),
		sampling = get(result, "sampling", nothing),
		resonances = get(result, "resonances", nothing),
		artifacts = get(result, "artifacts", nothing),
		rational_model = get(result, "rational_model", nothing),
		metrics = get(result, "metrics", nothing),
		fit_diagnostics = get(result, "fit_diagnostics", nothing),
		omitted_large_fields = ["model_trace", "complex_residual_trace"],
	)
end

function _scalar_pole_selection_reject(code, label, reason, result, variant; details = NamedTuple())
	evidence = _scalar_vf_rejection_evidence(result, label, variant)
	_scalar_pole_reject(
		code,
		label,
		reason;
		details = merge(details, (rejection_evidence = evidence,)),
	)
end

function _scalar_candidate_resonance_record(resonance, pole_record, laplace_s, model_scale, minimum_ratio)
	pole = ComplexF64(pole_record["pole_real_rad_per_s"], pole_record["pole_imag_rad_per_s"])
	residue = ComplexF64(pole_record["residue_real_rad_per_s"], pole_record["residue_imag_rad_per_s"])
	pole_response = residue ./ (laplace_s .- pole)
	if Bool(pole_record["conjugate_term_inferred"])
		pole_response .+= conj(residue) ./ (laplace_s .- conj(pole))
	end
	residue_response_ratio = maximum(abs.(pole_response)) / model_scale
	eligible = residue_response_ratio >= minimum_ratio
	return (
		storage_index = Int(pole_record["storage_index"]),
		frequency_hz = Float64(resonance["fr_hz"]),
		linewidth_hz = Float64(resonance["bandwidth_hz"]),
		ql = Float64(resonance["ql"]),
		pole_real_rad_per_s = Float64(pole_record["pole_real_rad_per_s"]),
		pole_imag_rad_per_s = Float64(pole_record["pole_imag_rad_per_s"]),
		residue_real_rad_per_s = Float64(pole_record["residue_real_rad_per_s"]),
		residue_imag_rad_per_s = Float64(pole_record["residue_imag_rad_per_s"]),
		residue_abs_rad_per_s = Float64(pole_record["residue_abs_rad_per_s"]),
		residue_response_ratio = residue_response_ratio,
		candidate_classification = "candidate_resonance",
		eligible = eligible,
		exclusion_reason = eligible ? nothing : "vanishing_residue_response",
	)
end

function _scalar_pole_selected_record(result, label, settings; variant)
	get(result, "schema_version", nothing) == "scalar-s21-vector-fit.v2" ||
		_scalar_pole_reject("wrong_vector_schema", label, "vector evidence does not satisfy scalar-s21-vector-fit.v2.";
				details = (observed_schema = get(result, "schema_version", nothing),))
	get(result, "status", nothing) == "success" ||
		_scalar_pole_reject("vector_fit_failed", label, "the vector fitter did not converge to a success payload.";
			details = (reason = get(result, "reason", "unstated"),))
	get(result, "model", nothing) == "scalar_s21_vector" ||
		_scalar_pole_reject("vector_model", label, "the vector payload has the wrong model identity.")
	rational = get(result, "rational_model", nothing)
	rational isa AbstractDict || _scalar_pole_selection_reject(
		"pole_accounting", label, "the rational-model record is missing.", result, variant,
	)
	poles = get(rational, "poles", Any[])
	!isempty(poles) || _scalar_pole_selection_reject(
		"pole_accounting", label, "the rational-model pole ledger is empty.", result, variant;
		details = (observed_count = 0, required_minimum_count = 1),
	)
	get(rational, "stored_pole_count", nothing) == length(poles) || _scalar_pole_selection_reject(
		"pole_accounting", label, "stored_pole_count disagrees with the pole ledger.", result, variant;
		details = (
			observed_count = get(rational, "stored_pole_count", nothing),
			required_count = length(poles),
			matching_policy = "stored_count_equals_complete_ledger_length",
		),
	)
	all(index -> get(poles[index], "storage_index", nothing) == index - 1, eachindex(poles)) ||
		_scalar_pole_selection_reject(
			"pole_residue_alignment", label, "pole storage indices are not consecutive and residue-aligned.", result, variant;
			details = (
				observed_storage_indices = [get(pole, "storage_index", nothing) for pole in poles],
				required_storage_indices = collect(0:(length(poles) - 1)),
				matching_policy = "consecutive_storage_order_is_pole_residue_alignment",
			),
		)
	calculated_order = sum(pole -> get(pole, "pole_kind", nothing) == "real" ? 1 : 2, poles)
	get(rational, "final_model_order", nothing) == calculated_order || _scalar_pole_selection_reject(
		"pole_accounting", label, "final_model_order disagrees with the complete pole ledger.", result, variant;
		details = (
			observed_order = get(rational, "final_model_order", nothing),
			required_order = calculated_order,
			matching_policy = "real_pole_order_one_complex_pair_order_two",
		),
	)
	all(pole -> get(pole, "classification", nothing) in ("resonance", "excluded"), poles) ||
		_scalar_pole_selection_reject(
			"pole_accounting", label, "a rational pole is missing an explicit classification.", result, variant;
			details = (
				observed_classifications = [get(pole, "classification", nothing) for pole in poles],
				required_classifications = ["resonance", "excluded"],
			),
		)
	candidate_resonances = get(result, "resonances", Any[])
	ledger_candidates = filter(pole -> get(pole, "classification", nothing) == "resonance", poles)
	length(candidate_resonances) == length(ledger_candidates) || _scalar_pole_selection_reject(
		"pole_accounting", label, "the candidate-resonance bucket disagrees with the rational pole ledger.", result, variant;
		details = (
			candidate_resonance_count = length(candidate_resonances),
			ledger_candidate_count = length(ledger_candidates),
			matching_policy = "complete_candidate_bucket_equals_resonance_classified_ledger",
		),
	)
	candidate_pairs = NamedTuple[]
	for (candidate_index, resonance) in enumerate(candidate_resonances)
		matching_poles = filter(poles) do pole
			get(pole, "classification", nothing) == "resonance" &&
			get(pole, "pole_real_rad_per_s", nothing) == get(resonance, "pole_real_rad_per_s", nothing) &&
			get(pole, "pole_imag_rad_per_s", nothing) == get(resonance, "pole_imag_rad_per_s", nothing)
		end
		length(matching_poles) == 1 || _scalar_pole_selection_reject(
			"pole_residue_alignment",
			label,
			"a candidate resonance does not map exactly to one rational pole/residue record.",
			result,
			variant;
			details = (
				candidate_index = candidate_index - 1,
				matching_count = length(matching_poles),
				matching_policy = "exact_pole_coordinates_no_nearest",
			),
		)
		push!(candidate_pairs, (resonance = resonance, pole = only(matching_poles)))
	end
	length(unique(Int(pair.pole["storage_index"]) for pair in candidate_pairs)) == length(candidate_pairs) ||
		_scalar_pole_selection_reject(
			"pole_residue_alignment", label, "multiple candidate resonances map to one stored pole.", result, variant;
			details = (matching_policy = "one_candidate_per_storage_index_no_nearest",),
		)
	fit_diagnostics = get(result, "fit_diagnostics", nothing)
	fit_diagnostics isa AbstractDict || _scalar_pole_selection_reject(
		"fit_diagnostics", label, "the vector-fit convergence diagnostics are missing.", result, variant,
	)
	get(fit_diagnostics, "converged", false) === true || _scalar_pole_selection_reject(
		"not_converged",
		label,
		"the vector fitter did not satisfy its convergence tolerance.",
		result,
		variant;
		details = (
			iteration_count = get(fit_diagnostics, "iteration_count", nothing),
			convergence_tolerance = get(fit_diagnostics, "convergence_tolerance", nothing),
			last_delta_max = isempty(get(fit_diagnostics, "delta_max_history", Any[])) ? nothing : last(fit_diagnostics["delta_max_history"]),
		),
	)

	model_trace = result["model_trace"]
	model_frequencies_hz = Float64.(model_trace["frequency_hz"])
	model_s21 = ComplexF64.(Float64.(model_trace["s21_real"]) .+ im .* Float64.(model_trace["s21_imag"]))
	model_scale = maximum(abs.(model_s21))
	model_scale > 0 || _scalar_pole_selection_reject(
		"response_scale", label, "the fitted scalar response has zero magnitude.", result, variant,
	)
	laplace_s = 2π * im .* model_frequencies_hz
	minimum_ratio = settings.scalar_pole_min_residue_response_ratio
	classified_candidates = [
		merge(pair, (
			evidence = _scalar_candidate_resonance_record(
				pair.resonance,
				pair.pole,
				laplace_s,
				model_scale,
				minimum_ratio,
			),
		))
		for pair in candidate_pairs
	]
	eligible_candidates = filter(pair -> pair.evidence.eligible, classified_candidates)
	length(eligible_candidates) == 1 || _scalar_pole_selection_reject(
		"target_pole_count",
		label,
		"the declared one-resonator topology/window did not contain exactly one residue-qualified eligible pole.",
		result,
		variant;
		details = (
			candidate_count = length(classified_candidates),
			eligible_count = length(eligible_candidates),
			required_eligible_count = 1,
			matching_policy = "exact_eligible_count_no_nearest",
			candidate_resonances = [pair.evidence for pair in classified_candidates],
		),
	)
	selected = only(eligible_candidates)
	return selected.resonance, selected.pole, poles, [pair.evidence for pair in classified_candidates]
end

function _scalar_pole_fit_evidence(
	result,
	label,
	settings;
	window_scale,
	background_poles,
)
	resonance, selected_pole, poles, candidate_resonances = _scalar_pole_selected_record(
		result,
		label,
		settings;
		variant = (window_scale = window_scale, background_poles = background_poles),
	)
	rational = result["rational_model"]
	frequency_hz = Float64(resonance["fr_hz"])
	linewidth_hz = Float64(resonance["bandwidth_hz"])
	all(isfinite, (frequency_hz, linewidth_hz)) && frequency_hz > 0 && linewidth_hz > 0 ||
		_scalar_pole_reject("finite_selected_pole", label, "the selected frequency/linewidth is not finite and positive.")

	sampling = result["sampling"]
	maximum_step_hz = Float64(sampling["maximum_frequency_step_hz"])
	samples_per_linewidth = linewidth_hz / maximum_step_hz
	samples_per_linewidth >= settings.scalar_pole_min_samples_per_linewidth || _scalar_pole_reject(
		"sampling_density",
		label,
		"the fitted pole has too few samples per linewidth.";
		details = (
			observed_samples_per_linewidth = samples_per_linewidth,
			minimum_samples_per_linewidth = settings.scalar_pole_min_samples_per_linewidth,
			linewidth_hz = linewidth_hz,
			maximum_frequency_step_hz = maximum_step_hz,
		),
	)

	selected_index = Int(selected_pole["storage_index"])
	selected_candidate = only(filter(candidate -> candidate.storage_index == selected_index, candidate_resonances))
	residue_response_ratio = selected_candidate.residue_response_ratio
	nearby = NamedTuple[]
	for other in candidate_resonances
		other.storage_index == selected_index && continue
		separation_linewidths = abs(other.frequency_hz - frequency_hz) / linewidth_hz
		push!(nearby, (
			storage_index = other.storage_index,
			frequency_hz = other.frequency_hz,
			separation_linewidths = separation_linewidths,
			residue_response_ratio = other.residue_response_ratio,
			eligible = other.eligible,
			exclusion_reason = other.exclusion_reason,
		))
	end
	blocking_nearby = filter(item -> item.eligible, nearby)
	minimum_candidate_nearby_separation = isempty(nearby) ? nothing : minimum(item.separation_linewidths for item in nearby)
	minimum_nearby_separation = isempty(blocking_nearby) ? nothing : minimum(item.separation_linewidths for item in blocking_nearby)
	(isnothing(minimum_nearby_separation) || minimum_nearby_separation >= settings.scalar_pole_min_nearby_separation_linewidths) || _scalar_pole_reject(
		"nearby_pole_ambiguity",
		label,
		"another residue-qualified candidate pole lies too close to the sole eligible target pole.";
		details = (
			nearby_candidate_poles = nearby,
			blocking_nearby_poles = blocking_nearby,
			minimum_separation_linewidths = settings.scalar_pole_min_nearby_separation_linewidths,
			matching_policy = "no_nearest_fallback",
		),
	)

	residual_trace = result["complex_residual_trace"]
	residual_frequencies_hz = Float64.(residual_trace["frequency_hz"])
	residual_abs = Float64.(residual_trace["residual_abs"])
	local_mask = abs.(residual_frequencies_hz .- frequency_hz) .<= linewidth_hz
	count(local_mask) >= 3 || _scalar_pole_reject(
		"local_residual_sampling", label, "fewer than three residual samples lie within plus/minus one linewidth.",
	)
	local_complex_rms_error = sqrt(sum(abs2, residual_abs[local_mask]) / count(local_mask))
	complex_rms_error = Float64(result["metrics"]["rms_error"])
	max_abs_error = Float64(result["metrics"]["max_abs_error"])
	complex_rms_error <= settings.scalar_pole_max_complex_rms_error || _scalar_pole_reject(
		"complex_rms", label, "global complex RMSE exceeds the promotion gate.";
		details = (observed = complex_rms_error, maximum = settings.scalar_pole_max_complex_rms_error),
	)
	local_complex_rms_error <= settings.scalar_pole_max_local_complex_rms_error || _scalar_pole_reject(
		"local_complex_rms", label, "local complex RMSE exceeds the promotion gate.";
		details = (observed = local_complex_rms_error, maximum = settings.scalar_pole_max_local_complex_rms_error),
	)
	max_abs_error <= settings.scalar_pole_max_abs_error || _scalar_pole_reject(
		"max_abs_error", label, "maximum complex residual magnitude exceeds the promotion gate.";
		details = (observed = max_abs_error, maximum = settings.scalar_pole_max_abs_error),
	)
	return (
		schema_version = "scalar-s21-vector-fit.v2",
		eligible = true,
		failure_codes = String[],
		selection_policy = "exactly_one_eligible_target_pole_in_declared_topology_and_window_no_nearest_matching",
		window_scale = Float64(window_scale),
		background_poles = Int(background_poles),
		fit_window_hz = Float64.(result["fit_window_hz"]),
		requested_fit_window_hz = Float64.(result["requested_fit_window_hz"]),
		fit_settings = result["fit_settings"],
		sampling = (
			sample_count = Int(sampling["sample_count"]),
			minimum_frequency_step_hz = Float64(sampling["minimum_frequency_step_hz"]),
			maximum_frequency_step_hz = maximum_step_hz,
			samples_per_linewidth = samples_per_linewidth,
		),
		selected_pole = (
			storage_index = selected_index,
			frequency_hz = frequency_hz,
			linewidth_hz = linewidth_hz,
			ql = Float64(resonance["ql"]),
			pole_real_rad_per_s = Float64(selected_pole["pole_real_rad_per_s"]),
			pole_imag_rad_per_s = Float64(selected_pole["pole_imag_rad_per_s"]),
			residue_real_rad_per_s = Float64(selected_pole["residue_real_rad_per_s"]),
			residue_imag_rad_per_s = Float64(selected_pole["residue_imag_rad_per_s"]),
			residue_abs_rad_per_s = Float64(selected_pole["residue_abs_rad_per_s"]),
			residue_response_ratio = residue_response_ratio,
		),
		pole_accounting = (
			stored_pole_count = Int(rational["stored_pole_count"]),
			final_model_order = Int(rational["final_model_order"]),
			poles = poles,
			candidate_resonance_count = length(candidate_resonances),
			eligible_resonance_count = count(candidate -> candidate.eligible, candidate_resonances),
			vanishing_residue_candidate_count = count(candidate -> !candidate.eligible, candidate_resonances),
			artifact_count = length(result["artifacts"]),
		),
		candidate_resonances = candidate_resonances,
		nearby_poles = nearby,
		blocking_nearby_poles = blocking_nearby,
		minimum_candidate_nearby_separation_linewidths = minimum_candidate_nearby_separation,
		minimum_nearby_separation_linewidths = minimum_nearby_separation,
		residual_gates = (
			complex_rms_error = complex_rms_error,
			local_complex_rms_error = local_complex_rms_error,
			local_window_definition = "abs(f-fr) <= linewidth_hz",
			max_abs_error = max_abs_error,
		),
		fit_diagnostics = result["fit_diagnostics"],
	)
end

function _scalar_source_level(
	level_id,
	frequencies_hz,
	source_evaluator,
	source_plan_identity,
	reference_contract_id,
	port_plane,
	discovery_center_hz,
	base_half_window_hz,
	settings;
	vector_fitter,
)
	grid_hash = _frequency_grid_sha256(frequencies_hz)
	source = source_evaluator(String(level_id), Float64.(frequencies_hz))
	measured = ComplexF64.(source.measured_s21)
	reference = ComplexF64.(source.reference_s21)
	normalized = _normalized_s21(
		frequencies_hz,
		measured,
		reference,
		settings.min_reference_magnitude,
	)
	fit_window_hz = [
		discovery_center_hz - base_half_window_hz,
		discovery_center_hz + base_half_window_hz,
	]
	result = vector_fitter(
		frequencies_hz,
		normalized;
		n_resonators = 1,
		bg_poles = settings.vector_bg_poles,
		max_iterations = settings.vector_max_iterations,
		min_q = settings.vector_min_q,
		restrict_to_input_span = true,
		fit_window_hz = fit_window_hz,
	)
	fit = _scalar_pole_fit_evidence(
		result,
		"$(source.label) $(level_id)",
		settings;
		window_scale = 1.0,
		background_poles = settings.vector_bg_poles,
	)
	measured_trace_sha256 = _complex_trace_sha256("measured_s21", frequencies_hz, measured)
	reference_trace_sha256 = _complex_trace_sha256("reference_s21", frequencies_hz, reference)
	response_sha256 = _complex_trace_sha256("normalized_s21", frequencies_hz, normalized)
	return (
		level_id = String(level_id),
		source_execution_id = String(source.source_execution_id),
		source_plan_id = String(source.source_plan_id),
		source_plan_identity = String(source_plan_identity),
		source_plan_sha256 = _scalar_source_plan_sha256(source_plan_identity),
		measured_trace_id = String(source.measured_trace_id),
		reference_trace_id = String(source.reference_trace_id),
		reference_contract_id = String(reference_contract_id),
		port_plane = String(port_plane),
		frequency_grid_sha256 = grid_hash,
		frequency_grid_start_hz = first(frequencies_hz),
		frequency_grid_stop_hz = last(frequencies_hz),
		frequency_sample_count = length(frequencies_hz),
		frequency_step_hz = maximum(diff(frequencies_hz)),
		measured_trace_sha256 = measured_trace_sha256,
		reference_trace_sha256 = reference_trace_sha256,
		response_sha256 = response_sha256,
		fit = fit,
		normalized_s21 = normalized,
		frequencies_hz = Float64.(frequencies_hz),
	)
end

"""Prove integer-factor nesting of two local scalar-pole source grids.

The proof uses the construction topology—shared endpoints, an exact interval
count ratio, and stride-aligned nested samples. Float64 maximum-step values are
retained only as diagnostics because subtracting nearby frequencies around GHz
carriers can make their ratio differ materially from the constructed factor.
"""
function _scalar_refinement_grid_proof(level0_grid, level1_grid, required_factor, label)
	factor = Int(required_factor)
	factor >= 2 || _scalar_pole_reject(
		"refinement_factor", label, "the declared scalar-pole refinement factor is less than two.";
		details = (required = factor,),
	)
	level0_interval_count = length(level0_grid) - 1
	level1_interval_count = length(level1_grid) - 1
	level0_interval_count > 0 || _scalar_pole_reject(
		"refinement_grid", label, "the level-0 scalar-pole source grid has no intervals.",
	)
	level1_interval_count == factor * level0_interval_count || _scalar_pole_reject(
		"refinement_factor", label, "the two local source grids do not implement the declared integer interval-count refinement.";
		details = (
			level0_interval_count = level0_interval_count,
			level1_interval_count = level1_interval_count,
			required_factor = factor,
		),
	)

	frequency_scale_hz = max(
		maximum(abs, level0_grid),
		maximum(abs, level1_grid),
		1.0,
	)
	frequency_match_tolerance_hz = 8 * eps(frequency_scale_hz)
	endpoint_match_max_abs_error_hz = max(
		abs(first(level0_grid) - first(level1_grid)),
		abs(last(level0_grid) - last(level1_grid)),
	)
	endpoint_match_max_abs_error_hz <= frequency_match_tolerance_hz || _scalar_pole_reject(
		"refinement_endpoints", label, "the two local source grids do not share endpoints within the frequency-scale Float64 tolerance.";
		details = (
			observed_max_abs_error_hz = endpoint_match_max_abs_error_hz,
			maximum_hz = frequency_match_tolerance_hz,
		),
	)
	nested_sample_match_max_abs_error_hz = maximum(
		abs(level0_grid[index] - level1_grid[1 + (index - 1) * factor])
		for index in eachindex(level0_grid)
	)
	nested_sample_match_max_abs_error_hz <= frequency_match_tolerance_hz || _scalar_pole_reject(
		"refinement_nested_samples", label, "the stride-aligned level-1 samples do not reproduce the level-0 grid within the frequency-scale Float64 tolerance.";
		details = (
			observed_max_abs_error_hz = nested_sample_match_max_abs_error_hz,
			maximum_hz = frequency_match_tolerance_hz,
			nested_sample_stride = factor,
		),
	)

	return (
		proof_method = "same_endpoints_exact_interval_ratio_and_nested_stride_samples",
		observed_factor = div(level1_interval_count, level0_interval_count),
		level0_interval_count = level0_interval_count,
		level1_interval_count = level1_interval_count,
		frequency_scale_hz = frequency_scale_hz,
		frequency_match_tolerance_hz = frequency_match_tolerance_hz,
		endpoint_match_max_abs_error_hz = endpoint_match_max_abs_error_hz,
		nested_sample_stride = factor,
		nested_sample_count = length(level0_grid),
		nested_sample_match_max_abs_error_hz = nested_sample_match_max_abs_error_hz,
		maximum_step_diagnostics_hz = (
			level0 = maximum(diff(level0_grid)),
			level1 = maximum(diff(level1_grid)),
		),
	)
end

"""
Extract one promotion-owned scalar pole from two fresh local HB source grids.

The discovery fit only supplies center and linewidth estimates. Level 0 and
level 1 are independent source evaluations, and every stability fit selects a
sole eligible pole by exact count; no nearest-pole continuation is permitted.
"""
function _extract_scalar_pole_eligibility(
	discovery_mode,
	label,
	topology_id,
	source_plan_identity,
	reference_contract_id,
	port_plane,
	settings;
	source_evaluator,
	vector_fitter = fit_vector_s21,
)
	discovery_center_hz = Float64(discovery_mode.frequency_hz)
	discovery_linewidth_hz = Float64(discovery_mode.bandwidth_hz)
	all(isfinite, (discovery_center_hz, discovery_linewidth_hz)) && discovery_center_hz > 0 && discovery_linewidth_hz > 0 ||
		_scalar_pole_reject("invalid_discovery", label, "discovery did not produce a finite positive center and linewidth.")
	base_half_window_hz = clamp(
		settings.scalar_pole_local_half_window_linewidths * discovery_linewidth_hz,
		settings.scalar_pole_min_half_window_hz,
		settings.scalar_pole_max_half_window_hz,
	)
	source_half_window_hz = maximum(settings.scalar_pole_window_scales) * base_half_window_hz
	level0_step_hz = discovery_linewidth_hz / (
		settings.scalar_pole_min_samples_per_linewidth * settings.scalar_pole_level0_sampling_safety_factor
	)
	level1_step_hz = level0_step_hz / settings.scalar_pole_refinement_factor
	level1_step_hz >= settings.scalar_pole_min_frequency_step_hz || _scalar_pole_reject(
		"frequency_step_resource_guard",
		label,
		"the requested refined scalar-pole source step is below the reviewed resource floor.";
		details = (
			requested_level1_step_hz = level1_step_hz,
			minimum_frequency_step_hz = settings.scalar_pole_min_frequency_step_hz,
		),
	)
	source_span_hz = 2 * source_half_window_hz
	planned_level0_interval_count = round(Int, source_span_hz / level0_step_hz)
	planned_level0_interval_count >= 1 || _scalar_pole_reject(
		"source_sample_resource_guard", label, "the planned level-0 scalar-pole source grid has no intervals.",
	)
	planned_level0_sample_count = planned_level0_interval_count + 1
	planned_level1_interval_count = settings.scalar_pole_refinement_factor * planned_level0_interval_count
	planned_level1_sample_count = planned_level1_interval_count + 1
	max(planned_level0_sample_count, planned_level1_sample_count) <=
		settings.scalar_pole_max_source_samples_per_level || _scalar_pole_reject(
		"source_sample_resource_guard",
		label,
		"a planned scalar-pole source grid exceeds the reviewed per-level sample limit.";
		details = (
			planned_level0_sample_count = planned_level0_sample_count,
			planned_level1_sample_count = planned_level1_sample_count,
			maximum_source_samples_per_level = settings.scalar_pole_max_source_samples_per_level,
		),
	)
	planned_level0_actual_step_hz = source_span_hz / planned_level0_interval_count
	planned_level1_actual_step_hz = source_span_hz / planned_level1_interval_count
	planned_level1_actual_step_hz >= settings.scalar_pole_min_frequency_step_hz || _scalar_pole_reject(
		"frequency_step_resource_guard",
		label,
		"the constructed refined scalar-pole source step is below the reviewed resource floor.";
		details = (
			planned_level1_actual_step_hz = planned_level1_actual_step_hz,
			minimum_frequency_step_hz = settings.scalar_pole_min_frequency_step_hz,
		),
	)
	level0_grid = _slot_frequency_grid(discovery_center_hz, source_half_window_hz, level0_step_hz)
	level1_grid = collect(range(
		first(level0_grid),
		last(level0_grid);
		length = settings.scalar_pole_refinement_factor * (length(level0_grid) - 1) + 1,
	))
	length(level0_grid) == planned_level0_sample_count || error(
		"Scalar-pole level-0 allocation disagrees with its reviewed pre-allocation resource plan.",
	)
	length(level1_grid) == planned_level1_sample_count || error(
		"Scalar-pole level-1 allocation disagrees with its reviewed pre-allocation resource plan.",
	)
	refinement_grid_proof = _scalar_refinement_grid_proof(
		level0_grid,
		level1_grid,
		settings.scalar_pole_refinement_factor,
		label,
	)
	level0 = _scalar_source_level(
		"level0",
		level0_grid,
		source_evaluator,
		source_plan_identity,
		reference_contract_id,
		port_plane,
		discovery_center_hz,
		base_half_window_hz,
		settings;
		vector_fitter = vector_fitter,
	)
	level1 = _scalar_source_level(
		"level1",
		level1_grid,
		source_evaluator,
		source_plan_identity,
		reference_contract_id,
		port_plane,
		discovery_center_hz,
		base_half_window_hz,
		settings;
		vector_fitter = vector_fitter,
	)
	level0.frequency_grid_sha256 != level1.frequency_grid_sha256 ||
		_scalar_pole_reject("reused_refinement_grid", label, "level 0 and level 1 reused the same source grid.")
	level0.source_execution_id != level1.source_execution_id ||
		_scalar_pole_reject("reused_source_execution", label, "level 0 and level 1 reused one measured source execution.")

	coarse_pole = level0.fit.selected_pole
	refined_pole = level1.fit.selected_pole
	frequency_shift_hz = abs(refined_pole.frequency_hz - coarse_pole.frequency_hz)
	linewidth_shift_hz = abs(refined_pole.linewidth_hz - coarse_pole.linewidth_hz)
	frequency_shift_gate_hz = min(
		settings.scalar_pole_max_frequency_shift_abs_hz,
		settings.scalar_pole_max_frequency_shift_fraction * refined_pole.linewidth_hz,
	)
	linewidth_shift_gate_hz = min(
		settings.scalar_pole_max_linewidth_shift_abs_hz,
		settings.scalar_pole_max_linewidth_shift_fraction * refined_pole.linewidth_hz,
	)
	frequency_shift_hz <= frequency_shift_gate_hz || _scalar_pole_reject(
		"refinement_frequency_shift", label, "level-to-level pole-frequency shift exceeds the stricter absolute/fractional gate.";
		details = (observed_hz = frequency_shift_hz, maximum_hz = frequency_shift_gate_hz),
	)
	linewidth_shift_hz <= linewidth_shift_gate_hz || _scalar_pole_reject(
		"refinement_linewidth_shift", label, "level-to-level linewidth shift exceeds the stricter absolute/fractional gate.";
		details = (observed_hz = linewidth_shift_hz, maximum_hz = linewidth_shift_gate_hz),
	)

	stability = NamedTuple[]
	for window_scale in settings.scalar_pole_window_scales, bg_poles in settings.scalar_pole_bg_pole_checks
		fit = if window_scale == 1.0 && bg_poles == settings.vector_bg_poles
			level1.fit
		else
			fit_window_hz = [
				discovery_center_hz - window_scale * base_half_window_hz,
				discovery_center_hz + window_scale * base_half_window_hz,
			]
			result = vector_fitter(
				level1.frequencies_hz,
				level1.normalized_s21;
				n_resonators = 1,
				bg_poles = bg_poles,
				max_iterations = settings.vector_max_iterations,
				min_q = settings.vector_min_q,
				restrict_to_input_span = true,
				fit_window_hz = fit_window_hz,
			)
			_scalar_pole_fit_evidence(
				result,
				"$(label) refined stability window=$(window_scale) bg=$(bg_poles)",
				settings;
				window_scale = window_scale,
				background_poles = bg_poles,
			)
		end
		cell_frequency_shift_hz = abs(fit.selected_pole.frequency_hz - refined_pole.frequency_hz)
		cell_linewidth_shift_hz = abs(fit.selected_pole.linewidth_hz - refined_pole.linewidth_hz)
		cell_frequency_shift_hz <= frequency_shift_gate_hz || _scalar_pole_reject(
			"window_order_frequency_stability", label, "a refined window/background fit exceeds the frequency-stability gate.";
			details = (window_scale = window_scale, background_poles = bg_poles, observed_hz = cell_frequency_shift_hz, maximum_hz = frequency_shift_gate_hz),
		)
		cell_linewidth_shift_hz <= linewidth_shift_gate_hz || _scalar_pole_reject(
			"window_order_linewidth_stability", label, "a refined window/background fit exceeds the linewidth-stability gate.";
			details = (window_scale = window_scale, background_poles = bg_poles, observed_hz = cell_linewidth_shift_hz, maximum_hz = linewidth_shift_gate_hz),
		)
		push!(stability, (
			window_scale = Float64(window_scale),
			background_poles = Int(bg_poles),
			frequency_shift_from_refined_hz = cell_frequency_shift_hz,
			linewidth_shift_from_refined_hz = cell_linewidth_shift_hz,
			fit = fit,
		))
	end

	compact_level(level) = Base.structdiff(level, (normalized_s21 = nothing, frequencies_hz = nothing))
	evidence = (
		schema_version = "d3-scalar-pole-eligibility.v1",
		eligible = true,
		failure_codes = String[],
		label = String(label),
		declared_topology_id = String(topology_id),
		discovery = (
			role = "discovery_only_not_promotion_authority",
			frequency_hz = discovery_center_hz,
			linewidth_hz = discovery_linewidth_hz,
			frequency_step_hz = settings.frequency_step_hz,
		),
		source_plan = (
			identity = String(source_plan_identity),
			sha256 = _scalar_source_plan_sha256(source_plan_identity),
		),
		source_grid_plan = (
			base_half_window_hz = base_half_window_hz,
			source_half_window_hz = source_half_window_hz,
			local_half_window_linewidths = settings.scalar_pole_local_half_window_linewidths,
			clipped_half_window_bounds_hz = [settings.scalar_pole_min_half_window_hz, settings.scalar_pole_max_half_window_hz],
			level0_target_step_hz = level0_step_hz,
			level1_target_step_hz = level1_step_hz,
			planned_level0_sample_count = planned_level0_sample_count,
			planned_level1_sample_count = planned_level1_sample_count,
			planned_level0_actual_step_hz = planned_level0_actual_step_hz,
			planned_level1_actual_step_hz = planned_level1_actual_step_hz,
		),
		levels = [compact_level(level0), compact_level(level1)],
		refinement = (
			factor = settings.scalar_pole_refinement_factor,
			observed_factor = refinement_grid_proof.observed_factor,
			proof_method = refinement_grid_proof.proof_method,
			level0_interval_count = refinement_grid_proof.level0_interval_count,
			level1_interval_count = refinement_grid_proof.level1_interval_count,
			frequency_scale_hz = refinement_grid_proof.frequency_scale_hz,
			frequency_match_tolerance_hz = refinement_grid_proof.frequency_match_tolerance_hz,
			endpoint_match_max_abs_error_hz = refinement_grid_proof.endpoint_match_max_abs_error_hz,
			nested_sample_stride = refinement_grid_proof.nested_sample_stride,
			nested_sample_count = refinement_grid_proof.nested_sample_count,
			nested_sample_match_max_abs_error_hz = refinement_grid_proof.nested_sample_match_max_abs_error_hz,
			maximum_step_diagnostics_hz = refinement_grid_proof.maximum_step_diagnostics_hz,
			frequency_shift_hz = frequency_shift_hz,
			frequency_shift_gate_hz = frequency_shift_gate_hz,
			linewidth_shift_hz = linewidth_shift_hz,
			linewidth_shift_gate_hz = linewidth_shift_gate_hz,
			gate_policy = "min_absolute_fraction_times_refined_linewidth",
		),
		stability = stability,
		pole_residue_continuation = (
			matching_policy = "exactly_one_eligible_pole_per_fit_no_nearest_matching",
			level0_selected_pole = coarse_pole,
			level1_selected_pole = refined_pole,
		),
		gates = (
			minimum_samples_per_linewidth = settings.scalar_pole_min_samples_per_linewidth,
			minimum_frequency_step_hz = settings.scalar_pole_min_frequency_step_hz,
			maximum_source_samples_per_level = settings.scalar_pole_max_source_samples_per_level,
			minimum_residue_response_ratio = settings.scalar_pole_min_residue_response_ratio,
			minimum_nearby_separation_linewidths = settings.scalar_pole_min_nearby_separation_linewidths,
			maximum_complex_rms_error = settings.scalar_pole_max_complex_rms_error,
			maximum_local_complex_rms_error = settings.scalar_pole_max_local_complex_rms_error,
			maximum_abs_error = settings.scalar_pole_max_abs_error,
		),
		selected_refined_pole = refined_pole,
	)
	return (
		frequency_hz = refined_pole.frequency_hz,
		bandwidth_hz = refined_pole.linewidth_hz,
		vector_rms_error = level1.fit.residual_gates.complex_rms_error,
		pole_real_rad_per_s = refined_pole.pole_real_rad_per_s,
		pole_imag_rad_per_s = refined_pole.pole_imag_rad_per_s,
		residue_real_rad_per_s = refined_pole.residue_real_rad_per_s,
		residue_imag_rad_per_s = refined_pole.residue_imag_rad_per_s,
		scalar_pole_eligibility = evidence,
	)
end

function _d3_trace_identity(
	case_id,
	design_id,
	candidate_identity,
	loaded_grid_sha256,
	pair_grid_sha256,
	qubit_grid_sha256,
	floating_qubit_input_sha256,
)
	for (label, hash) in (
		("loaded", loaded_grid_sha256),
		("pair", pair_grid_sha256),
		("qubit", qubit_grid_sha256),
	)
		occursin(r"^[0-9a-f]{64}$", String(hash)) ||
			error("$(label) frequency-grid identity must be a lowercase SHA-256 digest.")
	end
	occursin(r"^[0-9a-f]{64}$", String(floating_qubit_input_sha256)) ||
		error("Floating-qubit input identity must be a lowercase SHA-256 digest.")
	identity = String(candidate_identity)
	design = String(design_id)
	case = String(case_id)
	return (
		reference_contract_id = "d3-reference-contract-physical-terminal-coupling-off-v1|case=$(case)|floating_qubit_sha256=$(floating_qubit_input_sha256)|$(identity)",
		filter_off_reference_id = "d3-filter-off-reference-v1|topology=system_B_maxwell_diagonal_MTL_physical_terminal_R_to_GND_C0r_plus_Cr1_plus_Cr2_qubit_dynamic_nodes_absent|case=$(case)|design=$(design)|$(identity)",
		common_readout_off_reference_id = "d3-common-readout-off-reference-v1|R_to_GND=C0r_plus_Cr1_plus_Cr2|QL_to_GND=Cr1|QR_to_GND=Cr2|floating_qubit_sha256=$(floating_qubit_input_sha256)|design=$(design)|$(identity)",
		filter_off_reference_trace_id = "d3-filter-off-reference-hb|grid_sha256=$(loaded_grid_sha256)|design=$(design)|$(identity)",
		off_reference_empty_feedline_trace_id = "d3-empty-feedline-hb|grid_sha256=$(loaded_grid_sha256)|case=$(case)",
		qubit_empty_feedline_trace_id = "d3-empty-feedline-hb|grid_sha256=$(qubit_grid_sha256)|case=$(case)",
		calibration_id = "d3-filter-channel|grid_sha256=$(loaded_grid_sha256)|case=$(case)|$(identity)",
		pair_measured_trace_id = "d3-system-b-readout-filter-hb|grid_sha256=$(pair_grid_sha256)|design=$(design)|$(identity)",
		pair_empty_feedline_trace_id = "d3-empty-feedline-hb|grid_sha256=$(pair_grid_sha256)|case=$(case)",
		pair_assignment_id = "$(design)|grid_sha256=$(pair_grid_sha256)|$(identity)",
		qubit_frequency_grid_sha256 = String(qubit_grid_sha256),
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

_empty_feedline_reference_identity(frequencies_hz) =
	"empty_feedline|grid_sha256=$(_frequency_grid_sha256(frequencies_hz))"

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

function _extract_d3_bare_resonator_response(
	evaluator,
	design,
	resonator,
	frequencies_hz,
	reference_s21,
	anchor_hz,
)
	frequency_grid_sha256 = _frequency_grid_sha256(frequencies_hz)
	per_point = NamedTuple[]
	for probe_fF in evaluator.settings.c_probe_capacitances_fF
		plan = build_d3_bare_resonator_feedline_plan(
			evaluator.case,
			design;
			resonator = resonator,
			probe_capacitance_fF = probe_fF,
			feedline_length_um = evaluator.settings.feedline_length_um,
			feedline = evaluator.feedline,
			hb_settings = evaluator.hb_settings,
		)
		hb = _run_candidate_hb(
			evaluator,
			plan,
			frequencies_hz,
			"bare $(resonator) C_probe $(probe_fF) fF",
		)
		normalized = _normalized_s21(
			frequencies_hz,
			hb.s21,
			reference_s21,
			evaluator.settings.min_reference_magnitude,
		)
		mode = _fit_single_loaded_mode(
			frequencies_hz,
			normalized,
			anchor_hz,
			"bare $(resonator) C_probe $(probe_fF) fF",
			evaluator.settings,
			require_slot_ownership = false,
		)
		stage_label = "bare $(resonator) C_probe $(probe_fF) fF"
		source_plan_identity = join((
			"plan_id=$(plan.id)",
			"topology=d3-bare-$(resonator)-finite-probe",
			"case_id=$(evaluator.case.id)",
			"feedline_source=$(evaluator.feedline.source)",
			"hb_settings=$(_d3_hb_settings_identity(evaluator.hb_settings))",
			"design=$(repr(design))",
			"probe_capacitance_fF_bits=$(bitstring(probe_fF))",
		), "|")
		source_execution_count = Ref(0)
		source_evaluator = function(level_id, local_frequencies_hz)
			source_execution_count[] += 1
			local_grid_sha256 = _frequency_grid_sha256(local_frequencies_hz)
			local_hb = _run_candidate_hb(
				evaluator,
				plan,
				local_frequencies_hz,
				"$(stage_label) scalar-pole $(level_id)",
			)
			local_reference = _reference_trace!(evaluator, local_frequencies_hz)
			return (
				label = stage_label,
				measured_s21 = ComplexF64.(local_hb.s21),
				reference_s21 = local_reference,
				source_execution_id = "$(source_plan_identity)|level=$(level_id)|execution=$(source_execution_count[])",
				source_plan_id = plan.id,
				measured_trace_id = "d3-bare-$(resonator)-local-hb|level=$(level_id)|grid_sha256=$(local_grid_sha256)|probe_bits=$(bitstring(probe_fF))|design=$(design.id)",
				reference_trace_id = _empty_feedline_reference_identity(local_frequencies_hz),
			)
		end
		eligible_mode = _extract_scalar_pole_eligibility(
			mode,
			stage_label,
			"d3-bare-$(resonator)-finite-positive-C_probe-feedline-S21",
			source_plan_identity,
			"d3-empty-feedline-reference-per-local-grid",
			"JosephsonCircuits external feedline ports 1->2, 50 Ohm reference",
			evaluator.settings;
			source_evaluator = source_evaluator,
		)
		push!(per_point, (
			probe_capacitance_fF = probe_fF,
			frequency_grid_sha256 = frequency_grid_sha256,
			reference_identity = _empty_feedline_reference_identity(frequencies_hz),
			discovery_fit = mode,
			fit = eligible_mode,
			scalar_pole_eligibility = eligible_mode.scalar_pole_eligibility,
			frequencies_hz = Float64.(frequencies_hz),
			s21 = ComplexF64.(hb.s21),
			reference_s21 = ComplexF64.(reference_s21),
		))
	end
	length(per_point) >= 5 || error("Bare resonator extraction requires five successful per-point S21 fits.")
	intercept_fit = _quadratic_zero_intercept(
		evaluator.settings.c_probe_capacitances_fF,
		[item.fit.frequency_hz for item in per_point],
		evaluator.settings.min_readout_frequency_extrapolation_r2,
		"bare $(resonator) C_probe->0 frequency",
		"bare_$(resonator)_extrapolation.frequency",
	)
	return (
		frequency_hz = intercept_fit.intercept,
		analytic_scan_anchor_hz = Float64(anchor_hz),
		anchor_role = "scan_assignment_only_not_frequency_authority",
		frequency_grid_sha256 = frequency_grid_sha256,
		frequency_grid_start_hz = first(frequencies_hz),
		frequency_grid_stop_hz = last(frequencies_hz),
		reference_identity = _empty_feedline_reference_identity(frequencies_hz),
		c_probe_capacitances_fF = copy(evaluator.settings.c_probe_capacitances_fF),
		per_point_s21_fits = per_point,
		zero_probe_frequency_fit = intercept_fit,
	)
end

function _require_vector_fit(result, expected_count, label, settings)
	get(result, "schema_version", nothing) == "scalar-s21-vector-fit.v2" ||
		error("$(label) requires direct scalar-s21-vector-fit.v2 evidence.")
	get(result, "model", nothing) == "scalar_s21_vector" ||
		error("$(label) vector-fit model identity is invalid.")
	get(result, "status", "missing") == "success" ||
		error("$(label) vector-fit execution failed: $(get(result, "reason", "unstated reason"))")
	fit_diagnostics = get(result, "fit_diagnostics", Dict())
	get(fit_diagnostics, "converged", false) === true || reject_d3_candidate(
		"vector.not_converged",
		"$(label) vector fitter did not satisfy its convergence tolerance.";
		details = (fit_diagnostics = fit_diagnostics,),
	)
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

function _compact_vector_crosscheck(result)
	get(result, "schema_version", nothing) == "scalar-s21-vector-fit.v2" || error(
		"D3 pair cross-check requires scalar-s21-vector-fit.v2.",
	)
	return (
		role = "cross_check_only",
		schema_version = result["schema_version"],
		model = result["model"],
		fit_settings = result["fit_settings"],
		fit_window_hz = result["fit_window_hz"],
		requested_fit_window_hz = result["requested_fit_window_hz"],
		sampling = result["sampling"],
		resonances = result["resonances"],
		artifacts = result["artifacts"],
		rational_model = result["rational_model"],
		metrics = result["metrics"],
		fit_diagnostics = result["fit_diagnostics"],
	)
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
	(!require_slot_ownership || abs(frequency_hz - slot_hz) <= settings.off_reference_ownership_half_width_hz) ||
		reject_d3_candidate(
			"off_reference.ownership_window",
			"$(label) resonance lies outside its off-reference ownership window.";
			details = (
				frequency_hz = frequency_hz,
				slot_hz = slot_hz,
				ownership_half_width_hz = settings.off_reference_ownership_half_width_hz,
			),
		)
	return (
		frequency_hz = frequency_hz,
		bandwidth_hz = Float64(bandwidth_hz),
		vector_rms_error = Float64(vector_rms_error),
		pole_real_rad_per_s = resonance["pole_real_rad_per_s"],
		pole_imag_rad_per_s = resonance["pole_imag_rad_per_s"],
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
		max_iterations = settings.vector_max_iterations,
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

function _require_zero_probe_readout_slot_ownership(readout_frequency_hz, slot_hz, ownership_half_width_hz)
	values = Float64[readout_frequency_hz, slot_hz, ownership_half_width_hz]
	all(isfinite, values) || error("Zero-probe readout Slot-ownership inputs must be finite.")
	values[3] >= 0 || error("Zero-probe readout Slot-ownership half width must be non-negative.")
	abs(values[1] - values[2]) <= values[3] || reject_d3_candidate(
		"off_reference.readout_ownership_window",
		"Readout zero-probe frequency intercept lies outside its off-reference ownership window.";
		details = (
			readout_frequency_hz = values[1],
			slot_hz = values[2],
			ownership_half_width_hz = values[3],
		),
	)
	return values[1]
end

"""Extract real linearized g from the coupling-induced readout pole shift."""
function _linearized_g_from_readout_shift_hz(coupling_off_qubit_hz, coupling_off_readout_hz, coupling_on_readout_hz)
	values = Float64[coupling_off_qubit_hz, coupling_off_readout_hz, coupling_on_readout_hz]
	all(isfinite, values) || reject_d3_candidate(
		"g.nonfinite_readout_shift",
		"Linearized g requires finite off-reference qubit, off-reference readout, and coupling-on readout frequencies.";
		details = (values_hz = values,),
	)
	values[2] > values[1] || reject_d3_candidate(
		"g.nonpositive_off_reference_detuning",
		"The off-reference readout frequency must lie above the off-reference qubit frequency.";
		details = (coupling_off_qubit_hz = values[1], coupling_off_readout_hz = values[2]),
	)
	readout_shift_hz = values[3] - values[2]
	readout_shift_hz > 0 || reject_d3_candidate(
		"g.nonpositive_readout_shift",
		"Qubit coupling must shift the readout-like pole upward for positive readout-qubit detuning.";
		details = (
			coupling_off_readout_hz = values[2],
			coupling_on_readout_hz = values[3],
			readout_shift_hz = readout_shift_hz,
		),
	)
	radicand_hz2 = readout_shift_hz * (values[3] - values[1])
	isfinite(radicand_hz2) && radicand_hz2 > 0 || reject_d3_candidate(
		"g.invalid_radicand",
		"Linearized g radicand must be finite and positive.";
		details = (readout_shift_hz = readout_shift_hz, radicand_hz2 = radicand_hz2),
	)
	return sqrt(radicand_hz2)
end

function _readout_shift_g_diagnostic(off_reference_qubit_hz, off_reference_readout_hz, system_a_readout_like_hz)
	values = Float64[
		off_reference_qubit_hz,
		off_reference_readout_hz,
		system_a_readout_like_hz,
	]
	all(isfinite, values) || return (
		status = "nonfinite",
		role = "finite_open_s21_diagnostic_not_gate",
		system_a_g_initializer_hz = nothing,
	)
	readout_shift_hz = values[3] - values[2]
	radicand_hz2 = readout_shift_hz * (values[3] - values[1])
	return (
		status = radicand_hz2 > 0 ? "real" : "nonpositive_radicand",
		role = "finite_open_s21_diagnostic_not_gate",
		off_reference_qubit_hz = values[1],
		off_reference_readout_hz = values[2],
		system_a_readout_like_hz = values[3],
		system_a_readout_hybridization_shift_hz = readout_shift_hz,
		radicand_hz2 = radicand_hz2,
		system_a_g_initializer_hz = radicand_hz2 > 0 ? sqrt(radicand_hz2) : nothing,
	)
end

"""Predict three local pole centers used only to construct each System-C grid.

This initializer diagonalizes a three-coordinate matrix from System-A and
System-B evidence. Its eigenvalues are scan anchors only: they neither extract
nor validate the final System-C poles and cannot populate final metrics.

# Arguments
- `fq_hz`, `fr_hz`, `fp_hz`: Common off-reference scan anchors in hertz.
- `g_hz`, `j_hz`: Fixed response-effective exchange couplings in hertz.

# Returns
Three ascending initializer frequencies in hertz.

# Throws
`ErrorException` when any frequency or coupling is non-finite or non-positive.
"""
function _system_c_initializer_poles_hz(fq_hz, fr_hz, fp_hz, g_hz, j_hz)
	values = Float64[fq_hz, fr_hz, fp_hz, g_hz, j_hz]
	all(isfinite, values) && all(>(0.0), values) || error("Three-mode frequencies and couplings must be finite and positive.")
	matrix_hz = Symmetric([
		values[1] values[4] 0.0
		values[4] values[2] values[5]
		0.0 values[5] values[3]
	])
	return sort(Float64.(eigvals(matrix_hz)))
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

"""Enumerate every Im(Z21 PTC) sign bracket; interpolation is discovery only."""
function _z21_ptc_sign_brackets(frequencies_hz, z21_ptc, target_hz, half_width_hz)
	indexes = findall(abs.(frequencies_hz .- target_hz) .<= half_width_hz)
	length(indexes) >= 3 || reject_d3_candidate(
		"notch.insufficient_samples",
		"Notch window contains fewer than three HB samples.";
		details = (sample_count = length(indexes),),
	)
	local_frequencies = Float64.(frequencies_hz[indexes])
	local_z21 = ComplexF64.(z21_ptc[indexes])
	all(isfinite, local_frequencies) && all(isfinite, real.(local_z21)) && all(isfinite, imag.(local_z21)) ||
		error("Notch observable contains an invalid value.")
	all(diff(local_frequencies) .> 0) || error("Notch frequencies must be strictly increasing.")
	brackets = NamedTuple[]
	covered_intervals = Set{Int}()
	for local_index in 2:(length(indexes) - 1)
		imag(local_z21[local_index]) == 0 || continue
		y_left = imag(local_z21[local_index - 1])
		y_right = imag(local_z21[local_index + 1])
		y_left != 0 && y_right != 0 && signbit(y_left) != signbit(y_right) || continue
		push!(brackets, (
			left_frequency_hz = local_frequencies[local_index - 1],
			right_frequency_hz = local_frequencies[local_index + 1],
			discovery_frequency_hz = local_frequencies[local_index],
			discovery_method = "exact_scan_sample_inside_sign_bracket",
			discovery_only = true,
		))
		push!(covered_intervals, local_index - 1, local_index)
	end
	for local_index in 1:(length(indexes) - 1)
		local_index in covered_intervals && continue
		y_left = imag(local_z21[local_index])
		y_right = imag(local_z21[local_index + 1])
		y_left != 0 && y_right != 0 && signbit(y_left) != signbit(y_right) || continue
		x_left = local_frequencies[local_index]
		x_right = local_frequencies[local_index + 1]
		root_hz = x_left - y_left * (x_right - x_left) / (y_right - y_left)
		push!(brackets, (
			left_frequency_hz = x_left,
			right_frequency_hz = x_right,
			discovery_frequency_hz = Float64(root_hz),
			discovery_method = "linear_ImZ21_scan_interpolation",
			discovery_only = true,
		))
	end
	sort!(brackets; by = bracket -> bracket.left_frequency_hz)
	return [merge(bracket, (candidate_id = "z21-root-$(lpad(index, 3, '0'))",)) for (index, bracket) in pairs(brackets)]
end

"""Refine one discovered bracket using only fresh actual-frequency evidence.

The scan-derived interpolation never enters the residual gate. Endpoints,
every safeguarded secant/bisection trial, and the final promoted point are
evaluated through `actual_z21_at_frequency` and retained as provenance.
"""
function _refine_z21_ptc_sign_bracket(
	actual_z21_at_frequency,
	bracket;
	frequency_tolerance_hz,
	max_iterations,
	max_abs_re_ohm,
	max_abs_im_ohm,
	max_abs_complex_ohm,
	trust_interval_hz,
	expected_orientation,
)
	tolerance = Float64(frequency_tolerance_hz)
	iterations_limit = Int(max_iterations)
	left = Float64(bracket.left_frequency_hz)
	right = Float64(bracket.right_frequency_hz)
	left < right || error("Z21 PTC refinement bracket must have positive width.")
	evaluations = NamedTuple[]
	function evaluate_actual(frequency_hz, role)
		value = ComplexF64(actual_z21_at_frequency(Float64(frequency_hz)))
		isfinite(real(value)) && isfinite(imag(value)) || error(
			"Actual arbitrary-frequency Z21 PTC evaluation returned a non-finite value.",
		)
		push!(evaluations, (
			frequency_hz = Float64(frequency_hz),
			z21_ptc_ohm = value,
			role = String(role),
			evidence = "fresh_actual_hb_ptc_evaluation",
		))
		return value
	end
	left_value = evaluate_actual(left, "refinement_left_endpoint")
	right_value = evaluate_actual(right, "refinement_right_endpoint")
	failure_codes = String[]
	bracketed_signed_crossing = imag(left_value) != 0 && imag(right_value) != 0 &&
		signbit(imag(left_value)) != signbit(imag(right_value))
	bracketed_signed_crossing || push!(failure_codes, "refinement.actual_endpoint_not_bracketed_signed_crossing")
	orientation = sign(imag(right_value) - imag(left_value))
	iteration_count = 0
	if bracketed_signed_crossing
		while right - left > tolerance && iteration_count < iterations_limit &&
			imag(left_value) != 0 && imag(right_value) != 0
			iteration_count += 1
			width = right - left
			secant = right - imag(right_value) * width / (imag(right_value) - imag(left_value))
			guard_left = left + 0.1 * width
			guard_right = right - 0.1 * width
			trial = isfinite(secant) && guard_left <= secant <= guard_right ? secant : (left + right) / 2
			trial_value = evaluate_actual(trial, "safeguarded_secant_bisection_iteration")
			if imag(trial_value) == 0
				left = right = trial
				left_value = right_value = trial_value
			elseif signbit(imag(left_value)) != signbit(imag(trial_value))
				right = trial
				right_value = trial_value
			else
				left = trial
				left_value = trial_value
			end
		end
	end
	converged = bracketed_signed_crossing && (right - left <= tolerance || imag(left_value) == 0 || imag(right_value) == 0)
	converged || push!(failure_codes, "refinement.frequency_tolerance_not_met")
	refined_frequency_hz = abs(imag(left_value)) <= abs(imag(right_value)) ? left : right
	refined_value = evaluate_actual(refined_frequency_hz, "final_gate_evidence")
	trust_start, trust_stop = Float64.(Tuple(trust_interval_hz))
	trust_start <= refined_frequency_hz <= trust_stop || push!(failure_codes, "continuation.outside_trust_interval")
	if !isnothing(expected_orientation) && orientation != Int(expected_orientation)
		push!(failure_codes, "continuation.orientation_mismatch")
	end
	abs(real(refined_value)) <= max_abs_re_ohm || push!(failure_codes, "residual.real_gate")
	abs(imag(refined_value)) <= max_abs_im_ohm || push!(failure_codes, "residual.imag_gate")
	abs(refined_value) <= max_abs_complex_ohm || push!(failure_codes, "residual.complex_gate")
	unique!(failure_codes)
	return (
		candidate_id = bracket.candidate_id,
		discovery = bracket,
		refinement = (
			method = "safeguarded_secant_bisection",
			frequency_tolerance_hz = tolerance,
			max_iterations = iterations_limit,
			iteration_count = iteration_count,
			final_bracket_hz = (left, right),
			converged = converged,
			actual_evaluations = evaluations,
			final_evidence_source = "fresh_actual_arbitrary_frequency_hb_ptc_not_interpolation",
		),
		frequency_hz = refined_frequency_hz,
		z21_ptc_ohm = refined_value,
		bracketed_signed_crossing = bracketed_signed_crossing,
		orientation = Int(orientation),
		trust_interval_hz = (trust_start, trust_stop),
		residuals = (
			re_ohm = real(refined_value),
			im_ohm = imag(refined_value),
			abs_ohm = abs(refined_value),
		),
		eligible = isempty(failure_codes),
		failure_codes = failure_codes,
	)
end

"""Track one bracketed signed complex-Z21 crossing across the diagonal-preserving homotopy.

Every lambda step publishes all refined roots, including ineligible ones. The
declared trust interval must contain exactly one eligible root; the function
never chooses the nearest candidate or falls back to scan interpolation.
"""
function _z21_ptc_complex_zero_continuation(
	coupling_fractions,
	scan_evidence_at_fraction,
	actual_z21_at_fraction_frequency;
	target_hz,
	half_width_hz,
	frequency_tolerance_hz,
	max_iterations,
	max_abs_re_ohm,
	max_abs_im_ohm,
	max_abs_complex_ohm,
	max_continuation_step_hz,
	require_same_orientation,
	continuation_id,
)
	fractions = Float64.(collect(coupling_fractions))
	fractions == [0.0, 0.25, 0.5, 0.75, 1.0] || error(
		"Z21 PTC coupling fractions must be exactly [0, 0.25, 0.5, 0.75, 1].",
	)
	all(value -> isfinite(value) && value > 0, (
		Float64(target_hz),
		Float64(half_width_hz),
		Float64(frequency_tolerance_hz),
		Float64(max_continuation_step_hz),
	)) || error("Z21 PTC target, scan width, tolerance, and continuation step must be finite and positive.")
	Int(max_iterations) > 0 || error("Z21 PTC refinement max iterations must be positive.")
	all(value -> isfinite(value) && value >= 0, (
		Float64(max_abs_re_ohm),
		Float64(max_abs_im_ohm),
		Float64(max_abs_complex_ohm),
	)) || error("Z21 PTC complex residual gates must be finite and non-negative.")
	steps = NamedTuple[]
	previous_frequency_hz = nothing
	reference_orientation = nothing
	for (step_index, fraction) in pairs(fractions)
		scan = scan_evidence_at_fraction(fraction)
		frequencies = Float64.(collect(scan.frequencies_hz))
		z21 = ComplexF64.(collect(scan.z21_ptc))
		length(frequencies) == length(z21) || error("Z21 PTC scan evidence lengths differ.")
		trust_interval_hz = if isnothing(previous_frequency_hz)
			(Float64(target_hz - half_width_hz), Float64(target_hz + half_width_hz))
		else
			(
				max(Float64(target_hz - half_width_hz), previous_frequency_hz - max_continuation_step_hz),
				min(Float64(target_hz + half_width_hz), previous_frequency_hz + max_continuation_step_hz),
			)
		end
		brackets = _z21_ptc_sign_brackets(frequencies, z21, target_hz, half_width_hz)
		candidates = [
			_refine_z21_ptc_sign_bracket(
				frequency -> actual_z21_at_fraction_frequency(fraction, frequency),
				bracket;
				frequency_tolerance_hz = frequency_tolerance_hz,
				max_iterations = max_iterations,
				max_abs_re_ohm = max_abs_re_ohm,
				max_abs_im_ohm = max_abs_im_ohm,
				max_abs_complex_ohm = max_abs_complex_ohm,
				trust_interval_hz = trust_interval_hz,
				expected_orientation = require_same_orientation ? reference_orientation : nothing,
			)
			for bracket in brackets
		]
		eligible = [candidate for candidate in candidates if candidate.eligible]
		step_role = step_index == 1 ? "reference" : (step_index == length(fractions) ? "loaded" : "continuation")
		step = (
			step_index = step_index,
			role = step_role,
			coupling_fraction = fraction,
			continuation_id = String(continuation_id),
			trust_interval_hz = trust_interval_hz,
			scan_provenance = scan.provenance,
			all_roots = candidates,
			eligible_candidate_ids = [candidate.candidate_id for candidate in eligible],
			eligible = length(eligible) == 1,
			failure_codes = length(eligible) == 1 ? String[] : [
				isempty(eligible) ? "continuation.no_eligible_root" : "continuation.multiple_eligible_roots",
			],
		)
		length(eligible) == 1 || reject_d3_candidate(
			step_index == 1 ? "notch.reference_root_count" : "notch.continuation_root_count",
			"Z21 PTC $(step_role) step requires exactly one eligible root in its declared trust interval; found $(length(eligible)).";
			details = (
				schema_version = "d3-z21-ptc-complex-zero.v2",
				continuation_id = String(continuation_id),
				completed_steps = steps,
				failed_step = step,
			),
		)
		selected = only(eligible)
		step = merge(step, (selected = selected,))
		push!(steps, step)
		previous_frequency_hz = selected.frequency_hz
		isnothing(reference_orientation) && (reference_orientation = selected.orientation)
	end
	return (
		schema_version = "d3-z21-ptc-complex-zero.v2",
		status = "eligible",
		continuation_id = String(continuation_id),
		thresholds = (
			frequency_tolerance_hz = Float64(frequency_tolerance_hz),
			max_iterations = Int(max_iterations),
			max_abs_re_ohm = Float64(max_abs_re_ohm),
			max_abs_im_ohm = Float64(max_abs_im_ohm),
			max_abs_complex_ohm = Float64(max_abs_complex_ohm),
			coupling_fractions = fractions,
			max_continuation_step_hz = Float64(max_continuation_step_hz),
			require_same_orientation = Bool(require_same_orientation),
		),
		reference = first(steps).selected,
		loaded = last(steps).selected,
		steps = steps,
		all_roots = [(coupling_fraction = step.coupling_fraction, roots = step.all_roots) for step in steps],
		refinement = "every_scan_sign_bracket_refined_with_fresh_actual_HB_PTC_evaluations",
		provenance = (
			discovery = "scan_interpolation_discovers_brackets_only",
			final_evidence = "actual_arbitrary_frequency_HB_PTC_evaluation",
			selection = "exactly_one_eligible_root_per_declared_trust_interval_no_nearest_fallback",
			topology = "diagonal_preserving_Cr_homotopy",
			endpoint_composition = D3_Z21_PTC_ENDPOINT_COMPOSITION_PROVENANCE,
		),
		eligible = true,
		failure_codes = String[],
	)
end

"""Build one intrinsic Z21 continuation plan with a response-exact λ=0 endpoint.

Positive coupling fractions retain the node-preserving Cr homotopy. At exactly
zero coupling, the intrinsic two-port response factorizes from the disconnected
qubit dynamics, so this response view keeps the readout-side
`C0r + Cr1 + Cr2`
diagonal. The generic fraction builder remains node-preserving for consumers
that own qubit-node observables.
"""
function _build_intrinsic_z21_ptc_plan(
	case,
	design;
	floating_qubit_nominal,
	hb_settings,
	coupling_fraction,
)
	fraction = Float64(coupling_fraction)
	isfinite(fraction) && 0 <= fraction <= 1 || error(
		"Intrinsic Z21 PTC coupling fraction must be finite and lie in [0, 1].",
	)
	plan = if fraction == 0.0
		build_intrinsic_pair_plan(
			case,
			design;
			hb_settings = hb_settings,
			floating_qubit_nominal = floating_qubit_nominal,
			qubit_coupling_state = :diagonal_preserving_off,
		)
	else
		build_intrinsic_pair_plan(
			case,
			design;
			hb_settings = hb_settings,
			floating_qubit_nominal = floating_qubit_nominal,
			qubit_coupling_fraction = fraction,
		)
	end
	plan.metadata[:d3_qubit_coupling_fraction] = fraction
	plan.metadata[:d3_z21_ptc_endpoint_composition] = fraction == 0.0 ?
		D3_Z21_PTC_FACTORIZED_ENDPOINT_COMPOSITION :
		D3_Z21_PTC_CONNECTED_ENDPOINT_COMPOSITION
	return plan
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
			cost_publication_status = record.cost_publication_status,
			promotion_eligible = record.promotion_eligible,
			promotion_blockers = record.promotion_blockers,
			metrics = record.metrics,
			diagnostics = record.diagnostics,
		))
	elseif record.status === :inspectable
		_d3_plain_data((
			candidate = candidate,
			status = "inspectable",
			cost_publication_status = record.cost_publication_status,
			publication_blockers = record.publication_blockers,
			promotion_eligible = record.promotion_eligible,
			promotion_blockers = record.promotion_blockers,
			diagnostics = record.diagnostics,
			traces = record.traces,
		))
	elseif record.status === :rejected
		_d3_plain_data((
			candidate = candidate,
			status = "rejected",
			cost_publication_status = record.cost_publication_status,
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

function _d3_qubit_with_lj(qubit::D3FloatingQubitNominal, lj_per_junction_h)
	lj_h = Float64(lj_per_junction_h)
	isfinite(lj_h) && lj_h > 0 || error("System-C L_J sweep requires positive finite per-junction inductance.")
	return D3FloatingQubitNominal(
		model_id = qubit.model_id,
		capacitance_source_id = qubit.capacitance_source_id,
		C01_fF = qubit.C01_fF,
		C02_fF = qubit.C02_fF,
		C12_fF = qubit.C12_fF,
		Cr1_fF = qubit.Cr1_fF,
		Cr2_fF = qubit.Cr2_fF,
		C0r_fF = qubit.C0r_fF,
		L_J_per_junction_nH = lj_h / D3_HENRIES_PER_NH,
		electrostatic_reduction = qubit.electrostatic_reduction,
	)
end

function _d3_system_c_lj_sweep(
	qubit::D3FloatingQubitNominal,
	slot_hz,
	nominal_lj_per_junction_h,
	settings,
)
	contract = settings.system_c_s21_lj_sweep
	cq_eff_f = floating_qubit_capacitance_layers(qubit).Cq_LB_fF * D3_FARADS_PER_FF
	q_identification_hz = Float64(slot_hz) .+ Float64.(contract["q_diagonal_identification_offsets_from_slot_hz"])
	all(value -> isfinite(value) && value > 0, q_identification_hz) || error(
		"System-C q-diagonal identification frequencies must be finite and positive.",
	)
	lj_points_h = [2 / ((2π * frequency_hz)^2 * cq_eff_f) for frequency_hz in q_identification_hz]
	nominal_lj_h = Float64(nominal_lj_per_junction_h)
	isfinite(nominal_lj_h) && nominal_lj_h > 0 || error(
		"System-C injected nominal per-junction L_J must be finite and positive.",
	)
	push!(lj_points_h, nominal_lj_h)
	length(unique(lj_points_h)) >= 9 || error(
		"System-C sweep must contain nine distinct L_J points after adding nominal 21.5 nH to the eight off-center identification samples.",
	)
	sort!(lj_points_h)
	return (
		cq_eff_seed_f = cq_eff_f,
		lj_per_junction_h = lj_points_h,
		q_diagonal_hz = [1 / (2π * sqrt((lj_h / 2) * cq_eff_f)) for lj_h in lj_points_h],
	)
end

function _d3_system_c_frequency_grid(predicted_poles_hz, settings)
	contract = settings.system_c_s21_lj_sweep
	step_hz = Float64(contract["frequency_step_hz"])
	half_window_hz = Float64(contract["local_pole_half_window_hz"])
	wing_hz = Float64(contract["affine_nuisance_wing_hz"])
	poles_hz = sort(Float64.(predicted_poles_hz))
	length(poles_hz) == 3 && all(value -> isfinite(value) && value > 0, poles_hz) || error(
		"System-C grid construction requires three positive finite predicted poles.",
	)
	windows = [[pole_hz - half_window_hz, pole_hz + half_window_hz] for pole_hz in poles_hz]
	windows[1][1] -= wing_hz
	windows[end][2] += wing_hz
	grid = sort!(unique(vcat([
		collect((floor(window[1] / step_hz) * step_hz):step_hz:(ceil(window[2] / step_hz) * step_hz))
		for window in windows
	]...)))
	length(grid) >= Int(contract["gates"]["min_samples_per_trace"]) || error(
		"System-C per-trace union grid is shorter than min_samples_per_trace.",
	)
	return (frequencies_hz = grid, predicted_poles_hz = poles_hz, local_windows_hz = windows)
end

const D3_SYSTEM_C_SOURCE_TO_SEED_PARAMETER = Dict(
	"system_a" => Dict("g_system_a_on_hz" => "g_system_c_on_hz"),
	"system_b" => Dict(
		"f_r_lb_system_b_on_hz" => "f_r_lb_system_c_on_hz",
		"f_p_lb_system_b_on_hz" => "f_p_lb_system_c_on_hz",
		"j_system_b_on_hz" => "j_system_c_on_hz",
		"kappa_p_ext_lb_system_b_on_hz" => "kappa_p_ext_lb_system_c_on_hz",
	),
	"off_reference" => Dict(
		"c_q_eff_off_reference_f" => "c_q_eff_f",
		"f_r_off_reference_hz" => "f_r_lb_system_c_on_hz",
		"f_p_off_reference_hz" => "f_p_lb_system_c_on_hz",
		"kappa_p_ext_off_reference_hz" => "kappa_p_ext_lb_system_c_on_hz",
	),
)

function _d3_system_c_fit_contract(
	settings,
	sweep,
	target_values;
	source_estimates = Dict{String,Any}(),
)
	contract = settings.system_c_s21_lj_sweep
	bound_settings = contract["physical_bounds"]
	targets = _d3_system_c_target_values(target_values)
	cq_seed_f = Float64(sweep.cq_eff_seed_f)
	frequency_half_width_hz = Float64(bound_settings["diagonal_frequency_half_width_hz"])
	physical_bounds = Dict(
		"c_q_eff_f" => cq_seed_f .* [1 - Float64(bound_settings["c_q_eff_relative_half_width"]), 1 + Float64(bound_settings["c_q_eff_relative_half_width"])],
		"f_r_lb_system_c_on_hz" => targets["system_c_readout_loaded_bare_hz"] .+ [-frequency_half_width_hz, frequency_half_width_hz],
		"f_p_lb_system_c_on_hz" => targets["system_c_filter_loaded_bare_hz"] .+ [-frequency_half_width_hz, frequency_half_width_hz],
		"g_system_c_on_hz" => Float64.(bound_settings["g_system_c_on_hz"]),
		"g_qp_system_c_on_hz" => Float64.(bound_settings["g_qp_system_c_on_hz"]),
		"j_system_c_on_hz" => Float64.(bound_settings["j_system_c_on_hz"]),
		"kappa_p_ext_lb_system_c_on_hz" => Float64.(bound_settings["kappa_p_ext_lb_system_c_on_hz"]),
	)
	parameter_order = [
		"c_q_eff_f", "f_r_lb_system_c_on_hz", "f_p_lb_system_c_on_hz",
		"g_system_c_on_hz", "g_qp_system_c_on_hz", "j_system_c_on_hz", "kappa_p_ext_lb_system_c_on_hz",
	]
	centers = Dict(
		"c_q_eff_f" => cq_seed_f,
		"f_r_lb_system_c_on_hz" => targets["system_c_readout_loaded_bare_hz"],
		"f_p_lb_system_c_on_hz" => targets["system_c_filter_loaded_bare_hz"],
		"g_system_c_on_hz" => targets["system_c_g_hz"],
		"g_qp_system_c_on_hz" => 0.0,
		"j_system_c_on_hz" => targets["system_c_j_hz"],
		"kappa_p_ext_lb_system_c_on_hz" => targets["system_c_filter_loaded_bare_external_linewidth_hz"],
	)
	all(name -> begin
		lower, upper = physical_bounds[name]
		name == "g_qp_system_c_on_hz" ? lower < 0 < upper : 0 < lower < upper
	end, parameter_order) || error(
		"System-C physical bounds must be ordered; only signed g_qp may straddle zero.",
	)
	all(name -> begin
		lower, upper = physical_bounds[name]
		lower < centers[name] && centers[name] < upper
	end, parameter_order) || error("Canonical target-centered System-C seed lies outside its reviewed bounds.")
	physical_seed_normalized_offsets = Float64.(contract["physical_seed_normalized_offsets"])
	physical_seeds = [Dict(
		name => begin
			lower, upper = physical_bounds[name]
			center = centers[name]
			offset < 0 ? center + abs(offset) * (lower - center) : center + offset * (upper - center)
		end
		for name in parameter_order
	) for offset in physical_seed_normalized_offsets]
	converted_sources = Dict(
		String(group) => Dict(String(name) => Float64(value) for (name, value) in pairs(estimate))
		for (group, estimate) in pairs(source_estimates)
	)
	mapped_system_c_seed_estimates = Dict{String,Dict{String,Float64}}()
	source_to_system_c_seed_mapping = Dict{String,Any}[]
	initializer_seed_evidence = Dict{String,Any}[]
	for group in sort!(collect(keys(converted_sources)))
		expected_mapping = get(D3_SYSTEM_C_SOURCE_TO_SEED_PARAMETER, group, nothing)
		source_keys = Set(keys(converted_sources[group]))
		exact_source_contract = !isnothing(expected_mapping) && source_keys == Set(keys(expected_mapping))
		mapped_overrides = Dict{String,Float64}()
		mapping_rows = Dict{String,Any}[]
		if !isnothing(expected_mapping)
			for source_name in sort!(collect(intersect(source_keys, Set(keys(expected_mapping)))))
				target_name = expected_mapping[source_name]
				value = converted_sources[group][source_name]
				mapped_overrides[target_name] = value
				push!(mapping_rows, Dict(
					"source_parameter" => source_name,
					"system_c_seed_parameter" => target_name,
					"value" => value,
					"source_role" => group == "system_b" && source_name != "j_system_b_on_hz" ?
						"fixed_off_reference_derived_input" : "estimated_source_quantity",
				))
			end
		end
		append!(source_to_system_c_seed_mapping, [
			merge(row, Dict("comparison_group" => group)) for row in mapping_rows
		])
		seed = copy(centers)
		exact_source_contract && merge!(seed, mapped_overrides)
		inside = exact_source_contract && all(name -> begin
			lower, upper = physical_bounds[name]
			lower < seed[name] < upper
		end, parameter_order)
		status = !exact_source_contract ? "invalid_source_contract_not_appended" :
			(inside ? "appended" : "outside_bounds_not_appended")
		push!(initializer_seed_evidence, Dict(
			"comparison_group" => group,
			"status" => status,
			"source_estimates" => converted_sources[group],
			"source_to_system_c_seed_mapping" => mapping_rows,
			"mapped_system_c_seed_overrides" => mapped_overrides,
			"seed" => seed,
		))
		if exact_source_contract
			mapped_system_c_seed_estimates[group] = mapped_overrides
			inside && push!(physical_seeds, seed)
		end
	end
	return (
		physical_bounds = physical_bounds,
		physical_seeds = physical_seeds,
		multi_start_coverage_seed_count = length(physical_seed_normalized_offsets),
		target_centered_seed = centers,
		source_estimates = converted_sources,
		mapped_system_c_seed_estimates = mapped_system_c_seed_estimates,
		source_to_system_c_seed_mapping = source_to_system_c_seed_mapping,
		initializer_seed_evidence = initializer_seed_evidence,
	)
end

function _d3_system_c_comparison_status(source_estimates)
	required = Set(keys(D3_SYSTEM_C_SOURCE_TO_SEED_PARAMETER))
	available = Set(String(key) for key in keys(source_estimates))
	expected_ownership_sets = Dict(
		group => Set(keys(mapping)) for (group, mapping) in D3_SYSTEM_C_SOURCE_TO_SEED_PARAMETER
	)
	observed_ownership_sets = Dict(
		group => Set(String(key) for key in keys(source_estimates[group]))
		for group in intersect(required, available)
	)
	invalid_ownership_sets = Dict(
		group => observed_ownership_sets[group]
		for group in keys(observed_ownership_sets)
		if observed_ownership_sets[group] != expected_ownership_sets[group]
	)
	as_sorted_vectors(ownership) = Dict(
		group => sort!(collect(ownership[group]))
		for group in sort!(collect(keys(ownership)))
	)
	complete = available == required && isempty(invalid_ownership_sets)
	return (
		complete = complete,
		required_groups = sort!(collect(required)),
		available_groups = sort!(collect(available)),
		missing_groups = sort!(collect(setdiff(required, available))),
		unexpected_groups = sort!(collect(setdiff(available, required))),
		expected_ownership = as_sorted_vectors(expected_ownership_sets),
		observed_ownership = as_sorted_vectors(observed_ownership_sets),
		invalid_ownership = as_sorted_vectors(invalid_ownership_sets),
	)
end

function _d3_system_c_promotion_status(
	source_estimates,
	labeled_estimate_deltas,
	initializer_seed_evidence,
)
	comparison_status = _d3_system_c_comparison_status(source_estimates)
	initializer_seed_evidence isa AbstractVector || error("System-C initializer seed evidence must be a vector.")
	seed_rows = map(initializer_seed_evidence) do row
		row isa AbstractDict || error("Every System-C initializer seed evidence row must be a mapping.")
		(comparison_group = String(row["comparison_group"]), status = String(row["status"]))
	end
	observed_seed_groups = [row.comparison_group for row in seed_rows]
	initializer_seed_status = (
		complete = Set(observed_seed_groups) == Set(comparison_status.required_groups) &&
			length(observed_seed_groups) == length(unique(observed_seed_groups)) &&
			all(row -> row.status == "appended", seed_rows),
		observed_comparison_groups = observed_seed_groups,
		non_appended_comparison_groups = sort!(unique([
			row.comparison_group for row in seed_rows if row.status != "appended"
		])),
		rows = seed_rows,
	)
	deltas = labeled_estimate_deltas isa AbstractDict ? Dict(
		String(group) => Dict(String(name) => value for (name, value) in pairs(group_deltas))
		for (group, group_deltas) in pairs(labeled_estimate_deltas)
	) : Dict{String,Any}()
	expected_delta_ownership = Dict(
		group => sort!(collect(values(mapping)))
		for (group, mapping) in D3_SYSTEM_C_SOURCE_TO_SEED_PARAMETER
	)
	observed_delta_ownership = Dict(
		group => sort!(String.(collect(keys(group_deltas)))) for (group, group_deltas) in deltas
	)
	delta_status = (
		complete = Set(keys(deltas)) == Set(keys(expected_delta_ownership)) && all(
			group -> get(observed_delta_ownership, group, String[]) == expected_delta_ownership[group],
			keys(expected_delta_ownership),
		),
		expected_ownership = expected_delta_ownership,
		observed_ownership = observed_delta_ownership,
	)
	blockers = NamedTuple[]
	comparison_status.complete || push!(blockers, (
		code = "system_c.comparison_source_incomplete",
		reason = "System-A, System-B, and off-reference source quantities are incomplete or have invalid ownership.",
		details = comparison_status,
	))
	initializer_seed_status.complete || push!(blockers, (
		code = "system_c.initializer_seed_incomplete",
		reason = "Every comparison source must append exactly one in-bounds System-C initializer seed.",
		details = initializer_seed_status,
	))
	delta_status.complete || push!(blockers, (
		code = "system_c.comparison_delta_incomplete",
		reason = "Mapped System-C fit deltas are incomplete for the required comparison sources.",
		details = delta_status,
	))
	return (
		promotion_eligible = isempty(blockers),
		promotion_blockers = blockers,
		comparison_status = comparison_status,
		initializer_seed_status = initializer_seed_status,
		delta_status = delta_status,
	)
end

function _d3_system_c_publication_status(
	system_c_fit,
	initializer_attempt,
	initializer_seed_evidence,
)
	system_c_fit isa AbstractDict || error("System-C fit result must be a mapping.")
	initializer_attempt isa Union{AbstractDict,NamedTuple} || error(
		"System-C initializer attempt evidence must be a mapping.",
	)
	initializer_seed_evidence isa AbstractVector || error(
		"System-C initializer seed evidence must be a vector.",
	)
	compact_evidence = Dict(
		String(key) => value for (key, value) in pairs(system_c_fit) if String(key) != "fit_traces"
	)
	get(system_c_fit, "status", nothing) == "success" || reject_d3_candidate(
		"system_c.global_fit_gate",
		"System-C global complex-S21 L_J-sweep fit rejected the candidate: $(join(get(system_c_fit, "failure_reasons", ["unstated reason"]), "; ")).";
		details = (
			initializer_attempt = initializer_attempt,
			initializer_seed_evidence = initializer_seed_evidence,
			primary_fit_evidence = compact_evidence,
			cost_publication_status = "withheld",
			promotion_eligible = false,
		),
	)
	return (
		record_status = :valid,
		cost_publication_status = "published",
		publication_blockers = NamedTuple[],
		chain_reduction_check = get(system_c_fit, "chain_reduction_check", nothing),
	)
end

function _d3_bidirectional_bright_pole_assignments(
	system_c_candidates,
	vf_candidates,
	maximum_frequency_disagreement_hz,
	maximum_linewidth_disagreement_hz;
	trace_id,
	previous_assignment_state = nothing,
)
	system_c_bright = sort(filter(candidate -> candidate.eligible, system_c_candidates); by = candidate -> candidate.mode_index)
	vf_bright = sort(filter(candidate -> candidate.eligible, vf_candidates); by = candidate -> candidate.storage_index)
	!isempty(system_c_bright) || reject_d3_candidate(
		"system_c.no_bright_derived_pole",
		"System-C produced no projected-residue-qualified derived pole for the VF cross-check.";
		details = (trace_id = trace_id, candidates = system_c_candidates),
	)
	!isempty(vf_bright) || reject_d3_candidate(
		"system_c.vf_no_bright_pole",
		"System-C VF found no residue-qualified bright pole.";
		details = (trace_id = trace_id, candidates = vf_candidates),
	)
	length(system_c_bright) == length(vf_bright) || reject_d3_candidate(
		"system_c.vf_bright_pole_count_mismatch",
		"Bidirectional VF validation requires equal counts of bright System-C and eligible VF poles.";
		details = (trace_id = trace_id, system_c_bright_poles = system_c_bright, vf_bright_poles = vf_bright),
	)
	frequency_gate_hz = Float64(maximum_frequency_disagreement_hz)
	linewidth_gate_hz = Float64(maximum_linewidth_disagreement_hz)
	isfinite(frequency_gate_hz) && frequency_gate_hz > 0 || error("VF frequency gate must be positive and finite.")
	isfinite(linewidth_gate_hz) && linewidth_gate_hz > 0 || error("VF linewidth gate must be positive and finite.")
	function permutations(values)
		length(values) <= 1 && return [collect(values)]
		result = Vector{Vector{Int}}()
		for index in eachindex(values)
			remainder = [values[position] for position in eachindex(values) if position != index]
			for tail in permutations(remainder)
				push!(result, vcat(values[index], tail))
			end
		end
		return result
	end
	function pair_evidence(system_c, vf)
		overlap = abs(sum(conj.(system_c.response_signature) .* vf.response_signature))
		frequency_residual_hz = vf.frequency_hz - system_c.frequency_hz
		linewidth_residual_hz = vf.linewidth_hz - system_c.linewidth_hz
		previous = isnothing(previous_assignment_state) ? nothing : get(previous_assignment_state, system_c.mode_index, nothing)
		continuation_frequency_residual_hz = isnothing(previous) ? 0.0 :
			(vf.frequency_hz - previous.vf_frequency_hz) -
			(system_c.frequency_hz - previous.system_c_frequency_hz)
		continuation_linewidth_residual_hz = isnothing(previous) ? 0.0 :
			(vf.linewidth_hz - previous.vf_linewidth_hz) -
			(system_c.linewidth_hz - previous.system_c_linewidth_hz)
		components = (
			frequency = abs(frequency_residual_hz) / frequency_gate_hz,
			linewidth = abs(linewidth_residual_hz) / linewidth_gate_hz,
			complex_response_signature = 1 - clamp(overlap, 0.0, 1.0),
			continuation_frequency = abs(continuation_frequency_residual_hz) / frequency_gate_hz,
			continuation_linewidth = abs(continuation_linewidth_residual_hz) / linewidth_gate_hz,
		)
		return (
			association_policy = "sweep_continuation_plus_complex_residue_response_signature_permutation",
			system_c_branch_identity = "continued_mu_$(system_c.mode_index)",
			system_c_mode_index = system_c.mode_index,
			system_c_frequency_hz = system_c.frequency_hz,
			system_c_linewidth_hz = system_c.linewidth_hz,
			system_c_projected_residue_response_ratio = system_c.projected_residue_response_ratio,
			vf_pole_identity = "stored_pole_$(vf.storage_index)",
			vf_storage_index = vf.storage_index,
			vf_frequency_hz = vf.frequency_hz,
			vf_linewidth_hz = vf.linewidth_hz,
			vf_residue_response_ratio = vf.residue_response_ratio,
			frequency_residual_hz = frequency_residual_hz,
			linewidth_residual_hz = linewidth_residual_hz,
			complex_response_signature_overlap = overlap,
			continuation_available = !isnothing(previous),
			continuation_frequency_residual_hz = continuation_frequency_residual_hz,
			continuation_linewidth_residual_hz = continuation_linewidth_residual_hz,
			score_components = components,
			pair_score = sum(components),
		)
	end
	function assignment_for(order)
		pairs = [pair_evidence(system_c, vf) for (system_c, vf) in zip(system_c_bright, vf_bright[order])]
		return (order = collect(order), pairs = pairs, score = sum(pair.pair_score for pair in pairs))
	end
	all_assignments = [assignment_for(order) for order in permutations(collect(eachindex(vf_bright)))]
	sort!(all_assignments; by = assignment -> assignment.score)
	winner = first(all_assignments)
	runner_up = length(all_assignments) == 1 ? nothing : all_assignments[2]
	unique_margin = isnothing(runner_up) ? nothing : runner_up.score - winner.score
	(isnothing(unique_margin) || unique_margin > max(1e-12, 1e-9 * max(1.0, abs(winner.score)))) || reject_d3_candidate(
		"system_c.vf_assignment_ambiguity",
		"VF-to-System-C sweep association has no unique residue-signature and continuation-scored permutation; rank or nearest-frequency fallback is forbidden.";
		details = (
			trace_id = trace_id,
			winning_score = winner.score,
			runner_up_score = isnothing(runner_up) ? nothing : runner_up.score,
			winning_margin = unique_margin,
			candidate_assignments = all_assignments,
			maximum_frequency_disagreement_hz = frequency_gate_hz,
			maximum_linewidth_disagreement_hz = linewidth_gate_hz,
		),
	)
	all(pair -> abs(pair.frequency_residual_hz) <= frequency_gate_hz, winner.pairs) || reject_d3_candidate(
		"system_c.vf_pole_disagreement",
		"The uniquely associated VF permutation violates the reviewed frequency gate.";
		details = (trace_id = trace_id, winning_assignment = winner, maximum_hz = frequency_gate_hz),
	)
	all(pair -> abs(pair.linewidth_residual_hz) <= linewidth_gate_hz, winner.pairs) || reject_d3_candidate(
		"system_c.vf_linewidth_disagreement",
		"The uniquely associated VF permutation violates the reviewed total-linewidth gate.";
		details = (trace_id = trace_id, winning_assignment = winner, maximum_hz = linewidth_gate_hz),
	)
	state = Dict{Int,Any}()
	if !isnothing(previous_assignment_state)
		previous_assignment_state isa AbstractDict || error("Previous VF assignment state must be a mapping.")
		for (mode_index, last_seen) in pairs(previous_assignment_state)
			state[Int(mode_index)] = last_seen
		end
	end
	for pair in winner.pairs
		state[pair.system_c_mode_index] = (
			system_c_frequency_hz = pair.system_c_frequency_hz,
			system_c_linewidth_hz = pair.system_c_linewidth_hz,
			vf_frequency_hz = pair.vf_frequency_hz,
			vf_linewidth_hz = pair.vf_linewidth_hz,
			vf_storage_index = pair.vf_storage_index,
		)
	end
	return (
		assignments = winner.pairs,
		assignment_state = state,
		score_evidence = (
			winning_score = winner.score,
			runner_up_score = isnothing(runner_up) ? nothing : runner_up.score,
			winning_margin = unique_margin,
			runner_up_exists = !isnothing(runner_up),
			unique_without_competitor = isnothing(runner_up),
			candidate_scores = [(order = assignment.order, score = assignment.score) for assignment in all_assignments],
		),
	)
end

function _d3_system_c_vf_crosscheck(trace, fitted_trace, settings; previous_assignment_state = nothing)
	contract = settings.system_c_s21_lj_sweep
	normalized_s21 = _normalized_s21(
		trace.frequency_hz,
		trace.s21,
		trace.empty_feedline_s21,
		settings.min_reference_magnitude,
	)
	result = fit_vector_s21(
		trace.frequency_hz,
		normalized_s21;
		n_resonators = 3,
		bg_poles = settings.vector_bg_poles,
		max_iterations = settings.vector_max_iterations,
		min_q = settings.vector_min_q,
		restrict_to_input_span = true,
	)
	get(result, "schema_version", nothing) == "scalar-s21-vector-fit.v2" || error(
		"System-C VF cross-check requires scalar-s21-vector-fit.v2.",
	)
	get(result, "status", nothing) == "success" || reject_d3_candidate(
		"system_c.vf_failure",
		"System-C VF cross-check failed: $(get(result, "reason", "unstated reason")).";
		details = (trace_id = trace.trace_id,),
	)
	get(get(result, "fit_diagnostics", Dict()), "converged", false) === true || reject_d3_candidate(
		"system_c.vf_not_converged",
		"System-C VF cross-check did not converge.";
		details = (trace_id = trace.trace_id, fit_diagnostics = get(result, "fit_diagnostics", nothing)),
	)
	rms_error = Float64(get(get(result, "metrics", Dict()), "rms_error", Inf))
	rms_error <= settings.max_vector_rms_error || reject_d3_candidate(
		"system_c.vf_rms_gate",
		"System-C VF cross-check exceeds the configured RMS gate.";
		details = (trace_id = trace.trace_id, rms_error = rms_error, maximum = settings.max_vector_rms_error),
	)
	rational_poles = result["rational_model"]["poles"]
	model_trace = result["model_trace"]
	model_frequencies_hz = Float64.(model_trace["frequency_hz"])
	model_s21 = ComplexF64.(Float64.(model_trace["s21_real"]) .+ im .* Float64.(model_trace["s21_imag"]))
	model_scale = maximum(abs.(model_s21))
	model_scale > 0 || error("System-C VF model response scale must be positive.")
	laplace_s = 2π * im .* model_frequencies_hz
	minimum_ratio = Float64(contract["bright_vf_min_residue_response_ratio"])
	classified = map(result["resonances"]) do resonance
		matches = filter(rational_poles) do pole
			get(pole, "classification", nothing) == "resonance" &&
			get(pole, "pole_real_rad_per_s", nothing) == get(resonance, "pole_real_rad_per_s", nothing) &&
			get(pole, "pole_imag_rad_per_s", nothing) == get(resonance, "pole_imag_rad_per_s", nothing)
		end
		length(matches) == 1 || error("System-C VF resonance does not map to exactly one stored pole/residue record.")
		pole = only(matches)
		candidate = _scalar_candidate_resonance_record(resonance, pole, laplace_s, model_scale, minimum_ratio)
		vf_pole_rad_per_s = ComplexF64(Float64(pole["pole_real_rad_per_s"]), Float64(pole["pole_imag_rad_per_s"]))
		vf_residue_rad_per_s = ComplexF64(Float64(pole["residue_real_rad_per_s"]), Float64(pole["residue_imag_rad_per_s"]))
		response = vf_residue_rad_per_s ./ (laplace_s .- vf_pole_rad_per_s)
		norm_value = norm(response)
		norm_value > 0 || error("VF pole-response signature norm must be positive.")
		merge(candidate, (response_signature = response ./ norm_value,))
	end
	system_c_candidates = map(fitted_trace["hybridized_poles"]) do pole
		complex_pole_hz = ComplexF64(
			Float64(pole["complex_pole_real_hz"]),
			Float64(pole["complex_pole_imag_hz"]),
		)
		projected_residue_hz = ComplexF64(
			Float64(pole["projected_s21_residue_real_hz"]),
			Float64(pole["projected_s21_residue_imag_hz"]),
		)
		response = projected_residue_hz ./ (model_frequencies_hz .- complex_pole_hz)
		response_ratio = maximum(abs.(response)) / model_scale
		norm_value = norm(response)
		norm_value > 0 || error("System-C projected pole-response signature norm must be positive.")
		(
			mode_index = Int(pole["mu"]),
			frequency_hz = Float64(pole["frequency_hz"]),
			linewidth_hz = Float64(pole["total_linewidth_hz"]),
			projected_residue_response_ratio = response_ratio,
			eligible = response_ratio >= minimum_ratio,
			response_signature = response ./ norm_value,
		)
	end
	frequency_gate_hz = Float64(contract["max_vf_pole_disagreement_hz"])
	linewidth_gate_hz = Float64(contract["max_vf_linewidth_disagreement_hz"])
	association = _d3_bidirectional_bright_pole_assignments(
		system_c_candidates,
		classified,
		frequency_gate_hz,
		linewidth_gate_hz;
		trace_id = trace.trace_id,
		previous_assignment_state = previous_assignment_state,
	)
	without_signature(candidate) = Dict(String(key) => value for (key, value) in pairs(candidate) if key != :response_signature)
	return (
		trace_id = trace.trace_id,
		schema_version = result["schema_version"],
		fit_settings = result["fit_settings"],
		sampling = result["sampling"],
		metrics = result["metrics"],
		fit_diagnostics = result["fit_diagnostics"],
		candidate_resonances = without_signature.(classified),
		system_c_candidate_poles = without_signature.(system_c_candidates),
		bidirectional_bright_pole_assignments = association.assignments,
		association_score_evidence = association.score_evidence,
		association_state = association.assignment_state,
		thresholds = (
			minimum_residue_response_ratio = minimum_ratio,
			maximum_pole_disagreement_hz = frequency_gate_hz,
			maximum_linewidth_disagreement_hz = linewidth_gate_hz,
		),
	)
end

function evaluate_d3_slot(evaluator::D3SlotEvaluator, candidate; capture_traces = false)
	key = Tuple(candidate)
	try
		design = _candidate_design(evaluator.seed_design, candidate)
		settings = evaluator.settings
		design_slot_hz = Float64(design.slot_target_ghz) * D3_HZ_PER_GHZ
		slot_hz = (
			evaluator.system_c_target_values["system_c_filter_loaded_bare_hz"] +
			evaluator.system_c_target_values["system_c_readout_loaded_bare_hz"]
		) / 2
		isapprox(design_slot_hz, slot_hz; atol = 1.0e-6, rtol = 0.0) || error(
			"Selected design slot disagrees with the injected System-C diagonal-target center.",
		)
		notch_target_hz = evaluator.system_c_target_values["system_c_intrinsic_notch_hz"]
		candidate_identity = _candidate_identity(candidate)
		filter_off_reference_frequencies_hz = _slot_frequency_grid(
			slot_hz,
			settings.reference_scan_half_width_hz,
			settings.frequency_step_hz,
		)
		filter_off_reference_grid_sha256 = _frequency_grid_sha256(filter_off_reference_frequencies_hz)
		pair_frequencies_hz = _slot_frequency_grid(
			slot_hz,
			settings.pair_trace_half_width_hz,
			settings.frequency_step_hz,
		)
		pair_grid_sha256 = _frequency_grid_sha256(pair_frequencies_hz)
		qubit_frequencies_hz = _slot_frequency_grid(
			evaluator.qubit_coupling_off_frequency_hz,
			settings.qubit_local_half_width_hz,
			settings.frequency_step_hz,
		)
		qubit_grid_sha256 = _frequency_grid_sha256(qubit_frequencies_hz)
		trace_identity = _d3_trace_identity(
			evaluator.case.id,
			design.id,
			candidate_identity,
			filter_off_reference_grid_sha256,
			pair_grid_sha256,
			qubit_grid_sha256,
			evaluator.floating_qubit_input_sha256,
		)
		reference_contract_id = trace_identity.reference_contract_id
		filter_off_reference_id = trace_identity.filter_off_reference_id
		common_readout_off_reference_id = trace_identity.common_readout_off_reference_id
		filter_off_reference_trace_id = trace_identity.filter_off_reference_trace_id
		off_reference_empty_feedline_trace_id = trace_identity.off_reference_empty_feedline_trace_id
		qubit_empty_feedline_trace_id = trace_identity.qubit_empty_feedline_trace_id
		calibration_id = trace_identity.calibration_id
		pair_measured_trace_id = trace_identity.pair_measured_trace_id
		pair_empty_feedline_trace_id = trace_identity.pair_empty_feedline_trace_id
		port_plane = "JosephsonCircuits external ports, 50 Ohm reference"
		comparison_estimates = Dict{String,Any}()
		initializer_stages = Dict{String,Dict{String,Any}}(
			"off_reference" => Dict{String,Any}("status" => "pending"),
			"system_a" => Dict{String,Any}("status" => "pending"),
			"system_b" => Dict{String,Any}("status" => "pending"),
		)
		initializer_failures = Dict{String,Any}()
		off_reference_probe_continuation = Any[]
		bare_frequency_evidence = nothing
		qubit_off_reference_hz = nothing
		off_reference_qubit_y = nothing
		off_reference_qubit_root = nothing
		filter_off_reference_reference = nothing
		filter_hb = nothing
		filter_mode = nothing
		channel_calibration = nothing
		readout_frequency_hz = nothing
		readout_off_reference_linewidth_hz = nothing
		readout_coupling_off_frequency_fit = nothing
		readout_linewidth_fit = nothing
		readout_frequency_fit = nothing
		qubit_frequency_fit = nothing
		coupling_on_readout_frequency_hz = nothing
		g_hz = nothing
		g_shift_fit_diagnostic = nothing
		readout_modes = Any[]
		coupling_off_modes = Any[]
		readout_captures = Any[]
		pair_reference = nothing
		system_b_pair_hb = nothing
		j_fit = nothing
		pair_vector_result = nothing
		vector_poles_hz = Float64[]
		try
		off_reference_qubit_weights = _qubit_common_coordinate_weights(
			evaluator.floating_qubit_nominal,
			:off_reference,
		)
		off_reference_qubit_plan = build_d3_qubit_admittance_plan(
			evaluator.floating_qubit_nominal;
			hb_settings = evaluator.hb_settings,
			loading_state = :off_reference,
		)
		off_reference_qubit_hb = _run_candidate_hb(
			evaluator,
			off_reference_qubit_plan,
			qubit_frequencies_hz,
			"standalone off-reference qubit differential admittance",
		)
		off_reference_qubit_y = _d3_differential_y_response(
			off_reference_qubit_hb;
			all_ports = (1, 2),
			island_ports = (1, 2),
			alpha = off_reference_qubit_weights.alpha,
			beta = off_reference_qubit_weights.beta,
			measurement_view = "standalone_two_island_port_off_reference_qubit_Ydiff",
		)
		off_reference_qubit_root = _extract_d3_unique_positive_slope_y_root_in_trust_interval(
			off_reference_qubit_y.frequencies_hz,
			off_reference_qubit_y.ydiff_siemens,
			evaluator.qubit_coupling_off_frequency_hz,
			settings.qubit_root_trust_half_width_hz;
			stage_label = "off-reference qubit differential admittance",
		)
		qubit_off_reference_hz = off_reference_qubit_root.frequency_hz
		filter_off_reference_reference = _reference_trace!(evaluator, filter_off_reference_frequencies_hz)
		qubit_reference = _reference_trace!(evaluator, qubit_frequencies_hz)
		bare_frequency_evidence = if capture_traces
			bare_weights = _qubit_common_coordinate_weights(evaluator.floating_qubit_nominal, :bare_component)
			bare_qubit_grid = _dedicated_frequency_grid(
				_analytic_bare_qubit_frequency_hz(evaluator.floating_qubit_nominal),
				settings;
				role = "bare_qubit_differential_Y",
			)
			bare_readout_grid = _dedicated_frequency_grid(
				_analytic_bare_resonator_frequency_hz(evaluator.case, design.lr_total_um),
				settings;
				role = "bare_readout_S21_C_probe_sweep",
			)
			bare_filter_grid = _dedicated_frequency_grid(
				_analytic_bare_resonator_frequency_hz(evaluator.case, design.lp_total_um),
				settings;
				role = "bare_filter_S21_C_probe_sweep",
			)
			bare_readout_reference = _reference_trace!(evaluator, bare_readout_grid.frequencies_hz)
			bare_filter_reference = _reference_trace!(evaluator, bare_filter_grid.frequencies_hz)
			bare_qubit_plan = build_d3_qubit_admittance_plan(
				evaluator.floating_qubit_nominal;
				hb_settings = evaluator.hb_settings,
				loading_state = :bare_component,
			)
			bare_qubit_hb = _run_candidate_hb(
				evaluator,
				bare_qubit_plan,
				bare_qubit_grid.frequencies_hz,
				"standalone bare qubit differential admittance",
			)
			bare_qubit_y = _d3_differential_y_response(
				bare_qubit_hb;
				all_ports = (1, 2),
				island_ports = (1, 2),
				alpha = bare_weights.alpha,
				beta = bare_weights.beta,
				measurement_view = "standalone_two_island_port_bare_qubit_Ydiff",
			)
			bare_qubit_root = _extract_d3_unique_positive_slope_y_root_in_trust_interval(
				bare_qubit_y.frequencies_hz,
				bare_qubit_y.ydiff_siemens,
				bare_qubit_grid.analytic_scan_anchor_hz,
				settings.qubit_root_trust_half_width_hz;
				stage_label = "bare qubit differential admittance",
			)
			(
				scope = "final_validation_context_only_never_cost_or_pair_reference",
				qubit = merge(bare_qubit_root, (
					matrix_provenance = bare_qubit_y.provenance,
					frequency_grid = bare_qubit_grid,
				)),
				readout = merge(_extract_d3_bare_resonator_response(
					evaluator,
					design,
					:readout,
					bare_readout_grid.frequencies_hz,
					bare_readout_reference,
					bare_readout_grid.analytic_scan_anchor_hz,
				), (frequency_grid = bare_readout_grid,)),
				filter = merge(_extract_d3_bare_resonator_response(
					evaluator,
					design,
					:filter,
					bare_filter_grid.frequencies_hz,
					bare_filter_reference,
					bare_filter_grid.analytic_scan_anchor_hz,
				), (frequency_grid = bare_filter_grid,)),
			)
		else
			nothing
		end
		filter_plan = build_maxwell_diagonal_pair_feedline_plan(
			evaluator.case,
			design;
			filter_capacitance_fF = design.filter_to_line_capacitance_fF,
			feedline_length_um = settings.feedline_length_um,
			feedline = evaluator.feedline,
			hb_settings = evaluator.hb_settings,
			floating_qubit_nominal = evaluator.floating_qubit_nominal,
			qubit_coupling_state = :diagonal_preserving_off,
		)
		filter_hb = _run_candidate_hb(
			evaluator,
			filter_plan,
			filter_off_reference_frequencies_hz,
			"Maxwell-diagonal pair filter off-reference",
		)
		filter_normalized = _normalized_s21(
			filter_off_reference_frequencies_hz,
			filter_hb.s21,
			filter_off_reference_reference,
			settings.min_reference_magnitude,
		)
		filter_discovery_mode = _fit_single_loaded_mode(
			filter_off_reference_frequencies_hz,
			filter_normalized,
			slot_hz,
			"Maxwell-diagonal pair filter off-reference",
			settings,
			require_slot_ownership = true,
		)
		filter_source_plan_identity = join((
			"plan_id=$(filter_plan.id)",
			"topology=d3-system-B-filter-off-reference",
			"case_id=$(evaluator.case.id)",
			"feedline_source=$(evaluator.feedline.source)",
			"hb_settings=$(_d3_hb_settings_identity(evaluator.hb_settings))",
			"floating_qubit_sha256=$(evaluator.floating_qubit_input_sha256)",
			"candidate=$(candidate_identity)",
			"design=$(repr(design))",
		), "|")
		filter_source_execution_count = Ref(0)
		filter_source_evaluator = function(level_id, local_frequencies_hz)
			filter_source_execution_count[] += 1
			local_grid_sha256 = _frequency_grid_sha256(local_frequencies_hz)
			local_hb = _run_candidate_hb(
				evaluator,
				filter_plan,
				local_frequencies_hz,
				"Maxwell-diagonal pair filter off-reference scalar-pole $(level_id)",
			)
			local_reference = _reference_trace!(evaluator, local_frequencies_hz)
			return (
				label = "Maxwell-diagonal pair filter off-reference",
				measured_s21 = ComplexF64.(local_hb.s21),
				reference_s21 = local_reference,
				source_execution_id = "$(filter_source_plan_identity)|level=$(level_id)|execution=$(filter_source_execution_count[])",
				source_plan_id = filter_plan.id,
				measured_trace_id = "d3-filter-off-reference-local-hb|level=$(level_id)|grid_sha256=$(local_grid_sha256)|design=$(design.id)|$(candidate_identity)",
				reference_trace_id = _empty_feedline_reference_identity(local_frequencies_hz),
			)
		end
		filter_mode = _extract_scalar_pole_eligibility(
			filter_discovery_mode,
			"Maxwell-diagonal pair filter off-reference",
			"d3-system-B-filter-only-maxwell-diagonal-MTL-with-design-Cext",
			filter_source_plan_identity,
			filter_off_reference_id,
			port_plane,
			settings;
			source_evaluator = filter_source_evaluator,
		)
		channel_calibration_provenance = Dict(
			"calibration_id" => calibration_id,
			"reference_contract_id" => reference_contract_id,
			"filter_off_reference_trace_id" => filter_off_reference_trace_id,
			"empty_feedline_trace_id" => off_reference_empty_feedline_trace_id,
			"filter_off_reference_id" => filter_off_reference_id,
			"off_reference_topology" => "system_B_maxwell_diagonal_MTL_with_physical_terminal_R_to_GND_C0r_plus_Cr1_plus_Cr2_and_qubit_dynamic_nodes_absent",
			"quantity_scope" => "system_B_qubit_dynamic_nodes_absent_g_zero_filter_off_reference_calibration",
			"wide_200khz_trace_scalar_pole_role" => "discovery_only_not_frequency_or_linewidth_promotion_authority",
			"wide_200khz_trace_channel_calibration_role" => "independent_broad_complex_response_estimator_under_existing_channel_fit_gates",
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
			filter_off_reference_frequencies_hz,
			filter_hb.s21,
			filter_off_reference_reference;
			phasor_convention = "exp_plus_iomega_t",
			fit_window_hz = [
				filter_mode.frequency_hz - calibration_fit_half_width_hz,
				filter_mode.frequency_hz + calibration_fit_half_width_hz,
			],
			background_windows_hz = [
				[first(filter_off_reference_frequencies_hz), filter_mode.frequency_hz - calibration_background_inner_hz],
				[filter_mode.frequency_hz + calibration_background_inner_hz, last(filter_off_reference_frequencies_hz)],
			],
			fp_hz = filter_mode.frequency_hz,
			filter_off_reference_linewidth_hz = filter_mode.bandwidth_hz,
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
		coupling_off_modes = Any[]
		readout_captures = Any[]
		readout_shift_g_diagnostics = Any[]
		system_a_failure = nothing
		previous_probe_capacitance_fF = nothing
		previous_coupling_off_frequency_hz = nothing
		previous_coupling_on_frequency_hz = nothing
		for capacitance_fF in settings.c_probe_capacitances_fF
			probe_grid = _d3_readout_probe_grid(
				capacitance_fF,
				previous_probe_capacitance_fF,
				previous_coupling_off_frequency_hz,
				slot_hz,
				settings,
			)
			probe_frequencies_hz = probe_grid.frequencies_hz
			probe_grid_sha256 = probe_grid.frequency_grid_sha256
			probe_reference = _reference_trace!(evaluator, probe_frequencies_hz)
			probe_reference_trace_id = _empty_feedline_reference_identity(probe_frequencies_hz)
			coupling_off_trace_id = "d3-readout-g-probe-diagonal-preserving-off|grid_sha256=$(probe_grid_sha256)|capacitance_fF=$(bitstring(capacitance_fF))|floating_qubit_sha256=$(evaluator.floating_qubit_input_sha256)|design=$(design.id)|$(candidate_identity)"
			coupling_on_trace_id = "d3-readout-g-probe-physical-on|grid_sha256=$(probe_grid_sha256)|capacitance_fF=$(bitstring(capacitance_fF))|floating_qubit_sha256=$(evaluator.floating_qubit_input_sha256)|design=$(design.id)|$(candidate_identity)"
			qubit_probe_trace_id = "d3-qubit-probe-hb|grid_sha256=$(qubit_grid_sha256)|capacitance_fF=$(bitstring(capacitance_fF))|floating_qubit_sha256=$(evaluator.floating_qubit_input_sha256)|design=$(design.id)|$(candidate_identity)"
			coupling_off_plan = build_readout_only_feedline_plan(
				evaluator.case,
				design;
				capacitance_fF = capacitance_fF,
				feedline_length_um = settings.feedline_length_um,
				feedline = evaluator.feedline,
				hb_settings = evaluator.hb_settings,
				floating_qubit_nominal = evaluator.floating_qubit_nominal,
				qubit_coupling_state = :diagonal_preserving_off,
			)
			coupling_off_hb = _run_candidate_hb(
				evaluator,
				coupling_off_plan,
				probe_frequencies_hz,
				"readout-only diagonal-preserving coupling-off probe $(capacitance_fF) fF",
			)
			coupling_off_normalized = _normalized_s21(
				probe_frequencies_hz,
				coupling_off_hb.s21,
				probe_reference,
				settings.min_reference_magnitude,
			)
			coupling_off_discovery_anchor_hz = isnothing(previous_coupling_off_frequency_hz) ?
				slot_hz : Float64(previous_coupling_off_frequency_hz)
			coupling_off_discovery_mode = _fit_single_loaded_mode(
				probe_frequencies_hz,
				coupling_off_normalized,
				coupling_off_discovery_anchor_hz,
				"readout-only diagonal-preserving coupling-off probe $(capacitance_fF) fF",
				settings,
				require_slot_ownership = false,
			)
			function eligible_readout_mode(discovery_mode, plan, coupling_state, stage_label)
				source_plan_identity = join((
					"plan_id=$(plan.id)",
					"topology=d3-system-A-readout-$(coupling_state)",
					"case_id=$(evaluator.case.id)",
					"feedline_source=$(evaluator.feedline.source)",
					"hb_settings=$(_d3_hb_settings_identity(evaluator.hb_settings))",
					"candidate=$(candidate_identity)",
					"probe_capacitance_fF_bits=$(bitstring(capacitance_fF))",
					"floating_qubit_sha256=$(evaluator.floating_qubit_input_sha256)",
					"design=$(repr(design))",
				), "|")
				source_execution_count = Ref(0)
				source_evaluator = function(level_id, local_frequencies_hz)
					source_execution_count[] += 1
					local_grid_sha256 = _frequency_grid_sha256(local_frequencies_hz)
					local_hb = _run_candidate_hb(
						evaluator,
						plan,
						local_frequencies_hz,
						"$(stage_label) scalar-pole $(level_id)",
					)
					local_reference = _reference_trace!(evaluator, local_frequencies_hz)
					return (
						label = stage_label,
						measured_s21 = ComplexF64.(local_hb.s21),
						reference_s21 = local_reference,
						source_execution_id = "$(source_plan_identity)|level=$(level_id)|execution=$(source_execution_count[])",
						source_plan_id = plan.id,
						measured_trace_id = "d3-system-A-readout-local-hb|state=$(coupling_state)|level=$(level_id)|grid_sha256=$(local_grid_sha256)|probe_bits=$(bitstring(capacitance_fF))|design=$(design.id)|$(candidate_identity)",
						reference_trace_id = _empty_feedline_reference_identity(local_frequencies_hz),
					)
				end
				return _extract_scalar_pole_eligibility(
					discovery_mode,
					stage_label,
					"d3-system-A-readout-$(coupling_state)-finite-positive-C_probe-feedline-S21",
					source_plan_identity,
					common_readout_off_reference_id,
					port_plane,
					settings;
					source_evaluator = source_evaluator,
				)
			end
			coupling_off_mode = merge(_d3_accept_readout_probe_mode(eligible_readout_mode(
				coupling_off_discovery_mode,
				coupling_off_plan,
				"diagonal-preserving-off",
				"readout-only diagonal-preserving coupling-off probe $(capacitance_fF) fF",
			), coupling_off_discovery_anchor_hz, probe_grid, settings;
				coupling_state = "diagonal-preserving-off",
				previous_accepted_frequency_hz = previous_coupling_off_frequency_hz,
			), (
				finite_probe_mode_assignment = "previous_accepted_pole_continuation_no_nearest_fallback",
				discovery_fit = coupling_off_discovery_mode,
				frequency_grid_sha256 = probe_grid_sha256,
				measured_trace_id = coupling_off_trace_id,
				reference_trace_id = probe_reference_trace_id,
			))
			push!(coupling_off_modes, coupling_off_mode)
			push!(off_reference_probe_continuation, (
				probe_capacitance_fF = coupling_off_mode.continuation.current_capacitance_fF,
				frequency_hz = coupling_off_mode.frequency_hz,
				linewidth_hz = coupling_off_mode.bandwidth_hz,
				measured_trace_id = coupling_off_mode.measured_trace_id,
				reference_trace_id = coupling_off_mode.reference_trace_id,
				continuation = coupling_off_mode.continuation,
			))
			if isnothing(system_a_failure)
			try
			coupling_on_plan = build_readout_only_feedline_plan(
				evaluator.case,
				design;
				capacitance_fF = capacitance_fF,
				feedline_length_um = settings.feedline_length_um,
				feedline = evaluator.feedline,
				hb_settings = evaluator.hb_settings,
				floating_qubit_nominal = evaluator.floating_qubit_nominal,
				qubit_coupling_state = :physical_on,
			)
			coupling_on_y_plan = build_readout_only_feedline_plan(
				evaluator.case,
				design;
				capacitance_fF = capacitance_fF,
				feedline_length_um = settings.feedline_length_um,
				feedline = evaluator.feedline,
				hb_settings = evaluator.hb_settings,
				floating_qubit_nominal = evaluator.floating_qubit_nominal,
				qubit_coupling_state = :physical_on,
				include_island_observation_ports = true,
			)
			coupling_on_hb = _run_candidate_hb(
				evaluator,
				coupling_on_plan,
				probe_frequencies_hz,
				"readout-only physical-qubit coupling-on probe $(capacitance_fF) fF",
			)
			coupling_on_normalized = _normalized_s21(
				probe_frequencies_hz,
				coupling_on_hb.s21,
				probe_reference,
				settings.min_reference_magnitude,
			)
			coupling_on_discovery_anchor_hz = isnothing(previous_coupling_on_frequency_hz) ?
				slot_hz : Float64(previous_coupling_on_frequency_hz)
			coupling_on_discovery_mode = _fit_single_loaded_mode(
				probe_frequencies_hz,
				coupling_on_normalized,
				coupling_on_discovery_anchor_hz,
				"readout-only physical-qubit coupling-on probe $(capacitance_fF) fF",
				settings,
				require_slot_ownership = false,
			)
			coupling_on_mode = _d3_accept_readout_probe_mode(eligible_readout_mode(
				coupling_on_discovery_mode,
				coupling_on_plan,
				"physical-on",
				"readout-only physical-qubit coupling-on probe $(capacitance_fF) fF",
			), coupling_on_discovery_anchor_hz, probe_grid, settings;
				coupling_state = "physical-on",
				previous_accepted_frequency_hz = previous_coupling_on_frequency_hz,
			)
			qubit_y_hb = _run_candidate_hb(
				evaluator,
				coupling_on_y_plan,
				qubit_frequencies_hz,
				"readout-only physical-qubit differential admittance $(capacitance_fF) fF",
			)
			qubit_y_response = _d3_differential_y_response(
				qubit_y_hb;
				all_ports = (1, 2, 3, 4),
				island_ports = (3, 4),
				alpha = off_reference_qubit_weights.alpha,
				beta = off_reference_qubit_weights.beta,
				measurement_view = "separate_four_port_system_A_island_Ydiff",
			)
			qubit_root = _extract_d3_unique_positive_slope_y_root_in_trust_interval(
				qubit_y_response.frequencies_hz,
				qubit_y_response.ydiff_siemens,
				qubit_off_reference_hz,
				settings.qubit_root_trust_half_width_hz;
				stage_label = "System A physical q-like differential admittance $(capacitance_fF) fF",
			)
			(first(probe_frequencies_hz) <= qubit_root.frequency_hz <= last(probe_frequencies_hz)) && reject_d3_candidate(
				"mode_assignment.qubit_inside_slot_grid",
				"Assigned qubit-like pole lies inside the current per-probe readout grid.";
				details = (
					qubit_pole_hz = qubit_root.frequency_hz,
					probe_grid_start_hz = first(probe_frequencies_hz),
					probe_grid_stop_hz = last(probe_frequencies_hz),
					probe_grid_sha256 = probe_grid_sha256,
				),
			)
			shift_g_diagnostic = _readout_shift_g_diagnostic(
				qubit_off_reference_hz,
				coupling_off_mode.frequency_hz,
				coupling_on_mode.frequency_hz,
			)
			readout_shift_hz = coupling_on_mode.frequency_hz - coupling_off_mode.frequency_hz
			predicted_qubit_pole_hz = qubit_off_reference_hz +
				coupling_off_mode.frequency_hz - coupling_on_mode.frequency_hz
			qubit_crosscheck_residual_hz = qubit_root.frequency_hz - predicted_qubit_pole_hz
			push!(readout_shift_g_diagnostics, shift_g_diagnostic)
			push!(readout_modes, merge(coupling_on_mode, (
				finite_probe_mode_assignment = "previous_accepted_pole_continuation_no_nearest_fallback",
				discovery_fit = coupling_on_discovery_mode,
				frequency_grid_sha256 = probe_grid_sha256,
				measured_trace_id = coupling_on_trace_id,
				reference_trace_id = probe_reference_trace_id,
				diagonal_preserving_coupling_off_mode = coupling_off_mode,
				readout_shift_hz = readout_shift_hz,
				predicted_qubit_pole_hz = predicted_qubit_pole_hz,
				qubit_crosscheck_residual_hz = qubit_crosscheck_residual_hz,
				qubit_crosscheck_role = "finite_probe_diagnostic_not_gate",
				qubit_mode = merge(qubit_root, (
					frequency_grid_sha256 = qubit_grid_sha256,
					measured_trace_id = qubit_probe_trace_id,
					measurement_view = "separate_four_port_system_A_island_Ydiff",
					matrix_provenance = qubit_y_response.provenance,
				)),
				shift_derived_g_diagnostic = shift_g_diagnostic,
			)))
			capture_traces && push!(readout_captures, (
				probe_capacitance_fF = capacitance_fF,
				frequency_grid_sha256 = probe_grid_sha256,
				measured_trace_id = coupling_on_trace_id,
				reference_trace_id = probe_reference_trace_id,
				frequencies_hz = probe_frequencies_hz,
				s21 = ComplexF64.(coupling_on_hb.s21),
				reference_s21 = probe_reference,
				diagonal_preserving_coupling_off_measured_trace_id = coupling_off_trace_id,
				diagonal_preserving_coupling_off_s21 = ComplexF64.(coupling_off_hb.s21),
				coupling_off_continuation = coupling_off_mode.continuation,
				coupling_on_continuation = coupling_on_mode.continuation,
				qubit_frequency_grid_sha256 = qubit_grid_sha256,
				qubit_measured_trace_id = qubit_probe_trace_id,
				qubit_reference_trace_id = qubit_empty_feedline_trace_id,
				qubit_frequencies_hz = qubit_frequencies_hz,
				qubit_ydiff_siemens = ComplexF64.(qubit_y_response.ydiff_siemens),
				qubit_matrix_provenance = qubit_y_response.provenance,
			))
			previous_coupling_on_frequency_hz = coupling_on_mode.frequency_hz
			catch exception
				exception isa D3CandidateRejected || rethrow()
				system_a_failure = exception
			end
			end
			previous_probe_capacitance_fF = capacitance_fF
			previous_coupling_off_frequency_hz = coupling_off_mode.frequency_hz
		end
		readout_coupling_off_frequency_fit = _quadratic_zero_intercept(
			settings.c_probe_capacitances_fF,
			[mode.frequency_hz for mode in coupling_off_modes],
			settings.min_readout_frequency_extrapolation_r2,
			"readout diagonal-preserving coupling-off weak-probe frequency",
			"readout_extrapolation.coupling_off_frequency",
		)
		readout_linewidth_fit = _zero_constrained_linewidth_fit(
			settings.c_probe_capacitances_fF,
			[mode.bandwidth_hz for mode in coupling_off_modes],
			settings.min_readout_linewidth_extrapolation_r2,
			"common readout off-reference weak-probe linewidth",
			"readout_extrapolation.linewidth",
		)
		readout_frequency_hz = readout_coupling_off_frequency_fit.intercept
		_require_zero_probe_readout_slot_ownership(
			readout_frequency_hz,
			slot_hz,
			settings.off_reference_ownership_half_width_hz,
		)
		readout_off_reference_linewidth_hz = readout_linewidth_fit.intercept
		readout_off_reference_linewidth_hz == 0.0 || error(
			"Lossless Maxwell-diagonal readout zero-probe linewidth must be exactly zero.",
		)
		comparison_estimates["off_reference"] = Dict(
			"c_q_eff_off_reference_f" => floating_qubit_capacitance_layers(evaluator.floating_qubit_nominal).Cq_LB_fF * D3_FARADS_PER_FF,
			"f_r_off_reference_hz" => readout_frequency_hz,
			"f_p_off_reference_hz" => filter_mode.frequency_hz,
			"kappa_p_ext_off_reference_hz" => filter_mode.bandwidth_hz,
		)
		initializer_stages["off_reference"] = Dict(
			"status" => "available",
			"estimates" => comparison_estimates["off_reference"],
			"readout_probe_continuation" => off_reference_probe_continuation,
		)
		try
			isnothing(system_a_failure) || throw(system_a_failure)
			length(readout_modes) == length(settings.c_probe_capacitances_fF) || error(
				"System-A initializer completed without the exact C_probe response count.",
			)
			readout_frequency_fit = _quadratic_zero_intercept(
				settings.c_probe_capacitances_fF,
				[mode.frequency_hz for mode in readout_modes],
				settings.min_readout_frequency_extrapolation_r2,
				"readout weak-probe frequency",
				"readout_extrapolation.frequency",
			)
			qubit_frequency_fit = _quadratic_zero_intercept(
				settings.c_probe_capacitances_fF,
				[mode.qubit_mode.frequency_hz for mode in readout_modes],
				settings.min_readout_frequency_extrapolation_r2,
				"coupling-on qubit-like weak-probe frequency",
				"qubit_extrapolation.frequency",
			)
			diagnostic_g_values_hz = [item.system_a_g_initializer_hz for item in readout_shift_g_diagnostics]
			g_fit = if all(value -> !isnothing(value), diagnostic_g_values_hz)
				try
					merge(
						_quadratic_zero_intercept(
							settings.c_probe_capacitances_fF,
							Float64.(diagnostic_g_values_hz),
							settings.min_g_extrapolation_r2,
							"readout-shift-derived g weak-probe diagnostic",
							"g_extrapolation",
						),
						(role = "finite_open_s21_diagnostic_not_gate", status = "fit_available"),
					)
				catch exception
					exception isa D3CandidateRejected || rethrow()
					(status = "fit_rejected_diagnostic_only", role = "finite_open_s21_diagnostic_not_gate", code = exception.code, reason = exception.reason, details = exception.details)
				end
			else
				(status = "nonreal_shift_diagnostic", role = "finite_open_s21_diagnostic_not_gate", probe_diagnostics = readout_shift_g_diagnostics)
			end
			g_shift_fit_diagnostic = g_fit
			g_fit = hasproperty(g_fit, :intercept) ? g_fit : nothing
			coupling_on_readout_frequency_hz = readout_frequency_fit.intercept
			g_hz = _linearized_g_from_readout_shift_hz(
				qubit_off_reference_hz,
				readout_frequency_hz,
				coupling_on_readout_frequency_hz,
			)
			comparison_estimates["system_a"] = Dict("g_system_a_on_hz" => g_hz)
			initializer_stages["system_a"] = Dict("status" => "available", "estimates" => comparison_estimates["system_a"])
		catch exception
			exception isa D3CandidateRejected || rethrow()
			initializer_failures["system_a"] = (code = exception.code, reason = exception.reason, details = exception.details)
			initializer_stages["system_a"] = Dict("status" => "missing_expected_physical_rejection", "code" => exception.code, "reason" => exception.reason, "details" => exception.details)
		end
		try
		pair_reference = _reference_trace!(evaluator, pair_frequencies_hz)
		system_b_pair_plan = build_single_pair_feedline_plan(
			evaluator.case,
			design;
			capacitance_fF = design.filter_to_line_capacitance_fF,
			feedline_length_um = settings.feedline_length_um,
			feedline = evaluator.feedline,
			hb_settings = evaluator.hb_settings,
			floating_qubit_nominal = evaluator.floating_qubit_nominal,
			qubit_coupling_state = :diagonal_preserving_off,
		)
		system_b_pair_hb = _run_candidate_hb(
			evaluator,
			system_b_pair_plan,
			pair_frequencies_hz,
			"System B readout-filter pair",
		)
		system_b_pair_normalized = _normalized_s21(
			pair_frequencies_hz,
			system_b_pair_hb.s21,
			pair_reference,
			settings.min_reference_magnitude,
		)
		fit_window = [slot_hz - settings.pair_fit_half_width_hz, slot_hz + settings.pair_fit_half_width_hz]
		background_windows = [
			[slot_hz - settings.pair_trace_half_width_hz, slot_hz - settings.pair_background_inner_half_width_hz],
			[slot_hz + settings.pair_background_inner_half_width_hz, slot_hz + settings.pair_trace_half_width_hz],
		]
		filter_off_reference_linewidth_hz = filter_mode.bandwidth_hz
		j_fit = fit_d3_through_line_s21(
			pair_frequencies_hz,
			system_b_pair_hb.s21,
			pair_reference;
			phasor_convention = "exp_plus_iomega_t",
			fit_window_hz = fit_window,
			background_windows_hz = background_windows,
			fp_hz = filter_mode.frequency_hz,
			fr_hz = readout_frequency_hz,
			filter_off_reference_linewidth_hz = filter_off_reference_linewidth_hz,
			readout_off_reference_linewidth_hz = readout_off_reference_linewidth_hz,
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
				"filter_off_reference_id" => filter_off_reference_id,
				"common_readout_off_reference_id" => common_readout_off_reference_id,
				"off_reference_topology" => "common_readout_physical_terminal_R_to_GND_C0r_plus_Cr1_plus_Cr2_plus_filter_finite_Cext_and_MTL_self_terms",
				"quantity_scope" => "system_B_qubit_dynamic_nodes_absent_g_zero_response_fitted_J",
				"floating_qubit_input_sha256" => evaluator.floating_qubit_input_sha256,
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
				off_reference_filter_hz = filter_mode.frequency_hz,
				off_reference_filter_linewidth_hz = filter_mode.bandwidth_hz,
				off_reference_readout_hz = readout_frequency_hz,
				off_reference_readout_linewidth_hz = readout_off_reference_linewidth_hz,
				off_reference_readout_filter_center_hz = (filter_mode.frequency_hz + readout_frequency_hz) / 2,
				system_b_j_initializer_fit = _compact_j_fit(j_fit),
			),
		)

		pair_fit_mask = abs.(pair_frequencies_hz .- slot_hz) .<= settings.pair_fit_half_width_hz
		pair_vector_result = fit_vector_s21(
			pair_frequencies_hz[pair_fit_mask],
			system_b_pair_normalized[pair_fit_mask];
			n_resonators = 2,
			bg_poles = settings.vector_bg_poles,
			max_iterations = settings.vector_max_iterations,
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
		off_reference_center_hz = (filter_mode.frequency_hz + readout_frequency_hz) / 2
		model_paired_pole_center_hz = sum(model_poles_hz) / 2
		isapprox(model_paired_pole_center_hz, off_reference_center_hz; atol = 1.0e-6, rtol = 0.0) ||
			error("J-only two-mode poles must preserve the off-reference center.")
		vector_paired_pole_center_hz = sum(vector_poles_hz) / 2
		pair_pole_center_offset_hz = vector_paired_pole_center_hz - off_reference_center_hz
		abs(pair_pole_center_offset_hz) <= settings.max_pair_pole_center_offset_hz ||
			reject_d3_candidate(
			"vector.pair_center_offset_gate",
			"Paired vector-pole center differs from the Maxwell-diagonal off-reference center by $(pair_pole_center_offset_hz) Hz.";
			details = (
				off_reference_readout_filter_center_hz = off_reference_center_hz,
				vector_paired_pole_center_hz = vector_paired_pole_center_hz,
				pair_pole_center_offset_hz = pair_pole_center_offset_hz,
			),
			)

		j_hz = Float64(j_fit["params"]["j_hz"])
		comparison_estimates["system_b"] = Dict(
			"f_r_lb_system_b_on_hz" => readout_frequency_hz,
			"f_p_lb_system_b_on_hz" => filter_mode.frequency_hz,
			"j_system_b_on_hz" => j_hz,
			"kappa_p_ext_lb_system_b_on_hz" => filter_mode.bandwidth_hz,
		)
		initializer_stages["system_b"] = Dict(
			"status" => "available",
			"estimates" => comparison_estimates["system_b"],
			"fit_parameter" => "j_system_b_on_hz",
			"fixed_off_reference_derived_inputs" => [
				"f_r_lb_system_b_on_hz",
				"f_p_lb_system_b_on_hz",
				"kappa_p_ext_lb_system_b_on_hz",
			],
		)
		catch exception
			exception isa D3CandidateRejected || rethrow()
			initializer_failures["system_b"] = (code = exception.code, reason = exception.reason, details = exception.details)
			initializer_stages["system_b"] = Dict(
				"status" => "missing_expected_physical_rejection",
				"code" => exception.code,
				"reason" => exception.reason,
				"details" => exception.details,
			)
		end
		catch exception
			exception isa D3CandidateRejected || rethrow()
			initializer_failures["off_reference"] = (code = exception.code, reason = exception.reason, details = exception.details)
			initializer_stages["off_reference"] = Dict(
				"status" => "missing_expected_physical_rejection",
				"code" => exception.code,
				"reason" => exception.reason,
				"details" => exception.details,
			)
			!isempty(off_reference_probe_continuation) &&
				(initializer_stages["off_reference"]["readout_probe_continuation"] = off_reference_probe_continuation)
			for group in ("off_reference", "system_a", "system_b")
				get(initializer_stages[group], "status", nothing) == "pending" &&
					(initializer_stages[group] = Dict(
						"status" => "not_attempted_due_initializer_dependency",
						"blocked_by" => "off_reference",
					))
			end
		end
		initializer_attempt = (
			status = isempty(initializer_failures) ? "complete" : "incomplete",
			stages = initializer_stages,
			failures = initializer_failures,
			caught_exception_type = isempty(initializer_failures) ? nothing : "D3CandidateRejected",
			non_physical_errors_caught = false,
		)

		nominal_lj_h = evaluator.system_c_target_values["qubit_junction_inductance_per_junction_h"]
		system_c_sweep = _d3_system_c_lj_sweep(
			evaluator.floating_qubit_nominal,
			slot_hz,
			nominal_lj_h,
			settings,
		)
		system_c_fit_inputs = _d3_system_c_fit_contract(
			settings,
			system_c_sweep,
			evaluator.system_c_target_values;
			source_estimates = comparison_estimates,
		)
		system_c_topology_id = "d3-system-c-full-physical-qubit-readout-filter-feedline-v1"
		system_c_fit_traces = Dict{String,Any}[]
		system_c_trace_evidence = NamedTuple[]
		for (trace_index, (lj_per_junction_h, q_diagonal_hz)) in enumerate(zip(
			system_c_sweep.lj_per_junction_h,
			system_c_sweep.q_diagonal_hz,
		))
			predicted_poles_hz = _system_c_initializer_poles_hz(
				q_diagonal_hz,
				system_c_fit_inputs.target_centered_seed["f_r_lb_system_c_on_hz"],
				system_c_fit_inputs.target_centered_seed["f_p_lb_system_c_on_hz"],
				system_c_fit_inputs.target_centered_seed["g_system_c_on_hz"] *
					(nominal_lj_h / lj_per_junction_h)^0.25,
				system_c_fit_inputs.target_centered_seed["j_system_c_on_hz"],
			)
			grid = _d3_system_c_frequency_grid(predicted_poles_hz, settings)
			grid_sha256 = _frequency_grid_sha256(grid.frequencies_hz)
			lj_qubit = _d3_qubit_with_lj(evaluator.floating_qubit_nominal, lj_per_junction_h)
			plan = build_single_pair_feedline_plan(
				evaluator.case,
				design;
				capacitance_fF = design.filter_to_line_capacitance_fF,
				feedline_length_um = settings.feedline_length_um,
				feedline = evaluator.feedline,
				hb_settings = evaluator.hb_settings,
				floating_qubit_nominal = lj_qubit,
				qubit_coupling_state = :physical_on,
			)
			trace_id = "d3-system-c-lj-sweep|index=$(trace_index)|lj_h=$(bitstring(lj_per_junction_h))|grid_sha256=$(grid_sha256)|design=$(design.id)|$(candidate_identity)"
			reference_trace_id = _empty_feedline_reference_identity(grid.frequencies_hz)
			hb = _run_candidate_hb(
				evaluator,
				plan,
				grid.frequencies_hz,
				"System C full physical L_J sweep trace $(trace_index)",
			)
			reference_s21 = _reference_trace!(evaluator, grid.frequencies_hz)
			push!(system_c_fit_traces, Dict(
				"trace_id" => trace_id,
				"empty_feedline_trace_id" => reference_trace_id,
				"candidate_id" => candidate_identity,
				"reference_contract_id" => reference_contract_id,
				"topology_id" => system_c_topology_id,
				"port_plane" => port_plane,
				"lj_per_junction_h" => lj_per_junction_h,
				"frequency_hz" => grid.frequencies_hz,
				"s21" => ComplexF64.(hb.s21),
				"empty_feedline_s21" => reference_s21,
				"s21_sigma" => Float64(settings.system_c_s21_lj_sweep["s21_sigma"]),
			))
			push!(system_c_trace_evidence, (
				trace_id = trace_id,
				empty_feedline_trace_id = reference_trace_id,
				candidate_id = candidate_identity,
				reference_contract_id = reference_contract_id,
				topology_id = system_c_topology_id,
				port_plane = port_plane,
				lj_per_junction_h = lj_per_junction_h,
				q_diagonal_initializer_hz = q_diagonal_hz,
				predicted_poles_hz = grid.predicted_poles_hz,
				local_windows_hz = grid.local_windows_hz,
				frequency_grid_sha256 = grid_sha256,
				frequency_hz = grid.frequencies_hz,
				s21 = ComplexF64.(hb.s21),
				empty_feedline_s21 = reference_s21,
			))
		end
		length(system_c_fit_traces) >= 9 || error("System-C fit requires all nine reviewed L_J traces.")
		system_c_fit = fit_d3_system_c_s21_lj_sweep(
			system_c_fit_traces;
			phasor_convention = "exp_plus_iomega_t",
			nominal_lj_per_junction_h = nominal_lj_h,
			physical_bounds = system_c_fit_inputs.physical_bounds,
			physical_seeds = system_c_fit_inputs.physical_seeds,
			multi_start_coverage_seed_count = system_c_fit_inputs.multi_start_coverage_seed_count,
			nuisance_bounds = settings.system_c_s21_lj_sweep["nuisance_bounds"],
			numerical_tolerances = settings.system_c_s21_lj_sweep["numerical_tolerances"],
			gates = settings.system_c_s21_lj_sweep["gates"],
			stability_lj_subranges = settings.system_c_s21_lj_sweep["stability_lj_subranges_1based_inclusive"],
			stability_frequency_trim_fraction = settings.system_c_s21_lj_sweep["stability_frequency_trim_fraction"],
			stability_frequency_grid_stride = settings.system_c_s21_lj_sweep["stability_frequency_grid_stride"],
			stability_bound_inset_fraction = settings.system_c_s21_lj_sweep["stability_bound_inset_fraction"],
			labeled_estimates = system_c_fit_inputs.mapped_system_c_seed_estimates,
			provenance = Dict(
				"fit_id" => "d3-system-c-global-s21-lj-sweep|design=$(design.id)|$(candidate_identity)",
				"candidate_id" => candidate_identity,
				"reference_contract_id" => reference_contract_id,
				"topology_id" => system_c_topology_id,
				"port_plane" => port_plane,
			),
		)
		publication_status = _d3_system_c_publication_status(
			system_c_fit,
			initializer_attempt,
			system_c_fit_inputs.initializer_seed_evidence,
		)
		chain_reduction_check = publication_status.chain_reduction_check
		system_c_fit_params = system_c_fit["params"]
		system_c_vf_evidence = Any[]
		previous_vf_assignment_state = nothing
		for (trace, fitted) in zip(system_c_trace_evidence, system_c_fit["per_lj"])
			evidence = _d3_system_c_vf_crosscheck(
				trace,
				fitted,
				settings;
				previous_assignment_state = previous_vf_assignment_state,
			)
			push!(system_c_vf_evidence, evidence)
			previous_vf_assignment_state = evidence.association_state
		end
		promotion_status = _d3_system_c_promotion_status(
			system_c_fit_inputs.source_estimates,
			get(system_c_fit, "labeled_estimate_deltas", Dict{String,Any}()),
			system_c_fit_inputs.initializer_seed_evidence,
		)

		notch_frequencies_hz = _slot_frequency_grid(
			notch_target_hz,
			settings.notch_half_width_hz,
			settings.frequency_step_hz,
		)
		notch_grid_sha256 = _frequency_grid_sha256(notch_frequencies_hz)
		reference_notch_trace_id = "d3-intrinsic-no-qubit-reference-notch|grid_sha256=$(notch_grid_sha256)|design=$(design.id)|$(candidate_identity)"
		loaded_notch_trace_id = "d3-intrinsic-qubit-loaded-notch|grid_sha256=$(notch_grid_sha256)|floating_qubit_sha256=$(evaluator.floating_qubit_input_sha256)|design=$(design.id)|$(candidate_identity)"
		continuation_id = "d3-z21-ptc-complex-zero|design=$(design.id)|floating_qubit_sha256=$(evaluator.floating_qubit_input_sha256)|$(candidate_identity)"
		intrinsic_plans = Dict{Float64,Any}()
		intrinsic_scans = Dict{Float64,Any}()
		for fraction in settings.z21_ptc_coupling_fractions
			plan = _build_intrinsic_z21_ptc_plan(
				evaluator.case,
				design,
				floating_qubit_nominal = evaluator.floating_qubit_nominal,
				hb_settings = evaluator.hb_settings,
				coupling_fraction = fraction,
			)
			intrinsic_plans[fraction] = plan
			intrinsic_scans[fraction] = _run_candidate_hb(
				evaluator,
				plan,
				notch_frequencies_hz,
				"intrinsic Z21 PTC coupling fraction $(fraction)";
				compensate_port_indices = (1, 2),
				removal_intent = :intrinsic_pair_probe_scaffold,
			)
		end
		reference_intrinsic_plan = intrinsic_plans[0.0]
		reference_intrinsic_hb = intrinsic_scans[0.0]
		intrinsic_plan = intrinsic_plans[1.0]
		intrinsic_hb = intrinsic_scans[1.0]
		z21_ptc_complex_zero = _z21_ptc_complex_zero_continuation(
			settings.z21_ptc_coupling_fractions,
			fraction -> (
				frequencies_hz = notch_frequencies_hz,
				z21_ptc = intrinsic_scans[fraction].z21_ptc,
				provenance = (
					trace_id = fraction == 0 ? reference_notch_trace_id :
						(fraction == 1 ? loaded_notch_trace_id : "$(continuation_id)|lambda=$(fraction)|scan"),
					frequency_grid_sha256 = notch_grid_sha256,
					coupling_fraction = fraction,
					endpoint_composition = intrinsic_plans[fraction].metadata[:d3_z21_ptc_endpoint_composition],
					evidence = "actual_HB_PTC_scan_for_bracket_discovery_only",
				),
			),
			(fraction, frequency_hz) -> begin
				hb = _run_candidate_hb(
					evaluator,
					intrinsic_plans[fraction],
					[frequency_hz],
					"intrinsic Z21 PTC actual refinement lambda=$(fraction) frequency=$(frequency_hz)";
					compensate_port_indices = (1, 2),
					removal_intent = :intrinsic_pair_probe_scaffold,
				)
				only(hb.z21_ptc)
			end;
			target_hz = notch_target_hz,
			half_width_hz = settings.notch_half_width_hz,
			frequency_tolerance_hz = settings.z21_ptc_zero_frequency_tolerance_hz,
			max_iterations = settings.z21_ptc_zero_max_iterations,
			max_abs_re_ohm = settings.max_z21_ptc_zero_abs_re_ohm,
			max_abs_im_ohm = settings.max_z21_ptc_zero_abs_im_ohm,
			max_abs_complex_ohm = settings.max_z21_ptc_zero_abs_complex_ohm,
			max_continuation_step_hz = settings.z21_ptc_max_continuation_step_hz,
			require_same_orientation = settings.z21_ptc_require_same_orientation,
			continuation_id = continuation_id,
		)
		reference_notch = merge(z21_ptc_complex_zero.reference, (
			ownership = "unique_eligible_bracketed_signed_crossing_reference_root",
			trace_id = reference_notch_trace_id,
			frequency_grid_sha256 = notch_grid_sha256,
		))
		notch = merge(z21_ptc_complex_zero.loaded, (
			ownership = "same_orientation_bracketed_signed_crossing_declared_trust_interval_continuation",
			trace_id = loaded_notch_trace_id,
			frequency_grid_sha256 = notch_grid_sha256,
			reference_trace_id = reference_notch_trace_id,
		))
		intrinsic_wide_trace = if capture_traces
			wide_capture = _intrinsic_wide_capture_grid(
				design,
				notch_target_hz,
				Float64(system_c_fit_params["f_p_lb_system_c_on_hz"]),
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

		nominal_lj_index = findfirst(
			entry -> Float64(entry["lj_per_junction_h"]) == nominal_lj_h,
			system_c_fit["per_lj"],
		)
		isnothing(nominal_lj_index) && error("System-C fit evidence is missing the nominal 21.5 nH trace.")
		nominal_system_c = system_c_fit["per_lj"][nominal_lj_index]
		metrics = (
			system_c_filter_loaded_bare_hz = Float64(system_c_fit_params["f_p_lb_system_c_on_hz"]),
			system_c_readout_loaded_bare_hz = Float64(system_c_fit_params["f_r_lb_system_c_on_hz"]),
			system_c_intrinsic_notch_hz = notch.frequency_hz,
			system_c_filter_loaded_bare_external_linewidth_hz = Float64(system_c_fit_params["kappa_p_ext_lb_system_c_on_hz"]),
			system_c_j_hz = Float64(system_c_fit_params["j_system_c_on_hz"]),
			system_c_g_hz = Float64(system_c_fit_params["g_system_c_on_hz"]),
			system_c_readout_minus_filter_loaded_bare_detuning_hz = Float64(system_c_fit_params["f_r_lb_system_c_on_hz"] - system_c_fit_params["f_p_lb_system_c_on_hz"]),
		)
		final_validation_frequency_rows = capture_traces && isempty(initializer_failures) ? [
			(layer = "bare", quantity_id = "fqB_hz", system_tag = "Bare Qubit Component", frequency_hz = bare_frequency_evidence.qubit.frequency_hz, source_method = "compensated_two_island_port_Ydiff_positive_slope_root", ownership_label = "qubit_component_response", cost_function_role = "context_only"),
			(layer = "bare", quantity_id = "frB_hz", system_tag = "Bare Readout Component", frequency_hz = bare_frequency_evidence.readout.frequency_hz, source_method = "finite_positive_C_probe_two_level_local_HB_scalar_VF_v2_eligible_zero_C_probe_intercept", ownership_label = "readout_component_response", cost_function_role = "context_only"),
			(layer = "bare", quantity_id = "fpB_hz", system_tag = "Bare Filter Component", frequency_hz = bare_frequency_evidence.filter.frequency_hz, source_method = "finite_positive_C_probe_two_level_local_HB_scalar_VF_v2_eligible_zero_C_probe_intercept", ownership_label = "filter_component_response", cost_function_role = "context_only"),
			(layer = "off_reference", quantity_id = "off_reference_qubit_hz", system_tag = "Off-Reference", frequency_hz = qubit_off_reference_hz, source_method = "compensated_two_island_port_Ydiff_positive_slope_root", ownership_label = "off_reference_comparison_evidence", cost_function_role = "initializer_only"),
			(layer = "off_reference", quantity_id = "off_reference_readout_hz", system_tag = "Off-Reference", frequency_hz = readout_frequency_hz, source_method = "finite_positive_C_probe_two_level_local_HB_scalar_VF_v2_eligible_zero_C_probe_intercept", ownership_label = "off_reference_comparison_evidence", cost_function_role = "initializer_only"),
			(layer = "off_reference", quantity_id = "off_reference_filter_hz", system_tag = "Off-Reference", frequency_hz = filter_mode.frequency_hz, source_method = "two_level_local_HB_scalar_VF_v2_eligible_filter_frequency_and_linewidth", ownership_label = "off_reference_comparison_evidence", cost_function_role = "initializer_only"),
			(layer = "hybridized", quantity_id = "system_a_q_like_hz", system_tag = "System A Physical On", frequency_hz = qubit_frequency_fit.intercept, source_method = "separate_four_port_compensated_Ydiff_zero_C_probe_intercept", ownership_label = "q_like_response", cost_function_role = "physical_validation_diagnostic"),
			(layer = "hybridized", quantity_id = "system_a_r_like_hz", system_tag = "System A Physical On", frequency_hz = coupling_on_readout_frequency_hz, source_method = "authoritative_two_port_S21_two_level_local_HB_scalar_VF_v2_eligible_zero_C_probe_intercept", ownership_label = "r_like_response", cost_function_role = "physical_validation_diagnostic"),
			(layer = "hybridized", quantity_id = "system_b_lower_pole_hz", system_tag = "System B Physical Pair", frequency_hz = vector_poles_hz[1], source_method = "observed_pair_window_independent_vector_fit", ownership_label = "lower_pole_order_only_readout_filter_ownership_unassigned", cost_function_role = "physical_validation_diagnostic"),
			(layer = "hybridized", quantity_id = "system_b_upper_pole_hz", system_tag = "System B Physical Pair", frequency_hz = vector_poles_hz[2], source_method = "observed_pair_window_independent_vector_fit", ownership_label = "upper_pole_order_only_readout_filter_ownership_unassigned", cost_function_role = "physical_validation_diagnostic"),
			(layer = "loaded_bare", quantity_id = "system_c_qubit_diagonal_hz", system_tag = "System C Global Fit Nominal L_J", frequency_hz = nominal_system_c["f_q_lb_system_c_on_hz"], source_method = "global_complex_S21_LJ_sweep_fit", ownership_label = "system_c_final_authority", cost_function_role = "fit_evidence"),
			(layer = "loaded_bare", quantity_id = "system_c_readout_diagonal_hz", system_tag = "System C Global Fit", frequency_hz = system_c_fit_params["f_r_lb_system_c_on_hz"], source_method = "global_complex_S21_LJ_sweep_fit", ownership_label = "system_c_final_authority", cost_function_role = "objective"),
			(layer = "loaded_bare", quantity_id = "system_c_filter_diagonal_hz", system_tag = "System C Global Fit", frequency_hz = system_c_fit_params["f_p_lb_system_c_on_hz"], source_method = "global_complex_S21_LJ_sweep_fit", ownership_label = "system_c_final_authority", cost_function_role = "objective"),
			[(layer = "hybridized", quantity_id = "system_c_hybridized_mode_$(pole["mu"])_hz", system_tag = "System C Global Fit Nominal L_J", frequency_hz = pole["frequency_hz"], source_method = "global_complex_S21_LJ_sweep_fit", ownership_label = "system_c_final_authority", cost_function_role = "fit_evidence") for pole in nominal_system_c["hybridized_poles"]]...,
		] : nothing
		diagnostics = (
			status = "success",
			design = design,
			extraction_contract = "d3-system-c-response-authority.v1",
			frequency_layers = (
				bare_qubit_hz = bare_frequency_evidence === nothing ? nothing : bare_frequency_evidence.qubit.frequency_hz,
				bare_readout_hz = bare_frequency_evidence === nothing ? nothing : bare_frequency_evidence.readout.frequency_hz,
				bare_filter_hz = bare_frequency_evidence === nothing ? nothing : bare_frequency_evidence.filter.frequency_hz,
				off_reference_qubit_hz = qubit_off_reference_hz,
				off_reference_readout_hz = readout_frequency_hz,
				off_reference_filter_hz = isnothing(filter_mode) ? nothing : filter_mode.frequency_hz,
				system_a_q_like_hz = isnothing(qubit_frequency_fit) ? nothing : qubit_frequency_fit.intercept,
				system_a_r_like_hz = coupling_on_readout_frequency_hz,
				system_c_qubit_diagonal_hz = nominal_system_c["f_q_lb_system_c_on_hz"],
				system_c_readout_diagonal_hz = system_c_fit_params["f_r_lb_system_c_on_hz"],
				system_c_filter_diagonal_hz = system_c_fit_params["f_p_lb_system_c_on_hz"],
				system_c_nominal_hybridized_poles_hz = [pole["frequency_hz"] for pole in nominal_system_c["hybridized_poles"]],
			),
			final_validation_frequency_rows = final_validation_frequency_rows,
			bare_frequency_response = bare_frequency_evidence,
			off_reference_common_readout = (
				off_reference_id = common_readout_off_reference_id,
				frequency_hz = readout_frequency_hz,
				linewidth_hz = readout_off_reference_linewidth_hz,
				active_couplings = String[],
				off_couplings = ["g", "J"],
				retained_loading = ["readout_MTL_diagonal_self_terms", "physical_terminal_R_to_GND_C0r_plus_Cr1_plus_Cr2"],
				probe_role = "observation_only_C_probe_extrapolated_to_zero_no_physical_filter_Cext_design",
				readout_endpoint_shunts = [
					(
						id = "C0r_plus_Cr1_plus_Cr2_physical_terminal_diagonal",
						capacitance_fF = evaluator.floating_qubit_nominal.C0r_fF + evaluator.floating_qubit_nominal.Cr1_fF + evaluator.floating_qubit_nominal.Cr2_fF,
						provenance = "physical_node_basis_coupling_off_diagonal",
					),
				],
			),
			systems = (
				off_reference = (
					id = "coupling-off-reference",
					active_couplings = String[],
					off_couplings = ["g", "J"],
					metric_ownership = ["initializer_c_q_eff", "initializer_f_r", "initializer_f_p", "initializer_kappa_p_ext"],
				),
				A = (
					id = "qubit-readout-response-system",
					dynamic_nodes = ["qubit_left", "qubit_right", "distributed_readout"],
					ports = ["feedline_port_1", "feedline_port_2", "separate_island_probe_3", "separate_island_probe_4"],
					active_couplings = ["physical_Cr1", "physical_Cr2"],
					off_couplings = ["J"],
					common_readout_off_reference_id = common_readout_off_reference_id,
					coupling_off_fixture = "factorized_readout_S21_R_to_GND_C0r_plus_Cr1_plus_Cr2_qubit_dynamic_nodes_absent_plus_separate_fqLB_Ydiff_QL_to_GND_Cr1_QR_to_GND_Cr2",
					coupling_off_factorization = (
						composition = "factorized_g_zero_shared_reference_identity",
						readout_s21_fixture = "R_to_GND_C0r_plus_Cr1_plus_Cr2_qubit_dynamic_nodes_absent",
						qubit_ydiff_fixture = "QL_to_GND_Cr1_QR_to_GND_Cr2_separate_two_island_port_view",
					),
					metric_ownership = ["initializer_g", "physical_response_frequencies"],
				),
				B = (
					id = "readout-filter-feedline",
					dynamic_nodes = ["readout", "filter", "feedline"],
					ports = ["feedline_port_1", "feedline_port_2"],
					active_couplings = ["J", "filter_Cext_design"],
					off_couplings = ["g"],
					common_readout_off_reference_id = common_readout_off_reference_id,
					coupling_off_fixture = "R_to_GND_C0r_plus_Cr1_plus_Cr2_qubit_dynamic_nodes_absent",
					metric_ownership = ["initializer_j"],
				),
				C = (
					id = "qubit-readout-filter-feedline",
					dynamic_nodes = ["qubit_left", "qubit_right", "readout", "filter", "feedline"],
					ports = ["feedline_port_1", "feedline_port_2"],
					active_couplings = ["physical_Cr1", "physical_Cr2", "J", "filter_Cext_design"],
					off_couplings = ["direct_qubit_filter_coupling"],
					common_readout_off_reference_id = common_readout_off_reference_id,
					physical_on_fixture = "R_to_QL_Cr1_and_R_to_QR_Cr2_cross_branches_no_coupling_off_diagonal_shunts",
					final_parameter_source = "global complex-S21 L_J-sweep fit",
					metric_ownership = ["system_c_diagonals", "system_c_g", "system_c_j", "system_c_filter_external_linewidth", "system_c_intrinsic_notch"],
				),
			),
			off_reference_filter = isnothing(filter_mode) ? nothing : merge(filter_mode, (
				external_coupling_design_capacitance_fF = design.filter_to_line_capacitance_fF,
				external_coupling_role = "finite_Cext_design_retained_with_feedline_and_MTL_diagonal_loading",
			)),
			off_reference_readout_probe_modes = coupling_off_modes,
			probe_sweep_modes = readout_modes,
			system_a_g_initializer_evidence = (
				fixture_topology = "separate_authoritative_two_port_S21_and_four_port_island_Ydiff_measurement_views",
				coupling_off_reference = "factorized_readout_S21_R_to_GND_C0r_plus_Cr1_plus_Cr2_qubit_dynamic_nodes_absent_plus_separate_fqLB_Ydiff_QL_to_GND_Cr1_QR_to_GND_Cr2",
				coupling_off_composition = "factorized_g_zero_shared_reference_identity",
				off_reference_qubit_frequency_role = "compensated_differential_Y_positive_slope_root",
				formula = "g_initializer=sqrt((f_readout_like_coupling_on_zero_probe-f_readout_off_reference_zero_probe)*(f_readout_like_coupling_on_zero_probe-f_qubit_off_reference))",
				g_role = "initializer_only_not_final_authority",
				c_probe_capacitances_fF = copy(settings.c_probe_capacitances_fF),
				probe_role = "observation_only_C_probe_extrapolated_to_zero_not_physical_filter_design_loading",
				coupling_off_physical_terminal_shunts = [
					(id = "QL_to_GND_Cr1", capacitance_fF = evaluator.floating_qubit_nominal.Cr1_fF, response_view = "separate_off_reference_qubit_Ydiff"),
					(id = "QR_to_GND_Cr2", capacitance_fF = evaluator.floating_qubit_nominal.Cr2_fF, response_view = "separate_off_reference_qubit_Ydiff"),
					(id = "R_to_GND_C0r_plus_Cr1_plus_Cr2", capacitance_fF = evaluator.floating_qubit_nominal.C0r_fF + evaluator.floating_qubit_nominal.Cr1_fF + evaluator.floating_qubit_nominal.Cr2_fF, response_view = "authoritative_two_port_readout_S21"),
				],
				system_a_readout_like_zero_probe_frequency_hz = coupling_on_readout_frequency_hz,
				system_a_g_initializer_hz = g_hz,
			),
			off_reference_readout_zero_probe_frequency_fit = readout_coupling_off_frequency_fit,
			system_a_readout_like_zero_probe_frequency_fit = readout_frequency_fit,
			system_a_qubit_like_zero_probe_frequency_fit = qubit_frequency_fit,
			off_reference_readout_zero_probe_linewidth_fit = readout_linewidth_fit,
			finite_probe_g_extrapolation_diagnostic_not_authority = g_shift_fit_diagnostic,
			off_reference_readout_linewidth_hz = readout_off_reference_linewidth_hz,
			off_reference_qubit_response = isnothing(off_reference_qubit_root) ? nothing : merge(off_reference_qubit_root, (
				matrix_provenance = off_reference_qubit_y.provenance,
				frequency_grid = (
					role = "off_reference_qubit_differential_Y",
					analytic_scan_anchor_hz = evaluator.qubit_coupling_off_frequency_hz,
					anchor_role = "scan_assignment_only_not_frequency_authority",
					frequency_grid_sha256 = qubit_grid_sha256,
					frequency_grid_start_hz = first(qubit_frequencies_hz),
					frequency_grid_stop_hz = last(qubit_frequencies_hz),
					frequency_step_hz = settings.frequency_step_hz,
				),
			)),
			floating_qubit = (
				model_id = evaluator.floating_qubit_nominal.model_id,
				capacitance_source_id = evaluator.floating_qubit_nominal.capacitance_source_id,
				input_sha256 = evaluator.floating_qubit_input_sha256,
				topology_id = evaluator.floating_qubit_nominal.electrostatic_reduction.open_side_contract_status == "canonical_candidate" ?
					"d3-open-side-local-maxwell-kron-reduced-six-branch-two-parallel-lj-v2" :
					"d3-floating-qubit-kron-reduced-five-branch-two-parallel-lj-v1",
				coupling_off_reference = "Cr endpoint shunts retain nodal diagonals",
				off_reference_retained_loading = "qubit_side_Cr1_Cr2_diagonal_loading_with_physical_q_readout_exchange_off",
				off_reference_frequency_hz = qubit_off_reference_hz,
				analytic_kron_reduction_frequency_hz = evaluator.qubit_coupling_off_frequency_hz,
				qubit_frequency_grid_sha256 = qubit_grid_sha256,
					electrostatic_reduction = floating_qubit_reduction_evidence(
						evaluator.floating_qubit_nominal;
						f01_target_hz = evaluator.system_c_target_values["qubit_transition_frequency_hz"],
						expected_L_J_per_junction_nH = evaluator.system_c_target_values["qubit_junction_inductance_per_junction_h"] / D3_HENRIES_PER_NH,
					target_contract_id = evaluator.qubit_target_contract_id,
					target_contract_sha256 = evaluator.qubit_target_contract_sha256,
				),
			),
			reference_contract_id = reference_contract_id,
			filter_off_reference_id = filter_off_reference_id,
			common_readout_off_reference_id = common_readout_off_reference_id,
			filter_off_reference_frequency_grid_sha256 = filter_off_reference_grid_sha256,
			pair_frequency_grid_sha256 = pair_grid_sha256,
			qubit_frequency_grid_sha256 = qubit_grid_sha256,
			system_b_channel_calibration_initializer = isnothing(channel_calibration) ? nothing : _compact_channel_calibration(channel_calibration),
			system_b_j_initializer_fit = isnothing(j_fit) ? nothing : _compact_j_fit(j_fit),
			system_b_vector_crosscheck_poles_hz = vector_poles_hz,
			system_b_pair_vector_crosscheck = isnothing(pair_vector_result) ? nothing : _compact_vector_crosscheck(pair_vector_result),
			system_c_global_fit = Dict(key => value for (key, value) in system_c_fit if key != "fit_traces"),
			system_c_chain_reduction_check = chain_reduction_check,
			system_c_required_comparison_groups = promotion_status.comparison_status.required_groups,
			system_c_comparison_groups_complete = promotion_status.comparison_status.complete,
			system_c_comparison_status = promotion_status.comparison_status,
			system_c_promotion_eligible = promotion_status.promotion_eligible,
			system_c_promotion_blockers = promotion_status.promotion_blockers,
			system_c_initializer_attempt = initializer_attempt,
			system_c_initializer_seed_evidence = system_c_fit_inputs.initializer_seed_evidence,
			system_c_source_estimates = system_c_fit_inputs.source_estimates,
			system_c_source_to_seed_mapping = system_c_fit_inputs.source_to_system_c_seed_mapping,
			system_c_vf_evidence = system_c_vf_evidence,
			system_c_sweep_settings = settings.system_c_s21_lj_sweep,
			z21_ptc_complex_zero = z21_ptc_complex_zero,
			notch = notch,
			reference_notch = reference_notch,
		)
		j_fit_trace = isnothing(j_fit) ? nothing : j_fit["fit_trace"]
		traces = capture_traces ? (
			filter = isnothing(filter_hb) || isnothing(filter_off_reference_reference) ? nothing : (
				frequency_grid_sha256 = filter_off_reference_grid_sha256,
				measured_trace_id = filter_off_reference_trace_id,
				reference_trace_id = off_reference_empty_feedline_trace_id,
				frequencies_hz = filter_off_reference_frequencies_hz,
				s21 = ComplexF64.(filter_hb.s21),
				reference_s21 = filter_off_reference_reference,
			),
			readout_probe_sweep = readout_captures,
			pair = isnothing(system_b_pair_hb) || isnothing(pair_reference) || isnothing(j_fit_trace) ? nothing : (
				system = "B",
				frequency_grid_sha256 = pair_grid_sha256,
				measured_trace_id = pair_measured_trace_id,
				reference_trace_id = pair_empty_feedline_trace_id,
				frequencies_hz = pair_frequencies_hz,
				s21 = ComplexF64.(system_b_pair_hb.s21),
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
			system_c_lj_sweep = (
				traces = system_c_trace_evidence,
				fit_traces = system_c_fit["fit_traces"],
				per_lj = system_c_fit["per_lj"],
				vf_evidence = system_c_vf_evidence,
			),
			intrinsic = (
				system = "C",
				endpoint_composition = intrinsic_plan.metadata[:d3_z21_ptc_endpoint_composition],
				frequency_grid_sha256 = notch_grid_sha256,
				trace_id = loaded_notch_trace_id,
				frequencies_hz = notch_frequencies_hz,
				z21_ptc = ComplexF64.(intrinsic_hb.z21_ptc),
			),
			intrinsic_reference = (
				system = "B",
				endpoint_composition = reference_intrinsic_plan.metadata[:d3_z21_ptc_endpoint_composition],
				frequency_grid_sha256 = notch_grid_sha256,
				trace_id = reference_notch_trace_id,
				frequencies_hz = notch_frequencies_hz,
				z21_ptc = ComplexF64.(reference_intrinsic_hb.z21_ptc),
			),
			intrinsic_wide = intrinsic_wide_trace,
		) : nothing
		record = if publication_status.record_status === :valid
			(
				status = :valid,
				cost_publication_status = publication_status.cost_publication_status,
				promotion_eligible = promotion_status.promotion_eligible,
				promotion_blockers = promotion_status.promotion_blockers,
				metrics = metrics,
				diagnostics = diagnostics,
				traces = traces,
			)
		elseif publication_status.record_status === :inspectable
			(
				status = :inspectable,
				cost_publication_status = publication_status.cost_publication_status,
				publication_blockers = publication_status.publication_blockers,
				promotion_eligible = false,
				promotion_blockers = promotion_status.promotion_blockers,
				diagnostics = diagnostics,
				traces = traces,
			)
		else
			error("Unsupported System-C publication record status $(publication_status.record_status).")
		end
		evaluator.records[key] = record
		_journal_d3_evaluation!(evaluator, candidate, record)
		return record
	catch exception
		if exception isa D3CandidateRejected
				record = (
					status = :rejected,
					cost_publication_status = "withheld",
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
