using SuperconductingCircuitsCore

const ROOT = normpath(joinpath(@__DIR__, "..", ".."))
const CHECK = "--check" in ARGS

const EXAMPLES = (
    (
        builder=build_parallel_lc_resonator_example,
        output="docs/assets/circuit_draw/pluto_examples/grounded_lc_resonator/schematic_export.json",
    ),
    (
        builder=build_reflective_jpa_capacitive_coupled_lc_example,
        output="docs/assets/circuit_draw/pluto_examples/reflective_jpa_capacitive_coupled_lc/schematic_export.json",
    ),
    (
        builder=build_floating_lc_xy_line_example,
        output="docs/assets/circuit_draw/pluto_examples/floating_lc_xy_line/schematic_export.json",
    ),
)

function _export_json(builder)
    example = builder(;
        point_count=1,
        optional_hb_kwargs=Dict{Symbol,Any}(:nbatches => 1, :iterations => 1, :ftol => 1e-8),
    )
    return schematic_export_json(to_schematic_export_spec(example.plan))
end

function main()
    failures = String[]
    for example in EXAMPLES
        output_path = joinpath(ROOT, example.output)
        rendered = _export_json(example.builder)
        if CHECK
            if !isfile(output_path)
                push!(failures, "missing $(example.output)")
            elseif read(output_path, String) != rendered
                push!(failures, "stale $(example.output)")
            end
        else
            mkpath(dirname(output_path))
            write(output_path, rendered)
            println("wrote $(example.output)")
        end
    end

    if !isempty(failures)
        for failure in failures
            println(stderr, failure)
        end
        return 1
    end
    return 0
end

exit(main())
