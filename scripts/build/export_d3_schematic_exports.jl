using SuperconductingCircuitsCore

const ROOT = normpath(joinpath(@__DIR__, "..", ".."))
const CHECK = "--check" in ARGS

include(
    joinpath(
        ROOT,
        "notebooks",
        "pluto",
        "D3 Intrinsic Purcell Filter Design",
        "d3_circuit_plans.jl",
    ),
)

const D3_CIRCUIT_PLANS = (
    (
        builder=build_d3_intrinsic_purcell_equivalent_circuit_plan,
        output="docs/assets/circuit_draw/circuit_plans/d3_intrinsic_purcell_equivalent/schematic_export.json",
        uses_idc_fixture=true,
    ),
    (
        builder=build_d3_intrinsic_purcell_hybridized_circuit_plan,
        output="docs/assets/circuit_draw/circuit_plans/d3_intrinsic_purcell_hybridized/schematic_export.json",
        uses_idc_fixture=true,
    ),
    (
        builder=build_d3_linewidth_la_equivalent_circuit_plan,
        output="docs/assets/circuit_draw/circuit_plans/d3_linewidth_la_equivalent/schematic_export.json",
        uses_idc_fixture=true,
    ),
    (
        builder=build_d3_linewidth_la_hybridized_circuit_plan,
        output="docs/assets/circuit_draw/circuit_plans/d3_linewidth_la_hybridized/schematic_export.json",
        uses_idc_fixture=true,
    ),
    (
        builder=build_d3_intrinsic_pair_notch_equivalent_circuit_plan,
        output="docs/assets/circuit_draw/circuit_plans/d3_intrinsic_pair_notch_equivalent/schematic_export.json",
        uses_idc_fixture=false,
    ),
    (
        builder=build_d3_intrinsic_pair_notch_hybridized_circuit_plan,
        output="docs/assets/circuit_draw/circuit_plans/d3_intrinsic_pair_notch_hybridized/schematic_export.json",
        uses_idc_fixture=false,
    ),
)

const D3_IDC_FIXTURE = (
    idc_filter_ground_capacitance_f=35.0e-15,
    idc_feedline_ground_capacitance_f=34.5e-15,
    idc_mutual_capacitance_f=38.0e-15,
)

function _d3_export_json(entry)
    built = entry.uses_idc_fixture ?
        entry.builder(; D3_IDC_FIXTURE...) :
        entry.builder()
    return schematic_export_json(to_schematic_export_spec(built.plan))
end

function main()
    failures = String[]
    for entry in D3_CIRCUIT_PLANS
        output_path = joinpath(ROOT, entry.output)
        rendered = _d3_export_json(entry)
        if CHECK
            if !isfile(output_path)
                push!(failures, "missing $(entry.output)")
            elseif read(output_path, String) != rendered
                push!(failures, "stale $(entry.output)")
            end
        else
            mkpath(dirname(output_path))
            write(output_path, rendered)
            println("wrote $(entry.output)")
        end
    end

    if !isempty(failures)
        foreach(failure -> println(stderr, failure), failures)
        return 1
    end
    return 0
end

exit(main())
