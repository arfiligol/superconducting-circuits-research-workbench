using Test

const TEST_WORKBENCH_ROOT = normpath(joinpath(@__DIR__, "..", ".."))
include(joinpath(
    TEST_WORKBENCH_ROOT,
    "notebooks",
    "pluto",
    "D3 Intrinsic Purcell Filter Design",
    "d3_rev10_slot_search.jl",
))

@testset "D3 Rev10 winner relative-change zero reference" begin
    @test relative_change(0.0, 0.0) == 0.0
    @test relative_change(-0.0, 0.0) == 0.0
    @test relative_change(0.0, 1.0) == Inf
    @test relative_change(0.0, -1.0) == Inf
    @test json_relative_change(relative_change(0.0, 0.0)) == 0.0
    @test json_relative_change(relative_change(0.0, 1.0)) == "Inf"
    @test JSON3.read(JSON3.write((
        zero_to_zero=json_relative_change(relative_change(0.0, 0.0)),
        zero_to_nonzero=json_relative_change(relative_change(0.0, 1.0)),
    )), Dict{String,Any}) == Dict{String,Any}(
        "zero_to_zero" => 0.0,
        "zero_to_nonzero" => "Inf",
    )
end

@testset "D3 Rev10 runner authority identity" begin
    manifest_path = joinpath(
        D3_SOURCE_ROOT,
        MANIFEST_BASENAME,
    )
    loaded_path, manifest = load_manifest(manifest_path)
    @test loaded_path == abspath(manifest_path)
    @test file_sha256(loaded_path) == EXPECTED_MANIFEST_SHA256
    @test String(manifest["sources"]["target_contract_sha256"]) ==
        D3_REV10_OBJECTIVE_AUTHORITY.target_contract_sha256 ==
        "d68606de00484311bac45ce3e0f78b0e14b2a31cbbbbf9bfa086e1aa1acc5519"
end
