function sweep_result_dataframe(result::SweepResult)
    rows = Any[]
    points = get(result.provenance, :points, Dict{Symbol,Any}[])
    axis_names = _axis_names(result.execution_plan.sweep_spec)

    for idx in eachindex(result.point_statuses)
        point = idx <= length(points) ? points[idx] : Dict{Symbol,Any}()
        row = Pair{Symbol,Any}[
            :point_index => idx,
            :status => result.point_statuses[idx],
            :success => result.point_statuses[idx] == :success,
        ]

        for name in axis_names
            push!(row, name => get(point, name, missing))
        end

        push!(rows, (; row...))
    end

    return DataFrame(rows)
end
