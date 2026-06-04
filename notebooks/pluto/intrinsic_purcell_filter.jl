### A Pluto.jl notebook ###
# v1.0.1

using Markdown
using InteractiveUtils

# ╔═╡ 08e970fa-5f21-11f1-ba4c-33ab598452ec
begin
	import Pkg
	Pkg.activate(joinpath(first(DEPOT_PATH), "environments", "v1.12"); io=devnull)

	using Revise
	using PlutoUI
	using SuperconductingCircuitsCore
	using SuperconductingCircuitsVisualizer

	figure_config = PlotlyFigureConfig(
		download_filename=splitext(basename(@__FILE__))[1],
	)

	wide_figure_cell = WideCell(;
		max_width=max(1000, something(figure_config.display_width_px, 1000) + 80),
	)

	if !isdefined(@__MODULE__, :HBExampleHelpers)
		include(joinpath(@__DIR__, "includes", "hb_example_helpers.jl"))
	end

	if !isdefined(@__MODULE__, :PortMatrixPostProcessing)
		include(joinpath(@__DIR__, "includes", "port_matrix_post_processing.jl"))
	end

	zero_mode_s = HBExampleHelpers.zero_mode_s
	zero_mode_y_matrix_stack = PortMatrixPostProcessing.zero_mode_y_matrix_stack
	apply_port_termination_compensation =
		PortMatrixPostProcessing.apply_port_termination_compensation
	invert_port_matrix_stack = PortMatrixPostProcessing.invert_port_matrix_stack
end

# ╔═╡ 8318940f-8044-4a89-bb24-f2d95d2780cc
TableOfContents()

# ╔═╡ 596da8b8-b30d-4bc4-8bd8-574dee543003
md"""
# Intrinsic Purcell Filter: Two MTL-Coupled Quarter-Wave Resonators

This notebook reproduces the distributed-circuit model used in the intrinsic Purcell-filter paper.

The modeled system is:

- one readout quarter-wave resonator,
- one filter quarter-wave resonator,
- one finite MTL coupling window,
- two ports placed at the open ends of the two resonators.

The target observable is the transfer impedance

```math
Z_{21}(\omega)=\frac{V_2(\omega)}{I_1(\omega)}\bigg|_{I_2=0}.
```

The ``Z`` figures below use port-termination compensation (PTC): remove the
solver port shunts in the ``Y`` domain, then invert the compensated ``Y`` matrix
back to ``Z``.
"""

# ╔═╡ e581c849-bf89-45f3-9c31-6c14a4720dee
begin
	# ----------------------------
	# Unit constants
	# ----------------------------
	um = 1e-6
	GHz = 1e9
	MHz = 1e6

	# ----------------------------
	# Paper geometry, Table III, MTL case
	# Define geometry in μm because the paper reports μm.
	# ----------------------------
	lr_open_um = 974.0
	lr_short_um = 1617.0

	lp_open_um = 759.0
	lp_short_um = 1659.0

	lc_um = 318.0
	d_um = 5.5

	# ----------------------------
	# Convert geometry to SI units for JuliaCore
	# ----------------------------
	lr_open_m = lr_open_um * um
	lr_short_m = lr_short_um * um

	lp_open_m = lp_open_um * um
	lp_short_m = lp_short_um * um

	lc_m = lc_um * um
	d_m = d_um * um

	lr_total_m = lr_open_m + lc_m + lr_short_m
	lp_total_m = lp_open_m + lc_m + lp_short_m

	# JuliaCore coordinate:
	# quarter_wave_resonator! builds from grounded_head / shorted end
	# to open_tail / open end.
	window_start_r_m = lr_short_m
	window_start_p_m = lp_short_m
	window_length_m = lc_m

	# ----------------------------
	# Paper transmission-line parameters
	# ----------------------------
	Z0_ohm = 66.0
	v_m_per_s = 1.19e8

	# Uncoupled CPW per-unit-length parameters
	C0_F_per_m = 1 / (Z0_ohm * v_m_per_s)
	L0_H_per_m = Z0_ohm / v_m_per_s

	# Paper mutual MTL capacitance
	Cm_fF_per_mm = 8.5
	Cm_F_per_m = Cm_fF_per_mm * 1e-15 / 1e-3

	# Homogeneous-medium approximation used in the paper
	Lm_H_per_m = Z0_ohm^2 * Cm_F_per_m

	# Matrix form used by circuit model
	C_matrix_F_per_m = [
		C0_F_per_m + Cm_F_per_m   -Cm_F_per_m
		-Cm_F_per_m               C0_F_per_m + Cm_F_per_m
	]

	L_matrix_H_per_m = [
		L0_H_per_m   Lm_H_per_m
		Lm_H_per_m   L0_H_per_m
	]

	# ----------------------------
	# Discretization and HB setup
	# ----------------------------
	section_length_um = 10.0
	section_length_m = section_length_um * um

	port_resistance_ohm = 50.0

	start_frequency_GHz = 7.0
	stop_frequency_GHz = 12.0

	start_frequency = start_frequency_GHz * GHz
	stop_frequency = stop_frequency_GHz * GHz
	point_count = 5001

	pump_frequency_GHz = 20.0
	pump_frequency = pump_frequency_GHz * GHz
	pump_current = 0.0

	optional_hb_kwargs = Dict{Symbol,Any}(
		:nbatches => 1,
		:iterations => 160,
		:ftol => 1e-8,
	)
end

# ╔═╡ 321fa419-de1a-4abf-8844-d566d0819d63
begin
	geometry_check = (
		lr_open_um = lr_open_m / um,
		lr_short_um = lr_short_m / um,
		lp_open_um = lp_open_m / um,
		lp_short_um = lp_short_m / um,
		lc_um = lc_m / um,
		d_um = d_m / um,
		lr_total_um = lr_total_m / um,
		lp_total_um = lp_total_m / um,
		window_start_r_um = window_start_r_m / um,
		window_start_p_um = window_start_p_m / um,
		window_length_um = window_length_m / um,
	)
end

# ╔═╡ 2f9e9c89-e94d-47c6-b487-9c2e38c2878b
begin
	fr_est_Hz = v_m_per_s / (4 * lr_total_m)
	fp_est_Hz = v_m_per_s / (4 * lp_total_m)

	effective_notch_length_m = lr_short_m + lc_m + lp_short_m
	fn_est_Hz = v_m_per_s / (4 * effective_notch_length_m)

	frequency_check = (
		fr_est_GHz = fr_est_Hz / GHz,
		fp_est_GHz = fp_est_Hz / GHz,
		fn_est_GHz = fn_est_Hz / GHz,
		effective_notch_length_um = effective_notch_length_m / um,
	)
end

# ╔═╡ 864bf649-1d5b-408f-a461-fcffad02cf0c
begin
	rlgc_check = (
		C0_pF_per_m = C0_F_per_m / 1e-12,
		L0_nH_per_m = L0_H_per_m / 1e-9,
		Cm_fF_per_mm = Cm_F_per_m * 1e-3 / 1e-15,
		Lm_nH_per_m = Lm_H_per_m / 1e-9,
		Cm_over_C0 = Cm_F_per_m / C0_F_per_m,
	)
end

# ╔═╡ 7faa7031-161a-4560-9539-b29668e60799
begin
	C11 = C_matrix_F_per_m[1, 1]
	C12 = C_matrix_F_per_m[1, 2]

	L11 = L_matrix_H_per_m[1, 1]
	L12 = L_matrix_H_per_m[1, 2]

	Cm_from_matrix_F_per_m = -C12
	Cg_from_matrix_F_per_m = C11 - Cm_from_matrix_F_per_m

	Ls_from_matrix_H_per_m = L11
	Lm_from_matrix_H_per_m = L12

	Ce_F_per_m = Cg_from_matrix_F_per_m
	Le_H_per_m = Ls_from_matrix_H_per_m + Lm_from_matrix_H_per_m

	Co_F_per_m = Cg_from_matrix_F_per_m + 2 * Cm_from_matrix_F_per_m
	Lo_H_per_m = Ls_from_matrix_H_per_m - Lm_from_matrix_H_per_m

	Ze_ohm = sqrt(Le_H_per_m / Ce_F_per_m)
	Zo_ohm = sqrt(Lo_H_per_m / Co_F_per_m)

	ve_m_per_s = 1 / sqrt(Le_H_per_m * Ce_F_per_m)
	vo_m_per_s = 1 / sqrt(Lo_H_per_m * Co_F_per_m)

	mode_check = (
		Ze_ohm = Ze_ohm,
		Zo_ohm = Zo_ohm,
		ve_m_per_s = ve_m_per_s,
		vo_m_per_s = vo_m_per_s,
		ve_over_v = ve_m_per_s / v_m_per_s,
		vo_over_v = vo_m_per_s / v_m_per_s,
	)
end

# ╔═╡ eccc0717-b624-4caa-b794-9d69c5869805
begin
	readout_resonator_spec = RLGCSpec(
		length_m = lr_total_m,
		section_length_m = section_length_m,
		l_per_m_h = L0_H_per_m,
		c_per_m_f = C0_F_per_m,
	)

	filter_resonator_spec = RLGCSpec(
		length_m = lp_total_m,
		section_length_m = section_length_m,
		l_per_m_h = L0_H_per_m,
		c_per_m_f = C0_F_per_m,
	)

	mtl_model = MTLCoupledRLGCSpec(
		start1_m = window_start_r_m,
		start2_m = window_start_p_m,
		length_m = window_length_m,
		section_length_m = section_length_m,
		l_matrix_per_m_h = L_matrix_H_per_m,
		c_matrix_per_m_f = C_matrix_F_per_m,
	)

	readout_section_overrides = [
		coupled_line_section_override(mtl_model, 1),
	]

	filter_section_overrides = [
		coupled_line_section_override(mtl_model, 2),
	]
end

# ╔═╡ 7a301a79-a23a-41d0-9102-79c2a14dde7e
begin
	circuit_plan = @circuit "intrinsic-purcell-filter-two-qwr" begin
		readout_grounded_head = external_node("readout_grounded_head")
		readout_open_tail = external_node("readout_open_tail")

		filter_grounded_head = external_node("filter_grounded_head")
		filter_open_tail = external_node("filter_open_tail")

		readout_resonator = quarter_wave_resonator!(
			id = :readout_resonator,
			grounded_head = readout_grounded_head,
			open_tail = readout_open_tail,
			spec = readout_resonator_spec,
			breakpoints_m = [
				window_start_r_m,
				window_start_r_m + window_length_m,
			],
			section_overrides = readout_section_overrides,
		)

		filter_resonator = quarter_wave_resonator!(
			id = :filter_resonator,
			grounded_head = filter_grounded_head,
			open_tail = filter_open_tail,
			spec = filter_resonator_spec,
			breakpoints_m = [
				window_start_p_m,
				window_start_p_m + window_length_m,
			],
			section_overrides = filter_section_overrides,
		)

		mtl_window = couple_transmission_window!(
			id = :readout_filter_mtl_window,
			line1 = readout_resonator.line,
			line2 = filter_resonator.line,
			start1 = window_start_r_m,
			start2 = window_start_p_m,
			length = window_length_m,
			model = mtl_model,
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

		group(:two_qwr_mtl_system) do
			label = "Two MTL-coupled quarter-wave resonators"
			role = :intrinsic_purcell_filter
			members = [
				:readout_resonator,
				:filter_resonator,
				:readout_filter_mtl_window,
			]
		end

		schematic!(:analysis_view) do
			track(:readout_track) do
				line = readout_resonator.line
				orientation = :left_to_right
				relative_order = :top
				role = :readout_resonator
				label = "readout resonator"
			end

			track(:filter_track) do
				line = filter_resonator.line
				orientation = :left_to_right
				relative_order = :bottom
				role = :filter_resonator
				label = "filter resonator"
			end

			terminal(:readout_open_terminal) do
				endpoint = readout_open_tail
				track = :readout_track
				side = :left
				kind = :port
				label = "1"
			end

			terminal(:filter_open_terminal) do
				endpoint = filter_open_tail
				track = :filter_track
				side = :left
				kind = :port
				label = "2"
			end

			coupled_span(:mtl_span) do
				relation = mtl_window
				track1 = :readout_track
				track2 = :filter_track
				from1 = window_start_r_m
				to1 = window_start_r_m + window_length_m
				from2 = window_start_p_m
				to2 = window_start_p_m + window_length_m
				label = "MTL"
				render = :parallel_cpw_window
			end
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

	circuit_plan
end

# ╔═╡ 76ab9cf8-8229-4376-a3da-419646988f56
hb_validation_report = validate_hb_intent(circuit_plan)

# ╔═╡ 71bf0cb8-dc6f-492c-a42b-1e672f55a6fc
begin
	graph = engineering_graph(circuit_plan)
	layout = schematic_layout_intent(circuit_plan)
	schematic_export = to_schematic_export_spec(circuit_plan)

	graph_summary = (
		components = sort(collect(keys(graph.components)); by=string),
		ports = sort(collect(keys(graph.ports)); by=string),
		groups = sort(collect(keys(graph.groups)); by=string),
		relation_count = length(graph.relations),
	)

	layout_summary = (
		tracks = sort(collect(keys(layout.tracks)); by=string),
		coupled_spans = sort(collect(keys(layout.coupled_spans)); by=string),
		terminals = sort(collect(keys(layout.terminals)); by=string),
	)

	export_summary = (
		components = length(schematic_export.components),
		relations = length(schematic_export.relations),
		ports = length(schematic_export.ports),
		tracks = length(schematic_export.tracks),
		coupled_spans = length(schematic_export.coupled_spans),
	)

	(graph_summary, layout_summary, export_summary)
end

# ╔═╡ ef12de00-fec1-4ef2-b107-9cb4039e5d57
begin
	compiled_circuit = compile_to_josephson(circuit_plan)

	compiled_summary = (
		netlist_rows = length(compiled_circuit.netlist),
		port_ids = sort(collect(keys(compiled_circuit.port_map)); by=string),
		warning_count = length(compiled_circuit.warnings),
	)

	compiled_summary
end

# ╔═╡ 6597ff65-41d6-4e00-9507-e25f828190d4
begin
	frequency_sweep = point_count == 1 ?
		[Float64(start_frequency)] :
		range(Float64(start_frequency), Float64(stop_frequency); length=Int(point_count))

	hb_problem = build_hb_problem(
		compiled_circuit,
		HBRunSpec(
			frequency_sweep = frequency_sweep,
			pump_frequencies = Dict(:pump => Float64(pump_frequency)),
			source_currents = Dict(:pump_in => Float64(pump_current)),
			optional_hb_kwargs = Dict{Symbol,Any}(optional_hb_kwargs),
		),
	)
end

# ╔═╡ 7f2b48f8-3dfe-4150-a016-f999d0fd1cd4
output_request_report = validate_output_request_configuration(compiled_circuit, hb_problem)

# ╔═╡ 39497980-2964-4b8c-b851-c8f35f29cf98
result = run_hb_problem(hb_problem)

# ╔═╡ 3c286442-91f5-4a55-828e-853d12e638fe
begin
	s11 = zero_mode_s(result, 1, 1)
	s21 = zero_mode_s(result, 2, 1)
	s12 = zero_mode_s(result, 1, 2)
	s22 = zero_mode_s(result, 2, 2)
end

# ╔═╡ 90610ecd-62af-4e20-81dd-3ee39407d71e
begin
	z11_raw = result.traces[:z_parameter_mode]["om=0|op=1|im=0|ip=1"]
	z21_raw = result.traces[:z_parameter_mode]["om=0|op=2|im=0|ip=1"]
	z12_raw = result.traces[:z_parameter_mode]["om=0|op=1|im=0|ip=2"]
	z22_raw = result.traces[:z_parameter_mode]["om=0|op=2|im=0|ip=2"]

	raw_z_check = (
		first_z21_raw = z21_raw[1],
		first_abs_z21_raw = abs(z21_raw[1]),
	)
end

# ╔═╡ 9a3b075d-5ef4-43f0-b00a-fba176e9beac
begin
	raw_y_stack = zero_mode_y_matrix_stack(result; ports = [1, 2])

	ptc_resistance_ohm_by_port = Dict(
		1 => port_resistance_ohm,
		2 => port_resistance_ohm,
	)

	ptc_y_stack = apply_port_termination_compensation(
		raw_y_stack;
		resistance_ohm_by_port = ptc_resistance_ohm_by_port,
	)

	ptc_z_stack = invert_port_matrix_stack(ptc_y_stack; source_kind = :ptc_z_from_y)

	z11_ptc = vec(ptc_z_stack.values[1, 1, :])
	z21_ptc = vec(ptc_z_stack.values[2, 1, :])
	z12_ptc = vec(ptc_z_stack.values[1, 2, :])
	z22_ptc = vec(ptc_z_stack.values[2, 2, :])

	ptc_z_check = (
		raw_y_source_kind = raw_y_stack.source_kind,
		ptc_y_source_kind = ptc_y_stack.source_kind,
		ptc_z_source_kind = ptc_z_stack.source_kind,
		first_z21_ptc = z21_ptc[1],
		first_abs_z21_ptc = abs(z21_ptc[1]),
		first_abs_z21_ptc_minus_raw = abs(z21_ptc[1] - z21_raw[1]),
	)
end

# ╔═╡ 02ccd188-03e5-45e9-9aad-0dda54fd0125
begin
	s_parameter_traces = [
		"S11" => s11,
		"S21" => s21,
		"S12" => s12,
		"S22" => s22,
	]

	raw_z_parameter_traces = [
		"Z11" => z11_raw,
		"Z21" => z21_raw,
		"Z12" => z12_raw,
		"Z22" => z22_raw,
	]

	z_parameter_traces = [
		"Z11" => z11_ptc,
		"Z21" => z21_ptc,
		"Z12" => z12_ptc,
		"Z22" => z22_ptc,
	]
end

# ╔═╡ f10eddd4-090c-4c75-92be-f858603e8fd5
begin
	function local_minimum_record(frequencies_hz, trace, estimate_hz; search_window_hz=500.0e6)
		candidate_indices = findall(
			frequency -> abs(frequency - estimate_hz) <= search_window_hz / 2,
			frequencies_hz,
		)

		if isempty(candidate_indices)
			candidate_indices = collect(eachindex(frequencies_hz))
		end

		local_value, local_position = findmin(abs.(trace[candidate_indices]))
		result_index = candidate_indices[local_position]

		return (
			frequency_GHz = frequencies_hz[result_index] / GHz,
			estimate_GHz = estimate_hz / GHz,
			delta_MHz = (frequencies_hz[result_index] - estimate_hz) / MHz,
			min_abs_value = local_value,
			trace_value = trace[result_index],
		)
	end

	z21_raw_notch_record = local_minimum_record(
		result.frequencies_hz,
		z21_raw,
		fn_est_Hz;
		search_window_hz = 1.0 * GHz,
	)

	z21_ptc_notch_record = local_minimum_record(
		result.frequencies_hz,
		z21_ptc,
		fn_est_Hz;
		search_window_hz = 1.0 * GHz,
	)
end

# ╔═╡ 60097318-cb6c-4f77-8262-06cf3bdb73db
begin
	sanity = (
		point_count_matches = length(result.frequencies_hz) == point_count,
		has_one_coupled_span = length(layout.coupled_spans) == 1,
		finite_s21 = all(isfinite, real.(s21)) && all(isfinite, imag.(s21)),
		finite_z21_raw = all(isfinite, real.(z21_raw)) && all(isfinite, imag.(z21_raw)),
		finite_z21_ptc = all(isfinite, real.(z21_ptc)) && all(isfinite, imag.(z21_ptc)),
		hb_intent_ok = !has_errors(hb_validation_report),
		raw_y_source_kind = raw_y_stack.source_kind,
		ptc_y_source_kind = ptc_y_stack.source_kind,
		ptc_z_source_kind = ptc_z_stack.source_kind,
		z21_raw_notch_GHz = z21_raw_notch_record.frequency_GHz,
		z21_raw_notch_delta_MHz = z21_raw_notch_record.delta_MHz,
		z21_ptc_notch_GHz = z21_ptc_notch_record.frequency_GHz,
		z21_ptc_notch_delta_MHz = z21_ptc_notch_record.delta_MHz,
		max_abs_raw_z_reciprocity_error_ohm = maximum(abs.(z21_raw .- z12_raw)),
		max_abs_ptc_z_reciprocity_error_ohm = maximum(abs.(z21_ptc .- z12_ptc)),
		max_abs_z21_ptc_raw_difference_ohm = maximum(abs.(z21_ptc .- z21_raw)),
		max_abs_raw_z_real_part_ohm = maximum(
			abs.(vcat(real.(z11_raw), real.(z21_raw), real.(z12_raw), real.(z22_raw))),
		),
		max_abs_ptc_z_real_part_ohm = maximum(
			abs.(vcat(real.(z11_ptc), real.(z21_ptc), real.(z12_ptc), real.(z22_ptc))),
		),
	)

	sanity
end

# ╔═╡ 9f48c85f-39f1-4465-b2a5-f3f03099c18c
begin
	s_parameter_db_magnitude_figure(
		result.frequencies_hz,
		s_parameter_traces;
		title = "Two MTL-Coupled QWRs: S-parameter Magnitude (dB)",
		config = figure_config,
	)
end |> wide_figure_cell

# ╔═╡ 68ebcd1d-3a0b-4a00-8135-e3475038c791
begin
	s_parameter_abs_magnitude_figure(
		result.frequencies_hz,
		s_parameter_traces;
		title = "Two MTL-Coupled QWRs: S-parameter Magnitude",
		config = figure_config,
	)
end |> wide_figure_cell

# ╔═╡ 0cd19fe1-ec0b-48b7-83d4-76ad3eeb33be
begin
	z_parameter_imaginary_figure(
		result.frequencies_hz,
		z_parameter_traces;
		title = "Imaginary Part of PTC Impedance Matrix",
		config = figure_config,
	)
end |> wide_figure_cell

# ╔═╡ f97e3df9-be39-4d07-99f7-6e8c392a0e7c
begin
	z_parameter_real_figure(
		result.frequencies_hz,
		z_parameter_traces;
		title = "Real Part of PTC Impedance Matrix",
		config = figure_config,
	)
end |> wide_figure_cell

# ╔═╡ 7a11e8ad-46a9-4c08-9cfb-c2ecebe77b85
begin
	z_parameter_abs_imaginary_figure(
		result.frequencies_hz,
		z_parameter_traces;
		title = "Absolute Imaginary Part of PTC Impedance Matrix",
		config = figure_config,
		y_axis_type = :log,
	)
end |> wide_figure_cell

# ╔═╡ 77ac6cb3-fa20-49ae-bfcf-822846c08546
trace_families = sort(collect(keys(result.traces)); by=string)

# ╔═╡ Cell order:
# ╠═08e970fa-5f21-11f1-ba4c-33ab598452ec
# ╠═8318940f-8044-4a89-bb24-f2d95d2780cc
# ╠═596da8b8-b30d-4bc4-8bd8-574dee543003
# ╠═e581c849-bf89-45f3-9c31-6c14a4720dee
# ╠═321fa419-de1a-4abf-8844-d566d0819d63
# ╠═2f9e9c89-e94d-47c6-b487-9c2e38c2878b
# ╠═864bf649-1d5b-408f-a461-fcffad02cf0c
# ╠═7faa7031-161a-4560-9539-b29668e60799
# ╠═eccc0717-b624-4caa-b794-9d69c5869805
# ╠═7a301a79-a23a-41d0-9102-79c2a14dde7e
# ╠═76ab9cf8-8229-4376-a3da-419646988f56
# ╠═71bf0cb8-dc6f-492c-a42b-1e672f55a6fc
# ╠═ef12de00-fec1-4ef2-b107-9cb4039e5d57
# ╠═6597ff65-41d6-4e00-9507-e25f828190d4
# ╠═7f2b48f8-3dfe-4150-a016-f999d0fd1cd4
# ╠═39497980-2964-4b8c-b851-c8f35f29cf98
# ╠═3c286442-91f5-4a55-828e-853d12e638fe
# ╠═90610ecd-62af-4e20-81dd-3ee39407d71e
# ╠═9a3b075d-5ef4-43f0-b00a-fba176e9beac
# ╠═02ccd188-03e5-45e9-9aad-0dda54fd0125
# ╠═f10eddd4-090c-4c75-92be-f858603e8fd5
# ╠═60097318-cb6c-4f77-8262-06cf3bdb73db
# ╠═9f48c85f-39f1-4465-b2a5-f3f03099c18c
# ╠═68ebcd1d-3a0b-4a00-8135-e3475038c791
# ╠═0cd19fe1-ec0b-48b7-83d4-76ad3eeb33be
# ╠═f97e3df9-be39-4d07-99f7-6e8c392a0e7c
# ╠═7a11e8ad-46a9-4c08-9cfb-c2ecebe77b85
# ╠═77ac6cb3-fa20-49ae-bfcf-822846c08546
