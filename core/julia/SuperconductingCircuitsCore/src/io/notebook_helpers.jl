function sweep_result_dataframe(result::SweepResult)
    rows = NamedTuple[]
    axis_names = [axis.name for axis in result.axes]

    for point in result.points
        row = Pair{Symbol,Any}[
            :point_index => point.point_index,
            :success => point.success,
            :error_message => point.error_message,
        ]

        for name in axis_names
            push!(row, Symbol(name) => get(point.parameters, name, missing))
        end

        push!(rows, (; row...))
    end

    return DataFrame(rows)
end
