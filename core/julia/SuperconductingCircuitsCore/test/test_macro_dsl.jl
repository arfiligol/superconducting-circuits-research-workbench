using Test
using SuperconductingCircuitsCore

@testset "@circuit_component exposes explicit public interface" begin
    lc_resonator! = @circuit_component "lc_resonator" begin
        pin :signal
        probe :debug_node
        anchor :schematic_center

        parameter(:capacitance; unit="F")
        parameter(:inductance; unit="H")

        shunt_capacitor!(
            id=:Cres,
            at=pin(:signal),
            capacitance=capacitance,
            role=:resonator_capacitance,
        )
        shunt_inductor!(
            id=:Lres,
            at=pin(:signal),
            inductance=inductance,
            role=:resonator_inductance,
        )
    end

    plan = CircuitPlan("component-macro")
    drive = external_node("drive")
    instance = lc_resonator!(
        plan;
        id=:res,
        signal=drive,
        capacitance=58.2e-15,
        inductance=21.5e-9,
    )

    @test instance isa CircuitComponentInstance
    @test component_id(instance) == "res"
    @test pin(instance, :signal) == drive
    @test probe(instance, :debug_node) isa ProbeEndpoint
    @test anchor(instance, :schematic_center) isa AnchorRef
    @test component_pins(instance) == [:signal]
    @test Set(relation.id for relation in plan.relations if hasproperty(relation, :id)) ==
          Set(["res_Cres", "res_Lres"])
    @test haskey(engineering_graph(plan).components, :res)
    @test_throws FrameworkValidationError couple_capacitive!(
        plan;
        id=:bad_anchor_coupling,
        from=anchor(instance, :schematic_center),
        to=drive,
        capacitance=1e-15,
    )
end

@testset "@circuit expansion calls canonical APIs" begin
    expansion = macroexpand(
        @__MODULE__,
        quote
            SuperconductingCircuitsCore.@circuit "macro-demo" begin
                drive = external_node("drive")
                shunt_capacitor!(
                    id=:Cdrive,
                    at=drive,
                    capacitance=1e-12,
                )

                port(:drive_port) do
                    index = 1
                    endpoint = drive
                    resistance = 50.0
                    role = :probe
                end

                group(:measurement_path) do
                    label = "Measurement path"
                    role = :user_defined_role
                    members = [:drive_port]
                end
            end
        end;
        recursive=true,
    )

    expanded_text = sprint(show, expansion)

    @test occursin("CircuitPlan", expanded_text)
    @test occursin("shunt_capacitor!", expanded_text)
    @test occursin("external_port!", expanded_text)
    @test occursin("record_engineering_group!", expanded_text)
    @test !occursin("component" * "(", expanded_text)
end

@testset "@circuit builds runnable plan with primitive, port, group, and schematic layout" begin
    plan = SuperconductingCircuitsCore.@circuit "primitive-plan" begin
        drive = external_node("drive")
        shunt_capacitor!(
            id=:Cdrive,
            at=drive,
            capacitance=1e-12,
        )

        port(:drive_port) do
            index = 1
            endpoint = drive
            resistance = 50.0
            role = :probe
        end

        group(:measurement_path) do
            label = "Measurement path"
            role = :measurement_path
            members = [:drive_port]
        end

        schematic!(:paper_view) do
            track(:drive_track) do
                line = :drive_line
                orientation = :left_to_right
                relative_order = :top
            end
            terminal(:drive_terminal) do
                endpoint = drive
                track = :drive_track
                side = :left
                kind = :port
                label = "1"
            end
        end
    end

    graph = engineering_graph(plan)
    layout = schematic_layout_intent(plan)

    @test haskey(graph.ports, :drive_port)
    @test graph.ports[:drive_port].role == :probe
    @test haskey(graph.groups, :measurement_path)
    @test graph.groups[:measurement_path].role == :measurement_path
    @test haskey(layout.tracks, :drive_track)
    @test haskey(layout.terminals, :drive_terminal)
    @test validate_authoring(plan).issues == ValidationIssue[]
end

@testset "@hbintent is plan-bound and port-role neutral" begin
    plan = SuperconductingCircuitsCore.@circuit "hb-plan" begin
        drive = external_node("drive")
        shunt_capacitor!(id=:Cdrive, at=drive, capacitance=1e-12)

        port(:probe_port) do
            index = 1
            endpoint = drive
            resistance = 50.0
            role = :probe
        end
    end

    @hbintent plan begin
        pump_axis(:pump; frequency_parameter=:pump_frequency)
        source_slot(:pump_in) do
            role = :pump
            port = :probe_port
            mode = (1,)
            current_parameter = :pump_current
        end
        sparameter(:s11) do
            outputmode = (0,)
            outputport = :probe_port
            inputmode = (0,)
            inputport = :probe_port
        end
    end

    @test validate_hb_intent(plan).issues == ValidationIssue[]
    @test length(plan.metadata[:hb_intent].source_slots) == 1
    @test length(plan.metadata[:hb_intent].observables) == 1

    invalid = CircuitPlan("invalid-hb")
    external_port!(
        invalid;
        id=:existing,
        index=1,
        endpoint=external_node("existing"),
        resistance=50.0,
        role=:probe,
    )
    @hbintent invalid begin
        pump_axis(:pump; frequency_parameter=:pump_frequency)
        source_slot(:missing) do
            role = :pump
            port = :missing_port
            mode = (1,)
            current_parameter = :pump_current
        end
    end

    report = validate_hb_intent(invalid)
    @test has_errors(report)
    @test any(issue -> issue.code == :unknown_source_slot_port, errors(report))
end
