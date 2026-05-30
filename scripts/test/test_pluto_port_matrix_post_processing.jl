using LinearAlgebra
using Test

include(joinpath(@__DIR__, "..", "..", "notebooks", "pluto", "includes", "port_matrix_post_processing.jl"))
using .PortMatrixPostProcessing

struct FakeResult
    frequencies_hz::Vector{Float64}
    traces::Dict{Symbol,Any}
end

function _label(output_port::Integer, input_port::Integer)
    return mode_trace_label(outputport=output_port, inputport=input_port)
end

function _result_with_y_traces()
    traces = Dict{String,Vector{ComplexF64}}(
        _label(1, 1) => [2.0 + 0.0im, 3.0 + 0.0im],
        _label(1, 2) => [-1.0 + 0.0im, -0.5 + 0.0im],
        _label(2, 1) => [-1.0 + 0.0im, -0.5 + 0.0im],
        _label(2, 2) => [2.0 + 0.0im, 1.5 + 0.0im],
    )
    return FakeResult(
        [5.0e9, 6.0e9],
        Dict{Symbol,Any}(
            :portnumbers => [1, 2],
            :y_parameter_mode => traces,
        ),
    )
end

function _result_with_z_traces()
    traces = Dict{String,Vector{ComplexF64}}(
        _label(1, 1) => [50.0 + 0.0im],
        _label(1, 2) => [0.0 + 0.0im],
        _label(2, 1) => [0.0 + 0.0im],
        _label(2, 2) => [25.0 + 0.0im],
    )
    return FakeResult(
        [5.0e9],
        Dict{Symbol,Any}(
            :portnumbers => [1, 2],
            :z_parameter_mode => traces,
        ),
    )
end

@testset "zero-mode matrix stack reads selected Y traces" begin
    stack = zero_mode_y_matrix_stack(_result_with_y_traces(); ports=[2, 1])

    @test stack.labels == ["2", "1"]
    @test stack.frequencies_hz == [5.0e9, 6.0e9]
    @test stack.source_kind == :y_trace
    @test stack.values[:, :, 1] ≈ ComplexF64[
        2.0 -1.0
        -1.0 2.0
    ]
    @test stack.values[:, :, 2] ≈ ComplexF64[
        1.5 -0.5
        -0.5 3.0
    ]
end

@testset "zero-mode Y stack can be derived from selected Z traces" begin
    stack = zero_mode_y_matrix_stack(_result_with_z_traces())

    @test stack.labels == ["1", "2"]
    @test stack.source_kind == :z_inverse
    @test stack.values[:, :, 1] ≈ ComplexF64[
        0.02 0.0
        0.0 0.04
    ]
end

@testset "port termination compensation subtracts selected shunt conductance" begin
    stack = zero_mode_y_matrix_stack(_result_with_y_traces())
    compensated = apply_port_termination_compensation(
        stack;
        resistance_ohm_by_port=Dict(1 => 50.0, 2 => 100.0),
    )

    @test compensated.values[:, :, 1] ≈ ComplexF64[
        1.98 -1.0
        -1.0 1.99
    ]
    @test stack.values[:, :, 1] ≈ ComplexF64[
        2.0 -1.0
        -1.0 2.0
    ]
end

@testset "coordinate transform applies non-conjugating inverse transpose" begin
    stack = PortMatrixStack(
        labels=["p1", "p2"],
        frequencies_hz=[5.0e9],
        values=reshape(ComplexF64[2.0, -1.0, -1.0, 2.0], 2, 2, 1),
        source_kind=:test,
    )
    transform = common_differential_transform(2, 1, 2)
    modal = apply_coordinate_transform(stack, transform; labels=["common", "differential"])

    @test modal.labels == ["common", "differential"]
    @test modal.values[:, :, 1] ≈ ComplexF64[
        2.0 0.0
        0.0 1.5
    ]
end

@testset "Kron reduction applies Schur complement over dropped ports" begin
    values = Array{ComplexF64,3}(undef, 3, 3, 1)
    values[:, :, 1] = ComplexF64[
        4.0 1.0 2.0
        1.0 3.0 0.5
        2.0 0.5 5.0
    ]
    stack = PortMatrixStack(
        labels=["a", "b", "c"],
        frequencies_hz=[5.0e9],
        values=values,
        source_kind=:test,
    )

    reduced = kron_reduce(stack; keep_indices=[1, 3])

    @test reduced.labels == ["a", "c"]
    @test reduced.values[:, :, 1] ≈ ComplexF64[
        11 / 3 11 / 6
        11 / 6 59 / 12
    ]
end
