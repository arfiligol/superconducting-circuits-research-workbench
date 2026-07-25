# This file owns the D3-specific conservative closed-circuit handoff from the
# distributed q-r-p circuit into a three-mode quadratic Hamiltonian. It does
# not own S-parameter fitting, lossy ports, optimization, or notebook control
# flow. The low-level D3 topology and Core modal algebra remain owned by
# d3_purcell_common.jl and SuperconductingCircuitsCore respectively.

import LinearAlgebra

"""Declare one q/r/p mode-ownership window for the forward handoff.

Coupling-off selection first requires the mode frequency to lie in
`frequency_window_hz` and its normalized node-flux weight on
`participation_node_names` to meet the declared threshold. A prior node-flux
vector may resolve multiple eligible modes by continuation overlap; otherwise
multiple eligible modes fail as ambiguous. Physical-on modes are continued
from those selected off vectors over the exact spectrum. No nearest-frequency
fallback exists.
"""
struct D3ForwardModeTarget
	role::Symbol
	frequency_window_hz::Tuple{Float64,Float64}
	participation_node_names::Vector{String}
	minimum_node_flux_participation::Float64
	continuation_node_flux::Union{Nothing,Vector{Float64}}
	minimum_continuation_overlap::Float64
end

function D3ForwardModeTarget(;
	role,
	frequency_window_hz,
	participation_node_names,
	minimum_node_flux_participation,
	continuation_node_flux = nothing,
	minimum_continuation_overlap = 0.0,
)
	mode_role = Symbol(role)
	mode_role in (:q, :r, :p) || error("D3 forward mode role must be q, r, or p.")
	window_values = Float64.(collect(frequency_window_hz))
	length(window_values) == 2 || error("D3 forward frequency window must have two endpoints.")
	all(isfinite, window_values) && 0 < window_values[1] < window_values[2] || error(
		"D3 forward frequency window endpoints must be finite, positive, and increasing.",
	)
	node_names = String.(collect(participation_node_names))
	!isempty(node_names) && length(unique(node_names)) == length(node_names) || error(
		"D3 forward participation node names must be nonempty and unique.",
	)
	minimum_participation = Float64(minimum_node_flux_participation)
	isfinite(minimum_participation) && 0 < minimum_participation <= 1 || error(
		"D3 forward minimum node-flux participation must lie in (0, 1].",
	)
	minimum_overlap = Float64(minimum_continuation_overlap)
	isfinite(minimum_overlap) && 0 <= minimum_overlap <= 1 || error(
		"D3 forward minimum continuation overlap must lie in [0, 1].",
	)
	continuation = if isnothing(continuation_node_flux)
		nothing
	else
		values = Float64.(collect(continuation_node_flux))
		!isempty(values) && all(isfinite, values) && LinearAlgebra.norm(values) > 0 || error(
			"D3 forward continuation node-flux vector must be nonempty, finite, and nonzero.",
		)
		values
	end
	return D3ForwardModeTarget(
		mode_role,
		(window_values[1], window_values[2]),
		node_names,
		minimum_participation,
		continuation,
		minimum_overlap,
	)
end

function _d3_forward_external_node_name(endpoint)
	endpoint isa ExternalNodeEndpoint || error(
		"D3 forward participation anchors must be external node endpoints.",
	)
	occursin(r"^[A-Za-z0-9_]+$", endpoint.name) || error(
		"D3 forward external node names must use the compiler-stable alphanumeric/underscore subset.",
	)
	return "ext_$(endpoint.name)"
end

function _add_d3_forward_maxwell_diagonal_pair!(circuit_plan; case, design, index, hb_settings)
	lr_total_m = design.lr_total_um * D3_METERS_PER_UM
	lp_total_m = design.lp_total_um * D3_METERS_PER_UM
	lr_short_m = design.lr_short_um * D3_METERS_PER_UM
	lp_short_m = design.lp_short_um * D3_METERS_PER_UM
	lc_m = design.lc_um * D3_METERS_PER_UM
	readout_spec = RLGCSpec(
		length_m = lr_total_m,
		section_length_m = hb_settings.section_length_m,
		l_per_m_h = case.single_l_per_m_h,
		c_per_m_f = case.single_c_per_m_f,
	)
	filter_spec = RLGCSpec(
		length_m = lp_total_m,
		section_length_m = hb_settings.section_length_m,
		l_per_m_h = case.single_l_per_m_h,
		c_per_m_f = case.single_c_per_m_f,
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
		spec = readout_spec,
		breakpoints_m = [lr_short_m, lr_short_m + lc_m],
		section_overrides = [
			TransmissionLineSectionOverride(
				start_m = lr_short_m,
				length_m = lc_m,
				l_per_m_h = case.mtl_l_matrix_h_per_m[1, 1],
				c_per_m_f = case.mtl_c_matrix_f_per_m[1, 1],
				tag = :d3_forward_mtl_diagonal_readout,
			),
		],
	)
	filter_resonator = quarter_wave_resonator!(
		circuit_plan;
		id = Symbol("filter_resonator_$(index)"),
		grounded_head = filter_grounded_head,
		open_tail = filter_open_tail,
		spec = filter_spec,
		breakpoints_m = [lp_short_m, lp_short_m + lc_m],
		section_overrides = [
			TransmissionLineSectionOverride(
				start_m = lp_short_m,
				length_m = lc_m,
				l_per_m_h = case.mtl_l_matrix_h_per_m[2, 2],
				c_per_m_f = case.mtl_c_matrix_f_per_m[2, 2],
				tag = :d3_forward_mtl_diagonal_filter,
			),
		],
	)
	return (
		readout_open_tail = readout_open_tail,
		filter_open_tail = filter_open_tail,
		readout_line = readout_resonator.line,
		filter_line = filter_resonator.line,
	)
end

"""Build the D3 coupling-off and physical-on conservative closed plans.

Both plans use identical external node names, resonator IDs, breakpoints, and
section counts. The off plan retains Maxwell `Lii/Cii` self entries and the
`C0r`, Cr1, and Cr2 node-basis diagonals. The on plan restores the full Q2D
`C12/L12` window and physical Cr1/Cr2 cross branches while retaining the same
local `C0r` shunt.
"""
function build_d3_forward_closed_plan_pair(
	case,
	design;
	hb_settings,
	floating_qubit_nominal::D3FloatingQubitNominal,
)
	off_plan = CircuitPlan("d3-forward-coupling-off-$(design.id)")
	on_plan = CircuitPlan("d3-forward-physical-on-$(design.id)")
	off_pair = _add_d3_forward_maxwell_diagonal_pair!(
		off_plan;
		case = case,
		design = design,
		index = 1,
		hb_settings = hb_settings,
	)
	on_pair = add_mtl_pair!(
		on_plan;
		case = case,
		design = design,
		index = 1,
		hb_settings = hb_settings,
	)
	on_ladders = on_plan.metadata[:transmission_line_ladders]
	on_pair = merge(on_pair, (
		readout_line = on_ladders[:readout_resonator_1],
		filter_line = on_ladders[:filter_resonator_1],
	))
	qubit_prefix = "d3_forward_qubit_1"
	off_qubit = add_floating_qubit_mode_layer_coupling_off!(
		off_plan,
		off_pair.readout_open_tail,
		floating_qubit_nominal;
		id_prefix = qubit_prefix,
	)
	on_qubit = add_floating_qubit_nominal!(
		on_plan,
		on_pair.readout_open_tail,
		floating_qubit_nominal;
		id_prefix = qubit_prefix,
	)
	off_plan.metadata[:d3_forward_coupling_state] = :diagonal_preserving_off
	on_plan.metadata[:d3_forward_coupling_state] = :physical_on
	participation_nodes = (
		q = [
			_d3_forward_external_node_name(off_qubit.island1),
			_d3_forward_external_node_name(off_qubit.island2),
		],
		r = [_d3_forward_external_node_name(off_pair.readout_open_tail)],
		p = [_d3_forward_external_node_name(off_pair.filter_open_tail)],
	)
	return (
		coupling_off = (plan = off_plan, pair_nodes = off_pair, qubit_nodes = off_qubit),
		physical_on = (plan = on_plan, pair_nodes = on_pair, qubit_nodes = on_qubit),
		participation_node_names = participation_nodes,
	)
end

function _d3_forward_target_order(mode_targets)
	targets = D3ForwardModeTarget[target for target in mode_targets]
	length(targets) == 3 || error("D3 forward handoff requires exactly three q/r/p mode targets.")
	by_role = Dict{Symbol,D3ForwardModeTarget}()
	for target in targets
		haskey(by_role, target.role) && error("D3 forward mode targets must have unique q/r/p roles.")
		by_role[target.role] = target
	end
	Set(keys(by_role)) == Set((:q, :r, :p)) || error(
		"D3 forward mode targets must declare exactly q, r, and p.",
	)
	return [by_role[:q], by_role[:r], by_role[:p]]
end

function _d3_forward_flux_participation(vector, node_indices)
	denominator = sum(abs2, vector)
	isfinite(denominator) && denominator > 0 || error("D3 forward mode has zero or non-finite node flux.")
	return sum(abs2, vector[node_indices]) / denominator
end

function _d3_forward_continuation_overlap(reference, candidate)
	length(reference) == length(candidate) || error(
		"D3 forward continuation vector does not match the current ordered-node dimension.",
	)
	denominator = LinearAlgebra.norm(reference) * LinearAlgebra.norm(candidate)
	isfinite(denominator) && denominator > 0 || error(
		"D3 forward continuation overlap requires two finite nonzero node-flux vectors.",
	)
	return abs(LinearAlgebra.dot(reference, candidate)) / denominator
end

function _d3_forward_select_mode(
	modes::GeneralizedModeSolution,
	target::D3ForwardModeTarget;
	continuation_override = nothing,
	enforce_frequency_window = true,
	selection_label,
)
	node_indices = Int[]
	for node_name in target.participation_node_names
		index = findfirst(==(node_name), modes.model.source.node_names)
		isnothing(index) && error(
			"D3 forward $(selection_label) $(target.role) target references missing node $(node_name).",
		)
		push!(node_indices, index)
	end
	window_indices = enforce_frequency_window ? findall(
		frequency -> target.frequency_window_hz[1] <= frequency <= target.frequency_window_hz[2],
		modes.frequencies_hz,
	) : collect(eachindex(modes.frequencies_hz))
	isempty(window_indices) && error(
		"D3 forward $(selection_label) $(target.role) target has no mode in its declared frequency window.",
	)
	continuation = isnothing(continuation_override) ? target.continuation_node_flux :
		Float64.(collect(continuation_override))
	candidates = [
		begin
			flux = modes.node_flux_vectors[:, mode_index]
			(
				mode_index = mode_index,
				frequency_hz = modes.frequencies_hz[mode_index],
				node_flux_participation = _d3_forward_flux_participation(flux, node_indices),
				continuation_overlap = isnothing(continuation) ? nothing :
					_d3_forward_continuation_overlap(continuation, flux),
			)
		end
		for mode_index in window_indices
	]
	eligible = [
		candidate for candidate in candidates
		if candidate.node_flux_participation >= target.minimum_node_flux_participation &&
			(isnothing(continuation) || candidate.continuation_overlap >= target.minimum_continuation_overlap)
	]
	isempty(eligible) && error(
		"D3 forward $(selection_label) $(target.role) target has no mode meeting its declared participation/continuation thresholds.",
	)
	selected = if length(eligible) == 1
		only(eligible)
	elseif isnothing(continuation)
		error(
			"D3 forward $(selection_label) $(target.role) target is ambiguous: multiple modes meet its window and participation threshold.",
		)
	else
		best_overlap = maximum(candidate.continuation_overlap for candidate in eligible)
		overlap_tolerance = 2048.0 * eps(Float64)
		winners = [
			candidate for candidate in eligible
			if abs(candidate.continuation_overlap - best_overlap) <= overlap_tolerance
		]
		length(winners) == 1 || error(
			"D3 forward $(selection_label) $(target.role) continuation is ambiguous between multiple modes.",
		)
		only(winners)
	end
	return merge(selected, (
		role = target.role,
		frequency_window_hz = target.frequency_window_hz,
		frequency_window_enforced = enforce_frequency_window,
		participation_node_names = copy(target.participation_node_names),
		minimum_node_flux_participation = target.minimum_node_flux_participation,
		minimum_continuation_overlap = target.minimum_continuation_overlap,
		candidate_modes = candidates,
		node_flux_vector = copy(modes.node_flux_vectors[:, selected.mode_index]),
	))
end

function _d3_forward_select_qrp_modes(
	modes,
	targets;
	continuation_overrides = nothing,
	enforce_frequency_window = true,
	selection_label,
)
	selections = [
		_d3_forward_select_mode(
			modes,
			targets[index];
			continuation_override = isnothing(continuation_overrides) ? nothing :
				continuation_overrides[index],
			enforce_frequency_window = enforce_frequency_window,
			selection_label = selection_label,
		)
		for index in eachindex(targets)
	]
	indices = [selection.mode_index for selection in selections]
	length(unique(indices)) == 3 || error(
		"D3 forward $(selection_label) q/r/p ownership is ambiguous because roles selected the same mode.",
	)
	return selections
end

function _d3_forward_gauge(number_conserving_hz, pairing_hz)
	hamiltonian = Matrix{Float64}(number_conserving_hz)
	pairing = Matrix{Float64}(pairing_hz)
	size(hamiltonian) == (3, 3) && size(pairing) == (3, 3) || error(
		"D3 forward gauge requires 3x3 number-conserving and pairing matrices.",
	)
	q_sign = 1.0
	r_sign = hamiltonian[1, 2] < 0 ? -1.0 : 1.0
	p_sign = r_sign * hamiltonian[2, 3] < 0 ? -1.0 : 1.0
	signs = Float64[q_sign, r_sign, p_sign]
	gauge = LinearAlgebra.Diagonal(signs)
	gauged_hamiltonian = Matrix{Float64}(gauge * hamiltonian * gauge)
	gauged_pairing = Matrix{Float64}(gauge * pairing * gauge)
	gauged_hamiltonian[1, 2] >= 0 && gauged_hamiltonian[2, 3] >= 0 || error(
		"D3 forward deterministic gauge failed to make g and J nonnegative.",
	)
	return (
		signs = signs,
		number_conserving_matrix_hz = gauged_hamiltonian,
		pairing_matrix_hz = gauged_pairing,
	)
end

function _d3_forward_diagonal_tolerance(first_diagonal, second_diagonal)
	scale = max(maximum(abs, first_diagonal), maximum(abs, second_diagonal), floatmin(Float64))
	return 512.0 * max(length(first_diagonal), 1) * eps(Float64) * scale
end

function _d3_forward_identity(value, field, fallback)
	return hasproperty(value, field) ? getproperty(value, field) : fallback
end

"""Execute one forward-only D3 closed-circuit to q-r-p Hamiltonian handoff."""
function evaluate_d3_forward_closed_handoff(
	case,
	design;
	hb_settings,
	floating_qubit_nominal::D3FloatingQubitNominal,
	mode_targets,
)
	targets = _d3_forward_target_order(mode_targets)
	plans = build_d3_forward_closed_plan_pair(
		case,
		design;
		hb_settings = hb_settings,
		floating_qubit_nominal = floating_qubit_nominal,
	)
	off_compiled = compile_to_josephson(plans.coupling_off.plan)
	on_compiled = compile_to_josephson(plans.physical_on.plan)
	isempty(off_compiled.port_map) && isempty(on_compiled.port_map) || error(
		"D3 forward closed handoff does not permit external ports.",
	)
	off_model = extract_linear_nodal_model(off_compiled)
	on_model = extract_linear_nodal_model(on_compiled)
	off_model.node_names == on_model.node_names || error(
		"D3 forward coupling-off and physical-on plans must compile to identical ordered nodes.",
	)
	off_diagonal = [off_model.capacitance[index, index] for index in axes(off_model.capacitance, 1)]
	on_diagonal = [on_model.capacitance[index, index] for index in axes(on_model.capacitance, 1)]
	diagonal_residual = maximum(abs, off_diagonal .- on_diagonal)
	diagonal_tolerance = _d3_forward_diagonal_tolerance(off_diagonal, on_diagonal)
	diagonal_residual <= diagonal_tolerance || error(
		"D3 forward off/on capacitance nodal diagonals are not preserved.",
	)

	reduced = reduce_linear_model_pair(off_model, on_model)
	off_modes = solve_generalized_modes(reduced.coupling_off)
	on_modes = solve_generalized_modes(reduced.physical_on)
	off_selections = _d3_forward_select_qrp_modes(
		off_modes,
		targets;
		selection_label = "coupling-off",
	)
	# Physical hybrid modes may move outside a bare ownership window. Match them
	# over the full exact spectrum by node-flux continuation from the selected
	# off modes; this is deliberately not a nearest-frequency association.
	on_selections = _d3_forward_select_qrp_modes(
		on_modes,
		targets;
		continuation_overrides = [selection.node_flux_vector for selection in off_selections],
		enforce_frequency_window = false,
		selection_label = "physical-on",
	)
	off_indices = [selection.mode_index for selection in off_selections]
	projection = project_selected_modes(off_modes, reduced.physical_on, off_indices)
	exact_on_frequencies = [selection.frequency_hz for selection in on_selections]
	closure = linear_projection_closure(projection, exact_on_frequencies)
	raw_hamiltonian_hz = projection.number_conserving_matrix_rad_s ./ (2π)
	raw_pairing_hz = projection.pairing_matrix_rad_s ./ (2π)
	gauge = _d3_forward_gauge(raw_hamiltonian_hz, raw_pairing_hz)
	hamiltonian_hz = gauge.number_conserving_matrix_hz

	return (
		contract_id = "d3-forward-closed-qrp-handoff-v1",
		mode_order = (:q, :r, :p),
		fq_hz = hamiltonian_hz[1, 1],
		fr_hz = hamiltonian_hz[2, 2],
		fp_hz = hamiltonian_hz[3, 3],
		g_hz = hamiltonian_hz[1, 2],
		G_hz = hamiltonian_hz[1, 3],
		g_qp_signed_hz = hamiltonian_hz[1, 3],
		J_hz = hamiltonian_hz[2, 3],
		number_conserving_matrix_hz = hamiltonian_hz,
		pairing_matrix_hz = gauge.pairing_matrix_hz,
		gauge_signs = gauge.signs,
		loaded_bare_frequencies_hz = projection.loaded_bare_angular_frequencies_rad_s ./ (2π),
		coupling_off_mode_selection = off_selections,
		physical_on_mode_selection = on_selections,
		exact_physical_on_selected_frequencies_hz = exact_on_frequencies,
		exact_physical_on_all_frequencies_hz = copy(on_modes.frequencies_hz),
		projected_bdg_frequencies_hz = copy(projection.projected_bdg_frequencies_hz),
		projected_rwa_frequencies_hz = copy(projection.projected_rwa_frequencies_hz),
		projection_closure = closure,
		non_rwa = (
			pairing_matrix_hz = gauge.pairing_matrix_hz,
			projected_bdg_frequencies_hz = copy(projection.projected_bdg_frequencies_hz),
			projected_rwa_frequencies_hz = copy(projection.projected_rwa_frequencies_hz),
			rwa_minus_bdg_hz = copy(closure.rwa_minus_bdg_hz),
		),
		nodal_diagonal_closure = (
			capacitance_max_abs_residual_f = diagonal_residual,
			capacitance_tolerance_f = diagonal_tolerance,
			inverse_inductance_equal = off_model.inverse_inductance == on_model.inverse_inductance,
		),
		hashes = (
			node_order_sha256 = off_model.node_order_sha256,
			coupling_off = (
				source_sha256 = off_model.source_sha256,
				capacitance_sha256 = off_model.capacitance_sha256,
				inverse_inductance_sha256 = off_model.inverse_inductance_sha256,
				reduced_capacitance_sha256 = reduced.coupling_off.capacitance_sha256,
				reduced_inverse_inductance_sha256 = reduced.coupling_off.inverse_inductance_sha256,
			),
			physical_on = (
				source_sha256 = on_model.source_sha256,
				capacitance_sha256 = on_model.capacitance_sha256,
				inverse_inductance_sha256 = on_model.inverse_inductance_sha256,
				reduced_capacitance_sha256 = reduced.physical_on.capacitance_sha256,
				reduced_inverse_inductance_sha256 = reduced.physical_on.inverse_inductance_sha256,
			),
		),
		provenance = (
			case_id = String(_d3_forward_identity(case, :id, :unspecified_case)),
			design_id = String(_d3_forward_identity(design, :id, :unspecified_design)),
			floating_qubit_model_id = floating_qubit_nominal.model_id,
			floating_qubit_capacitance_source_id = floating_qubit_nominal.capacitance_source_id,
			section_length_m = Float64(hb_settings.section_length_m),
			coupling_off_plan_id = plans.coupling_off.plan.id,
			physical_on_plan_id = plans.physical_on.plan.id,
			coupling_off_topology_key = off_model.provenance.topology_key,
			physical_on_topology_key = on_model.provenance.topology_key,
			mtl_mutual_capacitance_per_m_f = -Float64(case.mtl_c_matrix_f_per_m[1, 2]),
			mtl_mutual_inductance_per_m_h = Float64(case.mtl_l_matrix_h_per_m[1, 2]),
		),
		continuation = (
			node_order_sha256 = off_model.node_order_sha256,
			q_node_flux = copy(off_selections[1].node_flux_vector),
			r_node_flux = copy(off_selections[2].node_flux_vector),
			p_node_flux = copy(off_selections[3].node_flux_vector),
		),
	)
end
