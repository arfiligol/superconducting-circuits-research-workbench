# D3 finite-order response is derived from the same compiled top-level
# CircuitPlan used by the equivalent model. This file owns only the D3-specific
# matched-port boundary extraction and neutral floating-qubit 7 -> 6 Routh
# reduction; it does not own topology construction, optimization, or rendering.

using LinearAlgebra
using SHA
using SuperconductingCircuitsCore

function _d3_exact_n_write_float_bits!(chunk, used, value)
    bits = reinterpret(UInt64, iszero(value) ? 0.0 : Float64(value))
    @inbounds for shift in 63:-1:0
        used += 1
        chunk[used] = UInt8('0') + UInt8((bits >> shift) & 0x01)
    end
    return used
end

function _d3_exact_n_matrix_sha256(label, matrix)
    values = Matrix{Float64}(matrix)
    context = SHA.SHA2_256_CTX()
    SHA.update!(
        context,
        codeunits(
            "d3-float64-matrix-v1|$(String(label))|rows=$(size(values, 1))|cols=$(size(values, 2))",
        ),
    )
    chunk = Vector{UInt8}(undef, 4096)
    used = 0
    for row in axes(values, 1), column in axes(values, 2)
        if used + 65 > length(chunk)
            SHA.update!(context, chunk, used)
            used = 0
        end
        used += 1
        chunk[used] = UInt8('|')
        used = _d3_exact_n_write_float_bits!(chunk, used, values[row, column])
    end
    used > 0 && SHA.update!(context, chunk, used)
    return bytes2hex(SHA.digest!(context))
end

function _d3_exact_n_complex_matrix_sha256(label, matrix)
    values = Matrix{ComplexF64}(matrix)
    context = SHA.SHA2_256_CTX()
    SHA.update!(
        context,
        codeunits(
            "d3-complex128-matrix-v1|$(String(label))|rows=$(size(values, 1))|cols=$(size(values, 2))",
        ),
    )
    chunk = Vector{UInt8}(undef, 4096)
    used = 0
    for row in axes(values, 1), column in axes(values, 2)
        if used + 130 > length(chunk)
            SHA.update!(context, chunk, used)
            used = 0
        end
        value = values[row, column]
        used += 1
        chunk[used] = UInt8('|')
        used = _d3_exact_n_write_float_bits!(chunk, used, real(value))
        used += 1
        chunk[used] = UInt8(',')
        used = _d3_exact_n_write_float_bits!(chunk, used, imag(value))
    end
    used > 0 && SHA.update!(context, chunk, used)
    return bytes2hex(SHA.digest!(context))
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

    capacitance_factorization = lu(capacitance)
    inverse_capacitance =
        capacitance_factorization \ Matrix{Float64}(I, dimension, dimension)
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
    capacitance_solved_stiffness = capacitance_factorization \ stiffness
    capacitance_solved_conductance = capacitance_factorization \ conductance
    identity_dimension = Matrix{Float64}(I, dimension, dimension)
    zero_dimension = zeros(Float64, dimension, dimension)
    closed_flux_velocity_generator = [
        zero_dimension identity_dimension
        -capacitance_solved_stiffness zero_dimension
    ]
    open_flux_velocity_generator = [
        zero_dimension identity_dimension
        -capacitance_solved_stiffness -capacitance_solved_conductance
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
    machine_relative_resolution = 4096 * dimension * eps(Float64)
    capacitance_reciprocity =
        _d3_rp_reciprocity_error(capacitance)
    stiffness_reciprocity =
        _d3_rp_reciprocity_error(stiffness)
    max(capacitance_reciprocity, stiffness_reciprocity) <=
        machine_relative_resolution || error(
        "D3 complete-complement RP C/K reciprocity is not machine-resolved.",
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
        machine_relative_resolution || error(
        "D3 complete-complement RP port conductance reciprocity is not machine-resolved.",
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
        machine_relative_resolution || error(
        "D3 complete-complement RP K/G passivity is not machine-resolved.",
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
            machine_relative_resolution=machine_relative_resolution,
            capacitance_reciprocity_error=capacitance_reciprocity,
            stiffness_reciprocity_error=stiffness_reciprocity,
            conductance_reciprocity_error=conductance_reciprocity,
            capacitance_positive_definite=true,
            stiffness_minimum_eigenvalue=minimum(stiffness_eigenvalues),
            stiffness_psd_absolute_tolerance=
                machine_relative_resolution * stiffness_scale,
            conductance_minimum_eigenvalue=minimum(conductance_eigenvalues),
            conductance_psd_absolute_tolerance=
                machine_relative_resolution * conductance_scale,
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

    elimination_machine_relative_resolution =
        4096 * size(d_ee, 1) * eps(Float64)
    elimination_condition_number = cond(d_ee)
    elimination_reciprocal_condition =
        isfinite(elimination_condition_number) &&
        elimination_condition_number > 0 ?
        inv(elimination_condition_number) : 0.0
    d_ee_factorization = try
        lu(d_ee)
    catch exception
        error(
            "D3 complete-complement RP eliminated-block solve failed: $(sprint(showerror, exception))",
        )
    end
    eliminated_response = try
        d_ee_factorization \ d_er
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
        elimination_machine_relative_resolution ||
        error(
            "D3 complete-complement RP eliminated-block solve residual is not machine-resolved.",
        )
    eliminated_response_derivative = try
        d_ee_factorization \ (
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
        elimination_machine_relative_resolution ||
        error(
            "D3 complete-complement RP derivative solve residual is not machine-resolved.",
        )

    effective =
        d_rr - d_re * eliminated_response
    effective_derivative =
        derivative_rr -
        derivative_re * eliminated_response -
        d_re * eliminated_response_derivative
    reciprocity_error =
        _d3_rp_reciprocity_error(effective)
    effective_machine_relative_resolution =
        elimination_machine_relative_resolution
    reciprocity_error <=
        effective_machine_relative_resolution || error(
        "D3 complete-complement RP effective-operator reciprocity is not machine-resolved.",
    )
    effective = (effective + transpose(effective)) / 2
    effective_derivative =
        (effective_derivative + transpose(effective_derivative)) / 2
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
            elimination_machine_relative_resolution=
                elimination_machine_relative_resolution,
            elimination_condition_number=elimination_condition_number,
            elimination_reciprocal_condition=
                elimination_reciprocal_condition,
            relative_elimination_solve_residual=relative_solve_residual,
            relative_derivative_solve_residual=
                relative_derivative_solve_residual,
            effective_machine_relative_resolution=
                effective_machine_relative_resolution,
            effective_reciprocity_error=reciprocity_error,
        ),
    )
end

function _d3_targeted_schur_fixed_context(model)
    coordinate_order = Symbol.(collect(model.coordinate_order))
    dimension = length(coordinate_order)
    anchors = model.anchored_coordinate_indices
    all(name -> hasproperty(anchors, name), (:q, :r, :p, :f1, :fc, :f2)) ||
        error("D3 targeted-Schur context requires q/r/p/f1/fc/f2 anchors.")
    anchor_indices = Int[getproperty(anchors, name) for name in (:q, :r, :p, :f1, :fc, :f2)]
    all(index -> 1 <= index <= dimension, anchor_indices) &&
        length(unique(anchor_indices)) == length(anchor_indices) ||
        error("D3 targeted-Schur anchor indices are invalid or non-unique.")
    selector = Matrix{Float64}(model.selector)
    size(selector) == (dimension, 2) || error(
        "D3 targeted-Schur context requires an N x 2 port selector.",
    )
    impedances = Float64.(collect(model.reference_impedance_ohm))
    length(impedances) == 2 && all(value -> isfinite(value) && value > 0, impedances) ||
        error("D3 targeted-Schur context requires two positive port impedances.")
    capacitance = Matrix{Float64}(model.capacitance)
    stiffness = Matrix{Float64}(model.inverse_inductance)
    size(capacitance) == size(stiffness) == (dimension, dimension) ||
        error("D3 targeted-Schur reference C/K shapes disagree.")
    all(isfinite, capacitance) && all(isfinite, stiffness) && all(isfinite, selector) ||
        error("D3 targeted-Schur reference matrices must be finite.")
    machine_resolution = 4096 * dimension * eps(Float64)
    max(_d3_rp_reciprocity_error(capacitance), _d3_rp_reciprocity_error(stiffness)) <=
        machine_resolution || error("D3 targeted-Schur reference C/K are not reciprocal.")
    capacitance = Matrix(Symmetric((capacitance + transpose(capacitance)) / 2))
    stiffness = Matrix(Symmetric((stiffness + transpose(stiffness)) / 2))
    isposdef(Symmetric(capacitance)) || error(
        "D3 targeted-Schur reference capacitance must be positive definite.",
    )
    conductance = selector * Diagonal(1 ./ impedances) * transpose(selector)
    stiffness_spectrum = eigvals(Symmetric(stiffness))
    conductance_spectrum = eigvals(Symmetric(conductance))
    stiffness_scale = max(maximum(abs, stiffness_spectrum), floatmin(Float64))
    conductance_scale = max(maximum(abs, conductance_spectrum), floatmin(Float64))
    minimum(stiffness_spectrum) >= -machine_resolution * stiffness_scale ||
        error("D3 targeted-Schur reference stiffness is not machine-positive-semidefinite.")
    minimum(conductance_spectrum) >= -machine_resolution * conductance_scale ||
        error("D3 targeted-Schur port conductance is not machine-positive-semidefinite.")
    retained = [Int(anchors.r), Int(anchors.p)]
    eliminated = [index for index in 1:dimension if !(index in retained)]
    return (
        conductance=Matrix{Float64}(conductance),
        selector=selector,
        reference_impedance_ohm=impedances,
        coordinate_order=coordinate_order,
        anchored_coordinate_indices=anchors,
        retained_indices=retained,
        eliminated_indices=eliminated,
        dimension=dimension,
        machine_relative_resolution=machine_resolution,
        validation=(
            capacitance_positive_definite=true,
            stiffness_minimum_eigenvalue=minimum(stiffness_spectrum),
            conductance_minimum_eigenvalue=minimum(conductance_spectrum),
        ),
    )
end

function _d3_targeted_schur_candidate_context(fixed, capacitance, stiffness)
    c = Matrix{Float64}(capacitance)
    k = Matrix{Float64}(stiffness)
    size(c) == size(k) == (fixed.dimension, fixed.dimension) ||
        error("D3 targeted-Schur candidate C/K shapes disagree with the fixed context.")
    all(isfinite, c) && all(isfinite, k) ||
        error("D3 targeted-Schur candidate C/K matrices must be finite.")
    max(_d3_rp_reciprocity_error(c), _d3_rp_reciprocity_error(k)) <=
        fixed.machine_relative_resolution ||
        error("D3 targeted-Schur candidate C/K reciprocity is not machine-resolved.")
    return (
        capacitance=Matrix(Symmetric((c + transpose(c)) / 2)),
        stiffness=Matrix(Symmetric((k + transpose(k)) / 2)),
        conductance=fixed.conductance,
        retained_indices=fixed.retained_indices,
        eliminated_indices=fixed.eliminated_indices,
        machine_relative_resolution=fixed.machine_relative_resolution,
    )
end

function _d3_targeted_schur_operator(context, angular_frequency_rad_s)
    omega = ComplexF64(angular_frequency_rad_s)
    isfinite(real(omega)) && isfinite(imag(omega)) && real(omega) > 0 ||
        error("D3 targeted-Schur angular frequency must be finite with positive real part.")
    dynamic = ComplexF64.(context.stiffness) .-
        omega^2 .* context.capacitance .-
        im * omega .* context.conductance
    derivative = -2 * omega .* context.capacitance .- im .* context.conductance
    r = context.retained_indices
    e = context.eliminated_indices
    d_rr = dynamic[r, r]
    d_re = dynamic[r, e]
    d_er = dynamic[e, r]
    d_ee = dynamic[e, e]
    dp_rr = derivative[r, r]
    dp_re = derivative[r, e]
    dp_er = derivative[e, r]
    dp_ee = derivative[e, e]
    factorization = try
        lu(d_ee; check=true)
    catch exception
        exception isa SingularException || exception isa ZeroPivotException || rethrow()
        error("D3 targeted-Schur eliminated block is singular: $(sprint(showerror, exception))")
    end
    response = factorization \ d_er
    response_derivative = factorization \ (dp_er - dp_ee * response)
    all(value -> isfinite(real(value)) && isfinite(imag(value)), response) ||
        error("D3 targeted-Schur eliminated solve became non-finite.")
    residual = d_ee * response - d_er
    residual_scale = opnorm(d_ee, Inf) * opnorm(response, Inf) + opnorm(d_er, Inf)
    _d3_rp_relative_error(opnorm(residual, Inf), residual_scale) <=
        4096 * size(d_ee, 1) * eps(Float64) ||
        error("D3 targeted-Schur eliminated solve residual is not machine-resolved.")
    effective = d_rr - d_re * response
    effective_derivative =
        dp_rr - dp_re * response - d_re * response_derivative
    _d3_rp_reciprocity_error(effective) <=
        4096 * size(d_ee, 1) * eps(Float64) ||
        error("D3 targeted-Schur effective operator is not machine-reciprocal.")
    return (
        effective_dynamic_stiffness=Matrix{ComplexF64}(
            (effective + transpose(effective)) / 2,
        ),
        effective_dynamic_stiffness_derivative=Matrix{ComplexF64}(
            (effective_derivative + transpose(effective_derivative)) / 2,
        ),
    )
end

function _d3_targeted_schur_newton(value_and_derivative, initial_omega, label)
    omega = ComplexF64(initial_omega)
    for iteration in 1:32
        value, derivative = value_and_derivative(omega)
        all(isfinite, (real(value), imag(value), real(derivative), imag(derivative))) ||
            error("$(label) evaluation became non-finite.")
        iszero(derivative) && error("$(label) derivative is zero.")
        delta = value / derivative
        next_omega = omega - delta
        all(isfinite, (real(next_omega), imag(next_omega))) && real(next_omega) > 0 ||
            error("$(label) selected an invalid root.")
        omega = next_omega
        if abs(delta) <= 1.0e-10 * max(abs(omega), 1.0)
            residual, derivative_at_root = value_and_derivative(omega)
            return (
                root_rad_s=omega,
                iterations=iteration,
                residual=residual,
                derivative=derivative_at_root,
            )
        end
    end
    error("$(label) did not settle within 32 iterations.")
end

function _d3_targeted_schur_diagonal_root(context, index, anchor_hz, label)
    anchor = Float64(anchor_hz)
    isfinite(anchor) && anchor > 0 || error("$(label) anchor must be finite and positive.")
    return _d3_targeted_schur_newton(2π * anchor, label) do omega
        operator = _d3_targeted_schur_operator(context, omega)
        return (
            operator.effective_dynamic_stiffness[index, index],
            operator.effective_dynamic_stiffness_derivative[index, index],
        )
    end
end

"""Extract the fixed-node complete-complement RP anchored-bare quantities."""
function _d3_targeted_schur_outputs(
    context;
    readout_root_anchor_hz,
    filter_root_anchor_hz,
)
    readout = _d3_targeted_schur_diagonal_root(
        context,
        1,
        readout_root_anchor_hz,
        "D3 targeted-Schur readout diagonal root",
    )
    filter = _d3_targeted_schur_diagonal_root(
        context,
        2,
        filter_root_anchor_hz,
        "D3 targeted-Schur filter diagonal root",
    )
    residue_slopes = (r=-readout.derivative, p=-filter.derivative)
    normalization = sqrt(residue_slopes.r * residue_slopes.p)
    isfinite(real(normalization)) && isfinite(imag(normalization)) && !iszero(normalization) ||
        error("D3 targeted-Schur residue normalization is singular or non-finite.")
    midpoint = (readout.root_rad_s + filter.root_rad_s) / 2
    midpoint_operator = _d3_targeted_schur_operator(context, midpoint)
    exchange_rad_s = midpoint_operator.effective_dynamic_stiffness[1, 2] / normalization

    diagonal_roots_hz = (
        r=ComplexF64(readout.root_rad_s / (2π)),
        p=ComplexF64(filter.root_rad_s / (2π)),
    )
    kappa_hz = (
        r=Float64(-2 * imag(diagonal_roots_hz.r)),
        p=Float64(-2 * imag(diagonal_roots_hz.p)),
    )
    all(value -> isfinite(value) && value >= 0, values(kappa_hz)) || error(
        "D3 targeted-Schur anchored-bare linewidths must be finite and nonnegative.",
    )
    kappa_sum_hz = sum(values(kappa_hz))
    kappa_sum_hz > 0 || error("D3 targeted-Schur anchored-bare linewidth sum is zero.")
    return (
        readout=readout,
        filter=filter,
        diagonal_roots_hz=diagonal_roots_hz,
        residue_slopes=(
            r=ComplexF64(residue_slopes.r),
            p=ComplexF64(residue_slopes.p),
        ),
        exchange_rad_s=exchange_rad_s,
        kappa_hz=kappa_hz,
        kappa_sum_hz=kappa_sum_hz,
        linewidth_fraction_min=
            minimum(values(kappa_hz)) / kappa_sum_hz,
    )
end

function _d3_complete_complement_rp_principal_indices(context, coordinate)
    coordinate in (:r, :p) || error(
        "D3 complete-complement RP diagonal root supports only r or p.",
    )
    retained_index = coordinate == :r ? 1 : 2
    return [
        context.retained_indices[retained_index],
        context.eliminated_indices...,
    ]
end

function _d3_complete_complement_rp_simple_root_diagnostics(poles, pole_index)
    eigenvalue = ComplexF64(poles.physical_eigenvalues[pole_index])
    raw_eigenvalues = ComplexF64.(poles.raw_eigenvalues)
    raw_index = findfirst(==(eigenvalue), raw_eigenvalues)
    isnothing(raw_index) && error(
        "D3 complete-complement RP selected pole is missing from the raw spectrum.",
    )
    state_count = size(poles.state_matrix, 1)
    machine_relative_resolution = 4096 * state_count * eps(Float64)
    scale_per_s = max(maximum(abs, raw_eigenvalues), abs(eigenvalue))
    algebraic_resolution_per_s = machine_relative_resolution * scale_per_s
    nearest_pole_separation_per_s = minimum(
        abs(raw_eigenvalues[index] - eigenvalue)
        for index in eachindex(raw_eigenvalues) if index != raw_index
    )
    nearest_pole_separation_per_s > algebraic_resolution_per_s || error(
        "D3 complete-complement RP selected pole is merged, degenerate, or not machine-resolved as a simple root.",
    )
    return (
        raw_state_index=raw_index,
        eigenvalue_per_s=eigenvalue,
        nearest_pole_separation_per_s=nearest_pole_separation_per_s,
        algebraic_resolution_per_s=algebraic_resolution_per_s,
    )
end

function _d3_complete_complement_rp_diagonal_root(
    model,
    context,
    coordinate,
    raw_frequency_band_hz,
)
    indices = _d3_complete_complement_rp_principal_indices(
        context,
        coordinate,
    )
    retained_index = coordinate == :r ? 1 : 2
    band = _d3_loaded_bare_root_band(raw_frequency_band_hz)
    poles = matched_open_poles(
        context.capacitance[indices, indices],
        context.stiffness[indices, indices],
        context.selector[indices, :],
        context.reference_impedance_ohm,
    )
    passive_candidates = collect(eachindex(poles.frequencies_hz))
    selection_anchor_hz = band[1] + (band[2] - band[1]) / 2
    selection_distances_hz = [
        abs(real(poles.frequencies_hz[index]) - selection_anchor_hz)
        for index in passive_candidates
    ]
    minimum_distance_hz = minimum(selection_distances_hz)
    selection_distance_resolution_hz =
        4096 * length(poles.raw_eigenvalues) * eps(Float64) * max(
            selection_anchor_hz,
            maximum(abs, poles.frequencies_hz),
        )
    nearest_candidates = passive_candidates[
        abs.(selection_distances_hz .- minimum_distance_hz) .<=
        selection_distance_resolution_hz
    ]
    length(nearest_candidates) == 1 || error(
        "D3 complete-complement $(coordinate) diagonal nearest-anchor root selection is non-unique.",
    )
    pole_index = only(nearest_candidates)
    simple_root =
        _d3_complete_complement_rp_simple_root_diagnostics(poles, pole_index)
    root_hz = ComplexF64(poles.frequencies_hz[pole_index])
    root_operator = _d3_complete_complement_rp_operator(
        context,
        2π * root_hz,
    )
    relative_root_residual = _d3_rp_relative_error(
        abs(
            root_operator.effective_dynamic_stiffness[
                retained_index,
                retained_index,
            ],
        ),
        root_operator.diagonal_balance_scale[retained_index],
    )
    return (
        coordinate=coordinate,
        root_hz=root_hz,
        angular_root_rad_s=2π * root_hz,
        frequency_hz=real(root_hz),
        external_linewidth_hz=max(-2 * imag(root_hz), 0.0),
        frequency_band_hz=band,
        selection_anchor_hz=selection_anchor_hz,
        selection_distance_resolution_hz=
            selection_distance_resolution_hz,
        selected_root_inside_band=
            band[1] <= real(root_hz) <= band[2],
        principal_subsystem_coordinates=context.coordinate_order[indices],
        principal_subsystem_pole_index=pole_index,
        simple_root=simple_root,
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
complete-complement downfolding. Each supplied root band contributes only its
midpoint as a selection anchor: the unique nearest passive principal-subsystem
root is returned, while band containment is recorded as diagnostic evidence
and is not an eligibility gate.
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
    all(
        value -> isfinite(real(value)) && isfinite(imag(value)),
        coupling_values,
    ) || error(
        "D3 complete-complement RP coupling evidence is non-finite.",
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
    isfinite(determinant_closure_error) || error(
        "D3 complete-complement RP determinant closure error is non-finite.",
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
        numeric_control_disposition=(
            status=:proposed_inactive,
            role=:diagnostic_only,
            fields=D3_COMPLETE_COMPLEMENT_RP_GATE_FIELDS,
        ),
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

function _d3_targeted_cofactor_notch_from_model(model, selection_anchor_hz)
    anchor_hz = Float64(selection_anchor_hz)
    isfinite(anchor_hz) && anchor_hz > 0 || error(
        "D3 targeted cofactor-zero anchor must be finite and positive.",
    )
    capacitance = Matrix{Float64}(model.capacitance)
    stiffness = Matrix{Float64}(model.inverse_inductance)
    dimension = size(capacitance, 1)
    size(capacitance) == size(stiffness) == (dimension, dimension) || error(
        "D3 targeted cofactor-zero C/K matrices must be square and shape-matched.",
    )
    all(isfinite, capacitance) && all(isfinite, stiffness) || error(
        "D3 targeted cofactor-zero C/K matrices must be finite.",
    )
    port_indices = Int.(collect(model.port_indices))
    length(port_indices) == 2 && length(unique(port_indices)) == 2 &&
        all(index -> 1 <= index <= dimension, port_indices) || error(
        "D3 targeted cofactor-zero requires two distinct valid port indices.",
    )
    input_index, output_index = port_indices
    rows = [index for index in 1:dimension if index != input_index]
    columns = [index for index in 1:dimension if index != output_index]
    angular_anchor_rad_s = 2π * anchor_hz
    scaled_zero_eigenvalues = ComplexF64.(eigvals(
        stiffness[rows, columns] / angular_anchor_rad_s^2,
        capacitance[rows, columns],
    ))
    machine_relative_resolution = 4096 * dimension * eps(Float64)
    zero_candidate_indices = [
        index for index in eachindex(scaled_zero_eigenvalues)
        if isfinite(scaled_zero_eigenvalues[index]) &&
           real(scaled_zero_eigenvalues[index]) > 0 &&
           abs(imag(scaled_zero_eigenvalues[index])) <=
               machine_relative_resolution *
               max(abs(scaled_zero_eigenvalues[index]), 1.0)
    ]
    isempty(zero_candidate_indices) && error(
        "D3 targeted cofactor pencil exposes no finite positive machine-real zero.",
    )
    zero_candidate_frequencies_hz = Float64[
        anchor_hz * sqrt(real(scaled_zero_eigenvalues[index]))
        for index in zero_candidate_indices
    ]
    selection_distances_hz =
        abs.(zero_candidate_frequencies_hz .- anchor_hz)
    selection_resolution_hz = machine_relative_resolution * max(
        anchor_hz,
        maximum(zero_candidate_frequencies_hz),
    )
    minimum_selection_distance_hz = minimum(selection_distances_hz)
    nearest_positions = findall(
        distance -> abs(distance - minimum_selection_distance_hz) <=
            selection_resolution_hz,
        selection_distances_hz,
    )
    length(nearest_positions) == 1 || error(
        "D3 targeted cofactor zero nearest the anchor is not machine-unique.",
    )
    selected_position = only(nearest_positions)
    selected_zero_index = zero_candidate_indices[selected_position]
    finite_zero_indices = findall(isfinite, scaled_zero_eigenvalues)
    other_finite_zero_indices = [
        index for index in finite_zero_indices if index != selected_zero_index
    ]
    nearest_scaled_zero_separation = isempty(other_finite_zero_indices) ? Inf :
        minimum(
            abs(
                scaled_zero_eigenvalues[index] -
                scaled_zero_eigenvalues[selected_zero_index],
            )
            for index in other_finite_zero_indices
        )
    scaled_zero_resolution = machine_relative_resolution * max(
        maximum(abs, scaled_zero_eigenvalues[finite_zero_indices]),
        1.0,
    )
    nearest_scaled_zero_separation > scaled_zero_resolution || error(
        "D3 targeted cofactor zero is not machine-resolved as a simple root.",
    )

    notch_hz = zero_candidate_frequencies_hz[selected_position]
    angular_frequency_rad_s = 2π * notch_hz
    dynamic_stiffness = stiffness - angular_frequency_rad_s^2 * capacitance
    factorization = try
        lu(dynamic_stiffness; check=true)
    catch exception
        exception isa SingularException || exception isa ZeroPivotException || rethrow()
        error(
            "D3 targeted cofactor-zero local denominator is singular: " *
            sprint(showerror, exception),
        )
    end
    pivot_magnitudes = abs.(diag(factorization.U))
    all(isfinite, pivot_magnitudes) && all(value -> !iszero(value), pivot_magnitudes) || error(
        "D3 targeted cofactor-zero local denominator is non-finite or zero.",
    )
    source = zeros(Float64, dimension)
    source[input_index] = 1.0
    response = factorization \ source
    all(isfinite, response) || error(
        "D3 targeted cofactor-zero local response is non-finite.",
    )
    solve_residual = dynamic_stiffness * response - source
    relative_solve_residual = _d3_rp_relative_error(
        norm(solve_residual, Inf),
        opnorm(dynamic_stiffness, Inf) * norm(response, Inf) + 1.0,
    )
    isfinite(relative_solve_residual) || error(
        "D3 targeted cofactor-zero local solve residual is non-finite.",
    )
    z21 = ComplexF64(-im * angular_frequency_rad_s * response[output_index])
    isfinite(real(z21)) && isfinite(imag(z21)) || error(
        "D3 targeted cofactor-zero Z21 evaluation is non-finite.",
    )
    return (
        frequency_hz=notch_hz,
        z21_ohm=z21,
        selection_anchor_hz=anchor_hz,
        zero_candidates=(
            scaled_squared_frequency_eigenvalues=scaled_zero_eigenvalues,
            physical_candidate_indices=zero_candidate_indices,
            frequencies_hz=zero_candidate_frequencies_hz,
            selected_position=selected_position,
            selected_generalized_eigenvalue=
                scaled_zero_eigenvalues[selected_zero_index],
            nearest_finite_spectrum_separation=
                nearest_scaled_zero_separation,
            finite_spectrum_resolution=scaled_zero_resolution,
        ),
        local_denominator=(
            factorization_succeeded=true,
            minimum_pivot_magnitude=minimum(pivot_magnitudes),
            maximum_pivot_magnitude=maximum(pivot_magnitudes),
        ),
        local_residual=(
            relative_solve_residual=relative_solve_residual,
            abs_z21_ohm=abs(z21),
        ),
    )
end

function _d3_intrinsic_pair_notch_from_model(
    model,
    frequency_bracket_hz;
    frequency_tolerance_hz=1.0e3,
    relative_frequency_tolerance=1.0e-12,
    max_iterations=256,
    max_abs_real_z21_ohm=1.0e-2,
    max_abs_imag_z21_ohm=1.0e-2,
    max_abs_complex_z21_ohm=1.0e-2,
)
    bracket = Float64.(collect(frequency_bracket_hz))
    length(bracket) == 2 && all(isfinite, bracket) &&
        0 < bracket[1] < bracket[2] || error(
        "D3 intrinsic-pair notch bracket must contain two finite increasing positive frequencies.",
    )
    selection_anchor_hz = bracket[1] + (bracket[2] - bracket[1]) / 2
    capacitance = Matrix{Float64}(model.capacitance)
    stiffness = Matrix{Float64}(model.inverse_inductance)
    dimension = size(capacitance, 1)
    size(capacitance) == (dimension, dimension) &&
        size(stiffness) == (dimension, dimension) || error(
        "D3 intrinsic-pair notch C/K matrices must be square and shape-matched.",
    )
    all(isfinite, capacitance) && all(isfinite, stiffness) || error(
        "D3 intrinsic-pair notch C/K matrices must be finite.",
    )
    machine_relative_resolution = 4096 * dimension * eps(Float64)
    max(
        _d3_rp_reciprocity_error(capacitance),
        _d3_rp_reciprocity_error(stiffness),
    ) <= machine_relative_resolution || error(
        "D3 intrinsic-pair notch C/K reciprocity is not machine-resolved.",
    )
    capacitance = Matrix(Symmetric((capacitance + transpose(capacitance)) / 2))
    stiffness = Matrix(Symmetric((stiffness + transpose(stiffness)) / 2))
    isposdef(Symmetric(capacitance)) || error(
        "D3 intrinsic-pair notch capacitance must be positive definite.",
    )
    stiffness_eigenvalues = eigvals(Symmetric(stiffness))
    stiffness_scale = max(maximum(abs, stiffness_eigenvalues), floatmin(Float64))
    minimum(stiffness_eigenvalues) >=
        -machine_relative_resolution * stiffness_scale || error(
        "D3 intrinsic-pair notch stiffness is not machine-positive-semidefinite.",
    )
    port_indices = Int.(collect(model.port_indices))
    length(port_indices) == 2 && length(unique(port_indices)) == 2 &&
        all(index -> 1 <= index <= dimension, port_indices) || error(
        "D3 intrinsic-pair notch requires two distinct valid port indices.",
    )
    input_index, output_index = port_indices
    rows = [index for index in 1:dimension if index != input_index]
    columns = [index for index in 1:dimension if index != output_index]
    angular_anchor_rad_s = 2π * selection_anchor_hz
    angular_anchor_squared = angular_anchor_rad_s^2
    scaled_zero_eigenvalues = ComplexF64.(eigvals(
        stiffness[rows, columns] / angular_anchor_squared,
        capacitance[rows, columns],
    ))
    zero_candidate_indices = [
        index for index in eachindex(scaled_zero_eigenvalues)
        if isfinite(scaled_zero_eigenvalues[index]) &&
           real(scaled_zero_eigenvalues[index]) > 0 &&
           abs(imag(scaled_zero_eigenvalues[index])) <=
               machine_relative_resolution *
               max(abs(scaled_zero_eigenvalues[index]), 1.0)
    ]
    isempty(zero_candidate_indices) && error(
        "D3 intrinsic-pair notch cofactor pencil exposes no finite positive machine-real zero.",
    )
    zero_candidate_frequencies_hz = Float64[
        selection_anchor_hz *
        sqrt(real(scaled_zero_eigenvalues[index]))
        for index in zero_candidate_indices
    ]
    selection_distance_resolution_hz =
        machine_relative_resolution * max(
            selection_anchor_hz,
            maximum(zero_candidate_frequencies_hz),
        )
    selection_distances_hz =
        abs.(zero_candidate_frequencies_hz .- selection_anchor_hz)
    minimum_selection_distance_hz = minimum(selection_distances_hz)
    nearest_positions = findall(
        distance -> abs(distance - minimum_selection_distance_hz) <=
            selection_distance_resolution_hz,
        selection_distances_hz,
    )
    length(nearest_positions) == 1 || error(
        "D3 intrinsic-pair notch nearest-anchor zero is not machine-unique.",
    )
    selected_position = only(nearest_positions)
    selected_zero_index = zero_candidate_indices[selected_position]
    finite_zero_indices = findall(isfinite, scaled_zero_eigenvalues)
    other_finite_zero_indices = [
        index for index in finite_zero_indices if index != selected_zero_index
    ]
    nearest_scaled_zero_separation = isempty(other_finite_zero_indices) ? Inf :
        minimum(
            abs(
                scaled_zero_eigenvalues[index] -
                scaled_zero_eigenvalues[selected_zero_index],
            )
            for index in other_finite_zero_indices
        )
    scaled_zero_resolution = machine_relative_resolution * max(
        maximum(abs, scaled_zero_eigenvalues[finite_zero_indices]),
        1.0,
    )
    nearest_scaled_zero_separation > scaled_zero_resolution || error(
        "D3 intrinsic-pair notch selected zero is not machine-resolved as a simple cofactor root.",
    )
    notch_hz = zero_candidate_frequencies_hz[selected_position]

    scaled_pole_eigenvalues = Float64.(eigvals(
        Symmetric(stiffness / angular_anchor_squared),
        Symmetric(capacitance),
    ))
    conservative_pole_frequencies_hz = Float64[
        selection_anchor_hz * sqrt(value)
        for value in scaled_pole_eigenvalues
        if isfinite(value) && value > 0
    ]
    isempty(conservative_pole_frequencies_hz) && error(
        "D3 intrinsic-pair notch conservative model exposes no finite positive poles.",
    )
    nearest_pole_separation_hz = minimum(
        abs.(conservative_pole_frequencies_hz .- notch_hz),
    )
    zero_pole_resolution_hz = machine_relative_resolution * max(
        notch_hz,
        maximum(conservative_pole_frequencies_hz),
    )
    nearest_pole_separation_hz > zero_pole_resolution_hz || error(
        "D3 intrinsic-pair notch zero is machine-degenerate with a conservative pole.",
    )
    z21 = _d3_intrinsic_pair_z21(model, notch_hz)
    isfinite(real(z21)) && isfinite(imag(z21)) || error(
        "D3 intrinsic-pair notch Z21 evaluation is non-finite.",
    )
    tolerances = (
        real=Float64(max_abs_real_z21_ohm),
        imag=Float64(max_abs_imag_z21_ohm),
        complex=Float64(max_abs_complex_z21_ohm),
    )
    all(isfinite, values(tolerances)) || error(
        "D3 intrinsic-pair Z21 residual tolerances must be finite.",
    )
    legacy_solver_controls = (
        absolute_frequency_tolerance_hz=Float64(frequency_tolerance_hz),
        relative_frequency_tolerance=Float64(relative_frequency_tolerance),
        max_iterations=Int(max_iterations),
    )
    all(isfinite, (
        legacy_solver_controls.absolute_frequency_tolerance_hz,
        legacy_solver_controls.relative_frequency_tolerance,
    )) || error(
        "D3 intrinsic-pair legacy solver controls must be finite.",
    )
    residuals_ohm = (
        real=abs(real(z21)),
        imag=abs(imag(z21)),
        complex=abs(z21),
    )
    residual_comparisons = (
        real=abs(real(z21)) <= tolerances.real,
        imag=abs(imag(z21)) <= tolerances.imag,
        complex=abs(z21) <= tolerances.complex,
    )
    return (
        quantity=:f_n_rp_on,
        frequency_hz=notch_hz,
        z21_ohm=z21,
        frequency_bracket_hz=bracket,
        selection_anchor_hz=selection_anchor_hz,
        selected_zero_inside_bracket=
            bracket[1] <= notch_hz <= bracket[2],
        cofactor_indices=(
            removed_input_row=input_index,
            removed_output_column=output_index,
            retained_rows=rows,
            retained_columns=columns,
        ),
        zero_candidates=(
            scaled_squared_frequency_eigenvalues=scaled_zero_eigenvalues,
            physical_candidate_indices=zero_candidate_indices,
            frequencies_hz=zero_candidate_frequencies_hz,
            selected_position=selected_position,
            selected_generalized_eigenvalue=
                scaled_zero_eigenvalues[selected_zero_index],
            nearest_finite_spectrum_separation=
                nearest_scaled_zero_separation,
            finite_spectrum_resolution=scaled_zero_resolution,
            selection_distances_hz=selection_distances_hz,
            selection_distance_resolution_hz=
                selection_distance_resolution_hz,
        ),
        conservative_poles=(
            scaled_squared_frequency_eigenvalues=scaled_pole_eigenvalues,
            frequencies_hz=conservative_pole_frequencies_hz,
            nearest_selected_zero_separation_hz=
                nearest_pole_separation_hz,
            zero_pole_resolution_hz=zero_pole_resolution_hz,
        ),
        machine_validation=(
            machine_relative_resolution=machine_relative_resolution,
            capacitance_positive_definite=true,
            stiffness_minimum_eigenvalue=minimum(stiffness_eigenvalues),
            stiffness_psd_absolute_tolerance=
                machine_relative_resolution * stiffness_scale,
        ),
        legacy_solver_controls=legacy_solver_controls,
        residual_tolerances_ohm=tolerances,
        residuals_ohm=residuals_ohm,
        residual_comparisons=residual_comparisons,
        numeric_control_disposition=(
            frequency_interval=:selection_seed_only,
            legacy_solver_controls=:proposed_inactive,
            residual_tolerances=:proposed_inactive,
            role=:diagnostic_only,
        ),
        model=model,
        provenance=(
            contract_id="d3-intrinsic-pair-rp-on-z21-zero.v1",
            circuit_plan_sha256=model.provenance.circuit_plan_sha256,
            coupling_state=:rp_on,
            excluded_subsystems=(:qubit, :c0r, :idc, :feedline),
            numerical_authority=
                :cofactor_generalized_eigenzero_plus_exact_linear_terminal_impedance,
            hb_ptc_role=:optional_cross_check,
        ),
    )
end

"""
Extract the authoritative intrinsic-pair RP-on notch by selecting the unique
machine-real cofactor transmission zero nearest the supplied interval midpoint.
The interval is selection provenance, not an eligibility boundary. The exact
conservative Z21 evaluation is independent of the 50-ohm normalization used to
declare the two observation ports.
"""
function d3_intrinsic_pair_notch_frequency(built, frequency_bracket_hz; kwargs...)
    model = d3_auxiliary_compiled_port_model(
        built;
        contract_id="d3-intrinsic-pair-rp-on-z21-zero.v1",
    )
    return _d3_intrinsic_pair_notch_from_model(
        model,
        frequency_bracket_hz;
        kwargs...,
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
