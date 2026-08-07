using Test

const WORKBENCH_ROOT = normpath(joinpath(@__DIR__, "..", ".."))
const D3_ROOT = joinpath(
    WORKBENCH_ROOT,
    "notebooks",
    "pluto",
    "D3 Intrinsic Purcell Filter Design",
)

include(joinpath(D3_ROOT, "d3_stage_models.jl"))

const EXPECTED_CORE_ENTRY = realpath(joinpath(
    WORKBENCH_ROOT,
    "core",
    "julia",
    "SuperconductingCircuitsCore",
    "src",
    "SuperconductingCircuitsCore.jl",
))
realpath(pathof(SuperconductingCircuitsCore)) == EXPECTED_CORE_ENTRY || error(
    "D3 IDC runtime test must load SuperconductingCircuitsCore from this Workbench candidate.",
)

@testset "D3 IDC finite-positive runtime" begin
    mapping = D3IDCMapping(
        8.0,
        (5.0, 10.0),
        (35.0, 75.0),
        "finite_positive_um",
        Dict(
            "C_12_fF" => (0.5, 9.0),
            "C_1G_fF" => (0.25, 22.0),
            "C_2G_fF" => (0.24, 22.0),
        ),
        Dict{Tuple{Float64,Float64},NamedTuple}(),
        "d3-same-die-filter-feedline-idc-q3d-gap8-linear-length-v1",
        repeat("a", 64),
        "d3-same-die-filter-feedline-idc-q3d-tensor-fit-v1",
        Dict{String,Any}("sha256" => repeat("b", 64)),
        Dict{String,Any}("fit_method" => "ordinary_least_squares_at_selected_gap"),
    )

    inside = mapping(60.0)
    @test inside.evaluation_extrapolated == false
    @test inside.evaluation_source ==
        "linear_length_least_squares_interpolation"
    @test inside.source_length_range_um == (35.0, 75.0)
    @test inside.runtime_length_domain == "finite_positive_um"
    @test !hasproperty(mapping, :valid_length_range_um)

    below = mapping(20.0)
    outside = mapping(100.0)
    @test below.evaluation_extrapolated == true
    @test outside.evaluation_extrapolated == true
    @test outside.evaluation_source ==
        "linear_length_least_squares_extrapolation"
    @test outside.idc_mutual_capacitance_f == 59.0e-15
    @test mapping(floatmax(Float64)).idc_mutual_capacitance_f > 0

    stage = _d3_stage_idc_triplet(mapping, 100.0)
    @test stage.source_length_range_um == (35.0, 75.0)
    @test stage.runtime_length_domain == "finite_positive_um"
    @test stage.evaluation_extrapolated == true
    @test stage.evaluation_source == outside.evaluation_source
    @test stage.mapping_semantic_sha256 ==
        d3_idc_mapping_semantic_sha256(mapping)
    @test_throws ErrorException _d3_stage_idc_triplet(
        x -> merge(mapping(x), (evaluation_extrapolated=false,)),
        100.0,
    )

    for invalid in (0.0, -1.0, Inf, -Inf, NaN)
        @test_throws ErrorException mapping(invalid)
    end
end
