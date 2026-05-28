using Test
using SuperconductingCircuitsCore

@testset "macro fixture component" begin
    resonator = MinimalComponentLibrary.TestGroundedComponent("res")

    @test SuperconductingCircuitsCore.component_id(resonator) == "res"
    @test SuperconductingCircuitsCore.component_pins(resonator) == [:signal]
    @test SuperconductingCircuitsCore.pin(resonator, :signal) isa PinEndpoint

    plan = CircuitPlan("macro-demo")
    register_component!(plan, resonator)

    @test haskey(plan.components, "res")
    @test haskey(plan.parameters, :capacitance)
end

@testset "@circuit expansion uses canonical APIs" begin
    expansion = macroexpand(
        @__MODULE__,
        quote
            SuperconductingCircuitsCore.@circuit "demo" begin
                res = component(
                    MinimalComponentLibrary.TestGroundedComponent("res");
                    display_name=:res,
                    role=:resonator,
                )

                port(:signal_port) do
                    index = 1
                    endpoint = SuperconductingCircuitsCore.pin(res, :signal)
                    resistance = 50.0
                    role = :mixed
                end
            end
        end;
        recursive=true,
    )

    expanded_text = sprint(show, expansion)

    @test occursin("CircuitPlan", expanded_text)
    @test occursin("register_component!", expanded_text)
    @test occursin("record_engineering_component!", expanded_text)
    @test occursin("external_port!", expanded_text)
    @test occursin("source_location", expanded_text)
    @test !occursin("record_engineering_port!", expanded_text)
end

@testset "@circuit minimal notebook pattern" begin
    plan = SuperconductingCircuitsCore.@circuit "demo" begin
        res = component(
            MinimalComponentLibrary.TestGroundedComponent("res");
            display_name=:res,
            role=:resonator,
        )

        port(:signal_port) do
            index = 1
            endpoint = SuperconductingCircuitsCore.pin(res, :signal)
            resistance = 50.0
            role = :mixed
        end
    end

    graph = SuperconductingCircuitsCore.engineering_graph(plan)

    @test haskey(plan.components, "res")
    @test haskey(plan.metadata[:external_ports], :signal_port)
    @test haskey(graph.components, :res)
    @test haskey(graph.ports, :signal_port)
    @test graph.components[:res].display_name == "res"
    @test graph.ports[:signal_port].role == :mixed
    @test hasproperty(graph.ports[:signal_port].source_location, :line)
end
