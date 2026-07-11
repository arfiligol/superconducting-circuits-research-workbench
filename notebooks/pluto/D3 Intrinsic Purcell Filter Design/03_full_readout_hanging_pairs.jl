### A Pluto.jl notebook ###
# v1.0.2

#> [frontmatter]
#> title = "03 D3 Full Readout Hanging Pairs HB Simulation"
#> tags = ["julia-core", "pluto", "d3", "purcell-filter", "shared-readout"]
#> description = "Five-pair D3 shared-readout HB traces for downstream ownership diagnostics."

using Markdown
using InteractiveUtils

# ╔═╡ 3b2b4c37-60f1-43f2-9fc7-ffed2c93d401
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

# ╔═╡ 6baa9cf0-184e-4565-a92f-ccbbec2f9e06
TableOfContents()

# ╔═╡ 97a854f8-fce1-40c4-a17e-509301c87233
md"""
# 03 Full D3 Readout Hanging Paired Resonators HB Simulation

This Pluto notebook builds the full five-pair shared-readout circuit from the
Python-generated length table. Each readout/filter pair has internal MTL
coupling; only the **filter resonator open end** capacitively couples to the
readout line.

This notebook writes solver-returned `S11`/`S21` and raw `Z21` for the loaded
shared-readout circuit. It does not remove the external port shunts. The Python
analysis notebook owns vector-fit and mode-ownership diagnostics only; it does
not fit `$J$`. A future Human-approved workflow must call the reusable calibrated
complex-`$S_{21}$` API through the D3 evaluator.

Interpret this workflow with the canonical [Multiconductor RLGC Matrices](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/transmission-lines/multiconductor-rlgc-matrix-semantics.qmd),
[Loaded-Bare Readout / Filter References](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/readout/loaded-bare-readout-filter-references.qmd),
[Bare vs Hybridized Readout / Filter Modes](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/readout/bare-vs-hybridized-readout-filter-modes.qmd),
[Readout-Filter S21 J Fit](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/readout/readout-filter-s21-j-fit.qmd),
[Harmonic Balance: Periodic Steady State and Mode Semantics](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/numerical-methods/harmonic-balance-periodic-steady-state.qmd),
[Port Reference Impedance Semantics](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/simulation/port-reference-impedance-semantics.qmd),
and [Port-Termination Compensation (PTC)](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/simulation/port-termination-compensation.qmd).
"""

# ╔═╡ 93c2864e-b478-4d17-8cb7-e3bf0156235a
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
	base_design_variant_id = String(d3_design_config["active_design_variant_id"])
	hook_spacing_override = get(ENV, "D3_SHARED_READOUT_HOOK_SPACING_UM", "")
	single_slot_override = get(ENV, "D3_SINGLE_SLOT_GHZ", "")
	variant_parts = String[base_design_variant_id]
	!isempty(hook_spacing_override) && push!(variant_parts, "hook_spacing_$(csv_slug(hook_spacing_override))um")
	!isempty(single_slot_override) && push!(variant_parts, "single_slot_$(csv_slug(single_slot_override))")
	design_variant_id = Symbol(join(variant_parts, "__"))
	design_csv_filename = String(d3_design_config["design_csv_filename"])
	output_suffix = design_variant_id == :baseline ? "" : "__$(csv_slug(design_variant_id))"
	full_output_dir = joinpath(d3_output_dir, "full_readout_hanging_pairs$(output_suffix)")
	design_csv_path = joinpath(d3_output_dir, "design_inputs", design_csv_filename)
	case_json_path = joinpath(orpen_circuit_output_dir, "orpen_q2d_rlgc_cases.json")
	selected_designs_csv_path = joinpath(full_output_dir, "d3_full_selected_designs.csv")
	manifest_csv_path = joinpath(full_output_dir, "d3_full_shared_readout_manifest.csv")
	trace_dir = joinpath(full_output_dir, "traces")

	selected_case_id = Symbol(String(d3_design_config["selected_case_id"]))

	run_hb = true
	frequency_step_mhz = 0.2

	section_length_m = 10.0um
	port_resistance_ohm = 50.0
	feedline_margin_um = Float64(d3_design_config["shared_readout_feedline_margin_um"])
	shared_readout_hook_spacing_um = isempty(hook_spacing_override) ?
		Float64(d3_design_config["shared_readout_hook_spacing_um"]) :
		parse(Float64, hook_spacing_override)
	slot_count_for_feedline = isempty(single_slot_override) ? 5 : 1
	feedline_length_um = 2 * feedline_margin_um + max(slot_count_for_feedline - 1, 0) * shared_readout_hook_spacing_um
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

# ╔═╡ 40717c3d-6fdd-4a41-bad6-87ba8e72c652
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

# ╔═╡ 25b4a213-e82a-4f2f-a4f1-e6b951366487
begin
	best_slot_candidates = read_design_csv(design_csv_path; case_id = selected_case_id)
	if !isempty(single_slot_override)
		single_slot_ghz = parse(Float64, single_slot_override)
		best_slot_candidates = [
			row for row in best_slot_candidates
			if isapprox(row.slot_target_ghz, single_slot_ghz; atol = 1.0e-9)
		]
		length(best_slot_candidates) == 1 || error("D3_SINGLE_SLOT_GHZ=$(single_slot_override) matched $(length(best_slot_candidates)) designs.")
	end
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
			filter_to_line_capacitance_fF = row.filter_to_line_capacitance_fF,
			fr_est_GHz = row.fr_est_ghz,
			fp_est_GHz = row.fp_est_ghz,
			fn_est_GHz = row.fn_est_ghz,
			score = row.analytic_score,
		)
		for row in best_slot_candidates
	]
end

# ╔═╡ 521c4a11-3819-4a75-9d33-7a23bc876c62
begin
	function designs_for_target_set(designs, target_set_id)
		selected = sort(
			[design for design in designs if design.target_set_id == target_set_id];
			by = design -> design.slot_target_ghz,
		)
		expected_count = isempty(single_slot_override) ? 5 : 1
		length(selected) == expected_count || error("Target set $(target_set_id) must have $(expected_count) designs, got $(length(selected)).")
		return selected
	end

	shared_target_sets = [
		(
			target_set_id = slot_set.id,
			target_set_name = String(slot_set.name),
			scan_start_ghz = Float64(slot_set.scan_start_ghz),
			scan_stop_ghz = Float64(slot_set.scan_stop_ghz),
			designs = designs_for_target_set(best_slot_candidates, slot_set.id),
		)
		for slot_set in target_slot_sets
	]
end

# ╔═╡ bf04740d-b32d-43e7-a9f9-7088a5ce9444
begin
	function shared_readout_frequencies(target_set)
		return frequency_range_with_step(
			target_set.scan_start_ghz * GHz,
			target_set.scan_stop_ghz * GHz,
			frequency_step_mhz * MHz,
		)
	end

	function run_shared_target_set(case, target_set)
		frequencies_hz = shared_readout_frequencies(target_set)
		circuit_plan = build_shared_readout_plan(
			case,
			target_set;
			feedline_length_um = feedline_length_um,
			margin_um = feedline_margin_um,
			feedline = feedline_rlgc,
			hb_settings = hb_settings,
		)
		hb = run_sparameter_hb(circuit_plan, frequencies_hz; hb_settings = hb_settings)
		trace_csv = joinpath(
			trace_dir,
			"set_$(csv_slug(target_set.target_set_id))__shared_readout__per_design_capacitance__s.csv",
		)
		write_sparameter_trace_csv(trace_csv, hb.result.frequencies_hz, hb.s11, hb.s21, hb.z21)
			return (
				target_set_id = String(target_set.target_set_id),
				target_set_name = target_set.target_set_name,
				filter_to_line_capacitance_mode = "per_design_required",
			feedline_length_um = feedline_length_um,
			feedline_margin_um = feedline_margin_um,
			shared_readout_hook_spacing_um = shared_readout_hook_spacing_um,
			scan_start_ghz = target_set.scan_start_ghz,
			scan_stop_ghz = target_set.scan_stop_ghz,
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

	shared_readout_runs = run_hb ?
		[run_shared_target_set(selected_case, target_set) for target_set in shared_target_sets] :
		NamedTuple[]
	shared_readout_manifest = [
		Base.structdiff(row, NamedTuple{(:frequencies_hz, :s11, :s21, :z21, :z21_ptc)})
		for row in shared_readout_runs
	]
end

# ╔═╡ ea42597a-c0c9-47f0-b490-0a02b3ece0f3
begin
	write_namedtuple_csv(selected_designs_csv_path, length_handcheck_table)
	run_hb && write_namedtuple_csv(manifest_csv_path, shared_readout_manifest)
	output_paths = (
		selected_designs_csv = selected_designs_csv_path,
		manifest_csv = run_hb ? manifest_csv_path : "not written; set run_hb = true",
		trace_dir = trace_dir,
	)
end

# ╔═╡ 7fef4fed-0538-4a8d-aa2a-a45268d54930
begin
	full_readout_plots = [
		plot_sparameter_trace(
			run;
			title = "$(run.target_set_name), per-design Cext",
		)
		for run in shared_readout_runs
	]
	d3_shared_readout_raw_plot = isempty(full_readout_plots) ? missing : full_readout_plots[1]
end

# ╔═╡ 83ad8bdb-b28c-4792-a859-4193566ca19b
begin
	expected_design_count = isempty(single_slot_override) ? 5 : 1
	self_check = (
		has_length_rows = length(best_slot_candidates) == expected_design_count,
		has_one_d3_set = length(shared_target_sets) == 1 && first(shared_target_sets).target_set_id == :d3,
		has_expected_designs = all(target_set -> length(target_set.designs) == expected_design_count, shared_target_sets),
		wrote_expected_runs = !run_hb || length(shared_readout_runs) == length(shared_target_sets),
		all_hb_intents_ok = !run_hb || all(row -> row.hb_intent_ok, shared_readout_runs),
	)
	all(values(self_check)) || error("Full readout self-check failed: $(self_check)")
	self_check
end

# ╔═╡ Cell order:
# ╠═3b2b4c37-60f1-43f2-9fc7-ffed2c93d401
# ╠═6baa9cf0-184e-4565-a92f-ccbbec2f9e06
# ╟─97a854f8-fce1-40c4-a17e-509301c87233
# ╠═93c2864e-b478-4d17-8cb7-e3bf0156235a
# ╠═40717c3d-6fdd-4a41-bad6-87ba8e72c652
# ╠═25b4a213-e82a-4f2f-a4f1-e6b951366487
# ╠═521c4a11-3819-4a75-9d33-7a23bc876c62
# ╠═bf04740d-b32d-43e7-a9f9-7088a5ce9444
# ╠═ea42597a-c0c9-47f0-b490-0a02b3ece0f3
# ╠═7fef4fed-0538-4a8d-aa2a-a45268d54930
# ╠═83ad8bdb-b28c-4792-a859-4193566ca19b
