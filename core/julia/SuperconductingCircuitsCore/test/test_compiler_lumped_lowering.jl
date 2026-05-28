function lumped_fixture_plan()
    plan = CircuitPlan("lumped-mvp")
    lc = register_component!(plan, MinimalComponentLibrary.TestGroundedComponent("lc"))
    drive = external_node("drive")

    connect!(plan, pin(lc, :signal), drive)
    couple_capacitive!(
        plan;
        id="lc_to_ground",
        from=pin(lc, :signal),
        to=ground(),
        capacitance=80.0e-15,
    )
    shunt_capacitor!(
        plan;
        id="drive_shunt",
        at=pin(lc, :signal),
        capacitance=20.0e-15,
    )
    shunt_inductor!(
        plan;
        id="drive_shunt_l",
        at=pin(lc, :signal),
        inductance=8.0e-9,
    )

    return plan, lc, drive
end

@testset "lumped compiler lowers supported relations" begin
    plan, lc, drive = lumped_fixture_plan()

    compiled = compile_to_josephson(plan)

    @test compiled isa JosephsonCompiledCircuit
    @test length(compiled.netlist) == 3
    @test all(row -> row isa Tuple && length(row) == 4, compiled.netlist)
    @test ("C_lc_to_ground", "ext_drive", "0", :C_lc_to_ground) in compiled.netlist
    @test ("C_drive_shunt", "ext_drive", "0", :C_drive_shunt) in compiled.netlist
    @test ("L_drive_shunt_l", "ext_drive", "0", :L_drive_shunt_l) in compiled.netlist

    @test compiled.node_map[pin(lc, :signal)] == "ext_drive"
    @test compiled.node_map[drive] == "ext_drive"
    @test compiled.node_map[ground()] == "0"

    @test compiled.component_map["lc"] == [1, 2, 3]
    relation_map = compiled.provenance[:relation_map]
    @test relation_map["lc_to_ground"] == [1]
    @test relation_map["drive_shunt"] == [2]
    @test relation_map["drive_shunt_l"] == [3]

    @test compiled.component_values[:C_lc_to_ground] == 80.0e-15
    @test compiled.component_values[:C_drive_shunt] == 20.0e-15
    @test compiled.component_values[:L_drive_shunt_l] == 8.0e-9
    @test topology_key(compiled) isa TopologyKey
    @test compiled.metadata[:netlist_row_count] == 3
    @test !any(warning -> occursin("skeleton", lowercase(warning)), compiled.warnings)
end

@testset "lumped compiler fails clearly on unsupported relation paths" begin
    plan = CircuitPlan("unsupported-window")
    line_a = register_component!(plan, MinimalComponentLibrary.TestLineComponent("line_a", [:main], :main))
    line_b = register_component!(plan, MinimalComponentLibrary.TestLineComponent("line_b", [:main], :main))
    couple_window!(
        plan;
        id="window",
        line_a=line_span(line_a; from_m=0.1mm, to_m=0.2mm),
        line_b=line_span(line_b; from_m=0.1mm, to_m=0.2mm),
        spec=base_window_spec(length_m=0.1mm),
    )

    try
        compile_to_josephson(plan)
        @test false
    catch err
        @test err isa FrameworkValidationError
        @test occursin("not supported", sprint(showerror, err))
        @test occursin("CoupledWindowRelation", sprint(showerror, err))
    end

    flux_plan = CircuitPlan("unsupported-mutual")
    line = register_component!(flux_plan, MinimalComponentLibrary.TestLineComponent("line", [:main], :main))
    loop_owner = register_component!(flux_plan, MinimalComponentLibrary.TestGroundedComponent("loop_owner"))
    couple_inductive!(
        flux_plan;
        id="flux",
        from=line_tap(line; at_m=0.1mm),
        to=loop_endpoint(loop_owner, :loop),
        mutual_inductance=3.0e-12,
    )

    try
        compile_to_josephson(flux_plan)
        @test false
    catch err
        @test err isa FrameworkValidationError
        @test occursin("not supported", sprint(showerror, err))
        @test occursin("InductiveCoupling", sprint(showerror, err))
    end
end
