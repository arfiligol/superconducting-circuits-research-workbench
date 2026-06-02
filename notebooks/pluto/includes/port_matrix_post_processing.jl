module PortMatrixPostProcessing

using LinearAlgebra

export PortMatrixStack,
    mode_trace_label,
    matrix_stack_from_traces,
    zero_mode_z_matrix_stack,
    zero_mode_y_matrix_stack,
    apply_port_termination_compensation,
    common_differential_transform,
    apply_coordinate_transform,
    kron_reduce

struct PortMatrixStack
    labels::Vector{String}
    frequencies_hz::Vector{Float64}
    values::Array{ComplexF64,3}
    source_kind::Symbol
end

function PortMatrixStack(; labels, frequencies_hz, values, source_kind)
    label_values = String.(collect(labels))
    frequency_values = Float64.(collect(frequencies_hz))
    matrix_values = ComplexF64.(values)

    isempty(label_values) && error("labels must contain at least one entry.")
    isempty(frequency_values) && error("frequencies_hz must contain at least one point.")
    ndims(matrix_values) == 3 || error("values must be a three-dimensional matrix stack.")
    size(matrix_values, 1) == length(label_values) ||
        error("values first dimension must match labels length.")
    size(matrix_values, 2) == length(label_values) ||
        error("values second dimension must match labels length.")
    size(matrix_values, 3) == length(frequency_values) ||
        error("values third dimension must match frequencies_hz length.")

    return PortMatrixStack(
        label_values,
        frequency_values,
        matrix_values,
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
        source_kind=source_kind,
    )
end

function zero_mode_z_matrix_stack(result; ports=nothing)
    selected_ports = _result_ports(result, ports)
    return matrix_stack_from_traces(
        _trace_family(result, :z_parameter_mode),
        result.frequencies_hz;
        ports=selected_ports,
        source_kind=:z_trace,
    )
end

function zero_mode_y_matrix_stack(result; ports=nothing, prefer_native::Bool=true)
    selected_ports = _result_ports(result, ports)
    if prefer_native && _has_trace_family(result, :y_parameter_mode)
        return matrix_stack_from_traces(
            _trace_family(result, :y_parameter_mode),
            result.frequencies_hz;
            ports=selected_ports,
            source_kind=:y_trace,
        )
    end

    z_stack = zero_mode_z_matrix_stack(result; ports=selected_ports)
    return PortMatrixStack(
        labels=z_stack.labels,
        frequencies_hz=z_stack.frequencies_hz,
        values=_invert_stack(z_stack.values, "Z->Y conversion"),
        source_kind=:z_inverse,
    )
end

function apply_port_termination_compensation(stack::PortMatrixStack; resistance_ohm_by_port)
    values = copy(stack.values)
    for (port, resistance) in pairs(resistance_ohm_by_port)
        port_index = Int(port)
        resistance_ohm = Float64(resistance)
        resistance_ohm > 0 || error("Port $(port_index) has non-positive termination resistance.")
        label_index = findfirst(==(string(port_index)), stack.labels)
        isnothing(label_index) &&
            error("Port $(port_index) is not present in this matrix stack.")
        values[label_index, label_index, :] .-= ComplexF64(1 / resistance_ohm)
    end

    return PortMatrixStack(
        labels=stack.labels,
        frequencies_hz=stack.frequencies_hz,
        values=values,
        source_kind=stack.source_kind,
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

function apply_coordinate_transform(stack::PortMatrixStack, transform_matrix; labels=nothing)
    transform = ComplexF64.(transform_matrix)
    ndims(transform) == 2 || error("transform_matrix must be two-dimensional.")
    size(transform, 1) == size(transform, 2) || error("transform_matrix must be square.")
    size(transform, 1) == length(stack.labels) ||
        error("transform_matrix shape does not match the matrix stack dimension.")

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
        source_kind=stack.source_kind,
    )
end

function kron_reduce(stack::PortMatrixStack; keep_indices)
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
        values[:, :, frequency_index] = y_kk - y_kd * _solve_matrix(y_dd, y_dk, "Kron reduction")
    end

    return PortMatrixStack(
        labels=stack.labels[keep],
        frequencies_hz=stack.frequencies_hz,
        values=values,
        source_kind=stack.source_kind,
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

function _has_trace_family(result, family::Symbol)
    traces = get(result.traces, family, nothing)
    return traces isa AbstractDict && !isempty(traces)
end

function _required_trace(traces::AbstractDict, label::String)
    haskey(traces, label) ||
        error("Trace $(label) is not available. Available labels: $(_available_labels(traces))")
    return traces[label]
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
