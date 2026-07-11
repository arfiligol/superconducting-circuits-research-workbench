### A Pluto.jl notebook ###
# v1.0.2

#> [frontmatter]
#> title = "Orpen Q2D Purcell Pair Design Search"
#> tags = ["julia-core", "pluto", "q2d", "mtl", "purcell-filter", "design-search"]
#> description = "Length-first design search for Orpen Q2D intrinsic Purcell readout/filter pairs."

using Markdown
using InteractiveUtils

# ╔═╡ 50f7c70a-6994-4283-ae1a-765e314b2913
begin
	import Pkg
	Pkg.activate(joinpath(first(DEPOT_PATH), "environments", "v1.12"); io = devnull)

	using DelimitedFiles
	using LinearAlgebra
	using PlutoUI
	using Statistics
	using SuperconductingCircuitsCore
	using SuperconductingCircuitsVisualizer

	PlotlyJS = SuperconductingCircuitsVisualizer.PlotlyJS
	figure_config = PlotlyFigureConfig(
		download_filename = splitext(basename(@__FILE__))[1],
	)
	wide_figure_cell = WideCell(;
		max_width = max(1000, something(figure_config.display_width_px, 1000) + 80),
	)

	JSON3 = SuperconductingCircuitsCore.JSON3

	if !isdefined(@__MODULE__, :HBExampleHelpers)
		include(joinpath(@__DIR__, "..", "includes", "hb_example_helpers.jl"))
	end

	if !isdefined(@__MODULE__, :PortMatrixPostProcessing)
		include(joinpath(@__DIR__, "..", "includes", "port_matrix_post_processing.jl"))
	end

	zero_mode_s = HBExampleHelpers.zero_mode_s
	zero_mode_y_matrix_stack = PortMatrixPostProcessing.zero_mode_y_matrix_stack
	apply_port_termination_compensation =
		PortMatrixPostProcessing.apply_port_termination_compensation
	invert_port_matrix_stack = PortMatrixPostProcessing.invert_port_matrix_stack
end

# ╔═╡ 53e7b3e9-2e0f-4f76-8720-3890e453c8d2
TableOfContents()

# ╔═╡ 1263ae94-774b-4b19-a5f4-af72447b668e
md"""
# Orpen Q2D Purcell Pair Design Search

This notebook owns the first design-search pass only. It reads selected Orpen
Q2D RLGC cases, solves the five resonator section lengths from target delays,
then optionally runs the existing distributed circuit model on a small candidate
set. It does not define new package APIs.

Interpret the matrices with the canonical [Multiconductor RLGC Matrices: Basis, Modes, and Physical Meaning](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/transmission-lines/multiconductor-rlgc-matrix-semantics.qmd).
Interpret raw matrices and compensation through [Network Trace Views](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/network-trace-views.qmd),
[Port Reference Impedance Semantics](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/simulation/port-reference-impedance-semantics.qmd),
and [Port-Termination Compensation](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/simulation/port-termination-compensation.qmd).
The current OrPen payload and Workbench coupled consumer carry only $L/C$;
missing $R/G$ is not extracted zero-loss evidence.

This notebook derives PTC resistance from exact compiled port/resistor rows and
declares `intrinsic_pair_probe_scaffold` as the removal intent. The in-memory
check is evidence-backed; persisted traces still need the complete
row/value/removal-intent lineage before promotion.

The length solve uses single-trace delay outside the MTL window and MTL
diagonal delay inside the window:

```text
Tr = lr_short / v_single + lc / v_mtl + lr_open / v_single
Tp = lp_short / v_single + lc / v_mtl + lp_open / v_single
Tn = lr_short / v_single + lc / v_mtl + lp_short / v_single
```
"""

# ╔═╡ ed4f5b1c-766d-477a-bd20-bd501850fa81
begin
	um = 1.0e-6
	GHz = 1.0e9
	MHz = 1.0e6
	fF = 1.0e-15

	workspace_root = normpath(joinpath(@__DIR__, "..", "..", "..", ".."))
	orpen_circuit_output_dir = joinpath(
		workspace_root,
		"orpen_sc_pdk",
		"build",
		"simulation",
		"circuit",
		"intrinsic_purcell_filter",
	)
	case_json_path = joinpath(orpen_circuit_output_dir, "orpen_q2d_rlgc_cases.json")
	length_csv_path = joinpath(orpen_circuit_output_dir, "orpen_purcell_pair_length_candidates.csv")
	intrinsic_csv_path = joinpath(orpen_circuit_output_dir, "orpen_purcell_pair_intrinsic_hb.csv")
	fit_csv_path = joinpath(orpen_circuit_output_dir, "orpen_purcell_pair_shared_readout_s11_fit.csv")
	mode_csv_path = joinpath(orpen_circuit_output_dir, "orpen_purcell_pair_shared_readout_modes.csv")
	intrinsic_trace_dir = joinpath(orpen_circuit_output_dir, "orpen_purcell_pair_intrinsic_z21_traces")
	fit_trace_dir = joinpath(orpen_circuit_output_dir, "orpen_purcell_pair_s11_fit_traces")

	selected_case_id = :height7
	target_slot_sets = (
		(id = :wide_250mhz, name = "5.5-6.5 GHz / 250 MHz spacing", slots = [5.5, 5.75, 6.0, 6.25, 6.5], scan_start_ghz = 5.0, scan_stop_ghz = 7.0),
		(id = :dense_120mhz, name = "5.76-6.24 GHz / 120 MHz spacing", slots = [5.76, 5.88, 6.0, 6.12, 6.24], scan_start_ghz = 5.4, scan_stop_ghz = 6.6),
	)
	target_slot_rows = [
		(
			target_set_id = slot_set.id,
			target_set_name = slot_set.name,
			target_slot_ghz = Float64(slot_ghz),
			scan_start_ghz = Float64(slot_set.scan_start_ghz),
			scan_stop_ghz = Float64(slot_set.scan_stop_ghz),
		) for slot_set in target_slot_sets for slot_ghz in slot_set.slots
]
	isempty(target_slot_rows) && error("Set at least one target frequency in target_slot_sets.")
	target_slot_count = length(target_slot_rows)
	target_slots_ghz = [row.target_slot_ghz for row in target_slot_rows]
	notch_target_ghz = 4.5

	lc_grid_um = collect(100.0:20.0:320.0)
	short_split_grid = collect(0.10:0.05:0.90)
	min_section_length_um = 300.0
	total_length_bounds_um = (3500.0, 8000.0)

	run_intrinsic_hb = true
	run_readout_fit_hb = true
	simulation_candidate_count = target_slot_count
	frequency_step_mhz = 0.2
	intrinsic_scan_start_ghz = 3.8
	intrinsic_scan_stop_ghz = 6.8

	section_length_m = 10.0um
	port_resistance_ohm = 50.0
	readout_bus_length_um = 1000.0
	readout_bus_margin_um = 100.0
	filter_to_line_capacitance_fF_grid = [20.0]

	pump_frequency = 20.0GHz
	pump_current = 0.0
	optional_hb_kwargs = Dict{Symbol,Any}(
		:nbatches => 1,
		:iterations => 160,
		:ftol => 1.0e-8,
	)
end

# ╔═╡ 098bba23-811c-41b0-b963-4a2959652f91
begin
	isfile(case_json_path) || error(
		"Missing Orpen Q2D case JSON. Run orpen_sc_pdk/scripts/export_orpen_q2d_intrinsic_purcell_cases.py first: " *
		case_json_path,
	)
	case_payload = JSON3.read(read(case_json_path, String), Dict{String,Any})
end

# ╔═╡ ef8cb681-d81b-402a-91f9-4925321ce87a
begin
	function matrix2(value)
		return Float64[
			Float64(value[1][1]) Float64(value[1][2])
			Float64(value[2][1]) Float64(value[2][2])
		]
	end

	function require_symmetric_2x2(name, matrix)
		isapprox(matrix[1, 2], matrix[2, 1]; atol = 1.0e-18, rtol = 1.0e-9) ||
			error("$(name) must be symmetric: $(matrix)")
		return nothing
	end

	function require_positive_definite_2x2(name, matrix)
		isposdef(Symmetric(matrix)) || error("$(name) must be positive definite: $(matrix)")
		return nothing
	end

	function make_orpen_case(record)
		mtl = record["mtl"]
		single = record["single"]
		mtl_l = matrix2(mtl["l_matrix_h_per_m"])
		mtl_c = matrix2(mtl["c_matrix_f_per_m"])
		single_l = matrix2(single["l_matrix_h_per_m"])
		single_c = matrix2(single["c_matrix_f_per_m"])

		require_symmetric_2x2("MTL L", mtl_l)
		require_symmetric_2x2("MTL C", mtl_c)
		require_symmetric_2x2("single L", single_l)
		require_symmetric_2x2("single C", single_c)
		require_positive_definite_2x2("MTL L", mtl_l)
		require_positive_definite_2x2("MTL C", mtl_c)
		require_positive_definite_2x2("single L", single_l)
		require_positive_definite_2x2("single C", single_c)
		mtl_c[1, 2] <= 0 || error("MTL Maxwell C[1,2] must be non-positive.")

		mtl_diag_l = mtl_l[1, 1]
		mtl_diag_c = mtl_c[1, 1]
		single_l_per_m_h = Float64(single["l_per_m_h"])
		single_c_per_m_f = Float64(single["c_per_m_f"])

		return (
			id = Symbol(record["id"]),
			label = String(record["label"]),
			height_um = Float64(record["flip_chip_gap_height_um"]),
			mtl_point = record["mtl_point"],
			single_trace_point = record["single_trace_point"],
			mtl_l_matrix_h_per_m = mtl_l,
			mtl_c_matrix_f_per_m = mtl_c,
			single_l_matrix_h_per_m = single_l,
			single_c_matrix_f_per_m = single_c,
			single_l_per_m_h = single_l_per_m_h,
			single_c_per_m_f = single_c_per_m_f,
			mtl_diag_l_per_m_h = mtl_diag_l,
			mtl_diag_c_per_m_f = mtl_diag_c,
			single_velocity_m_per_s = 1 / sqrt(single_l_per_m_h * single_c_per_m_f),
			mtl_diag_velocity_m_per_s = 1 / sqrt(mtl_diag_l * mtl_diag_c),
			mtl_diag_zo_ohm = sqrt(mtl_diag_l / mtl_diag_c),
			zm_ohm = Float64(mtl["zm_ohm"]),
			zo_effective_ohm = Float64(single["zo_effective_ohm"]),
			zo_diagonal_ohm = Float64(single["zo_diagonal_ohm"]),
			delta_effective_ohm = Float64(record["match"]["delta_effective_ohm"]),
			delta_diagonal_ohm = Float64(record["match"]["delta_diagonal_ohm"]),
		)
	end

	orpen_cases = [make_orpen_case(record) for record in case_payload["cases"]]
	selected_case = only([case for case in orpen_cases if case.id == selected_case_id])
end

# ╔═╡ 2bf661f0-77e7-4822-9134-4c1e6e22f6cb
q2d_case_table = [
	(
		case_id = String(case.id),
		height_um = case.height_um,
		Zo_effective_ohm = case.zo_effective_ohm,
		Zo_diagonal_ohm = case.zo_diagonal_ohm,
		Zm_ohm = case.zm_ohm,
		delta_Zm_minus_Zo_effective_ohm = case.delta_effective_ohm,
		MTL_diagonal_Zo_ohm = case.mtl_diag_zo_ohm,
		single_velocity_m_per_s = case.single_velocity_m_per_s,
		mtl_diagonal_velocity_m_per_s = case.mtl_diag_velocity_m_per_s,
	)
	for case in orpen_cases
]

# ╔═╡ 5597a30d-2f6b-414d-9e47-b8e07b2284f8
begin
	function frequency_from_delay_ghz(delay_s)
		return 1 / (4 * Float64(delay_s)) / GHz
	end

	function solve_lengths_for_slot(; case, target_slot, lc_um, short_split, notch_target_ghz)
		slot_ghz = target_slot.target_slot_ghz
		v_single = case.single_velocity_m_per_s
		v_mtl = case.mtl_diag_velocity_m_per_s
		lc_delay_s = Float64(lc_um) * um / v_mtl
		tr_s = 1 / (4 * Float64(slot_ghz) * GHz)
		tp_s = tr_s
		tn_s = 1 / (4 * Float64(notch_target_ghz) * GHz)
		short_delay_sum_s = tn_s - lc_delay_s
		short_delay_sum_s > 0 || return nothing

		lr_short_delay_s = Float64(short_split) * short_delay_sum_s
		lp_short_delay_s = (1 - Float64(short_split)) * short_delay_sum_s
		lr_open_delay_s = tr_s - lc_delay_s - lr_short_delay_s
		lp_open_delay_s = tp_s - lc_delay_s - lp_short_delay_s
		minimum([lr_short_delay_s, lp_short_delay_s, lr_open_delay_s, lp_open_delay_s]) > 0 ||
			return nothing

		lr_short_um = lr_short_delay_s * v_single / um
		lp_short_um = lp_short_delay_s * v_single / um
		lr_open_um = lr_open_delay_s * v_single / um
		lp_open_um = lp_open_delay_s * v_single / um
		lr_total_um = lr_short_um + lc_um + lr_open_um
		lp_total_um = lp_short_um + lc_um + lp_open_um
		notch_length_um = lr_short_um + lc_um + lp_short_um

		fr_reconstructed_ghz = frequency_from_delay_ghz(
			lr_short_um * um / v_single + lc_delay_s + lr_open_um * um / v_single,
		)
		fp_reconstructed_ghz = frequency_from_delay_ghz(
			lp_short_um * um / v_single + lc_delay_s + lp_open_um * um / v_single,
		)
		fn_reconstructed_ghz = frequency_from_delay_ghz(
			lr_short_um * um / v_single + lc_delay_s + lp_short_um * um / v_single,
		)

		lengths = [lr_short_um, lp_short_um, lr_open_um, lp_open_um]
		lengths_ok = minimum(lengths) >= min_section_length_um
		total_ok = total_length_bounds_um[1] <= lr_total_um <= total_length_bounds_um[2] &&
			total_length_bounds_um[1] <= lp_total_um <= total_length_bounds_um[2]
		lengths_ok && total_ok || return nothing

		# ponytail: score is only a first-pass length rank; HB/fits own final ranking.
		analytic_score =
			abs(short_split - 0.5) / 0.5 +
			0.15 * abs(lc_um - 200.0) / 120.0 +
			0.05 * abs(slot_ghz - 6.0) / 0.5

		return (
			id = Symbol(
				"$(target_slot.target_set_id)_h$(round(Int, case.height_um * 10))_s$(round(Int, slot_ghz * 100))_lc$(round(Int, lc_um))_a$(round(Int, short_split * 100))",
			),
			case_id = case.id,
			target_set_id = target_slot.target_set_id,
			target_set_name = String(target_slot.target_set_name),
			scan_start_ghz = target_slot.scan_start_ghz,
			scan_stop_ghz = target_slot.scan_stop_ghz,
			slot_target_ghz = Float64(slot_ghz),
			notch_target_ghz = Float64(notch_target_ghz),
			lr_open_um = lr_open_um,
			lr_short_um = lr_short_um,
			lc_um = Float64(lc_um),
			lp_short_um = lp_short_um,
			lp_open_um = lp_open_um,
			lr_total_um = lr_total_um,
			lp_total_um = lp_total_um,
			notch_length_um = notch_length_um,
			short_split = Float64(short_split),
			lr_short_delay_ps = lr_short_delay_s / 1.0e-12,
			lc_delay_ps = lc_delay_s / 1.0e-12,
			lp_short_delay_ps = lp_short_delay_s / 1.0e-12,
			lr_total_delay_ps = tr_s / 1.0e-12,
			lp_total_delay_ps = tp_s / 1.0e-12,
			notch_delay_ps = tn_s / 1.0e-12,
			fr_est_ghz = fr_reconstructed_ghz,
			fp_est_ghz = fp_reconstructed_ghz,
			fn_est_ghz = fn_reconstructed_ghz,
			analytic_score = analytic_score,
		)
	end

	function first_n(values, count)
		return values[1:min(Int(count), length(values))]
	end

	function best_slot_candidate_for_target(length_candidates, target_slot)
		candidates = [
			row for row in length_candidates if
			row.target_set_id == target_slot.target_set_id &&
			row.slot_target_ghz == target_slot.target_slot_ghz
		]
		!isempty(candidates) || error(
			"No length candidates for target_set=$(target_slot.target_set_id), target_slot_ghz=$(target_slot.target_slot_ghz).",
		)
		return first(sort(candidates; by = row -> row.analytic_score))
	end

	function generate_length_candidates(case)
		candidates = Any[]
		for target_slot in target_slot_rows
			for lc_um in lc_grid_um
				for short_split in short_split_grid
					candidate = solve_lengths_for_slot(
						case = case,
						target_slot = target_slot,
						lc_um = lc_um,
						short_split = short_split,
						notch_target_ghz = notch_target_ghz,
					)
					isnothing(candidate) || push!(candidates, candidate)
				end
			end
		end
		return sort(candidates; by = row -> row.analytic_score)
	end

	length_candidates = generate_length_candidates(selected_case)
	isempty(length_candidates) && error("No length candidates survived the hard geometry filters.")

	best_slot_candidates = [
		best_slot_candidate_for_target(length_candidates, target_slot)
		for target_slot in target_slot_rows
	]

	simulation_seed_candidates = first_n(
		sort(best_slot_candidates; by = row -> abs(row.slot_target_ghz - 6.0)),
		simulation_candidate_count,
	)
end

# ╔═╡ e6b07033-1fb8-434a-8e99-16b9b6f49d41
length_handcheck_table = [
	(
		target_set_id = String(row.target_set_id),
		target_set_name = row.target_set_name,
		slot_GHz = row.slot_target_ghz,
		lr_open_um = row.lr_open_um,
		lr_short_um = row.lr_short_um,
		lc_um = row.lc_um,
		lp_short_um = row.lp_short_um,
		lp_open_um = row.lp_open_um,
		lr_total_um = row.lr_total_um,
		lp_total_um = row.lp_total_um,
		notch_length_um = row.notch_length_um,
		lr_short_delay_ps = row.lr_short_delay_ps,
		lc_delay_ps = row.lc_delay_ps,
		lp_short_delay_ps = row.lp_short_delay_ps,
		fr_est_GHz = row.fr_est_ghz,
		fp_est_GHz = row.fp_est_ghz,
		fn_est_GHz = row.fn_est_ghz,
		score = row.analytic_score,
	)
	for row in best_slot_candidates
]

# ╔═╡ 9a1d42ff-38c5-4710-a20d-321c77e47c1e
begin
	function frequency_range(start_hz, stop_hz, point_count)
		point_count == 1 && return [Float64(start_hz)]
		return collect(range(Float64(start_hz), Float64(stop_hz); length = Int(point_count)))
	end

	function frequency_range_with_step(start_hz, stop_hz, step_hz)
		step = Float64(step_hz)
		step > 0 || error("frequency step must be positive.")
		point_count = round(Int, (Float64(stop_hz) - Float64(start_hz)) / step) + 1
		point_count >= 2 || error("frequency range must contain at least two points.")
		return frequency_range(start_hz, stop_hz, point_count)
	end

	function csv_value(value)
		ismissing(value) && return ""
		return string(value)
	end

	function csv_slug(value)
		return replace(string(value), "." => "p", "-" => "m", "/" => "_", " " => "_")
	end

	function window_indices(frequencies_hz, center_hz, half_width_hz)
		indices = findall(frequency -> abs(frequency - center_hz) <= half_width_hz, frequencies_hz)
		return isempty(indices) ? collect(eachindex(frequencies_hz)) : indices
	end

	function local_peak_record(frequencies_hz, trace, center_hz; half_width_hz)
		indices = window_indices(frequencies_hz, center_hz, half_width_hz)
		local_value, local_position = findmax(abs.(trace[indices]))
		result_index = indices[local_position]
		return (
			index = result_index,
			frequency_ghz = frequencies_hz[result_index] / GHz,
			abs_value = local_value,
			at_sweep_edge = result_index == firstindex(frequencies_hz) ||
				result_index == lastindex(frequencies_hz),
		)
	end

	function local_minimum_record(frequencies_hz, trace, center_hz; half_width_hz)
		indices = window_indices(frequencies_hz, center_hz, half_width_hz)
		local_value, local_position = findmin(abs.(trace[indices]))
		result_index = indices[local_position]
		return (
			index = result_index,
			frequency_ghz = frequencies_hz[result_index] / GHz,
			abs_value = local_value,
			at_sweep_edge = result_index == firstindex(frequencies_hz) ||
				result_index == lastindex(frequencies_hz),
		)
	end

	function two_peak_splitting_mhz(frequencies_hz, trace, center_hz; half_width_hz, min_separation_hz)
		indices = window_indices(frequencies_hz, center_hz, half_width_hz)
		values = abs.(trace)
		peaks = Int[]
		for index in indices
			index == firstindex(values) && continue
			index == lastindex(values) && continue
			values[index] >= values[index - 1] && values[index] >= values[index + 1] &&
				push!(peaks, index)
		end
		sorted_peaks = sort(peaks; by = index -> values[index], rev = true)
		selected = Int[]
		for index in sorted_peaks
			all(abs(frequencies_hz[index] - frequencies_hz[other]) >= min_separation_hz for other in selected) ||
				continue
			push!(selected, index)
			length(selected) == 2 && break
		end
		length(selected) < 2 && return missing
		frequencies = sort(frequencies_hz[selected])
		return (frequencies[2] - frequencies[1]) / MHz
	end

	function ptc_z_traces(result, compiled)
		raw_y_stack = zero_mode_y_matrix_stack(result; ports = [1, 2])
		ptc_y_stack = apply_port_termination_compensation(
			raw_y_stack,
			compiled;
			compensate_port_indices = (1, 2),
			removal_intent = :intrinsic_pair_probe_scaffold,
		)
		ptc_z_stack = invert_port_matrix_stack(ptc_y_stack; source_kind = :ptc_z_from_y)
		return (
			z11 = vec(ptc_z_stack.values[1, 1, :]),
			z21 = vec(ptc_z_stack.values[2, 1, :]),
			z22 = vec(ptc_z_stack.values[2, 2, :]),
		)
	end

	function write_intrinsic_z21_trace_csv(path, frequencies_hz, z)
		mkpath(dirname(path))
		open(path, "w") do io
			println(io, "frequency_ghz,z11_abs_ohm,z21_re_ohm,z21_im_ohm,z21_abs_ohm,z22_abs_ohm")
			for index in eachindex(frequencies_hz)
				println(
					io,
					join(
						[
							frequencies_hz[index] / GHz,
							abs(z.z11[index]),
							real(z.z21[index]),
							imag(z.z21[index]),
							abs(z.z21[index]),
							abs(z.z22[index]),
						],
						",",
					),
				)
			end
		end
		return path
	end
end

# ╔═╡ bbe12ee0-8000-4fb6-b6f5-acb639f94ac8
begin
	function build_intrinsic_pair_plan(case, design)
		lr_total_m = design.lr_total_um * um
		lp_total_m = design.lp_total_um * um
		lr_short_m = design.lr_short_um * um
		lp_short_m = design.lp_short_um * um
		lc_m = design.lc_um * um

		readout_resonator_spec = RLGCSpec(
			length_m = lr_total_m,
			section_length_m = section_length_m,
			l_per_m_h = case.single_l_per_m_h,
			c_per_m_f = case.single_c_per_m_f,
		)
		filter_resonator_spec = RLGCSpec(
			length_m = lp_total_m,
			section_length_m = section_length_m,
			l_per_m_h = case.single_l_per_m_h,
			c_per_m_f = case.single_c_per_m_f,
		)
		mtl_model = MTLCoupledRLGCSpec(
			start1_m = lr_short_m,
			start2_m = lp_short_m,
			length_m = lc_m,
			section_length_m = section_length_m,
			l_matrix_per_m_h = case.mtl_l_matrix_h_per_m,
			c_matrix_per_m_f = case.mtl_c_matrix_f_per_m,
		)

		circuit_plan = @circuit "orpen-q2d-purcell-pair-$(design.id)" begin
			readout_grounded_head = external_node("readout_grounded_head")
			readout_open_tail = external_node("readout_open_tail")
			filter_grounded_head = external_node("filter_grounded_head")
			filter_open_tail = external_node("filter_open_tail")

			readout_resonator = quarter_wave_resonator!(
				id = :readout_resonator,
				grounded_head = readout_grounded_head,
				open_tail = readout_open_tail,
				spec = readout_resonator_spec,
				breakpoints_m = [lr_short_m, lr_short_m + lc_m],
				section_overrides = [coupled_line_section_override(mtl_model, 1)],
			)
			filter_resonator = quarter_wave_resonator!(
				id = :filter_resonator,
				grounded_head = filter_grounded_head,
				open_tail = filter_open_tail,
				spec = filter_resonator_spec,
				breakpoints_m = [lp_short_m, lp_short_m + lc_m],
				section_overrides = [coupled_line_section_override(mtl_model, 2)],
			)
			couple_transmission_window!(
				id = :readout_filter_mtl_window,
				line1 = readout_resonator.line,
				line2 = filter_resonator.line,
				start1 = lr_short_m,
				start2 = lp_short_m,
				length = lc_m,
				model = mtl_model,
				coupling_orientation = :same_direction,
			)
			port(:readout_open_port) do
				index = 1
				endpoint = readout_open_tail
				resistance = port_resistance_ohm
				role = :readout_open_end
			end
			port(:filter_open_port) do
				index = 2
				endpoint = filter_open_tail
				resistance = port_resistance_ohm
				role = :filter_open_end
			end
		end

		@hbintent circuit_plan begin
			pump_axis(:pump; frequency_parameter = :pump_frequency)
			source_slot(:pump_in) do
				role = :pump
				port = :readout_open_port
				mode = (1,)
				current_parameter = :pump_current
			end
			sparameter(:s11) do
				outputmode = (0,)
				outputport = :readout_open_port
				inputmode = (0,)
				inputport = :readout_open_port
			end
			sparameter(:s21) do
				outputmode = (0,)
				outputport = :filter_open_port
				inputmode = (0,)
				inputport = :readout_open_port
			end
			solver_controls() do
				n_pump_harmonics = 1
				n_modulation_harmonics = 1
				returnS = true
				returnZ = true
				returnQE = true
				returnCM = true
				keyedarrays = false
			end
		end

		return circuit_plan
	end

	function run_intrinsic_candidate(case, design)
		frequencies_hz = frequency_range_with_step(
			intrinsic_scan_start_ghz * GHz,
			intrinsic_scan_stop_ghz * GHz,
			frequency_step_mhz * MHz,
		)
		circuit_plan = build_intrinsic_pair_plan(case, design)
		validation_report = validate_hb_intent(circuit_plan)
		compiled = compile_to_josephson(circuit_plan)
		hb_problem = build_hb_problem(
			compiled,
			HBRunSpec(
				frequency_sweep = frequencies_hz,
				pump_frequencies = Dict(:pump => Float64(pump_frequency)),
				source_currents = Dict(:pump_in => Float64(pump_current)),
				optional_hb_kwargs = Dict{Symbol,Any}(optional_hb_kwargs),
			),
		)
		result = run_hb_problem(hb_problem)
		z = ptc_z_traces(result, compiled)
		fr = local_peak_record(result.frequencies_hz, z.z11, design.fr_est_ghz * GHz; half_width_hz = 0.7GHz)
		fp = local_peak_record(result.frequencies_hz, z.z22, design.fp_est_ghz * GHz; half_width_hz = 0.7GHz)
		fn = local_minimum_record(result.frequencies_hz, z.z21, notch_target_ghz * GHz; half_width_hz = 0.8GHz)
		splitting_mhz = two_peak_splitting_mhz(
			result.frequencies_hz,
			z.z21,
			design.slot_target_ghz * GHz;
			half_width_hz = 0.8GHz,
			min_separation_hz = 8.0MHz,
		)
		half_z21_peak_split_mhz = ismissing(splitting_mhz) ? missing : splitting_mhz / 2
		score =
			abs(fr.frequency_ghz - design.slot_target_ghz) / 0.5 +
			abs(fp.frequency_ghz - design.slot_target_ghz) / 0.5 +
			abs(fn.frequency_ghz - notch_target_ghz) / 0.25
		trace_csv = joinpath(
			intrinsic_trace_dir,
			"set_$(csv_slug(design.target_set_id))__slot_$(csv_slug(design.slot_target_ghz))GHz__z21.csv",
		)
		write_intrinsic_z21_trace_csv(trace_csv, result.frequencies_hz, z)

		return (
			id = design.id,
			case_id = design.case_id,
			target_set_id = String(design.target_set_id),
			target_set_name = design.target_set_name,
			slot_target_ghz = design.slot_target_ghz,
			lc_um = design.lc_um,
			fr_hb_ghz = fr.frequency_ghz,
			fp_hb_ghz = fp.frequency_ghz,
			fn_hb_ghz = fn.frequency_ghz,
			z21_notch_abs_ohm = fn.abs_value,
			z21_peak_splitting_mhz = splitting_mhz,
			half_z21_peak_split_mhz = half_z21_peak_split_mhz,
			z21_pair_peaks_visible_intrinsic = !ismissing(splitting_mhz),
			trace_csv = trace_csv,
			hb_intent_ok = !has_errors(validation_report),
			netlist_rows = length(compiled.netlist),
			score = score,
		)
	end
end

# ╔═╡ 32a02daa-241a-4a60-8207-2c4ca07b55cb
intrinsic_hb_table = run_intrinsic_hb ?
	[run_intrinsic_candidate(selected_case, design) for design in simulation_seed_candidates] :
	NamedTuple[]

# ╔═╡ 892b45d5-54e0-4823-8dcf-202907505c74
begin
	function spring_gamma_p(frequency_hz; fp_hz, fr_hz, j_hz, kappa_p_hz)
		omega = 2π * Float64(frequency_hz)
		omega_p = 2π * Float64(fp_hz)
		omega_r = 2π * Float64(fr_hz)
		j = 2π * Float64(j_hz)
		kappa_p = 2π * Float64(kappa_p_hz)
		tiny_gamma = 2π * 1.0e3
		denominator = im * (omega - omega_p) + kappa_p / 2 +
			j^2 / (im * (omega - omega_r) + tiny_gamma / 2)
		return 1 - kappa_p / denominator
	end

	function spring_branch_admittance(frequencies_hz; fp_hz, fr_hz, j_hz, kappa_p_hz)
		gamma_p = [
			spring_gamma_p(
				frequency;
				fp_hz = fp_hz,
				fr_hz = fr_hz,
				j_hz = j_hz,
				kappa_p_hz = kappa_p_hz,
			)
			for frequency in frequencies_hz
		]
		return (1 .- gamma_p) ./ (1 .+ gamma_p)
	end

	function shared_readout_core(params, frequencies_hz, branch_count)
		total_y = zeros(ComplexF64, length(frequencies_hz))
		for branch_index in 1:branch_count
			offset = 4 * (branch_index - 1)
			fp_ghz, fr_ghz, j_mhz, kappa_mhz = params[(offset + 1):(offset + 4)]
			total_y .+= spring_branch_admittance(
				frequencies_hz;
				fp_hz = fp_ghz * GHz,
				fr_hz = fr_ghz * GHz,
				j_hz = j_mhz * MHz,
				kappa_p_hz = kappa_mhz * MHz,
			)
		end
		return (
			s11 = -total_y ./ (2 .+ total_y),
			s21 = 2 ./ (2 .+ total_y),
		)
	end

	function affine_fit_curve(model_values, data)
		matrix = hcat(ones(ComplexF64, length(model_values)), ComplexF64.(model_values))
		coefficients = matrix \ ComplexF64.(data)
		return (curve = matrix * coefficients, offset = coefficients[1], scale = coefficients[2])
	end

	function s11_fit_metrics(s11_data, s11_fit)
		complex_residual = s11_fit .- s11_data
		abs_residual = abs.(s11_fit) .- abs.(s11_data)
		complex_sse = sum(abs2, complex_residual)
		complex_sst = sum(abs2, s11_data .- mean(s11_data))
		abs_sse = sum(abs2, abs_residual)
		abs_sst = sum(abs2, abs.(s11_data) .- mean(abs.(s11_data)))
		return (
			s11_complex_mse = mean(abs2, complex_residual),
			s11_complex_rmse = sqrt(mean(abs2, complex_residual)),
			s11_complex_r2 = 1 - complex_sse / complex_sst,
			s11_abs_mse = mean(abs2, abs_residual),
			s11_abs_rmse = sqrt(mean(abs2, abs_residual)),
			s11_abs_r2 = 1 - abs_sse / abs_sst,
			s11_max_complex_error = maximum(abs.(complex_residual)),
			s11_max_abs_error = maximum(abs.(abs_residual)),
		)
	end

	function shared_fit_curves(params, frequencies_hz, s11_data, branch_count)
		core = shared_readout_core(params, frequencies_hz, branch_count)
		s11_fit = affine_fit_curve(core.s11, s11_data)
		return (
			s11 = s11_fit.curve,
			s21_model = core.s21,
			s11_offset = s11_fit.offset,
			s11_scale = s11_fit.scale,
			metrics = s11_fit_metrics(s11_data, s11_fit.curve),
		)
	end

	function shared_fit_loss(params, frequencies_hz, s11_data, branch_count)
		fit = shared_fit_curves(params, frequencies_hz, s11_data, branch_count)
		return fit.metrics.s11_complex_mse
	end

	function clamp_fit_params(params, bounds)
		return [
			min(max(params[index], bounds[index][1]), bounds[index][2])
			for index in eachindex(params)
		]
	end

	function coordinate_fit_shared(frequencies_hz, s11_data, initial_params, bounds, branch_count)
		params = clamp_fit_params(collect(Float64.(initial_params)), bounds)
		steps = repeat([0.02, 0.02, 3.0, 8.0], branch_count)
		best = shared_fit_loss(params, frequencies_hz, s11_data, branch_count)
		while maximum(steps) > 0.04
			improved = false
			for index in eachindex(params)
				for direction in (-1.0, 1.0)
					candidate = copy(params)
					candidate[index] += direction * steps[index]
					candidate = clamp_fit_params(candidate, bounds)
					loss = shared_fit_loss(candidate, frequencies_hz, s11_data, branch_count)
					if loss < best
						params = candidate
						best = loss
						improved = true
					end
				end
			end
			improved || (steps ./= 2)
		end
		return (params = params, loss = best)
	end
end

# ╔═╡ dff52a16-2d12-49e1-81b8-d503b061609d
begin
	function write_shared_readout_trace_csv(path, frequencies_hz, s11, fitted_s11, s21)
		mkpath(dirname(path))
		open(path, "w") do io
			println(io, "frequency_ghz,s11_re,s11_im,s11_abs,s11_fit_re,s11_fit_im,s11_fit_abs,s21_re,s21_im,s21_abs")
			for index in eachindex(frequencies_hz)
				println(
					io,
					join(
						[
							frequencies_hz[index] / GHz,
							real(s11[index]),
							imag(s11[index]),
							abs(s11[index]),
							real(fitted_s11[index]),
							imag(fitted_s11[index]),
							abs(fitted_s11[index]),
							real(s21[index]),
							imag(s21[index]),
							abs(s21[index]),
						],
						",",
					),
				)
			end
		end
		return path
	end

	function designs_for_target_set(designs, target_set_id)
		selected = sort(
			[design for design in designs if design.target_set_id == target_set_id];
			by = design -> design.slot_target_ghz,
		)
		length(selected) == 5 || error("Target set $(target_set_id) must have five pair designs, got $(length(selected)).")
		return selected
	end

	function target_set_design_groups(designs)
		return [
			(
				target_set_id = slot_set.id,
				target_set_name = String(slot_set.name),
				scan_start_ghz = Float64(slot_set.scan_start_ghz),
				scan_stop_ghz = Float64(slot_set.scan_stop_ghz),
				designs = designs_for_target_set(designs, slot_set.id),
			)
			for slot_set in target_slot_sets
		]
	end

	function readout_fit_frequency_range(target_set)
		return frequency_range_with_step(
			target_set.scan_start_ghz * GHz,
			target_set.scan_stop_ghz * GHz,
			frequency_step_mhz * MHz,
		)
	end

	function readout_branch_positions_m(branch_count)
		start_m = readout_bus_margin_um * um
		stop_m = (readout_bus_length_um - readout_bus_margin_um) * um
		stop_m > start_m || error("readout_bus_length_um must be larger than 2 * readout_bus_margin_um.")
		return collect(range(start_m, stop_m; length = branch_count))
	end

	function build_shared_readout_fit_plan(case, target_set, capacitance_fF)
		designs = target_set.designs
		branch_positions_m = readout_branch_positions_m(length(designs))
		readout_line_length_m = readout_bus_length_um * um
		readout_line_spec = RLGCSpec(
			length_m = readout_line_length_m,
			section_length_m = section_length_m,
			l_per_m_h = case.single_l_per_m_h,
			c_per_m_f = case.single_c_per_m_f,
		)

		circuit_plan = CircuitPlan("orpen-q2d-shared-readout-$(target_set.target_set_id)")
		input = external_node("readout_input")
		output = external_node("readout_output")

		readout_line = transmission_line!(
			circuit_plan;
			id = :readout_line,
			head = input,
			tail = output,
			spec = readout_line_spec,
			head_termination = :external,
			tail_termination = :external,
			breakpoints_m = branch_positions_m,
		)
		for (index, design) in pairs(designs)
			lr_total_m = design.lr_total_um * um
			lp_total_m = design.lp_total_um * um
			lr_short_m = design.lr_short_um * um
			lp_short_m = design.lp_short_um * um
			lc_m = design.lc_um * um
			readout_resonator_spec = RLGCSpec(
				length_m = lr_total_m,
				section_length_m = section_length_m,
				l_per_m_h = case.single_l_per_m_h,
				c_per_m_f = case.single_c_per_m_f,
			)
			filter_resonator_spec = RLGCSpec(
				length_m = lp_total_m,
				section_length_m = section_length_m,
				l_per_m_h = case.single_l_per_m_h,
				c_per_m_f = case.single_c_per_m_f,
			)
			mtl_model = MTLCoupledRLGCSpec(
				start1_m = lr_short_m,
				start2_m = lp_short_m,
				length_m = lc_m,
				section_length_m = section_length_m,
				l_matrix_per_m_h = case.mtl_l_matrix_h_per_m,
				c_matrix_per_m_f = case.mtl_c_matrix_f_per_m,
			)
			readout_grounded_head = external_node("readout_grounded_head_$(index)")
			readout_open_tail = external_node("readout_open_tail_$(index)")
			filter_grounded_head = external_node("filter_grounded_head_$(index)")
			filter_open_tail = external_node("filter_open_tail_$(index)")
			readout_resonator = quarter_wave_resonator!(
				circuit_plan;
				id = Symbol("readout_resonator_$(index)"),
				grounded_head = readout_grounded_head,
				open_tail = readout_open_tail,
				spec = readout_resonator_spec,
				breakpoints_m = [lr_short_m, lr_short_m + lc_m],
				section_overrides = [coupled_line_section_override(mtl_model, 1)],
			)
			filter_resonator = quarter_wave_resonator!(
				circuit_plan;
				id = Symbol("filter_resonator_$(index)"),
				grounded_head = filter_grounded_head,
				open_tail = filter_open_tail,
				spec = filter_resonator_spec,
				breakpoints_m = [lp_short_m, lp_short_m + lc_m],
				section_overrides = [coupled_line_section_override(mtl_model, 2)],
			)
			couple_transmission_window!(
				circuit_plan;
				id = Symbol("readout_filter_mtl_window_$(index)"),
				line1 = readout_resonator.line,
				line2 = filter_resonator.line,
				start1 = lr_short_m,
				start2 = lp_short_m,
				length = lc_m,
				model = mtl_model,
				coupling_orientation = :same_direction,
			)
			couple_capacitive!(
				circuit_plan;
				id = Symbol("filter_to_readout_line_$(index)"),
				from = node_at_distance(readout_line, branch_positions_m[index]),
				to = filter_open_tail,
				capacitance = Float64(capacitance_fF) * fF,
				role = :filter_to_readout_line_coupling,
			)
		end
		external_port!(
			circuit_plan;
			id = :input_port,
			index = 1,
			endpoint = input,
			resistance = port_resistance_ohm,
			role = :readout_line_input,
		)
		external_port!(
			circuit_plan;
			id = :output_port,
			index = 2,
			endpoint = output,
			resistance = port_resistance_ohm,
			role = :readout_line_output,
		)

		@hbintent circuit_plan begin
			pump_axis(:pump; frequency_parameter = :pump_frequency)
			source_slot(:pump_in) do
				role = :pump
				port = :input_port
				mode = (1,)
				current_parameter = :pump_current
			end
			sparameter(:s11) do
				outputmode = (0,)
				outputport = :input_port
				inputmode = (0,)
				inputport = :input_port
			end
			sparameter(:s21) do
				outputmode = (0,)
				outputport = :output_port
				inputmode = (0,)
				inputport = :input_port
			end
			solver_controls() do
				n_pump_harmonics = 1
				n_modulation_harmonics = 1
				returnS = true
				returnZ = true
				returnQE = true
				returnCM = true
				keyedarrays = false
			end
		end

		return circuit_plan
	end

	function shared_initial_params(designs)
		return collect(Iterators.flatten(([design.fp_est_ghz, design.fr_est_ghz, 10.0, 40.0] for design in designs)))
	end

	function shared_fit_bounds(designs)
		return collect(Iterators.flatten((
			[
				(max(design.scan_start_ghz, design.slot_target_ghz - 0.20), min(design.scan_stop_ghz, design.slot_target_ghz + 0.20)),
				(max(design.scan_start_ghz, design.slot_target_ghz - 0.20), min(design.scan_stop_ghz, design.slot_target_ghz + 0.20)),
				(1.0, 200.0),
				(1.0, 400.0),
			]
			for design in designs
		)))
	end

	function mode_rows_from_fit(target_set, params, fit_loss, capacitance_fF)
		rows = NamedTuple[]
		for (index, design) in pairs(target_set.designs)
			offset = 4 * (index - 1)
			fp_ghz, fr_ghz, j_mhz, kappa_mhz = params[(offset + 1):(offset + 4)]
			center_ghz = (fp_ghz + fr_ghz) / 2
			mode_half_split_ghz = sqrt(((fp_ghz - fr_ghz) / 2)^2 + (j_mhz / 1000)^2)
			for (mode_label, mode_frequency_ghz) in (("lower", center_ghz - mode_half_split_ghz), ("upper", center_ghz + mode_half_split_ghz))
				push!(
					rows,
					(
						target_set_id = String(target_set.target_set_id),
						target_set_name = target_set.target_set_name,
						slot_target_ghz = design.slot_target_ghz,
						mode = mode_label,
						mode_frequency_ghz = mode_frequency_ghz,
						filter_to_line_capacitance_fF = Float64(capacitance_fF),
						fit_loss = fit_loss,
					),
				)
			end
		end
		return rows
	end

	function run_shared_readout_fit(case, target_set, capacitance_fF)
		frequencies_hz = readout_fit_frequency_range(target_set)
		circuit_plan = build_shared_readout_fit_plan(case, target_set, capacitance_fF)
		validation_report = validate_hb_intent(circuit_plan)
		compiled = compile_to_josephson(circuit_plan)
		hb_problem = build_hb_problem(
			compiled,
			HBRunSpec(
				frequency_sweep = frequencies_hz,
				pump_frequencies = Dict(:pump => Float64(pump_frequency)),
				source_currents = Dict(:pump_in => Float64(pump_current)),
				optional_hb_kwargs = Dict{Symbol,Any}(optional_hb_kwargs),
			),
		)
		result = run_hb_problem(hb_problem)
		s11 = zero_mode_s(result, 1, 1)
		s21 = zero_mode_s(result, 2, 1)
		branch_count = length(target_set.designs)
		fit = coordinate_fit_shared(
			result.frequencies_hz,
			s11,
			shared_initial_params(target_set.designs),
			shared_fit_bounds(target_set.designs),
			branch_count,
		)
		fitted = shared_fit_curves(fit.params, result.frequencies_hz, s11, branch_count)
		fit_trace_stem =
			"set_$(csv_slug(target_set.target_set_id))__shared_readout__c_$(csv_slug(capacitance_fF))fF"
		trace_csv = joinpath(fit_trace_dir, "$(fit_trace_stem).csv")
		write_shared_readout_trace_csv(
			trace_csv,
			result.frequencies_hz,
			s11,
			fitted.s11,
			s21,
		)

		fit_rows = NamedTuple[]
		for (index, design) in pairs(target_set.designs)
			offset = 4 * (index - 1)
			fp_ghz, fr_ghz, j_mhz, kappa_mhz = fit.params[(offset + 1):(offset + 4)]
			visible = kappa_mhz <= 40.0 && 2 * j_mhz >= max(5.0, kappa_mhz / 2)
			score =
				abs(fr_ghz - design.slot_target_ghz) / 0.5 +
				abs(fp_ghz - design.slot_target_ghz) / 0.5 +
				abs(j_mhz - 10.0) / 10.0 +
				max(0.0, kappa_mhz - 40.0) / 40.0 +
				(visible ? 0.0 : 1.0)
			push!(
				fit_rows,
				(
					id = design.id,
					case_id = design.case_id,
					target_set_id = String(target_set.target_set_id),
					target_set_name = target_set.target_set_name,
					slot_target_ghz = design.slot_target_ghz,
					filter_to_line_capacitance_fF = Float64(capacitance_fF),
					fr_fit_ghz = fr_ghz,
					fp_fit_ghz = fp_ghz,
					j_fit_mhz = j_mhz,
					kappa_p_fit_mhz = kappa_mhz,
					splitting_visible = visible,
					fit_loss = fit.loss,
					s11_complex_mse = fitted.metrics.s11_complex_mse,
					s11_complex_rmse = fitted.metrics.s11_complex_rmse,
					s11_complex_r2 = fitted.metrics.s11_complex_r2,
					s11_abs_mse = fitted.metrics.s11_abs_mse,
					s11_abs_rmse = fitted.metrics.s11_abs_rmse,
					s11_abs_r2 = fitted.metrics.s11_abs_r2,
					s11_max_complex_error = fitted.metrics.s11_max_complex_error,
					s11_max_abs_error = fitted.metrics.s11_max_abs_error,
					trace_csv = trace_csv,
					hb_intent_ok = !has_errors(validation_report),
					netlist_rows = length(compiled.netlist),
					ranking_score = score,
				),
			)
		end

		return (
			target_set_id = target_set.target_set_id,
			target_set_name = target_set.target_set_name,
			frequencies_hz = result.frequencies_hz,
			s11 = s11,
			s21 = s21,
			fitted_s11 = fitted.s11,
			fit_rows = fit_rows,
			mode_rows = mode_rows_from_fit(target_set, fit.params, fit.loss, capacitance_fF),
			trace_csv = trace_csv,
			fit_loss = fit.loss,
			hb_intent_ok = !has_errors(validation_report),
			netlist_rows = length(compiled.netlist),
		)
	end
end

# ╔═╡ adf0eae2-f2ec-40bd-ae7c-3e9eaf2648f1
begin
	shared_target_sets = target_set_design_groups(simulation_seed_candidates)
	shared_readout_runs = run_readout_fit_hb ?
		[
			run_shared_readout_fit(selected_case, target_set, capacitance_fF)
			for target_set in shared_target_sets
			for capacitance_fF in filter_to_line_capacitance_fF_grid
		] :
		NamedTuple[]

	function flatten_rows(vectors)
		rows = NamedTuple[]
		for vector in vectors
			append!(rows, vector)
		end
		return rows
	end

	s11_fit_table = flatten_rows([run.fit_rows for run in shared_readout_runs])
	shared_mode_table = flatten_rows([run.mode_rows for run in shared_readout_runs])
end

# ╔═╡ 0ab2bcf9-9d8f-4f07-a737-9f7d60f80f70
begin
	function shared_readout_plot(run)
		return PlotlyJS.Plot(
			[
				PlotlyJS.scatter(
					x = run.frequencies_hz ./ GHz,
					y = abs.(run.s11),
					mode = "markers",
					name = "HB |S11|",
					marker = PlotlyJS.attr(color = "#0072B2", size = 4),
				),
				PlotlyJS.scatter(
					x = run.frequencies_hz ./ GHz,
					y = abs.(run.fitted_s11),
					mode = "lines",
					name = "S11 fit",
					line = PlotlyJS.attr(color = "#0072B2", width = 2, dash = "dash"),
				),
				PlotlyJS.scatter(
					x = run.frequencies_hz ./ GHz,
					y = abs.(run.s21),
					mode = "markers",
					name = "HB |S21|",
					marker = PlotlyJS.attr(color = "#D55E00", size = 4),
				),
			],
			PlotlyJS.Layout(
				title = "Shared Readout Sweep: $(run.target_set_name)",
				xaxis = PlotlyJS.attr(title = "Frequency (GHz)"),
				yaxis = PlotlyJS.attr(title = "|S|"),
			),
		)
	end

	shared_readout_plots = [shared_readout_plot(run) for run in shared_readout_runs]
end

# ╔═╡ 0e19cf8b-c2ef-48e0-b80d-5c786cb27f14
wide_250mhz_shared_readout_plot = isempty(shared_readout_plots) ? missing : shared_readout_plots[1]

# ╔═╡ f65201dd-ff6f-4f97-98d1-1f3d77a24068
dense_120mhz_shared_readout_plot = length(shared_readout_plots) < 2 ? missing : shared_readout_plots[2]

# ╔═╡ 18ef418c-7dc3-4bea-9345-158a7c224268
begin
	function read_intrinsic_z21_trace(path)
		data, _ = readdlm(path, ','; header = true)
		return (
			frequency_ghz = Float64.(data[:, 1]),
			z21_abs_ohm = Float64.(data[:, 5]),
		)
	end

	function intrinsic_z21_plot(target_set_id)
		rows = sort(
			[row for row in intrinsic_hb_table if row.target_set_id == String(target_set_id)];
			by = row -> row.slot_target_ghz,
		)
		traces = [
			begin
			trace = read_intrinsic_z21_trace(row.trace_csv)
				PlotlyJS.scatter(
					x = trace.frequency_ghz,
					y = trace.z21_abs_ohm,
					mode = "markers",
					name = "target $(round(row.slot_target_ghz; digits = 2)) GHz",
					marker = PlotlyJS.attr(size = 4),
				)
			end
			for row in rows
		]
		title = isempty(rows) ? "Intrinsic Z21" : "Intrinsic Pair Z21: $(first(rows).target_set_name)"
		return PlotlyJS.Plot(
			traces,
			PlotlyJS.Layout(
				title = title,
				xaxis = PlotlyJS.attr(title = "Frequency (GHz)"),
				yaxis = PlotlyJS.attr(title = "|Z21| (ohm)", type = "log"),
			),
		)
	end

	intrinsic_z21_plots = [
		intrinsic_z21_plot(slot_set.id)
		for slot_set in target_slot_sets
	]
end

# ╔═╡ c874c238-fb4d-4f02-b309-9cab3d5982ab
wide_250mhz_intrinsic_z21_plot = isempty(intrinsic_z21_plots) ? missing : intrinsic_z21_plots[1]

# ╔═╡ e614274a-c7cd-4061-812c-614fdff06caf
dense_120mhz_intrinsic_z21_plot = length(intrinsic_z21_plots) < 2 ? missing : intrinsic_z21_plots[2]

# ╔═╡ 7c35b1ec-a69a-4fe2-8826-648e2ca39b07
begin
	function write_namedtuple_csv(path, rows)
		mkpath(dirname(path))
		if isempty(rows)
			open(path, "w") do io
				println(io, "")
			end
			return path
		end
		names = propertynames(first(rows))
		open(path, "w") do io
			println(io, join(string.(names), ","))
			for row in rows
				println(io, join([csv_value(getproperty(row, name)) for name in names], ","))
			end
		end
		return path
	end

	write_namedtuple_csv(length_csv_path, length_handcheck_table)
	run_intrinsic_hb && write_namedtuple_csv(intrinsic_csv_path, intrinsic_hb_table)
	run_readout_fit_hb && write_namedtuple_csv(fit_csv_path, s11_fit_table)
	run_readout_fit_hb && write_namedtuple_csv(mode_csv_path, shared_mode_table)

	output_paths = (
		length_csv = length_csv_path,
		intrinsic_csv = run_intrinsic_hb ? intrinsic_csv_path : "not written; set run_intrinsic_hb = true",
		s11_fit_csv = run_readout_fit_hb ? fit_csv_path : "not written; set run_readout_fit_hb = true",
		shared_mode_csv = run_readout_fit_hb ? mode_csv_path : "not written; set run_readout_fit_hb = true",
		intrinsic_trace_dir = intrinsic_trace_dir,
		s11_fit_trace_dir = fit_trace_dir,
	)
end

# ╔═╡ e44aa6b4-3a5a-48ec-b1e0-67887dd9b333
begin
	length_self_check = (
		has_expected_slots = length(best_slot_candidates) == length(target_slot_rows),
		fr_roundtrip_ok = all(row -> abs(row.fr_est_ghz - row.slot_target_ghz) < 1.0e-9, best_slot_candidates),
		fp_roundtrip_ok = all(row -> abs(row.fp_est_ghz - row.slot_target_ghz) < 1.0e-9, best_slot_candidates),
		fn_roundtrip_ok = all(row -> abs(row.fn_est_ghz - notch_target_ghz) < 1.0e-9, best_slot_candidates),
		min_section_ok = all(
			row -> minimum([row.lr_open_um, row.lr_short_um, row.lp_short_um, row.lp_open_um]) >= min_section_length_um,
			best_slot_candidates,
		),
	)
	all(values(length_self_check)) || error("Length generator self-check failed: $(length_self_check)")
	length_self_check
end

# ╔═╡ Cell order:
# ╠═50f7c70a-6994-4283-ae1a-765e314b2913
# ╠═53e7b3e9-2e0f-4f76-8720-3890e453c8d2
# ╟─1263ae94-774b-4b19-a5f4-af72447b668e
# ╠═ed4f5b1c-766d-477a-bd20-bd501850fa81
# ╠═098bba23-811c-41b0-b963-4a2959652f91
# ╠═ef8cb681-d81b-402a-91f9-4925321ce87a
# ╠═2bf661f0-77e7-4822-9134-4c1e6e22f6cb
# ╠═5597a30d-2f6b-414d-9e47-b8e07b2284f8
# ╠═e6b07033-1fb8-434a-8e99-16b9b6f49d41
# ╠═9a1d42ff-38c5-4710-a20d-321c77e47c1e
# ╠═bbe12ee0-8000-4fb6-b6f5-acb639f94ac8
# ╠═32a02daa-241a-4a60-8207-2c4ca07b55cb
# ╠═892b45d5-54e0-4823-8dcf-202907505c74
# ╠═dff52a16-2d12-49e1-81b8-d503b061609d
# ╠═adf0eae2-f2ec-40bd-ae7c-3e9eaf2648f1
# ╠═0ab2bcf9-9d8f-4f07-a737-9f7d60f80f70
# ╠═0e19cf8b-c2ef-48e0-b80d-5c786cb27f14
# ╠═f65201dd-ff6f-4f97-98d1-1f3d77a24068
# ╠═18ef418c-7dc3-4bea-9345-158a7c224268
# ╠═c874c238-fb4d-4f02-b309-9cab3d5982ab
# ╠═e614274a-c7cd-4061-812c-614fdff06caf
# ╠═7c35b1ec-a69a-4fe2-8826-648e2ca39b07
# ╠═e44aa6b4-3a5a-48ec-b1e0-67887dd9b333
