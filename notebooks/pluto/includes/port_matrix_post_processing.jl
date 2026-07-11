"""
Frequency-indexed port-matrix post-processing used by Workbench notebooks.

Canonical semantics:
- https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/network-trace-views.qmd
- https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/simulation/port-reference-impedance-semantics.qmd
- https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/simulation/port-termination-compensation.qmd
- https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/admittance-coordinate-transforms.qmd
- https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/numerical-methods/schur-complement-kron-reduction.qmd

This module owns implementation mechanics, not the reusable physical meaning.
The coordinate-transform implementation uses transpose semantics and therefore
supports the canonical real-valued transform contract.
"""
module PortMatrixPostProcessing

using LinearAlgebra

export PortMatrixStack,
    mode_trace_label,
    matrix_stack_from_traces,
    zero_mode_z_matrix_stack,
    zero_mode_y_matrix_stack,
    compiled_port_shunt_evidence,
    apply_port_termination_compensation,
    invert_port_matrix_stack,
    common_differential_transform,
    apply_coordinate_transform,
    kron_reduce

"""
    PortMatrixStack

Own a frequency-indexed impedance or admittance matrix together with unique
coordinate labels and source lineage. This container enforces shape and
quantity invariants; it does not infer port, reference-plane, or loading
semantics.
"""
struct PortMatrixStack
    labels::Vector{String}
    frequencies_hz::Vector{Float64}
    values::Array{ComplexF64,3}
    quantity_kind::Symbol
    source_kind::Symbol

    function PortMatrixStack(labels, frequencies_hz, values, quantity_kind, source_kind)
        isempty(labels) && error("labels must contain at least one entry.")
        length(unique(labels)) == length(labels) || error("labels must be unique.")
        isempty(frequencies_hz) && error("frequencies_hz must contain at least one point.")
        quantity_kind in (:impedance, :admittance) ||
            error("quantity_kind must be :impedance or :admittance.")
        ndims(values) == 3 || error("values must be a three-dimensional matrix stack.")
        size(values, 1) == length(labels) || error("values first dimension must match labels length.")
        size(values, 2) == length(labels) || error("values second dimension must match labels length.")
        size(values, 3) == length(frequencies_hz) ||
            error("values third dimension must match frequencies_hz length.")
        return new(labels, frequencies_hz, values, quantity_kind, source_kind)
    end
end

function PortMatrixStack(; labels, frequencies_hz, values, quantity_kind, source_kind)
    label_values = String.(collect(labels))
    frequency_values = Float64.(collect(frequencies_hz))
    matrix_values = ComplexF64.(values)

    return PortMatrixStack(
        label_values,
        frequency_values,
        matrix_values,
        quantity_kind,
        Symbol(source_kind),
    )
end

function mode_trace_label(; outputmode=(0,), outputport::Integer, inputmode=(0,), inputport::Integer)
    output_token = _mode_token(outputmode)
    input_token = _mode_token(inputmode)
    return "om=$(output_token)|op=$(Int(outputport))|im=$(input_token)|ip=$(Int(inputport))"
end

function matrix_stack_from_traces(
    traces::AbstractDict,
    frequencies_hz;
    ports,
    outputmode=(0,),
    inputmode=(0,),
    quantity_kind,
    source_kind=:trace,
)
    selected_ports = _normalize_ports(ports)
    frequency_values = Float64.(collect(frequencies_hz))
    isempty(frequency_values) && error("frequencies_hz must contain at least one point.")

    values = Array{ComplexF64,3}(undef, length(selected_ports), length(selected_ports), length(frequency_values))
    for (output_index, output_port) in pairs(selected_ports)
        for (input_index, input_port) in pairs(selected_ports)
            label = mode_trace_label(
                outputmode=outputmode,
                outputport=output_port,
                inputmode=inputmode,
                inputport=input_port,
            )
            trace = _required_trace(traces, label)
            length(trace) == length(frequency_values) ||
                error("Trace $(label) length does not match frequencies_hz length.")
            values[output_index, input_index, :] = ComplexF64.(trace)
        end
    end

    return PortMatrixStack(
        labels=string.(selected_ports),
        frequencies_hz=frequency_values,
        values=values,
        quantity_kind=quantity_kind,
        source_kind=source_kind,
    )
end

function zero_mode_z_matrix_stack(result; ports=nothing)
    selected_ports = _result_ports(result, ports)
    return matrix_stack_from_traces(
        _trace_family(result, :z_parameter_mode),
        result.frequencies_hz;
        ports=selected_ports,
        quantity_kind=:impedance,
        source_kind=:z_trace,
    )
end

function zero_mode_y_matrix_stack(result; ports=nothing)
    selected_ports = _result_ports(result, ports)
    z_stack = zero_mode_z_matrix_stack(result; ports=selected_ports)
    return PortMatrixStack(
        labels=z_stack.labels,
        frequencies_hz=z_stack.frequencies_hz,
        values=_invert_stack(z_stack.values, "Z->Y conversion"),
        quantity_kind=:admittance,
        source_kind=:z_inverse,
    )
end

"""
    compiled_port_shunt_evidence(compiled; port_indices)

Prove that each requested compiled port has exactly one colocated
`R_port_<index>` shunt and exactly one logical `port_map` identity. The returned
resistances are the only values accepted by port-termination compensation.
"""
function compiled_port_shunt_evidence(compiled; port_indices)
    selected_ports = _normalize_ports(port_indices)
    all(>(0), selected_ports) || error("port_indices must contain positive port indices.")

    for field in (:netlist, :component_values, :port_map)
        hasproperty(compiled, field) || error("compiled circuit does not contain :$(field).")
    end
    netlist = getproperty(compiled, :netlist)
    component_values = getproperty(compiled, :component_values)
    port_map = getproperty(compiled, :port_map)
    netlist isa AbstractVector || error("compiled.netlist must be a vector.")
    component_values isa AbstractDict || error("compiled.component_values must be a dictionary.")
    port_map isa AbstractDict || error("compiled.port_map must be a dictionary.")

    mapped_port_ids = Dict{Int,Vector{Any}}()
    for (port_id, mapping) in pairs(port_map)
        hasproperty(mapping, :index) || error("compiled.port_map entry $(port_id) does not contain an index.")
        mapped_index = getproperty(mapping, :index)
        mapped_index isa Integer || error("compiled.port_map entry $(port_id) has a non-integer index.")
        push!(get!(mapped_port_ids, Int(mapped_index), Any[]), port_id)
    end

    evidence = Dict{Int,NamedTuple}()
    for port_index in selected_ports
        port_name = "P$(port_index)"
        resistor_id = "R_port_$(port_index)"
        resistor_ref = Symbol(resistor_id)
        port_rows = [row for row in netlist if _row_has_name(row, port_name)]
        resistor_rows = [row for row in netlist if _row_has_name(row, resistor_id)]
        length(port_rows) == 1 ||
            error("Compiled port $(port_index) requires exactly one $(port_name) row; found $(length(port_rows)).")
        length(resistor_rows) == 1 ||
            error("Compiled port $(port_index) requires exactly one $(resistor_id) row; found $(length(resistor_rows)).")

        port_row = only(port_rows)
        resistor_row = only(resistor_rows)
        length(port_row) == 4 || error("Compiled $(port_name) row must contain four fields.")
        length(resistor_row) == 4 || error("Compiled $(resistor_id) row must contain four fields.")
        port_row[4] isa Integer && Int(port_row[4]) == port_index ||
            error("Compiled $(port_name) row does not declare port index $(port_index).")
        port_row[2:3] == resistor_row[2:3] ||
            error("Compiled $(port_name) and $(resistor_id) rows are not on the same branch.")
        port_row[3] == "0" || error("Compiled $(port_name) and $(resistor_id) branch must terminate at ground node 0.")
        resistor_row[4] == resistor_ref ||
            error("Compiled $(resistor_id) row must reference :$(resistor_id).")
        haskey(component_values, resistor_ref) ||
            error("compiled.component_values does not contain :$(resistor_id).")

        raw_resistance = component_values[resistor_ref]
        raw_resistance isa Real || error("Compiled $(resistor_id) resistance must be real-valued.")
        resistance_ohm = Float64(raw_resistance)
        isfinite(resistance_ohm) && resistance_ohm > 0 ||
            error("Compiled $(resistor_id) resistance must be positive and finite.")

        port_ids = get(mapped_port_ids, port_index, Any[])
        length(port_ids) == 1 ||
            error("Compiled port $(port_index) requires exactly one logical port_map identity; found $(length(port_ids)).")
        evidence[port_index] = (
            port_id=only(port_ids),
            port_index=port_index,
            node=port_row[2],
            port_row=port_row,
            resistor_id=resistor_id,
            resistor_row=resistor_row,
            resistance_ohm=resistance_ohm,
        )
    end
    return evidence
end

"""
    apply_port_termination_compensation(
        stack,
        compiled;
        compensate_port_indices,
        removal_intent,
    )

Remove explicitly intended compiled port shunts from a raw admittance matrix
obtained by inverting the solver's Z traces. Arbitrary resistance inputs and
already-transformed matrices are rejected.
"""
function apply_port_termination_compensation(
    stack::PortMatrixStack,
    compiled;
    compensate_port_indices,
    removal_intent::Symbol,
)
    _require_admittance(stack, "Port-termination compensation")
    stack.source_kind == :z_inverse ||
        error("Port-termination compensation requires a raw :z_inverse admittance stack.")
    isempty(string(removal_intent)) && error("removal_intent must be a non-empty Symbol.")
    evidence = compiled_port_shunt_evidence(compiled; port_indices=compensate_port_indices)

    values = copy(stack.values)
    for port_index in keys(evidence)
        label_indices = findall(==(string(port_index)), stack.labels)
        length(label_indices) == 1 || error(
            "Port $(port_index) requires exactly one matching matrix label; found $(length(label_indices)).",
        )
        label_index = only(label_indices)
        values[label_index, label_index, :] .-= ComplexF64(1 / evidence[port_index].resistance_ohm)
    end

    return PortMatrixStack(
        labels=stack.labels,
        frequencies_hz=stack.frequencies_hz,
        values=values,
        quantity_kind=:admittance,
        source_kind=Symbol("ptc_", string(stack.source_kind)),
    )
end

function invert_port_matrix_stack(stack::PortMatrixStack; source_kind=:matrix_inverse)
    return PortMatrixStack(
        labels=stack.labels,
        frequencies_hz=stack.frequencies_hz,
        values=_invert_stack(stack.values, "$(stack.source_kind) inversion"),
        quantity_kind=stack.quantity_kind == :impedance ? :admittance : :impedance,
        source_kind=source_kind,
    )
end

function common_differential_transform(
    dimension::Integer,
    first_index::Integer,
    second_index::Integer;
    alpha::Real=0.5,
    beta::Real=0.5,
)
    dimension_value = Int(dimension)
    first = Int(first_index)
    second = Int(second_index)

    dimension_value >= 2 ||
        error("Common/differential transform requires at least two dimensions.")
    first != second || error("Common/differential transform requires two distinct indices.")
    1 <= first <= dimension_value || error("first_index is out of range.")
    1 <= second <= dimension_value || error("second_index is out of range.")
    abs(Float64(alpha) + Float64(beta) - 1.0) <= 1e-6 ||
        error("alpha + beta must equal 1.")

    transform = Matrix{ComplexF64}(I, dimension_value, dimension_value)
    transform[first, :] .= 0
    transform[first, first] = ComplexF64(alpha)
    transform[first, second] = ComplexF64(beta)
    transform[second, :] .= 0
    transform[second, first] = 1 + 0im
    transform[second, second] = -1 + 0im
    return transform
end

"""
    apply_coordinate_transform(stack, transform_matrix; labels=nothing)

Transform an admittance stack with the real power-conjugate contract
`A^-T * Y * A^-1`. Complex, non-finite, singular, or dimensionally incompatible
coordinate matrices fail instead of selecting another power convention.
"""
function apply_coordinate_transform(stack::PortMatrixStack, transform_matrix; labels=nothing)
    _require_admittance(stack, "Coordinate transform")
    transform = ComplexF64.(transform_matrix)
    ndims(transform) == 2 || error("transform_matrix must be two-dimensional.")
    size(transform, 1) == size(transform, 2) || error("transform_matrix must be square.")
    size(transform, 1) == length(stack.labels) ||
        error("transform_matrix shape does not match the matrix stack dimension.")
    all(isreal, transform) ||
        error("transform_matrix must be real-valued for the inverse-transpose coordinate contract.")
    all(isfinite, transform) || error("transform_matrix must contain only finite values.")

    inverse_transform = _invert_matrix(transform, "coordinate transform matrix")
    values = Array{ComplexF64,3}(undef, size(stack.values))
    for frequency_index in axes(stack.values, 3)
        values[:, :, frequency_index] =
            transpose(inverse_transform) * stack.values[:, :, frequency_index] * inverse_transform
    end

    output_labels = isnothing(labels) ? stack.labels : String.(collect(labels))
    length(output_labels) == length(stack.labels) ||
        error("labels length must match the matrix stack dimension.")
    return PortMatrixStack(
        labels=output_labels,
        frequencies_hz=stack.frequencies_hz,
        values=values,
        quantity_kind=:admittance,
        source_kind=Symbol("coordinate_transform_", string(stack.source_kind)),
    )
end

"""
    kron_reduce(stack; keep_indices)

Eliminate unforced coordinates from an admittance stack with a Schur-complement
solve. A non-finite eliminated-block condition number fails with frequency and
coordinate context; a finite condition number is evidence for the notebook and
is not automatically approved or rejected by this helper.
"""
function kron_reduce(stack::PortMatrixStack; keep_indices)
    _require_admittance(stack, "Kron reduction")
    keep = Int.(collect(keep_indices))
    isempty(keep) && error("Kron reduction requires at least one kept index.")
    length(unique(keep)) == length(keep) ||
        error("Kron keep_indices must not contain duplicates.")

    dimension = length(stack.labels)
    all(index -> 1 <= index <= dimension, keep) ||
        error("Kron keep_indices are out of range.")
    keep_set = Set(keep)
    drop = [index for index in 1:dimension if !(index in keep_set)]

    values = Array{ComplexF64,3}(undef, length(keep), length(keep), length(stack.frequencies_hz))
    for frequency_index in axes(stack.values, 3)
        y = stack.values[:, :, frequency_index]
        y_kk = y[keep, keep]
        if isempty(drop)
            values[:, :, frequency_index] = y_kk
            continue
        end

        y_kd = y[keep, drop]
        y_dd = y[drop, drop]
        y_dk = y[drop, keep]
        context =
            "Kron reduction at frequency index $(frequency_index) " *
            "($(stack.frequencies_hz[frequency_index]) Hz) for dropped labels " *
            "[$(join(stack.labels[drop], ", "))]"
        condition_number = try
            cond(y_dd)
        catch
            NaN
        end
        isfinite(condition_number) || error(
            "$(context): measured condition number $(condition_number) is non-finite.",
        )
        values[:, :, frequency_index] = y_kk - y_kd * _solve_matrix(y_dd, y_dk, context)
    end

    return PortMatrixStack(
        labels=stack.labels[keep],
        frequencies_hz=stack.frequencies_hz,
        values=values,
        quantity_kind=:admittance,
        source_kind=Symbol("kron_reduction_", string(stack.source_kind)),
    )
end

function _mode_token(mode)
    return join(string.(Int.(collect(mode))), ",")
end

function _normalize_ports(ports)
    selected_ports = Int.(collect(ports))
    isempty(selected_ports) && error("ports must contain at least one port.")
    length(unique(selected_ports)) == length(selected_ports) ||
        error("ports must not contain duplicates.")
    return selected_ports
end

function _result_ports(result, ports)
    if isnothing(ports)
        trace_ports = get(result.traces, :portnumbers, nothing)
        isnothing(trace_ports) &&
            error("ports must be provided when result.traces does not contain :portnumbers.")
        return _normalize_ports(trace_ports)
    end

    return _normalize_ports(ports)
end

function _trace_family(result, family::Symbol)
    traces = get(result.traces, family, nothing)
    traces isa AbstractDict || error("result.traces does not contain :$(family).")
    return traces
end

function _required_trace(traces::AbstractDict, label::String)
    haskey(traces, label) ||
        error("Trace $(label) is not available. Available labels: $(_available_labels(traces))")
    return traces[label]
end

function _row_has_name(row, name::String)
    return row isa Tuple && !isempty(row) && first(row) == name
end

function _require_admittance(stack::PortMatrixStack, operation::String)
    stack.quantity_kind == :admittance ||
        error("$(operation) requires an admittance matrix stack; received $(stack.quantity_kind).")
    return nothing
end

function _available_labels(traces::AbstractDict)
    return join(sort(string.(collect(keys(traces)))), ", ")
end

function _invert_stack(values, context::String)
    inverted = Array{ComplexF64,3}(undef, size(values))
    for frequency_index in axes(values, 3)
        inverted[:, :, frequency_index] =
            _invert_matrix(values[:, :, frequency_index], "$(context) at frequency index $(frequency_index)")
    end
    return inverted
end

function _invert_matrix(matrix, context::String)
    try
        return matrix \ Matrix{ComplexF64}(I, size(matrix, 1), size(matrix, 1))
    catch err
        error("Matrix inversion failed in $(context): $(sprint(showerror, err))")
    end
end

function _solve_matrix(matrix, rhs, context::String)
    try
        return matrix \ rhs
    catch err
        error("Matrix solve failed in $(context): $(sprint(showerror, err))")
    end
end

end
