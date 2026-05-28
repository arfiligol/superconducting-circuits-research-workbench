@testset "parameter roles and metadata" begin
    numeric = ParameterMetadata(
        name=:capacitance_f,
        role=NumericParameter(),
        owner="component",
        targets=[:capacitance],
        sweep_name=:c,
        units="F",
    )

    @test is_numeric(numeric)
    @test !is_structural(numeric)
    @test parameter_role(numeric) isa NumericParameter
    @test parameter_owner(numeric) == "component"
    @test strongest_parameter_role([NumericParameter(), StructuralParameter()]) isa StructuralParameter
    @test ParameterBinding(:capacitance_f, 1.0e-15).value == 1.0e-15
end

