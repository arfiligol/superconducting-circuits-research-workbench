using Test

include(joinpath(@__DIR__, "src", "QubitExternalCouplingAnalysis.jl"))
using .QubitExternalCouplingAnalysis

const fF_smoke = 1e-15
const nH_smoke = 1e-9
const um_smoke = 1e-6

function smoke_line(length_m; n_sections=12)
    return RLGCSpec(
        length_m=length_m,
        n_sections=n_sections,
        l_per_m_h=404.313e-9,
        c_per_m_f=179.86e-12,
    )
end

function smoke_window(length_m; n_sections=4)
    return CoupledWindowSpec(
        length_m=length_m,
        n_sections=n_sections,
        l11_per_m_h=410.0e-9,
        l22_per_m_h=410.0e-9,
        lm_per_m_h=18.0e-9,
        c1g_per_m_f=170.0e-12,
        c2g_per_m_f=170.0e-12,
        cm_per_m_f=8.0e-12,
    )
end

@testset "framework v1 smoke" begin
    @testset "learn happy path" begin
        draft = CircuitDraft("qwr_lc")
        qwr = quarter_wave_resonator!(draft, "qwr"; line=smoke_line(1.0e-3), boundary=:short)
        lc = lc_resonator!(draft, "lc"; L=8.0 * nH_smoke, C=120.0 * fF_smoke)

        @test qwr isa QuarterWaveResonatorComponent
        @test lc isa LCResonatorComponent
        couple_capacitive!(draft, tap(qwr, 0.25), pin(lc, :plus); C=1.5 * fF_smoke, id="qwr_lc")
        connect_pins!(draft, pin(lc, :minus), ground(); id="lc_ground")

        artifact = finalize_circuit(draft)
        @test length(artifact.netlist) == length(artifact.provenance_table)
        @test any(row -> row[1] == "C_qwr_lc_coupling", artifact.netlist)
        @test haskey(artifact.segmentation_plan.lines, "qwr__main")
        coupling_record = only(filter(record -> record.generated_name == "C_qwr_lc_coupling", artifact.provenance_table))
        @test coupling_record.row_index > 0
        @test coupling_record.primitive_kind == :C
        @test coupling_record.relation_id == "qwr_lc"
        @test coupling_record.parameter_owner == :relation
        @test coupling_record.parameter_snapshot[:capacitance_f] == 1.5 * fF_smoke
    end

    @testset "two qubits with buses and tunable coupler" begin
        draft = CircuitDraft("two_qubits")

        q1 = lc_qubit!(draft, "q1"; L=9.0 * nH_smoke, C=90.0 * fF_smoke)
        q2 = lc_qubit!(draft, "q2"; L=9.5 * nH_smoke, C=88.0 * fF_smoke)
        coupler = tunable_coupler!(draft, "tc"; L=4.0 * nH_smoke, C=150.0 * fF_smoke)
        bus_a = cpw_line!(draft, "bus_a"; line=smoke_line(1.2e-3))
        bus_b = cpw_line!(draft, "bus_b"; line=smoke_line(1.2e-3))

        @test q1 isa LCQubitComponent
        @test q2 isa LCQubitComponent
        @test coupler isa TunableCouplerComponent
        @test bus_a isa CPWLineComponent
        @test bus_b isa CPWLineComponent
        connect_pins!(draft, pin(q1, :minus), ground(); id="q1_ground")
        connect_pins!(draft, pin(q2, :minus), ground(); id="q2_ground")
        couple_capacitive!(draft, pin(q1, :pad), tap(bus_a, 0.20); C=2.0 * fF_smoke, id="q1_bus")
        couple_capacitive!(draft, pin(q2, :pad), tap(bus_b, 0.80); C=2.0 * fF_smoke, id="q2_bus")
        couple_capacitive!(draft, tap(bus_a, 0.50), pin(coupler, :left); C=1.0 * fF_smoke, id="bus_a_tc")
        couple_capacitive!(draft, tap(bus_b, 0.50), pin(coupler, :right); C=1.0 * fF_smoke, id="bus_b_tc")

        artifact = finalize_circuit(draft)
        @test length(artifact.netlist) == length(artifact.provenance_table)
        @test any(row -> row[1] == "C_q1_bus_coupling", artifact.netlist)
        @test any(row -> row[1] == "C_bus_a_tc_coupling", artifact.netlist)
    end

    @testset "mtl coupled window" begin
        draft = CircuitDraft("mtl")
        readout = cpw_line!(draft, "readout"; line=smoke_line(1.0e-3))
        filter = cpw_line!(draft, "filter"; line=smoke_line(1.0e-3))

        coupled_window!(
            draft,
            section(readout, 0.30, 0.40),
            section(filter, 0.55, 0.65);
            spec=smoke_window(100.0 * um_smoke),
            id="window",
        )

        artifact = finalize_circuit(draft)
        @test any(row -> startswith(row[1], "K_window"), artifact.netlist)
        @test any(record -> record.role == :relation_mtl_cross_C, artifact.provenance_table)
        mtl_record = first(Base.filter(record -> record.relation_id == "window" && record.role == :relation_mtl_cross_C, artifact.provenance_table))
        @test sort(mtl_record.component_ids) == ["filter", "readout"]
        @test mtl_record.parameter_snapshot[:length_m] == 100.0 * um_smoke
    end

    @testset "absolute tap and section coordinates" begin
        draft_fraction = CircuitDraft("fraction_coords")
        line_fraction = cpw_line!(draft_fraction, "line"; line=smoke_line(1.0e-3))
        q_fraction = lc_qubit!(draft_fraction, "q"; L=8.0 * nH_smoke, C=90.0 * fF_smoke)
        couple_capacitive!(draft_fraction, tap(line_fraction, 0.25), pin(q_fraction, :pad); C=1.0 * fF_smoke, id="tap")
        artifact_fraction = finalize_circuit(draft_fraction)

        draft_meter = CircuitDraft("meter_coords")
        line_meter = cpw_line!(draft_meter, "line"; line=smoke_line(1.0e-3))
        q_meter = lc_qubit!(draft_meter, "q"; L=8.0 * nH_smoke, C=90.0 * fF_smoke)
        couple_capacitive!(draft_meter, tap_m(line_meter, 250.0 * um_smoke), pin(q_meter, :pad); C=1.0 * fF_smoke, id="tap")
        artifact_meter = finalize_circuit(draft_meter)

        @test artifact_fraction.segmentation_plan.lines["line__main"].breakpoints_m ≈ artifact_meter.segmentation_plan.lines["line__main"].breakpoints_m

        draft_window = CircuitDraft("meter_window")
        line_a = cpw_line!(draft_window, "line_a"; line=smoke_line(1.0e-3))
        line_b = cpw_line!(draft_window, "line_b"; line=smoke_line(1.0e-3))
        coupled_window!(
            draft_window,
            section_m(line_a, 300.0 * um_smoke, 400.0 * um_smoke),
            section_m(line_b, 550.0 * um_smoke, 650.0 * um_smoke);
            spec=smoke_window(100.0 * um_smoke),
            id="window",
        )
        @test any(record -> record.relation_id == "window", finalize_circuit(draft_window).provenance_table)
    end

    @testset "current study builds with v1 API" begin
        cfg = StudyConfig()
        context = QubitExternalCouplingAnalysis.build_floating_qubit_environment_netlist(cfg)
        @test length(context.symbolic_netlist) > 0
        @test length(context.symbolic_artifact.netlist) == length(context.symbolic_artifact.provenance_table)
        @test any(row -> row[1] == "P1", context.symbolic_netlist)
        @test any(row -> startswith(row[1], "K_pf_qwr_window"), context.symbolic_netlist)
        @test any(record -> record.relation_id == "pf_qwr_window" && length(record.component_ids) == 2, context.symbolic_artifact.provenance_table)
    end

    @testset "finalization is non-destructive" begin
        draft = CircuitDraft("nondestructive")
        bus = cpw_line!(draft, "bus"; line=smoke_line(1.0e-3))
        port = external_pin!(draft, "port")
        connect_pins!(draft, pin(bus, :left), pin(port, :node); id="bus_port")
        terminated_port!(draft, pin(port, :node); port_number=1, id="port1")

        first = finalize_circuit(draft)
        second = finalize_circuit(draft)
        @test first.netlist == second.netlist
        @test length(first.provenance_table) == length(second.provenance_table)
    end

    @testset "semantic design sweeps" begin
        draft = CircuitDraft("sweep")
        q1 = lc_qubit!(draft, "q1"; L=8.0 * nH_smoke, C=90.0 * fF_smoke)
        q2 = lc_qubit!(draft, "q2"; L=8.5 * nH_smoke, C=91.0 * fF_smoke)
        bus = cpw_line!(draft, "bus"; line=smoke_line(1.0e-3))
        couple_capacitive!(draft, pin(q1, :pad), tap(bus, 0.25); C=1.0 * fF_smoke, id="q1_bus")
        couple_capacitive!(draft, pin(q2, :pad), tap(bus, 0.75); C=1.2 * fF_smoke, id="q2_bus")

        axis_c = sweep_relation("q1_bus", :capacitance_f, [1.0, 2.0] .* fF_smoke; label="Cq1 bus", unit="F")
        axis_l = sweep_component("q1", :L_h, [8.0, 9.0, 10.0] .* nH_smoke; label="q1 L", unit="H")
        plan = sweep_plan(axis_c, axis_l)
        @test design_sweep_point_count(plan) == 6

        point = sweep_point(plan, 4)
        patched = apply_sweep_point(draft, point)
        @test patched !== draft
        @test draft.components["q1"] !== patched.components["q1"]
        @test draft.components["q1"].L_h == 8.0 * nH_smoke
        @test patched.components["q1"].L_h != draft.components["q1"].L_h

        df = run_design_sweep(
            draft,
            plan;
            evaluator=(patched_draft, artifact, point) -> Dict(:row_count => length(artifact.netlist)),
        )
        @test size(df, 1) == 6
        @test all(df.success)

        linked_axis = sweep_parameters(
            [
                component_parameter("q1", :C_f) => (value -> value),
                component_parameter("q2", :C_f) => (value -> value * 1.1),
            ];
            values=[80.0, 90.0] .* fF_smoke,
            label="linked capacitance",
            unit="F",
        )
        linked_point = sweep_point(sweep_plan(linked_axis), 1)
        linked_draft = apply_sweep_point(draft, linked_point)
        @test linked_draft.components["q1"].C_f == 90.0 * fF_smoke
        @test linked_draft.components["q2"].C_f ≈ 99.0 * fF_smoke

        bad_axis = sweep_component("q1", :L_h, [-1.0 * nH_smoke]; label="bad L", unit="H")
        bad_df = run_design_sweep(draft, sweep_plan(bad_axis); on_error=:record)
        @test size(bad_df, 1) == 1
        @test bad_df.success[1] == false
    end

    @testset "rejection cases" begin
        draft = CircuitDraft("rejections")
        line_a = cpw_line!(draft, "line_a"; line=smoke_line(1.0e-3))
        line_b = cpw_line!(draft, "line_b"; line=smoke_line(1.0e-3))
        q = lc_qubit!(draft, "q"; L=8.0 * nH_smoke, C=90.0 * fF_smoke)

        @test_throws FrameworkValidationError pin(q, :missing)
        @test_throws FrameworkValidationError cpw_line!(draft, "line_a"; line=smoke_line(1.0e-3))
        @test_throws FrameworkValidationError cpw_line!(draft, "line_c"; line=smoke_line(1.0e-3), prefix="line_a")
        @test_throws FrameworkValidationError connect_pins!(draft, section(line_a, 0.1, 0.2), pin(q, :pad); id="bad_connect")
        @test_throws FrameworkValidationError tap_m(line_a, 1.1e-3)
        @test_throws FrameworkValidationError section_m(line_a, 0.2e-3, 1.1e-3)

        coupled_window!(
            draft,
            section(line_a, 0.30, 0.50),
            section(line_b, 0.30, 0.50);
            spec=smoke_window(200.0 * um_smoke),
            id="window_a",
        )
        coupled_window!(
            draft,
            section(line_a, 0.40, 0.60),
            section(line_b, 0.60, 0.80);
            spec=smoke_window(200.0 * um_smoke),
            id="window_b",
        )
        @test_throws FrameworkValidationError finalize_circuit(draft)

        draft_tap = CircuitDraft("tap_inside")
        line_c = cpw_line!(draft_tap, "line_c"; line=smoke_line(1.0e-3))
        line_d = cpw_line!(draft_tap, "line_d"; line=smoke_line(1.0e-3))
        q_tap = lc_qubit!(draft_tap, "q"; L=8.0 * nH_smoke, C=90.0 * fF_smoke)
        coupled_window!(
            draft_tap,
            section(line_c, 0.30, 0.50),
            section(line_d, 0.30, 0.50);
            spec=smoke_window(200.0 * um_smoke),
            id="window",
        )
        couple_capacitive!(draft_tap, tap(line_c, 0.40), pin(q_tap, :pad); C=1.0 * fF_smoke, id="bad_tap")
        @test_throws FrameworkValidationError finalize_circuit(draft_tap)

        draft_dup_rel = CircuitDraft("duplicate_relation")
        q_dup = lc_qubit!(draft_dup_rel, "q"; L=8.0 * nH_smoke, C=90.0 * fF_smoke)
        connect_pins!(draft_dup_rel, pin(q_dup, :minus), ground(); id="same")
        @test_throws FrameworkValidationError connect_pins!(draft_dup_rel, pin(q_dup, :pad), ground(); id="same")

        draft_port = CircuitDraft("duplicate_port")
        port_a = external_pin!(draft_port, "port_a")
        port_b = external_pin!(draft_port, "port_b")
        terminated_port!(draft_port, pin(port_a, :node); port_number=1, id="port_a")
        terminated_port!(draft_port, pin(port_b, :node); port_number=1, id="port_b")
        @test_throws FrameworkValidationError finalize_circuit(draft_port)

        draft_bad_capability = CircuitDraft("bad_capability")
        line_bad = cpw_line!(draft_bad_capability, "line"; line=smoke_line(1.0e-3))
        q_bad = lc_qubit!(draft_bad_capability, "q"; L=8.0 * nH_smoke, C=90.0 * fF_smoke)
        terminated_port!(draft_bad_capability, pin(q_bad, :pad); port_number=1, id="bad_port")
        @test_throws FrameworkValidationError finalize_circuit(draft_bad_capability)
        @test line_bad isa CPWLineComponent
    end
end

println("Reusable framework v1 smoke passed.")
