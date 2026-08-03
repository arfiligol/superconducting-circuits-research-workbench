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
Stage-3 response and pole evaluation.
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

The returned matrices preserve `model.coordinate_order`. The anchored bare
Hamiltonian retains both its number-conserving `h` block and its pairing block;
this handoff does not construct a response by dropping either sector.
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
        contract_id="d3-numerical-lagrangian-to-cqed-handoff.v2",
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
            impedance_ohm=impedance_ohm,
            charge_block_rad_s=charge_block,
            flux_block_rad_s=flux_block,
        ),
        anchored_bare_hamiltonian=(
            number_conserving_matrix_rad_s=number_conserving,
        ),
        exact=(
            pairing_matrix_rad_s=pairing,
            doubled_matrix_rad_s=doubled,
            flux_frequencies_hz=exact_flux_hz,
            doubled_frequencies_hz=exact_doubled_hz,
            doubled_free_eigenvalues_hz=doubled_free_eigenvalues_hz,
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

"""Extract Stage-2 matrix diagnostics from the coupling-on number-conserving block.

The complete Equivalent CircuitPlan owns C, K, and the q/r/p coordinate
couplings. The diagonal values are pre-downfold report-only diagnostics; the
q+feedline-downfolded effective complex roots own the Stage-2 frequency
residuals.
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
    coordinate_index = Dict(
        coordinate => index
        for (index, coordinate) in enumerate(model.coordinate_order)
    )
    all(haskey(coordinate_index, coordinate) for coordinate in (:q, :r, :p)) ||
        error("D3 Stage-2 matrix extraction requires q, r, and p coordinates.")
    h = cqed_handoff.anchored_bare_hamiltonian.number_conserving_matrix_rad_s
    q = coordinate_index[:q]
    r = coordinate_index[:r]
    p = coordinate_index[:p]
    provenance = model.provenance
    return (
        stage_id=:stage2_equivalent,
        model_family=:equivalent_exact_n,
        circuit_plan_sha256=provenance.circuit_plan_sha256,
        capacitance_sha256=provenance.capacitance_sha256,
        inverse_inductance_sha256=provenance.inverse_inductance_sha256,
        selector_sha256=provenance.selector_sha256,
        fr_circuit_h_rr_pre_downfold_report_only_hz=h[r, r] / (2π),
        fp_circuit_h_pp_pre_downfold_report_only_hz=h[p, p] / (2π),
        J_circuit_h_rp_pre_downfold_report_only_hz=abs(h[r, p]) / (2π),
        fq_circuit_h_qq_pre_downfold_report_only_hz=h[q, q] / (2π),
        operand_authority=:coupling_on_anchored_bare_number_conserving_block,
        coordinate_order=copy(model.coordinate_order),
        number_conserving_sha256=
            cqed_handoff.hashes.number_conserving_sha256,
        pairing_sha256=cqed_handoff.hashes.pairing_sha256,
        exact_doubled_sha256=cqed_handoff.hashes.doubled_sha256,
    )
end

const D3_Q_FEEDLINE_DOWNFOLDED_RP_GATE_FIELDS = (
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

function _d3_q_feedline_downfolded_rp_gate_policy(raw)
    Tuple(propertynames(raw)) == D3_Q_FEEDLINE_DOWNFOLDED_RP_GATE_FIELDS ||
        error(
            "D3 q+feedline-downfolded RP gate policy fields must be exactly $(collect(D3_Q_FEEDLINE_DOWNFOLDED_RP_GATE_FIELDS)).",
        )
    values = Base.map(D3_Q_FEEDLINE_DOWNFOLDED_RP_GATE_FIELDS) do name
        value = getproperty(raw, name)
        value isa Real || error(
            "D3 q+feedline-downfolded RP gate $(name) must be real.",
        )
        parsed = Float64(value)
        isfinite(parsed) || error(
            "D3 q+feedline-downfolded RP gate $(name) must be finite.",
        )
        parsed
    end
    policy = NamedTuple{
        D3_Q_FEEDLINE_DOWNFOLDED_RP_GATE_FIELDS,
    }(Tuple(values))
    policy.maximum_elimination_condition_number >= 1 || error(
        "D3 q+feedline-downfolded RP maximum elimination condition number must be at least one.",
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
            "D3 q+feedline-downfolded RP gate $(name) must be nonnegative.",
        )
    end
    policy.minimum_normalized_residue_slope > 0 || error(
        "D3 q+feedline-downfolded RP minimum normalized residue slope must be positive.",
    )
    return policy
end

function _d3_q_feedline_relative_error(numerator, denominator)
    scale = max(Float64(denominator), floatmin(Float64))
    return Float64(numerator) / scale
end

function _d3_q_feedline_reciprocity_error(matrix)
    return _d3_q_feedline_relative_error(
        opnorm(matrix - transpose(matrix), Inf),
        opnorm(matrix, Inf),
    )
end

function _d3_q_feedline_downfolded_rp_context(model, raw_gate_policy)
    gate_policy =
        _d3_q_feedline_downfolded_rp_gate_policy(raw_gate_policy)
    coordinate_order = Symbol.(collect(model.coordinate_order))
    coordinate_order == [:q, :r, :p, :f1, :fc, :f2] || error(
        "D3 q+feedline-downfolded RP extraction requires coordinate order [q, r, p, f1, fc, f2].",
    )
    capacitance = Matrix{Float64}(model.capacitance)
    stiffness = Matrix{Float64}(model.inverse_inductance)
    size(capacitance) == (6, 6) && size(stiffness) == (6, 6) || error(
        "D3 q+feedline-downfolded RP extraction requires 6x6 C and K matrices.",
    )
    selector = Matrix{Float64}(model.selector)
    size(selector) == (6, 2) || error(
        "D3 q+feedline-downfolded RP extraction requires a 6x2 matched-port selector.",
    )
    reference_impedance_ohm = Float64.(collect(model.reference_impedance_ohm))
    length(reference_impedance_ohm) == 2 &&
        all(value -> isfinite(value) && value > 0, reference_impedance_ohm) ||
        error(
            "D3 q+feedline-downfolded RP extraction requires two finite positive reference impedances.",
        )
    all(isfinite, capacitance) && all(isfinite, stiffness) &&
        all(isfinite, selector) || error(
        "D3 q+feedline-downfolded RP matrices must contain only finite values.",
    )
    capacitance_reciprocity =
        _d3_q_feedline_reciprocity_error(capacitance)
    stiffness_reciprocity =
        _d3_q_feedline_reciprocity_error(stiffness)
    max(capacitance_reciprocity, stiffness_reciprocity) <=
        gate_policy.maximum_relative_reciprocity_error || error(
        "D3 q+feedline-downfolded RP C/K reciprocity exceeds the caller-owned gate.",
    )
    capacitance = Matrix(Symmetric((capacitance + transpose(capacitance)) / 2))
    stiffness = Matrix(Symmetric((stiffness + transpose(stiffness)) / 2))
    isposdef(Symmetric(capacitance)) || error(
        "D3 q+feedline-downfolded RP capacitance must be positive definite.",
    )
    conductance =
        selector *
        Diagonal(1 ./ reference_impedance_ohm) *
        transpose(selector)
    conductance_reciprocity =
        _d3_q_feedline_reciprocity_error(conductance)
    conductance_reciprocity <=
        gate_policy.maximum_relative_reciprocity_error || error(
        "D3 q+feedline-downfolded RP port conductance reciprocity exceeds the caller-owned gate.",
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
        "D3 q+feedline-downfolded RP K/G passivity exceeds the caller-owned gate.",
    )
    coordinate_index = Dict(
        coordinate => index
        for (index, coordinate) in enumerate(coordinate_order)
    )
    retained_indices = [coordinate_index[:r], coordinate_index[:p]]
    eliminated_indices = [
        coordinate_index[:q],
        coordinate_index[:f1],
        coordinate_index[:fc],
        coordinate_index[:f2],
    ]
    return (
        capacitance=capacitance,
        stiffness=stiffness,
        conductance=Matrix{Float64}(conductance),
        selector=selector,
        reference_impedance_ohm=reference_impedance_ohm,
        coordinate_order=coordinate_order,
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

function _d3_q_feedline_downfolded_rp_operator(context, angular_frequency_rad_s)
    angular_frequency = ComplexF64(angular_frequency_rad_s)
    isfinite(real(angular_frequency)) && isfinite(imag(angular_frequency)) ||
        error(
            "D3 q+feedline-downfolded RP angular frequency must be finite.",
        )
    real(angular_frequency) > 0 || error(
        "D3 q+feedline-downfolded RP angular frequency must have positive real part.",
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
        "D3 q+feedline-downfolded RP eliminated block is singular or exceeds the caller-owned condition-number gate.",
    )
    eliminated_response = try
        d_ee \ d_er
    catch exception
        error(
            "D3 q+feedline-downfolded RP eliminated-block solve failed: $(sprint(showerror, exception))",
        )
    end
    all(
        value -> isfinite(real(value)) && isfinite(imag(value)),
        eliminated_response,
    ) || error(
        "D3 q+feedline-downfolded RP eliminated-block solve produced non-finite values.",
    )
    solve_residual = d_ee * eliminated_response - d_er
    relative_solve_residual = _d3_q_feedline_relative_error(
        opnorm(solve_residual, Inf),
        opnorm(d_ee, Inf) * opnorm(eliminated_response, Inf) +
        opnorm(d_er, Inf),
    )
    relative_solve_residual <=
        context.gate_policy.maximum_relative_elimination_solve_residual ||
        error(
            "D3 q+feedline-downfolded RP eliminated-block solve residual exceeds the caller-owned gate.",
        )
    eliminated_response_derivative = try
        d_ee \ (
            derivative_er -
            derivative_ee * eliminated_response
        )
    catch exception
        error(
            "D3 q+feedline-downfolded RP derivative solve failed: $(sprint(showerror, exception))",
        )
    end
    all(
        value -> isfinite(real(value)) && isfinite(imag(value)),
        eliminated_response_derivative,
    ) || error(
        "D3 q+feedline-downfolded RP derivative solve produced non-finite values.",
    )
    derivative_solve_residual =
        d_ee * eliminated_response_derivative -
        (derivative_er - derivative_ee * eliminated_response)
    relative_derivative_solve_residual = _d3_q_feedline_relative_error(
        opnorm(derivative_solve_residual, Inf),
        opnorm(d_ee, Inf) * opnorm(eliminated_response_derivative, Inf) +
        opnorm(derivative_er - derivative_ee * eliminated_response, Inf),
    )
    relative_derivative_solve_residual <=
        context.gate_policy.maximum_relative_elimination_solve_residual ||
        error(
            "D3 q+feedline-downfolded RP derivative solve residual exceeds the caller-owned gate.",
        )

    effective =
        d_rr - d_re * eliminated_response
    effective_derivative =
        derivative_rr -
        derivative_re * eliminated_response -
        d_re * eliminated_response_derivative
    reciprocity_error =
        _d3_q_feedline_reciprocity_error(effective)
    reciprocity_error <=
        context.gate_policy.maximum_relative_reciprocity_error || error(
        "D3 q+feedline-downfolded RP effective-operator reciprocity exceeds the caller-owned gate.",
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

function _d3_q_feedline_downfolded_diagonal_root(
    model,
    context,
    coordinate,
    raw_frequency_band_hz,
)
    coordinate in (:r, :p) || error(
        "D3 q+feedline-downfolded RP diagonal root supports only r or p.",
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
        "D3 q+feedline-downfolded $(coordinate) diagonal exposes $(length(candidates)) passive roots inside the caller-owned band; expected exactly one.",
    )
    pole_index = only(candidates)
    root_hz = ComplexF64(poles.frequencies_hz[pole_index])
    root_operator = _d3_q_feedline_downfolded_rp_operator(
        context,
        2π * root_hz,
    )
    retained_index = coordinate == :r ? 1 : 2
    relative_root_residual = _d3_q_feedline_relative_error(
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
        "D3 q+feedline-downfolded $(coordinate) diagonal root residual exceeds the caller-owned gate.",
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
    d3_q_feedline_downfolded_rp_metrics(
        model;
        readout_root_band_hz,
        filter_root_band_hz,
        gate_policy,
    )

Evaluate the exact coupling-on matched-open `R=(r,p)` dynamic operator after
eliminating exactly `E=(q,f1,fc,f2)`. The two diagonal complex roots and the
complex-midpoint residue-normalized exchange are one inseparable Stage-2
authority. Raw number-conserving `h` entries are not used by this operator.
"""
function d3_q_feedline_downfolded_rp_metrics(
    model;
    readout_root_band_hz,
    filter_root_band_hz,
    gate_policy,
)
    context = _d3_q_feedline_downfolded_rp_context(model, gate_policy)
    readout = _d3_q_feedline_downfolded_diagonal_root(
        model,
        context,
        :r,
        readout_root_band_hz,
    )
    filter = _d3_q_feedline_downfolded_diagonal_root(
        model,
        context,
        :p,
        filter_root_band_hz,
    )
    readout_slope = -readout.operator.effective_dynamic_stiffness_derivative[1, 1]
    filter_slope = -filter.operator.effective_dynamic_stiffness_derivative[2, 2]
    readout_normalized_slope = _d3_q_feedline_relative_error(
        abs(readout_slope * readout.angular_root_rad_s),
        readout.operator.diagonal_balance_scale[1],
    )
    filter_normalized_slope = _d3_q_feedline_relative_error(
        abs(filter_slope * filter.angular_root_rad_s),
        filter.operator.diagonal_balance_scale[2],
    )
    min(readout_normalized_slope, filter_normalized_slope) >=
        context.gate_policy.minimum_normalized_residue_slope || error(
        "D3 q+feedline-downfolded RP residue slope is below the caller-owned normalized gate.",
    )
    normalization_product = readout_slope * filter_slope
    isfinite(real(normalization_product)) &&
        isfinite(imag(normalization_product)) &&
        !iszero(normalization_product) || error(
        "D3 q+feedline-downfolded RP residue normalization is singular or non-finite.",
    )
    normalization = sqrt(normalization_product)
    isfinite(real(normalization)) && isfinite(imag(normalization)) &&
        !iszero(normalization) || error(
        "D3 q+feedline-downfolded RP principal square-root branch is undefined.",
    )
    midpoint = (readout.angular_root_rad_s + filter.angular_root_rad_s) / 2
    midpoint_operator =
        _d3_q_feedline_downfolded_rp_operator(context, midpoint)
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
    relative_coupling_spread = _d3_q_feedline_relative_error(
        maximum_pairwise_spread_rad_s,
        abs(coupling_samples.midpoint),
    )
    relative_coupling_spread <=
        context.gate_policy.maximum_relative_coupling_spread || error(
        "D3 q+feedline-downfolded RP three-point coupling spread exceeds the caller-owned gate.",
    )

    midpoint_dynamic = midpoint_operator.dynamic_stiffness
    midpoint_eliminated =
        midpoint_dynamic[context.eliminated_indices, context.eliminated_indices]
    schur_determinant =
        det(midpoint_dynamic) / det(midpoint_eliminated)
    effective_determinant =
        det(midpoint_operator.effective_dynamic_stiffness)
    all(
        value -> isfinite(real(value)) && isfinite(imag(value)),
        (schur_determinant, effective_determinant),
    ) || error(
        "D3 q+feedline-downfolded RP determinant closure produced non-finite values.",
    )
    determinant_closure_error = _d3_q_feedline_relative_error(
        abs(schur_determinant - effective_determinant),
        max(abs(schur_determinant), abs(effective_determinant)),
    )
    determinant_closure_error <=
        context.gate_policy.maximum_relative_determinant_closure_error ||
        error(
            "D3 q+feedline-downfolded RP determinant closure exceeds the caller-owned gate.",
        )

    effective_exchange = coupling_samples.midpoint
    return (
        contract_id="d3-q-feedline-downfolded-rp-effective-operator.v1",
        coupling_state=:qrp_on,
        external_port_state=:matched_open,
        retained_coordinates=[:r, :p],
        eliminated_coordinates=[:q, :f1, :fc, :f2],
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
            schur_determinant=schur_determinant,
            effective_determinant=effective_determinant,
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
            eliminated_partition=[:q, :f1, :fc, :f2],
            frequency_rank_assignment=:forbidden,
            capacitance_sha256=_d3_exact_n_matrix_sha256(
                "d3-q-feedline-rp-capacitance-f",
                context.capacitance,
            ),
            inverse_inductance_sha256=_d3_exact_n_matrix_sha256(
                "d3-q-feedline-rp-inverse-inductance-h^-1",
                context.stiffness,
            ),
            conductance_sha256=_d3_exact_n_matrix_sha256(
                "d3-q-feedline-rp-conductance-s",
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
real parts own the D3 loaded-bare frequency residuals; the imaginary parts own
the corresponding loaded-bare external linewidth diagnostics. These are not
Full-QRP hybridized poles.
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

"""
    d3_exact_open_pole_identity_continuation(
        model,
        reference_states,
        energy_metric;
        minimum_overlap,
        minimum_assignment_margin,
        cqed_handoff,
    )

Assign unique q/r/p identities to the passive positive-frequency poles of the
exact doubled open generator by a global normalized stored-energy-overlap
assignment. `reference_states` must supply q/r/p vectors already embedded in
the exact doubled `state_order`, their physical/mathematical construction,
their source-model identity, and the target-model identity of that embedding.
No frequency rank participates in the assignment.

Reference construction and embedding are intentionally caller-owned. A Stage-2
caller may, for example, supply coupling-on canonical bare-coordinate unit
vectors; this evaluator neither constructs nor requires a coupling-off model.
Both acceptance thresholds are required caller inputs, and the evaluator has
no hidden overlap gate.
"""
function d3_exact_open_pole_identity_continuation(
    model,
    reference_states,
    energy_metric;
    minimum_overlap,
    minimum_assignment_margin,
    cqed_handoff=d3_numerical_cqed_handoff(model),
)
    _d3_exact_n_require_handoff_source(
        model,
        cqed_handoff,
        "D3 exact-open pole-identity cQED handoff",
    )
    target_identity = _d3_exact_n_source_model_identity(model)
    exact = cqed_handoff.port_response.exact
    state_order = copy(exact.state_order.doubled)
    state_count = length(state_order)
    generator = Matrix{ComplexF64}(exact.open_generator_per_s)
    size(generator) == (state_count, state_count) || error(
        "D3 exact-open generator shape disagrees with its doubled state order.",
    )

    required_reference_fields = (
        :vectors,
        :state_order,
        :construction,
        :source_model_identity,
        :embedded_target_model_identity,
    )
    all(name -> hasproperty(reference_states, name), required_reference_fields) ||
        error(
            "D3 exact-open q/r/p references require vectors, state_order, construction, source_model_identity, and embedded_target_model_identity.",
        )
    collect(reference_states.state_order) == state_order || error(
        "D3 exact-open q/r/p references use a different doubled state order.",
    )
    reference_source_identity = _d3_exact_n_validate_model_identity(
        reference_states.source_model_identity,
        "D3 exact-open reference source identity",
    )
    embedded_target_identity = _d3_exact_n_validate_model_identity(
        reference_states.embedded_target_model_identity,
        "D3 exact-open reference embedding target identity",
    )
    embedded_target_identity == target_identity || error(
        "D3 exact-open q/r/p references were embedded for a different target model.",
    )
    reference_construction =
        _d3_exact_n_reference_construction(reference_states.construction)
    identities = (:q, :r, :p)
    all(name -> hasproperty(reference_states.vectors, name), identities) ||
        error("D3 exact-open reference vectors must provide q, r, and p.")

    required_metric_fields = (
        :matrix,
        :state_order,
        :construction,
        :source_model_identity,
        :matrix_sha256,
    )
    all(name -> hasproperty(energy_metric, name), required_metric_fields) ||
        error(
            "D3 exact-open energy metric requires matrix, state_order, construction, source_model_identity, and matrix_sha256.",
        )
    collect(energy_metric.state_order) == state_order || error(
        "D3 exact-open energy metric uses a different doubled state order.",
    )
    metric_source_identity = _d3_exact_n_validate_model_identity(
        energy_metric.source_model_identity,
        "D3 exact-open energy-metric source identity",
    )
    metric_source_identity == target_identity || error(
        "D3 exact-open energy metric was derived from a different target model.",
    )
    metric_construction =
        _d3_exact_n_reference_construction(energy_metric.construction)
    metric = Matrix{ComplexF64}(energy_metric.matrix)
    size(metric) == (state_count, state_count) || error(
        "D3 exact-open energy metric has the wrong shape.",
    )
    metric_hash = _d3_exact_n_complex_matrix_sha256(
        "d3-exact-open-stored-energy-metric",
        metric,
    )
    lowercase(strip(String(energy_metric.matrix_sha256))) == metric_hash ||
        error("D3 exact-open energy-metric hash does not match its matrix.")
    hermitian_scale = max(opnorm(metric, Inf), floatmin(Float64))
    maximum(abs, metric - metric') <=
        4096 * state_count * eps(Float64) * hermitian_scale || error(
        "D3 exact-open energy metric must be Hermitian.",
    )
    metric = Matrix{ComplexF64}(Hermitian((metric + metric') / 2))
    metric_spectrum = eigvals(Hermitian(metric))
    metric_scale = max(maximum(abs, metric_spectrum), floatmin(Float64))
    metric_tolerance =
        4096 * state_count * eps(Float64) * metric_scale
    minimum(metric_spectrum) >= -metric_tolerance || error(
        "D3 exact-open energy metric must be positive semidefinite.",
    )

    overlap_gate = Float64(minimum_overlap)
    margin_gate = Float64(minimum_assignment_margin)
    isfinite(overlap_gate) && 0 < overlap_gate <= 1 || error(
        "D3 exact-open minimum_overlap must be finite in (0, 1].",
    )
    isfinite(margin_gate) && 0 < margin_gate <= 1 || error(
        "D3 exact-open minimum_assignment_margin must be finite in (0, 1].",
    )

    raw_references = NamedTuple{identities}(Tuple(
        ComplexF64.(collect(getproperty(reference_states.vectors, identity)))
        for identity in identities
    ))
    all(length(vector) == state_count for vector in values(raw_references)) ||
        error("D3 exact-open reference-vector length disagrees with state order.")
    all(
        value -> isfinite(real(value)) && isfinite(imag(value)),
        Iterators.flatten(values(raw_references)),
    ) || error("D3 exact-open reference vectors contain non-finite values.")
    reference_norms = NamedTuple{identities}(Tuple(
        real(vector' * metric * vector)
        for vector in values(raw_references)
    ))
    all(value -> isfinite(value) && value > metric_tolerance, values(reference_norms)) ||
        error("D3 exact-open reference vector has non-positive stored energy.")
    references = NamedTuple{identities}(Tuple(
        vector / sqrt(norm_value)
        for (vector, norm_value) in zip(
            values(raw_references),
            values(reference_norms),
        )
    ))
    reference_matrix = hcat(values(references)...)
    reference_gram = reference_matrix' * metric * reference_matrix
    reference_gram_spectrum = eigvals(Hermitian(
        (reference_gram + reference_gram') / 2,
    ))
    reference_scale =
        max(maximum(abs, reference_gram_spectrum), floatmin(Float64))
    minimum(reference_gram_spectrum) >
        4096 * length(identities) * eps(Float64) * reference_scale || error(
        "D3 exact-open q/r/p references are not energy-linearly independent.",
    )

    opened = eigen(generator)
    raw_frequency_hz = im .* opened.values ./ (2π)
    all(
        value -> isfinite(real(value)) && isfinite(imag(value)),
        raw_frequency_hz,
    ) || error("D3 exact-open generator produced non-finite poles.")
    pole_scale_hz = max(maximum(abs, raw_frequency_hz), floatmin(Float64))
    decay_tolerance_hz =
        256 * length(raw_frequency_hz) * eps(Float64) * pole_scale_hz
    positive_frequency_raw_indices = [
        index for index in eachindex(raw_frequency_hz)
        if real(raw_frequency_hz[index]) > 0 &&
           imag(raw_frequency_hz[index]) <= decay_tolerance_hz
    ]
    positive_frequency_vectors =
        Matrix{ComplexF64}(opened.vectors[:, positive_frequency_raw_indices])
    positive_frequency_norms = Float64[
        real(
            positive_frequency_vectors[:, column]' *
            metric *
            positive_frequency_vectors[:, column],
        )
        for column in axes(positive_frequency_vectors, 2)
    ]
    all(
        value -> isfinite(value) && value >= -metric_tolerance,
        positive_frequency_norms,
    ) || error(
        "D3 exact-open positive-frequency pole has negative stored energy.",
    )
    oscillatory_columns = [
        column for column in eachindex(positive_frequency_raw_indices)
        if positive_frequency_norms[column] > metric_tolerance
    ]
    positive_raw_indices =
        positive_frequency_raw_indices[oscillatory_columns]
    pole_vectors = positive_frequency_vectors[:, oscillatory_columns]
    pole_norms = positive_frequency_norms[oscillatory_columns]
    excluded_zero_energy_raw_indices = [
        positive_frequency_raw_indices[column]
        for column in eachindex(positive_frequency_raw_indices)
        if !(column in oscillatory_columns)
    ]
    length(positive_raw_indices) >= length(identities) || error(
        "D3 exact-open generator exposes fewer than three passive positive-frequency positive-energy poles.",
    )

    overlap_matrix = zeros(Float64, length(identities), length(positive_raw_indices))
    for row in eachindex(identities), column in eachindex(positive_raw_indices)
        overlap = abs2(
            getproperty(references, identities[row])' *
            metric *
            pole_vectors[:, column],
        ) / pole_norms[column]
        isfinite(overlap) && overlap >= 0 || error(
            "D3 exact-open normalized overlap is invalid.",
        )
        overlap <= 1 + 4096 * state_count * eps(Float64) || error(
            "D3 exact-open normalized overlap exceeds its energy-metric bound.",
        )
        overlap_matrix[row, column] = min(overlap, 1.0)
    end

    assignments = NamedTuple[]
    pole_count = length(positive_raw_indices)
    for q_index in 1:pole_count
        for r_index in 1:pole_count
            r_index == q_index && continue
            for p_index in 1:pole_count
                (p_index == q_index || p_index == r_index) && continue
                indices = (q_index, r_index, p_index)
                selected = (
                    overlap_matrix[1, q_index],
                    overlap_matrix[2, r_index],
                    overlap_matrix[3, p_index],
                )
                push!(
                    assignments,
                    (
                        indices=indices,
                        selected=selected,
                        mean_score=sum(selected) / length(identities),
                    ),
                )
            end
        end
    end
    sort!(
        assignments;
        by=assignment -> (
            assignment.mean_score,
            minimum(assignment.selected),
        ),
        rev=true,
    )
    length(assignments) >= 2 || error(
        "D3 exact-open identity assignment requires at least two global assignment candidates.",
    )
    best = assignments[1]
    runner_up = assignments[2]
    selected_overlaps =
        NamedTuple{identities}(Tuple(best.selected))
    minimum_selected_overlap = minimum(best.selected)
    assignment_margin = best.mean_score - runner_up.mean_score
    minimum_selected_overlap >= overlap_gate || error(
        "D3 exact-open q/r/p identity overlap is below the caller-declared gate.",
    )
    assignment_margin >= margin_gate || error(
        "D3 exact-open q/r/p identity assignment is ambiguous under the caller-declared margin.",
    )

    identity_assignment =
        NamedTuple{identities}(Tuple(best.indices))
    raw_state_assignment = NamedTuple{identities}(Tuple(
        positive_raw_indices[index] for index in best.indices
    ))
    pole_frequencies_hz =
        ComplexF64.(raw_frequency_hz[positive_raw_indices])
    pole_linewidths_hz =
        Float64.(max.(-2 .* imag.(pole_frequencies_hz), 0.0))
    poles = (
        frequencies_hz=pole_frequencies_hz,
        linewidths_hz=pole_linewidths_hz,
        raw_state_indices=positive_raw_indices,
        raw_eigenvalues_per_s=
            ComplexF64.(opened.values[positive_raw_indices]),
    )
    linewidth_lc =
        d3_linewidth_lc_from_identity_assignment(
            poles,
            identity_assignment,
        )
    reference_hashes = NamedTuple{identities}(Tuple(
        _d3_exact_n_complex_matrix_sha256(
            "d3-exact-open-reference-$(identity)",
            reshape(getproperty(references, identity), :, 1),
        )
        for identity in identities
    ))
    return (
        contract_id="d3-exact-open-qrp-identity-continuation.v1",
        identities=identities,
        state_order=state_order,
        positive_poles=poles,
        excluded_zero_energy_raw_state_indices=
            excluded_zero_energy_raw_indices,
        overlap_matrix=overlap_matrix,
        overlap_column_raw_state_indices=positive_raw_indices,
        assignment=(
            pole_indices=identity_assignment,
            raw_state_indices=raw_state_assignment,
            selected_overlaps=selected_overlaps,
            minimum_selected_overlap=minimum_selected_overlap,
            best_mean_score=best.mean_score,
            runner_up_mean_score=runner_up.mean_score,
            assignment_margin=assignment_margin,
            minimum_overlap=overlap_gate,
            minimum_assignment_margin=margin_gate,
        ),
        energy_metric=(
            construction=metric_construction,
            matrix_sha256=metric_hash,
            source_model_identity=metric_source_identity,
        ),
        references=(
            construction=reference_construction,
            source_model_identity=reference_source_identity,
            embedded_target_model_identity=embedded_target_identity,
            vector_sha256=reference_hashes,
            energy_gram=reference_gram,
        ),
        linewidth_lc=linewidth_lc,
        provenance=(
            numerical_authority=:exact_doubled_open_generator,
            identity_rule=:global_normalized_stored_energy_overlap,
            frequency_rank_assignment=:forbidden,
            source_model_identity=target_identity,
            exact_open_generator_sha256=
                cqed_handoff.hashes.exact_open_generator_sha256,
        ),
    )
end

function _d3_exact_n_metric_projector(
    metric,
    state_indices,
    metric_tolerance,
)
    gram = Matrix{ComplexF64}(Hermitian(
        (
            metric[state_indices, state_indices] +
            metric[state_indices, state_indices]'
        ) / 2,
    ))
    decomposition = eigen(Hermitian(gram))
    scale = max(maximum(abs, decomposition.values), floatmin(Float64))
    tolerance = max(
        Float64(metric_tolerance),
        4096 * length(decomposition.values) * eps(Float64) * scale,
    )
    retained = findall(value -> value > tolerance, decomposition.values)
    !isempty(retained) || error(
        "D3 subsystem stored-energy subspace has no positive-energy direction.",
    )
    inverse_gram =
        decomposition.vectors[:, retained] *
        Diagonal(1 ./ decomposition.values[retained]) *
        decomposition.vectors[:, retained]'
    return (
        state_indices=state_indices,
        inverse_gram=inverse_gram,
        rank=length(retained),
        gram_sha256=_d3_exact_n_complex_matrix_sha256(
            "d3-subsystem-energy-gram",
            gram,
        ),
    )
end

function _d3_exact_n_apply_metric_projector(state, metric, projector)
    coefficients =
        projector.inverse_gram *
        (metric * state)[projector.state_indices]
    projected = zeros(ComplexF64, length(state))
    projected[projector.state_indices] = coefficients
    return projected
end

"""
    d3_exact_open_subsystem_energy_participation_assignment(
        model,
        partition;
        pole_frequency_band_hz,
        minimum_participation,
        minimum_assignment_margin,
        cqed_handoff,
    )

Assign q/r/p identities directly from one coupling-on exact-open candidate.
The caller supplies a disjoint, exhaustive physical-coordinate partition
`(q, r, p, feedline)`. Exact-open eigenvectors are transformed back to
`(Phi, Phidot)`, and each subsystem score is the normalized stored energy of
the full-metric orthogonal projection onto that typed physical subspace.

The q/r/p assignment maximizes the global mean participation subject to
unique poles inside the required caller-owned frequency band. The band is a
candidate-set boundary, not a frequency-rank rule. Frequency rank and
coupling-off reference models are forbidden. The frequency band and both
identity gates are required caller-owned inputs.
"""
function d3_exact_open_subsystem_energy_participation_assignment(
    model,
    partition;
    pole_frequency_band_hz,
    minimum_participation,
    minimum_assignment_margin,
    cqed_handoff=d3_numerical_cqed_handoff(model),
)
    _d3_exact_n_require_handoff_source(
        model,
        cqed_handoff,
        "D3 exact-open subsystem-participation cQED handoff",
    )
    subsystems = (:q, :r, :p, :feedline)
    Tuple(propertynames(partition)) == subsystems || error(
        "D3 physical-coordinate partition fields must be exactly q, r, p, feedline.",
    )
    coordinate_order = copy(model.coordinate_order)
    dimension = length(coordinate_order)
    typed_indices = NamedTuple{subsystems}(Tuple(
        begin
            raw = collect(getproperty(partition, subsystem))
            !isempty(raw) || error(
                "D3 $(subsystem) physical-coordinate partition must not be empty.",
            )
            all(value -> value isa Integer, raw) || error(
                "D3 $(subsystem) physical-coordinate indices must be integers.",
            )
            Int.(raw)
        end
        for subsystem in subsystems
    ))
    flattened = collect(Iterators.flatten(values(typed_indices)))
    sort(flattened) == collect(1:dimension) &&
        length(unique(flattened)) == dimension || error(
        "D3 q/r/p/feedline physical-coordinate partition must be disjoint and exhaustive.",
    )

    participation_gate = Float64(minimum_participation)
    margin_gate = Float64(minimum_assignment_margin)
    frequency_band_hz = Float64.(collect(pole_frequency_band_hz))
    length(frequency_band_hz) == 2 &&
        all(isfinite, frequency_band_hz) &&
        0 < frequency_band_hz[1] < frequency_band_hz[2] || error(
        "D3 exact-open pole frequency band must contain two finite increasing positive values.",
    )
    isfinite(participation_gate) && 0 < participation_gate <= 1 || error(
        "D3 exact-open minimum_participation must be finite in (0, 1].",
    )
    isfinite(margin_gate) && 0 < margin_gate <= 1 || error(
        "D3 exact-open minimum_assignment_margin must be finite in (0, 1].",
    )

    capacitance = Matrix{Float64}(model.capacitance)
    stiffness = Matrix{Float64}(model.inverse_inductance)
    size(capacitance) == size(stiffness) == (dimension, dimension) || error(
        "D3 exact-open subsystem participation requires dimensionally consistent C/K matrices.",
    )
    zero_block = zeros(Float64, dimension, dimension)
    stored_energy_metric = [
        stiffness zero_block
        zero_block capacitance
    ]
    metric_spectrum = eigvals(Symmetric(stored_energy_metric))
    metric_scale = max(maximum(abs, metric_spectrum), floatmin(Float64))
    metric_tolerance =
        4096 * length(metric_spectrum) * eps(Float64) * metric_scale
    minimum(metric_spectrum) >= -metric_tolerance || error(
        "D3 flux/velocity stored-energy metric must be positive semidefinite.",
    )

    exact = cqed_handoff.port_response.exact
    generator = Matrix{ComplexF64}(exact.open_generator_per_s)
    doubled_to_flux_velocity =
        Matrix{ComplexF64}(exact.doubled_to_flux_velocity)
    state_count = 2 * dimension
    size(generator) == (state_count, state_count) &&
        size(doubled_to_flux_velocity) == (state_count, state_count) || error(
        "D3 exact-open generator or canonical transform has the wrong shape.",
    )
    opened = eigen(generator)
    raw_frequency_hz = im .* opened.values ./ (2π)
    all(
        value -> isfinite(real(value)) && isfinite(imag(value)),
        raw_frequency_hz,
    ) || error("D3 exact-open generator produced non-finite poles.")
    pole_scale_hz = max(maximum(abs, raw_frequency_hz), floatmin(Float64))
    decay_tolerance_hz =
        256 * length(raw_frequency_hz) * eps(Float64) * pole_scale_hz
    passive_positive_raw_indices = [
        index for index in eachindex(raw_frequency_hz)
        if real(raw_frequency_hz[index]) > 0 &&
           imag(raw_frequency_hz[index]) <= decay_tolerance_hz
    ]
    passive_positive_doubled_vectors =
        Matrix{ComplexF64}(
            opened.vectors[:, passive_positive_raw_indices],
        )
    passive_positive_flux_velocity_vectors =
        doubled_to_flux_velocity * passive_positive_doubled_vectors
    passive_positive_energy = Float64[
        real(
            passive_positive_flux_velocity_vectors[:, column]' *
            stored_energy_metric *
            passive_positive_flux_velocity_vectors[:, column],
        )
        for column in axes(passive_positive_flux_velocity_vectors, 2)
    ]
    all(
        value -> isfinite(value) && value >= -metric_tolerance,
        passive_positive_energy,
    ) || error("D3 passive positive-frequency pole has negative stored energy.")
    oscillatory_columns = findall(
        value -> value > metric_tolerance,
        passive_positive_energy,
    )
    positive_energy_raw_indices =
        passive_positive_raw_indices[oscillatory_columns]
    positive_energy_flux_velocity_vectors =
        passive_positive_flux_velocity_vectors[:, oscillatory_columns]
    positive_energy = passive_positive_energy[oscillatory_columns]
    excluded_zero_energy_raw_indices = [
        passive_positive_raw_indices[column]
        for column in eachindex(passive_positive_raw_indices)
        if !(column in oscillatory_columns)
    ]
    in_band_columns = [
        column for column in eachindex(positive_energy_raw_indices)
        if frequency_band_hz[1] <=
           real(raw_frequency_hz[positive_energy_raw_indices[column]]) <=
           frequency_band_hz[2]
    ]
    in_band_column_set = Set(in_band_columns)
    out_of_band_columns = [
        column for column in eachindex(positive_energy_raw_indices)
        if !(column in in_band_column_set)
    ]
    positive_raw_indices =
        positive_energy_raw_indices[in_band_columns]
    pole_vectors_flux_velocity =
        positive_energy_flux_velocity_vectors[:, in_band_columns]
    pole_energy = positive_energy[in_band_columns]
    excluded_out_of_band_positive_energy_raw_indices =
        positive_energy_raw_indices[out_of_band_columns]
    length(positive_raw_indices) >= 3 || error(
        "D3 exact-open candidate exposes fewer than three passive positive-energy poles inside the caller-owned frequency band.",
    )

    flux_velocity_indices = NamedTuple{subsystems}(Tuple(
        vcat(
            getproperty(typed_indices, subsystem),
            dimension .+ getproperty(typed_indices, subsystem),
        )
        for subsystem in subsystems
    ))
    participation = zeros(Float64, length(subsystems), length(positive_raw_indices))
    projection_receipts = Dict{Symbol,Any}()
    for (row, subsystem) in enumerate(subsystems)
        indices = getproperty(flux_velocity_indices, subsystem)
        projector = _d3_exact_n_metric_projector(
            stored_energy_metric,
            indices,
            metric_tolerance,
        )
        projection_receipts[subsystem] = (
            physical_coordinate_indices=
                copy(getproperty(typed_indices, subsystem)),
            physical_coordinate_names=
                coordinate_order[getproperty(typed_indices, subsystem)],
            flux_velocity_state_indices=indices,
            positive_metric_rank=projector.rank,
            subspace_gram_sha256=projector.gram_sha256,
        )
        for column in eachindex(positive_raw_indices)
            projected = _d3_exact_n_apply_metric_projector(
                pole_vectors_flux_velocity[:, column],
                stored_energy_metric,
                projector,
            )
            score = real(
                projected' *
                stored_energy_metric *
                projected,
            ) / pole_energy[column]
            isfinite(score) && score >= 0 || error(
                "D3 subsystem stored-energy participation is invalid.",
            )
            score <= 1 + 4096 * state_count * eps(Float64) || error(
                "D3 subsystem stored-energy participation exceeds one.",
            )
            participation[row, column] = min(score, 1.0)
        end
    end

    assignments = NamedTuple[]
    pole_count = length(positive_raw_indices)
    for q_index in 1:pole_count
        for r_index in 1:pole_count
            r_index == q_index && continue
            for p_index in 1:pole_count
                (p_index == q_index || p_index == r_index) && continue
                indices = (q_index, r_index, p_index)
                selected = (
                    participation[1, q_index],
                    participation[2, r_index],
                    participation[3, p_index],
                )
                push!(
                    assignments,
                    (
                        indices=indices,
                        selected=selected,
                        mean_score=sum(selected) / 3,
                    ),
                )
            end
        end
    end
    sort!(
        assignments;
        by=assignment -> (
            assignment.mean_score,
            minimum(assignment.selected),
        ),
        rev=true,
    )
    length(assignments) >= 2 || error(
        "D3 subsystem pole assignment requires at least two global candidates.",
    )
    best = assignments[1]
    runner_up = assignments[2]
    selected_participation = (
        q=best.selected[1],
        r=best.selected[2],
        p=best.selected[3],
    )
    minimum_selected_participation = minimum(best.selected)
    assignment_margin = best.mean_score - runner_up.mean_score
    minimum_selected_participation >= participation_gate || error(
        "D3 q/r/p subsystem participation is below the caller-declared gate.",
    )
    assignment_margin >= margin_gate || error(
        "D3 q/r/p subsystem assignment is ambiguous under the caller-declared margin.",
    )

    identity_assignment = (
        q=best.indices[1],
        r=best.indices[2],
        p=best.indices[3],
    )
    raw_state_assignment = (
        q=positive_raw_indices[best.indices[1]],
        r=positive_raw_indices[best.indices[2]],
        p=positive_raw_indices[best.indices[3]],
    )
    pole_frequencies_hz =
        ComplexF64.(raw_frequency_hz[positive_raw_indices])
    pole_linewidths_hz =
        Float64.(max.(-2 .* imag.(pole_frequencies_hz), 0.0))
    poles = (
        frequencies_hz=pole_frequencies_hz,
        linewidths_hz=pole_linewidths_hz,
        raw_state_indices=positive_raw_indices,
        raw_eigenvalues_per_s=
            ComplexF64.(opened.values[positive_raw_indices]),
    )
    linewidth_lc = d3_linewidth_lc_from_identity_assignment(
        poles,
        identity_assignment,
    )
    membership = zeros(Float64, dimension, length(subsystems))
    for (column, subsystem) in enumerate(subsystems)
        membership[getproperty(typed_indices, subsystem), column] .= 1.0
    end
    hashes = (
        source_model_identity=_d3_exact_n_source_model_identity(model),
        exact_open_generator_sha256=
            cqed_handoff.hashes.exact_open_generator_sha256,
        stored_energy_metric_sha256=_d3_exact_n_matrix_sha256(
            "d3-flux-velocity-stored-energy-metric",
            stored_energy_metric,
        ),
        partition_membership_sha256=_d3_exact_n_matrix_sha256(
            "d3-typed-subsystem-partition",
            membership,
        ),
        subsystem_participation_sha256=_d3_exact_n_matrix_sha256(
            "d3-subsystem-energy-participation",
            participation,
        ),
        positive_pole_set_sha256=_d3_exact_n_matrix_sha256(
            "d3-in-band-positive-pole-set",
            hcat(
                real.(pole_frequencies_hz),
                imag.(pole_frequencies_hz),
                pole_linewidths_hz,
                Float64.(positive_raw_indices),
            ),
        ),
        positive_pole_flux_velocity_vectors_sha256=
            _d3_exact_n_complex_matrix_sha256(
                "d3-positive-pole-flux-velocity-vectors",
                pole_vectors_flux_velocity,
            ),
    )
    receipt = (
        contract_id="d3-exact-open-subsystem-energy-participation.v1",
        coupling_state=:qrp_on,
        source_model_identity=hashes.source_model_identity,
        pole_frequency_band_hz=copy(frequency_band_hz),
        pole_counts=(
            passive_positive=length(passive_positive_raw_indices),
            positive_energy=length(positive_energy_raw_indices),
            in_band_positive_energy=length(positive_raw_indices),
            excluded_out_of_band_positive_energy=
                length(excluded_out_of_band_positive_energy_raw_indices),
            excluded_zero_energy=length(excluded_zero_energy_raw_indices),
        ),
        in_band_positive_energy_raw_state_indices=
            copy(positive_raw_indices),
        excluded_out_of_band_positive_energy_raw_state_indices=
            copy(excluded_out_of_band_positive_energy_raw_indices),
        excluded_zero_energy_raw_state_indices=
            copy(excluded_zero_energy_raw_indices),
        assignment_raw_state_indices=raw_state_assignment,
        minimum_participation=participation_gate,
        minimum_assignment_margin=margin_gate,
        hashes=hashes,
    )
    return (
        contract_id="d3-exact-open-subsystem-energy-participation.v1",
        coupling_state=:qrp_on,
        pole_frequency_band_hz=frequency_band_hz,
        coordinate_order=coordinate_order,
        state_order=(
            doubled=copy(exact.state_order.doubled),
            flux_velocity=copy(exact.state_order.flux_velocity),
        ),
        partition=NamedTuple{subsystems}(Tuple(
            projection_receipts[subsystem] for subsystem in subsystems
        )),
        positive_poles=poles,
        excluded_zero_energy_raw_state_indices=
            excluded_zero_energy_raw_indices,
        subsystem_order=subsystems,
        subsystem_participation=participation,
        subsystem_participation_column_raw_state_indices=
            positive_raw_indices,
        per_pole_participation_sum=vec(sum(participation; dims=1)),
        assignment=(
            pole_indices=identity_assignment,
            raw_state_indices=raw_state_assignment,
            selected_participation=selected_participation,
            minimum_selected_participation=
                minimum_selected_participation,
            best_mean_score=best.mean_score,
            runner_up_mean_score=runner_up.mean_score,
            assignment_margin=assignment_margin,
            minimum_participation=participation_gate,
            minimum_assignment_margin=margin_gate,
        ),
        linewidth_lc=linewidth_lc,
        hashes=hashes,
        receipt=receipt,
        provenance=(
            numerical_authority=:coupling_on_exact_doubled_open_generator,
            identity_rule=:global_typed_subsystem_stored_energy_participation,
            subsystem_projection=:full_metric_orthogonal_projection,
            pole_candidate_scope=:caller_owned_frequency_band,
            coupling_off_reference=:forbidden,
            frequency_rank_assignment=:forbidden,
        ),
    )
end

"""
Aggregate linewidth L_C after an external identity-continuation evaluator has
assigned unique q/r/p pole indices. This function deliberately refuses
frequency-rank ownership.
"""
function d3_linewidth_lc_from_identity_assignment(poles, identity_assignment)
    required = (:q, :r, :p)
    all(name -> hasproperty(identity_assignment, name), required) || error(
        "D3 linewidth L_C identity assignment must provide q, r, and p pole indices.",
    )
    indices = Int[getproperty(identity_assignment, name) for name in required]
    length(unique(indices)) == 3 || error(
        "D3 linewidth L_C q/r/p pole indices must be unique.",
    )
    linewidths = Float64.(poles.linewidths_hz)
    all(index -> 1 <= index <= length(linewidths), indices) || error(
        "D3 linewidth L_C identity assignment contains an out-of-range pole index.",
    )
    selected = NamedTuple{required}(Tuple(linewidths[index] for index in indices))
    resonator_sum = selected.r + selected.p
    resonator_sum > 0 || error(
        "D3 linewidth L_C requires a positive r+p linewidth sum.",
    )
    return (
        quantity=:kappa_sum_qrp_on_ext_on,
        linewidth_hz=sum(values(selected)),
        per_identity_linewidth_hz=selected,
        eta_r=selected.r / resonator_sum,
        eta_p=selected.p / resonator_sum,
        excluded_positive_pole_indices=[
            index for index in eachindex(linewidths) if !(index in indices)
        ],
        provenance=(
            contract_id="d3-linewidth-lc-identity-continued-qrp-sum.v1",
            pole_scope=:qrp_three,
            feedline_like_poles=:report_only,
            frequency_rank_assignment=:forbidden,
        ),
    )
end
