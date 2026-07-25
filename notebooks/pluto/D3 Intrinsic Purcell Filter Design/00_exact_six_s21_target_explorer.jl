### A Pluto.jl notebook ###
# v1.0.2

#> [frontmatter]
#> title = "00 D3 Same-Die Exact-Six S21 Target Explorer"
#> tags = ["julia-core", "pluto", "d3", "purcell-filter", "exact-six", "same-die"]
#> description = "Interactive Exact-Six S21 target exploration for the D3 same-C-Chip readout/filter topology."

using Markdown
using InteractiveUtils

# This Pluto notebook uses @bind for interactivity. When running this notebook outside of Pluto, the following 'mock version' of @bind gives bound variables a default value (instead of an error).
macro bind(def, element)
    #! format: off
    return quote
        local iv = try Base.loaded_modules[Base.PkgId(Base.UUID("6e696c72-6542-2067-7265-42206c756150"), "AbstractPlutoDingetjes")].Bonds.initial_value catch; b -> missing; end
        local el = $(esc(element))
        global $(esc(def)) = Core.applicable(Base.get, el) ? Base.get(el) : iv(el)
        el
    end
    #! format: on
end

# ╔═╡ 10e7160e-f3e0-4cc3-9bf8-c125610a30ed
begin
	import Pkg
	Pkg.activate(joinpath(first(DEPOT_PATH), "environments", "v1.12"); io = devnull)

	using LinearAlgebra
	using PlutoUI
	using Printf
	using SuperconductingCircuitsCore
	using SuperconductingCircuitsVisualizer

	JSON3 = SuperconductingCircuitsCore.JSON3
	figure_config = PlotlyFigureConfig(download_filename = splitext(basename(@__FILE__))[1])
	wide_figure_cell = WideCell(;
		max_width = max(1000, something(figure_config.display_width_px, 1000) + 80),
	)

	include(joinpath(@__DIR__, "d3_purcell_common.jl"))
	include(joinpath(@__DIR__, "d3_floating_qubit_input.jl"))
	include(joinpath(@__DIR__, "d3_forward_validation_common.jl"))
	include(joinpath(@__DIR__, "d3_forward_response_common.jl"))
	include(joinpath(@__DIR__, "d3_forward_execution.jl"))
end

# ╔═╡ aa73e95b-717e-4c90-961d-cbac903a2dd0
TableOfContents()

# ╔═╡ a5e8fb8c-8683-418e-b06f-4e02e6f65562
md"""
# D3 Same-Die Exact-Six `S21` Target Explorer

This notebook explores the **same-die D3 Design Target**: readout coordinate
`r` and filter coordinate `p` are both realized on the C-Chip (`D0/top`). The
opposing Q-Chip (`D1/bottom`) remains part of the electromagnetic environment,
but it does not own either resonator in this target.

The separate cross-die target—one resonator on each chip—must supply its own
input artifact and closure evidence. Its parameters are not interchangeable
with this notebook's output.

The exact matched-port formula uses the six coordinates

\$\$
(q,r,p,f_1,f_c,f_2),
\$\$

\$\$
\mathcal D_6(\omega)
=\mathbf K_6-\omega^2\mathbf C_6
-i\omega\mathbf B\mathbf Y_0\mathbf B^T,
\$\$

\$\$
\mathbf S(\omega)
=-\mathbf I-2i\omega\mathbf Y_0^{1/2}
\mathbf B^T\mathcal D_6^{-1}(\omega)
\mathbf B\mathbf Y_0^{1/2},
\qquad S_{21}=[\mathbf S]_{21},
\$\$

under the `exp(-iωt)` convention. The calibrated trace is the pointwise
complex ratio of the full response to the same two-`π` empty feedline.

The downloaded snapshot is a **candidate analytical target**, not a promoted
equivalent circuit or Layout. Validate it in order:

```text
Exact-Six analytical target
  -> finite equivalent circuit closure
  -> distributed/lumped hybrid-circuit closure
  -> same-die C-Chip Layout replay
```
"""

# ╔═╡ 45e8871a-1ff3-4395-9d57-58ba22ec0ee6
md"""
## Required real inputs

This notebook deliberately has no synthetic fallback. It reads the completed
same-die forward-search sidecar for response-matched `R/P/N` elements and the
workspace-private open-side Maxwell input for the six physical branch
capacitances. Missing inputs fail loudly.
"""

# ╔═╡ b73cfc8d-6f58-4706-8b8a-93b25e617805
begin
	workbench_root = normpath(joinpath(@__DIR__, "..", "..", ".."))
	workspace_root = normpath(joinpath(workbench_root, ".."))
	design_config = load_d3_design_config()
	search_evidence_path = joinpath(
		workbench_root,
		"build",
		"research",
		"d3_forward_circuit_validation_v2",
		"d3-forward-circuit-run.v2.search-evidence.json",
	)
	qubit_input_path = joinpath(
		workspace_root,
		String(design_config["floating_qubit_nominal_workspace_path"]),
	)
	isfile(search_evidence_path) || error(
		"Missing completed same-die D3 search evidence: $(search_evidence_path)",
	)
	isfile(qubit_input_path) || error(
		"Missing workspace-private D3 floating-qubit input: $(qubit_input_path)",
	)

	search_evidence = JSON3.read(read(search_evidence_path, String), Dict{String,Any})
	search_evidence["schema_version"] == "d3-forward-design-search-evidence.v1" || error(
		"D3 search-evidence schema is incompatible.",
	)
	search_evidence["status"] == "complete" || error(
		"D3 search evidence must be complete before it can seed target exploration.",
	)
	selected_candidates = Dict(
		Float64(candidate["slot_hz"]) => candidate
		for candidate in search_evidence["candidates"]
		if candidate["selected"] === true
	)
	Set(keys(selected_candidates)) == Set(D3_FORWARD_SLOT_HZ) || error(
		"D3 search evidence must contain one selected candidate for every canonical Slot.",
	)

	qubit_input = D3FloatingQubitInput.load_floating_qubit_nominal_input(
		qubit_input_path,
		D3FloatingQubitNominal,
		require_open_side_contract = true,
	)
	base_feedline = load_d3_feedline_rlgc(design_config)
end

# ╔═╡ 141c108c-dbaa-4e4f-987d-b095f8bf587f
md"""
## Baseline Slot

$(@bind slot_ghz Slider(D3_FORWARD_SLOT_HZ ./ 1.0e9; default = 6.0, show_value = true))

Changing the Slot loads that Slot's completed same-die candidate as the center
of every model-parameter Slider.
"""

# ╔═╡ 8a8cc366-871f-4cb9-b9bf-b3589395dc94
begin
	baseline_candidate = selected_candidates[Float64(slot_ghz) * 1.0e9]
	baseline_parameters = baseline_candidate["parameters"]
	baseline_qubit = qubit_input.model

	function centered_values(base; lower_scale = 0.5, upper_scale = 1.5, count = 201)
		value = Float64(base)
		value > 0 || error("Slider baseline must be positive.")
		return collect(range(lower_scale * value, upper_scale * value; length = count))
	end

	function bounded_values(base, lower, upper; count = 201)
		value = Float64(base)
		lower < value < upper || error("Bounded Slider baseline must lie inside its range.")
		return vcat(
			collect(range(Float64(lower), value; length = (count + 1) ÷ 2)),
			collect(range(value, Float64(upper); length = (count + 1) ÷ 2))[2:end],
		)
	end
end

# ╔═╡ bd9eb625-d00d-4f99-9ee2-414c1ad74147
md"""
## Floating-Qubit Parameters

Each value is a positive physical branch parameter. `L_J` is per junction for
two identical parallel linearized Josephson branches.

| Parameter | Slider |
| --- | --- |
| `C01` (fF) | $(@bind c01_fF Slider(centered_values(baseline_qubit.C01_fF); default = baseline_qubit.C01_fF, show_value = true)) |
| `C02` (fF) | $(@bind c02_fF Slider(centered_values(baseline_qubit.C02_fF); default = baseline_qubit.C02_fF, show_value = true)) |
| `C12` (fF) | $(@bind c12_fF Slider(centered_values(baseline_qubit.C12_fF); default = baseline_qubit.C12_fF, show_value = true)) |
| `Cr1` (fF) | $(@bind cr1_fF Slider(centered_values(baseline_qubit.Cr1_fF); default = baseline_qubit.Cr1_fF, show_value = true)) |
| `Cr2` (fF) | $(@bind cr2_fF Slider(centered_values(baseline_qubit.Cr2_fF); default = baseline_qubit.Cr2_fF, show_value = true)) |
| `C0r` local open-side shunt (fF) | $(@bind c0r_fF Slider(centered_values(baseline_qubit.C0r_fF); default = baseline_qubit.C0r_fF, show_value = true)) |
| `LJ` per junction (nH) | $(@bind lj_per_junction_nH Slider(centered_values(baseline_qubit.L_J_per_junction_nH; lower_scale = 0.7, upper_scale = 1.3); default = baseline_qubit.L_J_per_junction_nH, show_value = true)) |
"""

# ╔═╡ fde4af0c-af63-44e7-a6db-5c7bde8c1710
md"""
## Response-Matched Equivalent Elements

These six values define the readout, filter, and interference branches consumed
by the Exact-Six matrices.

| Parameter | Slider |
| --- | --- |
| `Cr` (fF) | $(@bind cr_fF Slider(centered_values(1.0e15 * Float64(baseline_parameters["response_match_Cr_f"])); default = 1.0e15 * Float64(baseline_parameters["response_match_Cr_f"]), show_value = true)) |
| `Lr` (nH) | $(@bind lr_nH Slider(centered_values(1.0e9 * Float64(baseline_parameters["response_match_Lr_h"])); default = 1.0e9 * Float64(baseline_parameters["response_match_Lr_h"]), show_value = true)) |
| `Cp` (fF) | $(@bind cp_fF Slider(centered_values(1.0e15 * Float64(baseline_parameters["response_match_Cp_f"])); default = 1.0e15 * Float64(baseline_parameters["response_match_Cp_f"]), show_value = true)) |
| `Lp` (nH) | $(@bind lp_nH Slider(centered_values(1.0e9 * Float64(baseline_parameters["response_match_Lp_h"])); default = 1.0e9 * Float64(baseline_parameters["response_match_Lp_h"]), show_value = true)) |
| `Cn` (fF) | $(@bind cn_fF Slider(centered_values(1.0e15 * Float64(baseline_parameters["response_match_Cn_f"])); default = 1.0e15 * Float64(baseline_parameters["response_match_Cn_f"]), show_value = true)) |
| `Ln` (nH) | $(@bind ln_nH Slider(centered_values(1.0e9 * Float64(baseline_parameters["response_match_Ln_h"])); default = 1.0e9 * Float64(baseline_parameters["response_match_Ln_h"]), show_value = true)) |
"""

# ╔═╡ 42cc6054-8c0f-4bfb-8f6f-31cd10c525fb
md"""
## Feedline And Interface Parameters

The characteristic impedance and phase velocity uniquely determine
`L′ = Zchar/v` and `C′ = 1/(Zchar v)`. The matched port reference remains the
fixed model condition `Z0 = 50 Ω`.

| Parameter | Slider |
| --- | --- |
| `Cext` (fF) | $(@bind cext_fF Slider(centered_values(1.0e15 * Float64(baseline_parameters["cext_f"]); lower_scale = 0.25, upper_scale = 2.0); default = 1.0e15 * Float64(baseline_parameters["cext_f"]), show_value = true)) |
| Feedline length (\u00b5m) | $(@bind feedline_length_um Slider(centered_values(1000.0; lower_scale = 0.5, upper_scale = 1.5); default = 1000.0, show_value = true)) |
| `Zchar` (\u03a9) | $(@bind feedline_zchar_ohm Slider(bounded_values(base_feedline.zo_ohm, 49.75, 50.25); default = base_feedline.zo_ohm, show_value = true)) |
| Phase velocity (`10^8` m/s) | $(@bind feedline_velocity_1e8_m_per_s Slider(centered_values(base_feedline.velocity_m_per_s / 1.0e8; lower_scale = 0.8, upper_scale = 1.2); default = base_feedline.velocity_m_per_s / 1.0e8, show_value = true)) |
"""

# ╔═╡ 74faf414-1957-403e-aa96-ce7541445331
md"""
## View Controls

| Control | Slider |
| --- | --- |
| Start frequency (GHz) | $(@bind scan_start_ghz Slider(3.5:0.05:5.0; default = 4.0, show_value = true)) |
| Stop frequency (GHz) | $(@bind scan_stop_ghz Slider(6.5:0.05:8.0; default = 7.2, show_value = true)) |

The port selector, two-`π` feedline topology, `Z0 = 50 Ω` port reference, and
lossless `R′ = G′ = 0` scope are fixed model-contract conditions rather than
design parameters. Changing one creates a different analytical model and is
therefore not exposed as a Slider here.
"""

# ╔═╡ d10b4e13-f48c-4eef-9e90-59efffb6841f
begin
	interactive_qubit = D3FloatingQubitNominal(
		model_id = "d3-same-die-exact-six-interactive-candidate",
		capacitance_source_id = qubit_input.input_sha256,
		C01_fF = c01_fF,
		C02_fF = c02_fF,
		C12_fF = c12_fF,
		Cr1_fF = cr1_fF,
		Cr2_fF = cr2_fF,
		C0r_fF = c0r_fF,
		L_J_per_junction_nH = lj_per_junction_nH,
		electrostatic_reduction = nothing,
	)
	interactive_elements = (
		Cr_f = Float64(cr_fF) * 1.0e-15,
		Lr_h = Float64(lr_nH) * 1.0e-9,
		Cp_f = Float64(cp_fF) * 1.0e-15,
		Lp_h = Float64(lp_nH) * 1.0e-9,
		Cn_f = Float64(cn_fF) * 1.0e-15,
		Ln_h = Float64(ln_nH) * 1.0e-9,
	)
	feedline_velocity_m_per_s = Float64(feedline_velocity_1e8_m_per_s) * 1.0e8
	interactive_feedline = D3FeedlineRLGC(
		source = "interactive transform of $(base_feedline.source)",
		extraction_frequency_hz = base_feedline.extraction_frequency_hz,
		l_per_m_h = Float64(feedline_zchar_ohm) / feedline_velocity_m_per_s,
		c_per_m_f = 1 / (Float64(feedline_zchar_ohm) * feedline_velocity_m_per_s),
		r_per_m_ohm = 0.0,
		g_per_m_s = 0.0,
		r_status = "unavailable_in_source",
		g_status = "unavailable_in_source",
		loss_assumption = "r_and_g_assumed_zero_for_lossless_exploration_only",
		target_impedance_ohm = 50.0,
		max_abs_impedance_error_ohm = 0.25,
		max_abs_impedance_error_role = "mismatch_screening_only",
	)
	feedline_length_m = Float64(feedline_length_um) * 1.0e-6
	cext_f = Float64(cext_fF) * 1.0e-15
	Float64(scan_start_ghz) < Float64(scan_stop_ghz) || error(
		"S21 view start frequency must be below its stop frequency.",
	)
	frequency_hz = collect(range(
		Float64(scan_start_ghz) * 1.0e9,
		Float64(scan_stop_ghz) * 1.0e9;
		length = 1601,
	))
end

# ╔═╡ 69c67d97-c7cc-48d4-81c9-68e711372f58
begin
	exact_six = d3_forward_exact_six_trace(
		interactive_elements,
		interactive_qubit,
		interactive_feedline,
		feedline_length_m,
		cext_f,
		frequency_hz,
	)
	reference = _d3_forward_response_trace(
		_d3_forward_feedline_reference_plan(
			(id = :d3_same_die_exact_six_target_explorer,);
			section_length_m = feedline_length_m / 2,
			feedline = interactive_feedline,
			feedline_length_m = feedline_length_m,
		),
		frequency_hz;
		z_closure_absolute_tolerance_ohm = D3_FORWARD_Z_CLOSURE_ABSOLUTE_TOLERANCE_OHM,
		s_closure_absolute_tolerance = D3_FORWARD_S_CLOSURE_ABSOLUTE_TOLERANCE,
		closure_relative_tolerance = D3_FORWARD_CLOSURE_RELATIVE_TOLERANCE,
	)
	calibration = _d3_forward_calibrate_s21(
		exact_six.s21,
		exact_six.s21,
		reference.s21,
		0.5,
	)
	calibrated_s21 = calibration.equivalent_s21
end

# ╔═╡ 6541dc0f-646c-4246-a66a-ad71b1461bba
begin
	s_parameter_db_magnitude_figure(
		frequency_hz,
		[
			"Exact-Six raw S21" => exact_six.s21,
			"Exact-Six calibrated S21" => calibrated_s21,
		];
		title = "D3 Same-Die Exact-Six Through-Transmission",
		config = figure_config,
	)
end |> wide_figure_cell

# ╔═╡ 00957fef-4f09-4dfc-9462-05e19960225b
begin
	s_parameter_phase_figure(
		frequency_hz,
		[
			"Exact-Six raw S21" => exact_six.s21,
			"Exact-Six calibrated S21" => calibrated_s21,
		];
		title = "D3 Same-Die Exact-Six Through-Transmission Phase",
		unit = :deg,
		config = figure_config,
	)
end |> wide_figure_cell

# ╔═╡ 694d70b8-1f3b-4c95-961b-09e2fd94cc41
begin
	qubit_layers = floating_qubit_capacitance_layers(interactive_qubit)
	format_general(value) = @sprintf("%.9g", value)
	format_frequency(value) = @sprintf("%.9f", value)
	parameter_rows = [
		("C01", c01_fF, "fF"),
		("C02", c02_fF, "fF"),
		("C12", c12_fF, "fF"),
		("Cr1", cr1_fF, "fF"),
		("Cr2", cr2_fF, "fF"),
		("LJ_per_junction", lj_per_junction_nH, "nH"),
		("Cr", cr_fF, "fF"),
		("Lr", lr_nH, "nH"),
		("Cp", cp_fF, "fF"),
		("Lp", lp_nH, "nH"),
		("Cn", cn_fF, "fF"),
		("Ln", ln_nH, "nH"),
		("Cext", cext_fF, "fF"),
		("feedline_length", feedline_length_um, "um"),
		("feedline_Zchar", feedline_zchar_ohm, "ohm"),
		("feedline_phase_velocity", feedline_velocity_m_per_s, "m/s"),
	]
	parameter_table = join(
		vcat(
			["| Parameter | Value | Unit |", "| --- | ---: | --- |"],
			["| `$(name)` | $(format_general(value)) | $(unit) |" for (name, value, unit) in parameter_rows],
		),
		"\n",
	)
	pole_table = join(
		vcat(
			["| Pole | Frequency (GHz) | Linewidth (MHz) |", "| ---: | ---: | ---: |"],
			[
				"| $(index) | $(format_frequency(real(pole) / 1.0e9)) | $(format_frequency(exact_six.poles.linewidths_hz[index] / 1.0e6)) |"
				for (index, pole) in enumerate(exact_six.poles.frequencies_hz)
			],
		),
		"\n",
	)
	Markdown.parse("""
	## Current Candidate Parameters

	$(parameter_table)

	Derived qubit capacitance layers: `Cq_LB = $(format_general(qubit_layers.Cq_LB_fF)) fF`,
	`Cdr = $(format_general(qubit_layers.Cdr_physical_fF)) fF`, and
	`Cr_attach_LB = $(format_general(qubit_layers.Cr_attach_LB_fF)) fF`.

	## Exact-Six Open Poles

	$(pole_table)
	""")
end

# ╔═╡ b9e393af-b138-419b-8880-55ea2dc51d9e
begin
	complex_samples(values) = [
		[real(value), imag(value)]
		for value in values
	]
	target_snapshot = Dict(
		"schema_version" => "d3-exact-six-analytical-target-snapshot.v1",
		"status" => "candidate_not_promoted",
		"design_target_id" => "d3-same-die-intrinsic-interferometric-purcell-filter",
		"implementation_topology" => Dict(
			"id" => "same-die-c-chip-readout-filter-v1",
			"readout_die" => "C-Chip/D0/top",
			"filter_die" => "C-Chip/D0/top",
			"opposing_environment_die" => "Q-Chip/D1/bottom",
		),
		"slot_hz" => Float64(slot_ghz) * 1.0e9,
		"coordinate_order" => exact_six.coordinate_order,
		"time_convention" => "exp(-i*omega*t)",
		"port_reference_impedance_ohm" => exact_six.reference_impedance_ohm,
		"parameters" => Dict(
			name => Dict("value" => Float64(value), "unit" => unit)
			for (name, value, unit) in parameter_rows
		),
		"derived_qubit_capacitance_layers_fF" => Dict(
			"Cq_LB" => qubit_layers.Cq_LB_fF,
			"Cdr_physical" => qubit_layers.Cdr_physical_fF,
			"Cr_attach_LB" => qubit_layers.Cr_attach_LB_fF,
		),
		"capacitance_matrix_f" => [collect(row) for row in eachrow(exact_six.capacitance)],
		"inverse_inductance_matrix_h_inv" => [
			collect(row) for row in eachrow(exact_six.inverse_inductance)
		],
		"port_selector" => [collect(row) for row in eachrow(exact_six.selector)],
		"open_poles" => [
			Dict(
				"frequency_real_hz" => real(pole),
				"frequency_imag_hz" => imag(pole),
				"total_linewidth_hz" => exact_six.poles.linewidths_hz[index],
			)
			for (index, pole) in enumerate(exact_six.poles.frequencies_hz)
		],
		"s21_view" => Dict(
			"frequency_start_hz" => first(frequency_hz),
			"frequency_stop_hz" => last(frequency_hz),
			"sample_count" => length(frequency_hz),
			"calibration" => calibration.provenance,
		),
		"s21_samples" => Dict(
			"frequency_hz" => frequency_hz,
			"complex_component_order" => ["real", "imaginary"],
			"raw" => complex_samples(exact_six.s21),
			"same_two_pi_feedline_reference" => complex_samples(reference.s21),
			"calibrated" => complex_samples(calibrated_s21),
		),
		"seed_provenance" => Dict(
			"selected_candidate_id" => baseline_candidate["candidate_id"],
			"search_evidence_path" => relpath(search_evidence_path, workbench_root),
			"qubit_input_sha256" => qubit_input.input_sha256,
			"feedline_source" => base_feedline.source,
		),
		"required_next_checks" => [
			"finite_equivalent_circuit_complex_s21_z21_and_open_pole_closure",
			"distributed_lumped_hybrid_circuit_closure",
			"same_die_c_chip_layout_replay",
			"human_promotion",
		],
	)
	target_json = sprint(io -> JSON3.pretty(io, target_snapshot))
end

# ╔═╡ b8048581-4fa7-4a86-bcd0-a9c913efc326
md"""
## Candidate Handoff

The snapshot preserves units, topology identity, the exact `C6` and
`K6` matrices, port selector, derived open poles, calibration
semantics, and required next checks. Downloading it does not promote the
candidate.

$(
	DownloadButton(
		target_json,
		"d3_same_die_exact_six_target_$(replace(string(slot_ghz), "." => "p"))GHz.json",
	)
)
"""

# ╔═╡ 3cc67754-db27-40d9-ab05-cb258a064fa4
begin
	sanity = (
		topology_is_same_die =
			target_snapshot["implementation_topology"]["readout_die"] ==
			target_snapshot["implementation_topology"]["filter_die"],
		capacitance_is_positive_definite = isposdef(Symmetric(exact_six.capacitance)),
		five_positive_open_poles = length(exact_six.poles.frequencies_hz) == 5,
		finite_raw_s21 = all(value -> isfinite(real(value)) && isfinite(imag(value)), exact_six.s21),
		finite_calibrated_s21 = all(
			value -> isfinite(real(value)) && isfinite(imag(value)),
			calibrated_s21,
		),
		calibration_reference_safe = calibration.minimum_observed_reference_magnitude >= 0.5,
	)
	all(values(sanity)) || error("D3 Exact-Six interactive target sanity check failed: $(sanity)")
	sanity
end

# ╔═╡ Cell order:
# ╠═10e7160e-f3e0-4cc3-9bf8-c125610a30ed
# ╠═aa73e95b-717e-4c90-961d-cbac903a2dd0
# ╟─a5e8fb8c-8683-418e-b06f-4e02e6f65562
# ╟─45e8871a-1ff3-4395-9d57-58ba22ec0ee6
# ╠═b73cfc8d-6f58-4706-8b8a-93b25e617805
# ╟─141c108c-dbaa-4e4f-987d-b095f8bf587f
# ╠═8a8cc366-871f-4cb9-b9bf-b3589395dc94
# ╟─bd9eb625-d00d-4f99-9ee2-414c1ad74147
# ╟─fde4af0c-af63-44e7-a6db-5c7bde8c1710
# ╟─42cc6054-8c0f-4bfb-8f6f-31cd10c525fb
# ╟─74faf414-1957-403e-aa96-ce7541445331
# ╠═d10b4e13-f48c-4eef-9e90-59efffb6841f
# ╠═69c67d97-c7cc-48d4-81c9-68e711372f58
# ╠═6541dc0f-646c-4246-a66a-ad71b1461bba
# ╠═00957fef-4f09-4dfc-9462-05e19960225b
# ╠═694d70b8-1f3b-4c95-961b-09e2fd94cc41
# ╠═b9e393af-b138-419b-8880-55ea2dc51d9e
# ╟─b8048581-4fa7-4a86-bcd0-a9c913efc326
# ╠═3cc67754-db27-40d9-ab05-cb258a064fa4
