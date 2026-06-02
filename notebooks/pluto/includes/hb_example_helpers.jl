module HBExampleHelpers

using LinearAlgebra

export db20,
    phase_deg,
    mode_label,
    mode_trace,
    zero_mode_s,
    zero_mode_z,
    zero_mode_z_matrix,
    zero_mode_y_matrix

db20(values) = 20 .* log10.(abs.(values))
phase_deg(values) = rad2deg.(angle.(values))

function _mode_token(mode)
    return join(string.(Int.(collect(mode))), ",")
end

function mode_label(; outputmode=(0,), outputport::Integer, inputmode=(0,), inputport::Integer)
    output_token = _mode_token(outputmode)
    input_token = _mode_token(inputmode)
    return "om=$(output_token)|op=$(Int(outputport))|im=$(input_token)|ip=$(Int(inputport))"
end

mode_label(outputmode, outputport::Integer, inputmode, inputport::Integer) =
    mode_label(; outputmode=outputmode, outputport=outputport, inputmode=inputmode, inputport=inputport)

function _available_labels(traces)
    return join(sort(string.(collect(keys(traces)))), ", ")
end

function _trace_family(result, family::Symbol)
    traces = get(result.traces, family, nothing)
    traces isa AbstractDict || error("result.traces does not contain :$(family).")
    return traces
end

function _trace_value(result, family::Symbol, label::String)
    traces = _trace_family(result, family)
    haskey(traces, label) ||
        error(
            "result.traces[:$(family)] does not contain $(label). Available labels: $(_available_labels(traces))",
        )
    return traces[label]
end

function zero_mode_s(result, output_port::Integer, input_port::Integer)
    return _trace_value(result, :zero_mode_s, "S$(Int(output_port))$(Int(input_port))")
end

function mode_trace(
    result,
    family::Symbol;
    outputmode=(0,),
    outputport::Integer,
    inputmode=(0,),
    inputport::Integer,
)
    label = mode_label(
        outputmode=outputmode,
        outputport=outputport,
        inputmode=inputmode,
        inputport=inputport,
    )
    return _trace_value(result, family, label)
end

function zero_mode_z(result, output_port::Integer, input_port::Integer)
    return mode_trace(
        result,
        :z_parameter_mode;
        outputmode=(0,),
        outputport=output_port,
        inputmode=(0,),
        inputport=input_port,
    )
end

function _matrix_ports(result, ports)
    if isnothing(ports)
        trace_ports = get(result.traces, :portnumbers, nothing)
        isnothing(trace_ports) &&
            error("ports must be provided when result.traces does not contain :portnumbers.")
        return Int.(collect(trace_ports))
    end

    selected_ports = Int.(collect(ports))
    isempty(selected_ports) && error("ports must contain at least one port.")
    return selected_ports
end

function _trace_length(trace, label::String)
    try
        return length(trace)
    catch err
        error("Trace $(label) does not have a usable length: $(sprint(showerror, err))")
    end
end

function zero_mode_z_matrix(result; ports=nothing)
    selected_ports = _matrix_ports(result, ports)
    traces = _trace_family(result, :z_parameter_mode)
    frequencies_hz = collect(Float64.(result.frequencies_hz))
    point_count = length(frequencies_hz)
    matrices = Array{ComplexF64,3}(undef, length(selected_ports), length(selected_ports), point_count)

    for (output_index, output_port) in pairs(selected_ports)
        for (input_index, input_port) in pairs(selected_ports)
            label = mode_label(; outputport=output_port, inputport=input_port)
            trace = get(traces, label, nothing)
            isnothing(trace) &&
                error(
                    "result.traces[:z_parameter_mode] does not contain $(label). Available labels: $(_available_labels(traces))",
                )
            _trace_length(trace, label) == point_count ||
                error("Trace $(label) length does not match result.frequencies_hz length.")
            matrices[output_index, input_index, :] = ComplexF64.(trace)
        end
    end

    return (
        ports=selected_ports,
        frequencies_hz=frequencies_hz,
        values=matrices,
    )
end

function zero_mode_y_matrix(result; ports=nothing)
    z = zero_mode_z_matrix(result; ports=ports)
    port_count = length(z.ports)
    point_count = length(z.frequencies_hz)
    matrices = Array{ComplexF64,3}(undef, port_count, port_count, point_count)
    status = Vector{
        NamedTuple{(:index, :frequency_hz, :ok, :reason),Tuple{Int,Float64,Bool,String}}
    }(undef, point_count)

    for point_index in 1:point_count
        z_at_frequency = z.values[:, :, point_index]
        if !all(isfinite, z_at_frequency)
            error(
                "Z matrix contains non-finite values at frequency $(z.frequencies_hz[point_index]) Hz.",
            )
        end

        try
            matrices[:, :, point_index] = inv(z_at_frequency)
            status[point_index] = (
                index=point_index,
                frequency_hz=z.frequencies_hz[point_index],
                ok=true,
                reason="",
            )
        catch err
            if err isa SingularException
                error(
                    "Z matrix is singular at frequency $(z.frequencies_hz[point_index]) Hz.",
                )
            else
                rethrow()
            end
        end
    end

    return (
        ports=z.ports,
        frequencies_hz=z.frequencies_hz,
        values=matrices,
        status=status,
    )
end

end
