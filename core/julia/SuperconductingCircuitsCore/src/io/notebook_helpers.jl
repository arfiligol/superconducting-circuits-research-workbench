function sweep_result_dataframe(result::SweepResult)
    rows = NamedTuple[]

    for point in result.points
        push!(
            rows,
            (
                point_index=point.point_index,
                success=point.success,
                error_message=point.error_message,
                parameters=copy(point.parameters),
            ),
        )
    end

    return DataFrame(rows)
end
