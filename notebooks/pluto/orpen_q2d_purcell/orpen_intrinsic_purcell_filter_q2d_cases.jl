### A Pluto.jl notebook ###
# v1.0.1

#> [frontmatter]
#> title = "Orpen Q2D Intrinsic Purcell Filter Cases"
#> tags = ["julia-core", "pluto", "hb", "mtl", "purcell-filter", "orpen-q2d"]
#> description = "Intrinsic Purcell-filter circuit run fed by selected Orpen AEDT Q2D RLGC matrices."

using Markdown
using InteractiveUtils

# ╔═╡ 1839a880-dc2b-4d23-91d0-199a12eac724
begin
	import Pkg
	Pkg.activate(joinpath(first(DEPOT_PATH), "environments", "v1.12"); io = devnull)

	using Revise
	using PlutoUI
	using SuperconductingCircuitsCore
	using SuperconductingCircuitsVisualizer

	JSON3 = SuperconductingCircuitsCore.JSON3

	figure_config = PlotlyFigureConfig(
		download_filename = splitext(basename(@__FILE__))[1],
		display_width_px = 1200,
		display_height_px = 720,
	)

	wide_figure_cell = WideCell(;
		max_width = max(1000, something(figure_config.display_width_px, 1000) + 80),
	)

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

# ╔═╡ aebc9b82-bfb3-46cb-8935-e7c336643d1e
TableOfContents()

# ╔═╡ 1c35918d-ecaf-49d2-9bc3-33536d597a14
md"""
# Orpen Q2D Intrinsic Purcell Filter Cases

This notebook keeps the intrinsic Purcell-filter topology: two quarter-wave
resonators coupled by one finite MTL window. The only changed source of truth is
the RLGC data:

- uncoupled resonator sections use the selected Orpen single-trace Q2D point;
- the coupled MTL window uses the selected Orpen two-trace Q2D matrix point.

The target observable is the transfer impedance `Z21`, with the same
port-termination compensation used by the existing intrinsic Purcell notebooks.

The matrix basis, Maxwell lowering, and artifact eligibility gates are
canonical in [Multiconductor RLGC Matrices: Basis, Modes, and Physical Meaning](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/transmission-lines/multiconductor-rlgc-matrix-semantics.qmd).
Interpret raw matrices and compensation through [Network Trace Views](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/network-trace-views.qmd),
[Port Reference Impedance Semantics](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/simulation/port-reference-impedance-semantics.qmd),
and [Port-Termination Compensation](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/simulation/port-termination-compensation.qmd).
The current payload and consumer are LC-only even though their names contain
`RLGC`.

This notebook derives PTC resistance from exact compiled port/resistor rows and
declares `intrinsic_pair_probe_scaffold` as the removal intent. The in-memory
check is evidence-backed; persisted traces still need the complete
row/value/removal-intent lineage before promotion.
"""

# ╔═╡ 01ddf92c-8466-4551-b963-14fc3ee9f8c7
begin
	um = 1e-6
	GHz = 1e9
	MHz = 1e6

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
	results_csv_path = joinpath(
		orpen_circuit_output_dir,
		"orpen_intrinsic_purcell_filter_results.csv",
	)

	isfile(case_json_path) || error(
		"Missing Orpen Q2D case JSON. Run scripts/export_orpen_q2d_intrinsic_purcell_cases.py first: " *
		case_json_path,
	)

	case_payload = JSON3.read(read(case_json_path, String), Dict{String,Any})
end

# ╔═╡ 6e1bc506-7348-4ec9-b1ab-a0ada58523b8
begin
	function matrix2(value)
		return Float64[
			Float64(value[1][1]) Float64(value[1][2])
			Float64(value[2][1]) Float64(value[2][2])
		]
	end

	function require_symmetric_2x2(name, matrix)
		isapprox(matrix[1, 2], matrix[2, 1]; atol = 1e-18, rtol = 1e-9) ||
			error("$(name) must be symmetric: $(matrix)")
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
		mtl_c[1, 2] <= 0 || error("MTL Maxwell C[1,2] must be non-positive.")
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
			single_l_per_m_h = Float64(single["l_per_m_h"]),
			single_c_per_m_f = Float64(single["c_per_m_f"]),
			zm_ohm = Float64(mtl["zm_ohm"]),
			zo_effective_ohm = Float64(single["zo_effective_ohm"]),
			zo_diagonal_ohm = Float64(single["zo_diagonal_ohm"]),
			delta_effective_ohm = Float64(record["match"]["delta_effective_ohm"]),
			delta_diagonal_ohm = Float64(record["match"]["delta_diagonal_ohm"]),
		)
	end

	orpen_cases = [make_orpen_case(record) for record in case_payload["cases"]]
end

# ╔═╡ 0e3cf7d6-7d34-4f6c-8bd2-208f78cad2df
begin
	lr_open_um = 2175.68
	lr_short_um = 3147.70
	lp_open_um = 1901.51
	lp_short_um = 3147.70
	lc_um = 204.60

	lr_open_m = lr_open_um * um
	lr_short_m = lr_short_um * um
	lp_open_m = lp_open_um * um
	lp_short_m = lp_short_um * um
	lc_m = lc_um * um

	lr_total_m = lr_open_m + lc_m + lr_short_m
	lp_total_m = lp_open_m + lc_m + lp_short_m
	window_start_r_m = lr_short_m
	window_start_p_m = lp_short_m
	window_length_m = lc_m
	effective_notch_length_m = lr_short_m + lc_m + lp_short_m

	active_coupling_orientation = :same_direction
	section_length_m = 10.0um
	port_resistance_ohm = 50.0

	start_frequency = 1.0GHz
	stop_frequency = 8.0GHz
	point_count = 10001
	frequency_sweep = point_count == 1 ?
		[Float64(start_frequency)] :
		range(Float64(start_frequency), Float64(stop_frequency); length = Int(point_count))

	pump_frequency = 20.0GHz
	pump_current = 0.0
	optional_hb_kwargs = Dict{Symbol,Any}(
		:nbatches => 1,
		:iterations => 160,
		:ftol => 1e-8,
	)

end

# ╔═╡ 0e160e58-e7fb-4674-aeb9-3e407a2c622f
begin
	function quarter_wave_frequency_hz(length_m, l_per_m_h, c_per_m_f)
		return 1 / sqrt(Float64(l_per_m_h) * Float64(c_per_m_f)) / (4 * Float64(length_m))
	end

	function local_minimum_record(frequencies_hz, trace, estimate_hz; search_window_hz = 1.0GHz)
		candidate_indices = findall(
			frequency -> abs(frequency - estimate_hz) <= search_window_hz / 2,
			frequencies_hz,
		)
		isempty(candidate_indices) && (candidate_indices = collect(eachindex(frequencies_hz)))
		local_value, local_position = findmin(abs.(trace[candidate_indices]))
		result_index = candidate_indices[local_position]
		return (
			frequency_GHz = frequencies_hz[result_index] / GHz,
			estimate_GHz = estimate_hz / GHz,
			delta_MHz = (frequencies_hz[result_index] - estimate_hz) / MHz,
			min_abs_value = local_value,
			trace_value = trace[result_index],
			at_sweep_edge = result_index == firstindex(frequencies_hz) ||
				result_index == lastindex(frequencies_hz),
		)
	end

	function run_orpen_q2d_case(case)
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
			start1_m = window_start_r_m,
			start2_m = window_start_p_m,
			length_m = window_length_m,
			section_length_m = section_length_m,
			l_matrix_per_m_h = case.mtl_l_matrix_h_per_m,
			c_matrix_per_m_f = case.mtl_c_matrix_f_per_m,
		)

		circuit_plan = @circuit "orpen-intrinsic-purcell-filter-$(case.id)" begin
			readout_grounded_head = external_node("readout_grounded_head")
			readout_open_tail = external_node("readout_open_tail")
			filter_grounded_head = external_node("filter_grounded_head")
			filter_open_tail = external_node("filter_open_tail")

			readout_resonator = quarter_wave_resonator!(
				id = :readout_resonator,
				grounded_head = readout_grounded_head,
				open_tail = readout_open_tail,
				spec = readout_resonator_spec,
				breakpoints_m = [window_start_r_m, window_start_r_m + window_length_m],
				section_overrides = [coupled_line_section_override(mtl_model, 1)],
			)

			filter_resonator = quarter_wave_resonator!(
				id = :filter_resonator,
				grounded_head = filter_grounded_head,
				open_tail = filter_open_tail,
				spec = filter_resonator_spec,
				breakpoints_m = [window_start_p_m, window_start_p_m + window_length_m],
				section_overrides = [coupled_line_section_override(mtl_model, 2)],
			)

			mtl_window = couple_transmission_window!(
				id = :readout_filter_mtl_window,
				line1 = readout_resonator.line,
				line2 = filter_resonator.line,
				start1 = window_start_r_m,
				start2 = window_start_p_m,
				length = window_length_m,
				model = mtl_model,
				coupling_orientation = active_coupling_orientation,
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
			sparameter(:s12) do
				outputmode = (0,)
				outputport = :readout_open_port
				inputmode = (0,)
				inputport = :filter_open_port
			end
			sparameter(:s22) do
				outputmode = (0,)
				outputport = :filter_open_port
				inputmode = (0,)
				inputport = :filter_open_port
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

		validation_report = validate_hb_intent(circuit_plan)
		compiled_circuit = compile_to_josephson(circuit_plan)
		hb_problem = build_hb_problem(
			compiled_circuit,
			HBRunSpec(
				frequency_sweep = frequency_sweep,
				pump_frequencies = Dict(:pump => Float64(pump_frequency)),
				source_currents = Dict(:pump_in => Float64(pump_current)),
				optional_hb_kwargs = Dict{Symbol,Any}(optional_hb_kwargs),
			),
		)
		output_request_report = validate_output_request_configuration(compiled_circuit, hb_problem)
		result = run_hb_problem(hb_problem)

		raw_y_stack = zero_mode_y_matrix_stack(result; ports = [1, 2])
		ptc_y_stack = apply_port_termination_compensation(
			raw_y_stack,
			compiled_circuit;
			compensate_port_indices = (1, 2),
			removal_intent = :intrinsic_pair_probe_scaffold,
		)
		ptc_z_stack = invert_port_matrix_stack(ptc_y_stack; source_kind = :ptc_z_from_y)

		z21_raw = result.traces[:z_parameter_mode]["om=0|op=2|im=0|ip=1"]
		z21_ptc = vec(ptc_z_stack.values[2, 1, :])
		estimate_hz = quarter_wave_frequency_hz(
			effective_notch_length_m,
			case.single_l_per_m_h,
			case.single_c_per_m_f,
		)

		return (
			case = case,
			circuit_plan = circuit_plan,
			validation_report = validation_report,
			compiled_circuit = compiled_circuit,
			output_request_report = output_request_report,
			result = result,
			s21 = zero_mode_s(result, 2, 1),
			z21_raw = z21_raw,
			z21_ptc = z21_ptc,
			estimate_hz = estimate_hz,
			raw_notch = local_minimum_record(result.frequencies_hz, z21_raw, estimate_hz),
			ptc_notch = local_minimum_record(result.frequencies_hz, z21_ptc, estimate_hz),
		)
	end
end

# ╔═╡ 7f66be82-5a1a-49af-a2ef-0aef2f46a639
case_results = [run_orpen_q2d_case(case) for case in orpen_cases]

# ╔═╡ 7d186996-f860-42a1-9160-97894d235ab0
rlgc_sanity_table = [
	(
		case_id = String(case.id),
		height_um = case.height_um,
		Zo_effective_ohm = case.zo_effective_ohm,
		Zo_diagonal_ohm = case.zo_diagonal_ohm,
		Zm_ohm = case.zm_ohm,
		delta_effective_ohm = case.delta_effective_ohm,
		delta_diagonal_ohm = case.delta_diagonal_ohm,
		single_L_nH_per_m = case.single_l_per_m_h / 1e-9,
		single_C_pF_per_m = case.single_c_per_m_f / 1e-12,
		mtl_C12_pF_per_m = case.mtl_c_matrix_f_per_m[1, 2] / 1e-12,
		mtl_L12_nH_per_m = case.mtl_l_matrix_h_per_m[1, 2] / 1e-9,
	)
	for case in orpen_cases
]

# ╔═╡ 5a095372-dfc8-4f54-908c-6057623a24bf
notch_frequency_table = [
	(
		case_id = String(run.case.id),
		height_um = run.case.height_um,
		estimate_GHz = run.ptc_notch.estimate_GHz,
		z21_ptc_notch_GHz = run.ptc_notch.frequency_GHz,
		z21_ptc_delta_MHz = run.ptc_notch.delta_MHz,
		z21_ptc_min_abs_ohm = run.ptc_notch.min_abs_value,
		z21_ptc_at_sweep_edge = run.ptc_notch.at_sweep_edge,
		z21_raw_notch_GHz = run.raw_notch.frequency_GHz,
		z21_raw_delta_MHz = run.raw_notch.delta_MHz,
		hb_intent_ok = !has_errors(run.validation_report),
		netlist_rows = length(run.compiled_circuit.netlist),
	)
	for run in case_results
]

# ╔═╡ c73ae208-b5c5-4250-8358-dcc6d9ec9127
begin
	mkpath(dirname(results_csv_path))
	open(results_csv_path, "w") do io
		println(io, "case_id,height_um,estimate_GHz,z21_ptc_notch_GHz,z21_ptc_delta_MHz,z21_ptc_min_abs_ohm,z21_raw_notch_GHz,z21_raw_delta_MHz")
		for row in notch_frequency_table
			println(
				io,
				join(
					[
						row.case_id,
						row.height_um,
						row.estimate_GHz,
						row.z21_ptc_notch_GHz,
						row.z21_ptc_delta_MHz,
						row.z21_ptc_min_abs_ohm,
						row.z21_raw_notch_GHz,
						row.z21_raw_delta_MHz,
					],
					",",
				),
			)
		end
	end
	results_csv_path
end

# ╔═╡ c5e58b1f-2ef1-4bff-b209-5f7684b5abb5
begin
	z21_ptc_traces = [
		"$(String(run.case.id)) Z21 PTC" => abs.(run.z21_ptc)
		for run in case_results
	]
	multi_curve_figure(
		first(case_results).result.frequencies_hz,
		z21_ptc_traces;
		title = "Orpen Q2D Intrinsic Purcell Filter: |Z21| PTC",
		yaxis_title = "|Z21| (ohm)",
		y_axis_type = :log,
		config = figure_config,
	)
end |> wide_figure_cell

# ╔═╡ 2ee4f839-aa6a-4770-87a5-1eaf59fdf5fe
begin
	z21_raw_traces = [
		"$(String(run.case.id)) Z21 raw" => abs.(run.z21_raw)
		for run in case_results
	]
	multi_curve_figure(
		first(case_results).result.frequencies_hz,
		z21_raw_traces;
		title = "Orpen Q2D Intrinsic Purcell Filter: |Z21| raw",
		yaxis_title = "|Z21 raw| (ohm)",
		y_axis_type = :log,
		config = figure_config,
	)
end |> wide_figure_cell

# ╔═╡ Cell order:
# ╠═1839a880-dc2b-4d23-91d0-199a12eac724
# ╠═aebc9b82-bfb3-46cb-8935-e7c336643d1e
# ╟─1c35918d-ecaf-49d2-9bc3-33536d597a14
# ╠═01ddf92c-8466-4551-b963-14fc3ee9f8c7
# ╠═6e1bc506-7348-4ec9-b1ab-a0ada58523b8
# ╠═0e3cf7d6-7d34-4f6c-8bd2-208f78cad2df
# ╠═0e160e58-e7fb-4674-aeb9-3e407a2c622f
# ╠═7f66be82-5a1a-49af-a2ef-0aef2f46a639
# ╠═7d186996-f860-42a1-9160-97894d235ab0
# ╠═5a095372-dfc8-4f54-908c-6057623a24bf
# ╠═c73ae208-b5c5-4250-8358-dcc6d9ec9127
# ╠═c5e58b1f-2ef1-4bff-b209-5f7684b5abb5
# ╠═2ee4f839-aa6a-4770-87a5-1eaf59fdf5fe
