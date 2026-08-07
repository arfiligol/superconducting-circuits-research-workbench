# D3 finite-order response is derived from the same compiled top-level
# CircuitPlan used by the equivalent model. This file owns only the D3-specific
# matched-port boundary extraction and neutral floating-qubit 7 -> 6 Routh
# reduction; it does not own topology construction, optimization, or rendering.

using LinearAlgebra
using SHA
using SuperconductingCircuitsCore

function _d3_exact_n_matrix_sha256(label, matrix)
    values = Matrix{Float64}(matrix)
    buffer = IOBuffer()
    write(
        buffer,
        "d3-float64-matrix-v1|$(String(label))|rows=$(size(values, 1))|cols=$(size(values, 2))",
    )
    for row in axes(values, 1), column in axes(values, 2)
        value = iszero(values[row, column]) ? 0.0 : values[row, column]
        write(buffer, UInt8('|'))
        write(buffer, bitstring(value))
    end
    return bytes2hex(SHA.sha256(take!(buffer)))
end

function _d3_exact_n_complex_matrix_sha256(label, matrix)
    values = Matrix{ComplexF64}(matrix)
    buffer = IOBuffer()
    write(
        buffer,
        "d3-complex128-matrix-v1|$(String(label))|rows=$(size(values, 1))|cols=$(size(values, 2))",
    )
    for row in axes(values, 1), column in axes(values, 2)
        value = values[row, column]
        real_value = iszero(real(value)) ? 0.0 : Float64(real(value))
        imag_value = iszero(imag(value)) ? 0.0 : Float64(imag(value))
        write(buffer, UInt8('|'))
        write(buffer, bitstring(real_value))
        write(buffer, UInt8(','))
        write(buffer, bitstring(imag_value))
    end
    return bytes2hex(SHA.sha256(take!(buffer)))
end

function _d3_exact_n_required_compiled_provenance(compiled, name)
    raw = get(compiled.provenance, name, nothing)
    isnothing(raw) && error(
        "D3 compiled provenance is missing $(name).",
    )
    value = strip(String(raw))
    !isempty(value) && lowercase(value) != "unknown" || error(
        "D3 compiled provenance $(name) must be concrete.",
    )
    return value
end

function _d3_exact_n_source_model_identity(model)
    hasproperty(model, :provenance) || error(
        "D3 physical model is missing provenance.",
    )
    names = (
        :circuit_plan_sha256,
        :capacitance_sha256,
        :inverse_inductance_sha256,
        :selector_sha256,
    )
    values = Base.map(names) do name
        hasproperty(model.provenance, name) || error(
            "D3 physical-model provenance is missing $(name).",
        )
        value = lowercase(strip(String(getproperty(model.provenance, name))))
        occursin(r"^[0-9a-f]{64}$", value) || error(
            "D3 physical-model provenance $(name) must be a SHA-256.",
        )
        value
    end
    return NamedTuple{names}(Tuple(values))
end

function _d3_exact_n_validate_model_identity(identity, label)
    names = (
        :circuit_plan_sha256,
        :capacitance_sha256,
        :inverse_inductance_sha256,
        :selector_sha256,
    )
    all(name -> hasproperty(identity, name), names) || error(
        "$(label) is missing a required model-identity field.",
    )
    values = Base.map(names) do name
        value = lowercase(strip(String(getproperty(identity, name))))
        occursin(r"^[0-9a-f]{64}$", value) || error(
            "$(label) $(name) must be a SHA-256.",
        )
        value
    end
    return NamedTuple{names}(Tuple(values))
end

function _d3_exact_n_require_handoff_source(model, cqed_handoff, label)
    hasproperty(cqed_handoff, :source_model_identity) || error(
        "$(label) is missing its source-model identity.",
    )
    cqed_handoff.source_model_identity ==
        _d3_exact_n_source_model_identity(model) || error(
        "$(label) was derived from a different physical model.",
    )
    return nothing
end

function _d3_exact_n_resolved_value(compiled, value_ref, label)
    value = if value_ref isa Real
        value_ref
    elseif value_ref isa Symbol && haskey(compiled.component_values, value_ref)
        compiled.component_values[value_ref]
    else
        error("$(label) has an unresolved compiled value reference $(repr(value_ref)).")
    end
    value isa Real || error("$(label) must resolve to one real scalar.")
    resolved = Float64(value)
    isfinite(resolved) && resolved > 0 || error(
        "$(label) must resolve to one finite positive scalar.",
    )
    return resolved
end

function _d3_exact_n_boundary(compiled)
    isempty(compiled.port_map) && error(
        "D3 Exact-N extraction requires the two declared matched ports.",
    )
    port_records = sort(
        collect(compiled.port_map);
        by=entry -> Int(entry.second.index),
    )
    length(port_records) == 2 || error(
        "D3 Exact-N v1 requires exactly two declared matched ports.",
    )
    [(Symbol(id), Int(info.index)) for (id, info) in port_records] ==
        [(:input_port, 1), (:output_port, 2)] || error(
        "D3 matched-port extraction requires input_port=P1 and output_port=P2.",
    )

    boundary_names = Set{String}()
    port_nodes = String[]
    reference_impedances = Float64[]
    port_ids = Symbol[]
    for (port_id, port_info) in port_records
        index = Int(port_info.index)
        port_name = "P$(index)"
        resistor_name = "R_port_$(index)"
        port_rows = [row for row in compiled.netlist if String(row[1]) == port_name]
        resistor_rows = [row for row in compiled.netlist if String(row[1]) == resistor_name]
        length(port_rows) == 1 || error(
            "D3 Exact-N requires exactly one compiled $(port_name) row.",
        )
        length(resistor_rows) == 1 || error(
            "D3 Exact-N requires exactly one compiled $(resistor_name) row.",
        )
        port_row = only(port_rows)
        resistor_row = only(resistor_rows)
        length(port_row) == 4 && length(resistor_row) == 4 || error(
            "D3 Exact-N matched-port boundary rows must use four-field netlist tuples.",
        )
        String(port_row[3]) == "0" && String(resistor_row[3]) == "0" || error(
            "D3 Exact-N matched ports and reference resistors must terminate at ground.",
        )
        Int(port_row[4]) == index || error(
            "D3 Exact-N compiled port number disagrees with port_map.",
        )
        String(port_row[2]) == String(resistor_row[2]) || error(
            "D3 Exact-N port $(index) and its reference resistor must share one node.",
        )
        push!(boundary_names, port_name, resistor_name)
        push!(port_nodes, String(port_row[2]))
        push!(
            reference_impedances,
            _d3_exact_n_resolved_value(
                compiled,
                resistor_row[4],
                "D3 Exact-N port $(index) reference impedance",
            ),
        )
        push!(port_ids, Symbol(port_id))
    end
    reference_impedances == [50.0, 50.0] || error(
        "D3 matched-port response is fixed to exactly 50 ohm at P1 and P2.",
    )

    conservative_rows = [
        row for row in compiled.netlist
        if !(String(row[1]) in boundary_names)
    ]
    length(conservative_rows) + length(boundary_names) == length(compiled.netlist) ||
        error("D3 Exact-N boundary filtering removed an unexpected number of rows.")
    conservative = JosephsonCompiledCircuit(
        netlist=conservative_rows,
        component_values=compiled.component_values,
        node_map=compiled.node_map,
        port_map=Dict{Symbol,Any}(),
        warnings=compiled.warnings,
        provenance=Dict{Symbol,Any}(
            :plan_id => get(compiled.provenance, :plan_id, "unknown"),
            :compiler => get(compiled.provenance, :compiler, :unknown),
            :topology_key => get(compiled.provenance, :topology_key, "unknown"),
            :d3_exact_n_source_plan_id =>
                get(compiled.provenance, :plan_id, "unknown"),
            :d3_exact_n_removed_boundary_rows => sort(collect(boundary_names)),
        ),
        metadata=Dict{Symbol,Any}(
            :d3_exact_n_boundary_view => true,
            :netlist_row_count => length(conservative_rows),
        ),
    )
    return (
        conservative=conservative,
        port_ids=port_ids,
        port_nodes=port_nodes,
        reference_impedance_ohm=reference_impedances,
        removed_rows=sort(collect(boundary_names)),
    )
end

function _d3_exact_n_node_name(compiled, endpoint, label)
    node_name = get(compiled.node_map, endpoint, nothing)
    isnothing(node_name) && error(
        "D3 Exact-N could not resolve the $(label) endpoint in the compiled Circuit Plan.",
    )
    String(node_name) == "0" && error("D3 Exact-N $(label) must not resolve to ground.")
    return String(node_name)
end

function _d3_exact_n_index(node_names, node_name, label)
    matches = findall(==(String(node_name)), node_names)
    length(matches) == 1 || error(
        "D3 Exact-N $(label) must resolve to exactly one extracted physical node.",
    )
    return only(matches)
end

function _d3_neutral_qubit_reduction(
    nodal_model,
    ql_node_name,
    qr_node_name,
    retained_node_names,
    retained_coordinate_order,
    port_nodes,
)
    node_names = nodal_model.node_names
    ordered_names = vcat(
        [String(ql_node_name), String(qr_node_name)],
        String.(collect(retained_node_names)),
    )
    length(unique(ordered_names)) == length(ordered_names) || error(
        "D3 neutral-qubit reduction node declarations must be unique.",
    )
    Set(node_names) == Set(ordered_names) || error(
        "D3 neutral-qubit reduction node declarations disagree with the extracted nodes.",
    )
    order = [
        _d3_exact_n_index(node_names, node_name, node_name)
        for node_name in ordered_names
    ]
    capacitance = nodal_model.capacitance[order, order]
    inverse_inductance = nodal_model.inverse_inductance[order, order]
    dimension = length(ordered_names)
    length(retained_coordinate_order) == dimension - 2 || error(
        "D3 retained coordinate labels disagree with the retained node count.",
    )

    # Excluding the mutual qL-qR branch, these are the total capacitances
    # incident on each island. Deriving them from the compiled C matrix keeps
    # the coordinate transform bound to the same Circuit Plan.
    a = capacitance[1, 1] + capacitance[1, 2]
    b = capacitance[2, 2] + capacitance[1, 2]
    s = a + b
    all(value -> isfinite(value) && value > 0, (a, b, s)) || error(
        "D3 Exact-N weighted qubit transform requires positive island loading A and B.",
    )

    # Phi_node = T * (Phi_Sigma, Phi_q, remaining physical node fluxes).
    transform = zeros(Float64, dimension, dimension)
    transform[1, 1] = 1.0
    transform[1, 2] = b / s
    transform[2, 1] = 1.0
    transform[2, 2] = -a / s
    for index in 3:dimension
        transform[index, index] = 1.0
    end
    local_capacitance = transpose(transform) * capacitance * transform
    local_inverse_inductance =
        transpose(transform) * inverse_inductance * transform

    common_q_cross_scale = max(
        norm(local_capacitance, Inf),
        floatmin(Float64),
    )
    abs(local_capacitance[1, 2]) <=
        512 * eps(Float64) * common_q_cross_scale || error(
        "D3 Exact-N weighted transform failed to eliminate the Sigma-q capacitance entry.",
    )
    stiffness_scale = max(norm(local_inverse_inductance, Inf), floatmin(Float64))
    norm(local_inverse_inductance[1, :], Inf) <=
        512 * eps(Float64) * stiffness_scale || error(
        "D3 Exact-N qubit common coordinate is not cyclic in the compiled Plan.",
    )

    retained = 2:dimension
    c_sigma_sigma = local_capacitance[1, 1]
    c_sigma_sigma > 0 || error(
        "D3 Exact-N common-coordinate capacitance must be positive.",
    )
    c_a_sigma = local_capacitance[retained, 1]
    reduced_capacitance =
        local_capacitance[retained, retained] -
        c_a_sigma * transpose(c_a_sigma) / c_sigma_sigma
    reduced_inverse_inductance =
        local_inverse_inductance[retained, retained]
    reduced_capacitance = Matrix(Symmetric(
        (reduced_capacitance + transpose(reduced_capacitance)) / 2,
    ))
    reduced_inverse_inductance = Matrix(Symmetric(
        (reduced_inverse_inductance + transpose(reduced_inverse_inductance)) / 2,
    ))
    isposdef(Symmetric(reduced_capacitance)) || error(
        "D3 Exact-N reduced capacitance matrix must be positive definite.",
    )
    stiffness_eigenvalues = eigvals(Symmetric(reduced_inverse_inductance))
    stiffness_tolerance =
        512 * length(stiffness_eigenvalues) * eps(Float64) *
        max(maximum(abs, stiffness_eigenvalues), floatmin(Float64))
    minimum(stiffness_eigenvalues) >= -stiffness_tolerance || error(
        "D3 Exact-N reduced inverse-inductance matrix must be passive semidefinite.",
    )

    full_selector = zeros(Float64, dimension, length(port_nodes))
    for (port_index, port_node) in enumerate(port_nodes)
        physical_index = _d3_exact_n_index(
            ordered_names,
            port_node,
            "port $(port_index)",
        )
        full_selector[physical_index, port_index] = 1.0
    end
    local_selector = transpose(transform) * full_selector
    norm(local_selector[1, :], Inf) == 0 || error(
        "D3 Exact-N matched ports must not drive the eliminated qubit common coordinate.",
    )
    reduced_selector = Matrix(local_selector[retained, :])

    return (
        coordinate_order=vcat([:q], Symbol.(collect(retained_coordinate_order))),
        physical_coordinate_order=vcat(
            [:qL, :qR],
            Symbol.(collect(retained_coordinate_order)),
        ),
        physical_node_order=ordered_names,
        compiled_node_order=node_names,
        compiled_to_physical_permutation=order,
        node_to_local_transform=transform,
        common_charge_reduction=(
            sector=:Q_Sigma_equals_zero,
            eliminated_coordinate=:Sigma,
            a_f=a,
            b_f=b,
            s_f=s,
            c_sigma_sigma_f=c_sigma_sigma,
            c_a_sigma_f=Vector{Float64}(c_a_sigma),
        ),
        capacitance=Matrix{Float64}(reduced_capacitance),
        inverse_inductance=Matrix{Float64}(reduced_inverse_inductance),
        selector=reduced_selector,
    )
end

function _d3_exact_n_neutral_qubit_reduction(
    nodal_model,
    physical_node_names,
    port_nodes,
)
    expected_names = collect(values(physical_node_names))
    length(unique(expected_names)) == 7 || error(
        "D3 Exact-N physical-node declarations must identify seven unique nodes.",
    )
    Set(nodal_model.node_names) == Set(expected_names) || error(
        "D3 Exact-N extracted node set disagrees with the seven declared physical nodes.",
    )
    return _d3_neutral_qubit_reduction(
        nodal_model,
        physical_node_names.qL,
        physical_node_names.qR,
        [
            physical_node_names.r,
            physical_node_names.p,
            physical_node_names.f1,
            physical_node_names.fc,
            physical_node_names.f2,
        ],
        [:r, :p, :f1, :fc, :f2],
        port_nodes,
    )
end

"""Return coordinate-, representation-, and response-explicit linear quantities.

The reduced anchored coordinates are the physical coordinates after the
topology transform and neutral common-charge reduction.  Coordinate-wise
impedance normalization changes their canonical representation but does not
rotate them into another coordinate basis.  The closed normal-mode result is
exported only as a frequency spectrum; no reusable eigenvector transformation
or third Hamiltonian basis is claimed.  Matched-open poles belong to the port
response and are sorted only for display.
"""
function d3_linear_quantity_views(
    model;
    cqed_handoff=d3_numerical_cqed_handoff(model),
    matrix_metrics=d3_stage2_matrix_metrics(
        model;
        cqed_handoff=cqed_handoff,
    ),
    matched_open_response=nothing,
)
    _d3_exact_n_require_handoff_source(
        model,
        cqed_handoff,
        "D3 linear basis quantity views",
    )
    anchored = matrix_metrics.anchored_oscillator_representation
    anchored.coordinate_basis ==
        :reduced_physically_anchored_flux_charge_coordinates || error(
        "D3 matrix metrics do not declare the reduced anchored coordinate basis.",
    )
    anchored.representation == :anchored_bare_coordinate_oscillator || error(
        "D3 matrix metrics do not declare the anchored oscillator representation.",
    )
    open_poles = isnothing(matched_open_response) ?
        matched_open_poles(
            model.capacitance,
            model.inverse_inductance,
            model.selector,
            model.reference_impedance_ohm,
    ) : matched_open_response
    open_frequency_hz = ComplexF64.(open_poles.frequencies_hz)
    isempty(open_frequency_hz) && error(
        "D3 matched-open response returned no positive-frequency poles.",
    )
    display_order = sortperm(
        eachindex(open_frequency_hz);
        by=index -> (real(open_frequency_hz[index]), imag(open_frequency_hz[index])),
    )
    sorted_open_frequency_hz = open_frequency_hz[display_order]
    sorted_open_linewidth_hz = Float64.(
        max.(-2 .* imag.(sorted_open_frequency_hz), 0.0),
    )
    passivity_roundoff_tolerance_hz =
        256.0 * (2 * length(model.coordinate_order)) * eps(Float64) *
        max(maximum(abs, sorted_open_frequency_hz), floatmin(Float64))
    return (
        contract_id="d3-linear-explicit-quantity-views.v2",
        coordinate_foundation=(
            raw_physical_node_flux=(
                basis=:raw_physical_node_flux_coordinates,
                coordinate_order=hasproperty(model, :physical_node_order) ?
                    copy(model.physical_node_order) : nothing,
            ),
            reduced_anchored_flux_charge=(
                basis=:reduced_physically_anchored_flux_charge_coordinates,
                coordinate_order=copy(model.coordinate_order),
                node_to_anchored_transform=
                    hasproperty(model, :node_to_local_transform) ?
                    Matrix{Float64}(model.node_to_local_transform) : nothing,
                common_charge_reduction=
                    hasproperty(model, :common_charge_reduction) ?
                    model.common_charge_reduction : nothing,
            ),
        ),
        anchored_oscillator_representation=anchored,
        fully_hybridized_closed_normal_mode_spectrum=(
            spectrum=:fully_hybridized_closed_normal_modes,
            coupling_state=:qrp_on,
            boundary=:closed,
            construction=:generalized_eigenproblem_K_u_equals_omega2_C_u,
            identity_assignment=:none,
            display_order=:ascending_frequency_only,
            frequencies_hz=copy(cqed_handoff.normal_modes.frequencies_hz),
            structural_free_mode_count=
                cqed_handoff.normal_modes.structural_free_mode_count,
        ),
        matched_open_port_poles=(
            response_class=:matched_open_port_response,
            coupling_state=:qrp_on,
            external_port_state=:matched_open,
            basis_claim=:none,
            identity_assignment=:none,
            display_order=:ascending_real_frequency_only,
            display_order_source_indices=display_order,
            frequencies_hz=sorted_open_frequency_hz,
            linewidths_hz=sorted_open_linewidth_hz,
            passivity_roundoff_tolerance_hz=passivity_roundoff_tolerance_hz,
        ),
    )
end

"""
    d3_exact_n_compiled_model(built)

Compile the canonical D3 Equivalent Circuit Plan, verify and remove only its
declared matched-port boundary rows, extract the seven-node conservative model
through JosephsonCircuits, and eliminate only the neutral floating-qubit common
charge coordinate. The finite feedline common coordinate is retained, so the
result has six second-order coordinates and five positive-frequency poles.
"""
function d3_exact_n_compiled_model(built)
    hasproperty(built, :plan) && hasproperty(built, :component) &&
        hasproperty(built, :feedline) || error(
        "D3 Exact-N extraction requires the result of the canonical Equivalent Circuit Plan builder.",
    )
    compiled = compile_to_josephson(built.plan)
    boundary = _d3_exact_n_boundary(compiled)
    nodal_model = extract_linear_nodal_model(boundary.conservative)
    physical_node_names = (
        qL=_d3_exact_n_node_name(
            compiled,
            built.component.qubit.island_1,
            "qL",
        ),
        qR=_d3_exact_n_node_name(
            compiled,
            built.component.qubit.island_2,
            "qR",
        ),
        r=_d3_exact_n_node_name(
            compiled,
            built.component.filter.readout_attachment,
            "readout",
        ),
        p=_d3_exact_n_node_name(
            compiled,
            built.component.filter.filter_resonator.node,
            "filter",
        ),
        f1=_d3_exact_n_node_name(compiled, built.feedline.input, "feedline f1"),
        fc=_d3_exact_n_node_name(compiled, built.feedline.center, "feedline fc"),
        f2=_d3_exact_n_node_name(compiled, built.feedline.output, "feedline f2"),
    )
    boundary.port_nodes == [physical_node_names.f1, physical_node_names.f2] ||
        error("D3 Exact-N P1/P2 nodes must equal the compiled f1/f2 reference planes.")
    reduced = _d3_exact_n_neutral_qubit_reduction(
        nodal_model,
        physical_node_names,
        boundary.port_nodes,
    )
    return merge(
        reduced,
        (
            reference_impedance_ohm=boundary.reference_impedance_ohm,
            port_ids=boundary.port_ids,
            port_nodes=boundary.port_nodes,
            removed_boundary_rows=boundary.removed_rows,
            compiled=compiled,
            conservative_nodal_model=nodal_model,
            provenance=(
                contract_id="d3-exact-n-compiled-port-response.v1",
                plan_id=_d3_exact_n_required_compiled_provenance(
                    compiled,
                    :plan_id,
                ),
                circuit_plan_sha256=bytes2hex(
                    SHA.sha256(schematic_export_json(built.plan)),
                ),
                topology_key=_d3_exact_n_required_compiled_provenance(
                    compiled,
                    :topology_key,
                ),
                conservative_source_sha256=nodal_model.source_sha256,
                node_order_sha256=nodal_model.node_order_sha256,
                nodal_capacitance_sha256=nodal_model.capacitance_sha256,
                nodal_inverse_inductance_sha256=
                    nodal_model.inverse_inductance_sha256,
                capacitance_sha256=_d3_exact_n_matrix_sha256(
                    "exact-n-capacitance-f",
                    reduced.capacitance,
                ),
                inverse_inductance_sha256=_d3_exact_n_matrix_sha256(
                    "exact-n-inverse-inductance-h^-1",
                    reduced.inverse_inductance,
                ),
                selector_sha256=_d3_exact_n_matrix_sha256(
                    "exact-n-port-selector",
                    reduced.selector,
                ),
                time_convention="exp(-i*omega*t)",
            ),
        ),
    )
end

"""
    d3_hybridized_compiled_model(built)

Compile a canonical D3 Hybridized Circuit Plan, retain every CPW/MTL and
feedline coordinate, and eliminate only the neutral floating-qubit common
charge coordinate. This supplies the unreduced physical model required for
direct-Hybridized Stage-2 response and pole evaluation.
"""
function d3_hybridized_compiled_model(built)
    hasproperty(built, :plan) && hasproperty(built, :component) &&
        hasproperty(built, :feedline) || error(
        "D3 Hybridized extraction requires the result of the canonical Hybridized Circuit Plan builder.",
    )
    compiled = compile_to_josephson(built.plan)
    boundary = _d3_exact_n_boundary(compiled)
    nodal_model = extract_linear_nodal_model(boundary.conservative)
    ql_node_name = _d3_exact_n_node_name(
        compiled,
        built.component.qubit.island_1,
        "qL",
    )
    qr_node_name = _d3_exact_n_node_name(
        compiled,
        built.component.qubit.island_2,
        "qR",
    )
    f1_node_name = _d3_exact_n_node_name(
        compiled,
        built.feedline.input,
        "feedline f1",
    )
    f2_node_name = _d3_exact_n_node_name(
        compiled,
        built.feedline.output,
        "feedline f2",
    )
    boundary.port_nodes == [f1_node_name, f2_node_name] || error(
        "D3 Hybridized P1/P2 nodes must equal the compiled f1/f2 reference planes.",
    )
    anchored_node_names = (
        r=_d3_exact_n_node_name(
            compiled,
            built.component.filter.readout_attachment,
            "readout anchor",
        ),
        p=_d3_exact_n_node_name(
            compiled,
            built.component.filter.filter_resonator.line.tail,
            "filter anchor",
        ),
        f1=f1_node_name,
        fc=_d3_exact_n_node_name(
            compiled,
            built.feedline.center,
            "feedline center",
        ),
        f2=f2_node_name,
    )
    length(unique(values(anchored_node_names))) == length(anchored_node_names) || error(
        "D3 Hybridized q/r/p/feedline anchors must resolve to distinct physical nodes.",
    )
    retained_node_names = [
        node_name for node_name in nodal_model.node_names
        if node_name != ql_node_name && node_name != qr_node_name
    ]
    reduced = _d3_neutral_qubit_reduction(
        nodal_model,
        ql_node_name,
        qr_node_name,
        retained_node_names,
        Symbol.(retained_node_names),
        boundary.port_nodes,
    )
    first(reduced.coordinate_order) == :q || error(
        "D3 Hybridized neutral-qubit reduction must retain q as its first coordinate.",
    )
    reduced_coordinate_index = Dict(
        coordinate => index
        for (index, coordinate) in enumerate(reduced.coordinate_order)
    )
    anchored_coordinate_indices = (
        q=1,
        r=get(
            reduced_coordinate_index,
            Symbol(anchored_node_names.r),
            nothing,
        ),
        p=get(
            reduced_coordinate_index,
            Symbol(anchored_node_names.p),
            nothing,
        ),
        f1=get(
            reduced_coordinate_index,
            Symbol(anchored_node_names.f1),
            nothing,
        ),
        fc=get(
            reduced_coordinate_index,
            Symbol(anchored_node_names.fc),
            nothing,
        ),
        f2=get(
            reduced_coordinate_index,
            Symbol(anchored_node_names.f2),
            nothing,
        ),
    )
    all(index -> index isa Int, values(anchored_coordinate_indices)) || error(
        "D3 Hybridized anchors are absent from the reduced physical coordinate order.",
    )
    length(unique(values(anchored_coordinate_indices))) ==
        length(anchored_coordinate_indices) || error(
        "D3 Hybridized anchored coordinate indices must be distinct.",
    )
    return merge(
        reduced,
        (
            anchored_coordinate_order=(:q, :r, :p, :f1, :fc, :f2),
            anchored_coordinate_indices=anchored_coordinate_indices,
            anchored_node_names=anchored_node_names,
            reference_impedance_ohm=boundary.reference_impedance_ohm,
            port_ids=boundary.port_ids,
            port_nodes=boundary.port_nodes,
            removed_boundary_rows=boundary.removed_rows,
            compiled=compiled,
            conservative_nodal_model=nodal_model,
            provenance=(
                contract_id="d3-hybridized-compiled-port-response.v1",
                plan_id=_d3_exact_n_required_compiled_provenance(
                    compiled,
                    :plan_id,
                ),
                circuit_plan_sha256=bytes2hex(
                    SHA.sha256(schematic_export_json(built.plan)),
                ),
                topology_key=_d3_exact_n_required_compiled_provenance(
                    compiled,
                    :topology_key,
                ),
                conservative_source_sha256=nodal_model.source_sha256,
                node_order_sha256=nodal_model.node_order_sha256,
                nodal_capacitance_sha256=nodal_model.capacitance_sha256,
                nodal_inverse_inductance_sha256=
                    nodal_model.inverse_inductance_sha256,
                capacitance_sha256=_d3_exact_n_matrix_sha256(
                    "hybridized-capacitance-f",
                    reduced.capacitance,
                ),
                inverse_inductance_sha256=_d3_exact_n_matrix_sha256(
                    "hybridized-inverse-inductance-h^-1",
                    reduced.inverse_inductance,
                ),
                selector_sha256=_d3_exact_n_matrix_sha256(
                    "hybridized-port-selector",
                    reduced.selector,
                ),
                time_convention="exp(-i*omega*t)",
            ),
        ),
    )
end

"""Carry one compiled physical model through the numerical cQED derivation.

The input `C` and `K` act on the reduced physically anchored flux-charge
coordinate order declared by `model.coordinate_order`.  Those coordinates are
the result of the topology-declared node transform and neutral common-charge
reduction; this function does not define another coordinate basis.  Instead it
applies the coordinate-wise canonical
normalization

`Z_i = sqrt((C^-1)[i,i] / K[i,i])`

and returns an *anchored bare-coordinate oscillator representation*.  Here
`bare` means subsystem-anchored coordinate identity, not coupling-off or an
isolated subsystem.  Its `h` and `Delta` blocks therefore share the same
coordinate order, transformation, and normalization.  The Exact doubled
matrix is a lossless rewriting of those two blocks, not a separate fit or a
normal-mode model.

Fully hybridized closed normal-mode frequencies are reported separately from
the generalized eigenproblem `K*u = omega^2*C*u`.  They must not be confused
with anchored diagonal entries or with matched-open poles.
"""
function d3_numerical_cqed_handoff(model)
    capacitance = Matrix{Float64}(model.capacitance)
    stiffness = Matrix{Float64}(model.inverse_inductance)
    source_model_identity = _d3_exact_n_source_model_identity(model)
    size(capacitance) == size(stiffness) || error(
        "D3 numerical cQED handoff requires equal-size C and K matrices.",
    )
    dimension = size(capacitance, 1)
    length(model.coordinate_order) == dimension || error(
        "D3 numerical cQED coordinate order disagrees with its matrices.",
    )
    isposdef(Symmetric(capacitance)) || error(
        "D3 numerical Legendre transform requires positive-definite C.",
    )
    stiffness_spectrum = eigvals(Symmetric(stiffness))
    stiffness_scale = max(maximum(abs, stiffness_spectrum), floatmin(Float64))
    stiffness_tolerance = 1024 * dimension * eps(Float64) * stiffness_scale
    minimum(stiffness_spectrum) >= -stiffness_tolerance || error(
        "D3 numerical cQED handoff requires passive positive-semidefinite K.",
    )
    all(LinearAlgebra.diag(stiffness) .> 0) || error(
        "D3 local oscillator normalization requires positive K diagonal entries.",
    )

    inverse_capacitance = capacitance \ Matrix{Float64}(I, dimension, dimension)
    impedance_ohm = sqrt.(
        LinearAlgebra.diag(inverse_capacitance) ./
        LinearAlgebra.diag(stiffness),
    )
    all(value -> isfinite(value) && value > 0, impedance_ohm) || error(
        "D3 local oscillator impedances must be finite and positive.",
    )
    sqrt_impedance = Diagonal(sqrt.(impedance_ohm))
    inverse_sqrt_impedance = Diagonal(1 ./ sqrt.(impedance_ohm))
    charge_block = Matrix{Float64}(
        inverse_sqrt_impedance * inverse_capacitance * inverse_sqrt_impedance,
    )
    flux_block = Matrix{Float64}(
        sqrt_impedance * stiffness * sqrt_impedance,
    )
    number_conserving = Matrix{Float64}(Symmetric(
        (charge_block + flux_block) / 2,
    ))
    pairing = Matrix{Float64}(Symmetric(
        (-charge_block + flux_block) / 2,
    ))
    doubled = [
        number_conserving pairing
        -pairing -number_conserving
    ]

    selector = Matrix{Float64}(model.selector)
    size(selector, 1) == dimension && size(selector, 2) == 2 || error(
        "D3 numerical cQED handoff requires a two-port selector with one row per coordinate.",
    )
    reference_impedance_ohm = Float64.(model.reference_impedance_ohm)
    length(reference_impedance_ohm) == 2 &&
        all(value -> isfinite(value) && value > 0, reference_impedance_ohm) ||
        error("D3 numerical cQED handoff requires two positive reference impedances.")
    square_root_y0 = Diagonal(1 ./ sqrt.(reference_impedance_ohm))
    conductance =
        selector * Diagonal(1 ./ reference_impedance_ohm) * transpose(selector)
    identity_dimension = Matrix{Float64}(I, dimension, dimension)
    zero_dimension = zeros(Float64, dimension, dimension)
    closed_flux_velocity_generator = [
        zero_dimension identity_dimension
        -(capacitance \ stiffness) zero_dimension
    ]
    open_flux_velocity_generator = [
        zero_dimension identity_dimension
        -(capacitance \ stiffness) -(capacitance \ conductance)
    ]

    flux_scale = Diagonal(sqrt.(impedance_ohm ./ 2))
    charge_scale = Diagonal(1 ./ sqrt.(2 .* impedance_ohm))
    doubled_to_flux_velocity = [
        flux_scale flux_scale
        -im .* (inverse_capacitance * charge_scale) im .* (inverse_capacitance * charge_scale)
    ]
    flux_velocity_to_doubled =
        doubled_to_flux_velocity \ Matrix{ComplexF64}(I, 2 * dimension, 2 * dimension)
    closed_doubled_generator =
        flux_velocity_to_doubled *
        closed_flux_velocity_generator *
        doubled_to_flux_velocity
    open_doubled_generator =
        flux_velocity_to_doubled *
        open_flux_velocity_generator *
        doubled_to_flux_velocity
    transformed_doubled = im .* closed_doubled_generator
    doubled_transform_residual = maximum(
        abs,
        transformed_doubled - ComplexF64.(doubled),
    )
    doubled_transform_scale = max(maximum(abs, doubled), floatmin(Float64))
    doubled_transform_residual <=
        8192 * dimension * eps(Float64) * doubled_transform_scale || error(
        "D3 flux/velocity to exact-doubled transform does not reproduce the conservative doubled operator.",
    )

    port_count = size(selector, 2)
    flux_velocity_drive = [
        zeros(Float64, dimension, port_count)
        2 .* inverse_capacitance * selector * square_root_y0
    ]
    flux_velocity_observation = [
        zeros(Float64, port_count, dimension) square_root_y0 * transpose(selector)
    ]
    direct_scattering = -Matrix{ComplexF64}(I, port_count, port_count)
    doubled_drive = flux_velocity_to_doubled * flux_velocity_drive
    doubled_observation =
        flux_velocity_observation * doubled_to_flux_velocity
    reconstructed_inverse_capacitance =
        sqrt_impedance * (number_conserving - pairing) * sqrt_impedance
    reconstructed_stiffness =
        inverse_sqrt_impedance * (number_conserving + pairing) * inverse_sqrt_impedance
    inverse_capacitance_residual = maximum(
        abs,
        reconstructed_inverse_capacitance - inverse_capacitance,
    )
    stiffness_residual = maximum(abs, reconstructed_stiffness - stiffness)

    generalized_squared = eigvals(Symmetric(stiffness), Symmetric(capacitance))
    generalized_scale = max(maximum(abs, generalized_squared), floatmin(Float64))
    generalized_tolerance = 4096 * dimension * eps(Float64) * generalized_scale
    minimum(generalized_squared) >= -generalized_tolerance || error(
        "D3 numerical exact C/K spectrum contains an active mode.",
    )
    exact_flux_hz = sort(
        sqrt.(
            Float64[
                value for value in generalized_squared
                if value > generalized_tolerance
            ],
        ) ./ (2π),
    )
    structural_free_mode_count = count(
        value -> abs(value) <= stiffness_tolerance,
        stiffness_spectrum,
    )
    structural_free_mode_count == dimension - length(exact_flux_hz) || error(
        "D3 structural free-mode count disagrees with the exact oscillatory spectrum.",
    )

    doubled_values = eigvals(doubled)
    doubled_scale = max(maximum(abs, doubled_values), floatmin(Float64))
    doubled_tolerance = 4096 * 2 * dimension * eps(Float64) * doubled_scale
    doubled_free_indices = first(
        sortperm(abs.(doubled_values)),
        2 * structural_free_mode_count,
    )
    doubled_free_tolerance =
        64 * sqrt(eps(Float64)) * doubled_scale
    all(
        abs(doubled_values[index]) <= doubled_free_tolerance
        for index in doubled_free_indices
    ) || error(
        "D3 exact doubled structural-free Jordan pair is not numerically close to zero.",
    )
    doubled_oscillatory_indices = [
        index for index in eachindex(doubled_values)
        if !(index in doubled_free_indices)
    ]
    maximum(
        abs,
        imag.(doubled_values[doubled_oscillatory_indices]),
    ) <= doubled_tolerance || error(
        "D3 exact doubled oscillatory spectrum is not real within numerical tolerance.",
    )
    doubled_positive_hz = sort(
        Float64[
            real(doubled_values[index]) / (2π)
            for index in doubled_oscillatory_indices
            if real(doubled_values[index]) > 0
        ],
    )
    length(doubled_positive_hz) == length(exact_flux_hz) || error(
        "D3 exact doubled and second-order flux models disagree on the positive oscillatory mode count.",
    )
    exact_doubled_hz = doubled_positive_hz
    doubled_free_eigenvalues_hz =
        ComplexF64.(doubled_values[doubled_free_indices] ./ (2π))

    exact_doubled_residual_hz = exact_doubled_hz .- exact_flux_hz
    matrix_hash = _d3_exact_n_matrix_sha256
    return (
        contract_id="d3-numerical-lagrangian-to-cqed-handoff.v3",
        source_model_identity=source_model_identity,
        coordinate_order=copy(model.coordinate_order),
        lagrangian=(
            form=:one_half_phidot_C_phidot_minus_one_half_phi_K_phi,
            capacitance_f=capacitance,
            inverse_inductance_h_inv=stiffness,
        ),
        legendre=(
            canonical_charge_relation=:Q_equals_C_phidot,
            velocity_relation=:phidot_equals_C_inverse_Q,
            inverse_capacitance_f_inv=inverse_capacitance,
        ),
        hamiltonian=(
            form=:one_half_Q_C_inverse_Q_plus_one_half_phi_K_phi,
            inverse_capacitance_f_inv=inverse_capacitance,
            inverse_inductance_h_inv=stiffness,
        ),
        oscillator_normalization=(
            coordinate_basis=
                :reduced_physically_anchored_flux_charge_coordinates,
            representation=:anchored_bare_coordinate_oscillator,
            coordinate_order=copy(model.coordinate_order),
            coordinate_rotation=:none,
            normalization=
                :Z_i_equals_sqrt_C_inverse_ii_over_K_ii,
            impedance_ohm=impedance_ohm,
            charge_block_rad_s=charge_block,
            flux_block_rad_s=flux_block,
        ),
        anchored_bare_hamiltonian=(
            coordinate_basis=
                :reduced_physically_anchored_flux_charge_coordinates,
            representation=:anchored_bare_coordinate_oscillator,
            coordinate_order=copy(model.coordinate_order),
            coordinate_rotation=:none,
            normalization=
                :Z_i_equals_sqrt_C_inverse_ii_over_K_ii,
            number_conserving_matrix_rad_s=number_conserving,
            pairing_matrix_rad_s=pairing,
        ),
        exact=(
            representation=:exact_doubled_anchored_oscillator,
            coordinate_basis=
                :reduced_physically_anchored_flux_charge_coordinates,
            doubled_matrix_rad_s=doubled,
            doubled_frequencies_hz=exact_doubled_hz,
            doubled_free_eigenvalues_hz=doubled_free_eigenvalues_hz,
            structural_free_mode_count=structural_free_mode_count,
        ),
        normal_modes=(
            spectrum=:fully_hybridized_closed_normal_modes,
            construction=:generalized_eigenproblem_K_u_equals_omega2_C_u,
            identity_assignment=:none,
            display_order=:ascending_frequency_only,
            frequencies_hz=exact_flux_hz,
            structural_free_mode_count=structural_free_mode_count,
        ),
        port_response=(
            representation=:transformed_flux_velocity_state_space,
            time_convention=:exp_minus_i_omega_t,
            selector=selector,
            reference_impedance_ohm=reference_impedance_ohm,
            conductance_s=conductance,
            direct_scattering=direct_scattering,
            exact=(
                state_order=(
                    flux_velocity=vcat(
                        Symbol.("Phi_" .* String.(model.coordinate_order)),
                        Symbol.("Phidot_" .* String.(model.coordinate_order)),
                    ),
                    doubled=vcat(
                        Symbol.("a_" .* String.(model.coordinate_order)),
                        Symbol.("adag_" .* String.(model.coordinate_order)),
                    ),
                ),
                doubled_to_flux_velocity=doubled_to_flux_velocity,
                flux_velocity_to_doubled=flux_velocity_to_doubled,
                closed_generator_per_s=closed_doubled_generator,
                open_generator_per_s=open_doubled_generator,
                drive_per_s=doubled_drive,
                observation=doubled_observation,
            ),
        ),
        closure=(
            inverse_capacitance_max_abs_residual=inverse_capacitance_residual,
            inverse_inductance_max_abs_residual=stiffness_residual,
            doubled_transform_max_abs_residual_rad_s=
                doubled_transform_residual,
            exact_doubled_minus_flux_hz=exact_doubled_residual_hz,
            max_abs_exact_doubled_residual_hz=
                isempty(exact_doubled_residual_hz) ? 0.0 :
                maximum(abs, exact_doubled_residual_hz),
        ),
        hashes=(
            capacitance_sha256=matrix_hash("cqed-capacitance-f", capacitance),
            inverse_inductance_sha256=matrix_hash(
                "cqed-inverse-inductance-h^-1",
                stiffness,
            ),
            inverse_capacitance_sha256=matrix_hash(
                "cqed-inverse-capacitance-f^-1",
                inverse_capacitance,
            ),
            number_conserving_sha256=matrix_hash(
                "cqed-number-conserving-rad-s",
                number_conserving,
            ),
            pairing_sha256=matrix_hash("cqed-pairing-rad-s", pairing),
            doubled_sha256=matrix_hash("cqed-doubled-rad-s", doubled),
            port_selector_sha256=matrix_hash(
                "cqed-port-selector",
                selector,
            ),
            port_conductance_sha256=matrix_hash(
                "cqed-port-conductance-s",
                conductance,
            ),
            doubled_to_flux_velocity_sha256=
                _d3_exact_n_complex_matrix_sha256(
                    "cqed-doubled-to-flux-velocity",
                    doubled_to_flux_velocity,
                ),
            exact_open_generator_sha256=
                _d3_exact_n_complex_matrix_sha256(
                    "cqed-exact-open-generator-s^-1",
                    open_doubled_generator,
                ),
            exact_drive_sha256=_d3_exact_n_complex_matrix_sha256(
                "cqed-exact-port-drive",
                doubled_drive,
            ),
            exact_observation_sha256=
                _d3_exact_n_complex_matrix_sha256(
                    "cqed-exact-port-observation",
                    doubled_observation,
                ),
        ),
    )
end

"""Extract Stage-2 anchored-bare oscillator quantities from `h` and `Delta`.

The reported `h` and `Delta` entries use the physically anchored
bare-coordinate oscillator basis and its declared diagonal-impedance
normalization.  Because this normalization scales each reduced anchored
coordinate independently and performs no rotation, `h_qq`, `h_rr`, and
`h_pp` are the anchored-bare coordinate-oscillator frequencies.  `h_rp` is
the number-conserving exchange coefficient in the same representation;
`Delta_rp` is reported separately for the exact non-RWA model.
"""
function d3_stage2_matrix_metrics(
    model;
    cqed_handoff=d3_numerical_cqed_handoff(model),
)
    _d3_exact_n_require_handoff_source(
        model,
        cqed_handoff,
        "D3 Stage-2 matrix-metrics cQED handoff",
    )
    cqed_handoff.coordinate_order == model.coordinate_order || error(
        "D3 Stage-2 matrix-metrics cQED handoff coordinate order disagrees with its model.",
    )
    hasproperty(model, :anchored_coordinate_indices) || error(
        "D3 direct-Hybridized matrix extraction requires explicit q/r/p anchor indices.",
    )
    anchors = model.anchored_coordinate_indices
    all(name -> hasproperty(anchors, name), (:q, :r, :p)) || error(
        "D3 direct-Hybridized matrix extraction requires q/r/p anchors.",
    )
    h = cqed_handoff.anchored_bare_hamiltonian.number_conserving_matrix_rad_s
    pairing = cqed_handoff.anchored_bare_hamiltonian.pairing_matrix_rad_s
    q = Int(anchors.q)
    r = Int(anchors.r)
    p = Int(anchors.p)
    provenance = model.provenance
    return (
        stage_id=:stage2_direct_hybridized,
        model_family=:hybridized_distributed_lumped,
        circuit_plan_sha256=provenance.circuit_plan_sha256,
        capacitance_sha256=provenance.capacitance_sha256,
        inverse_inductance_sha256=provenance.inverse_inductance_sha256,
        selector_sha256=provenance.selector_sha256,
        anchored_oscillator_representation=(
            coupling_state=:qrp_on,
            boundary=:closed_conservative_block,
            coordinate_basis=
                :reduced_physically_anchored_flux_charge_coordinates,
            representation=:anchored_bare_coordinate_oscillator,
                coordinate_order=copy(model.coordinate_order),
                anchored_coordinate_indices=(q=q, r=r, p=p),
            coordinate_rotation=:none,
            normalization=
                :Z_i_equals_sqrt_C_inverse_ii_over_K_ii,
            impedance_ohm=(
                q=cqed_handoff.oscillator_normalization.impedance_ohm[q],
                r=cqed_handoff.oscillator_normalization.impedance_ohm[r],
                p=cqed_handoff.oscillator_normalization.impedance_ohm[p],
            ),
            h_diagonal_frequency_hz=(
                q=h[q, q] / (2π),
                r=h[r, r] / (2π),
                p=h[p, p] / (2π),
            ),
            h_number_conserving_coupling_hz=(
                qr=h[q, r] / (2π),
                qp=h[q, p] / (2π),
                rp=h[r, p] / (2π),
            ),
            pairing_diagonal_hz=(
                q=pairing[q, q] / (2π),
                r=pairing[r, r] / (2π),
                p=pairing[p, p] / (2π),
            ),
            pairing_coupling_hz=(
                qr=pairing[q, r] / (2π),
                qp=pairing[q, p] / (2π),
                rp=pairing[r, p] / (2π),
            ),
        ),
        fq_anchored_bare_qrp_on_h_diagonal_hz=h[q, q] / (2π),
        fr_anchored_bare_qrp_on_h_diagonal_hz=h[r, r] / (2π),
        fp_anchored_bare_qrp_on_h_diagonal_hz=h[p, p] / (2π),
        J_rp_anchored_bare_qrp_on_h_number_conserving_hz=
            abs(h[r, p]) / (2π),
        Delta_rp_anchored_bare_qrp_on_pairing_report_only_hz=
            pairing[r, p] / (2π),
        fq_circuit_h_qq_pre_downfold_report_only_hz=h[q, q] / (2π),
        fr_circuit_h_rr_pre_downfold_report_only_hz=h[r, r] / (2π),
        fp_circuit_h_pp_pre_downfold_report_only_hz=h[p, p] / (2π),
        J_circuit_h_rp_pre_downfold_report_only_hz=abs(h[r, p]) / (2π),
        operand_authority=
            :coupling_on_anchored_bare_coordinate_oscillator_representation,
        coordinate_order=copy(model.coordinate_order),
        anchored_coordinate_indices=(q=q, r=r, p=p),
        number_conserving_sha256=
            cqed_handoff.hashes.number_conserving_sha256,
        pairing_sha256=cqed_handoff.hashes.pairing_sha256,
        exact_doubled_sha256=cqed_handoff.hashes.doubled_sha256,
    )
end

"""
    d3_stage2_quantity_views(
        model,
        cqed_handoff,
        matrix_metrics,
        unordered_rp_assignment,
    )

Return the explicitly separated D3 quantity views used by Human review:

1. raw physical node fluxes and the reduced anchored flux-charge coordinates;
2. the impedance-normalized oscillator representation of those same anchored
   coordinates, including `Z`, `h`, and `Delta`;
3. fully hybridized closed normal-mode frequencies;
4. matched-open response poles.  The poles are not another Hamiltonian basis;
   only q is individually identified, while the two resonator poles remain an
   unordered RP-subspace set.
"""
function d3_stage2_quantity_views(
    model,
    cqed_handoff,
    matrix_metrics,
    unordered_rp_assignment,
)
    _d3_exact_n_require_handoff_source(
        model,
        cqed_handoff,
        "D3 Stage-2 basis quantity views",
    )
    linear_views = d3_linear_quantity_views(
        model;
        cqed_handoff=cqed_handoff,
        matrix_metrics=matrix_metrics,
        matched_open_response=unordered_rp_assignment.positive_poles,
    )
    assigned_indices = unordered_rp_assignment.assignment
    assigned_poles = unordered_rp_assignment.positive_poles
    assigned_record(index) = begin
        display_index = findfirst(
            ==(index),
            linear_views.matched_open_port_poles.display_order_source_indices,
        )
        isnothing(display_index) && error(
            "D3 matched-open identity assignment is absent from the reported pole order.",
        )
        (
            display_index=display_index,
            frequency_hz=assigned_poles.frequencies_hz[index],
            linewidth_hz=assigned_poles.linewidths_hz[index],
        )
    end
    identity_assigned = (
        q_report_only=assigned_record(assigned_indices.q_pole_index),
        unordered_rp_subspace=Tuple(
            assigned_record(index)
            for index in assigned_indices.unordered_rp_pole_indices
        ),
    )

    return (
        contract_id="d3-stage2-explicit-quantity-views.v3",
        coordinate_foundation=linear_views.coordinate_foundation,
        anchored_oscillator_representation=
            linear_views.anchored_oscillator_representation,
        fully_hybridized_closed_normal_mode_spectrum=
            linear_views.fully_hybridized_closed_normal_mode_spectrum,
        matched_open_port_poles=merge(
            linear_views.matched_open_port_poles,
            (
                identity_assignment=
                    unordered_rp_assignment.provenance.identity_rule,
                q_and_unordered_rp_subspace_assignment=identity_assigned,
            ),
        ),
    )
end

const D3_COMPLETE_COMPLEMENT_RP_GATE_FIELDS = (
    :maximum_elimination_condition_number,
    :maximum_relative_elimination_solve_residual,
    :maximum_relative_reciprocity_error,
    :maximum_relative_passivity_violation,
    :maximum_relative_root_residual,
    :maximum_root_growth_rate_hz,
    :minimum_normalized_residue_slope,
    :maximum_relative_coupling_spread,
    :maximum_relative_determinant_closure_error,
)

function _d3_complete_complement_rp_gate_policy(raw)
    Tuple(propertynames(raw)) == D3_COMPLETE_COMPLEMENT_RP_GATE_FIELDS ||
        error(
            "D3 complete-complement RP gate policy fields must be exactly $(collect(D3_COMPLETE_COMPLEMENT_RP_GATE_FIELDS)).",
        )
    values = Base.map(D3_COMPLETE_COMPLEMENT_RP_GATE_FIELDS) do name
        value = getproperty(raw, name)
        value isa Real || error(
            "D3 complete-complement RP gate $(name) must be real.",
        )
        parsed = Float64(value)
        isfinite(parsed) || error(
            "D3 complete-complement RP gate $(name) must be finite.",
        )
        parsed
    end
    policy = NamedTuple{
        D3_COMPLETE_COMPLEMENT_RP_GATE_FIELDS,
    }(Tuple(values))
    policy.maximum_elimination_condition_number >= 1 || error(
        "D3 complete-complement RP maximum elimination condition number must be at least one.",
    )
    for name in (
        :maximum_relative_elimination_solve_residual,
        :maximum_relative_reciprocity_error,
        :maximum_relative_passivity_violation,
        :maximum_relative_root_residual,
        :maximum_root_growth_rate_hz,
        :maximum_relative_coupling_spread,
        :maximum_relative_determinant_closure_error,
    )
        getproperty(policy, name) >= 0 || error(
            "D3 complete-complement RP gate $(name) must be nonnegative.",
        )
    end
    policy.minimum_normalized_residue_slope > 0 || error(
        "D3 complete-complement RP minimum normalized residue slope must be positive.",
    )
    return policy
end

function _d3_rp_relative_error(numerator, denominator)
    scale = max(Float64(denominator), floatmin(Float64))
    return Float64(numerator) / scale
end

function _d3_rp_reciprocity_error(matrix)
    return _d3_rp_relative_error(
        opnorm(matrix - transpose(matrix), Inf),
        opnorm(matrix, Inf),
    )
end

function _d3_complete_complement_rp_context(model, raw_gate_policy)
    gate_policy =
        _d3_complete_complement_rp_gate_policy(raw_gate_policy)
    coordinate_order = Symbol.(collect(model.coordinate_order))
    hasproperty(model, :anchored_coordinate_indices) || error(
        "D3 complete-complement RP extraction requires explicit q/r/p/feedline anchor indices.",
    )
    anchors = model.anchored_coordinate_indices
    anchor_names = (:q, :r, :p, :f1, :fc, :f2)
    all(name -> hasproperty(anchors, name), anchor_names) || error(
        "D3 complete-complement RP extraction requires q/r/p/f1/fc/f2 anchors.",
    )
    anchor_indices = Int[getproperty(anchors, name) for name in anchor_names]
    dimension = length(coordinate_order)
    all(index -> 1 <= index <= dimension, anchor_indices) &&
        length(unique(anchor_indices)) == length(anchor_indices) || error(
        "D3 complete-complement RP anchor indices are invalid or non-unique.",
    )
    capacitance = Matrix{Float64}(model.capacitance)
    stiffness = Matrix{Float64}(model.inverse_inductance)
    size(capacitance) == (dimension, dimension) &&
        size(stiffness) == (dimension, dimension) || error(
        "D3 complete-complement RP C/K shapes disagree with the coordinate order.",
    )
    selector = Matrix{Float64}(model.selector)
    size(selector) == (dimension, 2) || error(
        "D3 complete-complement RP extraction requires an N x 2 matched-port selector.",
    )
    reference_impedance_ohm = Float64.(collect(model.reference_impedance_ohm))
    length(reference_impedance_ohm) == 2 &&
        all(value -> isfinite(value) && value > 0, reference_impedance_ohm) ||
        error(
            "D3 complete-complement RP extraction requires two finite positive reference impedances.",
        )
    all(isfinite, capacitance) && all(isfinite, stiffness) &&
        all(isfinite, selector) || error(
        "D3 complete-complement RP matrices must contain only finite values.",
    )
    capacitance_reciprocity =
        _d3_rp_reciprocity_error(capacitance)
    stiffness_reciprocity =
        _d3_rp_reciprocity_error(stiffness)
    max(capacitance_reciprocity, stiffness_reciprocity) <=
        gate_policy.maximum_relative_reciprocity_error || error(
        "D3 complete-complement RP C/K reciprocity exceeds the caller-owned gate.",
    )
    capacitance = Matrix(Symmetric((capacitance + transpose(capacitance)) / 2))
    stiffness = Matrix(Symmetric((stiffness + transpose(stiffness)) / 2))
    isposdef(Symmetric(capacitance)) || error(
        "D3 complete-complement RP capacitance must be positive definite.",
    )
    conductance =
        selector *
        Diagonal(1 ./ reference_impedance_ohm) *
        transpose(selector)
    conductance_reciprocity =
        _d3_rp_reciprocity_error(conductance)
    conductance_reciprocity <=
        gate_policy.maximum_relative_reciprocity_error || error(
        "D3 complete-complement RP port conductance reciprocity exceeds the caller-owned gate.",
    )
    stiffness_eigenvalues = eigvals(Symmetric(stiffness))
    conductance_eigenvalues = eigvals(Symmetric(conductance))
    stiffness_scale =
        max(maximum(abs, stiffness_eigenvalues), floatmin(Float64))
    conductance_scale =
        max(maximum(abs, conductance_eigenvalues), floatmin(Float64))
    stiffness_violation =
        max(-minimum(stiffness_eigenvalues), 0.0) / stiffness_scale
    conductance_violation =
        max(-minimum(conductance_eigenvalues), 0.0) / conductance_scale
    max(stiffness_violation, conductance_violation) <=
        gate_policy.maximum_relative_passivity_violation || error(
        "D3 complete-complement RP K/G passivity exceeds the caller-owned gate.",
    )
    retained_indices = [Int(anchors.r), Int(anchors.p)]
    eliminated_indices = [
        index for index in eachindex(coordinate_order)
        if !(index in retained_indices)
    ]
    return (
        capacitance=capacitance,
        stiffness=stiffness,
        conductance=Matrix{Float64}(conductance),
        selector=selector,
        reference_impedance_ohm=reference_impedance_ohm,
        coordinate_order=coordinate_order,
        anchored_coordinate_indices=anchors,
        retained_indices=retained_indices,
        eliminated_indices=eliminated_indices,
        gate_policy=gate_policy,
        validation=(
            capacitance_reciprocity_error=capacitance_reciprocity,
            stiffness_reciprocity_error=stiffness_reciprocity,
            conductance_reciprocity_error=conductance_reciprocity,
            stiffness_relative_passivity_violation=stiffness_violation,
            conductance_relative_passivity_violation=conductance_violation,
        ),
    )
end

function _d3_complete_complement_rp_operator(context, angular_frequency_rad_s)
    angular_frequency = ComplexF64(angular_frequency_rad_s)
    isfinite(real(angular_frequency)) && isfinite(imag(angular_frequency)) ||
        error(
            "D3 complete-complement RP angular frequency must be finite.",
        )
    real(angular_frequency) > 0 || error(
        "D3 complete-complement RP angular frequency must have positive real part.",
    )
    capacitance = context.capacitance
    stiffness = context.stiffness
    conductance = context.conductance
    retained = context.retained_indices
    eliminated = context.eliminated_indices
    dynamic =
        ComplexF64.(stiffness) -
        angular_frequency^2 .* capacitance -
        im * angular_frequency .* conductance
    derivative =
        -2 * angular_frequency .* capacitance -
        im .* conductance
    d_rr = dynamic[retained, retained]
    d_re = dynamic[retained, eliminated]
    d_er = dynamic[eliminated, retained]
    d_ee = dynamic[eliminated, eliminated]
    derivative_rr = derivative[retained, retained]
    derivative_re = derivative[retained, eliminated]
    derivative_er = derivative[eliminated, retained]
    derivative_ee = derivative[eliminated, eliminated]

    elimination_condition_number = cond(d_ee)
    isfinite(elimination_condition_number) &&
        elimination_condition_number <=
            context.gate_policy.maximum_elimination_condition_number || error(
        "D3 complete-complement RP eliminated block is singular or exceeds the caller-owned condition-number gate.",
    )
    eliminated_response = try
        d_ee \ d_er
    catch exception
        error(
            "D3 complete-complement RP eliminated-block solve failed: $(sprint(showerror, exception))",
        )
    end
    all(
        value -> isfinite(real(value)) && isfinite(imag(value)),
        eliminated_response,
    ) || error(
        "D3 complete-complement RP eliminated-block solve produced non-finite values.",
    )
    solve_residual = d_ee * eliminated_response - d_er
    relative_solve_residual = _d3_rp_relative_error(
        opnorm(solve_residual, Inf),
        opnorm(d_ee, Inf) * opnorm(eliminated_response, Inf) +
        opnorm(d_er, Inf),
    )
    relative_solve_residual <=
        context.gate_policy.maximum_relative_elimination_solve_residual ||
        error(
            "D3 complete-complement RP eliminated-block solve residual exceeds the caller-owned gate.",
        )
    eliminated_response_derivative = try
        d_ee \ (
            derivative_er -
            derivative_ee * eliminated_response
        )
    catch exception
        error(
            "D3 complete-complement RP derivative solve failed: $(sprint(showerror, exception))",
        )
    end
    all(
        value -> isfinite(real(value)) && isfinite(imag(value)),
        eliminated_response_derivative,
    ) || error(
        "D3 complete-complement RP derivative solve produced non-finite values.",
    )
    derivative_solve_residual =
        d_ee * eliminated_response_derivative -
        (derivative_er - derivative_ee * eliminated_response)
    relative_derivative_solve_residual = _d3_rp_relative_error(
        opnorm(derivative_solve_residual, Inf),
        opnorm(d_ee, Inf) * opnorm(eliminated_response_derivative, Inf) +
        opnorm(derivative_er - derivative_ee * eliminated_response, Inf),
    )
    relative_derivative_solve_residual <=
        context.gate_policy.maximum_relative_elimination_solve_residual ||
        error(
            "D3 complete-complement RP derivative solve residual exceeds the caller-owned gate.",
        )

    effective =
        d_rr - d_re * eliminated_response
    effective_derivative =
        derivative_rr -
        derivative_re * eliminated_response -
        d_re * eliminated_response_derivative
    reciprocity_error =
        _d3_rp_reciprocity_error(effective)
    reciprocity_error <=
        context.gate_policy.maximum_relative_reciprocity_error || error(
        "D3 complete-complement RP effective-operator reciprocity exceeds the caller-owned gate.",
    )
    eliminated_term = d_re * eliminated_response
    diagonal_balance_scale = [
        max(
            abs(d_rr[index, index]) +
            abs(eliminated_term[index, index]),
            floatmin(Float64),
        )
        for index in 1:2
    ]
    return (
        angular_frequency_rad_s=angular_frequency,
        dynamic_stiffness=dynamic,
        dynamic_stiffness_derivative=derivative,
        effective_dynamic_stiffness=Matrix{ComplexF64}(effective),
        effective_dynamic_stiffness_derivative=
            Matrix{ComplexF64}(effective_derivative),
        eliminated_response=Matrix{ComplexF64}(eliminated_response),
        eliminated_response_derivative=
            Matrix{ComplexF64}(eliminated_response_derivative),
        diagonal_balance_scale=diagonal_balance_scale,
        diagnostics=(
            elimination_condition_number=elimination_condition_number,
            relative_elimination_solve_residual=relative_solve_residual,
            relative_derivative_solve_residual=
                relative_derivative_solve_residual,
            effective_reciprocity_error=reciprocity_error,
        ),
    )
end

function _d3_complete_complement_rp_diagonal_root(
    model,
    context,
    coordinate,
    raw_frequency_band_hz,
)
    coordinate in (:r, :p) || error(
        "D3 complete-complement RP diagonal root supports only r or p.",
    )
    band = _d3_loaded_bare_root_band(raw_frequency_band_hz)
    coordinate_index = Dict(
        name => index
        for (index, name) in enumerate(context.coordinate_order)
    )
    indices = [
        coordinate_index[coordinate],
        context.eliminated_indices...,
    ]
    poles = matched_open_poles(
        context.capacitance[indices, indices],
        context.stiffness[indices, indices],
        context.selector[indices, :],
        context.reference_impedance_ohm,
    )
    candidates = [
        index for index in eachindex(poles.frequencies_hz)
        if band[1] <= real(poles.frequencies_hz[index]) <= band[2] &&
           imag(poles.frequencies_hz[index]) <=
               context.gate_policy.maximum_root_growth_rate_hz
    ]
    length(candidates) == 1 || error(
        "D3 complete-complement $(coordinate) diagonal exposes $(length(candidates)) passive roots inside the caller-owned band; expected exactly one.",
    )
    pole_index = only(candidates)
    root_hz = ComplexF64(poles.frequencies_hz[pole_index])
    root_operator = _d3_complete_complement_rp_operator(
        context,
        2π * root_hz,
    )
    retained_index = coordinate == :r ? 1 : 2
    relative_root_residual = _d3_rp_relative_error(
        abs(
            root_operator.effective_dynamic_stiffness[
                retained_index,
                retained_index,
            ],
        ),
        root_operator.diagonal_balance_scale[retained_index],
    )
    relative_root_residual <=
        context.gate_policy.maximum_relative_root_residual || error(
        "D3 complete-complement $(coordinate) diagonal root residual exceeds the caller-owned gate.",
    )
    return (
        coordinate=coordinate,
        root_hz=root_hz,
        angular_root_rad_s=2π * root_hz,
        frequency_hz=real(root_hz),
        external_linewidth_hz=max(-2 * imag(root_hz), 0.0),
        frequency_band_hz=band,
        principal_subsystem_coordinates=context.coordinate_order[indices],
        principal_subsystem_pole_index=pole_index,
        relative_root_residual=relative_root_residual,
        operator=root_operator,
        pole_provenance=poles.provenance,
        pole_hashes=poles.hashes,
    )
end

"""
    d3_complete_complement_rp_metrics(
        model;
        readout_root_band_hz,
        filter_root_band_hz,
        gate_policy,
    )

Evaluate the exact coupling-on matched-open dynamic operator on the retained
physically anchored `R=(r,p)` coordinates after Schur-downfolding exactly
the complete Hybridized complement `E=all coordinates except R`. The two
diagonal complex roots and the complex-midpoint
residue-normalized exchange are one inseparable Stage-2 authority.  This is
not a normal-mode basis and it is not the raw anchored `h` block: the basis is
anchored `r/p`, while the named operation is exact frequency-dependent
complete-complement downfolding.
"""
function d3_complete_complement_rp_metrics(
    model;
    readout_root_band_hz,
    filter_root_band_hz,
    gate_policy,
)
    context = _d3_complete_complement_rp_context(model, gate_policy)
    readout = _d3_complete_complement_rp_diagonal_root(
        model,
        context,
        :r,
        readout_root_band_hz,
    )
    filter = _d3_complete_complement_rp_diagonal_root(
        model,
        context,
        :p,
        filter_root_band_hz,
    )
    readout_slope = -readout.operator.effective_dynamic_stiffness_derivative[1, 1]
    filter_slope = -filter.operator.effective_dynamic_stiffness_derivative[2, 2]
    readout_normalized_slope = _d3_rp_relative_error(
        abs(readout_slope * readout.angular_root_rad_s),
        readout.operator.diagonal_balance_scale[1],
    )
    filter_normalized_slope = _d3_rp_relative_error(
        abs(filter_slope * filter.angular_root_rad_s),
        filter.operator.diagonal_balance_scale[2],
    )
    min(readout_normalized_slope, filter_normalized_slope) >=
        context.gate_policy.minimum_normalized_residue_slope || error(
        "D3 complete-complement RP residue slope is below the caller-owned normalized gate.",
    )
    normalization_product = readout_slope * filter_slope
    isfinite(real(normalization_product)) &&
        isfinite(imag(normalization_product)) &&
        !iszero(normalization_product) || error(
        "D3 complete-complement RP residue normalization is singular or non-finite.",
    )
    normalization = sqrt(normalization_product)
    isfinite(real(normalization)) && isfinite(imag(normalization)) &&
        !iszero(normalization) || error(
        "D3 complete-complement RP principal square-root branch is undefined.",
    )
    midpoint = (readout.angular_root_rad_s + filter.angular_root_rad_s) / 2
    midpoint_operator =
        _d3_complete_complement_rp_operator(context, midpoint)
    sample_frequencies = (
        readout=readout.angular_root_rad_s,
        midpoint=midpoint,
        filter=filter.angular_root_rad_s,
    )
    sample_operators = (
        readout=readout.operator,
        midpoint=midpoint_operator,
        filter=filter.operator,
    )
    coupling_samples = NamedTuple{
        keys(sample_operators),
    }(Tuple(
        operator.effective_dynamic_stiffness[1, 2] / normalization
        for operator in values(sample_operators)
    ))
    coupling_values = collect(values(coupling_samples))
    maximum_pairwise_spread_rad_s = maximum(
        abs(coupling_values[left] - coupling_values[right])
        for left in eachindex(coupling_values)
        for right in eachindex(coupling_values)
    )
    relative_coupling_spread = _d3_rp_relative_error(
        maximum_pairwise_spread_rad_s,
        abs(coupling_samples.midpoint),
    )
    relative_coupling_spread <=
        context.gate_policy.maximum_relative_coupling_spread || error(
        "D3 complete-complement RP three-point coupling spread exceeds the caller-owned gate.",
    )

    midpoint_dynamic = midpoint_operator.dynamic_stiffness
    midpoint_eliminated =
        midpoint_dynamic[context.eliminated_indices, context.eliminated_indices]
    full_logabs, full_phase = logabsdet(midpoint_dynamic)
    eliminated_logabs, eliminated_phase = logabsdet(midpoint_eliminated)
    effective_logabs, effective_phase =
        logabsdet(midpoint_operator.effective_dynamic_stiffness)
    all(isfinite, (full_logabs, eliminated_logabs, effective_logabs)) &&
        !iszero(full_phase) && !iszero(eliminated_phase) &&
        !iszero(effective_phase) || error(
        "D3 complete-complement RP determinant closure is singular or non-finite.",
    )
    schur_logabs = full_logabs - eliminated_logabs
    schur_phase = full_phase / eliminated_phase
    determinant_scale = max(schur_logabs, effective_logabs)
    scaled_schur = schur_phase * exp(schur_logabs - determinant_scale)
    scaled_effective =
        effective_phase * exp(effective_logabs - determinant_scale)
    determinant_closure_error = abs(scaled_schur - scaled_effective) /
        max(abs(scaled_schur), abs(scaled_effective), floatmin(Float64))
    determinant_closure_error <=
        context.gate_policy.maximum_relative_determinant_closure_error ||
        error(
            "D3 complete-complement RP determinant closure exceeds the caller-owned gate.",
        )

    effective_exchange = coupling_samples.midpoint
    return (
        contract_id="d3-complete-complement-rp-effective-operator.v1",
        coupling_state=:qrp_on,
        external_port_state=:matched_open,
        retained_coordinates=[:r, :p],
        eliminated_coordinates=context.coordinate_order[context.eliminated_indices],
        readout=readout,
        filter=filter,
        midpoint_angular_frequency_rad_s=midpoint,
        residue_slopes=(
            readout_s=readout_slope,
            filter_s=filter_slope,
            readout_normalized=readout_normalized_slope,
            filter_normalized=filter_normalized_slope,
        ),
        residue_normalization=normalization,
        square_root_branch=:principal_complex_square_root,
        coupling_samples_rad_s=coupling_samples,
        effective_exchange_rad_s=effective_exchange,
        coherent_exchange_hz=abs(real(effective_exchange)) / (2π),
        total_exchange_hz=abs(effective_exchange) / (2π),
        dissipative_cross_coupling_hz=
            -2 * imag(effective_exchange) / (2π),
        maximum_pairwise_coupling_spread_rad_s=
            maximum_pairwise_spread_rad_s,
        relative_coupling_spread=relative_coupling_spread,
        determinant_closure=(
            schur_logabs=schur_logabs,
            schur_phase=schur_phase,
            effective_logabs=effective_logabs,
            effective_phase=effective_phase,
            relative_error=determinant_closure_error,
        ),
        operator_samples=(
            angular_frequency_rad_s=sample_frequencies,
            readout=readout.operator,
            midpoint=midpoint_operator,
            filter=filter.operator,
        ),
        gate_policy=context.gate_policy,
        context_validation=context.validation,
        source_model_identity=_d3_exact_n_source_model_identity(model),
        provenance=(
            operator=:exact_open_dynamic_stiffness_schur,
            dynamic_stiffness="K-omega^2*C-i*omega*G",
            retained_partition=[:r, :p],
            eliminated_partition=:complete_hybridized_complement,
            eliminated_coordinate_indices=copy(context.eliminated_indices),
            frequency_rank_assignment=:forbidden,
            capacitance_sha256=_d3_exact_n_matrix_sha256(
                "d3-complete-complement-rp-capacitance-f",
                context.capacitance,
            ),
            inverse_inductance_sha256=_d3_exact_n_matrix_sha256(
                "d3-complete-complement-rp-inverse-inductance-h^-1",
                context.stiffness,
            ),
            conductance_sha256=_d3_exact_n_matrix_sha256(
                "d3-complete-complement-rp-conductance-s",
                context.conductance,
            ),
        ),
    )
end

function _d3_loaded_bare_root_band(raw)
    band = Float64.(collect(raw))
    length(band) == 2 && all(isfinite, band) &&
        0 < band[1] < band[2] || error(
        "D3 loaded-bare root band must contain two finite increasing positive frequencies.",
    )
    return band
end

function _d3_feedline_downfolded_coordinate_root(
    model,
    coordinate,
    frequency_band_hz,
)
    coordinate in (:r, :p) || error(
        "D3 feedline-downfolded loaded-bare extraction supports only r or p.",
    )
    coordinate_index = Dict(
        name => index for (index, name) in enumerate(model.coordinate_order)
    )
    all(haskey(coordinate_index, name) for name in (coordinate, :f1, :fc, :f2)) ||
        error(
            "D3 feedline-downfolded loaded-bare extraction requires the retained coordinate and f1/fc/f2.",
        )
    indices = [
        coordinate_index[coordinate],
        coordinate_index[:f1],
        coordinate_index[:fc],
        coordinate_index[:f2],
    ]
    capacitance = Matrix{Float64}(model.capacitance[indices, indices])
    stiffness =
        Matrix{Float64}(model.inverse_inductance[indices, indices])
    selector = Matrix{Float64}(model.selector[indices, :])
    isposdef(Symmetric(capacitance)) || error(
        "D3 feedline-downfolded $(coordinate) capacitance must be positive definite.",
    )
    conductance =
        selector *
        Diagonal(1 ./ Float64.(model.reference_impedance_ohm)) *
        transpose(selector)
    dimension = length(indices)
    generator = [
        zeros(Float64, dimension, dimension) Matrix{Float64}(I, dimension, dimension)
        -(capacitance \ stiffness) -(capacitance \ conductance)
    ]
    raw_eigenvalues_per_s = eigvals(generator)
    raw_frequencies_hz = im .* raw_eigenvalues_per_s ./ (2π)
    scale_hz = max(maximum(abs, raw_frequencies_hz), floatmin(Float64))
    tolerance_hz =
        512 * length(raw_frequencies_hz) * eps(Float64) * scale_hz
    band = _d3_loaded_bare_root_band(frequency_band_hz)
    candidates = [
        index for index in eachindex(raw_frequencies_hz)
        if band[1] <= real(raw_frequencies_hz[index]) <= band[2] &&
           imag(raw_frequencies_hz[index]) <= tolerance_hz
    ]
    length(candidates) == 1 || error(
        "D3 feedline-downfolded $(coordinate) diagonal exposes $(length(candidates)) passive roots inside the declared band; expected exactly one.",
    )
    raw_index = only(candidates)
    root_hz = ComplexF64(raw_frequencies_hz[raw_index])
    return (
        coordinate=coordinate,
        root_hz=root_hz,
        frequency_hz=real(root_hz),
        external_linewidth_hz=max(-2 * imag(root_hz), 0.0),
        frequency_band_hz=band,
        retained_subsystem_coordinates=
            model.coordinate_order[indices],
        raw_state_index=raw_index,
        raw_eigenvalue_per_s=
            ComplexF64(raw_eigenvalues_per_s[raw_index]),
        provenance=(
            source_coupling_state=:qrp_on,
            operator=:exact_open_flux_velocity,
            reduction=:feedline_schur_equivalent_principal_subsystem,
            retained_qrp_off_diagonal_terms=:excluded_from_diagonal_root,
            matched_ports=:on,
            frequency_rank_assignment=:forbidden,
            capacitance_sha256=_d3_exact_n_matrix_sha256(
                "d3-$(coordinate)-loaded-bare-capacitance-f",
                capacitance,
            ),
            inverse_inductance_sha256=_d3_exact_n_matrix_sha256(
                "d3-$(coordinate)-loaded-bare-inverse-inductance-h^-1",
                stiffness,
            ),
            conductance_sha256=_d3_exact_n_matrix_sha256(
                "d3-$(coordinate)-loaded-bare-conductance-s",
                conductance,
            ),
        ),
    )
end

"""
    d3_feedline_downfolded_loaded_bare_roots(model, frequency_band_hz)

Extract the readout and filter diagonal complex roots after eliminating the
matched finite-feedline coordinates from the coupling-on source model. The
real and imaginary parts are legacy response-equivalent fitter diagnostics;
they do not own the revision-9 Stage-2 objective. Stage 2 instead retains
`(r,p)` together and Schur-eliminates exactly `(q,f1,fc,f2)` through
`d3_complete_complement_rp_metrics`. These roots are not Full-QRP
hybridized poles.
"""
function d3_feedline_downfolded_loaded_bare_roots(
    model,
    frequency_band_hz,
)
    band = _d3_loaded_bare_root_band(frequency_band_hz)
    readout = _d3_feedline_downfolded_coordinate_root(model, :r, band)
    filter = _d3_feedline_downfolded_coordinate_root(model, :p, band)
    return (
        contract_id="d3-feedline-downfolded-loaded-bare-roots.v1",
        coupling_state=:qrp_on,
        port_state=:matched_open,
        readout=readout,
        filter=filter,
        source_model_identity=_d3_exact_n_source_model_identity(model),
    )
end

function _d3_state_space_port_trace(
    generator,
    drive,
    observation,
    direct_scattering,
    frequencies,
    label,
)
    state_count = size(generator, 1)
    size(generator, 2) == state_count || error("$(label) generator must be square.")
    size(drive, 1) == state_count || error("$(label) drive row count is invalid.")
    size(observation, 2) == state_count || error(
        "$(label) observation column count is invalid.",
    )
    port_count = size(drive, 2)
    size(observation, 1) == port_count &&
        size(direct_scattering) == (port_count, port_count) || error(
        "$(label) port dimensions are inconsistent.",
    )
    identity_state = Matrix{ComplexF64}(I, state_count, state_count)
    scattering = Matrix{ComplexF64}[]
    for frequency in frequencies
        angular_frequency = 2π * frequency
        push!(
            scattering,
            Matrix{ComplexF64}(
                direct_scattering +
                observation *
                ((-im * angular_frequency * identity_state - generator) \ drive),
            ),
        )
    end
    return (
        scattering=scattering,
        s21=ComplexF64[response[2, 1] for response in scattering],
    )
end

"""Evaluate the Exact-12 analytical port response.

The Exact-12 trace is a similarity-transformed first-order representation of
the same physical open EOM and retains the complete pairing sector.
"""
function d3_cqed_port_trace(cqed_handoff, frequency_hz)
    frequencies = Float64.(collect(frequency_hz))
    !isempty(frequencies) || error("D3 cQED response grid must not be empty.")
    all(value -> isfinite(value) && value > 0, frequencies) || error(
        "D3 cQED response frequencies must be finite and positive.",
    )
    all(diff(frequencies) .> 0) || error(
        "D3 cQED response frequencies must be strictly increasing.",
    )
    ports = cqed_handoff.port_response
    exact = _d3_state_space_port_trace(
        ports.exact.open_generator_per_s,
        ports.exact.drive_per_s,
        ports.exact.observation,
        ports.direct_scattering,
        frequencies,
        "D3 Exact-12 port response",
    )
    port_count = size(ports.direct_scattering, 1)
    identity_ports = Matrix{ComplexF64}(I, port_count, port_count)
    exact_unitarity_defect = maximum(
        maximum(abs, response' * response - identity_ports)
        for response in exact.scattering
    )
    return (
        frequency_hz=frequencies,
        exact=exact,
        passivity=(
            exact_max_unitarity_defect=exact_unitarity_defect,
        ),
        coordinate_order=copy(cqed_handoff.coordinate_order),
        reference_impedance_ohm=copy(ports.reference_impedance_ohm),
        hashes=cqed_handoff.hashes,
    )
end

"""Compare the independent Exact-12 state-space trace with direct C/K response."""
function d3_exact_n_response_closure(
    model,
    frequency_hz;
    cqed_handoff=d3_numerical_cqed_handoff(model),
)
    _d3_exact_n_require_handoff_source(
        model,
        cqed_handoff,
        "D3 analytical-closure cQED handoff",
    )
    analytical = d3_cqed_port_trace(cqed_handoff, frequency_hz)
    direct = d3_exact_n_trace(model, analytical.frequency_hz)
    length(direct.scattering) == length(analytical.exact.scattering) || error(
        "D3 analytical/direct response grids disagree.",
    )
    exact_scattering_residual = [
        analytical.exact.scattering[index] - direct.scattering[index]
        for index in eachindex(direct.scattering)
    ]
    exact_s21_residual = analytical.exact.s21 - direct.s21
    return (
        frequency_hz=analytical.frequency_hz,
        direct=direct,
        analytical=analytical,
        residuals=(
            exact_scattering=exact_scattering_residual,
            exact_s21=exact_s21_residual,
            max_abs_exact_scattering=maximum(
                maximum(abs, residual)
                for residual in exact_scattering_residual
            ),
            max_abs_exact_s21=maximum(abs, exact_s21_residual),
        ),
        exact_closure_status=:candidate_gate__tolerance_not_human_frozen,
    )
end

"""Evaluate one compiled D3 two-port model on an ordinary-frequency grid."""
function d3_compiled_port_trace(model, frequency_hz)
    frequencies = Float64.(collect(frequency_hz))
    !isempty(frequencies) || error("D3 compiled response grid must not be empty.")
    all(value -> isfinite(value) && value > 0, frequencies) || error(
        "D3 compiled response frequencies must be finite and positive.",
    )
    all(diff(frequencies) .> 0) || error(
        "D3 compiled response frequencies must be strictly increasing.",
    )
    responses = [
        matched_port_response(
            model.capacitance,
            model.inverse_inductance,
            2π * frequency,
            model.selector,
            model.reference_impedance_ohm,
        )
        for frequency in frequencies
    ]
    poles = matched_open_poles(
        model.capacitance,
        model.inverse_inductance,
        model.selector,
        model.reference_impedance_ohm,
    )
    return (
        frequency_hz=frequencies,
        scattering=[response.scattering for response in responses],
        s21=ComplexF64[response.scattering[2, 1] for response in responses],
        poles=poles,
        coordinate_order=model.coordinate_order,
        reference_impedance_ohm=model.reference_impedance_ohm,
        provenance=model.provenance,
    )
end

"""Evaluate the canonical D3 Exact-N response and enforce its five-pole invariant."""
function d3_exact_n_trace(model, frequency_hz)
    trace = d3_compiled_port_trace(model, frequency_hz)
    length(trace.poles.frequencies_hz) == 5 || error(
        "D3 Exact-N six-coordinate model must expose five positive-frequency poles.",
    )
    return trace
end

"""
Compile any D3 auxiliary two-port Circuit Plan without applying the Full-QRP
neutral-qubit reduction. The declared external-port rows are removed from the
conservative circuit and then reconstructed as one ordered selector.
"""
function d3_auxiliary_compiled_port_model(built; contract_id)
    hasproperty(built, :plan) || error(
        "D3 auxiliary extraction requires a Circuit Plan builder result.",
    )
    compiled = compile_to_josephson(built.plan)
    boundary = _d3_exact_n_boundary(compiled)
    nodal_model = extract_linear_nodal_model(boundary.conservative)
    length(boundary.port_nodes) == 2 || error(
        "D3 auxiliary extraction requires exactly two declared external ports.",
    )
    selector = zeros(Float64, length(nodal_model.node_names), 2)
    port_indices = Int[]
    for (column, node_name) in enumerate(boundary.port_nodes)
        index = _d3_exact_n_index(
            nodal_model.node_names,
            node_name,
            "auxiliary port $(column)",
        )
        selector[index, column] = 1.0
        push!(port_indices, index)
    end
    return (
        capacitance=nodal_model.capacitance,
        inverse_inductance=nodal_model.inverse_inductance,
        selector=selector,
        reference_impedance_ohm=boundary.reference_impedance_ohm,
        port_indices=port_indices,
        port_nodes=boundary.port_nodes,
        coordinate_order=Symbol.(nodal_model.node_names),
        compiled=compiled,
        conservative_nodal_model=nodal_model,
        provenance=(
            contract_id=String(contract_id),
            plan_id=_d3_exact_n_required_compiled_provenance(compiled, :plan_id),
            circuit_plan_sha256=bytes2hex(
                SHA.sha256(schematic_export_json(built.plan)),
            ),
            capacitance_sha256=nodal_model.capacitance_sha256,
            inverse_inductance_sha256=nodal_model.inverse_inductance_sha256,
            selector_sha256=_d3_exact_n_matrix_sha256(
                "d3-auxiliary-selector",
                selector,
            ),
            removed_boundary_rows=boundary.removed_rows,
            time_convention="exp(-i*omega*t)",
        ),
    )
end

function _d3_intrinsic_pair_z21(model, frequency_hz)
    frequency = Float64(frequency_hz)
    isfinite(frequency) && frequency > 0 || error(
        "D3 intrinsic-pair Z21 frequency must be finite and positive.",
    )
    response = linear_terminal_response(
        model.capacitance,
        model.inverse_inductance,
        2π * frequency,
        model.port_indices,
    )
    return ComplexF64(response.impedance[2, 1])
end

"""
Extract the authoritative intrinsic-pair RP-on notch from a bracketed exact
linear Z21 zero. The result is independent of the 50-ohm normalization used to
declare the two observation ports because it is evaluated from the conservative
terminal impedance matrix.
"""
function d3_intrinsic_pair_notch_frequency(
    built,
    frequency_bracket_hz;
    frequency_tolerance_hz=1.0e3,
    relative_frequency_tolerance=1.0e-12,
    max_iterations=256,
    max_abs_real_z21_ohm=1.0e-2,
    max_abs_imag_z21_ohm=1.0e-2,
    max_abs_complex_z21_ohm=1.0e-2,
)
    model = d3_auxiliary_compiled_port_model(
        built;
        contract_id="d3-intrinsic-pair-rp-on-z21-zero.v1",
    )
    bracket = Float64.(collect(frequency_bracket_hz))
    length(bracket) == 2 && all(isfinite, bracket) &&
        0 < bracket[1] < bracket[2] || error(
        "D3 intrinsic-pair notch bracket must contain two finite increasing positive frequencies.",
    )
    notch_hz = bracketed_bisection(
        frequency -> imag(_d3_intrinsic_pair_z21(model, frequency)),
        bracket;
        absolute_tolerance=frequency_tolerance_hz,
        relative_tolerance=relative_frequency_tolerance,
        max_iterations=max_iterations,
    )
    z21 = _d3_intrinsic_pair_z21(model, notch_hz)
    tolerances = (
        real=Float64(max_abs_real_z21_ohm),
        imag=Float64(max_abs_imag_z21_ohm),
        complex=Float64(max_abs_complex_z21_ohm),
    )
    all(value -> isfinite(value) && value >= 0, values(tolerances)) || error(
        "D3 intrinsic-pair Z21 residual tolerances must be finite and nonnegative.",
    )
    residual_gates = (
        real=abs(real(z21)) <= tolerances.real,
        imag=abs(imag(z21)) <= tolerances.imag,
        complex=abs(z21) <= tolerances.complex,
    )
    all(values(residual_gates)) || error(
        "D3 intrinsic-pair Z21 root failed its complex residual gates.",
    )
    return (
        quantity=:f_n_rp_on,
        frequency_hz=notch_hz,
        z21_ohm=z21,
        frequency_bracket_hz=bracket,
        frequency_tolerance_hz=Float64(frequency_tolerance_hz),
        residual_tolerances_ohm=tolerances,
        residual_gates=residual_gates,
        model=model,
        provenance=(
            contract_id="d3-intrinsic-pair-rp-on-z21-zero.v1",
            circuit_plan_sha256=model.provenance.circuit_plan_sha256,
            coupling_state=:rp_on,
            excluded_subsystems=(:qubit, :c0r, :idc, :feedline),
            numerical_authority=:exact_linear_terminal_impedance,
            hb_ptc_role=:optional_cross_check,
        ),
    )
end

function _d3_linewidth_la_filter_endpoint(built)
    hasproperty(built, :component) || error(
        "D3 linewidth L_A extraction requires its calibration Circuit Plan builder result.",
    )
    component = built.component
    hasproperty(component, :filter_node) && return component.filter_node
    hasproperty(component, :filter_open_tail) && return component.filter_open_tail
    error("D3 linewidth L_A calibration Plan does not expose its filter coordinate.")
end

"""
Extract linewidth L_A from the p-like pole of the diagonal-preserving
filter-only calibration circuit. Closed-mode terminal participation identifies
the filter reference mode; the open pole is then selected by C-metric overlap,
not by raw frequency rank.
"""
function d3_linewidth_la_extraction(
    built,
    frequency_band_hz;
    minimum_identity_overlap=0.5,
    minimum_assignment_margin=0.05,
)
    model = d3_auxiliary_compiled_port_model(
        built;
        contract_id="d3-linewidth-la-diagonal-filter-calibration.v1",
    )
    band = Float64.(collect(frequency_band_hz))
    length(band) == 2 && all(isfinite, band) && 0 < band[1] < band[2] || error(
        "D3 linewidth L_A frequency band must contain two finite increasing positive values.",
    )
    capacitance = Symmetric(Matrix{Float64}(model.capacitance))
    stiffness = Symmetric(Matrix{Float64}(model.inverse_inductance))
    closed = eigen(stiffness, capacitance)
    closed_frequency_hz = sqrt.(max.(closed.values, 0.0)) ./ (2π)
    filter_node_name = _d3_exact_n_node_name(
        model.compiled,
        _d3_linewidth_la_filter_endpoint(built),
        "linewidth L_A filter coordinate",
    )
    filter_index = _d3_exact_n_index(
        model.conservative_nodal_model.node_names,
        filter_node_name,
        "linewidth L_A filter coordinate",
    )
    closed_candidates = [
        index for index in eachindex(closed_frequency_hz)
        if band[1] <= closed_frequency_hz[index] <= band[2]
    ]
    isempty(closed_candidates) && error(
        "D3 linewidth L_A has no closed calibration mode inside the declared band.",
    )
    closed_participation = Dict(
        index => begin
            vector = closed.vectors[:, index]
            denominator = real(vector' * capacitance * vector)
            denominator > 0 || error(
                "D3 linewidth L_A closed mode has non-positive C norm.",
            )
            capacitance[filter_index, filter_index] * abs2(vector[filter_index]) /
                denominator
        end
        for index in closed_candidates
    )
    closed_index = argmax(closed_participation)
    reference = ComplexF64.(closed.vectors[:, closed_index])
    reference ./= sqrt(real(reference' * capacitance * reference))

    poles = matched_open_poles(
        model.capacitance,
        model.inverse_inductance,
        model.selector,
        model.reference_impedance_ohm,
    )
    opened = eigen(poles.state_matrix)
    raw_frequency_hz = im .* opened.values ./ (2π)
    scale_hz = max(maximum(abs, raw_frequency_hz), floatmin(Float64))
    decay_tolerance_hz =
        256.0 * length(raw_frequency_hz) * eps(Float64) * scale_hz
    physical_indices = [
        index for index in eachindex(raw_frequency_hz)
        if band[1] <= real(raw_frequency_hz[index]) <= band[2] &&
           imag(raw_frequency_hz[index]) <= decay_tolerance_hz
    ]
    isempty(physical_indices) && error(
        "D3 linewidth L_A has no passive open pole inside the declared band.",
    )
    dimension = size(model.capacitance, 1)
    overlaps = Dict(
        index => begin
            flux = ComplexF64.(opened.vectors[1:dimension, index])
            norm = real(flux' * capacitance * flux)
            norm > 0 || error(
                "D3 linewidth L_A open pole has non-positive C norm.",
            )
            abs2(reference' * capacitance * flux) / norm
        end
        for index in physical_indices
    )
    ranked = sort(collect(keys(overlaps)); by=index -> overlaps[index], rev=true)
    selected_index = first(ranked)
    selected_overlap = overlaps[selected_index]
    second_overlap = length(ranked) == 1 ? 0.0 : overlaps[ranked[2]]
    margin = selected_overlap - second_overlap
    selected_overlap >= Float64(minimum_identity_overlap) || error(
        "D3 linewidth L_A filter-pole identity overlap is below the declared gate.",
    )
    margin >= Float64(minimum_assignment_margin) || error(
        "D3 linewidth L_A filter-pole identity assignment is ambiguous.",
    )
    pole_frequency_hz = ComplexF64(raw_frequency_hz[selected_index])
    linewidth_hz = max(-2 * imag(pole_frequency_hz), 0.0)
    return (
        quantity=:kappa_p_ext_lb_qrp_off_ext_on,
        linewidth_hz=linewidth_hz,
        pole_frequency_hz=pole_frequency_hz,
        closed_reference_frequency_hz=closed_frequency_hz[closed_index],
        identity_overlap=selected_overlap,
        assignment_margin=margin,
        frequency_band_hz=band,
        model=model,
        provenance=(
            contract_id="d3-linewidth-la-diagonal-filter-calibration.v1",
            circuit_plan_sha256=model.provenance.circuit_plan_sha256,
            internal_coupling_state=:qrp_off,
            diagonal_loading=:retained,
            external_coupling_state=:on,
            internal_loss=:absent,
        ),
    )
end

"""
    d3_exact_open_energy_metric(model; cqed_handoff)

Reconstruct the positive-semidefinite stored-energy metric of the exact
doubled open state from the same compiled C/K model and canonical transform
used by `cqed_handoff`. The scalar factor of two relative to stored energy
cancels from every normalized overlap.
"""
function d3_exact_open_energy_metric(
    model;
    cqed_handoff=d3_numerical_cqed_handoff(model),
)
    _d3_exact_n_require_handoff_source(
        model,
        cqed_handoff,
        "D3 exact-open energy metric cQED handoff",
    )
    capacitance = Matrix{Float64}(model.capacitance)
    stiffness = Matrix{Float64}(model.inverse_inductance)
    size(capacitance) == size(stiffness) || error(
        "D3 exact-open energy metric requires equal-size C and K matrices.",
    )
    dimension = size(capacitance, 1)
    doubled_to_flux_velocity =
        Matrix{ComplexF64}(
            cqed_handoff.port_response.exact.doubled_to_flux_velocity,
        )
    size(doubled_to_flux_velocity) == (2 * dimension, 2 * dimension) || error(
        "D3 exact-open energy metric canonical transform has the wrong shape.",
    )
    flux_velocity_metric = [
        stiffness zeros(Float64, dimension, dimension)
        zeros(Float64, dimension, dimension) capacitance
    ]
    raw_metric =
        doubled_to_flux_velocity' *
        flux_velocity_metric *
        doubled_to_flux_velocity
    metric = Matrix{ComplexF64}(Hermitian((raw_metric + raw_metric') / 2))
    all(
        value -> isfinite(real(value)) && isfinite(imag(value)),
        metric,
    ) || error("D3 exact-open energy metric contains non-finite values.")
    spectrum = eigvals(Hermitian(metric))
    scale = max(maximum(abs, spectrum), floatmin(Float64))
    tolerance = 4096 * length(spectrum) * eps(Float64) * scale
    minimum(spectrum) >= -tolerance || error(
        "D3 exact-open stored-energy metric is not positive semidefinite.",
    )
    state_order =
        copy(cqed_handoff.port_response.exact.state_order.doubled)
    length(state_order) == size(metric, 1) || error(
        "D3 exact-open energy metric state order has the wrong length.",
    )
    source_model_identity = _d3_exact_n_source_model_identity(model)
    return (
        contract_id="d3-exact-open-stored-energy-metric.v1",
        matrix=metric,
        state_order=state_order,
        source_model_identity=source_model_identity,
        construction=:blockdiag_K_C_in_flux_velocity_then_canonical_similarity,
        scalar_convention=:twice_stored_energy,
        matrix_sha256=_d3_exact_n_complex_matrix_sha256(
            "d3-exact-open-stored-energy-metric",
            metric,
        ),
    )
end

function _d3_exact_n_reference_construction(value)
    value isa Symbol || value isa AbstractString || error(
        "D3 exact-open reference construction must be one Symbol or String.",
    )
    construction = strip(String(value))
    !isempty(construction) && lowercase(construction) != "unknown" || error(
        "D3 exact-open reference construction must be concrete.",
    )
    return construction
end

function _d3_exact_open_simple_pole_diagnostics(generator, opened, raw_indices)
    indices = Tuple(Int.(collect(raw_indices)))
    length(unique(indices)) == length(indices) || error(
        "D3 exact-open selected poles must have distinct raw state indices.",
    )
    state_count = size(generator, 1)
    all(index -> 1 <= index <= length(opened.values), indices) || error(
        "D3 exact-open selected pole index is out of range.",
    )
    machine_relative_resolution = 4096 * state_count * eps(Float64)
    generator_scale_per_s = max(opnorm(generator, Inf), floatmin(Float64))
    values = ComplexF64.(opened.values)
    return map(indices) do index
        eigenvalue = values[index]
        separation_per_s = minimum(
            abs(values[other] - eigenvalue)
            for other in eachindex(values) if other != index
        )
        scale_per_s = max(generator_scale_per_s, abs(eigenvalue))
        algebraic_resolution_per_s = machine_relative_resolution * scale_per_s
        separation_per_s > algebraic_resolution_per_s || error(
            "D3 exact-open selected pole is merged, degenerate, or not machine-resolved as a simple root.",
        )

        right_vector = ComplexF64.(opened.vectors[:, index])
        left_nullspace = svd(adjoint(generator) - conj(eigenvalue) * I)
        left_vector = ComplexF64.(adjoint(left_nullspace.Vt)[:, end])
        reciprocal_condition =
            abs(dot(left_vector, right_vector)) /
            (norm(left_vector) * norm(right_vector))
        isfinite(reciprocal_condition) &&
            reciprocal_condition > machine_relative_resolution || error(
            "D3 exact-open selected pole fails simple-root left/right conditioning.",
        )
        return (
            raw_state_index=index,
            eigenvalue_per_s=eigenvalue,
            frequency_hz=im * eigenvalue / (2π),
            nearest_pole_separation_per_s=separation_per_s,
            algebraic_resolution_per_s=algebraic_resolution_per_s,
            reciprocal_eigenvalue_condition=reciprocal_condition,
            minimum_reciprocal_condition=machine_relative_resolution,
        )
    end
end

"""Select one q pole and one unordered two-pole RP subspace from the exact open generator.

The q reference is first projected onto the complete W-orthogonal complement
of the anchored `R=span(r,p)` reference subspace. Candidate assignments are a
distinct q pole plus an unordered pair of RP poles. No frequency rank or
standalone r-like/p-like label participates in selection.
"""
function d3_exact_open_unordered_rp_subspace_assignment(
    model,
    reference_states,
    energy_metric;
    minimum_q_reference_overlap,
    minimum_each_rp_subspace_overlap,
    minimum_unordered_set_assignment_margin,
    cqed_handoff=d3_numerical_cqed_handoff(model),
)
    _d3_exact_n_require_handoff_source(
        model,
        cqed_handoff,
        "D3 exact-open unordered-RP cQED handoff",
    )
    target_identity = _d3_exact_n_source_model_identity(model)
    exact = cqed_handoff.port_response.exact
    state_order = copy(exact.state_order.doubled)
    state_count = length(state_order)
    generator = Matrix{ComplexF64}(exact.open_generator_per_s)
    size(generator) == (state_count, state_count) || error(
        "D3 exact-open generator shape disagrees with its doubled state order.",
    )

    reference_fields = (
        :vectors,
        :state_order,
        :construction,
        :source_model_identity,
        :embedded_target_model_identity,
    )
    all(name -> hasproperty(reference_states, name), reference_fields) || error(
        "D3 exact-open unordered-RP references require vectors, state order, construction, source identity, and target identity.",
    )
    collect(reference_states.state_order) == state_order || error(
        "D3 exact-open unordered-RP references use a different doubled state order.",
    )
    reference_source_identity = _d3_exact_n_validate_model_identity(
        reference_states.source_model_identity,
        "D3 exact-open unordered-RP reference source identity",
    )
    embedded_target_identity = _d3_exact_n_validate_model_identity(
        reference_states.embedded_target_model_identity,
        "D3 exact-open unordered-RP reference target identity",
    )
    reference_source_identity == target_identity || error(
        "D3 exact-open unordered-RP references belong to a different source model.",
    )
    embedded_target_identity == target_identity || error(
        "D3 exact-open unordered-RP references were embedded for a different model.",
    )
    reference_construction =
        _d3_exact_n_reference_construction(reference_states.construction)
    identities = (:q, :r, :p)
    all(name -> hasproperty(reference_states.vectors, name), identities) || error(
        "D3 exact-open unordered-RP reference vectors must provide q, r, and p.",
    )

    metric_fields = (
        :matrix,
        :state_order,
        :construction,
        :source_model_identity,
        :matrix_sha256,
    )
    all(name -> hasproperty(energy_metric, name), metric_fields) || error(
        "D3 exact-open unordered-RP energy metric is incomplete.",
    )
    collect(energy_metric.state_order) == state_order || error(
        "D3 exact-open unordered-RP energy metric uses a different doubled state order.",
    )
    metric_source_identity = _d3_exact_n_validate_model_identity(
        energy_metric.source_model_identity,
        "D3 exact-open unordered-RP energy-metric source identity",
    )
    metric_source_identity == target_identity || error(
        "D3 exact-open unordered-RP energy metric belongs to a different model.",
    )
    metric = Matrix{ComplexF64}(energy_metric.matrix)
    size(metric) == (state_count, state_count) || error(
        "D3 exact-open unordered-RP energy metric has the wrong shape.",
    )
    metric_hash = _d3_exact_n_complex_matrix_sha256(
        "d3-exact-open-stored-energy-metric",
        metric,
    )
    lowercase(strip(String(energy_metric.matrix_sha256))) == metric_hash || error(
        "D3 exact-open unordered-RP energy-metric hash does not match its matrix.",
    )
    metric_scale = max(opnorm(metric, Inf), floatmin(Float64))
    maximum(abs, metric - metric') <=
        4096 * state_count * eps(Float64) * metric_scale || error(
        "D3 exact-open unordered-RP energy metric must be Hermitian.",
    )
    metric = Matrix{ComplexF64}(Hermitian((metric + metric') / 2))
    metric_spectrum = eigvals(Hermitian(metric))
    metric_spectral_scale =
        max(maximum(abs, metric_spectrum), floatmin(Float64))
    metric_tolerance =
        4096 * state_count * eps(Float64) * metric_spectral_scale
    minimum(metric_spectrum) >= -metric_tolerance || error(
        "D3 exact-open unordered-RP energy metric must be positive semidefinite.",
    )

    q_gate = Float64(minimum_q_reference_overlap)
    rp_gate = Float64(minimum_each_rp_subspace_overlap)
    margin_gate = Float64(minimum_unordered_set_assignment_margin)
    for (value, label) in (
        (q_gate, "minimum_q_reference_overlap"),
        (rp_gate, "minimum_each_rp_subspace_overlap"),
        (margin_gate, "minimum_unordered_set_assignment_margin"),
    )
        isfinite(value) && 0 < value <= 1 || error(
            "D3 exact-open $(label) must be finite in (0, 1].",
        )
    end

    raw_references = NamedTuple{identities}(Tuple(
        ComplexF64.(collect(getproperty(reference_states.vectors, identity)))
        for identity in identities
    ))
    all(length(vector) == state_count for vector in values(raw_references)) || error(
        "D3 exact-open unordered-RP reference-vector length disagrees with state order.",
    )
    all(
        value -> isfinite(real(value)) && isfinite(imag(value)),
        Iterators.flatten(values(raw_references)),
    ) || error("D3 exact-open unordered-RP references contain non-finite values.")

    r_matrix = hcat(raw_references.r, raw_references.p)
    r_gram = Matrix{ComplexF64}(r_matrix' * metric * r_matrix)
    r_gram = Matrix{ComplexF64}(Hermitian((r_gram + r_gram') / 2))
    r_spectrum = eigvals(Hermitian(r_gram))
    r_scale = max(maximum(abs, r_spectrum), floatmin(Float64))
    minimum(r_spectrum) > 4096 * 2 * eps(Float64) * r_scale || error(
        "D3 exact-open anchored r/p references do not span a positive two-dimensional energy subspace.",
    )
    r_gram_inverse = inv(r_gram)
    rp_project(vector) = r_matrix * (r_gram_inverse * (r_matrix' * metric * vector))
    q_complement = raw_references.q - rp_project(raw_references.q)
    q_complement_energy = real(q_complement' * metric * q_complement)
    isfinite(q_complement_energy) && q_complement_energy > metric_tolerance || error(
        "D3 exact-open q reference has no positive-energy complete complement to the RP subspace.",
    )
    normalized_q_complement = q_complement / sqrt(q_complement_energy)

    opened = eigen(generator)
    raw_frequency_hz = im .* opened.values ./ (2π)
    all(
        value -> isfinite(real(value)) && isfinite(imag(value)),
        raw_frequency_hz,
    ) || error("D3 exact-open generator produced non-finite poles.")
    pole_scale_hz = max(maximum(abs, raw_frequency_hz), floatmin(Float64))
    decay_tolerance_hz =
        256 * length(raw_frequency_hz) * eps(Float64) * pole_scale_hz
    passive_indices = [
        index for index in eachindex(raw_frequency_hz)
        if real(raw_frequency_hz[index]) > 0 &&
           imag(raw_frequency_hz[index]) <= decay_tolerance_hz
    ]
    passive_vectors = Matrix{ComplexF64}(opened.vectors[:, passive_indices])
    passive_energies = Float64[
        real(passive_vectors[:, column]' * metric * passive_vectors[:, column])
        for column in axes(passive_vectors, 2)
    ]
    all(value -> isfinite(value) && value >= -metric_tolerance, passive_energies) || error(
        "D3 exact-open passive pole has negative stored energy.",
    )
    oscillatory_columns = [
        column for column in eachindex(passive_indices)
        if passive_energies[column] > metric_tolerance
    ]
    positive_raw_indices = passive_indices[oscillatory_columns]
    pole_vectors = passive_vectors[:, oscillatory_columns]
    pole_energies = passive_energies[oscillatory_columns]
    excluded_zero_energy_raw_indices = [
        passive_indices[column]
        for column in eachindex(passive_indices)
        if !(column in oscillatory_columns)
    ]
    length(positive_raw_indices) >= 3 || error(
        "D3 exact-open generator exposes fewer than three passive positive-frequency positive-energy poles.",
    )

    q_overlaps = Float64[]
    rp_overlaps = Float64[]
    for column in eachindex(positive_raw_indices)
        vector = pole_vectors[:, column]
        energy = pole_energies[column]
        q_overlap = abs2(normalized_q_complement' * metric * vector) / energy
        projected = rp_project(vector)
        rp_overlap = real(projected' * metric * projected) / energy
        for (value, label) in ((q_overlap, "q"), (rp_overlap, "RP"))
            isfinite(value) && value >= 0 || error(
                "D3 exact-open normalized $(label) overlap is invalid.",
            )
            value <= 1 + 4096 * state_count * eps(Float64) || error(
                "D3 exact-open normalized $(label) overlap exceeds its energy bound.",
            )
        end
        push!(q_overlaps, min(q_overlap, 1.0))
        push!(rp_overlaps, min(rp_overlap, 1.0))
    end

    assignments = NamedTuple[]
    pole_count = length(positive_raw_indices)
    rp_rank = sort(
        collect(1:pole_count);
        by=index -> (rp_overlaps[index], -positive_raw_indices[index]),
        rev=true,
    )
    for q_index in 1:pole_count
        eligible_rp = [index for index in rp_rank if index != q_index]
        # For a fixed q pole the two largest RP-pair sums can only involve the
        # three highest-ranked remaining RP overlaps. Keeping those candidates
        # avoids cubic enumeration while preserving the exact best and runner-up
        # assignment scores and deterministic raw-index tie breaking.
        top_rp = eligible_rp[1:min(3, length(eligible_rp))]
        for first_position in 1:(length(top_rp) - 1)
            for second_position in (first_position + 1):length(top_rp)
                first_rp = top_rp[first_position]
                second_rp = top_rp[second_position]
            selected = (
                q=q_overlaps[q_index],
                rp=(rp_overlaps[first_rp], rp_overlaps[second_rp]),
            )
            push!(assignments, (
                q_index=q_index,
                rp_indices=(first_rp, second_rp),
                selected=selected,
                mean_score=(selected.q + sum(selected.rp)) / 3,
            ))
            end
        end
    end
    length(assignments) >= 2 || error(
        "D3 exact-open unordered-RP assignment requires at least two distinct q+set candidates.",
    )
    sort!(assignments; by=assignment -> (
        assignment.mean_score,
        min(assignment.selected.q, assignment.selected.rp...),
        -positive_raw_indices[assignment.q_index],
        -positive_raw_indices[assignment.rp_indices[1]],
        -positive_raw_indices[assignment.rp_indices[2]],
    ), rev=true)
    best = assignments[1]
    runner_up = assignments[2]
    best.selected.q >= q_gate || error(
        "D3 exact-open q-complement overlap is below the caller-declared gate.",
    )
    minimum(best.selected.rp) >= rp_gate || error(
        "D3 exact-open RP-subspace overlap is below the caller-declared gate.",
    )
    assignment_margin = best.mean_score - runner_up.mean_score
    assignment_margin >= margin_gate || error(
        "D3 exact-open unordered q+RP-set assignment is ambiguous under the caller-declared margin.",
    )

    selected_raw_indices = (
        positive_raw_indices[best.q_index],
        positive_raw_indices[best.rp_indices[1]],
        positive_raw_indices[best.rp_indices[2]],
    )
    simple_pole_diagnostics = _d3_exact_open_simple_pole_diagnostics(
        generator,
        opened,
        selected_raw_indices,
    )

    pole_frequencies_hz = ComplexF64.(raw_frequency_hz[positive_raw_indices])
    pole_linewidths_hz = Float64.(max.(-2 .* imag.(pole_frequencies_hz), 0.0))
    poles = (
        frequencies_hz=pole_frequencies_hz,
        linewidths_hz=pole_linewidths_hz,
        raw_state_indices=positive_raw_indices,
        raw_eigenvalues_per_s=ComplexF64.(opened.values[positive_raw_indices]),
    )
    linewidth = d3_unordered_rp_subspace_linewidth(
        poles,
        best.rp_indices,
    )
    return (
        contract_id="d3-exact-open-q-and-unordered-rp-subspace.v1",
        state_order=state_order,
        positive_poles=poles,
        excluded_zero_energy_raw_state_indices=excluded_zero_energy_raw_indices,
        overlaps=(q_complement=q_overlaps, rp_subspace=rp_overlaps),
        overlap_column_raw_state_indices=positive_raw_indices,
        selected_simple_poles=simple_pole_diagnostics,
        assignment=(
            q_pole_index=best.q_index,
            unordered_rp_pole_indices=best.rp_indices,
            q_raw_state_index=positive_raw_indices[best.q_index],
            unordered_rp_raw_state_indices=Tuple(
                positive_raw_indices[index] for index in best.rp_indices
            ),
            selected_q_overlap=best.selected.q,
            selected_rp_subspace_overlaps=best.selected.rp,
            best_mean_score=best.mean_score,
            runner_up_mean_score=runner_up.mean_score,
            assignment_margin=assignment_margin,
            minimum_q_reference_overlap=q_gate,
            minimum_each_rp_subspace_overlap=rp_gate,
            minimum_unordered_set_assignment_margin=margin_gate,
        ),
        energy_metric=(
            construction=_d3_exact_n_reference_construction(energy_metric.construction),
            matrix_sha256=metric_hash,
            source_model_identity=metric_source_identity,
        ),
        references=(
            construction=reference_construction,
            source_model_identity=reference_source_identity,
            embedded_target_model_identity=embedded_target_identity,
            rp_energy_gram=r_gram,
            q_complete_complement_energy=q_complement_energy,
        ),
        unordered_rp_linewidth=linewidth,
        provenance=(
            numerical_authority=:exact_doubled_open_generator,
            identity_rule=:q_complete_complement_plus_unordered_rp_subspace,
            unordered_pair_permutation=:equivalent,
            frequency_rank_assignment=:forbidden,
            source_model_identity=target_identity,
            exact_open_generator_sha256=
                cqed_handoff.hashes.exact_open_generator_sha256,
            selected_pole_validity=:machine_resolved_algebraically_simple,
        ),
    )
end

"""Aggregate the two-pole linewidth of one unordered RP-subspace assignment."""
function d3_unordered_rp_subspace_linewidth(poles, raw_pair_indices)
    pair = Tuple(Int.(collect(raw_pair_indices)))
    length(pair) == 2 && pair[1] != pair[2] || error(
        "D3 unordered-RP linewidth requires two distinct pole indices.",
    )
    linewidths = Float64.(poles.linewidths_hz)
    all(value -> isfinite(value) && value >= 0, linewidths) || error(
        "D3 unordered-RP linewidth input must contain finite nonnegative values.",
    )
    all(index -> 1 <= index <= length(linewidths), pair) || error(
        "D3 unordered-RP linewidth contains an out-of-range pole index.",
    )
    selected = Tuple(linewidths[index] for index in pair)
    total = sum(selected)
    total > 0 || error(
        "D3 unordered-RP linewidth requires a positive two-pole sum.",
    )
    fractions = Tuple(value / total for value in selected)
    return (
        quantity=:kappa_sum_unordered_rp_subspace,
        linewidth_sum_hz=total,
        unordered_pair_linewidths_hz=selected,
        linewidth_fraction_min=minimum(fractions),
        linewidth_fraction_max=maximum(fractions),
        unordered_pair_pole_indices=pair,
        excluded_positive_pole_indices=[
            index for index in eachindex(linewidths) if !(index in pair)
        ],
        provenance=(
            contract_id="d3-unordered-rp-subspace-linewidth.v1",
            pole_scope=:unordered_rp_two_pole_subspace,
            q_and_feedline_like_poles=:report_only,
            frequency_rank_assignment=:forbidden,
        ),
    )
end
