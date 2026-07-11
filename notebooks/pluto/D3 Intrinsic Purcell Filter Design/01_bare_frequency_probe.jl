### A Pluto.jl notebook ###
# v1.0.2

#> [frontmatter]
#> title = "01 D3 Coupled-Pair Frequency Probe HB Simulation"
#> tags = ["julia-core", "pluto", "d3", "purcell-filter", "probe"]
#> description = "Single-pair HB probe traces from Python-generated D3 resonator lengths."

using Markdown
using InteractiveUtils

# ╔═╡ 4cf0f8d3-fcb2-40c8-8dc6-8a1a5a85d001
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

# ╔═╡ 2385fa9e-c390-41ad-afd6-ad3fa0c8bc06
TableOfContents()

# ╔═╡ b8719af5-840f-4f9a-ae16-dff6c2fe3eb5
md"""
# 01 Coupled-Pair Frequency Probe HB Simulation

This Pluto notebook only builds circuits and runs HB from the Python-generated
length table. The readout line couples only to the **filter resonator open
end**, using the same coupling capacitor value planned for the full readout
line.

The file and output folder still use `bare_frequency_probe` for compatibility
with earlier analysis scripts. Physically, once the MTL coupling section is
present, the two resonator peaks are **hybridized coupled-pair modes**, not
uncoupled bare resonator modes.

Mode assignment is not taken from one spectrum. Use the perturbation traces:

```text
baseline
readout_open_minus / readout_open_plus  -> only readout resonator open-end length moves
filter_open_minus / filter_open_plus    -> only filter resonator open-end length moves
```

The central-difference sensitivity tells which physical resonator the
hybridized mode is closer to. Python analysis consumes these CSVs and performs
the frequency extraction.

Interpret this workflow with the canonical [Multiconductor RLGC Matrices](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/transmission-lines/multiconductor-rlgc-matrix-semantics.qmd),
[Baseline Resonator Estimate](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/transmission-lines/baseline-resonator-estimate.qmd),
[Resonator Length Correction Loop](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/transmission-lines/resonator-length-correction-loop.qmd),
[Harmonic Balance: Periodic Steady State and Mode Semantics](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/numerical-methods/harmonic-balance-periodic-steady-state.qmd),
[Port Reference Impedance Semantics](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/simulation/port-reference-impedance-semantics.qmd),
and [Port-Termination Compensation (PTC)](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/simulation/port-termination-compensation.qmd).
"""

# ╔═╡ 6f33b676-3ce7-4862-b6c0-e5754eb8e101
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
	bare_output_dir = joinpath(d3_output_dir, "bare_frequency_probe$(output_suffix)")
	design_csv_path = joinpath(d3_output_dir, "design_inputs", design_csv_filename)
	case_json_path = joinpath(orpen_circuit_output_dir, "orpen_q2d_rlgc_cases.json")
	selected_designs_csv_path = joinpath(bare_output_dir, "d3_bare_selected_designs.csv")
	manifest_csv_path = joinpath(bare_output_dir, "d3_bare_probe_manifest.csv")
	intrinsic_z21_manifest_csv_path = joinpath(bare_output_dir, "d3_intrinsic_z21_manifest.csv")
	trace_dir = joinpath(bare_output_dir, "traces")
	intrinsic_z21_trace_dir = joinpath(bare_output_dir, "intrinsic_z21_traces")

	selected_case_id = Symbol(String(d3_design_config["selected_case_id"]))

	run_hb = true
	frequency_step_mhz = 0.2
	probe_scan_half_width_ghz = 0.70
	filter_to_line_capacitance_fF = 27.36
	length_perturbation_um = 50.0
	run_intrinsic_z21 = true
	intrinsic_z21_scan_start_ghz = 4.0
	intrinsic_z21_scan_stop_ghz = 7.4

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

# ╔═╡ 08a9233a-ed77-4ef0-a9ca-e1af695c45d1
begin
	orpen_cases = load_orpen_cases(case_json_path)
	selected_case = only([case for case in orpen_cases if case.id == selected_case_id])
	q2d_selected_case = (
		case_id = String(selected_case.id),
		height_um = selected_case.height_um,
		resonator_single_Zo_effective_ohm = selected_case.zo_effective_ohm,
		Zm_ohm = selected_case.zm_ohm,
		MTL_diagonal_Zo_ohm = selected_case.mtl_diag_zo_ohm,
		single_velocity_m_per_s = selected_case.single_velocity_m_per_s,
		mtl_diagonal_velocity_m_per_s = selected_case.mtl_diag_velocity_m_per_s,
		feedline_target_Zo_ohm = feedline_rlgc.target_impedance_ohm,
		feedline_extracted_Zo_ohm = feedline_rlgc.zo_ohm,
		feedline_velocity_m_per_s = feedline_rlgc.velocity_m_per_s,
	)
end

# ╔═╡ 0b63afdf-52aa-4c22-a23b-8210c18e59b9
begin
	best_slot_candidates = read_design_csv(design_csv_path; case_id = selected_case_id)
	target_slot_sets = target_sets_from_designs(best_slot_candidates)
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
			fr_est_GHz = row.fr_est_ghz,
			fp_est_GHz = row.fp_est_ghz,
			fn_est_GHz = row.fn_est_ghz,
			score = row.analytic_score,
		)
		for row in best_slot_candidates
	]
end

# ╔═╡ 61465ec6-fbb2-476c-a7c9-a2ac333868b5
begin
	ownership_variants = (
		(id = :baseline, readout_delta_um = 0.0, filter_delta_um = 0.0),
		(id = :readout_open_minus, readout_delta_um = -length_perturbation_um, filter_delta_um = 0.0),
		(id = :readout_open_plus, readout_delta_um = length_perturbation_um, filter_delta_um = 0.0),
		(id = :filter_open_minus, readout_delta_um = 0.0, filter_delta_um = -length_perturbation_um),
		(id = :filter_open_plus, readout_delta_um = 0.0, filter_delta_um = length_perturbation_um),
	)
	probe_designs = [
		perturb_design_open_length(
			design;
			variant_id = variant.id,
			readout_delta_um = variant.readout_delta_um,
			filter_delta_um = variant.filter_delta_um,
		)
		for design in best_slot_candidates
		for variant in ownership_variants
	]
end

# ╔═╡ 8e0e7f35-d58a-45d3-8764-6b7895c56fda
begin
	function probe_frequencies(design)
		start_ghz = max(design.scan_start_ghz, design.slot_target_ghz - probe_scan_half_width_ghz)
		stop_ghz = min(design.scan_stop_ghz, design.slot_target_ghz + probe_scan_half_width_ghz)
		return frequency_range_with_step(start_ghz * GHz, stop_ghz * GHz, frequency_step_mhz * MHz)
	end

	function run_probe_design(case, design)
		frequencies_hz = probe_frequencies(design)
		circuit_plan = build_single_pair_feedline_plan(
			case,
			design;
			capacitance_fF = filter_to_line_capacitance_fF,
			feedline_length_um = feedline_length_um,
			feedline = feedline_rlgc,
			hb_settings = hb_settings,
		)
		hb = run_sparameter_hb(circuit_plan, frequencies_hz; hb_settings = hb_settings)
		trace_csv = joinpath(
			trace_dir,
			"set_$(csv_slug(design.target_set_id))__slot_$(csv_slug(design.slot_target_ghz))GHz__$(csv_slug(design.variant_id))__s.csv",
		)
		write_sparameter_trace_csv(trace_csv, hb.result.frequencies_hz, hb.s11, hb.s21, hb.z21)
		actual_capacitance_fF = Float64(filter_to_line_capacitance_fF)
		return (
			id = string(design.id),
			case_id = String(design.case_id),
			target_set_id = String(design.target_set_id),
			target_set_name = design.target_set_name,
			slot_target_ghz = design.slot_target_ghz,
			variant_id = String(design.variant_id),
			readout_open_delta_um = design.readout_open_delta_um,
			filter_open_delta_um = design.filter_open_delta_um,
			filter_to_line_capacitance_fF = actual_capacitance_fF,
			lr_total_um = design.lr_total_um,
			lp_total_um = design.lp_total_um,
			trace_csv = trace_csv,
			hb_intent_ok = hb.hb_intent_ok,
			netlist_rows = hb.netlist_rows,
			frequencies_hz = hb.result.frequencies_hz,
			s11 = hb.s11,
			s21 = hb.s21,
		)
	end

	probe_runs = run_hb ? [run_probe_design(selected_case, design) for design in probe_designs] : NamedTuple[]
	probe_manifest = [
		Base.structdiff(row, NamedTuple{(:frequencies_hz, :s11, :s21, :z21, :z21_ptc)})
		for row in probe_runs
	]
end

# ╔═╡ af1161f9-c6d0-409d-b442-3c2c0e7152f7
begin
	function intrinsic_z21_frequencies()
		return frequency_range_with_step(
			intrinsic_z21_scan_start_ghz * GHz,
			intrinsic_z21_scan_stop_ghz * GHz,
			frequency_step_mhz * MHz,
		)
	end

	function run_intrinsic_z21_design(case, design)
		frequencies_hz = intrinsic_z21_frequencies()
		circuit_plan = build_intrinsic_pair_plan(case, design; hb_settings = hb_settings)
		hb = run_sparameter_hb(
			circuit_plan,
			frequencies_hz;
			hb_settings = hb_settings,
			compensate_port_indices = (1, 2),
			removal_intent = :intrinsic_pair_probe_scaffold,
		)
		trace_csv = joinpath(
			intrinsic_z21_trace_dir,
			"set_$(csv_slug(design.target_set_id))__slot_$(csv_slug(design.slot_target_ghz))GHz__z21.csv",
		)
		write_sparameter_trace_csv(trace_csv, hb.result.frequencies_hz, hb.s11, hb.s21, hb.z21, hb.z21_ptc)
		return (
			id = string(design.id),
			case_id = String(design.case_id),
			target_set_id = String(design.target_set_id),
			target_set_name = design.target_set_name,
			slot_target_ghz = design.slot_target_ghz,
			notch_target_ghz = design.notch_target_ghz,
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

	intrinsic_z21_runs = run_intrinsic_z21 ? [
		run_intrinsic_z21_design(selected_case, design)
		for design in best_slot_candidates
	] : NamedTuple[]
	intrinsic_z21_manifest = [
		Base.structdiff(row, NamedTuple{(:frequencies_hz, :s11, :s21, :z21, :z21_ptc)})
		for row in intrinsic_z21_runs
	]
end

# ╔═╡ fd0899d0-6f74-4855-ac51-78d8ac653a69
begin
	write_namedtuple_csv(selected_designs_csv_path, length_handcheck_table)
	run_hb && write_namedtuple_csv(manifest_csv_path, probe_manifest)
	run_intrinsic_z21 && write_namedtuple_csv(intrinsic_z21_manifest_csv_path, intrinsic_z21_manifest)
	output_paths = (
		selected_designs_csv = selected_designs_csv_path,
		manifest_csv = run_hb ? manifest_csv_path : "not written; set run_hb = true",
		intrinsic_z21_manifest_csv = run_intrinsic_z21 ? intrinsic_z21_manifest_csv_path : "not written; set run_intrinsic_z21 = true",
		trace_dir = trace_dir,
		intrinsic_z21_trace_dir = intrinsic_z21_trace_dir,
	)
end

# ╔═╡ 90567ca8-cf2a-4f0f-b958-b07b9ad92be2
begin
	function plots_for_slot(target_set_id, slot_ghz)
		rows = [
			row for row in probe_runs if
			row.target_set_id == String(target_set_id) && row.slot_target_ghz == slot_ghz
		]
		return [
			plot_sparameter_trace(
				row;
				title = "$(row.target_set_name), $(row.slot_target_ghz) GHz, $(row.variant_id)",
			)
			for row in rows
		]
	end

	example_6ghz_ownership_plots = isempty(probe_runs) ? [] : plots_for_slot(:d3, 6.0)
end

# ╔═╡ 2a518b23-d231-447f-8d8d-0dd4ec150cca
begin
	self_check = (
		has_length_rows = length(best_slot_candidates) == 5,
		has_one_d3_set = length(target_slot_sets) == 1 && first(target_slot_sets).id == :d3,
		has_five_variants_per_slot = length(probe_designs) == 5 * length(best_slot_candidates),
		wrote_expected_runs = !run_hb || length(probe_runs) == length(probe_designs),
		wrote_intrinsic_z21_runs = !run_intrinsic_z21 || length(intrinsic_z21_runs) == length(best_slot_candidates),
		all_hb_intents_ok = !run_hb || all(row -> row.hb_intent_ok, probe_runs),
	)
	all(values(self_check)) || error("Coupled-pair probe self-check failed: $(self_check)")
	self_check
end

# ╔═╡ Cell order:
# ╠═4cf0f8d3-fcb2-40c8-8dc6-8a1a5a85d001
# ╠═2385fa9e-c390-41ad-afd6-ad3fa0c8bc06
# ╟─b8719af5-840f-4f9a-ae16-dff6c2fe3eb5
# ╠═6f33b676-3ce7-4862-b6c0-e5754eb8e101
# ╠═08a9233a-ed77-4ef0-a9ca-e1af695c45d1
# ╠═0b63afdf-52aa-4c22-a23b-8210c18e59b9
# ╠═61465ec6-fbb2-476c-a7c9-a2ac333868b5
# ╠═8e0e7f35-d58a-45d3-8764-6b7895c56fda
# ╠═af1161f9-c6d0-409d-b442-3c2c0e7152f7
# ╠═fd0899d0-6f74-4855-ac51-78d8ac653a69
# ╠═90567ca8-cf2a-4f0f-b958-b07b9ad92be2
# ╠═2a518b23-d231-447f-8d8d-0dd4ec150cca
