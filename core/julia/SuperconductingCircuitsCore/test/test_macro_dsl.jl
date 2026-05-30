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

    @test lc_resonator! isa CircuitComponentBuilder
    @test component_builder_allowed_keywords(lc_resonator!) == [:signal, :capacitance, :inductance]

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

    keyword_error = try
        lc_resonator!(
            CircuitPlan("component-keyword-error");
            id=:bad,
            singal=drive,
            capacitance=58.2e-15,
            inductance=21.5e-9,
        )
    catch err
        err
    end
    @test keyword_error isa FrameworkValidationError
    keyword_message = sprint(showerror, keyword_error)
    @test occursin("lc_resonator", keyword_message)
    @test occursin("singal", keyword_message)
    @test occursin("signal", keyword_message)
    @test occursin("capacitance", keyword_message)

    parameter_error = try
        lc_resonator!(
            CircuitPlan("component-parameter-error");
            id=:bad,
            signal=drive,
            capacotance=58.2e-15,
            inductance=21.5e-9,
        )
    catch err
        err
    end
    @test parameter_error isa FrameworkValidationError
    @test occursin("capacotance", sprint(showerror, parameter_error))

    missing_error = try
        lc_resonator!(
            CircuitPlan("component-missing-parameter");
            id=:bad,
            signal=drive,
            inductance=21.5e-9,
        )
    catch err
        err
    end
    @test missing_error isa FrameworkValidationError
    missing_message = sprint(showerror, missing_error)
    @test occursin("lc_resonator", missing_message)
    @test occursin("capacitance", missing_message)
    @test occursin("Allowed keywords", missing_message)
end

@testset "@circuit_component line declarations expose distance taps" begin
    single_line! = @circuit_component "single_line" begin
        line :main
        parameter(:length_m; unit="m")
    end
    multi_line! = @circuit_component "multi_line" begin
        line(:main)
        line(:auxiliary)
        parameter(:length_m; unit="m")
    end

    single = single_line!(CircuitPlan("single-line"); id=:line, length_m=1.0e-3)
    @test component_lines(single) == [:main]
    single_tap = tap(single, 0.25e-3)
    @test single_tap isa LineTapEndpoint
    @test single_tap.line_ref == LineRef("line", :main)
    @test single_tap.at_m == 0.25e-3

    multi = multi_line!(CircuitPlan("multi-line"); id=:multi, length_m=2.0e-3)
    @test component_lines(multi) == [:auxiliary, :main]
    @test_throws FrameworkValidationError tap(multi, 0.25e-3)
    selected = line_tap(multi; line=:auxiliary, at_m=0.25e-3)
    @test selected.line_ref == LineRef("multi", :auxiliary)
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

@testset "@circuit grammar accepts canonical calls and component builders only" begin
    local_lc! = @circuit_component "local_lc" begin
        pin :signal
        parameter(:capacitance; unit="F")
        parameter(:inductance; unit="H")

        shunt_capacitor!(id=:C, at=pin(:signal), capacitance=capacitance)
        shunt_inductor!(id=:L, at=pin(:signal), inductance=inductance)
    end

    plan = SuperconductingCircuitsCore.@circuit "component-builder-plan" begin
        drive = external_node("drive")
        res = local_lc!(
            id=:res,
            signal=drive,
            capacitance=58.2e-15,
            inductance=21.5e-9,
        )
        shunt_capacitor!(id=:Cdrive, at=pin(res, :signal), capacitance=1e-15)
    end

    @test haskey(plan.components, "res")
    @test Set(relation.id for relation in plan.relations if hasproperty(relation, :id)) ==
          Set(["res_C", "res_L", "Cdrive"])

    push_error = try
        SuperconductingCircuitsCore.@circuit "bad-push" begin
            values = Int[]
            push!(values, 1)
        end
    catch err
        err
    end
    @test push_error isa FrameworkValidationError
    @test occursin("Unsupported @circuit statement", sprint(showerror, push_error))

    unsupported_error = try
        Core.eval(
            @__MODULE__,
            quote
                SuperconductingCircuitsCore.@circuit "bad-expression" begin
                    if true
                        nothing
                    end
                end
            end
        )
    catch err
        err
    end
    @test unsupported_error isa LoadError || unsupported_error isa ErrorException
    @test occursin("Unsupported @circuit statement", sprint(showerror, unsupported_error))
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
    probe_only = SuperconductingCircuitsCore.@circuit "probe-role-only" begin
        drive = external_node("drive")
        shunt_capacitor!(id=:Cdrive, at=drive, capacitance=1e-12)

        port(:probe_port) do
            index = 1
            endpoint = drive
            resistance = 50.0
            role = :probe
        end
    end

    @test !haskey(probe_only.metadata, :hb_intent)

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
        solver_controls() do
            n_pump_harmonics = 3
            n_modulation_harmonics = 2
            returnS = true
            returnZ = true
            returnQE = false
            returnCM = false
            keyedarrays = false
        end
    end

    @test validate_hb_intent(plan).issues == ValidationIssue[]
    @test length(plan.metadata[:hb_intent].source_slots) == 1
    @test length(plan.metadata[:hb_intent].observables) == 1
    @test plan.metadata[:hb_intent].default_solver_controls.n_pump_harmonics == 3
    @test plan.metadata[:hb_intent].default_solver_controls.n_modulation_harmonics == 2
    @test plan.metadata[:hb_intent].default_solver_controls.returnQE == false
    @test plan.metadata[:hb_intent].default_solver_controls.returnCM == false

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
