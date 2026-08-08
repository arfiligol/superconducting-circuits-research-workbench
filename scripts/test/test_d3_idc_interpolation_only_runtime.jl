using Test

const WORKBENCH_ROOT = normpath(joinpath(@__DIR__, "..", ".."))
const D3_ROOT = joinpath(
    WORKBENCH_ROOT,
    "notebooks",
    "pluto",
    "D3 Intrinsic Purcell Filter Design",
)

include(joinpath(D3_ROOT, "d3_rev10_models.jl"))

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

@testset "D3 IDC interpolation-only runtime" begin
    mapping = D3IDCMapping(
        8.0,
        (5.0, 10.0),
        (35.0, 75.0),
        "closed_source_support_um",
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

    expected_fF = Dict(
        35.0 => (filter_ground=30.4, feedline_ground=30.75, mutual=26.5),
        60.0 => (filter_ground=36.4, feedline_ground=37.0, mutual=39.0),
        75.0 => (filter_ground=40.0, feedline_ground=40.75, mutual=46.5),
    )
    for length_um in (35.0, 60.0, 75.0)
        result = mapping(length_um)
        expected = expected_fF[length_um]
        @test isapprox(
            result.idc_filter_ground_capacitance_f,
            expected.filter_ground * 1e-15,
        )
        @test isapprox(
            result.idc_feedline_ground_capacitance_f,
            expected.feedline_ground * 1e-15,
        )
        @test isapprox(
            result.idc_mutual_capacitance_f,
            expected.mutual * 1e-15,
        )
        @test result.evaluation_source ==
            "linear_length_least_squares_interpolation"
        @test result.source_length_range_um == (35.0, 75.0)
        @test result.runtime_length_domain == "closed_source_support_um"
        @test !hasproperty(result, :evaluation_extrapolated)
    end
    @test !hasproperty(mapping, :valid_length_range_um)

    for invalid in (20.0, 100.0, 0.0, -1.0, Inf, -Inf, NaN)
        @test_throws ErrorException mapping(invalid)
    end

    mapped = _d3_rev10_idc_triplet(mapping, 60.0)
    @test mapped.source_length_range_um == (35.0, 75.0)
    @test mapped.runtime_length_domain == "closed_source_support_um"
    @test mapped.evaluation_source ==
        "linear_length_least_squares_interpolation"
    @test !hasproperty(mapped, :evaluation_extrapolated)
    @test mapped.mapping_semantic_sha256 ==
        d3_idc_mapping_semantic_sha256(mapping)
    @test_throws ErrorException _d3_rev10_idc_triplet(
        _ -> mapping(60.0),
        100.0,
    )
    @test_throws ErrorException _d3_rev10_idc_triplet(
        _ -> merge(
            mapping(60.0),
            (runtime_length_domain="finite_positive_um",),
        ),
        60.0,
    )
    @test_throws ErrorException _d3_rev10_idc_triplet(
        _ -> merge(
            mapping(60.0),
            (evaluation_source="linear_length_least_squares_extrapolation",),
        ),
        60.0,
    )
end
