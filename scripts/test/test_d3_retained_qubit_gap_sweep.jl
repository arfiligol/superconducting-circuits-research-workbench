using Test
using SuperconductingCircuitsCore

const D3_INPUT_ROOT = normpath(joinpath(
    @__DIR__, "..", "..", "notebooks", "pluto",
    "D3 Intrinsic Purcell Filter Design",
))
include(joinpath(D3_INPUT_ROOT, "d3_floating_qubit_input.jl"))
using .D3FloatingQubitInput

@testset "D3 rejects direct-retained row-sum input" begin
    mktempdir() do directory
        path = joinpath(directory, "unsupported-gap-sweep.json")
        write(
            path,
            SuperconductingCircuitsCore.JSON3.write(Dict(
                "schema_version" =>
                    "d3-retained-qubit-readout-maxwell-gap-sweep.v1",
            )),
        )
        @test_throws ErrorException load_floating_qubit_nominal_input(
            path,
            (; kwargs...) -> (; kwargs...),
        )
    end
end
