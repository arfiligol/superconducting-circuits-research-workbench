# This test freezes the cross-language D3 semantic-value hash framing against
# static golden vectors. It covers exact scalar types, UTF-8 byte lengths,
# ordered containers, mapping key order, Float64 bits, and the real generic
# optimizer conditions payload with sol_review excluded.

using Test
using SuperconductingCircuitsCore

const JSON3 = SuperconductingCircuitsCore.JSON3
const D3_ROOT = joinpath(@__DIR__, "..", "..", "notebooks", "pluto", "D3 Intrinsic Purcell Filter Design")
include(joinpath(D3_ROOT, "d3_semantic_hash.jl"))
using .D3SemanticHash

fixture = JSON3.read(read(joinpath(@__DIR__, "fixtures", "d3_semantic_hash_vectors.v1.json"), String), Dict{String,Any})

@testset "D3 semantic hash golden vectors" begin
    @test fixture["semantic_hash_framing"] == SEMANTIC_HASH_FRAMING
    for vector in fixture["vectors"]
        value = haskey(vector, "float64_hex_bits") ? reinterpret(Float64, parse(UInt64, vector["float64_hex_bits"]; base = 16)) : vector["value"]
        @test semantic_value_sha256(value) == vector["expected_sha256"]
    end
    expected_by_name = Dict(vector["name"] => vector["expected_sha256"] for vector in fixture["vectors"])
    @test expected_by_name["negative_zero"] == expected_by_name["integer_zero"]
    @test expected_by_name["float_one"] == expected_by_name["integer_one"]
    @test expected_by_name["float_1e8"] == expected_by_name["integer_1e8"]
    negative_zero = only(vector for vector in fixture["vectors"] if vector["name"] == "negative_zero")
    @test signbit(reinterpret(Float64, parse(UInt64, negative_zero["float64_hex_bits"]; base = 16)))
    @test_throws ErrorException semantic_value_sha256(Dict("量" => 1))
    @test_throws ErrorException semantic_value_sha256(Float32(1.0))
    @test_throws ErrorException semantic_value_sha256(Inf)

    conditions = JSON3.read(read(joinpath(D3_ROOT, "d3_optimizer_conditions.json"), String), Dict{String,Any})
    @test conditions["sol_review"]["hash_framing"] == SEMANTIC_HASH_FRAMING
    conditions_payload = Dict(key => value for (key, value) in conditions if key != "sol_review")
    @test semantic_value_sha256(conditions_payload) == fixture["actual_conditions_without_sol_review_expected_sha256"]
    @test conditions["metric_specs"]["g_hz"]["scale"] == 10.0e6
    @test conditions["sol_review"]["approved_conditions_sha256"] == semantic_value_sha256(conditions_payload)
    conditions_roundtrip = JSON3.read(JSON3.write(conditions_payload), Dict{String,Any})
    @test semantic_value_sha256(conditions_roundtrip) == semantic_value_sha256(conditions_payload)

    current_payload = Dict(
        "schema_version" => "d3-slot-execution-manifest.v1",
        "semantic_hash_framing" => SEMANTIC_HASH_FRAMING,
        "contract" => Dict("slot_target_ghz" => 6.0, "budget" => 1e8, "zero" => -0.0, "scale" => 2.5),
    )
    nominal_payload = Dict(
        "schema_version" => "d3-nominal-validation-manifest.v1",
        "semantic_hash_framing" => SEMANTIC_HASH_FRAMING,
        "contract" => Dict("execution" => Dict("evaluation_budget" => 1.0), "variation" => Dict("kind" => "none", "parameters" => Any[])),
    )
    for payload in (current_payload, nominal_payload)
        roundtrip = JSON3.read(JSON3.write(payload), Dict{String,Any})
        @test semantic_value_sha256(roundtrip) == semantic_value_sha256(payload)
    end
end
