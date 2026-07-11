### A Pluto.jl notebook ###
# v1.0.2

#> [frontmatter]
#> title = "02 D3 Filter Frequency Loading HB Trace Producer"
#> tags = ["julia-core", "pluto", "d3", "purcell-filter", "calibration"]
#> description = "Filter-only HB trace producer; fine-window promotion awaits a Human-approved contract."

using Markdown
using InteractiveUtils

# ╔═╡ 1c4dfb1a-f6c1-4d60-a4fb-5d87fc9ec201
begin
	import Pkg
	Pkg.activate(joinpath(first(DEPOT_PATH), "environments", "v1.12"); io = devnull)

	using LinearAlgebra
	using PlutoUI
	using SuperconductingCircuitsCore
	using SuperconductingCircuitsVisualizer

	PlotlyJS = SuperconductingCircuitsVisualizer.PlotlyJS
	figure_config = PlotlyFigureConfig(download_filename = splitext(basename(@__FILE__))[1])
	wide_figure_cell = WideCell(;
		max_width = max(1000, something(figure_config.display_width_px, 1000) + 80),
	)

	JSON3 = SuperconductingCircuitsCore.JSON3
	include(joinpath(@__DIR__, "..", "includes", "hb_example_helpers.jl"))
	zero_mode_s = HBExampleHelpers.zero_mode_s
	include(joinpath(@__DIR__, "d3_purcell_common.jl"))
end

# ╔═╡ 48d8b2d0-7d18-489b-9370-517664a0bb2f
TableOfContents()

# ╔═╡ 8fb170dd-c79f-4028-8286-60167d8355fe
md"""
# 02 Filter Frequency Loading HB Trace Producer

This Pluto notebook owns **filter-only** circuit construction and HB trace
production from the Python-generated length table. It does not own resonance
fitting, accepted linewidths, or resonator-length corrections.

Two diagnostic section models are compared:

- `matched_lc_reference`: the middle `lc` section keeps the MTL-diagonal phase
  velocity but has the same characteristic impedance as the surrounding
  single-trace CPW.
- `mtl_diagonal_lc_mismatch`: the middle `lc` section uses the Q2D MTL diagonal
  RLGC terms, creating the real impedance step used in the current pair model.

Python Notebook 02 reads an already generated fine-trace manifest, calls the
shared complex-notch fitter, and publishes candidate evidence for Human review.
It does not promote that evidence into loading or correction results.

The through feedline uses the independent 50 Ω LC extraction in
`d3_design_config.json`; the selected Q2D case's single-trace LC model remains a
resonator-section model only.

Interpret this workflow with the canonical [Notch Resonator Complex S21 Fit](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/notch-resonator-complex-s21-fit.qmd),
[Vector Fitting and Passivity](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/vector-fitting-passivity.qmd),
[Multiconductor RLGC Matrices](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/transmission-lines/multiconductor-rlgc-matrix-semantics.qmd),
[Resonator Length Correction Loop](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/transmission-lines/resonator-length-correction-loop.qmd),
[Loaded-Bare Readout / Filter References](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/readout/loaded-bare-readout-filter-references.qmd),
[Harmonic Balance: Periodic Steady State and Mode Semantics](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/numerical-methods/harmonic-balance-periodic-steady-state.qmd),
[Port Reference Impedance Semantics](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/simulation/port-reference-impedance-semantics.qmd),
and [Port-Termination Compensation (PTC)](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/simulation/port-termination-compensation.qmd).
"""

# ╔═╡ 52f323e0-f839-4646-b4fa-2d8947edac8c
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
	d3_output_dir = joinpath(orpen_circuit_output_dir, "d3_intrinsic_purcell_filter_design")
	d3_design_config = load_d3_design_config()
	feedline_rlgc = load_d3_feedline_rlgc(d3_design_config)
	design_variant_id = Symbol(String(d3_design_config["active_design_variant_id"]))
	design_csv_filename = String(d3_design_config["design_csv_filename"])
	output_suffix = design_variant_id == :baseline ? "" : "__$(csv_slug(design_variant_id))"
	calibration_output_dir = joinpath(d3_output_dir, "filter_frequency_loading_calibration$(output_suffix)")
	design_csv_path = joinpath(d3_output_dir, "design_inputs", design_csv_filename)
	case_json_path = joinpath(orpen_circuit_output_dir, "orpen_q2d_rlgc_cases.json")
	selected_designs_csv_path = joinpath(calibration_output_dir, "d3_filter_loading_selected_designs.csv")
	manifest_csv_path = joinpath(calibration_output_dir, "d3_filter_loading_manifest.csv")
	fine_manifest_csv_path = joinpath(calibration_output_dir, "d3_filter_loading_fine_s21_manifest.csv")
	trace_dir = joinpath(calibration_output_dir, "traces")

	selected_case_id = Symbol(String(d3_design_config["selected_case_id"]))

	run_hb = true
	frequency_step_mhz = 0.2
	scan_half_width_ghz = 0.70
	filter_cap_sweep_fF = [0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 31.7, 40.0, 50.0]

	request_fine_s21_generation = false

	section_length_m = 10.0um
	port_resistance_ohm = 50.0
	feedline_length_um = 1000.0
	pump_frequency = 20.0GHz
	pump_current = 0.0
	optional_hb_kwargs = Dict{Symbol,Any}(
		:nbatches => 1,
		:iterations => 160,
		:ftol => 1.0e-8,
	)
	hb_settings = D3HBSettings(
		section_length_m,
		port_resistance_ohm,
		pump_frequency,
		pump_current,
		1,
		1,
		optional_hb_kwargs,
	)
end

# ╔═╡ 9724167e-3fdb-4b73-b130-147b12d91258
begin
	orpen_cases = load_orpen_cases(case_json_path)
	selected_case = only([case for case in orpen_cases if case.id == selected_case_id])

	function impedance_matched_lc_values(case)
		z_single = sqrt(case.single_l_per_m_h / case.single_c_per_m_f)
		v_lc = case.mtl_diag_velocity_m_per_s
		return (
			l_per_m_h = z_single / v_lc,
			c_per_m_f = 1 / (z_single * v_lc),
			impedance_ohm = z_single,
			velocity_m_per_s = v_lc,
		)
	end

	matched_lc = impedance_matched_lc_values(selected_case)
	filter_model_cases = (
		(
			id = :matched_lc_reference,
			label = "Full impedance match reference",
			lc_l_per_m_h = matched_lc.l_per_m_h,
			lc_c_per_m_f = matched_lc.c_per_m_f,
			lc_impedance_ohm = matched_lc.impedance_ohm,
			lc_velocity_m_per_s = matched_lc.velocity_m_per_s,
		),
		(
			id = :mtl_diagonal_lc_mismatch,
			label = "Q2D MTL diagonal lc mismatch",
			lc_l_per_m_h = selected_case.mtl_diag_l_per_m_h,
			lc_c_per_m_f = selected_case.mtl_diag_c_per_m_f,
			lc_impedance_ohm = selected_case.mtl_diag_zo_ohm,
			lc_velocity_m_per_s = selected_case.mtl_diag_velocity_m_per_s,
		),
	)
end

# ╔═╡ 7eb3d78a-e3f0-4bcb-b720-6b1dac796e3e
begin
	best_slot_candidates = read_design_csv(design_csv_path; case_id = selected_case_id)
	length_handcheck_table = [
		(
			target_set_id = String(row.target_set_id),
			target_set_name = row.target_set_name,
			slot_GHz = row.slot_target_ghz,
			lp_short_um = row.lp_short_um,
			lc_um = row.lc_um,
			lp_open_um = row.lp_open_um,
			lp_total_um = row.lp_total_um,
			fp_est_GHz = row.fp_est_ghz,
			fn_est_GHz = row.fn_est_ghz,
			score = row.analytic_score,
		)
		for row in best_slot_candidates
	]
end

# ╔═╡ f7a4a9e6-02b9-4510-a186-a2ec9578c74d
begin
	function filter_scan_frequencies(design)
		start_ghz = max(design.scan_start_ghz, design.slot_target_ghz - scan_half_width_ghz)
		stop_ghz = min(design.scan_stop_ghz, design.slot_target_ghz + scan_half_width_ghz)
		return frequency_range_with_step(start_ghz * GHz, stop_ghz * GHz, frequency_step_mhz * MHz)
	end

	function run_filter_loading_case(
		case,
		design,
		model_case,
		capacitance_fF;
		frequencies_hz = filter_scan_frequencies(design),
		output_trace_dir = trace_dir,
		trace_tag = "",
	)
		circuit_plan = build_filter_only_feedline_plan(
			case,
			design;
			capacitance_fF = capacitance_fF,
			feedline_length_um = feedline_length_um,
			feedline = feedline_rlgc,
			lc_l_per_m_h = model_case.lc_l_per_m_h,
			lc_c_per_m_f = model_case.lc_c_per_m_f,
			model_case_id = model_case.id,
			hb_settings = hb_settings,
		)
		hb = run_sparameter_hb(circuit_plan, frequencies_hz; hb_settings = hb_settings)
		tag_suffix = isempty(String(trace_tag)) ? "" : "__$(csv_slug(trace_tag))"
		trace_csv = joinpath(
			output_trace_dir,
			"model_$(csv_slug(model_case.id))__slot_$(csv_slug(design.slot_target_ghz))GHz__c_$(csv_slug(capacitance_fF))fF$(tag_suffix)__s.csv",
		)
		write_sparameter_trace_csv(trace_csv, hb.result.frequencies_hz, hb.s11, hb.s21, hb.z21)
		return (
			id = string(design.id),
			case_id = String(design.case_id),
			model_case_id = String(model_case.id),
			model_case_label = model_case.label,
			target_set_id = String(design.target_set_id),
			target_set_name = design.target_set_name,
			slot_target_ghz = design.slot_target_ghz,
			filter_to_line_capacitance_fF = Float64(capacitance_fF),
			lc_impedance_ohm = model_case.lc_impedance_ohm,
			lc_velocity_m_per_s = model_case.lc_velocity_m_per_s,
			lp_short_um = design.lp_short_um,
			lc_um = design.lc_um,
			lp_open_um = design.lp_open_um,
			lp_total_um = design.lp_total_um,
			trace_csv = trace_csv,
			hb_intent_ok = hb.hb_intent_ok,
			netlist_rows = hb.netlist_rows,
			frequencies_hz = hb.result.frequencies_hz,
			s11 = hb.s11,
			s21 = hb.s21,
			z21 = hb.z21,
			z21_ptc = hb.z21_ptc,
		)
	end

	filter_loading_runs = run_hb ? [
		run_filter_loading_case(selected_case, design, model_case, capacitance_fF)
		for model_case in filter_model_cases
		for design in best_slot_candidates
		for capacitance_fF in filter_cap_sweep_fF
	] : NamedTuple[]
	filter_loading_manifest = [
		Base.structdiff(row, NamedTuple{(:frequencies_hz, :s11, :s21, :z21, :z21_ptc)})
		for row in filter_loading_runs
	]
end

# ╔═╡ 68c8e28e-9194-40f4-a343-19df72a8a1ac
md"""
## Fine S21 Generation Boundary

The existing fine manifest and traces remain valid source artifacts for the
Python evidence notebook and are not overwritten here. The former path chose
fine windows from a local vector-fit linewidth result. That is not an approved
window contract: 22 current windows do not bracket their sampled notch.

A future fine run requires an explicit Human-approved per-trace center, window,
and step artifact. This notebook does not invent defaults or fall back to the
old vector-fit selection.
"""

# ╔═╡ cb3a1f20-1a3e-4c4f-96bc-d37ac4243921
begin
	request_fine_s21_generation && error(
		"Fine S21 generation requires a Human-approved per-trace center/window/step artifact contract.",
	)
	fine_generation_status = :blocked_pending_human_window_contract
end

# ╔═╡ 63a9d88c-e29c-4ec4-b0e2-526ee7b4814b
begin
	write_namedtuple_csv(selected_designs_csv_path, length_handcheck_table)
	run_hb && write_namedtuple_csv(manifest_csv_path, filter_loading_manifest)
	output_paths = (
		selected_designs_csv = selected_designs_csv_path,
		manifest_csv = run_hb ? manifest_csv_path : "not written; set run_hb = true",
		fine_manifest_csv = isfile(fine_manifest_csv_path) ? fine_manifest_csv_path : "not present",
		trace_dir = trace_dir,
		fine_generation_status = fine_generation_status,
	)
end

# ╔═╡ d13c6eb8-9912-4b9f-8f17-151758c0bfb2
begin
	self_check = (
		has_length_rows = length(best_slot_candidates) == 5,
		has_two_model_cases = length(filter_model_cases) == 2,
		wrote_expected_runs = !run_hb || length(filter_loading_runs) == length(filter_model_cases) * length(best_slot_candidates) * length(filter_cap_sweep_fF),
		all_hb_intents_ok = !run_hb || all(row -> row.hb_intent_ok, filter_loading_runs),
		fine_generation_not_requested = !request_fine_s21_generation,
	)
	all(values(self_check)) || error("Filter loading calibration self-check failed: $(self_check)")
	self_check
end

# ╔═╡ Cell order:
# ╠═1c4dfb1a-f6c1-4d60-a4fb-5d87fc9ec201
# ╠═48d8b2d0-7d18-489b-9370-517664a0bb2f
# ╟─8fb170dd-c79f-4028-8286-60167d8355fe
# ╠═52f323e0-f839-4646-b4fa-2d8947edac8c
# ╠═9724167e-3fdb-4b73-b130-147b12d91258
# ╠═7eb3d78a-e3f0-4bcb-b720-6b1dac796e3e
# ╠═f7a4a9e6-02b9-4510-a186-a2ec9578c74d
# ╟─68c8e28e-9194-40f4-a343-19df72a8a1ac
# ╠═cb3a1f20-1a3e-4c4f-96bc-d37ac4243921
# ╠═63a9d88c-e29c-4ec4-b0e2-526ee7b4814b
# ╠═d13c6eb8-9912-4b9f-8f17-151758c0bfb2
