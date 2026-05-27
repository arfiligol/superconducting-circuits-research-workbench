function _is_zero_mode(mode)
    return all(value -> value == 0, mode)
end

function _mode_token(mode)
    return join(string.(Int.(collect(mode))), ",")
end

function _mode_trace_label(outputmode, outputport, inputmode, inputport)
    return "om=$(_mode_token(outputmode))|op=$(Int(outputport))|im=$(_mode_token(inputmode))|ip=$(Int(inputport))"
end

function _flattened_mode_port_index(mode_index::Int, port_index::Int, mode_count::Int)
    return mode_index + (port_index - 1) * mode_count
end

function _property_or_nothing(value, name::Symbol)
    return try
        getproperty(value, name)
    catch
        nothing
    end
end

function _collect_mode_parameter_traces(parameter_array, modes, portnumbers)
    traces = Dict{String,Vector{ComplexF64}}()
    isnothing(parameter_array) && return traces
    isempty(parameter_array) && return traces

    mode_count = length(modes)
    for outputmode_index in eachindex(modes)
        outputmode = modes[outputmode_index]
        for outputport_index in eachindex(portnumbers)
            outputport = portnumbers[outputport_index]
            row_index = _flattened_mode_port_index(outputmode_index, outputport_index, mode_count)
            for inputmode_index in eachindex(modes)
                inputmode = modes[inputmode_index]
                for inputport_index in eachindex(portnumbers)
                    inputport = portnumbers[inputport_index]
                    column_index = _flattened_mode_port_index(
                        inputmode_index,
                        inputport_index,
                        mode_count,
                    )
                    label = _mode_trace_label(outputmode, outputport, inputmode, inputport)
                    traces[label] = collect(ComplexF64.(vec(parameter_array[row_index, column_index, :])))
                end
            end
        end
    end

    return traces
end

function extract_zero_mode_sparameters(solution; port_indices=nothing)
    linearized = _property_or_nothing(solution, :linearized)
    isnothing(linearized) && return Dict{String,Vector{ComplexF64}}()

    s_parameters = _property_or_nothing(linearized, :S)
    modes = _property_or_nothing(linearized, :modes)
    portnumbers = _property_or_nothing(linearized, :portnumbers)
    if any(isnothing, (s_parameters, modes, portnumbers)) || isempty(s_parameters)
        return Dict{String,Vector{ComplexF64}}()
    end

    requested_ports = isnothing(port_indices) ? Int.(collect(portnumbers)) : Int.(collect(port_indices))
    zero_mode_index = findfirst(_is_zero_mode, modes)
    isnothing(zero_mode_index) && return Dict{String,Vector{ComplexF64}}()

    traces = Dict{String,Vector{ComplexF64}}()
    mode_count = length(modes)
    port_lookup = Dict(Int(portnumbers[idx]) => idx for idx in eachindex(portnumbers))

    for output_port in sort(requested_ports)
        outputport_index = get(port_lookup, output_port, nothing)
        isnothing(outputport_index) && continue
        row_index = _flattened_mode_port_index(zero_mode_index, outputport_index, mode_count)

        for input_port in sort(requested_ports)
            inputport_index = get(port_lookup, input_port, nothing)
            isnothing(inputport_index) && continue
            column_index = _flattened_mode_port_index(zero_mode_index, inputport_index, mode_count)
            label = "S$(output_port)$(input_port)"
            traces[label] = collect(ComplexF64.(vec(s_parameters[row_index, column_index, :])))
        end
    end

    return traces
end

function extract_linearized_traces(solution; port_indices=nothing)
    linearized = _property_or_nothing(solution, :linearized)
    isnothing(linearized) && return Dict{Symbol,Any}()

    modes = _property_or_nothing(linearized, :modes)
    portnumbers = _property_or_nothing(linearized, :portnumbers)
    if any(isnothing, (modes, portnumbers))
        return Dict{Symbol,Any}()
    end

    s_parameters = _property_or_nothing(linearized, :S)
    z_parameters = _property_or_nothing(linearized, :Z)

    return Dict{Symbol,Any}(
        :modes => [Int.(collect(mode)) for mode in modes],
        :portnumbers => Int.(collect(portnumbers)),
        :zero_mode_s => extract_zero_mode_sparameters(solution; port_indices=port_indices),
        :s_parameter_mode => _collect_mode_parameter_traces(s_parameters, modes, portnumbers),
        :z_parameter_mode => _collect_mode_parameter_traces(z_parameters, modes, portnumbers),
    )
end
