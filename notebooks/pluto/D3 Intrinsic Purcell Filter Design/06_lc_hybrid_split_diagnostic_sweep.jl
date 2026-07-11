### A Pluto.jl notebook ###
# v1.0.2

#> [frontmatter]
#> title = "06 D3 LC Hybrid-Split Diagnostic Sweep"
#> tags = ["julia-core", "d3", "purcell-filter", "z21", "diagnostic-sweep"]
#> description = "MTL overlap sweep feeding a half-hybrid-split diagnostic with per-lc bare-frequency Cext rechecks."

using Markdown
using InteractiveUtils

# ╔═╡ imports
begin
	import Pkg
	Pkg.activate(joinpath(first(DEPOT_PATH), "environments", "v1.12"); io = devnull)

	using LinearAlgebra
	using PlutoUI
	using SuperconductingCircuitsCore
	using SuperconductingCircuitsVisualizer

	PlotlyJS = SuperconductingCircuitsVisualizer.PlotlyJS
	JSON3 = SuperconductingCircuitsCore.JSON3
	include(joinpath(@__DIR__, "..", "includes", "hb_example_helpers.jl"))
	zero_mode_s = HBExampleHelpers.zero_mode_s
	include(joinpath(@__DIR__, "d3_purcell_common.jl"))
end

# ╔═╡ title
md"""
# 06 `$l_c$` Hybrid-Split Diagnostic Sweep

This notebook is the controlled version of the earlier diagnostic `lc` sweep.
For one representative slot, each `lc` point compensates both short and open
sections so the first-order readout frequency, filter frequency, and notch
delay stay anchored to the base design.

Each compensated `lc` point then reruns:

- filter-only `C_ext` sweep, to measure the loaded filter bare frequency;
- readout-only weak-probe sweep, to measure the readout bare frequency;
- intrinsic pair `Z21`, to measure the hybridized pair and notch.

Python analysis uses these outputs to report half of the corrected hybrid split
as `half_hybrid_split_mhz`. That value is a diagnostic only; it is not an
extracted $J$ and does not replace the canonical complex-`S21` $J$ fit.

Interpret this workflow with the canonical [Multiconductor RLGC Matrices](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/transmission-lines/multiconductor-rlgc-matrix-semantics.qmd),
[Resonator Length Correction Loop](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/transmission-lines/resonator-length-correction-loop.qmd),
[Loaded-Bare Readout / Filter References](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/readout/loaded-bare-readout-filter-references.qmd),
[Bare vs Hybridized Readout / Filter Modes](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/readout/bare-vs-hybridized-readout-filter-modes.qmd),
[Readout-Filter S21 J Fit](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/readout/readout-filter-s21-j-fit.qmd),
[Harmonic Balance: Periodic Steady State and Mode Semantics](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/numerical-methods/harmonic-balance-periodic-steady-state.qmd),
[Port Reference Impedance Semantics](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/simulation/port-reference-impedance-semantics.qmd),
and [Port-Termination Compensation (PTC)](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/simulation/port-termination-compensation.qmd).

HB operating-point, mode, and convergence semantics are owned by the Harmonic
Balance page above.
"""

# ╔═╡ config
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
	output_suffix = "__$(csv_slug(design_variant_id))"
	sweep_output_dir = joinpath(d3_output_dir, "lc_hybrid_split_diagnostic$(output_suffix)")
	trace_dir = joinpath(sweep_output_dir, "traces")
	filter_trace_dir = joinpath(trace_dir, "filter_loading")
	readout_trace_dir = joinpath(trace_dir, "readout_probe")
	z21_trace_dir = joinpath(trace_dir, "intrinsic_z21")
	setup_csv_path = joinpath(sweep_output_dir, "d3_lc_hybrid_split_diagnostic_setup.csv")
	designs_csv_path = joinpath(sweep_output_dir, "d3_lc_hybrid_split_diagnostic_designs.csv")
	corrected_design_csv_path = joinpath(sweep_output_dir, "d3_lc_hybrid_split_diagnostic_corrected_design_inputs.csv")
	filter_manifest_csv_path = joinpath(sweep_output_dir, "d3_controlled_filter_loading_manifest.csv")
	readout_manifest_csv_path = joinpath(sweep_output_dir, "d3_controlled_readout_probe_manifest.csv")
	z21_manifest_csv_path = joinpath(sweep_output_dir, "d3_controlled_intrinsic_z21_manifest.csv")
	design_csv_path = joinpath(d3_output_dir, "design_inputs", String(d3_design_config["design_csv_filename"]))
	case_json_path = joinpath(orpen_circuit_output_dir, "orpen_q2d_rlgc_cases.json")

	selected_case_id = Symbol(String(d3_design_config["selected_case_id"]))
	representative_slot_ghz = 6.0
	run_hb = true
	frequency_step_mhz = 0.2
	probe_scan_half_width_ghz = 0.70
	z21_scan_start_ghz = 4.0
	z21_scan_stop_ghz = 7.4

	lc_sweep_um = [40.0, 80.0, 120.0, 160.0, 200.0, 240.0]
	filter_cap_sweep_fF = [0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 31.7]
	readout_probe_cap_sweep_fF = [0.2, 0.5, 1.0, 2.0]
	controlled_design_source = :generated

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

# ╔═╡ inputs
begin
	orpen_cases = load_orpen_cases(case_json_path)
	selected_case = only([case for case in orpen_cases if case.id == selected_case_id])
	base_designs = read_design_csv(design_csv_path; case_id = selected_case_id)
	base_design = only([row for row in base_designs if isapprox(row.slot_target_ghz, representative_slot_ghz; atol = 1.0e-9)])
	selected_filter_cext_fF = require_design_capacitance_fF(base_design)
	velocity_ratio = selected_case.single_velocity_m_per_s / selected_case.mtl_diag_velocity_m_per_s
end

# ╔═╡ controlled_designs
begin
	function controlled_lc_design(base_design, lc_um)
		lc_value_um = Float64(lc_um)
		compensation_delta_um = 0.5 * (lc_value_um - base_design.lc_um) * velocity_ratio
		lr_short_um = base_design.lr_short_um - compensation_delta_um
		lp_short_um = base_design.lp_short_um - compensation_delta_um
		lr_open_um = base_design.lr_open_um - compensation_delta_um
		lp_open_um = base_design.lp_open_um - compensation_delta_um
		min(lr_short_um, lp_short_um, lr_open_um, lp_open_um, lc_value_um) > 0 ||
			error("Invalid controlled lc lengths for lc=$(lc_um).")
		return merge(
			base_design,
			(
				id = Symbol("$(base_design.id)__controlled_lc$(csv_slug(lc_value_um))"),
				sweep_id = Symbol("controlled_lc$(csv_slug(lc_value_um))"),
				lc_um = lc_value_um,
				lc_compensation_delta_um = compensation_delta_um,
				lr_short_um = lr_short_um,
				lp_short_um = lp_short_um,
				lr_open_um = lr_open_um,
				lp_open_um = lp_open_um,
				lr_total_um = lr_short_um + lc_value_um + lr_open_um,
				lp_total_um = lp_short_um + lc_value_um + lp_open_um,
				notch_length_um = lr_short_um + lc_value_um + lp_short_um,
			),
		)
	end

	function controlled_fields(design)
		return merge(
			design,
			(
				sweep_id = Symbol("controlled_lc$(csv_slug(design.lc_um))"),
				lc_compensation_delta_um = NaN,
			),
		)
	end

	controlled_designs = if controlled_design_source === :generated
		[controlled_lc_design(base_design, lc_um) for lc_um in lc_sweep_um]
	elseif controlled_design_source === :corrected_csv
		isfile(corrected_design_csv_path) || error("Missing explicitly selected corrected-design CSV: $(corrected_design_csv_path)")
		[controlled_fields(design) for design in read_design_csv(corrected_design_csv_path; case_id = selected_case_id)]
	else
		error("controlled_design_source must be :generated or :corrected_csv.")
	end
end

# ╔═╡ readout_only_helper
begin
	nothing
end

# ╔═╡ run_helpers
begin
	function probe_frequencies(design)
		start_ghz = max(design.scan_start_ghz, design.slot_target_ghz - probe_scan_half_width_ghz)
		stop_ghz = min(design.scan_stop_ghz, design.slot_target_ghz + probe_scan_half_width_ghz)
		return frequency_range_with_step(start_ghz * GHz, stop_ghz * GHz, frequency_step_mhz * MHz)
	end

	function z21_frequencies()
		return frequency_range_with_step(
			z21_scan_start_ghz * GHz,
			z21_scan_stop_ghz * GHz,
			frequency_step_mhz * MHz,
		)
	end

	function filter_caps_for_design(design)
		return sort(unique(vcat(filter_cap_sweep_fF, [require_design_capacitance_fF(design)])))
	end

	function run_filter_loading_design(case, design, capacitance_fF)
		circuit_plan = build_filter_only_feedline_plan(
			case,
			design;
			capacitance_fF = capacitance_fF,
			feedline_length_um = feedline_length_um,
			feedline = feedline_rlgc,
			lc_l_per_m_h = case.mtl_diag_l_per_m_h,
			lc_c_per_m_f = case.mtl_diag_c_per_m_f,
			model_case_id = :mtl_diagonal_lc_mismatch,
			hb_settings = hb_settings,
		)
		hb = run_sparameter_hb(circuit_plan, probe_frequencies(design); hb_settings = hb_settings)
		trace_csv = joinpath(
			filter_trace_dir,
			"lc_$(csv_slug(design.lc_um))um__c_$(csv_slug(capacitance_fF))fF__filter_s.csv",
		)
		write_sparameter_trace_csv(trace_csv, hb.result.frequencies_hz, hb.s11, hb.s21, hb.z21)
		return (
			sweep_id = String(design.sweep_id),
			slot_target_ghz = design.slot_target_ghz,
			lc_um = design.lc_um,
			filter_to_line_capacitance_fF = Float64(capacitance_fF),
			selected_filter_to_line_capacitance_fF = selected_filter_cext_fF,
			lp_short_um = design.lp_short_um,
			lp_open_um = design.lp_open_um,
			lp_total_um = design.lp_total_um,
			trace_csv = trace_csv,
			hb_intent_ok = hb.hb_intent_ok,
			netlist_rows = hb.netlist_rows,
		)
	end

	function run_readout_probe_design(case, design, capacitance_fF)
		circuit_plan = build_readout_only_feedline_plan(
			case,
			design;
			capacitance_fF = capacitance_fF,
			feedline_length_um = feedline_length_um,
			feedline = feedline_rlgc,
			hb_settings = hb_settings,
		)
		hb = run_sparameter_hb(circuit_plan, probe_frequencies(design); hb_settings = hb_settings)
		trace_csv = joinpath(
			readout_trace_dir,
			"lc_$(csv_slug(design.lc_um))um__c_$(csv_slug(capacitance_fF))fF__readout_s.csv",
		)
		write_sparameter_trace_csv(trace_csv, hb.result.frequencies_hz, hb.s11, hb.s21, hb.z21)
		return (
			sweep_id = String(design.sweep_id),
			slot_target_ghz = design.slot_target_ghz,
			lc_um = design.lc_um,
			readout_probe_capacitance_fF = Float64(capacitance_fF),
			lr_short_um = design.lr_short_um,
			lr_open_um = design.lr_open_um,
			lr_total_um = design.lr_total_um,
			trace_csv = trace_csv,
			hb_intent_ok = hb.hb_intent_ok,
			netlist_rows = hb.netlist_rows,
		)
	end

	function run_z21_design(case, design)
		circuit_plan = build_intrinsic_pair_plan(case, design; hb_settings = hb_settings)
		hb = run_sparameter_hb(
			circuit_plan,
			z21_frequencies();
			hb_settings = hb_settings,
			compensate_port_indices = (1, 2),
			removal_intent = :intrinsic_pair_probe_scaffold,
		)
		trace_csv = joinpath(z21_trace_dir, "lc_$(csv_slug(design.lc_um))um__z21.csv")
		write_sparameter_trace_csv(trace_csv, hb.result.frequencies_hz, hb.s11, hb.s21, hb.z21, hb.z21_ptc)
		return (
			sweep_id = String(design.sweep_id),
			slot_target_ghz = design.slot_target_ghz,
			notch_target_ghz = design.notch_target_ghz,
			lc_um = design.lc_um,
			lr_short_um = design.lr_short_um,
			lp_short_um = design.lp_short_um,
			lr_open_um = design.lr_open_um,
			lp_open_um = design.lp_open_um,
			lr_total_um = design.lr_total_um,
			lp_total_um = design.lp_total_um,
			notch_length_um = design.notch_length_um,
			trace_csv = trace_csv,
			hb_intent_ok = hb.hb_intent_ok,
			netlist_rows = hb.netlist_rows,
		)
	end
end

# ╔═╡ run_sweeps
begin
	filter_runs = run_hb ? [
		run_filter_loading_design(selected_case, design, capacitance_fF)
		for design in controlled_designs
		for capacitance_fF in filter_caps_for_design(design)
	] : NamedTuple[]

	readout_runs = run_hb ? [
		run_readout_probe_design(selected_case, design, capacitance_fF)
		for design in controlled_designs
		for capacitance_fF in readout_probe_cap_sweep_fF
	] : NamedTuple[]

	z21_runs = run_hb ? [run_z21_design(selected_case, design) for design in controlled_designs] : NamedTuple[]
end

# ╔═╡ write_outputs
begin
	setup_rows = [
		(
			case_id = String(selected_case.id),
			slot_target_ghz = representative_slot_ghz,
			base_lc_um = base_design.lc_um,
			selected_filter_to_line_capacitance_fF = selected_filter_cext_fF,
			compensation = "short and open sections adjusted by half of lc delay change",
			frequency_step_mhz = frequency_step_mhz,
			z21_scan_start_ghz = z21_scan_start_ghz,
			z21_scan_stop_ghz = z21_scan_stop_ghz,
		),
	]
	design_rows = [
		(
			sweep_id = String(design.sweep_id),
			slot_target_ghz = design.slot_target_ghz,
			lc_um = design.lc_um,
			lc_compensation_delta_um = design.lc_compensation_delta_um,
			lr_short_um = design.lr_short_um,
			lr_open_um = design.lr_open_um,
			lp_short_um = design.lp_short_um,
			lp_open_um = design.lp_open_um,
			lr_total_um = design.lr_total_um,
			lp_total_um = design.lp_total_um,
			notch_length_um = design.notch_length_um,
			selected_filter_to_line_capacitance_fF = selected_filter_cext_fF,
		)
		for design in controlled_designs
	]
	write_namedtuple_csv(setup_csv_path, setup_rows)
	write_namedtuple_csv(designs_csv_path, design_rows)
	run_hb && write_namedtuple_csv(filter_manifest_csv_path, filter_runs)
	run_hb && write_namedtuple_csv(readout_manifest_csv_path, readout_runs)
	run_hb && write_namedtuple_csv(z21_manifest_csv_path, z21_runs)
	output_paths = (
		setup_csv = setup_csv_path,
		designs_csv = designs_csv_path,
		filter_manifest_csv = filter_manifest_csv_path,
		readout_manifest_csv = readout_manifest_csv_path,
		z21_manifest_csv = z21_manifest_csv_path,
	)
end

# ╔═╡ self_check
begin
	expected_filter_runs = sum(length(filter_caps_for_design(design)) for design in controlled_designs)
	self_check = (
		has_controlled_designs = length(controlled_designs) == length(lc_sweep_um),
		wrote_filter_runs = !run_hb || length(filter_runs) == expected_filter_runs,
		wrote_readout_runs = !run_hb || length(readout_runs) == length(controlled_designs) * length(readout_probe_cap_sweep_fF),
		wrote_z21_runs = !run_hb || length(z21_runs) == length(controlled_designs),
		all_filter_hb_ok = !run_hb || all(row -> row.hb_intent_ok, filter_runs),
		all_readout_hb_ok = !run_hb || all(row -> row.hb_intent_ok, readout_runs),
		all_z21_hb_ok = !run_hb || all(row -> row.hb_intent_ok, z21_runs),
	)
	all(values(self_check)) || error("Controlled half-hybrid-split diagnostic sweep self-check failed: $(self_check)")
	self_check
end

# ╔═╡ Cell order:
# ╠═imports
# ╟─title
# ╠═config
# ╠═inputs
# ╠═controlled_designs
# ╠═readout_only_helper
# ╠═run_helpers
# ╠═run_sweeps
# ╠═write_outputs
# ╠═self_check
