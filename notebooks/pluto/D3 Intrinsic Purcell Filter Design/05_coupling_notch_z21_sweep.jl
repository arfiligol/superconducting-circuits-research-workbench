### A Pluto.jl notebook ###
# v1.0.2

#> [frontmatter]
#> title = "05 D3 Coupling And Notch Z21 Sweep"
#> tags = ["julia-core", "d3", "purcell-filter", "z21", "sweep"]
#> description = "PTC Z21 sweeps over MTL coupling length and short-side length."

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
# 05 Coupling And Notch Z21 Sweep

This notebook keeps the CPW/Q2D spec fixed, then sweeps:

- `lc_um`: MTL coupling-window length, a first-order geometry knob expected to
  influence `$J$`; the Z21 peak split produced here is not a `$J$` measurement.
- `short_side_delta_um`: common offset added to both short-side lengths, the
  first-order notch correction knob.

Open-side lengths are adjusted to preserve each resonator total length while
the sweep runs. That keeps this notebook focused on the coupling/notch knobs
instead of mixing in a large bare-frequency retune.

Python analysis reads the CSV traces and ranks geometry seeds for the later
complex-S21 evaluator. This sweep does not promote `$J$` evidence.

Interpret this workflow with the canonical [Multiconductor RLGC Matrices](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/transmission-lines/multiconductor-rlgc-matrix-semantics.qmd),
[Bare vs Hybridized Readout / Filter Modes](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/readout/bare-vs-hybridized-readout-filter-modes.qmd),
[Readout-Filter S21 J Fit](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/readout/readout-filter-s21-j-fit.qmd),
[Harmonic Balance: Periodic Steady State and Mode Semantics](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/numerical-methods/harmonic-balance-periodic-steady-state.qmd),
[Port Reference Impedance Semantics](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/simulation/port-reference-impedance-semantics.qmd),
and [Port-Termination Compensation (PTC)](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/simulation/port-termination-compensation.qmd).
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
	design_variant_id = Symbol(String(d3_design_config["active_design_variant_id"]))
	output_suffix = "__$(csv_slug(design_variant_id))"
	sweep_output_dir = joinpath(d3_output_dir, "coupling_notch_z21_sweep$(output_suffix)")
	trace_dir = joinpath(sweep_output_dir, "traces")
	manifest_csv_path = joinpath(sweep_output_dir, "d3_coupling_notch_z21_sweep_manifest.csv")
	setup_csv_path = joinpath(sweep_output_dir, "d3_coupling_notch_z21_sweep_setup.csv")
	design_csv_path = joinpath(d3_output_dir, "design_inputs", "d3_selected_resonator_lengths$(output_suffix).csv")
	case_json_path = joinpath(orpen_circuit_output_dir, "orpen_q2d_rlgc_cases.json")

	selected_case_id = Symbol(String(d3_design_config["selected_case_id"]))
	representative_slot_ghz = 6.0
	run_hb = true
	frequency_step_mhz = 1.0
	z21_scan_start_ghz = 4.0
	z21_scan_stop_ghz = 7.4
	open_side_compensation_mode = :preserve_total_length

	lc_sweep_um = [10.0, 20.0, 30.0, 40.0, 60.0, 80.0, 120.0, 160.0, 200.0]
	short_side_delta_sweep_um = [-100.0, 0.0, 100.0, 200.0, 300.0]
	candidate_setups = [
		(name = "lc200_notch4500_interp", lc_um = 200.0, short_side_delta_um = -35.15625),
		(name = "lc160_notch4500_interp", lc_um = 160.0, short_side_delta_um = -9.160305),
	]

	section_length_m = 10.0um
	port_resistance_ohm = 50.0
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

# ╔═╡ load_inputs
begin
	orpen_cases = load_orpen_cases(case_json_path)
	selected_case = only([case for case in orpen_cases if case.id == selected_case_id])
	base_designs = read_design_csv(design_csv_path; case_id = selected_case_id)
	representative_design = only([row for row in base_designs if isapprox(row.slot_target_ghz, representative_slot_ghz; atol = 1.0e-9)])
end

# ╔═╡ setup_table
begin
	setup_rows = [
		(
			case_id = String(selected_case.id),
			flip_chip_gap_height_um = selected_case.height_um,
			mtl_horizontal_offset_um = selected_case.mtl_point["horizontal_offset_um"],
			mtl_trace_gap_um = selected_case.mtl_point["trace_gap_um"],
			mtl_central_width_um = selected_case.mtl_point["central_width_um"],
			single_horizontal_offset_um = selected_case.single_trace_point["horizontal_offset_um"],
			single_trace_gap_um = selected_case.single_trace_point["trace_gap_um"],
			single_central_width_um = selected_case.single_trace_point["central_width_um"],
			Zm_ohm = selected_case.zm_ohm,
			single_Zo_effective_ohm = selected_case.zo_effective_ohm,
			mtl_diagonal_Zo_ohm = selected_case.mtl_diag_zo_ohm,
			single_velocity_m_per_s = selected_case.single_velocity_m_per_s,
			mtl_diagonal_velocity_m_per_s = selected_case.mtl_diag_velocity_m_per_s,
			base_lr_short_um = representative_design.lr_short_um,
			base_lp_short_um = representative_design.lp_short_um,
			base_lc_um = representative_design.lc_um,
			base_lr_open_um = representative_design.lr_open_um,
			base_lp_open_um = representative_design.lp_open_um,
			base_lr_total_um = representative_design.lr_total_um,
			base_lp_total_um = representative_design.lp_total_um,
			open_side_compensation_mode = String(open_side_compensation_mode),
			z21_scan_start_ghz = z21_scan_start_ghz,
			z21_scan_stop_ghz = z21_scan_stop_ghz,
			frequency_step_mhz = frequency_step_mhz,
		),
	]
	write_namedtuple_csv(setup_csv_path, setup_rows)
end

# ╔═╡ sweep_designs
begin
	function z21_sweep_design(design; sweep_id, lc_um, short_side_delta_um)
		lr_short_um = design.lr_short_um + Float64(short_side_delta_um)
		lp_short_um = design.lp_short_um + Float64(short_side_delta_um)
		lc_value_um = Float64(lc_um)
		if open_side_compensation_mode == :preserve_total_length
			lr_open_um = design.lr_total_um - lr_short_um - lc_value_um
			lp_open_um = design.lp_total_um - lp_short_um - lc_value_um
			lr_total_um = design.lr_total_um
			lp_total_um = design.lp_total_um
		elseif open_side_compensation_mode == :fixed_open_side
			lr_open_um = design.lr_open_um
			lp_open_um = design.lp_open_um
			lr_total_um = lr_short_um + lc_value_um + lr_open_um
			lp_total_um = lp_short_um + lc_value_um + lp_open_um
		else
			error("Unsupported open_side_compensation_mode=$(open_side_compensation_mode).")
		end
		min(lr_short_um, lp_short_um, lc_value_um, lr_open_um, lp_open_um) > 0 || error("Invalid sweep lengths.")
		return merge(
			design,
			(
				id = Symbol("$(design.id)__$(sweep_id)"),
				sweep_id = Symbol(sweep_id),
				open_side_compensation_mode = String(open_side_compensation_mode),
				lc_um = lc_value_um,
				short_side_delta_um = Float64(short_side_delta_um),
				lr_short_um = lr_short_um,
				lp_short_um = lp_short_um,
				lr_open_um = lr_open_um,
				lp_open_um = lp_open_um,
				lr_total_um = lr_total_um,
				lp_total_um = lp_total_um,
				notch_length_um = lr_short_um + lc_value_um + lp_short_um,
			),
		)
	end

	coarse_sweep_designs = [
		z21_sweep_design(
			representative_design;
			sweep_id = "coarse_lc$(csv_slug(lc_um))_ds$(csv_slug(short_delta_um))",
			lc_um = lc_um,
			short_side_delta_um = short_delta_um,
		)
		for lc_um in lc_sweep_um
		for short_delta_um in short_side_delta_sweep_um
	]

	candidate_sweep_designs = [
		z21_sweep_design(
			design;
			sweep_id = "candidate_$(csv_slug(setup.name))",
			lc_um = setup.lc_um,
			short_side_delta_um = setup.short_side_delta_um,
		)
		for setup in candidate_setups
		for design in base_designs
	]

	sweep_designs_to_run = vcat(coarse_sweep_designs, candidate_sweep_designs)
end

# ╔═╡ run_sweep
begin
	function sweep_frequencies()
		return frequency_range_with_step(z21_scan_start_ghz * GHz, z21_scan_stop_ghz * GHz, frequency_step_mhz * MHz)
	end

	function run_z21_sweep_design(case, design)
		frequencies_hz = sweep_frequencies()
		circuit_plan = build_intrinsic_pair_plan(case, design; hb_settings = hb_settings)
		hb = run_sparameter_hb(
			circuit_plan,
			frequencies_hz;
			hb_settings = hb_settings,
			compensate_port_indices = (1, 2),
			removal_intent = :intrinsic_pair_probe_scaffold,
		)
		trace_csv = joinpath(
			trace_dir,
			"slot_$(csv_slug(design.slot_target_ghz))GHz__$(csv_slug(design.sweep_id))__z21.csv",
		)
		write_sparameter_trace_csv(trace_csv, hb.result.frequencies_hz, hb.s11, hb.s21, hb.z21, hb.z21_ptc)
		return (
			sweep_id = String(design.sweep_id),
			target_set_id = String(design.target_set_id),
			target_set_name = design.target_set_name,
			case_id = String(design.case_id),
			slot_target_ghz = design.slot_target_ghz,
			notch_target_ghz = design.notch_target_ghz,
			open_side_compensation_mode = design.open_side_compensation_mode,
			lc_um = design.lc_um,
			short_side_delta_um = design.short_side_delta_um,
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

	sweep_runs = run_hb ? [run_z21_sweep_design(selected_case, design) for design in sweep_designs_to_run] : NamedTuple[]
	write_namedtuple_csv(manifest_csv_path, sweep_runs)
end

# ╔═╡ outputs
md"""
Wrote:

- `$(setup_csv_path)`
- `$(manifest_csv_path)`
- trace CSVs under `$(trace_dir)`
"""
