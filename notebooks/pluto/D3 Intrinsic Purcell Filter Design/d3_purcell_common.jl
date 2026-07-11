# This file holds the shared low-level circuit and CSV helpers for the D3
# intrinsic Purcell filter notebooks. The notebooks own the readable workflow
# cells; this include keeps the repeated HB plumbing in one place.
# Canonical harmonic-balance method and evidence semantics:
# https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/numerical-methods/harmonic-balance-periodic-steady-state.qmd
# Canonical network-observable semantics:
# https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/network-trace-views.qmd
# https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/simulation/port-reference-impedance-semantics.qmd
# https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/simulation/port-termination-compensation.qmd
# https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/transmission-lines/multiconductor-rlgc-matrix-semantics.qmd
# The current OrPen loader validates only the fields present in the legacy
# LC-only exploration envelope. It does not grant artifact eligibility or
# design-evidence status.

import DelimitedFiles

const D3_METERS_PER_UM = 1.0e-6
const D3_HZ_PER_GHZ = 1.0e9
const D3_FARADS_PER_FF = 1.0e-15
const D3_HENRIES_PER_NH = 1.0e-9

"""Reduced passive small-signal model for one symmetric floating qubit.

The five capacitances are positive physical branch values, not signed Maxwell
matrix entries. `L_J_per_junction_nH` is the inductance of each of two
identical parallel linearized Josephson branches. This type intentionally does
not model flux, junction asymmetry, loop inductance, or omitted matrix terms.
"""
struct D3FloatingQubitNominal
	model_id::String
	capacitance_source_id::String
	C01_fF::Float64
	C02_fF::Float64
	C12_fF::Float64
	Cr1_fF::Float64
	Cr2_fF::Float64
	L_J_per_junction_nH::Float64

	function D3FloatingQubitNominal(;
		model_id,
		capacitance_source_id,
		C01_fF,
		C02_fF,
		C12_fF,
		Cr1_fF,
		Cr2_fF,
		L_J_per_junction_nH,
	)
		model = strip(String(model_id))
		source = strip(String(capacitance_source_id))
		isempty(model) && error("Floating-qubit nominal model_id must be nonempty.")
		isempty(source) && error("Floating-qubit capacitance_source_id must be nonempty.")
		values = Float64[C01_fF, C02_fF, C12_fF, Cr1_fF, Cr2_fF, L_J_per_junction_nH]
		all(value -> isfinite(value) && value > 0, values) || error(
			"Floating-qubit capacitances and per-junction L_J must be finite and positive.",
		)
		return new(model, source, values...)
	end
end

function add_floating_qubit_nominal!(circuit_plan, readout_open_tail, qubit::D3FloatingQubitNominal; id_prefix = "floating_qubit")
	prefix = strip(String(id_prefix))
	isempty(prefix) && error("Floating-qubit id_prefix must be nonempty.")
	island1 = external_node("$(prefix)_island_1")
	island2 = external_node("$(prefix)_island_2")
	shunt_capacitor!(
		circuit_plan;
		id = "$(prefix)_C01",
		at = island1,
		capacitance = qubit.C01_fF * D3_FARADS_PER_FF,
		role = :floating_qubit_island_ground_capacitance,
	)
	shunt_capacitor!(
		circuit_plan;
		id = "$(prefix)_C02",
		at = island2,
		capacitance = qubit.C02_fF * D3_FARADS_PER_FF,
		role = :floating_qubit_island_ground_capacitance,
	)
	couple_capacitive!(
		circuit_plan;
		id = "$(prefix)_C12",
		from = island1,
		to = island2,
		capacitance = qubit.C12_fF * D3_FARADS_PER_FF,
		role = :floating_qubit_island_mutual_capacitance,
	)
	for junction_index in 1:2
		series_inductor!(
			circuit_plan;
			id = "$(prefix)_LJ_$(junction_index)",
			from = island1,
			to = island2,
			inductance = qubit.L_J_per_junction_nH * D3_HENRIES_PER_NH,
			role = :floating_qubit_linearized_josephson_inductance,
		)
	end
	couple_capacitive!(
		circuit_plan;
		id = "$(prefix)_Cr1",
		from = readout_open_tail,
		to = island1,
		capacitance = qubit.Cr1_fF * D3_FARADS_PER_FF,
		role = :readout_to_floating_qubit_capacitance,
	)
	couple_capacitive!(
		circuit_plan;
		id = "$(prefix)_Cr2",
		from = readout_open_tail,
		to = island2,
		capacitance = qubit.Cr2_fF * D3_FARADS_PER_FF,
		role = :readout_to_floating_qubit_capacitance,
	)
	return (island1 = island1, island2 = island2, readout_attachment = readout_open_tail)
end

struct D3FeedlineRLGC
	source::String
	extraction_frequency_hz::Float64
	l_per_m_h::Float64
	c_per_m_f::Float64
	r_per_m_ohm::Float64
	g_per_m_s::Float64
	r_status::String
	g_status::String
	loss_assumption::String
	target_impedance_ohm::Float64
	max_abs_impedance_error_ohm::Float64
	max_abs_impedance_error_role::String
	zo_ohm::Float64
	velocity_m_per_s::Float64

	function D3FeedlineRLGC(;
		source,
		extraction_frequency_hz,
		l_per_m_h,
		c_per_m_f,
		r_per_m_ohm,
		g_per_m_s,
		r_status,
		g_status,
		loss_assumption,
		target_impedance_ohm,
		max_abs_impedance_error_ohm,
		max_abs_impedance_error_role,
	)
		source_label = strip(String(source))
		isempty(source_label) && error("D3 feedline RLGC requires source provenance.")
		r_status_value = String(r_status)
		g_status_value = String(g_status)
		loss_assumption_value = String(loss_assumption)
		impedance_error_role = String(max_abs_impedance_error_role)
		r_status_value == "unavailable_in_source" || error("D3 feedline R status must be unavailable_in_source.")
		g_status_value == "unavailable_in_source" || error("D3 feedline G status must be unavailable_in_source.")
		loss_assumption_value == "r_and_g_assumed_zero_for_lossless_exploration_only" || error(
			"D3 feedline loss assumption must state the lossless exploration-only R/G zero assumption.",
		)
		impedance_error_role == "mismatch_screening_only" || error(
			"D3 feedline impedance-error gate is only a mismatch screening condition.",
		)
		values = Float64[
			extraction_frequency_hz,
			l_per_m_h,
			c_per_m_f,
			r_per_m_ohm,
			g_per_m_s,
			target_impedance_ohm,
			max_abs_impedance_error_ohm,
		]
		all(isfinite, values) || error("D3 feedline RLGC values must be finite.")
		values[1] > 0 || error("D3 feedline extraction frequency must be positive.")
		values[2] > 0 || error("D3 feedline L per meter must be positive.")
		values[3] > 0 || error("D3 feedline C per meter must be positive.")
		values[4] >= 0 || error("D3 feedline R per meter must be non-negative.")
		values[5] >= 0 || error("D3 feedline G per meter must be non-negative.")
		values[4] == 0 && values[5] == 0 || error(
			"Unavailable feedline R and G must be explicitly assumed zero for lossless exploration.",
		)
		values[6] == 50.0 || error("D3 feedline target impedance must be exactly 50 Ohm.")
		values[7] >= 0 || error("D3 feedline impedance-error gate must be non-negative.")
		zo_ohm = sqrt(values[2] / values[3])
		abs(zo_ohm - values[6]) <= values[7] || error(
			"D3 feedline LC-derived impedance $(zo_ohm) Ohm misses the 50 Ohm target by more than $(values[7]) Ohm.",
		)
		velocity_m_per_s = 1 / sqrt(values[2] * values[3])
		return new(
			source_label,
			values[1:5]...,
			r_status_value,
			g_status_value,
			loss_assumption_value,
			values[6:7]...,
			impedance_error_role,
			zo_ohm,
			velocity_m_per_s,
		)
	end
end

function load_d3_feedline_rlgc(config)
	payload = config["feedline_rlgc"]
	return D3FeedlineRLGC(
		source = payload["source"],
		extraction_frequency_hz = Float64(payload["extraction_frequency_ghz"]) * D3_HZ_PER_GHZ,
		l_per_m_h = payload["l_per_m_h"],
		c_per_m_f = payload["c_per_m_f"],
		r_per_m_ohm = payload["r_per_m_ohm"],
		g_per_m_s = payload["g_per_m_s"],
		r_status = payload["r_status"],
		g_status = payload["g_status"],
		loss_assumption = payload["loss_assumption"],
		target_impedance_ohm = payload["target_impedance_ohm"],
		max_abs_impedance_error_ohm = payload["max_abs_impedance_error_ohm"],
		max_abs_impedance_error_role = payload["max_abs_impedance_error_role"],
	)
end

struct D3HBSettings
	section_length_m::Float64
	port_resistance_ohm::Float64
	pump_frequency_hz::Float64
	pump_current_a::Float64
	n_pump_harmonics::Int
	n_modulation_harmonics::Int
	optional_hb_kwargs::Dict{Symbol,Any}

	function D3HBSettings(
		section_length_m,
		port_resistance_ohm,
		pump_frequency_hz,
		pump_current_a,
		n_pump_harmonics,
		n_modulation_harmonics,
		optional_hb_kwargs,
	)
		section_length = Float64(section_length_m)
		port_resistance = Float64(port_resistance_ohm)
		pump_frequency = Float64(pump_frequency_hz)
		pump_current = Float64(pump_current_a)
		all(isfinite, (section_length, port_resistance, pump_frequency, pump_current)) ||
			error("D3 HB settings must contain only finite numeric values.")
		section_length > 0 || error("D3 HB section_length_m must be positive.")
		port_resistance > 0 || error("D3 HB port_resistance_ohm must be positive.")
		pump_frequency > 0 || error("D3 HB pump_frequency_hz must be positive.")
		pump_harmonics = Int(n_pump_harmonics)
		modulation_harmonics = Int(n_modulation_harmonics)
		pump_harmonics > 0 || error("D3 HB n_pump_harmonics must be positive.")
		modulation_harmonics > 0 || error("D3 HB n_modulation_harmonics must be positive.")
		return new(
			section_length,
			port_resistance,
			pump_frequency,
			pump_current,
			pump_harmonics,
			modulation_harmonics,
			Dict{Symbol,Any}(optional_hb_kwargs),
		)
	end
end

function require_feedline_port_match(feedline::D3FeedlineRLGC, hb_settings::D3HBSettings)
	hb_settings.port_resistance_ohm == feedline.target_impedance_ohm || error(
		"HB port resistance $(hb_settings.port_resistance_ohm) Ohm must equal the D3 feedline target $(feedline.target_impedance_ohm) Ohm.",
	)
	return nothing
end

if !isdefined(@__MODULE__, :PortMatrixPostProcessing)
	include(joinpath(@__DIR__, "..", "includes", "port_matrix_post_processing.jl"))
end

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

function require_current_orpen_lc_exploration_envelope(payload)
	get(payload, "schema_version", nothing) ==
		"orpen-q2d-intrinsic-purcell-rlgc-cases.v1" || error(
			"Unsupported OrPen Q2D case schema. The current D3 exploration path accepts only orpen-q2d-intrinsic-purcell-rlgc-cases.v1.",
		)
	String.(get(payload, "trace_names", Any[])) == ["T1", "T2"] || error(
		"OrPen Q2D exploration payload must declare terminal order [T1, T2].",
	)
	capacitance_convention = String(get(payload, "capacitance_convention", ""))
	occursin("Maxwell", capacitance_convention) &&
		occursin("off-diagonal", capacitance_convention) &&
		occursin("negative", capacitance_convention) || error(
			"OrPen Q2D exploration payload must declare the retained negative Maxwell-C off-diagonal convention.",
		)
	haskey(payload, "single_trace_convention") || error(
		"OrPen Q2D exploration payload must declare its single-trace capacitance convention.",
	)
	cases = get(payload, "cases", nothing)
	cases isa AbstractVector && !isempty(cases) || error(
		"OrPen Q2D exploration payload must contain at least one case.",
	)
	return nothing
end

function load_orpen_cases(case_json_path)
	isfile(case_json_path) || error(
		"Missing OrPen Q2D case JSON. Run orpen_sc_pdk/scripts/export_orpen_q2d_intrinsic_purcell_cases.py first: " *
		case_json_path,
	)
	payload = JSON3.read(read(case_json_path, String), Dict{String,Any})
	require_current_orpen_lc_exploration_envelope(payload)
	return [make_orpen_case(record) for record in payload["cases"]]
end

function load_d3_design_config()
	config_path = joinpath(@__DIR__, "d3_design_config.json")
	isfile(config_path) || error("Missing D3 design config: $(config_path)")
	return JSON3.read(read(config_path, String), Dict{String,Any})
end

function frequency_range_with_step(start_hz, stop_hz, step_hz)
	step = Float64(step_hz)
	step > 0 || error("frequency step must be positive.")
	point_count = round(Int, (Float64(stop_hz) - Float64(start_hz)) / step) + 1
	point_count >= 2 || error("frequency range must contain at least two points.")
	return collect(range(Float64(start_hz), Float64(stop_hz); length = point_count))
end

function csv_value(value)
	raw = ismissing(value) ? "" : string(value)
	occursin(r"[,\"\r\n]", raw) || return raw
	return "\"$(replace(raw, "\"" => "\"\""))\""
end
csv_slug(value) = replace(string(value), "." => "p", "-" => "m", "/" => "_", " " => "_")

function csv_column(header, name)
	index = findfirst(==(name), vec(String.(header)))
	isnothing(index) && error("Missing CSV column $(name).")
	return index
end

read_float(row, columns, name) = parse(Float64, row[columns[name]])
read_optional_float(row, columns, name, default) = haskey(columns, name) ? parse(Float64, row[columns[name]]) : default

"""Read every CSV field as source text so one complete row can be identity-hashed.

This helper deliberately preserves the serialized source values instead of
silently normalizing columns that the circuit model does not consume.  The
typed `read_design_csv` path remains the execution model; this path owns only
full-row provenance.
"""
function read_csv_source_rows(path)
	isfile(path) || error("Missing CSV source: $(path)")
	data, header = DelimitedFiles.readdlm(path, ',', String; header = true)
	names = vec(String.(header))
	length(unique(names)) == length(names) || error("CSV source contains duplicate column names: $(path)")
	return [Dict(name => String(row[index]) for (index, name) in enumerate(names)) for row in eachrow(data)]
end

function select_d3_source_row(path; case_id, target_set_id, slot_target_ghz)
	matches = [
		row for row in read_csv_source_rows(path)
		if row["case_id"] == String(case_id) &&
			row["target_set_id"] == String(target_set_id) &&
			parse(Float64, row["slot_target_ghz"]) == Float64(slot_target_ghz)
	]
	length(matches) == 1 || error(
		"Expected exactly one CSV row for case=$(case_id), target_set=$(target_set_id), slot=$(slot_target_ghz) GHz; found $(length(matches)).",
	)
	return only(matches)
end

function read_design_csv(path; case_id = nothing)
	isfile(path) || error("Missing Python design CSV. Run notebooks/python/01_resonator_length_estimate.py first: $(path)")
	data, header = DelimitedFiles.readdlm(path, ',', String; header = true)
	columns = Dict(String(name) => csv_column(header, String(name)) for name in vec(String.(header)))
	rows = [
		(
			id = Symbol(row[columns["id"]]),
			case_id = Symbol(row[columns["case_id"]]),
			target_set_id = Symbol(row[columns["target_set_id"]]),
			target_set_name = String(row[columns["target_set_name"]]),
			scan_start_ghz = read_float(row, columns, "scan_start_ghz"),
			scan_stop_ghz = read_float(row, columns, "scan_stop_ghz"),
			slot_target_ghz = read_float(row, columns, "slot_target_ghz"),
			notch_target_ghz = read_float(row, columns, "notch_target_ghz"),
			lr_open_um = read_float(row, columns, "lr_open_um"),
			lr_short_um = read_float(row, columns, "lr_short_um"),
			lc_um = read_float(row, columns, "lc_um"),
			lp_short_um = read_float(row, columns, "lp_short_um"),
			lp_open_um = read_float(row, columns, "lp_open_um"),
			lr_total_um = read_float(row, columns, "lr_total_um"),
			lp_total_um = read_float(row, columns, "lp_total_um"),
			notch_length_um = read_float(row, columns, "notch_length_um"),
			short_split = read_float(row, columns, "short_split"),
			fr_est_ghz = read_float(row, columns, "fr_est_ghz"),
			fp_est_ghz = read_float(row, columns, "fp_est_ghz"),
			fn_est_ghz = read_float(row, columns, "fn_est_ghz"),
			analytic_score = read_float(row, columns, "analytic_score"),
			filter_to_line_capacitance_fF = read_optional_float(row, columns, "filter_to_line_capacitance_fF", NaN),
		)
		for row in eachrow(data)
	]
	selected = isnothing(case_id) ? rows : [row for row in rows if row.case_id == Symbol(case_id)]
	!isempty(selected) || error("No design rows for case_id=$(case_id) in $(path).")
	return sort(selected; by = row -> (String(row.target_set_id), row.slot_target_ghz))
end

function require_design_capacitance_fF(design)
	design_capacitance_fF = get(design, :filter_to_line_capacitance_fF, NaN)
	isfinite(design_capacitance_fF) || error("Missing finite per-design filter_to_line_capacitance_fF.")
	Float64(design_capacitance_fF) > 0 || error("Per-design filter_to_line_capacitance_fF must be positive.")
	return Float64(design_capacitance_fF)
end

function target_sets_from_designs(designs)
	return [
		(
			id = target_set_id,
			name = first(rows).target_set_name,
			slots = [row.slot_target_ghz for row in sort(rows; by = row -> row.slot_target_ghz)],
			scan_start_ghz = first(rows).scan_start_ghz,
			scan_stop_ghz = first(rows).scan_stop_ghz,
		)
		for target_set_id in unique([row.target_set_id for row in designs])
		for rows in ([row for row in designs if row.target_set_id == target_set_id],)
	]
end

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

function write_sparameter_trace_csv(path, frequencies_hz, s11, s21, z21)
	return _write_sparameter_trace_csv(path, frequencies_hz, s11, s21, z21, nothing)
end

function write_sparameter_trace_csv(path, frequencies_hz, s11, s21, z21, z21_ptc)
	return _write_sparameter_trace_csv(path, frequencies_hz, s11, s21, z21, z21_ptc)
end

function _write_sparameter_trace_csv(path, frequencies_hz, s11, s21, z21, z21_ptc)
	point_count = length(frequencies_hz)
	all(length(trace) == point_count for trace in (s11, s21, z21)) ||
		error("S-parameter and Z21 traces must match the frequency grid length.")
	!isnothing(z21_ptc) && length(z21_ptc) != point_count &&
		error("PTC Z21 trace must match the frequency grid length.")
	has_ptc = !isnothing(z21_ptc)
	mkpath(dirname(path))
	open(path, "w") do io
		header = "frequency_ghz,s11_re,s11_im,s11_abs,s21_re,s21_im,s21_abs,z21_re_ohm,z21_im_ohm,z21_abs_ohm"
		has_ptc && (header *= ",z21_ptc_re_ohm,z21_ptc_im_ohm,z21_ptc_abs_ohm,z21_ptc_abs_im_ohm")
		println(io, header)
		for index in eachindex(frequencies_hz)
			z21_value = z21[index]
			values = [
				frequencies_hz[index] / D3_HZ_PER_GHZ,
				real(s11[index]),
				imag(s11[index]),
				abs(s11[index]),
				real(s21[index]),
				imag(s21[index]),
				abs(s21[index]),
				real(z21_value),
				imag(z21_value),
				abs(z21_value),
			]
			if has_ptc
				z21_ptc_value = z21_ptc[index]
				append!(
					values,
					[
						real(z21_ptc_value),
						imag(z21_ptc_value),
						abs(z21_ptc_value),
						abs(imag(z21_ptc_value)),
					],
				)
			end
			println(
				io,
				join(values, ","),
			)
		end
	end
	return path
end

function perturb_design_open_length(design; variant_id, readout_delta_um = 0.0, filter_delta_um = 0.0)
	lr_open_um = design.lr_open_um + Float64(readout_delta_um)
	lp_open_um = design.lp_open_um + Float64(filter_delta_um)
	min(lr_open_um, lp_open_um) > 0 || error("Perturbed open length must stay positive.")
	return merge(
		design,
		(
			variant_id = Symbol(variant_id),
			readout_open_delta_um = Float64(readout_delta_um),
			filter_open_delta_um = Float64(filter_delta_um),
			lr_open_um = lr_open_um,
			lp_open_um = lp_open_um,
			lr_total_um = design.lr_short_um + design.lc_um + lr_open_um,
			lp_total_um = design.lp_short_um + design.lc_um + lp_open_um,
		),
	)
end

function add_mtl_pair!(circuit_plan; case, design, index, hb_settings)
	lr_total_m = design.lr_total_um * D3_METERS_PER_UM
	lp_total_m = design.lp_total_um * D3_METERS_PER_UM
	lr_short_m = design.lr_short_um * D3_METERS_PER_UM
	lp_short_m = design.lp_short_um * D3_METERS_PER_UM
	lc_m = design.lc_um * D3_METERS_PER_UM
	readout_resonator_spec = RLGCSpec(
		length_m = lr_total_m,
		section_length_m = hb_settings.section_length_m,
		l_per_m_h = case.single_l_per_m_h,
		c_per_m_f = case.single_c_per_m_f,
	)
	filter_resonator_spec = RLGCSpec(
		length_m = lp_total_m,
		section_length_m = hb_settings.section_length_m,
		l_per_m_h = case.single_l_per_m_h,
		c_per_m_f = case.single_c_per_m_f,
	)
	mtl_model = MTLCoupledRLGCSpec(
		start1_m = lr_short_m,
		start2_m = lp_short_m,
		length_m = lc_m,
		section_length_m = hb_settings.section_length_m,
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
	return (
		readout_open_tail = readout_open_tail,
		filter_open_tail = filter_open_tail,
	)
end

function add_mtl_pair_diagonal_reference!(circuit_plan; case, design, index, hb_settings)
	"""Build the pair Hamiltonian reference with the full pair geometry but no exchange channel.

	This is the mathematical diagonal of the Maxwell RLGC model, not a circuit
	obtained by physically deleting the cross capacitor.  Each resonator uses
	``Lii`` and ``Cii`` with all off-diagonal entries zero.  The full physical
	ladder instead lowers Maxwell ``C`` into ground shunts ``Cii + Cij`` plus a
	cross capacitor ``-Cij``; merely deleting that cross branch would change the
	nodal diagonal and make the coupling-on perturbation contain a spurious
	diagonal shift.  This reference keeps the pair Hamiltonian diagonal fixed so
	that J is the sole avoided-crossing term.
	"""
	lr_total_m = design.lr_total_um * D3_METERS_PER_UM
	lp_total_m = design.lp_total_um * D3_METERS_PER_UM
	lr_short_m = design.lr_short_um * D3_METERS_PER_UM
	lp_short_m = design.lp_short_um * D3_METERS_PER_UM
	lc_m = design.lc_um * D3_METERS_PER_UM
	readout_resonator_spec = RLGCSpec(
		length_m = lr_total_m,
		section_length_m = hb_settings.section_length_m,
		l_per_m_h = case.single_l_per_m_h,
		c_per_m_f = case.single_c_per_m_f,
	)
	filter_resonator_spec = RLGCSpec(
		length_m = lp_total_m,
		section_length_m = hb_settings.section_length_m,
		l_per_m_h = case.single_l_per_m_h,
		c_per_m_f = case.single_c_per_m_f,
	)
	readout_grounded_head = external_node("readout_diagonal_reference_grounded_head_$(index)")
	readout_open_tail = external_node("readout_diagonal_reference_open_tail_$(index)")
	filter_grounded_head = external_node("filter_diagonal_reference_grounded_head_$(index)")
	filter_open_tail = external_node("filter_diagonal_reference_open_tail_$(index)")
	quarter_wave_resonator!(
		circuit_plan;
		id = Symbol("readout_diagonal_reference_$(index)"),
		grounded_head = readout_grounded_head,
		open_tail = readout_open_tail,
		spec = readout_resonator_spec,
		breakpoints_m = [lr_short_m, lr_short_m + lc_m],
		section_overrides = [
			TransmissionLineSectionOverride(
				start_m = lr_short_m,
				length_m = lc_m,
				l_per_m_h = case.mtl_l_matrix_h_per_m[1, 1],
				c_per_m_f = case.mtl_c_matrix_f_per_m[1, 1],
				tag = :mtl_maxwell_diagonal_reference_readout,
			),
		],
	)
	quarter_wave_resonator!(
		circuit_plan;
		id = Symbol("filter_diagonal_reference_$(index)"),
		grounded_head = filter_grounded_head,
		open_tail = filter_open_tail,
		spec = filter_resonator_spec,
		breakpoints_m = [lp_short_m, lp_short_m + lc_m],
		section_overrides = [
			TransmissionLineSectionOverride(
				start_m = lp_short_m,
				length_m = lc_m,
				l_per_m_h = case.mtl_l_matrix_h_per_m[2, 2],
				c_per_m_f = case.mtl_c_matrix_f_per_m[2, 2],
				tag = :mtl_maxwell_diagonal_reference_filter,
			),
		],
	)
	return (
		readout_open_tail = readout_open_tail,
		filter_open_tail = filter_open_tail,
	)
end

function add_feedline!(circuit_plan; feedline, id, length_um, hb_settings, breakpoints_m = Float64[])
	require_feedline_port_match(feedline, hb_settings)
	input = external_node("$(id)_input")
	output = external_node("$(id)_output")
	line = transmission_line!(
		circuit_plan;
		id = Symbol(id),
		head = input,
		tail = output,
		spec = RLGCSpec(
			length_m = Float64(length_um) * D3_METERS_PER_UM,
			section_length_m = hb_settings.section_length_m,
			l_per_m_h = feedline.l_per_m_h,
			c_per_m_f = feedline.c_per_m_f,
			r_per_m_ohm = feedline.r_per_m_ohm,
			g_per_m_s = feedline.g_per_m_s,
		),
		head_termination = :external,
		tail_termination = :external,
		breakpoints_m = breakpoints_m,
	)
	external_port!(
		circuit_plan;
		id = :input_port,
		index = 1,
		endpoint = input,
		resistance = hb_settings.port_resistance_ohm,
		role = :readout_line_input,
	)
	external_port!(
		circuit_plan;
		id = :output_port,
		index = 2,
		endpoint = output,
		resistance = hb_settings.port_resistance_ohm,
		role = :readout_line_output,
	)
	return line
end

function attach_sparameter_hb_intent!(circuit_plan; hb_settings)
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
			n_pump_harmonics = hb_settings.n_pump_harmonics
			n_modulation_harmonics = hb_settings.n_modulation_harmonics
			returnS = true
			returnZ = true
			returnQE = true
			returnCM = true
			keyedarrays = false
		end
	end
	return circuit_plan
end

function build_feedline_reference_plan(feedline; feedline_length_um, breakpoints_m, hb_settings)
	breakpoints = Float64.(collect(breakpoints_m))
	all(isfinite, breakpoints) || error("Feedline-reference breakpoints must be finite.")
	circuit_plan = CircuitPlan("d3-empty-feedline-reference")
	add_feedline!(
		circuit_plan;
		feedline = feedline,
		id = :readout_line,
		length_um = feedline_length_um,
		hb_settings = hb_settings,
		breakpoints_m = breakpoints,
	)
	return attach_sparameter_hb_intent!(circuit_plan; hb_settings = hb_settings)
end

function build_single_pair_feedline_plan(
	case,
	design;
	capacitance_fF,
	feedline_length_um,
	feedline,
	hb_settings,
	floating_qubit_nominal = nothing,
)
	circuit_plan = CircuitPlan("d3-single-pair-$(design.id)-$(get(design, :variant_id, :baseline))")
	actual_capacitance_fF = Float64(capacitance_fF)
	isfinite(actual_capacitance_fF) && actual_capacitance_fF > 0 ||
		error("Single-pair filter_to_line capacitance_fF must be finite and positive.")
	coupling_position_m = Float64(feedline_length_um) * D3_METERS_PER_UM / 2
	readout_line = add_feedline!(
		circuit_plan;
		feedline = feedline,
		id = :readout_line,
		length_um = feedline_length_um,
		hb_settings = hb_settings,
		breakpoints_m = [coupling_position_m],
	)
	pair_nodes = add_mtl_pair!(circuit_plan; case = case, design = design, index = 1, hb_settings = hb_settings)
	isnothing(floating_qubit_nominal) || add_floating_qubit_nominal!(
		circuit_plan,
		pair_nodes.readout_open_tail,
		floating_qubit_nominal;
		id_prefix = "floating_qubit_nominal_1",
	)
	couple_capacitive!(
		circuit_plan;
		id = :filter_to_readout_line_1,
		from = node_at_distance(readout_line, coupling_position_m),
		to = pair_nodes.filter_open_tail,
		capacitance = actual_capacitance_fF * D3_FARADS_PER_FF,
		role = :filter_to_readout_line_coupling,
	)
	return attach_sparameter_hb_intent!(circuit_plan; hb_settings = hb_settings)
end

function build_intrinsic_pair_plan(case, design; hb_settings, floating_qubit_nominal = nothing)
	circuit_plan = CircuitPlan("d3-intrinsic-pair-$(design.id)")
	pair_nodes = add_mtl_pair!(circuit_plan; case = case, design = design, index = 1, hb_settings = hb_settings)
	isnothing(floating_qubit_nominal) || add_floating_qubit_nominal!(
		circuit_plan,
		pair_nodes.readout_open_tail,
		floating_qubit_nominal;
		id_prefix = "floating_qubit_nominal_intrinsic_1",
	)
	external_port!(
		circuit_plan;
		id = :input_port,
		index = 1,
		endpoint = pair_nodes.readout_open_tail,
		resistance = hb_settings.port_resistance_ohm,
		role = :readout_open_end,
	)
	external_port!(
		circuit_plan;
		id = :output_port,
		index = 2,
		endpoint = pair_nodes.filter_open_tail,
		resistance = hb_settings.port_resistance_ohm,
		role = :filter_open_end,
	)
	return attach_sparameter_hb_intent!(circuit_plan; hb_settings = hb_settings)
end

function build_filter_only_feedline_plan(
	case,
	design;
	capacitance_fF,
	feedline_length_um,
	feedline,
	hb_settings,
	lc_l_per_m_h = case.mtl_diag_l_per_m_h,
	lc_c_per_m_f = case.mtl_diag_c_per_m_f,
	model_case_id = :mtl_diagonal_lc,
)
	actual_capacitance_fF = Float64(capacitance_fF)
	isfinite(actual_capacitance_fF) && actual_capacitance_fF > 0 ||
		error("Filter-only capacitance_fF must be finite and positive.")
	circuit_plan = CircuitPlan("d3-filter-only-$(design.id)-$(model_case_id)-c$(csv_slug(capacitance_fF))")
	coupling_position_m = Float64(feedline_length_um) * D3_METERS_PER_UM / 2
	readout_line = add_feedline!(
		circuit_plan;
		feedline = feedline,
		id = :readout_line,
		length_um = feedline_length_um,
		hb_settings = hb_settings,
		breakpoints_m = [coupling_position_m],
	)
	filter_grounded_head = external_node("filter_only_grounded_head")
	filter_open_tail = external_node("filter_only_open_tail")
	lp_short_m = design.lp_short_um * D3_METERS_PER_UM
	lc_m = design.lc_um * D3_METERS_PER_UM
	filter_resonator = quarter_wave_resonator!(
		circuit_plan;
		id = :filter_only_resonator,
		grounded_head = filter_grounded_head,
		open_tail = filter_open_tail,
		spec = RLGCSpec(
			length_m = design.lp_total_um * D3_METERS_PER_UM,
			section_length_m = hb_settings.section_length_m,
			l_per_m_h = case.single_l_per_m_h,
			c_per_m_f = case.single_c_per_m_f,
		),
		breakpoints_m = [lp_short_m, lp_short_m + lc_m],
		section_overrides = [
			TransmissionLineSectionOverride(
				start_m = lp_short_m,
				length_m = lc_m,
				l_per_m_h = Float64(lc_l_per_m_h),
				c_per_m_f = Float64(lc_c_per_m_f),
				tag = Symbol(:filter_lc_section_, model_case_id),
			),
		],
	)
	couple_capacitive!(
		circuit_plan;
		id = :filter_only_to_readout_line,
		from = node_at_distance(readout_line, coupling_position_m),
		to = filter_open_tail,
		capacitance = actual_capacitance_fF * D3_FARADS_PER_FF,
		role = :filter_to_readout_line_coupling,
	)
	return attach_sparameter_hb_intent!(circuit_plan; hb_settings = hb_settings)
end

function build_maxwell_diagonal_pair_feedline_plan(
	case,
	design;
	filter_capacitance_fF,
	readout_probe_capacitance_fF = nothing,
	feedline_length_um,
	feedline,
	hb_settings,
	floating_qubit_nominal = nothing,
)
	filter_capacitance = Float64(filter_capacitance_fF)
	isfinite(filter_capacitance) && filter_capacitance > 0 ||
		error("Maxwell-diagonal pair filter capacitance_fF must be finite and positive.")
	probe_capacitance = isnothing(readout_probe_capacitance_fF) ? nothing : Float64(readout_probe_capacitance_fF)
	!isnothing(probe_capacitance) && (!isfinite(probe_capacitance) || probe_capacitance <= 0) &&
		error("Maxwell-diagonal pair readout probe capacitance_fF must be finite and positive.")
	circuit_plan = CircuitPlan(
		"d3-maxwell-diagonal-pair-$(design.id)-filterc$(csv_slug(filter_capacitance))" *
		(isnothing(probe_capacitance) ? "" : "-readoutprobec$(csv_slug(probe_capacitance))"),
	)
	coupling_position_m = Float64(feedline_length_um) * D3_METERS_PER_UM / 2
	readout_line = add_feedline!(
		circuit_plan;
		feedline = feedline,
		id = :readout_line,
		length_um = feedline_length_um,
		hb_settings = hb_settings,
		breakpoints_m = [coupling_position_m],
	)
	pair_nodes = add_mtl_pair_diagonal_reference!(
		circuit_plan;
		case = case,
		design = design,
		index = 1,
		hb_settings = hb_settings,
	)
	isnothing(floating_qubit_nominal) || add_floating_qubit_nominal!(
		circuit_plan,
		pair_nodes.readout_open_tail,
		floating_qubit_nominal;
		id_prefix = "floating_qubit_nominal_diagonal_reference_1",
	)
	feedline_tap = node_at_distance(readout_line, coupling_position_m)
	couple_capacitive!(
		circuit_plan;
		id = :filter_to_readout_line_diagonal_reference,
		from = feedline_tap,
		to = pair_nodes.filter_open_tail,
		capacitance = filter_capacitance * D3_FARADS_PER_FF,
		role = :filter_to_readout_line_coupling,
	)
	if !isnothing(probe_capacitance)
		couple_capacitive!(
			circuit_plan;
			id = :readout_probe_to_readout_line_diagonal_reference,
			from = feedline_tap,
			to = pair_nodes.readout_open_tail,
			capacitance = probe_capacitance * D3_FARADS_PER_FF,
			role = :readout_probe_coupling,
		)
	end
	return attach_sparameter_hb_intent!(circuit_plan; hb_settings = hb_settings)
end

function build_readout_only_feedline_plan(case, design; capacitance_fF, feedline_length_um, feedline, hb_settings)
	actual_capacitance_fF = Float64(capacitance_fF)
	isfinite(actual_capacitance_fF) && actual_capacitance_fF > 0 ||
		error("Readout-only probe capacitance_fF must be finite and positive.")
	circuit_plan = CircuitPlan("d3-readout-only-$(design.id)-c$(csv_slug(actual_capacitance_fF))")
	coupling_position_m = Float64(feedline_length_um) * D3_METERS_PER_UM / 2
	readout_line = add_feedline!(
		circuit_plan;
		feedline = feedline,
		id = :readout_line,
		length_um = feedline_length_um,
		hb_settings = hb_settings,
		breakpoints_m = [coupling_position_m],
	)
	readout_grounded_head = external_node("readout_only_grounded_head")
	readout_open_tail = external_node("readout_only_open_tail")
	lr_short_m = design.lr_short_um * D3_METERS_PER_UM
	lc_m = design.lc_um * D3_METERS_PER_UM
	quarter_wave_resonator!(
		circuit_plan;
		id = :readout_only_resonator,
		grounded_head = readout_grounded_head,
		open_tail = readout_open_tail,
		spec = RLGCSpec(
			length_m = design.lr_total_um * D3_METERS_PER_UM,
			section_length_m = hb_settings.section_length_m,
			l_per_m_h = case.single_l_per_m_h,
			c_per_m_f = case.single_c_per_m_f,
		),
		breakpoints_m = [lr_short_m, lr_short_m + lc_m],
		section_overrides = [
			TransmissionLineSectionOverride(
				start_m = lr_short_m,
				length_m = lc_m,
				l_per_m_h = case.mtl_diag_l_per_m_h,
				c_per_m_f = case.mtl_diag_c_per_m_f,
				tag = :readout_lc_section_mtl_diagonal,
			),
		],
	)
	couple_capacitive!(
		circuit_plan;
		id = :readout_only_to_readout_line,
		from = node_at_distance(readout_line, coupling_position_m),
		to = readout_open_tail,
		capacitance = actual_capacitance_fF * D3_FARADS_PER_FF,
		role = :readout_probe_coupling,
	)
	return attach_sparameter_hb_intent!(circuit_plan; hb_settings = hb_settings)
end

function shared_readout_branch_positions_m(design_count; feedline_length_um, margin_um)
	count = Int(design_count)
	count > 0 || error("Shared readout requires at least one design.")
	feedline_length = Float64(feedline_length_um)
	margin = Float64(margin_um)
	all(isfinite, (feedline_length, margin)) || error("Shared-readout dimensions must be finite.")
	feedline_length > 0 || error("Shared-readout feedline length must be positive.")
	0 <= margin < feedline_length / 2 || error("Shared-readout margin must lie inside the feedline.")
	return count == 1 ?
		[feedline_length * D3_METERS_PER_UM / 2] :
		collect(range(
			margin * D3_METERS_PER_UM,
			(feedline_length - margin) * D3_METERS_PER_UM;
			length = count,
		))
end

function build_shared_readout_plan(case, target_set; feedline_length_um, margin_um, feedline, hb_settings)
	designs = target_set.designs
	branch_positions_m = shared_readout_branch_positions_m(
		length(designs);
		feedline_length_um = feedline_length_um,
		margin_um = margin_um,
	)
	circuit_plan = CircuitPlan("d3-shared-readout-$(target_set.target_set_id)")
	readout_line = add_feedline!(
		circuit_plan;
		feedline = feedline,
		id = :readout_line,
		length_um = feedline_length_um,
		hb_settings = hb_settings,
		breakpoints_m = branch_positions_m,
	)
	for (index, design) in pairs(designs)
		actual_capacitance_fF = require_design_capacitance_fF(design)
		pair_nodes = add_mtl_pair!(circuit_plan; case = case, design = design, index = index, hb_settings = hb_settings)
		couple_capacitive!(
			circuit_plan;
			id = Symbol("filter_to_readout_line_$(index)"),
			from = node_at_distance(readout_line, branch_positions_m[index]),
			to = pair_nodes.filter_open_tail,
			capacitance = actual_capacitance_fF * D3_FARADS_PER_FF,
			role = :filter_to_readout_line_coupling,
		)
	end
	return attach_sparameter_hb_intent!(circuit_plan; hb_settings = hb_settings)
end

function run_sparameter_hb(
	circuit_plan,
	frequencies_hz;
	hb_settings,
	compensate_port_indices = (),
	removal_intent::Union{Nothing,Symbol} = nothing,
)
	compensation_requested = !isempty(compensate_port_indices)
	compensation_requested == !isnothing(removal_intent) || error(
		"PTC requires both explicit compensate_port_indices and a removal_intent.",
	)
	validation_report = validate_hb_intent(circuit_plan)
	has_errors(validation_report) && error("HB intent validation failed: $(validation_report)")
	compiled = compile_to_josephson(circuit_plan)
	hb_problem = build_hb_problem(
		compiled,
		HBRunSpec(
			frequency_sweep = frequencies_hz,
			pump_frequencies = Dict(:pump => hb_settings.pump_frequency_hz),
			source_currents = Dict(:pump_in => hb_settings.pump_current_a),
			optional_hb_kwargs = Dict{Symbol,Any}(hb_settings.optional_hb_kwargs),
		),
	)
	result = run_hb_problem(hb_problem)
	z21_ptc = if compensation_requested
		raw_y_stack = PortMatrixPostProcessing.zero_mode_y_matrix_stack(result; ports = [1, 2])
		ptc_y_stack = PortMatrixPostProcessing.apply_port_termination_compensation(
			raw_y_stack,
			compiled;
			compensate_port_indices = compensate_port_indices,
			removal_intent = removal_intent,
		)
		ptc_z_stack = PortMatrixPostProcessing.invert_port_matrix_stack(
			ptc_y_stack;
			source_kind = :ptc_z_from_y,
		)
		vec(ptc_z_stack.values[2, 1, :])
	else
		nothing
	end
	return (
		result = result,
		s11 = zero_mode_s(result, 1, 1),
		s21 = zero_mode_s(result, 2, 1),
		z21 = result.traces[:z_parameter_mode]["om=0|op=2|im=0|ip=1"],
		z21_ptc = z21_ptc,
		hb_intent_ok = !has_errors(validation_report),
		netlist_rows = length(compiled.netlist),
	)
end

function plot_sparameter_trace(trace; title)
	return PlotlyJS.Plot(
		[
			PlotlyJS.scatter(
				x = trace.frequencies_hz ./ D3_HZ_PER_GHZ,
				y = abs.(trace.s11),
				mode = "markers",
				name = "HB |S11|",
				marker = PlotlyJS.attr(size = 4),
			),
			PlotlyJS.scatter(
				x = trace.frequencies_hz ./ D3_HZ_PER_GHZ,
				y = abs.(trace.s21),
				mode = "markers",
				name = "HB |S21|",
				marker = PlotlyJS.attr(size = 4),
			),
		],
		PlotlyJS.Layout(
			title = title,
			xaxis = PlotlyJS.attr(title = "Frequency (GHz)"),
			yaxis = PlotlyJS.attr(title = "|S|"),
		),
	)
end
