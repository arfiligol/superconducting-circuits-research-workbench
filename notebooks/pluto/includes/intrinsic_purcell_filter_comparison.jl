module IntrinsicPurcellFilterComparison

using SuperconductingCircuitsCore

import ..HBExampleHelpers: zero_mode_s
import ..PortMatrixPostProcessing:
    apply_port_termination_compensation,
    invert_port_matrix_stack,
    zero_mode_y_matrix_stack

export matrix_line_values, run_rlgc_matrix_case

function matrix_line_values(c_matrix_f_per_m, l_matrix_h_per_m)
    line1_c = c_matrix_f_per_m[1, 1] + c_matrix_f_per_m[1, 2]
    line2_c = c_matrix_f_per_m[2, 2] + c_matrix_f_per_m[1, 2]
    line1_l = l_matrix_h_per_m[1, 1]
    line2_l = l_matrix_h_per_m[2, 2]
    line1_v = 1 / sqrt(line1_l * line1_c)
    line2_v = 1 / sqrt(line2_l * line2_c)

    return (
        line1_c_per_m_f = line1_c,
        line2_c_per_m_f = line2_c,
        line1_l_per_m_h = line1_l,
        line2_l_per_m_h = line2_l,
        line1_v_m_per_s = line1_v,
        line2_v_m_per_s = line2_v,
        notch_reference_v_m_per_s = (line1_v + line2_v) / 2,
    )
end

function run_rlgc_matrix_case(
    case_key,
    case_spec;
    lr_total_m,
    lp_total_m,
    effective_notch_length_m,
    window_start_r_m,
    window_start_p_m,
    window_length_m,
    section_length_m,
    frequency_sweep,
    pump_frequency,
    pump_current,
    optional_hb_kwargs,
    port_resistance_ohm,
    ptc_resistance_ohm_by_port,
    coupling_orientation = :same_direction,
    short_label = nothing,
)
    case_c_matrix = case_spec.C_matrix_F_per_m
    case_l_matrix = case_spec.L_matrix_H_per_m
    line_values = matrix_line_values(case_c_matrix, case_l_matrix)

    case_readout_resonator_spec = RLGCSpec(
        length_m = lr_total_m,
        section_length_m = section_length_m,
        l_per_m_h = line_values.line1_l_per_m_h,
        c_per_m_f = line_values.line1_c_per_m_f,
    )

    case_filter_resonator_spec = RLGCSpec(
        length_m = lp_total_m,
        section_length_m = section_length_m,
        l_per_m_h = line_values.line2_l_per_m_h,
        c_per_m_f = line_values.line2_c_per_m_f,
    )

    case_mtl_model = MTLCoupledRLGCSpec(
        start1_m = window_start_r_m,
        start2_m = window_start_p_m,
        length_m = window_length_m,
        section_length_m = section_length_m,
        l_matrix_per_m_h = case_l_matrix,
        c_matrix_per_m_f = case_c_matrix,
    )

    case_readout_section_overrides = [
        coupled_line_section_override(case_mtl_model, 1),
    ]

    case_filter_section_overrides = [
        coupled_line_section_override(case_mtl_model, 2),
    ]

    case_circuit_plan = @circuit "intrinsic-purcell-filter-two-qwr-$(case_key)" begin
        readout_grounded_head = external_node("readout_grounded_head")
        readout_open_tail = external_node("readout_open_tail")

        filter_grounded_head = external_node("filter_grounded_head")
        filter_open_tail = external_node("filter_open_tail")

        readout_resonator = quarter_wave_resonator!(
            id = :readout_resonator,
            grounded_head = readout_grounded_head,
            open_tail = readout_open_tail,
            spec = case_readout_resonator_spec,
            breakpoints_m = [
                window_start_r_m,
                window_start_r_m + window_length_m,
            ],
            section_overrides = case_readout_section_overrides,
        )

        filter_resonator = quarter_wave_resonator!(
            id = :filter_resonator,
            grounded_head = filter_grounded_head,
            open_tail = filter_open_tail,
            spec = case_filter_resonator_spec,
            breakpoints_m = [
                window_start_p_m,
                window_start_p_m + window_length_m,
            ],
            section_overrides = case_filter_section_overrides,
        )

        mtl_window = couple_transmission_window!(
            id = :readout_filter_mtl_window,
            line1 = readout_resonator.line,
            line2 = filter_resonator.line,
            start1 = window_start_r_m,
            start2 = window_start_p_m,
            length = window_length_m,
            model = case_mtl_model,
            coupling_orientation = coupling_orientation,
        )

        port(:readout_open_port) do
            index = 1
            endpoint = readout_open_tail
            resistance = port_resistance_ohm
            role = :readout_open_end
        end

        port(:filter_open_port) do
            index = 2
            endpoint = filter_open_tail
            resistance = port_resistance_ohm
            role = :filter_open_end
        end

        group(:two_qwr_mtl_system) do
            label = "Two MTL-coupled quarter-wave resonators"
            role = :intrinsic_purcell_filter
            members = [
                :readout_resonator,
                :filter_resonator,
                :readout_filter_mtl_window,
            ]
        end

        schematic!(:analysis_view) do
            track(:readout_track) do
                line = readout_resonator.line
                orientation = :left_to_right
                relative_order = :top
                role = :readout_resonator
                label = "readout resonator"
            end

            track(:filter_track) do
                line = filter_resonator.line
                orientation = :left_to_right
                relative_order = :bottom
                role = :filter_resonator
                label = "filter resonator"
            end

            terminal(:readout_open_terminal) do
                endpoint = readout_open_tail
                track = :readout_track
                side = :left
                kind = :port
                label = "1"
            end

            terminal(:filter_open_terminal) do
                endpoint = filter_open_tail
                track = :filter_track
                side = :left
                kind = :port
                label = "2"
            end

            coupled_span(:mtl_span) do
                relation = mtl_window
                track1 = :readout_track
                track2 = :filter_track
                from1 = window_start_r_m
                to1 = window_start_r_m + window_length_m
                from2 = window_start_p_m
                to2 = window_start_p_m + window_length_m
                label = "MTL"
                render = :parallel_cpw_window
            end
        end
    end

    @hbintent case_circuit_plan begin
        pump_axis(:pump; frequency_parameter = :pump_frequency)

        source_slot(:pump_in) do
            role = :pump
            port = :readout_open_port
            mode = (1,)
            current_parameter = :pump_current
        end

        sparameter(:s11) do
            outputmode = (0,)
            outputport = :readout_open_port
            inputmode = (0,)
            inputport = :readout_open_port
        end

        sparameter(:s21) do
            outputmode = (0,)
            outputport = :filter_open_port
            inputmode = (0,)
            inputport = :readout_open_port
        end

        sparameter(:s12) do
            outputmode = (0,)
            outputport = :readout_open_port
            inputmode = (0,)
            inputport = :filter_open_port
        end

        sparameter(:s22) do
            outputmode = (0,)
            outputport = :filter_open_port
            inputmode = (0,)
            inputport = :filter_open_port
        end

        solver_controls() do
            n_pump_harmonics = 1
            n_modulation_harmonics = 1
            returnS = true
            returnZ = true
            returnQE = true
            returnCM = true
            keyedarrays = false
        end
    end

    case_validation_report = validate_hb_intent(case_circuit_plan)
    case_compiled_circuit = compile_to_josephson(case_circuit_plan)
    case_hb_problem = build_hb_problem(
        case_compiled_circuit,
        HBRunSpec(
            frequency_sweep = frequency_sweep,
            pump_frequencies = Dict(:pump => Float64(pump_frequency)),
            source_currents = Dict(:pump_in => Float64(pump_current)),
            optional_hb_kwargs = Dict{Symbol,Any}(optional_hb_kwargs),
        ),
    )
    case_output_request_report = validate_output_request_configuration(
        case_compiled_circuit,
        case_hb_problem,
    )
    case_result = run_hb_problem(case_hb_problem)

    case_raw_y_stack = zero_mode_y_matrix_stack(case_result; ports = [1, 2])
    case_ptc_y_stack = apply_port_termination_compensation(
        case_raw_y_stack;
        resistance_ohm_by_port = ptc_resistance_ohm_by_port,
    )
    case_ptc_z_stack = invert_port_matrix_stack(
        case_ptc_y_stack;
        source_kind = :ptc_z_from_y,
    )

    return (
        key = case_key,
        label = case_spec.label,
        short_label = something(short_label, case_key == :paper_reference ? "Paper" : "Colleague"),
        coupling_orientation = coupling_orientation,
        line_values = line_values,
        fr_est_Hz = line_values.line1_v_m_per_s / (4 * lr_total_m),
        fp_est_Hz = line_values.line2_v_m_per_s / (4 * lp_total_m),
        fn_est_Hz = line_values.notch_reference_v_m_per_s / (4 * effective_notch_length_m),
        circuit_plan = case_circuit_plan,
        mtl_window = mtl_window,
        validation_report = case_validation_report,
        compiled_circuit = case_compiled_circuit,
        output_request_report = case_output_request_report,
        result = case_result,
        s11 = zero_mode_s(case_result, 1, 1),
        s21 = zero_mode_s(case_result, 2, 1),
        s12 = zero_mode_s(case_result, 1, 2),
        s22 = zero_mode_s(case_result, 2, 2),
        z11_raw = case_result.traces[:z_parameter_mode]["om=0|op=1|im=0|ip=1"],
        z21_raw = case_result.traces[:z_parameter_mode]["om=0|op=2|im=0|ip=1"],
        z12_raw = case_result.traces[:z_parameter_mode]["om=0|op=1|im=0|ip=2"],
        z22_raw = case_result.traces[:z_parameter_mode]["om=0|op=2|im=0|ip=2"],
        z11_ptc = vec(case_ptc_z_stack.values[1, 1, :]),
        z21_ptc = vec(case_ptc_z_stack.values[2, 1, :]),
        z12_ptc = vec(case_ptc_z_stack.values[1, 2, :]),
        z22_ptc = vec(case_ptc_z_stack.values[2, 2, :]),
    )
end

end
