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

function _present_output_array(value)::Bool
    isnothing(value) && return false
    return try
        length(value) > 0
    catch
        false
    end
end

function _array_rank(value)
    return try
        ndims(value)
    catch
        ndims(Array(value))
    end
end

function _linearized_output(solution)
    return _property_or_nothing(solution, :linearized)
end

function _family_property(family)
    canonical = _canonical_output_family(family)
    canonical == :S && return :S
    canonical == :Z && return :Z
    canonical == :QE && return :QE
    canonical == :QEideal && return :QEideal
    canonical == :CM && return :CM
    return canonical
end

function _linearized_family_array(linearized, family)
    isnothing(linearized) && return nothing
    return _property_or_nothing(linearized, _family_property(family))
end

function _linearized_family_available(linearized, family)::Bool
    return _present_output_array(_linearized_family_array(linearized, family))
end

function _validate_requested_output_families(solution, requested_families)
    requested = unique([
        _validate_known_output_family(family; context="Requested solver output family") for
        family in collect(requested_families)
    ])
    isempty(requested) && return nothing

    linearized = _linearized_output(solution)
    isnothing(linearized) && _validation_error(
        "JosephsonCircuits.hbsolve returned no linearized HB result while output families were requested: $(join(string.(requested), ", ")).",
    )

    missing = [family for family in requested if !_linearized_family_available(linearized, family)]
    isempty(missing) || _validation_error(
        "JosephsonCircuits.hbsolve did not return requested HB output family/families: $(join(string.(missing), ", ")).",
    )

    return nothing
end

function _mode_parameter_trace(parameter_array, modes, portnumbers, outputmode_index::Int, outputport_index::Int, inputmode_index::Int, inputport_index::Int, family::Symbol)
    rank = _array_rank(parameter_array)
    if rank == 5
        return parameter_array[outputmode_index, outputport_index, inputmode_index, inputport_index, :]
    elseif rank == 3
        mode_count = length(modes)
        row_index = _flattened_mode_port_index(outputmode_index, outputport_index, mode_count)
        column_index = _flattened_mode_port_index(inputmode_index, inputport_index, mode_count)
        return parameter_array[row_index, column_index, :]
    end
    _validation_error(
        "Linearized HB output family '$(family)' has unsupported rank $(rank); expected rank 3 or 5.",
    )
end

function _collect_mode_parameter_traces(parameter_array, modes, portnumbers, family::Symbol, ::Type{T}) where {T}
    traces = Dict{String,Vector{T}}()
    !_present_output_array(parameter_array) && return traces

    for outputmode_index in eachindex(modes)
        outputmode = modes[outputmode_index]
        for outputport_index in eachindex(portnumbers)
            outputport = portnumbers[outputport_index]
            for inputmode_index in eachindex(modes)
                inputmode = modes[inputmode_index]
                for inputport_index in eachindex(portnumbers)
                    inputport = portnumbers[inputport_index]
                    label = _mode_trace_label(outputmode, outputport, inputmode, inputport)
                    values = _mode_parameter_trace(
                        parameter_array,
                        modes,
                        portnumbers,
                        outputmode_index,
                        outputport_index,
                        inputmode_index,
                        inputport_index,
                        family,
                    )
                    traces[label] = collect(T.(vec(values)))
                end
            end
        end
    end

    return traces
end

function _collect_mode_parameter_traces(parameter_array, modes, portnumbers, family::Symbol)
    return _collect_mode_parameter_traces(parameter_array, modes, portnumbers, family, ComplexF64)
end

function _cm_trace(cm_array, modes, portnumbers, outputmode_index::Int, outputport_index::Int)
    rank = _array_rank(cm_array)
    if rank == 3
        return cm_array[outputmode_index, outputport_index, :]
    elseif rank == 2
        mode_count = length(modes)
        row_index = _flattened_mode_port_index(outputmode_index, outputport_index, mode_count)
        return cm_array[row_index, :]
    end
    _validation_error(
        "Linearized HB output family 'CM' has unsupported rank $(rank); expected rank 2 or 3.",
    )
end

function _cm_trace_label(outputmode, outputport)
    return "om=$(_mode_token(outputmode))|op=$(Int(outputport))"
end

function _collect_cm_traces(cm_array, modes, portnumbers)
    traces = Dict{String,Vector{Float64}}()
    !_present_output_array(cm_array) && return traces

    for outputmode_index in eachindex(modes)
        outputmode = modes[outputmode_index]
        for outputport_index in eachindex(portnumbers)
            outputport = portnumbers[outputport_index]
            label = _cm_trace_label(outputmode, outputport)
            traces[label] = collect(Float64.(vec(_cm_trace(cm_array, modes, portnumbers, outputmode_index, outputport_index))))
        end
    end

    return traces
end

function extract_zero_mode_sparameters(solution; port_indices=nothing)
    linearized = _linearized_output(solution)
    isnothing(linearized) && return Dict{String,Vector{ComplexF64}}()

    s_parameters = _linearized_family_array(linearized, :S)
    modes = _property_or_nothing(linearized, :modes)
    portnumbers = _property_or_nothing(linearized, :portnumbers)
    if any(isnothing, (modes, portnumbers)) || !_present_output_array(s_parameters)
        return Dict{String,Vector{ComplexF64}}()
    end

    requested_ports = isnothing(port_indices) ? Int.(collect(portnumbers)) : Int.(collect(port_indices))
    zero_mode_index = findfirst(_is_zero_mode, modes)
    isnothing(zero_mode_index) && return Dict{String,Vector{ComplexF64}}()

    traces = Dict{String,Vector{ComplexF64}}()
    port_lookup = Dict(Int(portnumbers[idx]) => idx for idx in eachindex(portnumbers))

    for output_port in sort(requested_ports)
        outputport_index = get(port_lookup, output_port, nothing)
        isnothing(outputport_index) && continue

        for input_port in sort(requested_ports)
            inputport_index = get(port_lookup, input_port, nothing)
            isnothing(inputport_index) && continue
            label = "S$(output_port)$(input_port)"
            traces[label] = collect(
                ComplexF64.(
                    vec(
                        _mode_parameter_trace(
                            s_parameters,
                            modes,
                            portnumbers,
                            zero_mode_index,
                            outputport_index,
                            zero_mode_index,
                            inputport_index,
                            :S,
                        ),
                    ),
                ),
            )
        end
    end

    return traces
end

function extract_linearized_traces(solution; port_indices=nothing, requested_families=Symbol[], requested_outputs=nothing)
    if !isnothing(requested_outputs)
        requested_families = requested_outputs
    end
    _validate_requested_output_families(solution, requested_families)

    linearized = _linearized_output(solution)
    isnothing(linearized) && return Dict{Symbol,Any}()

    modes = _property_or_nothing(linearized, :modes)
    portnumbers = _property_or_nothing(linearized, :portnumbers)
    if any(isnothing, (modes, portnumbers))
        isempty(requested_families) || _validation_error(
            "JosephsonCircuits.hbsolve returned linearized HB outputs without modes/portnumbers metadata required for trace extraction.",
        )
        return Dict{Symbol,Any}()
    end

    traces = Dict{Symbol,Any}(
        :modes => [Int.(collect(mode)) for mode in modes],
        :portnumbers => Int.(collect(portnumbers)),
    )

    s_parameters = _linearized_family_array(linearized, :S)
    if _present_output_array(s_parameters)
        traces[:zero_mode_s] = extract_zero_mode_sparameters(solution; port_indices=port_indices)
        traces[:s_parameter_mode] = _collect_mode_parameter_traces(s_parameters, modes, portnumbers, :S)
    else
        traces[:zero_mode_s] = Dict{String,Vector{ComplexF64}}()
    end

    z_parameters = _linearized_family_array(linearized, :Z)
    _present_output_array(z_parameters) &&
        (traces[:z_parameter_mode] = _collect_mode_parameter_traces(z_parameters, modes, portnumbers, :Z))

    qe = _linearized_family_array(linearized, :QE)
    _present_output_array(qe) &&
        (traces[:qe_mode] = _collect_mode_parameter_traces(qe, modes, portnumbers, :QE, Float64))

    qeideal = _linearized_family_array(linearized, :QEideal)
    _present_output_array(qeideal) &&
        (traces[:qeideal_mode] = _collect_mode_parameter_traces(qeideal, modes, portnumbers, :QEideal, Float64))

    cm = _linearized_family_array(linearized, :CM)
    _present_output_array(cm) && (traces[:cm_mode] = _collect_cm_traces(cm, modes, portnumbers))

    return traces
end
