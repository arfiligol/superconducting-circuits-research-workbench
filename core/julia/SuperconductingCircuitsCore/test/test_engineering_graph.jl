using SuperconductingCircuitsCore
using Test

const SCC = SuperconductingCircuitsCore

@testset "EngineeringGraph records plan-level semantics" begin
    plan = CircuitPlan("engineering-graph")
    component = register_component!(
        plan,
        MinimalComponentLibrary.TestGroundedComponent("res");
        display_name=:res,
        role=:resonator,
    )

    graph = SCC.engineering_graph(plan)

    @test graph isa SCC.EngineeringGraph
    @test plan.engineering_graph === graph
    @test haskey(graph.components, :res)

    recorded_component = graph.components[:res]
    @test recorded_component isa SCC.EngineeringComponent
    @test recorded_component.display_name == "res"
    @test recorded_component.component_type == :TestGroundedComponent
    @test recorded_component.role == :resonator
    @test recorded_component.pins == [:signal]
    @test haskey(recorded_component.parameters, :capacitance)

    port = external_port!(
        plan;
        id=:signal_port,
        endpoint=pin(component, :signal),
        index=1,
        role=:mixed,
        resistance=50,
    )

    @test port isa SCC.EngineeringPort
    @test graph.ports[:signal_port].component == :res
    @test graph.ports[:signal_port].port_index == 1
    @test graph.ports[:signal_port].resistance == 50.0

    group = SCC.record_engineering_group!(
        plan;
        id=:readout_chain,
        label="Readout chain",
        role=:readout,
        members=[:signal_port, :res],
    )

    @test group isa SCC.EngineeringGroup
    @test graph.groups[:readout_chain].members == [:signal_port, :res]

    relation = SCC.record_engineering_relation!(
        plan;
        id=:signal_feeds_res,
        relation_type=:feeds,
        from=:signal_port,
        to=pin(component, :signal),
        role=:readout_feed,
        label="feeds",
    )

    @test relation isa SCC.EngineeringRelation
    @test length(graph.relations) == 1
    @test graph.relations[1].relation_type == :feeds
end

@testset "EngineeringGraph exports DOT and schematic specs" begin
    plan = CircuitPlan("schematic-export")
    component = register_component!(
        plan,
        MinimalComponentLibrary.TestGroundedComponent("res");
        display_name=:res,
        role=:resonator,
    )
    external_port!(
        plan;
        id=:signal_port,
        endpoint=pin(component, :signal),
        index=1,
        role=:mixed,
        resistance=50.0,
    )
    SCC.record_engineering_relation!(
        plan;
        id=:signal_feeds_res,
        relation_type=:feeds,
        from=:signal_port,
        to=pin(component, :signal),
        role=:readout_feed,
        label="feeds",
    )

    graph = SCC.engineering_graph(plan)
    dot = SCC.to_dot(graph)

    @test startswith(dot, "digraph EngineeringGraph")
    @test occursin("\"signal_port\" -> \"res\"", dot)
    @test occursin("[label=\"feeds\"]", dot)

    spec = SCC.to_schemdraw_spec(graph)

    @test spec isa SCC.SchematicExportSpec
    @test length(spec.components) == 1
    @test length(spec.ports) == 1
    @test length(spec.relations) == 1
    @test spec.components[1].id == :res
    @test spec.components[1].schematic_kind == :TestGroundedComponent
    @test spec.ports[1].role == :mixed
    @test spec.relations[1].schematic_kind == :feeds
    @test spec.render_hints[:renderer] == :schemdraw
end
