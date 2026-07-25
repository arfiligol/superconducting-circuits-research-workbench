# This file owns the conservative D3 forward-response comparison between the
# physical distributed q-r-p network and one response-matched lumped network.
# It also owns the strict v3 Q2D pair/single input join used by this path. The
# low-level topology builders and linear-response algebra remain owned by
# d3_purcell_common.jl and SuperconductingCircuitsCore respectively.

import LinearAlgebra

const D3_FORWARD_RESPONSE_CONTRACT_ID = "d3-conservative-forward-response-v1"
const D3_FORWARD_Q2D_SCHEMA = "orpen-q2d-intrinsic-purcell-maxwell-lc-cases.v3"

function _d3_forward_matrix(value, dimension, label)
	value isa AbstractVector && length(value) == dimension || error(
		"$(label) must contain exactly $(dimension) rows.",
	)
	all(row -> row isa AbstractVector && length(row) == dimension, value) || error(
		"$(label) must be a $(dimension)x$(dimension) matrix.",
	)
	matrix = Matrix{Float64}(undef, dimension, dimension)
	for row in 1:dimension, column in 1:dimension
		matrix[row, column] = Float64(value[row][column])
	end
	all(isfinite, matrix) || error("$(label) must contain only finite values.")
	LinearAlgebra.isapprox(matrix, transpose(matrix); rtol = 1.0e-9, atol = 1.0e-18) || error(
		"$(label) must be symmetric.",
	)
	symmetric = LinearAlgebra.Symmetric((matrix + transpose(matrix)) / 2)
	LinearAlgebra.isposdef(symmetric) || error("$(label) must be positive definite.")
	return matrix
end

function _d3_forward_positive_parameter(parameters, field, case_id)
	raw = get(parameters, field, nothing)
	raw isa Real || error("Q2D v3 case $(case_id) $(field) must be numeric.")
	value = Float64(raw)
	isfinite(value) && value > 0 || error(
		"Q2D v3 case $(case_id) $(field) must be finite and positive.",
	)
	return value
end

function _d3_forward_source_hashes(metadata, case_id)
	integrity = get(metadata, "source_integrity", nothing)
	integrity isa AbstractDict || error("Q2D v3 metadata must contain source_integrity.")
	get(integrity, "algorithm", nothing) == "sha256" || error(
		"Q2D v3 source integrity must use sha256.",
	)
	get(integrity, "all_sources_hashed", false) === true || error(
		"Q2D v3 source integrity must declare all_sources_hashed=true.",
	)
	get(integrity, "solver_export_sizes_verified", false) === true || error(
		"Q2D v3 source integrity must declare solver_export_sizes_verified=true.",
	)
	by_case = get(integrity, "cases", nothing)
	by_case isa AbstractDict && haskey(by_case, case_id) || error(
		"Q2D v3 source integrity is missing case $(case_id).",
	)
	records = by_case[case_id]
	records isa AbstractVector && !isempty(records) || error(
		"Q2D v3 case $(case_id) must retain at least one source hash.",
	)
	for record in records
		record isa AbstractDict || error("Q2D v3 source-hash rows must be objects.")
		hash = String(get(record, "sha256", ""))
		occursin(r"^[0-9a-f]{64}$", hash) || error(
			"Q2D v3 source hash for $(case_id) is not a lowercase sha256 digest.",
		)
		!isempty(strip(String(get(record, "path", "")))) || error(
			"Q2D v3 source hash for $(case_id) must retain its source path.",
		)
		Int(get(record, "size_bytes", 0)) > 0 || error(
			"Q2D v3 source hash for $(case_id) must retain a positive source size.",
		)
	end
	return deepcopy(records)
end

function _d3_forward_validate_q2d_artifact(payload, role)
	expected = if role === :coupled_pair
		(
			case_role = "coupled_pair",
			case_schema = "orpen-q2d-coupled-pair-maxwell-lc.v1",
			topology_schemas = (
				"q2d-same-face-upper-ground-clearance.v1",
				"q2d-same-face-continuous-upper-ground.v1",
			),
			order = ["T1", "T2"],
			dimension = 2,
			c_semantics = "F/m; Maxwell off-diagonal retained as negative",
			l_semantics = "H/m; Maxwell mutual entries retained as positive",
		)
	elseif role === :single_reference
		(
			case_role = "single_reference",
			case_schema = "orpen-q2d-single-reference-maxwell-lc.v1",
			topology_schemas = (
				"q2d-single-reference-upper-ground-clearance.v1",
				"q2d-single-reference-continuous-upper-ground.v1",
			),
			order = ["T1"],
			dimension = 1,
			c_semantics = "F/m; one signal-to-Ground Maxwell self entry",
			l_semantics = "H/m; one signal-to-Ground Maxwell self entry",
		)
	else
		error("Unsupported D3 forward Q2D artifact role $(role).")
	end
	payload isa AbstractDict || error("Q2D v3 artifact must be a JSON object.")
	get(payload, "schema_version", nothing) == D3_FORWARD_Q2D_SCHEMA || error(
		"D3 forward Q2D input accepts only $(D3_FORWARD_Q2D_SCHEMA).",
	)
	get(payload, "artifact_status", nothing) == "complete" || error(
		"D3 forward Q2D input must be solve-complete.",
	)
	metadata = get(payload, "metadata", nothing)
	metadata isa AbstractDict || error("Q2D v3 artifact must contain metadata.")
	get(metadata, "case_role", nothing) == expected.case_role || error(
		"Q2D v3 artifact has the wrong homogeneous case role.",
	)
	get(metadata, "case_schema_version", nothing) == expected.case_schema || error(
		"Q2D v3 artifact has the wrong homogeneous case schema.",
	)
	topology_schema = String(get(metadata, "topology_contract", ""))
	topology_schema in expected.topology_schemas || error(
		"Q2D v3 artifact has the wrong topology contract.",
	)
	String.(get(metadata, "conductor_order", Any[])) == expected.order || error(
		"Q2D v3 artifact has the wrong conductor order.",
	)
	get(metadata, "reference_group", nothing) == "Ground" || error(
		"Q2D v3 artifact must use the Ground reference group.",
	)
	directions = get(metadata, "directions", nothing)
	directions isa AbstractDict &&
		get(directions, "voltage", nothing) == "V[i] = potential(Ti) - potential(Ground)" &&
		get(directions, "current", nothing) == "positive I[i] flows in +z" &&
		get(directions, "positive_z", nothing) ==
			"normal to the XY cross-section and along line propagation" || error(
		"Q2D v3 artifact has incompatible voltage, current, or propagation directions.",
	)
	representation = get(metadata, "matrix_representation", nothing)
	representation isa AbstractDict || error("Q2D v3 metadata must declare matrix_representation.")
	get(representation, "kind", nothing) == "distributed_maxwell_per_unit_length" || error(
		"Q2D v3 input must contain distributed Maxwell per-unit-length matrices.",
	)
	get(representation, "row_column_order", nothing) == "conductor_order" || error(
		"Q2D v3 matrix row/column order must be conductor_order.",
	)
	Int.(get(representation, "shape", Any[])) == [expected.dimension, expected.dimension] || error(
		"Q2D v3 matrix shape disagrees with its case role.",
	)
	get(representation, "C", nothing) == expected.c_semantics || error(
		"Q2D v3 capacitance semantics are incompatible.",
	)
	get(representation, "L", nothing) == expected.l_semantics || error(
		"Q2D v3 inductance semantics are incompatible.",
	)
	loss_terms = get(metadata, "loss_terms", nothing)
	loss_terms isa AbstractDict || error("Q2D v3 metadata must retain R/G availability.")
	for (quantity, unit) in (("R", "ohm/m"), ("G", "S/m"))
		term = get(loss_terms, quantity, nothing)
		term isa AbstractDict && get(term, "status", nothing) == "unavailable" &&
			get(term, "assumed_zero_for_v1", false) === true && get(term, "unit", nothing) == unit || error(
			"Q2D v3 $(quantity) must remain unavailable with assumed_zero_for_v1=true.",
		)
	end
	run = get(metadata, "run_provenance", nothing)
	run isa AbstractDict && get(run, "selected_case_status", nothing) == "solve_complete" || error(
		"Q2D v3 run provenance must declare selected_case_status=solve_complete.",
	)
	run_id = strip(String(get(run, "run_id", "")))
	!isempty(run_id) || error("Q2D v3 run provenance must retain a run_id.")
	extraction_frequency_hz = Float64(get(metadata, "extraction_frequency_hz", NaN))
	isfinite(extraction_frequency_hz) && extraction_frequency_hz > 0 || error(
		"Q2D v3 extraction frequency must be finite and positive.",
	)
	adaptive_frequency = strip(String(get(metadata, "adaptive_frequency_expression", "")))
	!isempty(adaptive_frequency) || error(
		"Q2D v3 metadata must retain adaptive_frequency_expression.",
	)
	cases = get(payload, "cases", nothing)
	cases isa AbstractVector && !isempty(cases) || error("Q2D v3 artifact must contain cases.")
	declared_case_ids = String.(get(run, "case_ids", Any[]))
	length(declared_case_ids) == length(unique(declared_case_ids)) || error(
		"Q2D v3 run provenance contains duplicate case ids.",
	)
	record_ids = String[]
	by_key = Dict{Any,Any}()
	key_order = Any[]
	for record in cases
		record isa AbstractDict || error("Q2D v3 case rows must be objects.")
		case_id = strip(String(get(record, "id", "")))
		!isempty(case_id) || error("Q2D v3 case id must be nonempty.")
		push!(record_ids, case_id)
		get(record, "schema_version", nothing) == expected.case_schema || error(
			"Q2D v3 case $(case_id) has a mixed case schema.",
		)
		get(record, "case_role", nothing) == expected.case_role || error(
			"Q2D v3 case $(case_id) has a mixed case role.",
		)
		parameters = get(record, "parameters", nothing)
		topology = get(record, "topology", nothing)
		parameters isa AbstractDict && topology isa AbstractDict || error(
			"Q2D v3 case $(case_id) must retain parameters and topology.",
		)
		get(parameters, "case_role", nothing) == expected.case_role || error(
			"Q2D v3 case $(case_id) parameter role is mixed.",
		)
		get(topology, "schema_version", nothing) == topology_schema || error(
			"Q2D v3 case $(case_id) topology schema is incompatible.",
		)
		String.(get(topology, "trace_names", Any[])) == expected.order || error(
			"Q2D v3 case $(case_id) topology conductor order is incompatible.",
		)
		get(topology, "reference_group", nothing) == "Ground" || error(
			"Q2D v3 case $(case_id) topology reference is incompatible.",
		)
		for (field, value) in (
			("resonator_die", "D0"),
			("resonator_face", "top"),
			("upper_die", "D1"),
			("upper_die_substrate_present", true),
			("upper_ground_face", "bottom"),
		)
			get(topology, field, nothing) == value || error(
				"Q2D v3 case $(case_id) has incompatible $(field) topology semantics.",
			)
		end
		clearance = Float64(get(topology, "upper_ground_clearance_width_um", NaN))
		alignment = get(topology, "upper_ground_clearance_alignment", nothing)
		continuous_upper_ground = endswith(
			topology_schema,
			"-continuous-upper-ground.v1",
		)
		if continuous_upper_ground
			get(topology, "upper_ground_metal_policy", nothing) ==
				"continuous_over_full_modeled_lateral_extent" || error(
				"Q2D v3 case $(case_id) must retain continuous upper-ground semantics.",
			)
			clearance == 0.0 || error(
				"Q2D v3 continuous-upper-ground case $(case_id) must use zero clearance.",
			)
			alignment in (nothing, "not_applicable") || error(
				"Q2D v3 continuous-upper-ground case $(case_id) has incompatible alignment.",
			)
		else
			get(topology, "upper_ground_metal_policy", nothing) ==
				"removed_only_within_local_clearance" || error(
				"Q2D v3 case $(case_id) must retain local-clearance semantics.",
			)
			isfinite(clearance) && clearance > 0 || error(
				"Q2D v3 case $(case_id) clearance must be finite and positive.",
			)
			(role === :coupled_pair ? alignment in (nothing, "centered") : alignment == "centered") || error(
				"Q2D v3 case $(case_id) has incompatible upper-ground clearance alignment.",
			)
		end
		Float64(get(parameters, "upper_ground_clearance_width_um", NaN)) == clearance || error(
			"Q2D v3 case $(case_id) parameter/topology clearance mismatch.",
		)
		trace_gap_um = Float64(get(parameters, "trace_gap_um", NaN))
		isfinite(trace_gap_um) && trace_gap_um > 0 || error(
			"Q2D v3 case $(case_id) trace gap must be finite and positive.",
		)
		trace_width_um = Float64(get(parameters, "trace_width_um", NaN))
		isfinite(trace_width_um) && trace_width_um > 0 || error(
			"Q2D v3 case $(case_id) trace width must be finite and positive.",
		)
		case_adaptive_frequency = strip(String(get(parameters, "adaptive_frequency", "")))
		case_adaptive_frequency == adaptive_frequency || error(
			"Q2D v3 case $(case_id) adaptive frequency disagrees with artifact metadata.",
		)
		cross_section = (
			flip_chip_gap_height_um = _d3_forward_positive_parameter(
				parameters, "flip_chip_gap_height_um", case_id,
			),
			d0_die_thickness_um = _d3_forward_positive_parameter(
				parameters, "d0_die_thickness_um", case_id,
			),
			d1_die_thickness_um = _d3_forward_positive_parameter(
				parameters, "d1_die_thickness_um", case_id,
			),
			air_height_um = _d3_forward_positive_parameter(
				parameters, "air_height_um", case_id,
			),
			ground_width_um = _d3_forward_positive_parameter(
				parameters, "ground_width_um", case_id,
			),
			metal_thickness_um = _d3_forward_positive_parameter(
				parameters, "metal_thickness_um", case_id,
			),
			adaptive_frequency = case_adaptive_frequency,
		)
		d_um = if role === :coupled_pair
			value = Float64(get(parameters, "inter_trace_ground_width_um", NaN))
			isfinite(value) && value > 0 || error(
				"Q2D v3 pair case $(case_id) must retain finite positive d.",
			)
			value
		else
			nothing
		end
		case_key = role === :coupled_pair ? (d_um, clearance) : clearance
		haskey(by_key, case_key) && error(
			"Q2D v3 artifact contains duplicate case identity $(case_key).",
		)
		l_matrix = _d3_forward_matrix(
			record["l_matrix_h_per_m"], expected.dimension, "Q2D v3 case $(case_id) L",
		)
		c_matrix = _d3_forward_matrix(
			record["c_matrix_f_per_m"], expected.dimension, "Q2D v3 case $(case_id) C",
		)
		all(>(0), vec(sum(c_matrix; dims = 2))) || error(
			"Q2D v3 case $(case_id) Maxwell C row sums must be positive.",
		)
		if role === :coupled_pair
			c_matrix[1, 2] < 0 || error("Q2D v3 pair Maxwell C12 must be negative.")
			l_matrix[1, 2] > 0 || error("Q2D v3 pair Maxwell L12 must be positive.")
		else
			l_matrix[1, 1] > 0 && c_matrix[1, 1] > 0 || error(
				"Q2D v3 single-reference scalar L/C must be positive.",
			)
		end
		by_key[case_key] = (
			case_id = case_id,
			clearance_um = clearance,
			d_um = d_um,
			trace_gap_um = trace_gap_um,
			trace_width_um = trace_width_um,
			cross_section = cross_section,
			l_matrix_h_per_m = l_matrix,
			c_matrix_f_per_m = c_matrix,
			source_hashes = _d3_forward_source_hashes(metadata, case_id),
		)
		push!(key_order, case_key)
	end
	length(record_ids) == length(unique(record_ids)) || error(
		"Q2D v3 artifact contains duplicate case ids.",
	)
	record_ids == declared_case_ids || error(
		"Q2D v3 run-provenance case ids do not exactly match the case rows.",
	)
	return (
		by_key = by_key,
		key_order = key_order,
		run_id = run_id,
		loss_terms = deepcopy(loss_terms),
		extraction_frequency_hz = extraction_frequency_hz,
		adaptive_frequency = adaptive_frequency,
		solver_provenance = deepcopy(get(metadata, "solver_provenance", Dict{String,Any}())),
	)
end

"""Load and exactly join homogeneous v3 pair/single Q2D cases."""
function load_d3_forward_q2d_cases(
	pair_json,
	single_json;
	expected_pair_cases = 9,
	expected_single_cases = 3,
)
	pair_path = String(pair_json)
	single_path = String(single_json)
	isfile(pair_path) || error("Missing D3 forward pair Q2D JSON: $(pair_path)")
	isfile(single_path) || error("Missing D3 forward single Q2D JSON: $(single_path)")
	pair_payload = SuperconductingCircuitsCore.JSON3.read(
		read(pair_path, String), Dict{String,Any},
	)
	single_payload = SuperconductingCircuitsCore.JSON3.read(
		read(single_path, String), Dict{String,Any},
	)
	pair = _d3_forward_validate_q2d_artifact(pair_payload, :coupled_pair)
	single = _d3_forward_validate_q2d_artifact(single_payload, :single_reference)
	length(pair.key_order) == expected_pair_cases &&
		length(single.key_order) == expected_single_cases || error(
		"D3 forward Q2D artifacts contain unexpected pair/single case counts.",
	)
	pair_clearances = Set(pair.by_key[key].clearance_um for key in pair.key_order)
	pair_clearances == Set(single.key_order) || error(
		"D3 forward Q2D pair/single clearances must match exactly; missing matches are forbidden.",
	)
	pair.run_id == single.run_id || error("D3 forward Q2D pair/single run ids must match.")
	pair.extraction_frequency_hz == single.extraction_frequency_hz || error(
		"D3 forward Q2D pair/single extraction frequencies must match.",
	)
	pair.adaptive_frequency == single.adaptive_frequency || error(
		"D3 forward Q2D pair/single adaptive frequencies must match.",
	)
	pair.solver_provenance == single.solver_provenance || error(
		"D3 forward Q2D pair/single solver provenance must match.",
	)
	return [
		begin
			pair_case = pair.by_key[pair_key]
			single_case = single.by_key[pair_case.clearance_um]
			pair_case.trace_width_um == single_case.trace_width_um &&
				pair_case.trace_gap_um == single_case.trace_gap_um || error(
				"D3 forward Q2D pair/single CPW width or gap disagrees at clearance $(pair_case.clearance_um) um.",
			)
			pair_case.cross_section == single_case.cross_section || error(
				"D3 forward Q2D pair/single cross-sections disagree at clearance $(pair_case.clearance_um) um.",
			)
			(
				id = Symbol("$(pair_case.case_id)__$(single_case.case_id)"),
				pair_case_id = pair_case.case_id,
				single_case_id = single_case.case_id,
				d_um = pair_case.d_um,
				inter_trace_ground_width_um = pair_case.d_um,
				trace_width_um = pair_case.trace_width_um,
				trace_gap_um = pair_case.trace_gap_um,
				upper_ground_clearance_width_um = pair_case.clearance_um,
				cross_section = pair_case.cross_section,
				mtl_l_matrix_h_per_m = pair_case.l_matrix_h_per_m,
				mtl_c_matrix_f_per_m = pair_case.c_matrix_f_per_m,
				single_l_matrix_h_per_m = single_case.l_matrix_h_per_m,
				single_c_matrix_f_per_m = single_case.c_matrix_f_per_m,
				single_l_per_m_h = single_case.l_matrix_h_per_m[1, 1],
				single_c_per_m_f = single_case.c_matrix_f_per_m[1, 1],
				source_artifacts = (
					pair = (
						run_id = pair.run_id,
						case_id = pair_case.case_id,
						source_hashes = pair_case.source_hashes,
					),
					single = (
						run_id = single.run_id,
						case_id = single_case.case_id,
						source_hashes = single_case.source_hashes,
					),
				),
				loss_terms = (pair = pair.loss_terms, single = single.loss_terms),
				extraction_frequency_hz = (
					pair = pair.extraction_frequency_hz,
					single = single.extraction_frequency_hz,
				),
				solver_provenance = (
					pair = pair.solver_provenance,
					single = single.solver_provenance,
				),
			)
		end
		for pair_key in pair.key_order
	]
end

function _d3_forward_section_length(section_length_m)
	section_length_m isa Real || error("D3 forward section length must be numeric.")
	value = Float64(section_length_m)
	isfinite(value) && value > 0 || error("D3 forward section length must be finite and positive.")
	return value
end

function _d3_forward_reference_impedance(feedline)
	values = Float64[
		feedline.l_per_m_h,
		feedline.c_per_m_f,
		feedline.r_per_m_ohm,
		feedline.g_per_m_s,
		feedline.target_impedance_ohm,
		feedline.max_abs_impedance_error_ohm,
		feedline.zo_ohm,
	]
	all(isfinite, values) || error("D3 forward feedline values must be finite.")
	values[1] > 0 && values[2] > 0 || error("D3 forward feedline L/C must be positive.")
	values[3] == 0 && values[4] == 0 || error(
		"D3 forward response requires exactly lossless feedline R=G=0.",
	)
	values[5] == 50.0 || error("D3 forward response requires an exact 50 Ohm reference target.")
	values[6] >= 0 || error("D3 forward feedline impedance-error gate must be nonnegative.")
	values[7] > 0 || error("D3 forward feedline z0 must be positive.")
	recomputed_z0 = sqrt(values[1] / values[2])
	recomputed_z0 == values[7] || error("D3 forward feedline z0 provenance is inconsistent.")
	abs(values[7] - values[5]) <= values[6] || error(
		"D3 forward feedline LC-derived z0 violates its declared 50 Ohm gate.",
	)
	return values[5]
end

function _d3_forward_feedline!(plan; feedline, length_m, section_length_m)
	length_value = Float64(length_m)
	isfinite(length_value) && length_value > 0 || error("D3 forward feedline length must be positive.")
	section_value = _d3_forward_section_length(section_length_m)
	reference_impedance_ohm = _d3_forward_reference_impedance(feedline)
	head = external_node("d3_forward_feedline_head")
	tail = external_node("d3_forward_feedline_tail")
	spec = RLGCSpec(
		length_m = length_value,
		section_length_m = section_value,
		l_per_m_h = feedline.l_per_m_h,
		c_per_m_f = feedline.c_per_m_f,
		r_per_m_ohm = feedline.r_per_m_ohm,
		g_per_m_s = feedline.g_per_m_s,
	)
	line = transmission_line!(
		plan;
		id = :d3_forward_open_feedline,
		head = head,
		tail = tail,
		spec = spec,
		head_termination = :open,
		tail_termination = :open,
		breakpoints_m = [length_value / 2],
	)
	return (
		line = line,
		head = head,
		tail = tail,
		center_tap = node_at_distance(line, length_value / 2),
		reference_impedance_ohm = reference_impedance_ohm,
	)
end

function _d3_forward_distributed_plan(
	case,
	design;
	section_length_m,
	floating_qubit_nominal,
	feedline,
	feedline_length_m,
	cext_f,
)
	plan = CircuitPlan("d3-forward-distributed-$(design.id)")
	section_value = _d3_forward_section_length(section_length_m)
	discretization = (section_length_m = section_value,)
	pair = add_mtl_pair!(
		plan; case = case, design = design, index = 1, hb_settings = discretization,
	)
	qubit = add_floating_qubit_nominal!(
		plan,
		pair.readout_open_tail,
		floating_qubit_nominal;
		id_prefix = "d3_forward_qubit",
	)
	line = _d3_forward_feedline!(
		plan;
		feedline = feedline,
		length_m = feedline_length_m,
		section_length_m = section_value,
	)
	cext = Float64(cext_f)
	isfinite(cext) && cext > 0 || error("D3 forward Cext must be finite and positive.")
	coupling = couple_capacitive!(
		plan;
		id = :d3_forward_Cext,
		from = pair.filter_open_tail,
		to = line.center_tap,
		capacitance = cext,
		role = :filter_to_feedline_capacitance,
	)
	return (plan = plan, pair = pair, qubit = qubit, feedline = line, cext = coupling)
end

function _d3_forward_resonator_model(case, design, section_length_m, kind)
	plan = CircuitPlan("d3-forward-resonator-$(kind)-$(design.id)")
	discretization = (section_length_m = _d3_forward_section_length(section_length_m),)
	nodes = if kind === :diagonal
		add_mtl_pair_diagonal_reference!(
			plan; case = case, design = design, index = 1, hb_settings = discretization,
		)
	elseif kind === :physical
		add_mtl_pair!(plan; case = case, design = design, index = 1, hb_settings = discretization)
	else
		error("D3 forward resonator model kind must be diagonal or physical.")
	end
	compiled = compile_to_josephson(plan)
	model = extract_linear_nodal_model(compiled)
	names = String[
		compiled.node_map[nodes.readout_open_tail],
		compiled.node_map[nodes.filter_open_tail],
	]
	indices = Int[]
	for name in names
		matches = findall(==(name), model.node_names)
		length(matches) == 1 || error("D3 forward resonator terminal $(name) must resolve exactly once.")
		push!(indices, only(matches))
	end
	return (plan = plan, nodes = nodes, compiled = compiled, model = model, terminal_names = names, terminal_indices = indices)
end

function _d3_forward_terminal_admittance(model, terminal_indices, terminal_position, angular_frequency)
	reduced = schur_dynamic_stiffness(
		model.capacitance,
		model.inverse_inductance,
		angular_frequency,
		terminal_indices,
	)
	return reduced.dynamic_stiffness[terminal_position, terminal_position] / (-im * angular_frequency)
end

function _d3_forward_match_elements(
	case,
	design;
	section_length_m,
	readout_root_bracket_hz,
	filter_root_bracket_hz,
	notch_root_bracket_hz,
	parallel_derivative_step_rad_s,
	bridge_derivative_step_rad_s,
	bisection_absolute_tolerance_rad_s,
	bisection_relative_tolerance,
	bisection_max_iterations,
	match_root_relative_tolerance,
	derivative_relative_tolerance,
)
	diagonal = _d3_forward_resonator_model(case, design, section_length_m, :diagonal)
	physical = _d3_forward_resonator_model(case, design, section_length_m, :physical)
	yr = angular_frequency -> _d3_forward_terminal_admittance(
		diagonal.model, diagonal.terminal_indices, 1, angular_frequency,
	)
	yp = angular_frequency -> _d3_forward_terminal_admittance(
		diagonal.model, diagonal.terminal_indices, 2, angular_frequency,
	)
	z21 = angular_frequency -> linear_terminal_response(
		physical.model.capacitance,
		physical.model.inverse_inductance,
		angular_frequency,
		physical.terminal_indices,
	).impedance[2, 1]
	bisection_kwargs = (
		absolute_tolerance = Float64(bisection_absolute_tolerance_rad_s),
		relative_tolerance = Float64(bisection_relative_tolerance),
		max_iterations = Int(bisection_max_iterations),
	)
	root = function (response, bracket_hz)
		bracket = 2π .* Float64.(collect(bracket_hz))
		return bracketed_bisection(
			angular_frequency -> imag(response(angular_frequency)),
			bracket;
			bisection_kwargs...,
		)
	end
	readout_root = root(yr, readout_root_bracket_hz)
	filter_root = root(yp, filter_root_bracket_hz)
	notch_root = root(z21, notch_root_bracket_hz)
	readout = match_parallel_lc(
		yr,
		readout_root;
		derivative_step_rad_s = parallel_derivative_step_rad_s,
		root_relative_tolerance = match_root_relative_tolerance,
		imaginary_derivative_relative_tolerance = derivative_relative_tolerance,
	)
	filter = match_parallel_lc(
		yp,
		filter_root;
		derivative_step_rad_s = parallel_derivative_step_rad_s,
		root_relative_tolerance = match_root_relative_tolerance,
		imaginary_derivative_relative_tolerance = derivative_relative_tolerance,
	)
	bridge = match_bridge_lc(
		z21,
		yr,
		yp,
		notch_root;
		derivative_step_rad_s = bridge_derivative_step_rad_s,
		root_relative_tolerance = match_root_relative_tolerance,
		imaginary_capacitance_relative_tolerance = derivative_relative_tolerance,
	)
	return (
		elements = (
			Cr_f = readout.capacitance_f,
			Lr_h = readout.inductance_h,
			Cp_f = filter.capacitance_f,
			Lp_h = filter.inductance_h,
			Cn_f = bridge.capacitance_f,
			Ln_h = bridge.inductance_h,
		),
		roots = (readout = readout, filter = filter, notch = bridge),
		diagonal_reference = diagonal,
		physical_pair = physical,
		provenance = (
			contract_id = "d3-response-matched-lc-v1",
			method = "bracketed bisection plus response-at-known-root LC recovery",
			bisection = bisection_kwargs,
			root_brackets_hz = (
				readout = Tuple(Float64.(collect(readout_root_bracket_hz))),
				filter = Tuple(Float64.(collect(filter_root_bracket_hz))),
				notch = Tuple(Float64.(collect(notch_root_bracket_hz))),
			),
			parallel_derivative_step_rad_s = Float64(parallel_derivative_step_rad_s),
			bridge_derivative_step_rad_s = Float64(bridge_derivative_step_rad_s),
			match_root_relative_tolerance = Float64(match_root_relative_tolerance),
			derivative_relative_tolerance = Float64(derivative_relative_tolerance),
		),
	)
end

function _d3_forward_equivalent_plan(
	design,
	elements;
	section_length_m,
	floating_qubit_nominal,
	feedline,
	feedline_length_m,
	cext_f,
)
	plan = CircuitPlan("d3-forward-equivalent-$(design.id)")
	section_value = _d3_forward_section_length(section_length_m)
	readout = external_node("d3_forward_equivalent_readout")
	filter = external_node("d3_forward_equivalent_filter")
	shunt_capacitor!(plan; id = :d3_forward_Cr, at = readout, capacitance = elements.Cr_f)
	shunt_inductor!(plan; id = :d3_forward_Lr, at = readout, inductance = elements.Lr_h)
	shunt_capacitor!(plan; id = :d3_forward_Cp, at = filter, capacitance = elements.Cp_f)
	shunt_inductor!(plan; id = :d3_forward_Lp, at = filter, inductance = elements.Lp_h)
	couple_capacitive!(
		plan;
		id = :d3_forward_Cn,
		from = readout,
		to = filter,
		capacitance = elements.Cn_f,
		role = :response_matched_bridge_capacitance,
	)
	series_inductor!(
		plan;
		id = :d3_forward_Ln,
		from = readout,
		to = filter,
		inductance = elements.Ln_h,
		role = :response_matched_bridge_inductance,
	)
	qubit = add_floating_qubit_nominal!(
		plan,
		readout,
		floating_qubit_nominal;
		id_prefix = "d3_forward_qubit",
	)
	line = _d3_forward_feedline!(
		plan;
		feedline = feedline,
		length_m = feedline_length_m,
		section_length_m = section_value,
	)
	cext = Float64(cext_f)
	isfinite(cext) && cext > 0 || error("D3 forward Cext must be finite and positive.")
	coupling = couple_capacitive!(
		plan;
		id = :d3_forward_Cext,
		from = filter,
		to = line.center_tap,
		capacitance = cext,
		role = :filter_to_feedline_capacitance,
	)
	return (
		plan = plan,
		readout = readout,
		filter = filter,
		qubit = qubit,
		feedline = line,
		cext = coupling,
	)
end

function _d3_forward_feedline_reference_plan(design; section_length_m, feedline, feedline_length_m)
	plan = CircuitPlan("d3-forward-feedline-reference-$(design.id)")
	line = _d3_forward_feedline!(
		plan;
		feedline = feedline,
		length_m = feedline_length_m,
		section_length_m = section_length_m,
	)
	return (plan = plan, feedline = line)
end

function _d3_forward_response_trace(
	plan_bundle,
	frequency_grid_hz;
	z_closure_absolute_tolerance_ohm,
	s_closure_absolute_tolerance,
	closure_relative_tolerance,
)
	compiled = compile_to_josephson(plan_bundle.plan)
	isempty(compiled.port_map) || error("D3 forward conservative plan must not contain ports.")
	compiled.hb_intent_summary === nothing || error("D3 forward conservative plan must not contain HB intent.")
	isempty(compiled.source_slot_map) || error("D3 forward conservative plan must not contain sources.")
	isempty(compiled.observable_request_map) || error("D3 forward conservative plan must not contain observables.")
	model = extract_linear_nodal_model(compiled)
	terminal_names = String[
		compiled.node_map[plan_bundle.feedline.head],
		compiled.node_map[plan_bundle.feedline.tail],
	]
	terminal_indices = Int[]
	for name in terminal_names
		matches = findall(==(name), model.node_names)
		length(matches) == 1 || error("D3 forward feedline terminal $(name) must resolve exactly once.")
		push!(terminal_indices, only(matches))
	end
	length(unique(terminal_indices)) == 2 || error("D3 forward feedline terminals must be distinct.")
	selector = zeros(Float64, length(model.node_names), 2)
	for port in 1:2
		selector[terminal_indices[port], port] = 1.0
	end
	frequencies = Float64.(collect(frequency_grid_hz))
	length(frequencies) >= 2 && all(isfinite, frequencies) && all(>(0), frequencies) &&
		all(diff(frequencies) .> 0) || error(
		"D3 forward frequency grid must contain finite, positive, strictly increasing points.",
	)
	z0 = plan_bundle.feedline.reference_impedance_ohm
	scattering = Matrix{ComplexF64}[]
	matched_impedance = Matrix{ComplexF64}[]
	closed_impedance = Matrix{ComplexF64}[]
	z_closure_residual_ohm = Float64[]
	s_closure_residual = Float64[]
	for frequency in frequencies
		angular_frequency = 2π * frequency
		matched = matched_port_response(
			model.capacitance,
			model.inverse_inductance,
			angular_frequency,
			selector,
			z0,
		)
		closed = linear_terminal_response(
			model.capacitance,
			model.inverse_inductance,
			angular_frequency,
			terminal_indices,
		)
		z_from_s = scattering_to_impedance(matched.scattering, z0)
		s_from_z = impedance_to_scattering(closed.impedance, z0)
		z_residual = maximum(abs, z_from_s - closed.impedance)
		s_residual = maximum(abs, matched.scattering - s_from_z)
		z_scale = max(maximum(abs, z_from_s), maximum(abs, closed.impedance), floatmin(Float64))
		s_scale = max(maximum(abs, matched.scattering), maximum(abs, s_from_z), floatmin(Float64))
		z_residual <= Float64(z_closure_absolute_tolerance_ohm) +
			Float64(closure_relative_tolerance) * z_scale || error(
			"D3 forward S-to-Z closure failed at $(frequency) Hz.",
		)
		s_residual <= Float64(s_closure_absolute_tolerance) +
			Float64(closure_relative_tolerance) * s_scale || error(
			"D3 forward Z-to-S closure failed at $(frequency) Hz.",
		)
		push!(scattering, matched.scattering)
		push!(matched_impedance, matched.impedance)
		push!(closed_impedance, closed.impedance)
		push!(z_closure_residual_ohm, z_residual)
		push!(s_closure_residual, s_residual)
	end
	poles = matched_open_poles(
		model.capacitance,
		model.inverse_inductance,
		selector,
		z0,
	)
	return (
		plan = plan_bundle.plan,
		compiled = compiled,
		model = model,
		terminal_names = terminal_names,
		terminal_indices = terminal_indices,
		selector = selector,
		frequency_hz = frequencies,
		angular_frequency_rad_s = 2π .* frequencies,
		scattering = scattering,
		matched_impedance_ohm = matched_impedance,
		closed_impedance_ohm = closed_impedance,
		s21 = ComplexF64[matrix[2, 1] for matrix in scattering],
		z21_ohm = ComplexF64[matrix[2, 1] for matrix in closed_impedance],
		reference_plane = (
			terminal_names = copy(terminal_names),
			reference_impedance_ohm = z0,
			line_id = plan_bundle.feedline.line.id,
			section_lengths_m = copy(plan_bundle.feedline.line.section_lengths_m),
			section_boundaries_m = copy(plan_bundle.feedline.line.section_boundaries_m),
			section_rlgc_per_m = copy(plan_bundle.feedline.line.section_rlgc_per_m),
		),
		closure = (
			z_from_s_max_residual_ohm = maximum(z_closure_residual_ohm),
			s_from_z_max_residual = maximum(s_closure_residual),
			z_from_s_residual_ohm = z_closure_residual_ohm,
			s_from_z_residual = s_closure_residual,
			tolerances = (
				z_absolute_ohm = Float64(z_closure_absolute_tolerance_ohm),
				s_absolute = Float64(s_closure_absolute_tolerance),
				relative = Float64(closure_relative_tolerance),
			),
		),
		poles = poles,
		hashes = (
			source_sha256 = model.source_sha256,
			node_order_sha256 = model.node_order_sha256,
			capacitance_sha256 = model.capacitance_sha256,
			inverse_inductance_sha256 = model.inverse_inductance_sha256,
			open_poles = poles.hashes,
		),
		provenance = (
			model = model.provenance,
			open_poles = poles.provenance,
			time_convention = "exp(-i*omega*t)",
		),
	)
end

function _d3_forward_complex_residual(distributed, equivalent)
	length(distributed) == length(equivalent) > 0 || error(
		"D3 forward comparison traces must be nonempty and aligned.",
	)
	residual = ComplexF64.(distributed .- equivalent)
	return (
		complex_residual = residual,
		max_abs = maximum(abs, residual),
		rms_abs = sqrt(sum(abs2, residual) / length(residual)),
	)
end

function _d3_forward_calibrate_s21(distributed, equivalent, reference, minimum_magnitude)
	length(distributed) == length(equivalent) == length(reference) > 0 || error(
		"D3 forward calibration traces must be nonempty and aligned.",
	)
	threshold = Float64(minimum_magnitude)
	isfinite(threshold) && threshold > 0 || error(
		"D3 forward minimum reference magnitude must be finite and positive.",
	)
	all(value -> isfinite(real(value)) && isfinite(imag(value)), reference) || error(
		"D3 forward feedline-reference S21 must be finite.",
	)
	minimum_observed = minimum(abs, reference)
	minimum_observed >= threshold || error(
		"D3 forward feedline-reference S21 magnitude $(minimum_observed) is unsafe for division.",
	)
	return (
		reference_s21 = ComplexF64.(reference),
		distributed_s21 = ComplexF64.(distributed ./ reference),
		equivalent_s21 = ComplexF64.(equivalent ./ reference),
		minimum_reference_magnitude = threshold,
		minimum_observed_reference_magnitude = minimum_observed,
		provenance = (
			contract_id = "d3-feedline-reference-calibration-v1",
			operation = "pointwise complex S21_full divided by S21_feedline_only",
			reference_plane = "matched terminal planes at both ends of the same finite open-feedline ladder",
			direct_path_treatment = "exact feedline-only division; no fitted or subtracted direct path",
		),
	)
end

"""Evaluate exact distributed and response-matched D3 forward responses.

The result reports numerical residuals and evidence only. It deliberately does
not decide whether those residuals are acceptable for a design.
"""
function evaluate_d3_forward_response(
	case,
	design;
	section_length_m,
	floating_qubit_nominal,
	feedline,
	feedline_length_m,
	cext_f,
	frequency_grid_hz,
	readout_root_bracket_hz,
	filter_root_bracket_hz,
	notch_root_bracket_hz,
	parallel_derivative_step_rad_s,
	bridge_derivative_step_rad_s,
	bisection_absolute_tolerance_rad_s,
	bisection_relative_tolerance,
	bisection_max_iterations,
	match_root_relative_tolerance,
	derivative_relative_tolerance,
	z_closure_absolute_tolerance_ohm,
	s_closure_absolute_tolerance,
	closure_relative_tolerance,
	calibration_minimum_reference_magnitude,
)
	section_value = _d3_forward_section_length(section_length_m)
	_d3_forward_reference_impedance(feedline)
	matching = _d3_forward_match_elements(
		case,
		design;
		section_length_m = section_value,
		readout_root_bracket_hz = readout_root_bracket_hz,
		filter_root_bracket_hz = filter_root_bracket_hz,
		notch_root_bracket_hz = notch_root_bracket_hz,
		parallel_derivative_step_rad_s = parallel_derivative_step_rad_s,
		bridge_derivative_step_rad_s = bridge_derivative_step_rad_s,
		bisection_absolute_tolerance_rad_s = bisection_absolute_tolerance_rad_s,
		bisection_relative_tolerance = bisection_relative_tolerance,
		bisection_max_iterations = bisection_max_iterations,
		match_root_relative_tolerance = match_root_relative_tolerance,
		derivative_relative_tolerance = derivative_relative_tolerance,
	)
	distributed_plan = _d3_forward_distributed_plan(
		case,
		design;
		section_length_m = section_value,
		floating_qubit_nominal = floating_qubit_nominal,
		feedline = feedline,
		feedline_length_m = feedline_length_m,
		cext_f = cext_f,
	)
	equivalent_plan = _d3_forward_equivalent_plan(
		design,
		matching.elements;
		section_length_m = section_value,
		floating_qubit_nominal = floating_qubit_nominal,
		feedline = feedline,
		feedline_length_m = feedline_length_m,
		cext_f = cext_f,
	)
	reference_plan = _d3_forward_feedline_reference_plan(
		design;
		section_length_m = section_value,
		feedline = feedline,
		feedline_length_m = feedline_length_m,
	)
	trace_kwargs = (
		z_closure_absolute_tolerance_ohm = z_closure_absolute_tolerance_ohm,
		s_closure_absolute_tolerance = s_closure_absolute_tolerance,
		closure_relative_tolerance = closure_relative_tolerance,
	)
	distributed = _d3_forward_response_trace(
		distributed_plan,
		frequency_grid_hz;
		trace_kwargs...,
	)
	equivalent = _d3_forward_response_trace(
		equivalent_plan,
		frequency_grid_hz;
		trace_kwargs...,
	)
	reference = _d3_forward_response_trace(
		reference_plan,
		frequency_grid_hz;
		trace_kwargs...,
	)
	distributed.terminal_names == equivalent.terminal_names || error(
		"D3 forward distributed/equivalent terminal ordering must be identical.",
	)
	distributed.terminal_names == reference.terminal_names || error(
		"D3 forward feedline reference must use the same ordered terminal planes.",
	)
	distributed.frequency_hz == equivalent.frequency_hz == reference.frequency_hz || error(
		"D3 forward distributed/equivalent/reference frequency grids must match exactly.",
	)
	distributed.reference_plane == equivalent.reference_plane == reference.reference_plane || error(
		"D3 forward distributed/equivalent/reference feedline sections and z0 must match exactly.",
	)
	calibration = merge(_d3_forward_calibrate_s21(
		distributed.s21,
		equivalent.s21,
		reference.s21,
		calibration_minimum_reference_magnitude,
	), (
		frequency_hz = copy(reference.frequency_hz),
		reference_plane = reference.reference_plane,
		reference_hashes = reference.hashes,
	))
	return (
		contract_id = D3_FORWARD_RESPONSE_CONTRACT_ID,
		matching = matching,
		distributed = distributed,
		equivalent = equivalent,
		feedline_reference = reference,
		calibration = calibration,
		residuals = (
			s21 = _d3_forward_complex_residual(
				calibration.distributed_s21, calibration.equivalent_s21,
			),
			raw_s21 = _d3_forward_complex_residual(distributed.s21, equivalent.s21),
			z21 = _d3_forward_complex_residual(distributed.z21_ohm, equivalent.z21_ohm),
		),
		provenance = (
			case_id = String(case.id),
			design_id = String(design.id),
			qubit_model_id = floating_qubit_nominal.model_id,
			feedline_source = feedline.source,
			feedline_length_m = Float64(feedline_length_m),
			feedline_section_length_m = section_value,
			filter_to_feedline_capacitance_f = Float64(cext_f),
			q2d_source_artifacts = hasproperty(case, :source_artifacts) ?
				case.source_artifacts : nothing,
			response_contract = D3_FORWARD_RESPONSE_CONTRACT_ID,
		),
	)
end
