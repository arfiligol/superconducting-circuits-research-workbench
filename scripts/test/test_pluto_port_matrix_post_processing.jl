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

function _compiled_port_fixture(; netlist=nothing, port_map=nothing)
    rows = isnothing(netlist) ? Any[
        ("P1", "node_1", "0", 1),
        ("R_port_1", "node_1", "0", :R_port_1),
        ("P2", "node_2", "0", 2),
        ("R_port_2", "node_2", "0", :R_port_2),
    ] : netlist
    mappings = isnothing(port_map) ? Dict(
        :input => (index=1,),
        :output => (index=2,),
    ) : port_map
    return (
        netlist=rows,
        component_values=Dict{Symbol,Any}(:R_port_1 => 50.0, :R_port_2 => 100.0),
        port_map=mappings,
    )
end

function _matrix_stack(
    matrix;
    labels,
    quantity_kind=:admittance,
    frequency_hz=5.0e9,
    source_kind=:test,
)
    dimension = length(labels)
    return PortMatrixStack(
        labels=labels,
        frequencies_hz=[frequency_hz],
        values=reshape(ComplexF64.(matrix), dimension, dimension, 1),
        quantity_kind=quantity_kind,
        source_kind=source_kind,
    )
end

@testset "matrix stacks require explicit quantity and unique labels" begin
    values = zeros(ComplexF64, 2, 2, 1)
    @test_throws UndefKeywordError PortMatrixStack(
        labels=["a", "b"],
        frequencies_hz=[1.0],
        values=values,
        source_kind=:test,
    )
    @test_throws ErrorException PortMatrixStack(
        labels=["a", "a"],
        frequencies_hz=[1.0],
        values=values,
        quantity_kind=:admittance,
        source_kind=:test,
    )
    @test_throws ErrorException PortMatrixStack(
        labels=["a", "b"],
        frequencies_hz=[1.0],
        values=values,
        quantity_kind=:scattering,
        source_kind=:test,
    )
end

@testset "zero-mode Y stack can be derived from selected Z traces" begin
    z_stack = zero_mode_z_matrix_stack(_result_with_z_traces())
    stack = zero_mode_y_matrix_stack(_result_with_z_traces())

    @test z_stack.quantity_kind == :impedance
    @test stack.labels == ["1", "2"]
    @test stack.quantity_kind == :admittance
    @test stack.source_kind == :z_inverse
    @test stack.values[:, :, 1] ≈ ComplexF64[
        0.02 0.0
        0.0 0.04
    ]
    @test invert_port_matrix_stack(z_stack).quantity_kind == :admittance
    @test invert_port_matrix_stack(stack).quantity_kind == :impedance
end

@testset "port termination compensation subtracts selected shunt conductance" begin
    compiled = _compiled_port_fixture()
    stack = zero_mode_y_matrix_stack(_result_with_z_traces())
    evidence = compiled_port_shunt_evidence(compiled; port_indices=[1, 2])
    compensated = apply_port_termination_compensation(
        stack,
        compiled;
        compensate_port_indices=[1, 2],
        removal_intent=:intrinsic_pair_probe_scaffold,
    )

    @test evidence[1].port_id == :input
    @test evidence[1].resistance_ohm == 50.0
    @test evidence[2].resistance_ohm == 100.0
    @test compensated.quantity_kind == :admittance
    @test compensated.source_kind == :ptc_z_inverse
    @test compensated.values[:, :, 1] ≈ ComplexF64[
        0.0 0.0
        0.0 0.03
    ]
    @test stack.values[:, :, 1] ≈ ComplexF64[
        0.02 0.0
        0.0 0.04
    ]

    wrong_branch = _compiled_port_fixture(netlist=Any[
        ("P1", "node_1", "0", 1),
        ("R_port_1", "other_node", "0", :R_port_1),
    ], port_map=Dict(:input => (index=1,)))
    missing_mapping = _compiled_port_fixture(port_map=Dict(:input => (index=1,)))
    @test_throws ErrorException compiled_port_shunt_evidence(wrong_branch; port_indices=[1])
    @test_throws ErrorException compiled_port_shunt_evidence(missing_mapping; port_indices=[2])
    @test_throws MethodError apply_port_termination_compensation(
        stack;
        resistance_ohm_by_port=Dict(1 => 50.0),
    )
    impedance_stack = zero_mode_z_matrix_stack(_result_with_z_traces())
    @test_throws ErrorException apply_port_termination_compensation(
        impedance_stack,
        compiled;
        compensate_port_indices=[1],
        removal_intent=:intrinsic_pair_probe_scaffold,
    )
    transformed = apply_coordinate_transform(stack, Matrix{ComplexF64}(I, 2, 2))
    @test transformed.source_kind == :coordinate_transform_z_inverse
    @test_throws ErrorException apply_port_termination_compensation(
        transformed,
        compiled;
        compensate_port_indices=[1],
        removal_intent=:intrinsic_pair_probe_scaffold,
    )
end

@testset "coordinate transform applies real power-conjugate inverse transpose" begin
    y = ComplexF64[
        2.0 -1.0
        -1.0 2.0
    ]
    stack = _matrix_stack(y; labels=["p1", "p2"])
    transform = common_differential_transform(2, 1, 2; alpha=0.3, beta=0.7)
    modal = apply_coordinate_transform(stack, transform; labels=["common", "differential"])

    @test transform ≈ ComplexF64[0.3 0.7; 1.0 -1.0]
    @test modal.labels == ["common", "differential"]
    @test modal.quantity_kind == :admittance
    @test modal.source_kind == :coordinate_transform_test
    @test modal.values[:, :, 1] ≈ ComplexF64[
        2.0 0.4
        0.4 1.58
    ]

    voltage_port = ComplexF64[1.0 + 0.2im, -0.4 + 0.1im]
    current_port = y * voltage_port
    voltage_modal = transform * voltage_port
    current_modal = transpose(transform) \ current_port
    @test current_modal ≈ ComplexF64[
        current_port[1] + current_port[2],
        0.7 * current_port[1] - 0.3 * current_port[2],
    ]
    @test modal.values[:, :, 1] * voltage_modal ≈ current_modal
    @test dot(voltage_modal, current_modal) ≈ dot(voltage_port, current_port)

    @test_throws ErrorException apply_coordinate_transform(
        stack,
        ComplexF64[1.0 0.0; 0.0 im],
    )
    @test_throws ErrorException apply_coordinate_transform(
        stack,
        ComplexF64[1.0 0.0; 0.0 Inf],
    )
    impedance_stack = _matrix_stack(y; labels=["p1", "p2"], quantity_kind=:impedance)
    @test_throws ErrorException apply_coordinate_transform(impedance_stack, transform)
end

@testset "Kron reduction applies Schur complement over dropped ports" begin
    y = ComplexF64[
        4.0 1.0 2.0
        1.0 3.0 0.5
        2.0 0.5 5.0
    ]
    stack = _matrix_stack(y; labels=["a", "b", "c"])

    reduced = kron_reduce(stack; keep_indices=[1, 3])
    expected = ComplexF64[
        11 / 3 11 / 6
        11 / 6 59 / 12
    ]

    @test reduced.labels == ["a", "c"]
    @test reduced.quantity_kind == :admittance
    @test reduced.source_kind == :kron_reduction_test
    @test reduced.values[:, :, 1] ≈ expected

    reversed = kron_reduce(stack; keep_indices=[3, 1])
    @test reversed.labels == ["c", "a"]
    @test reversed.values[:, :, 1] ≈ expected[[2, 1], [2, 1]]

    keep = [1, 3]
    drop = [2]
    voltage_keep = ComplexF64[0.7 + 0.2im, -0.4 + 0.1im]
    voltage_drop = -(y[drop, drop] \ (y[drop, keep] * voltage_keep))
    voltage_full = zeros(ComplexF64, 3)
    voltage_full[keep] = voltage_keep
    voltage_full[drop] = voltage_drop
    current_full = y * voltage_full
    @test isapprox(current_full[drop], zeros(ComplexF64, 1); atol=1.0e-12)
    @test current_full[keep] ≈ reduced.values[:, :, 1] * voltage_keep

    loaded_y = copy(y)
    loaded_y[2, 2] += 7.0
    loaded_stack = _matrix_stack(loaded_y; labels=["a", "b", "c"])
    loaded_reduced = kron_reduce(loaded_stack; keep_indices=keep)
    loaded_expected = loaded_y[keep, keep] -
        loaded_y[keep, drop] * (loaded_y[drop, drop] \ loaded_y[drop, keep])
    @test loaded_reduced.values[:, :, 1] ≈ loaded_expected
    @test !isapprox(loaded_reduced.values[:, :, 1], reduced.values[:, :, 1])

    near_singular_y = ComplexF64[
        4.0 1.0 1.0
        1.0 1.0 0.0
        1.0 0.0 1.0e-12
    ]
    near_singular = _matrix_stack(
        near_singular_y;
        labels=["a", "b", "c"],
        frequency_hz=5.5e9,
    )
    # A finite condition number remains evidence; only a Human chooses a rejection threshold.
    @test all(isfinite, kron_reduce(near_singular; keep_indices=[1]).values)

    singular_y = copy(near_singular_y)
    singular_y[3, 3] = 0.0
    singular = _matrix_stack(singular_y; labels=["a", "b", "c"], frequency_hz=6.25e9)
    singular_error = try
        kron_reduce(singular; keep_indices=[1])
        nothing
    catch err
        err
    end
    @test singular_error isa ErrorException
    singular_message = singular_error isa Exception ? sprint(showerror, singular_error) : ""
    @test occursin("frequency index 1", singular_message)
    @test occursin("6.25e9 Hz", singular_message)
    @test occursin("dropped labels [b, c]", singular_message)
    @test occursin("condition number Inf", singular_message)

    nonfinite_y = copy(near_singular_y)
    nonfinite_y[3, 3] = NaN
    nonfinite = _matrix_stack(nonfinite_y; labels=["a", "b", "c"])
    @test_throws ErrorException kron_reduce(nonfinite; keep_indices=[1])

    impedance_stack = _matrix_stack(y; labels=["a", "b", "c"], quantity_kind=:impedance)
    @test_throws ErrorException kron_reduce(impedance_stack; keep_indices=[1, 3])
end
