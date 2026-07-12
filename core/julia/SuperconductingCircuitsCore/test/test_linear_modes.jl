function closed_two_mode_plan(; physical_on)
    plan = CircuitPlan(physical_on ? "closed-two-mode-on" : "closed-two-mode-off")
    q = external_node("q")
    r = external_node("r")
    c_q = 100.0e-15
    c_r = 180.0e-15
    c_c = 12.0e-15
    shunt_capacitor!(
        plan;
        id="q_capacitance",
        at=q,
        capacitance=c_q + (physical_on ? 0.0 : c_c),
    )
    shunt_capacitor!(
        plan;
        id="r_capacitance",
        at=r,
        capacitance=c_r + (physical_on ? 0.0 : c_c),
    )
    physical_on && couple_capacitive!(
        plan;
        id="physical_coupling",
        from=q,
        to=r,
        capacitance=c_c,
    )
    shunt_inductor!(plan; id="q_inductance", at=q, inductance=11.0e-9)
    shunt_inductor!(plan; id="r_inductance", at=r, inductance=4.0e-9)
    return plan
end

function floating_common_pair_plan(; physical_on)
    plan = CircuitPlan(physical_on ? "floating-common-on" : "floating-common-off")
    q1 = external_node("q1")
    q2 = external_node("q2")
    r = external_node("r")
    c01 = 90.0e-15
    c02 = 110.0e-15
    c12 = 35.0e-15
    cr1 = 14.0e-15
    cr2 = 2.0e-15
    total = c01 + c02 + cr1 + cr2
    readout_attachment = cr1 + cr2 - (cr1 + cr2)^2 / total
    shunt_capacitor!(
        plan;
        id="q1_ground",
        at=q1,
        capacitance=c01 + (physical_on ? 0.0 : cr1),
    )
    shunt_capacitor!(
        plan;
        id="q2_ground",
        at=q2,
        capacitance=c02 + (physical_on ? 0.0 : cr2),
    )
    couple_capacitive!(plan; id="q_mutual", from=q1, to=q2, capacitance=c12)
    if physical_on
        couple_capacitive!(plan; id="cr1", from=r, to=q1, capacitance=cr1)
        couple_capacitive!(plan; id="cr2", from=r, to=q2, capacitance=cr2)
    else
        shunt_capacitor!(
            plan;
            id="readout_attachment",
            at=r,
            capacitance=readout_attachment,
        )
    end
    series_inductor!(plan; id="qubit_inductance", from=q1, to=q2, inductance=8.0e-9)
    shunt_inductor!(plan; id="readout_inductance", at=r, inductance=5.0e-9)
    return plan
end

@testset "closed linear nodal extraction and modal projection" begin
    off = extract_linear_nodal_model(compile_to_josephson(closed_two_mode_plan(physical_on=false)))
    on = extract_linear_nodal_model(compile_to_josephson(closed_two_mode_plan(physical_on=true)))
    @test off.node_names == ["ext_q", "ext_r"]
    @test off.provenance.contract_id == "closed-linear-nodal-model-v1"
    @test length(off.source_sha256) == 64
    @test off.inverse_inductance == on.inverse_inductance

    reduced = reduce_linear_model_pair(off, on)
    @test size(reduced.coupling_off.free_charge_basis, 2) == 0
    off_modes = solve_generalized_modes(reduced.coupling_off)
    on_modes = solve_generalized_modes(reduced.physical_on)
    @test maximum(off_modes.residuals) < 1.0e-12
    @test off_modes.c_orthogonality_error < 1.0e-12
    @test off_modes.frequencies_hz ≈ sort([
        1 / (2π * sqrt(11.0e-9 * 112.0e-15)),
        1 / (2π * sqrt(4.0e-9 * 192.0e-15)),
    ])

    projection = project_selected_modes(off_modes, reduced.physical_on, [1, 2])
    closure = linear_projection_closure(projection, on_modes.frequencies_hz)
    @test abs(projection.coupling_matrix_hz[1, 2]) > 0
    @test closure.max_abs_bdg_residual_hz < 1.0e-3
    @test closure.max_abs_rwa_minus_bdg_hz > 0
    @test projection.number_conserving_matrix_rad_s ≈
        transpose(projection.number_conserving_matrix_rad_s)
    @test projection.pairing_matrix_rad_s ≈ transpose(projection.pairing_matrix_rad_s)
end

@testset "closed source provenance binds sorted component rows to their values" begin
    capacitance = 1.25e-12
    inductance = 7.5e-9
    unsorted_rows = Any[
        ("L_z_inductance", "a", "0", :L_value),
        ("C_a_capacitance", "a", "0", :C_value),
    ]
    values = Dict{Symbol,Any}(:C_value => capacitance, :L_value => inductance)
    unsorted = JosephsonCompiledCircuit(
        netlist=unsorted_rows,
        component_values=values,
    )
    reordered = JosephsonCompiledCircuit(
        netlist=reverse(unsorted_rows),
        component_values=values,
    )
    unsorted_model = extract_linear_nodal_model(unsorted)
    reordered_model = extract_linear_nodal_model(reordered)
    expected = SuperconductingCircuitsCore._linear_sha256(String[
        "compiled-closed-linear-source-v2",
        "rows=2",
        "row=1",
        "name=C_a_capacitance",
        "node_a=a",
        "node_b=0",
        "value=$(bitstring(capacitance))",
        "row=2",
        "name=L_z_inductance",
        "node_a=a",
        "node_b=0",
        "value=$(bitstring(inductance))",
    ])
    wrong_row_value_binding = SuperconductingCircuitsCore._linear_sha256(String[
        "compiled-closed-linear-source-v2",
        "rows=2",
        "row=1",
        "name=C_a_capacitance",
        "node_a=a",
        "node_b=0",
        "value=$(bitstring(inductance))",
        "row=2",
        "name=L_z_inductance",
        "node_a=a",
        "node_b=0",
        "value=$(bitstring(capacitance))",
    ])
    @test unsorted_model.source_sha256 == expected
    @test reordered_model.source_sha256 == expected
    @test unsorted_model.source_sha256 != wrong_row_value_binding
end

@testset "floating free-charge coordinate is Schur reduced in one shared frame" begin
    off = extract_linear_nodal_model(compile_to_josephson(floating_common_pair_plan(physical_on=false)))
    on = extract_linear_nodal_model(compile_to_josephson(floating_common_pair_plan(physical_on=true)))
    reduced = reduce_linear_model_pair(off, on)
    @test size(reduced.coupling_off.free_charge_basis, 2) == 1
    @test reduced.coupling_off.free_charge_constraint_residual < 1.0e-12
    @test reduced.physical_on.free_charge_constraint_residual < 1.0e-12
    @test [reduced.coupling_off.capacitance[index, index] for index in 1:2] ≈
        [reduced.physical_on.capacitance[index, index] for index in 1:2]
    @test abs(reduced.coupling_off.capacitance[1, 2]) < 1.0e-24
    @test abs(reduced.physical_on.capacitance[1, 2]) > 1.0e-15

    off_modes = solve_generalized_modes(reduced.coupling_off)
    on_modes = solve_generalized_modes(reduced.physical_on)
    projection = project_selected_modes(off_modes, reduced.physical_on, [1, 2])
    closure = linear_projection_closure(projection, on_modes.frequencies_hz)
    @test closure.max_abs_bdg_residual_hz < 1.0e-3
end

@testset "closed linear extraction fails fast outside its conservative v1 scope" begin
    resistor = CircuitPlan("closed-resistor")
    resistor_node = external_node("resistor_node")
    shunt_capacitor!(resistor; id="c", at=resistor_node, capacitance=1.0e-12)
    shunt_inductor!(resistor; id="l", at=resistor_node, inductance=1.0e-9)
    series_resistor!(
        resistor;
        id="r",
        from=resistor_node,
        to=ground(),
        resistance=50.0,
    )
    @test_throws FrameworkValidationError extract_linear_nodal_model(
        compile_to_josephson(resistor),
    )

    nonlinear = CircuitPlan("closed-nonlinear")
    nonlinear_node = external_node("nonlinear_node")
    shunt_capacitor!(nonlinear; id="c", at=nonlinear_node, capacitance=1.0e-12)
    josephson_junction!(
        nonlinear;
        id="jj",
        from=nonlinear_node,
        to=ground(),
        josephson_inductance=1.0e-9,
    )
    @test_throws FrameworkValidationError extract_linear_nodal_model(
        compile_to_josephson(nonlinear),
    )

    singular = JosephsonCompiledCircuit(
        netlist=Any[
            ("C_between", "a", "b", :C_between),
            ("L_between", "a", "b", :L_between),
            ("C_ground_marker", "a", "0", :C_ground_marker),
        ],
        component_values=Dict{Symbol,Any}(
            :C_between => 1.0e-12,
            :L_between => 1.0e-9,
            :C_ground_marker => 0.0,
        ),
    )
    @test_throws FrameworkValidationError extract_linear_nodal_model(singular)

    complex_value = JosephsonCompiledCircuit(
        netlist=Any[
            ("C_ground", "a", "0", :C_ground),
            ("L_ground", "a", "0", :L_ground),
        ],
        component_values=Dict{Symbol,Any}(
            :C_ground => 1.0e-12 + 1.0e-15im,
            :L_ground => 1.0e-9,
        ),
    )
    @test_throws FrameworkValidationError extract_linear_nodal_model(complex_value)
end
