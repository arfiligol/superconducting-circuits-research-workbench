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
    @test isempty(graph.relations)

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
    @test graph.relations[end].relation_type == :feeds
end

@testset "EngineeringGraph exports DOT and canonical schematic specs" begin
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

    SCC.record_engineering_group!(
        plan;
        id=:measurement_path,
        label="Measurement path",
        role=:custom_lab_specific_group,
        members=[:signal_port, :res],
    )

    layout = SCC.schematic!(
        plan;
        id=:paper_view,
        layout_hints=Dict(:grid => :aligned_tracks),
        render_hints=Dict(:format => :renderer_neutral),
    ) do intent
        SCC.record_schematic_group!(
            intent;
            id=:schematic_readout_group,
            label="Schematic readout group",
            role=:readout_chain,
            members=[:readout_track],
        )
        SCC.record_schematic_track!(
            intent;
            id=:readout_track,
            line=:readout_line,
            orientation=:left_to_right,
            relative_order=:top,
            role=:readout_line,
            color=:blue,
        )
        SCC.record_schematic_track!(
            intent;
            id=:resonator_track,
            line=:resonator_line,
            orientation=:left_to_right,
            relative_order=:bottom,
            role=:resonator_line,
        )
        SCC.record_schematic_segment!(
            intent;
            id=:readout_left,
            track=:readout_track,
            from=0.0,
            to=1.2e-3,
            label="left",
        )
        SCC.record_schematic_coupled_span!(
            intent;
            id=:middle_window,
            relation=:signal_feeds_res,
            track1=:readout_track,
            track2=:resonator_track,
            from1=1.2e-3,
            to1=1.7e-3,
            from2=0.0,
            to2=0.5e-3,
            label="lc",
            interface_nodes=(line1_start=:A, line1_end=:B, line2_start=:C, line2_end=:D),
            render=:parallel_cpw_window,
        )
        SCC.record_schematic_terminal!(
            intent;
            id=:signal_terminal,
            endpoint=pin(component, :signal),
            track=:readout_track,
            side=:left,
            kind=:port,
            label="1",
        )
        SCC.record_schematic_node_label!(
            intent;
            id=:node_a,
            target=pin(component, :signal),
            label="A",
        )
        SCC.record_schematic_segment_label!(
            intent;
            id=:window_label,
            track=:readout_track,
            from=1.2e-3,
            to=1.7e-3,
            label="lc",
        )
        SCC.record_schematic_anchor!(
            intent;
            id=:window_center,
            target=:coupled_window_center,
            role=:report_reference,
            label="window center",
        )
    end

    graph = SCC.engineering_graph(plan)
    dot = SCC.to_dot(graph)

    @test startswith(dot, "digraph EngineeringGraph")
    @test occursin("\"signal_port\" -> \"res\"", dot)
    @test occursin("[label=\"feeds\"]", dot)

    @test layout === SCC.schematic_layout_intent(plan)
    @test layout.id == :paper_view
    @test graph.groups[:measurement_path].role == :custom_lab_specific_group
    @test !haskey(layout.groups, :measurement_path)
    @test layout.tracks[:readout_track].hints[:color] == :blue
    @test layout.coupled_spans[:middle_window].from1_m == 1.2e-3
    @test layout.anchors[:window_center].target == :coupled_window_center

    @test_throws FrameworkValidationError SCC.record_schematic_segment!(
        layout;
        id=:bad_segment,
        track=:missing_track,
        from=0.0,
        to=1.0,
    )
    @test_throws FrameworkValidationError SCC.record_schematic_coupled_span!(
        layout;
        id=:bad_same_track_span,
        relation=:signal_feeds_res,
        track1=:readout_track,
        track2=:readout_track,
        from1=0.0,
        to1=0.5e-3,
        from2=0.0,
        to2=0.5e-3,
    )
    @test_throws FrameworkValidationError SCC.record_schematic_anchor!(
        layout;
        id=:bad_anchor,
        target=pin(component, :signal),
    )

    spec = SCC.to_schematic_export_spec(plan)

    @test spec isa SCC.SchematicExportSpec
    @test spec.engineering_graph === graph
    @test spec.layout_intent === layout
    @test length(spec.components) == 1
    @test length(spec.ports) == 1
    @test length(spec.relations) == 1
    @test spec.components[1].id == :res
    @test spec.components[1].component_type == :TestGroundedComponent
    @test spec.ports[1].role == :mixed
    @test only(spec.relations).relation_type == :feeds
    @test length(spec.groups) == 2
    @test Set(group.source for group in spec.groups) == Set([:engineering_graph, :layout_intent])
    @test length(spec.tracks) == 2
    @test length(spec.segments) == 1
    @test length(spec.coupled_spans) == 1
    @test only(spec.coupled_spans).render == :parallel_cpw_window
    @test length(spec.terminals) == 1
    @test length(spec.node_labels) == 1
    @test length(spec.segment_labels) == 1
    @test length(spec.anchors) == 1
    @test spec.layout_hints[:grid] == :aligned_tracks
    @test spec.render_hints[:format] == :renderer_neutral

    data = SCC.schematic_export_data(spec)
    @test data.schema_version == 1
    @test only(data.components)["component_type"] == "TestGroundedComponent"
    @test only(data.ports)["resistance"] == 50.0
    @test data.render_hints["format"] == "renderer_neutral"

    json = SCC.schematic_export_json(spec)
    @test occursin("\"schema_version\"", json)
    @test occursin("\"component_type\": \"TestGroundedComponent\"", json)
end

@testset "Pluto 00/01/02 schematic exports carry Schemdraw render hints" begin
    common_kwargs = (
        point_count=1,
        optional_hb_kwargs=Dict{Symbol,Any}(:nbatches => 1, :iterations => 1, :ftol => 1e-8),
    )
    cases = (
        (
            example=build_parallel_lc_resonator_example(; common_kwargs...),
            component_type="GroundedLCResonator",
            branch_kind="linear",
            expected_labels=Set(["\$C_r\$", "\$L_r\$", "\$P_1\$"]),
        ),
        (
            example=build_reflective_jpa_capacitive_coupled_lc_example(;
                common_kwargs...,
                pump_current=0.0,
            ),
            component_type="CapacitivelyCoupledGroundedLCResonator",
            branch_kind="josephson",
            expected_labels=Set(["\$C_c\$", "\$C_r\$", "\$JJ\$", "\$P_1\$"]),
        ),
        (
            example=build_floating_lc_xy_line_example(; common_kwargs...),
            component_type="FloatingLCXYResonator",
            branch_kind="linear",
            expected_labels=Set(["\$C_{01}\$", "\$C_{02}\$", "\$C_r\$", "\$XY\$"]),
        ),
    )

    for case in cases
        spec = SCC.to_schematic_export_spec(case.example.plan)
        data = SCC.schematic_export_data(spec)
        schemdraw_hints = data.render_hints["schemdraw"]

        @test schemdraw_hints["component_type"] == case.component_type
        @test schemdraw_hints["parameters"]["inductive_branch_kind"] == case.branch_kind
        @test any(component -> component["component_type"] == case.component_type, data.components)
        @test all(port -> port["resistance"] == 50.0, data.ports)
        @test !isempty(data.terminals)

        labels = Set(values(schemdraw_hints["labels"]))
        @test issubset(case.expected_labels, labels)

        json = SCC.schematic_export_json(spec)
        @test occursin(case.component_type, json)
        @test occursin(case.branch_kind, json)
    end
end
