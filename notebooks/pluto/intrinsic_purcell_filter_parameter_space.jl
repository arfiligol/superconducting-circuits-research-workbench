### A Pluto.jl notebook ###
# v1.0.1

#> [frontmatter]
#> title = "Intrinsic Purcell Filter Parameter Space"
#> tags = ["julia-core", "pluto", "hb", "mtl", "purcell-filter", "parameter-space"]
#> description = "Baseline-anchored parameter-space sweep for two MTL-coupled quarter-wave resonators."

using Markdown
using InteractiveUtils

# ╔═╡ 24b8451e-2520-4c52-8f53-0e7219c2fdc4
begin
	import Pkg
	Pkg.activate(joinpath(first(DEPOT_PATH), "environments", "v1.12"); io=devnull)

	using Revise
	using PlutoUI
	using SuperconductingCircuitsCore
	using SuperconductingCircuitsAnalysisBridge
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

# ╔═╡ 06a726e7-120a-464b-a8dd-98a266e4ad3b
TableOfContents()

# ╔═╡ 785f11a6-a134-4cb7-9908-07dff8c8d1bc
analysis_bridge_status()

# ╔═╡ 5f45a2e2-4116-4875-a3fa-b65540cce0c9
md"""
# Intrinsic Purcell Filter Parameter Space

This notebook starts from a fixed layout baseline, marks that baseline in every parameter-space view, and then expands a local sweep around it.

The baseline is not just another sweep point. It is the reference design that already has layout work and similar simulation evidence behind it. Every candidate table therefore reports both its absolute value and its offset from the baseline.
"""

# ╔═╡ 4aa7cd1c-7dec-4ff8-a035-ed7100aeb2cb
begin
	um = 1e-6
	GHz = 1e9
	MHz = 1e6

	baseline_geometry = (
		lr_open_um = 2175.68,
		lp_open_um = 1901.51,
		lr_short_um = 3147.70,
		lp_short_um = 3147.70,
		lc_um = 204.60,
	)

	# Baseline per-unit-length values are embedded so this circuit-side sweep can
	# run before a Q2D export parser exists.
	baseline_rlgc = (
		l_per_m_h = 422.4791148287280e-9,
		c_per_m_f = (159.1481563210610 - 17.37485333418115) * 1e-12,
		l11_per_m_h = 422.4791148287280e-9,
		l22_per_m_h = 422.4824895169048e-9,
		l12_per_m_h = 203.3775930974167e-9,
		c11_per_m_f = 159.1481563210610e-12,
		c22_per_m_f = 159.1405028743178e-12,
		c12_mutual_per_m_f = 17.37485333418115e-12,
		r_per_m_ohm = 0.0,
		g_per_m_s = 0.0,
	)

	target_bands = (
		readout_center_ghz = 6.0,
		readout_lower_ghz = 5.5,
		readout_upper_ghz = 6.5,
		qubit_center_ghz = 4.5,
		qubit_lower_ghz = 4.0,
		qubit_upper_ghz = 5.0,
		filter_reference_ghz = 6.0,
	)
end

# ╔═╡ 879686f7-254e-4d68-9cb8-f62691cc4656
begin
	analytic_candidate_limit = 64
	coarse_candidate_count = 6
	fine_candidate_count = 4

	run_coarse_hb = false
	run_fine_hb = false

	coarse_start_frequency = 3.8GHz
	coarse_stop_frequency = 6.8GHz
	coarse_point_count = 1201

	fine_frequency_step = 0.5MHz
	fine_window_half_width = 0.35GHz

	coarse_section_length_m = 20.0um
	fine_section_length_m = 10.0um
	port_resistance_ohm = 50.0
	s21_vector_resonator_count = 2
	s21_vector_bg_poles = 2
	s21_vector_min_q = 2.0

	pump_frequency = 14.0GHz
	pump_current = 0.0
	optional_hb_kwargs = Dict{Symbol,Any}(
		:nbatches => 1,
		:iterations => 160,
		:ftol => 1e-8,
	)
end

# ╔═╡ 54f401d4-6996-426a-bfdd-bae83199b662
begin
	readout_target_grid_ghz = [5.5, 5.75, 6.0, 6.25, 6.5]
	filter_target_grid_ghz = [5.5, 6.0, 6.5]
	lc_grid_um = sort(unique([150.0, 175.0, 200.0, baseline_geometry.lc_um, 225.0, 250.0, 260.0]))
	self_lc_scale_grid = [0.95, 1.0, 1.05]
	mutual_lc_scale_grid = [0.70, 1.0, 1.30]
end

# ╔═╡ 22b7d387-2e2b-4bb2-a894-3068ce7b45c0
md"""
## Baseline Anchor

The sweep is local to the baseline layout. A candidate is scored by readout-band placement, qubit-band ``Z_{21}`` suppression, and distance from the baseline geometry / RLGC scaling.

Q2D layout exports are intentionally not required in this first notebook. They should be used later to map the accepted RLGC region back to cross-section layout parameters.
"""

# ╔═╡ 53ec427d-11a6-41a0-b33d-98ff358a2fb9
begin
	function phase_velocity_m_per_s(l_per_m_h, c_per_m_f)
		return 1 / sqrt(Float64(l_per_m_h) * Float64(c_per_m_f))
	end

	function quarter_wave_frequency_ghz(length_um, l_per_m_h, c_per_m_f)
		return phase_velocity_m_per_s(l_per_m_h, c_per_m_f) / (4 * Float64(length_um) * um) / GHz
	end

	function quarter_wave_length_um(frequency_ghz, l_per_m_h, c_per_m_f)
		return phase_velocity_m_per_s(l_per_m_h, c_per_m_f) / (4 * Float64(frequency_ghz) * GHz) / um
	end

	function band_error_ghz(value, lower, upper)
		value < lower && return lower - value
		value > upper && return value - upper
		return 0.0
	end

	function matrix_positive_definite_2x2(a, b, d)
		return a > 0 && d > 0 && a * d - b^2 > 0
	end

	function baseline_distance(
		geometry;
		baseline_geometry,
		self_lc_scale,
		mutual_lc_scale,
	)
		lr_total_um = geometry.lr_open_um + geometry.lc_um + geometry.lr_short_um
		lp_total_um = geometry.lp_open_um + geometry.lc_um + geometry.lp_short_um
		baseline_lr_total_um =
			baseline_geometry.lr_open_um + baseline_geometry.lc_um + baseline_geometry.lr_short_um
		baseline_lp_total_um =
			baseline_geometry.lp_open_um + baseline_geometry.lc_um + baseline_geometry.lp_short_um

		return sqrt(
			((lr_total_um - baseline_lr_total_um) / 250.0)^2 +
			((lp_total_um - baseline_lp_total_um) / 250.0)^2 +
			((geometry.lc_um - baseline_geometry.lc_um) / 50.0)^2 +
			((self_lc_scale - 1.0) / 0.05)^2 +
			((mutual_lc_scale - 1.0) / 0.30)^2
		)
	end

	function analytic_score(
		;
		readout_estimate_ghz,
		filter_estimate_ghz,
		notch_estimate_ghz,
		distance_from_baseline,
		target_bands,
	)
		readout_penalty =
			band_error_ghz(readout_estimate_ghz, target_bands.readout_lower_ghz, target_bands.readout_upper_ghz) / 0.5
		notch_penalty = abs(notch_estimate_ghz - target_bands.qubit_center_ghz) / 0.5
		filter_penalty = 0.15 * abs(filter_estimate_ghz - target_bands.filter_reference_ghz) / 0.5
		baseline_penalty = 0.03 * distance_from_baseline
		return readout_penalty + notch_penalty + filter_penalty + baseline_penalty
	end
end

# ╔═╡ 73455c10-a4f5-4709-84b8-d31597293ead
begin
	function make_design(
		;
		id,
		label,
		origin,
		is_baseline,
		lr_open_um,
		lp_open_um,
		lr_short_um,
		lp_short_um,
		lc_um,
		self_lc_scale,
		mutual_lc_scale,
		baseline_geometry,
		baseline_rlgc,
		target_bands,
	)
		geometry = (
			lr_open_um = Float64(lr_open_um),
			lp_open_um = Float64(lp_open_um),
			lr_short_um = Float64(lr_short_um),
			lp_short_um = Float64(lp_short_um),
			lc_um = Float64(lc_um),
		)

		l_per_m_h = baseline_rlgc.l_per_m_h * Float64(self_lc_scale)
		c_per_m_f = baseline_rlgc.c_per_m_f * Float64(self_lc_scale)
		l11_per_m_h = baseline_rlgc.l11_per_m_h * Float64(self_lc_scale)
		l22_per_m_h = baseline_rlgc.l22_per_m_h * Float64(self_lc_scale)
		l12_per_m_h = baseline_rlgc.l12_per_m_h * Float64(mutual_lc_scale)
		c11_per_m_f = baseline_rlgc.c11_per_m_f * Float64(self_lc_scale)
		c22_per_m_f = baseline_rlgc.c22_per_m_f * Float64(self_lc_scale)
		c12_mutual_per_m_f = baseline_rlgc.c12_mutual_per_m_f * Float64(mutual_lc_scale)

		lr_total_um = geometry.lr_open_um + geometry.lc_um + geometry.lr_short_um
		lp_total_um = geometry.lp_open_um + geometry.lc_um + geometry.lp_short_um
		effective_notch_length_um = geometry.lr_short_um + geometry.lc_um + geometry.lp_short_um

		readout_estimate_ghz = quarter_wave_frequency_ghz(lr_total_um, l_per_m_h, c_per_m_f)
		filter_estimate_ghz = quarter_wave_frequency_ghz(lp_total_um, l_per_m_h, c_per_m_f)
		notch_estimate_ghz = quarter_wave_frequency_ghz(effective_notch_length_um, l_per_m_h, c_per_m_f)

		distance = baseline_distance(
			geometry;
			baseline_geometry = baseline_geometry,
			self_lc_scale = self_lc_scale,
			mutual_lc_scale = mutual_lc_scale,
		)
		score = analytic_score(
			readout_estimate_ghz = readout_estimate_ghz,
			filter_estimate_ghz = filter_estimate_ghz,
			notch_estimate_ghz = notch_estimate_ghz,
			distance_from_baseline = distance,
			target_bands = target_bands,
		)

		return (
			id = Symbol(id),
			label = String(label),
			origin = Symbol(origin),
			is_baseline = Bool(is_baseline),
			lr_open_um = geometry.lr_open_um,
			lp_open_um = geometry.lp_open_um,
			lr_short_um = geometry.lr_short_um,
			lp_short_um = geometry.lp_short_um,
			lc_um = geometry.lc_um,
			lr_total_um = lr_total_um,
			lp_total_um = lp_total_um,
			effective_notch_length_um = effective_notch_length_um,
			self_lc_scale = Float64(self_lc_scale),
			mutual_lc_scale = Float64(mutual_lc_scale),
			l_per_m_h = l_per_m_h,
			c_per_m_f = c_per_m_f,
			l11_per_m_h = l11_per_m_h,
			l22_per_m_h = l22_per_m_h,
			l12_per_m_h = l12_per_m_h,
			c11_per_m_f = c11_per_m_f,
			c22_per_m_f = c22_per_m_f,
			c12_mutual_per_m_f = c12_mutual_per_m_f,
			readout_estimate_ghz = readout_estimate_ghz,
			filter_estimate_ghz = filter_estimate_ghz,
			notch_estimate_ghz = notch_estimate_ghz,
			distance_from_baseline = distance,
			analytic_score = score,
			delta_lr_total_um = lr_total_um -
				(baseline_geometry.lr_open_um + baseline_geometry.lc_um + baseline_geometry.lr_short_um),
			delta_lp_total_um = lp_total_um -
				(baseline_geometry.lp_open_um + baseline_geometry.lc_um + baseline_geometry.lp_short_um),
			delta_lc_um = geometry.lc_um - baseline_geometry.lc_um,
			delta_self_lc_scale = Float64(self_lc_scale) - 1.0,
			delta_mutual_lc_scale = Float64(mutual_lc_scale) - 1.0,
		)
	end

	function valid_design(design)
		lengths_ok = all(
			value -> value >= 300.0,
			[
				design.lr_open_um,
				design.lp_open_um,
				design.lr_short_um,
				design.lp_short_um,
			],
		)
		window_ok = 100.0 <= design.lc_um <= 320.0
		total_ok = 3500.0 <= design.lr_total_um <= 8000.0 &&
			3500.0 <= design.lp_total_um <= 8000.0
		l_ok = matrix_positive_definite_2x2(
			design.l11_per_m_h,
			design.l12_per_m_h,
			design.l22_per_m_h,
		)
		c_ok = matrix_positive_definite_2x2(
			design.c11_per_m_f,
			-design.c12_mutual_per_m_f,
			design.c22_per_m_f,
		)
		return lengths_ok && window_ok && total_ok && l_ok && c_ok
	end
end

# ╔═╡ c3e963b6-29a8-4614-a263-d4d303c4afc5
baseline_design = make_design(
	id = :baseline_layout_spec,
	label = "Baseline layout spec",
	origin = :baseline,
	is_baseline = true,
	lr_open_um = baseline_geometry.lr_open_um,
	lp_open_um = baseline_geometry.lp_open_um,
	lr_short_um = baseline_geometry.lr_short_um,
	lp_short_um = baseline_geometry.lp_short_um,
	lc_um = baseline_geometry.lc_um,
	self_lc_scale = 1.0,
	mutual_lc_scale = 1.0,
	baseline_geometry = baseline_geometry,
	baseline_rlgc = baseline_rlgc,
	target_bands = target_bands,
)

# ╔═╡ c0f28c24-4140-4674-856a-0b0db167a340
baseline_summary = [
	(
		label = baseline_design.label,
		lr_total_um = baseline_design.lr_total_um,
		lp_total_um = baseline_design.lp_total_um,
		lc_um = baseline_design.lc_um,
		readout_estimate_ghz = baseline_design.readout_estimate_ghz,
		filter_estimate_ghz = baseline_design.filter_estimate_ghz,
		notch_estimate_ghz = baseline_design.notch_estimate_ghz,
		distance_from_baseline = baseline_design.distance_from_baseline,
		analytic_score = baseline_design.analytic_score,
	)
]

# ╔═╡ 1c0d87a0-d2e1-4e2b-af06-1f1790f81f9f
begin
	function design_signature(design)
		return (
			round(design.lr_open_um; digits = 2),
			round(design.lp_open_um; digits = 2),
			round(design.lr_short_um; digits = 2),
			round(design.lp_short_um; digits = 2),
			round(design.lc_um; digits = 2),
			round(design.self_lc_scale; digits = 4),
			round(design.mutual_lc_scale; digits = 4),
		)
	end

	function unique_designs(designs)
		seen = Set{Any}()
		output = Any[]
		for design in designs
			signature = design_signature(design)
			signature in seen && continue
			push!(seen, signature)
			push!(output, design)
		end
		return output
	end

	function first_n(values, count)
		return values[1:min(Int(count), length(values))]
	end

	function generate_baseline_local_candidates(
		;
		baseline_design,
		baseline_geometry,
		baseline_rlgc,
		target_bands,
		readout_target_grid_ghz,
		filter_target_grid_ghz,
		lc_grid_um,
		self_lc_scale_grid,
		mutual_lc_scale_grid,
	)
		lr_open_fraction =
			baseline_geometry.lr_open_um / (baseline_geometry.lr_open_um + baseline_geometry.lr_short_um)
		lp_open_fraction =
			baseline_geometry.lp_open_um / (baseline_geometry.lp_open_um + baseline_geometry.lp_short_um)

		candidates = Any[]
		candidate_index = 0

		for self_lc_scale in self_lc_scale_grid
			l_per_m_h = baseline_rlgc.l_per_m_h * self_lc_scale
			c_per_m_f = baseline_rlgc.c_per_m_f * self_lc_scale
			for readout_target_ghz in readout_target_grid_ghz
				readout_total_um =
					quarter_wave_length_um(readout_target_ghz, l_per_m_h, c_per_m_f)
				for filter_target_ghz in filter_target_grid_ghz
					filter_total_um =
						quarter_wave_length_um(filter_target_ghz, l_per_m_h, c_per_m_f)
					for lc_um in lc_grid_um
						readout_body_um = readout_total_um - lc_um
						filter_body_um = filter_total_um - lc_um
						readout_body_um <= 0 && continue
						filter_body_um <= 0 && continue

						for mutual_lc_scale in mutual_lc_scale_grid
							candidate_index += 1
							design = make_design(
								id = Symbol("candidate_", candidate_index),
								label = "candidate $(candidate_index)",
								origin = :analytic_grid,
								is_baseline = false,
								lr_open_um = readout_body_um * lr_open_fraction,
								lr_short_um = readout_body_um * (1 - lr_open_fraction),
								lp_open_um = filter_body_um * lp_open_fraction,
								lp_short_um = filter_body_um * (1 - lp_open_fraction),
								lc_um = lc_um,
								self_lc_scale = self_lc_scale,
								mutual_lc_scale = mutual_lc_scale,
								baseline_geometry = baseline_geometry,
								baseline_rlgc = baseline_rlgc,
								target_bands = target_bands,
							)
							valid_design(design) && push!(candidates, design)
						end
					end
				end
			end
		end

		sorted_candidates = sort(unique_designs(candidates); by = design -> design.analytic_score)
		return unique_designs([baseline_design; sorted_candidates])
	end
end

# ╔═╡ 65d2f640-c0ce-40e4-932d-637a91c1ee14
candidate_designs = first_n(
	generate_baseline_local_candidates(
		baseline_design = baseline_design,
		baseline_geometry = baseline_geometry,
		baseline_rlgc = baseline_rlgc,
		target_bands = target_bands,
		readout_target_grid_ghz = readout_target_grid_ghz,
		filter_target_grid_ghz = filter_target_grid_ghz,
		lc_grid_um = lc_grid_um,
		self_lc_scale_grid = self_lc_scale_grid,
		mutual_lc_scale_grid = mutual_lc_scale_grid,
	),
	analytic_candidate_limit,
)

# ╔═╡ 980db74a-5908-4146-87be-49b5729941cb
analytic_candidate_table = [
	(
		id = design.id,
		label = design.label,
		is_baseline = design.is_baseline,
		lr_total_um = design.lr_total_um,
		lp_total_um = design.lp_total_um,
		lc_um = design.lc_um,
		self_lc_scale = design.self_lc_scale,
		mutual_lc_scale = design.mutual_lc_scale,
		readout_estimate_ghz = design.readout_estimate_ghz,
		filter_estimate_ghz = design.filter_estimate_ghz,
		notch_estimate_ghz = design.notch_estimate_ghz,
		delta_lr_total_um = design.delta_lr_total_um,
		delta_lp_total_um = design.delta_lp_total_um,
		delta_lc_um = design.delta_lc_um,
		distance_from_baseline = design.distance_from_baseline,
		analytic_score = design.analytic_score,
	)
	for design in candidate_designs
]

# ╔═╡ 8de17e51-5839-49a6-9217-e8ad3ab2fc88
begin
	function design_l_matrix_per_m_h(design)
		return [
			design.l11_per_m_h design.l12_per_m_h
			design.l12_per_m_h design.l22_per_m_h
		]
	end

	function design_c_matrix_per_m_f(design)
		return [
			design.c11_per_m_f -design.c12_mutual_per_m_f
			-design.c12_mutual_per_m_f design.c22_per_m_f
		]
	end

	function build_two_qwr_mtl_plan(design; section_length_m, port_resistance_ohm)
		lr_total_m = design.lr_total_um * um
		lp_total_m = design.lp_total_um * um
		lr_short_m = design.lr_short_um * um
		lp_short_m = design.lp_short_um * um
		lc_m = design.lc_um * um

		readout_resonator_spec = RLGCSpec(
			length_m = lr_total_m,
			section_length_m = section_length_m,
			l_per_m_h = design.l_per_m_h,
			c_per_m_f = design.c_per_m_f,
		)

		filter_resonator_spec = RLGCSpec(
			length_m = lp_total_m,
			section_length_m = section_length_m,
			l_per_m_h = design.l_per_m_h,
			c_per_m_f = design.c_per_m_f,
		)

		mtl_model = MTLCoupledRLGCSpec(
			start1_m = lr_short_m,
			start2_m = lp_short_m,
			length_m = lc_m,
			section_length_m = section_length_m,
			l_matrix_per_m_h = design_l_matrix_per_m_h(design),
			c_matrix_per_m_f = design_c_matrix_per_m_f(design),
		)

		readout_section_overrides = [coupled_line_section_override(mtl_model, 1)]
		filter_section_overrides = [coupled_line_section_override(mtl_model, 2)]

		circuit_plan = @circuit "intrinsic-purcell-filter-parameter-space" begin
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
				section_overrides = readout_section_overrides,
			)

			filter_resonator = quarter_wave_resonator!(
				id = :filter_resonator,
				grounded_head = filter_grounded_head,
				open_tail = filter_open_tail,
				spec = filter_resonator_spec,
				breakpoints_m = [lp_short_m, lp_short_m + lc_m],
				section_overrides = filter_section_overrides,
			)

			mtl_window = couple_transmission_window!(
				id = :readout_filter_mtl_window,
				line1 = readout_resonator.line,
				line2 = filter_resonator.line,
				start1 = lr_short_m,
				start2 = lp_short_m,
				length = lc_m,
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

			group(:baseline_anchored_parameter_space) do
				label = design.label
				role = :intrinsic_purcell_filter_parameter_space
				members = [
					:readout_resonator,
					:filter_resonator,
					:readout_filter_mtl_window,
				]
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
				keyedarrays = false
			end
		end

		return circuit_plan
	end
end

# ╔═╡ 8edab22b-a6fb-464f-8f4b-7ac9f4fb03f8
begin
	function frequency_range(start_frequency, stop_frequency, point_count)
		point_count == 1 && return [Float64(start_frequency)]
		return collect(range(Float64(start_frequency), Float64(stop_frequency); length = Int(point_count)))
	end

	coarse_frequencies_hz = frequency_range(
		coarse_start_frequency,
		coarse_stop_frequency,
		coarse_point_count,
	)

	fine_frequencies_hz = sort(unique(vcat(
		collect(range(
			(target_bands.qubit_center_ghz * GHz - fine_window_half_width),
			(target_bands.qubit_center_ghz * GHz + fine_window_half_width);
			step = fine_frequency_step,
		)),
		collect(range(
			(target_bands.readout_center_ghz * GHz - fine_window_half_width),
			(target_bands.readout_center_ghz * GHz + fine_window_half_width);
			step = fine_frequency_step,
		)),
	)))
end

# ╔═╡ cd0908ae-8c3f-4412-810a-871601006fbb
begin
	function candidate_indices(frequencies_hz, center_hz; search_window_hz)
		indices = findall(
			frequency -> abs(frequency - center_hz) <= search_window_hz / 2,
			frequencies_hz,
		)
		isempty(indices) && return collect(eachindex(frequencies_hz))
		return indices
	end

	function local_peak_record(frequencies_hz, trace, center_hz; search_window_hz)
		indices = candidate_indices(frequencies_hz, center_hz; search_window_hz = search_window_hz)
		local_value, local_position = findmax(abs.(trace[indices]))
		result_index = indices[local_position]
		return (
			index = result_index,
			frequency_hz = frequencies_hz[result_index],
			frequency_ghz = frequencies_hz[result_index] / GHz,
			abs_value = local_value,
			trace_value = trace[result_index],
		)
	end

	function local_minimum_record(frequencies_hz, trace, center_hz; search_window_hz)
		indices = candidate_indices(frequencies_hz, center_hz; search_window_hz = search_window_hz)
		local_value, local_position = findmin(abs.(trace[indices]))
		result_index = indices[local_position]
		return (
			index = result_index,
			frequency_hz = frequencies_hz[result_index],
			frequency_ghz = frequencies_hz[result_index] / GHz,
			abs_value = local_value,
			trace_value = trace[result_index],
		)
	end

	function nearest_abs_record(frequencies_hz, trace, target_hz)
		_, result_index = findmin(abs.(frequencies_hz .- target_hz))
		return (
			index = result_index,
			frequency_hz = frequencies_hz[result_index],
			frequency_ghz = frequencies_hz[result_index] / GHz,
			abs_value = abs(trace[result_index]),
			trace_value = trace[result_index],
		)
	end

	function ptc_z_traces(result; port_resistance_ohm)
		raw_y_stack = zero_mode_y_matrix_stack(result; ports = [1, 2])
		ptc_y_stack = apply_port_termination_compensation(
			raw_y_stack;
			resistance_ohm_by_port = Dict(1 => port_resistance_ohm, 2 => port_resistance_ohm),
		)
		ptc_z_stack = invert_port_matrix_stack(ptc_y_stack; source_kind = :ptc_z_from_y)

		return (
			z11 = vec(ptc_z_stack.values[1, 1, :]),
			z21 = vec(ptc_z_stack.values[2, 1, :]),
			z12 = vec(ptc_z_stack.values[1, 2, :]),
			z22 = vec(ptc_z_stack.values[2, 2, :]),
			raw_y_source_kind = raw_y_stack.source_kind,
			ptc_z_source_kind = ptc_z_stack.source_kind,
		)
	end
end

# ╔═╡ 2d855015-c69e-4466-8f09-0408962c2987
begin
	function simulate_design_metrics(
		compiled_circuit,
		design,
		frequencies_hz;
		target_bands,
		port_resistance_ohm,
		pump_frequency,
		pump_current,
		optional_hb_kwargs,
		s21_vector_resonator_count,
		s21_vector_bg_poles,
		s21_vector_min_q,
	)
		hb_problem = build_hb_problem(
			compiled_circuit,
			HBRunSpec(
				frequency_sweep = frequencies_hz,
				pump_frequencies = Dict(:pump => Float64(pump_frequency)),
				source_currents = Dict(:pump_in => Float64(pump_current)),
				optional_hb_kwargs = Dict{Symbol,Any}(optional_hb_kwargs),
			),
		)
		result = run_hb_problem(hb_problem)
		s21 = zero_mode_s(result, 2, 1)
		s21_vector_fit = fit_vector_s21(
			result.frequencies_hz,
			s21;
			n_resonators = s21_vector_resonator_count,
			bg_poles = s21_vector_bg_poles,
			min_q = s21_vector_min_q,
		)
		z_traces = ptc_z_traces(result; port_resistance_ohm = port_resistance_ohm)

		readout_peak = local_peak_record(
			result.frequencies_hz,
			z_traces.z11,
			design.readout_estimate_ghz * GHz;
			search_window_hz = 900MHz,
		)
		filter_peak = local_peak_record(
			result.frequencies_hz,
			z_traces.z22,
			design.filter_estimate_ghz * GHz;
			search_window_hz = 900MHz,
		)
		qubit_notch = local_minimum_record(
			result.frequencies_hz,
			z_traces.z21,
			target_bands.qubit_center_ghz * GHz;
			search_window_hz = 1.0GHz,
		)
		readout_transfer = nearest_abs_record(
			result.frequencies_hz,
			z_traces.z21,
			readout_peak.frequency_hz,
		)

		ratio_db = 20 * log10(
			max(readout_transfer.abs_value, eps(Float64)) /
			max(qubit_notch.abs_value, eps(Float64)),
		)
		readout_error_mhz =
			(readout_peak.frequency_ghz - target_bands.readout_center_ghz) * 1000
		qubit_notch_error_mhz =
			(qubit_notch.frequency_ghz - target_bands.qubit_center_ghz) * 1000
		simulation_score =
			abs(readout_error_mhz) / 500 +
			abs(qubit_notch_error_mhz) / 500 +
			0.15 * max(0.0, 12.0 - ratio_db) / 12.0 +
			0.03 * design.distance_from_baseline

		return (
			readout_peak_ghz = readout_peak.frequency_ghz,
			filter_peak_ghz = filter_peak.frequency_ghz,
			qubit_notch_ghz = qubit_notch.frequency_ghz,
			readout_error_mhz = readout_error_mhz,
			qubit_notch_error_mhz = qubit_notch_error_mhz,
			z21_readout_abs_ohm = readout_transfer.abs_value,
			z21_qubit_notch_abs_ohm = qubit_notch.abs_value,
			z21_readout_to_notch_ratio_db = ratio_db,
			readout_peak_in_band = target_bands.readout_lower_ghz <= readout_peak.frequency_ghz <=
				target_bands.readout_upper_ghz,
			qubit_notch_in_band = target_bands.qubit_lower_ghz <= qubit_notch.frequency_ghz <=
				target_bands.qubit_upper_ghz,
			simulation_score = simulation_score,
			frequencies_hz = result.frequencies_hz,
			s21_abs_trace = abs.(s21),
			s21_vector_fit = s21_vector_fit,
			z21_abs_trace = abs.(z_traces.z21),
			z11_abs_trace = abs.(z_traces.z11),
			z22_abs_trace = abs.(z_traces.z22),
			raw_y_source_kind = z_traces.raw_y_source_kind,
			ptc_z_source_kind = z_traces.ptc_z_source_kind,
			finite_z_traces =
				all(isfinite, real.(z_traces.z11)) &&
				all(isfinite, imag.(z_traces.z11)) &&
				all(isfinite, real.(z_traces.z21)) &&
				all(isfinite, imag.(z_traces.z21)) &&
				all(isfinite, real.(z_traces.z22)) &&
				all(isfinite, imag.(z_traces.z22)),
		)
	end

	function run_design_sweep(
		designs,
		frequencies_hz;
		section_length_m,
		target_bands,
		port_resistance_ohm,
		pump_frequency,
		pump_current,
		optional_hb_kwargs,
		s21_vector_resonator_count,
		s21_vector_bg_poles,
		s21_vector_min_q,
	)
		sweep = SweepSpec(
			axes = (design = StructuralAxis(designs),),
			compile_policy = CompileEveryPoint(),
			executor = SerialExecutor(),
		)
		return run_parameter_sweep(
			point -> build_two_qwr_mtl_plan(
				point[:design];
				section_length_m = section_length_m,
				port_resistance_ohm = port_resistance_ohm,
			),
			sweep;
			simulate = (compiled, point) -> simulate_design_metrics(
				compiled,
				point[:design],
				frequencies_hz;
				target_bands = target_bands,
				port_resistance_ohm = port_resistance_ohm,
				pump_frequency = pump_frequency,
				pump_current = pump_current,
				optional_hb_kwargs = optional_hb_kwargs,
				s21_vector_resonator_count = s21_vector_resonator_count,
				s21_vector_bg_poles = s21_vector_bg_poles,
				s21_vector_min_q = s21_vector_min_q,
			),
		)
	end
end

# ╔═╡ 8fdf26cb-09a1-40d7-84b9-692992e480ff
begin
	nonbaseline_candidates = [design for design in candidate_designs if !design.is_baseline]
	coarse_sweep_designs = [baseline_design; first_n(nonbaseline_candidates, coarse_candidate_count)]
	fine_seed_designs = [baseline_design; first_n(nonbaseline_candidates, fine_candidate_count)]
end

# ╔═╡ f7ad7541-29fe-42f0-b297-e73be76f24b4
coarse_sweep_result = run_coarse_hb ? run_design_sweep(
	coarse_sweep_designs,
	coarse_frequencies_hz;
	section_length_m = coarse_section_length_m,
	target_bands = target_bands,
	port_resistance_ohm = port_resistance_ohm,
	pump_frequency = pump_frequency,
	pump_current = pump_current,
	optional_hb_kwargs = optional_hb_kwargs,
) : nothing

# ╔═╡ cee8650e-1e51-473f-8543-37fe920f77af
begin
	function score_sort_value(row)
		ismissing(row.simulation_score) && return Inf
		return row.simulation_score
	end

	function simulation_summary_rows(result)
		isnothing(result) && return NamedTuple[]
		points = get(result.provenance, :points, Dict{Symbol,Any}[])
		rows = NamedTuple[]
		for index in eachindex(result.point_statuses)
			design = points[index][:design]
			base_row = (
				point_index = index,
				status = result.point_statuses[index],
				id = design.id,
				label = design.label,
				is_baseline = design.is_baseline,
				lr_total_um = design.lr_total_um,
				lp_total_um = design.lp_total_um,
				lc_um = design.lc_um,
				self_lc_scale = design.self_lc_scale,
				mutual_lc_scale = design.mutual_lc_scale,
				delta_lr_total_um = design.delta_lr_total_um,
				delta_lp_total_um = design.delta_lp_total_um,
				delta_lc_um = design.delta_lc_um,
				distance_from_baseline = design.distance_from_baseline,
				analytic_score = design.analytic_score,
			)

			if result.point_statuses[index] == :success
				metrics = result.point_results[index]
				push!(rows, (;
					base_row...,
					readout_peak_ghz = metrics.readout_peak_ghz,
					filter_peak_ghz = metrics.filter_peak_ghz,
					qubit_notch_ghz = metrics.qubit_notch_ghz,
					readout_error_mhz = metrics.readout_error_mhz,
					qubit_notch_error_mhz = metrics.qubit_notch_error_mhz,
					z21_readout_to_notch_ratio_db = metrics.z21_readout_to_notch_ratio_db,
					s21_vector_fit_status = get(metrics.s21_vector_fit, "status", "missing"),
					s21_vector_resonance_count =
						get(metrics.s21_vector_fit, "status", "failed") == "success" ?
						length(get(metrics.s21_vector_fit, "resonances", Any[])) : 0,
					readout_peak_in_band = metrics.readout_peak_in_band,
					qubit_notch_in_band = metrics.qubit_notch_in_band,
					simulation_score = metrics.simulation_score,
				))
			else
				push!(rows, (;
					base_row...,
					readout_peak_ghz = missing,
					filter_peak_ghz = missing,
					qubit_notch_ghz = missing,
					readout_error_mhz = missing,
					qubit_notch_error_mhz = missing,
					z21_readout_to_notch_ratio_db = missing,
					s21_vector_fit_status = "not_run",
					s21_vector_resonance_count = 0,
					readout_peak_in_band = false,
					qubit_notch_in_band = false,
					simulation_score = missing,
				))
			end
		end
		return sort(rows; by = row -> (row.is_baseline ? 0 : 1, score_sort_value(row)))
	end
end

# ╔═╡ 01d56441-546d-4122-aa47-3c29ecefb958
coarse_sweep_summary = simulation_summary_rows(coarse_sweep_result)

# ╔═╡ da84d8fb-11f2-48a1-b6d2-9bfb1a2ecea1
fine_sweep_designs = if run_fine_hb && !isempty(coarse_sweep_summary)
	success_rows = [
		row for row in coarse_sweep_summary
		if row.status == :success && !row.is_baseline
	]
	success_ids = Set(row.id for row in first_n(success_rows, fine_candidate_count))
	[baseline_design; [design for design in coarse_sweep_designs if design.id in success_ids]]
else
	fine_seed_designs
end

# ╔═╡ 799ad365-bc46-4211-881d-58f1b61e37f7
fine_sweep_result = run_fine_hb ? run_design_sweep(
	fine_sweep_designs,
	fine_frequencies_hz;
	section_length_m = fine_section_length_m,
	target_bands = target_bands,
	port_resistance_ohm = port_resistance_ohm,
	pump_frequency = pump_frequency,
	pump_current = pump_current,
	optional_hb_kwargs = optional_hb_kwargs,
) : nothing

# ╔═╡ 06a53096-a7cf-40ec-bd1b-012707d24390
fine_sweep_summary = simulation_summary_rows(fine_sweep_result)

# ╔═╡ 49396d42-0209-4f89-b551-e5cb2d95df7c
begin
	active_sweep_result = isnothing(fine_sweep_result) ? coarse_sweep_result : fine_sweep_result
	active_sweep_summary = isempty(fine_sweep_summary) ? coarse_sweep_summary : fine_sweep_summary

	function baseline_vs_best_rows(summary_rows; count = 5)
		isempty(summary_rows) && return NamedTuple[]
		baseline_rows = [row for row in summary_rows if row.is_baseline]
		candidate_rows = [
			row for row in summary_rows
			if !row.is_baseline && row.status == :success
		]
		return vcat(baseline_rows, first_n(candidate_rows, count))
	end

	baseline_vs_best_candidates = baseline_vs_best_rows(active_sweep_summary; count = 5)
end

# ╔═╡ 28b37527-3669-45c2-9f70-99f9eff8f056
begin
	analytic_candidates_for_plot = [design for design in candidate_designs if !design.is_baseline]
	parameter_space_figure = parameter_scatter_figure(
		[
			"Analytic candidates" => (
				x = [design.delta_lr_total_um for design in analytic_candidates_for_plot],
				y = [design.delta_lp_total_um for design in analytic_candidates_for_plot],
				text = [string(design.id) for design in analytic_candidates_for_plot],
				marker_color = [design.analytic_score for design in analytic_candidates_for_plot],
				colorbar_title = "analytic score",
				showscale = true,
			),
			"Baseline layout spec" => (
				x = [0.0],
				y = [0.0],
				text = ["Baseline layout spec"],
				marker_color = "#111827",
				marker_symbol = "star",
				marker_size = 18,
			),
		];
		title = "Baseline-Anchored Analytic Parameter Space",
		xaxis_title = "delta readout total length (um)",
		yaxis_title = "delta filter total length (um)",
		config = figure_config,
	)
end |> wide_figure_cell

# ╔═╡ 9a971b45-4789-4bd3-8c1f-94d70411391a
begin
	function successful_metrics(result)
		isnothing(result) && return []
		return [
			(point = get(result.provenance, :points, [])[index], metrics = result.point_results[index])
			for index in eachindex(result.point_statuses)
			if result.point_statuses[index] == :success
		]
	end

	function trace_overlay_pairs(result; trace_field = :z21_abs_trace, count = 5)
		points = successful_metrics(result)
		isempty(points) && return Pair{String,Any}[]
		baseline_points = [point for point in points if point.point[:design].is_baseline]
		candidate_points = sort(
			[point for point in points if !point.point[:design].is_baseline];
			by = point -> point.metrics.simulation_score,
		)
		selected = vcat(baseline_points, first_n(candidate_points, count))
		return [
			point.point[:design].label => getproperty(point.metrics, trace_field)
			for point in selected
		]
	end

	function active_frequencies_hz(result)
		points = successful_metrics(result)
		isempty(points) && return Float64[]
		return first(points).metrics.frequencies_hz
	end
end

# ╔═╡ 1692a74f-52c2-4d7d-b947-35ea6ae3d94e
if isnothing(active_sweep_result)
	md"""
	!!! info "HB sweep is gated"
	    Set `run_coarse_hb = true` to execute the baseline plus local candidates. Set `run_fine_hb = true` after coarse screening to run the finer two-window sweep.
	"""
else
	let frequencies_hz = active_frequencies_hz(active_sweep_result)
		z21_pairs = trace_overlay_pairs(active_sweep_result; trace_field = :z21_abs_trace, count = 5)
		multi_curve_figure(
			frequencies_hz,
			z21_pairs;
			title = "PTC |Z21|: Baseline vs Candidate Designs",
			yaxis_title = "|Z21| (ohm)",
			config = figure_config,
			y_axis_type = :log,
		)
	end |> wide_figure_cell
end

# ╔═╡ f0cb5277-44cf-4ec2-bf35-4798d7c346c4
if isempty(active_sweep_summary)
	md"""
	!!! info "No simulated scatter yet"
	    The simulated readout/notch scatter appears after an HB sweep has run.
	"""
else
	let candidate_rows = [row for row in active_sweep_summary if !row.is_baseline && row.status == :success],
		baseline_rows = [row for row in active_sweep_summary if row.is_baseline && row.status == :success]

		parameter_scatter_figure(
			[
				"Simulated candidates" => (
					x = [row.qubit_notch_ghz for row in candidate_rows],
					y = [row.readout_peak_ghz for row in candidate_rows],
					text = [string(row.id) for row in candidate_rows],
					marker_color = [row.simulation_score for row in candidate_rows],
					colorbar_title = "simulation score",
					showscale = true,
				),
				"Baseline layout spec" => (
					x = [row.qubit_notch_ghz for row in baseline_rows],
					y = [row.readout_peak_ghz for row in baseline_rows],
					text = ["Baseline layout spec"],
					marker_color = "#111827",
					marker_symbol = "star",
					marker_size = 18,
				),
			];
			title = "Simulated Readout Peak vs Qubit-Band Z21 Notch",
			xaxis_title = "Z21 notch frequency (GHz)",
			yaxis_title = "Readout peak frequency (GHz)",
			config = figure_config,
		)
	end |> wide_figure_cell
end

# ╔═╡ 0c149c3c-f1de-41fd-bcec-f9cfc6328f1b
sanity = (
	has_baseline_design = baseline_design.is_baseline,
	baseline_in_candidate_table = any(row -> row.is_baseline, analytic_candidate_table),
	candidate_count = length(candidate_designs),
	coarse_hb_enabled = run_coarse_hb,
	fine_hb_enabled = run_fine_hb,
	coarse_design_count = length(coarse_sweep_designs),
	fine_seed_design_count = length(fine_seed_designs),
	coarse_success_count = isnothing(coarse_sweep_result) ? 0 :
		count(==(:success), coarse_sweep_result.point_statuses),
	fine_success_count = isnothing(fine_sweep_result) ? 0 :
		count(==(:success), fine_sweep_result.point_statuses),
)

# ╔═╡ Cell order:
# ╠═24b8451e-2520-4c52-8f53-0e7219c2fdc4
# ╠═06a726e7-120a-464b-a8dd-98a266e4ad3b
# ╠═785f11a6-a134-4cb7-9908-07dff8c8d1bc
# ╟─5f45a2e2-4116-4875-a3fa-b65540cce0c9
# ╠═4aa7cd1c-7dec-4ff8-a035-ed7100aeb2cb
# ╠═879686f7-254e-4d68-9cb8-f62691cc4656
# ╠═54f401d4-6996-426a-bfdd-bae83199b662
# ╟─22b7d387-2e2b-4bb2-a894-3068ce7b45c0
# ╠═53ec427d-11a6-41a0-b33d-98ff358a2fb9
# ╠═73455c10-a4f5-4709-84b8-d31597293ead
# ╠═c3e963b6-29a8-4614-a263-d4d303c4afc5
# ╠═c0f28c24-4140-4674-856a-0b0db167a340
# ╠═1c0d87a0-d2e1-4e2b-af06-1f1790f81f9f
# ╠═65d2f640-c0ce-40e4-932d-637a91c1ee14
# ╠═980db74a-5908-4146-87be-49b5729941cb
# ╠═8de17e51-5839-49a6-9217-e8ad3ab2fc88
# ╠═8edab22b-a6fb-464f-8f4b-7ac9f4fb03f8
# ╠═cd0908ae-8c3f-4412-810a-871601006fbb
# ╠═2d855015-c69e-4466-8f09-0408962c2987
# ╠═8fdf26cb-09a1-40d7-84b9-692992e480ff
# ╠═f7ad7541-29fe-42f0-b297-e73be76f24b4
# ╠═cee8650e-1e51-473f-8543-37fe920f77af
# ╠═01d56441-546d-4122-aa47-3c29ecefb958
# ╠═da84d8fb-11f2-48a1-b6d2-9bfb1a2ecea1
# ╠═799ad365-bc46-4211-881d-58f1b61e37f7
# ╠═06a53096-a7cf-40ec-bd1b-012707d24390
# ╠═49396d42-0209-4f89-b551-e5cb2d95df7c
# ╠═28b37527-3669-45c2-9f70-99f9eff8f056
# ╠═9a971b45-4789-4bd3-8c1f-94d70411391a
# ╠═1692a74f-52c2-4d7d-b947-35ea6ae3d94e
# ╠═f0cb5277-44cf-4ec2-bf35-4798d7c346c4
# ╠═0c149c3c-f1de-41fd-bcec-f9cfc6328f1b
