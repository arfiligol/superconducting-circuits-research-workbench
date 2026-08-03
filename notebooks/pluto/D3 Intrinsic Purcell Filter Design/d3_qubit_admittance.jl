# D3 Stage-2 floating-qubit admittance is evaluated from the same compiled
# seven-node Equivalent Circuit used by Exact-N. The direct route uses virtual,
# unloaded qL/qR current injection. The independent HB route adds temporary
# probe ports only to a copied plan and removes their proven compiled shunts by
# PTC. This file owns only the D3-specific transform, Kron reduction, and
# provisional Cq/Re(Y) Purcell-T1 readback.

using LinearAlgebra

isdefined(@__MODULE__, :PortMatrixPostProcessing) ||
    include(joinpath(@__DIR__, "..", "includes", "port_matrix_post_processing.jl"))
using .PortMatrixPostProcessing: PortMatrixStack,
    zero_mode_z_matrix_stack,
    compiled_port_shunt_evidence,
    apply_port_termination_compensation,
    invert_port_matrix_stack,
    common_differential_transform,
    apply_coordinate_transform,
    kron_reduce

"""
    d3_qubit_differential_admittance(model, frequency_hz)

Return the coupling-on Full-QRP differential driving-point admittance seen by
the floating qubit. `model` must be the seven-node result of
`d3_exact_n_compiled_model`.

The calculation retains both physical 50-ohm feedline baths, introduces no
qL/qR probe conductance, transforms

    Phi_q = Phi_qL - Phi_qR
    Phi_Sigma = (A*Phi_qL + B*Phi_qR)/(A+B)

with its power-dual current map, and Schur-reduces Sigma, r, p, f1, fc, and f2
under zero external current injection. The provisional Purcell readback uses

    T1(omega) = C_q,eff / real(Y_q,eff(omega))

with `C_q,eff = model.capacitance[q,q]`, the differential diagonal after the
declared neutral-common-charge reduction. T1 is reported only where `real(Y)`
is strictly positive; passivity tolerance remains a Human-owned decision.
"""
function d3_qubit_differential_admittance(model, frequency_hz)
    frequencies = Float64.(collect(frequency_hz))
    !isempty(frequencies) && all(isfinite, frequencies) &&
        all(>(0), frequencies) && all(diff(frequencies) .> 0) || error(
        "D3 qubit-admittance frequencies must be strictly increasing and positive.",
    )

    required = (
        :physical_coordinate_order,
        :physical_node_order,
        :compiled_to_physical_permutation,
        :node_to_local_transform,
        :coordinate_order,
        :capacitance,
        :inverse_inductance,
        :selector,
        :reference_impedance_ohm,
        :port_nodes,
        :conservative_nodal_model,
        :provenance,
    )
    all(name -> hasproperty(model, name), required) || error(
        "D3 qubit admittance requires the complete d3_exact_n_compiled_model result.",
    )
    Tuple(Symbol.(model.physical_coordinate_order)) ==
        (:qL, :qR, :r, :p, :f1, :fc, :f2) || error(
        "D3 qubit admittance requires physical coordinates qL,qR,r,p,f1,fc,f2.",
    )
    Tuple(Symbol.(model.coordinate_order)) == (:q, :r, :p, :f1, :fc, :f2) || error(
        "D3 qubit admittance requires retained coordinates q,r,p,f1,fc,f2.",
    )

    order = Int.(model.compiled_to_physical_permutation)
    length(order) == 7 && sort(order) == collect(1:7) || error(
        "D3 qubit-admittance compiled-to-physical permutation must cover seven nodes.",
    )
    nodal = model.conservative_nodal_model
    capacitance_node = Matrix{Float64}(nodal.capacitance[order, order])
    stiffness_node = Matrix{Float64}(nodal.inverse_inductance[order, order])
    transform = Matrix{Float64}(model.node_to_local_transform)
    size(transform) == (7, 7) || error(
        "D3 qubit-admittance node-to-local transform must be 7-by-7.",
    )
    all(isfinite, transform) && isfinite(cond(transform)) || error(
        "D3 qubit-admittance node-to-local transform must be finite and nonsingular.",
    )

    conductance_node = zeros(Float64, 7, 7)
    impedances = Float64.(model.reference_impedance_ohm)
    length(impedances) == length(model.port_nodes) == 2 &&
        all(isfinite, impedances) && all(>(0), impedances) || error(
        "D3 qubit admittance requires two finite positive feedline impedances.",
    )
    for (port_node, impedance) in zip(model.port_nodes, impedances)
        indices = findall(==(String(port_node)), String.(model.physical_node_order))
        length(indices) == 1 || error(
            "D3 qubit admittance could not identify one physical node for port $(port_node).",
        )
        conductance_node[only(indices), only(indices)] += 1 / impedance
    end

    local_labels = [:Sigma, :q, :r, :p, :f1, :fc, :f2]
    keep = 2
    drop = [1, 3, 4, 5, 6, 7]
    reduced_capacitance = Matrix{Float64}(model.capacitance)
    reduced_stiffness = Matrix{Float64}(model.inverse_inductance)
    reduced_selector = Matrix{Float64}(model.selector)
    reduced_conductance =
        reduced_selector * Diagonal(1 ./ impedances) * transpose(reduced_selector)
    q_index = only(findall(==(:q), Symbol.(model.coordinate_order)))
    reduced_drop = [index for index in 1:6 if index != q_index]

    admittance = Vector{ComplexF64}(undef, length(frequencies))
    eliminated_condition_number = Vector{Float64}(undef, length(frequencies))
    zero_injection_residual = Vector{Float64}(undef, length(frequencies))
    reduced_model_closure = Vector{Float64}(undef, length(frequencies))
    for (frequency_index, frequency) in pairs(frequencies)
        omega = 2pi * frequency
        dynamic_node = stiffness_node - omega^2 * capacitance_node -
            im * omega * conductance_node
        admittance_local = transpose(transform) *
            (dynamic_node / (-im * omega)) * transform
        eliminated = admittance_local[drop, drop]
        eliminated_condition_number[frequency_index] = cond(eliminated)
        isfinite(eliminated_condition_number[frequency_index]) || error(
            "D3 qubit-admittance eliminated block is singular at $(frequency) Hz.",
        )
        response = try
            eliminated \ admittance_local[drop, keep]
        catch exception
            error(
                "D3 qubit-admittance Kron solve failed at $(frequency) Hz: " *
                sprint(showerror, exception),
            )
        end
        y_eff = admittance_local[keep, keep] -
            only(admittance_local[keep:keep, drop] * response)
        admittance[frequency_index] = y_eff

        voltage = zeros(ComplexF64, 7)
        voltage[keep] = 1
        voltage[drop] = -response
        current = admittance_local * voltage
        zero_injection_residual[frequency_index] = maximum(abs, current[drop]) /
            max(norm(admittance_local, Inf), floatmin(Float64))

        dynamic_reduced = reduced_stiffness - omega^2 * reduced_capacitance -
            im * omega * reduced_conductance
        admittance_reduced = dynamic_reduced / (-im * omega)
        response_reduced = admittance_reduced[reduced_drop, reduced_drop] \
            admittance_reduced[reduced_drop, q_index]
        y_eff_reduced = admittance_reduced[q_index, q_index] - only(
            admittance_reduced[q_index:q_index, reduced_drop] * response_reduced,
        )
        reduced_model_closure[frequency_index] = abs(
            admittance[frequency_index] - y_eff_reduced,
        )
    end

    real_admittance = real.(admittance)
    c_q_eff = reduced_capacitance[q_index, q_index]
    isfinite(c_q_eff) && c_q_eff > 0 || error(
        "D3 effective differential qubit capacitance must be finite and positive.",
    )
    t1_defined = real_admittance .> 0
    purcell_t1_s = [
        t1_defined[index] ? c_q_eff / real_admittance[index] : NaN
        for index in eachindex(real_admittance)
    ]
    worst_condition_index = argmax(eliminated_condition_number)

    return (
        contract_id="d3-stage2-qubit-differential-admittance.candidate-v1",
        frequency_hz=frequencies,
        differential_admittance_s=admittance,
        real_admittance_s=real_admittance,
        imaginary_admittance_s=imag.(admittance),
        effective_differential_capacitance_f=c_q_eff,
        purcell_t1_s=purcell_t1_s,
        purcell_t1_defined=t1_defined,
        coordinate_contract=(
            physical_labels=Symbol.(model.physical_coordinate_order),
            transformed_labels=local_labels,
            node_flux_from_local_flux=transform,
            voltage_convention=(
                common="V_Sigma = A/(A+B) * V_qL + B/(A+B) * V_qR",
                differential="V_q = V_qL - V_qR",
            ),
            current_convention=(
                common="I_Sigma = I_qL + I_qR",
                differential="I_q = B/(A+B) * I_qL - A/(A+B) * I_qR",
            ),
            weights=(
                A_f=model.common_charge_reduction.a_f,
                B_f=model.common_charge_reduction.b_f,
                sum_f=model.common_charge_reduction.s_f,
                alpha=model.common_charge_reduction.a_f /
                    model.common_charge_reduction.s_f,
                beta=model.common_charge_reduction.b_f /
                    model.common_charge_reduction.s_f,
            ),
        ),
        boundary=(
            qubit_probe=:virtual_unloaded_nodal_current_injection,
            qubit_probe_shunt_s=0.0,
            ptc_semantics=:probe_shunts_never_stamped,
            retained_environment=:two_physical_matched_feedline_baths,
            feedline_port_nodes=Symbol.(model.port_nodes),
            feedline_reference_impedance_ohm=impedances,
            retained_coordinate=:q,
            eliminated_coordinates=local_labels[drop],
            eliminated_external_current=:zero,
        ),
        t1_convention=(
            formula=:T1_equals_Cq_eff_over_real_Yq_eff,
            capacitance_source=:neutral_common_charge_reduced_Cqq,
            valid_only_for_strictly_positive_real_admittance=true,
            approximation=:weak_loading_harmonic_candidate,
            status=:candidate_not_human_accepted,
        ),
        diagnostics=(
            all_finite_admittance=all(isfinite, admittance),
            passive_at_every_sample=all(real_admittance .>= 0),
            minimum_real_admittance_s=minimum(real_admittance),
            negative_real_admittance_sample_count=count(value -> value < 0, real_admittance),
            maximum_eliminated_condition_number=
                eliminated_condition_number[worst_condition_index],
            worst_condition_frequency_hz=frequencies[worst_condition_index],
            eliminated_condition_number=eliminated_condition_number,
            maximum_zero_injection_residual=maximum(zero_injection_residual),
            maximum_seven_to_six_closure_s=maximum(reduced_model_closure),
            seven_to_six_closure_s=reduced_model_closure,
            source_model_provenance=model.provenance,
        ),
    )
end

"""
    d3_qubit_differential_admittance_hb(stage, frequency_hz; pump_frequency_hz)

Run the Stage-2 Equivalent Circuit through JosephsonCircuits with temporary
qL/qR probe ports P3/P4, prove their compiler-lowered shunts, remove only those
two shunts in raw Y, transform to the weighted Sigma/q coordinates, and Kron
reduce onto q. The physical P1/P2 50-ohm loads remain in the network.

The temporary ports exist only in a deep-copied diagnostic plan. They do not
change `stage.built.plan`, the optimizer candidate, or the CircuitPlan shown by
the Design Target.
"""
function d3_qubit_differential_admittance_hb(
    stage,
    frequency_hz;
    pump_frequency_hz,
)
    hasproperty(stage, :built) && hasproperty(stage.built, :plan) &&
        hasproperty(stage.built, :component) || error(
        "D3 HB qubit admittance requires a Stage-2 Equivalent Circuit candidate.",
    )
    frequencies = Float64.(collect(frequency_hz))
    !isempty(frequencies) && all(isfinite, frequencies) &&
        all(>(0), frequencies) && all(diff(frequencies) .> 0) || error(
        "D3 HB qubit-admittance frequencies must be strictly increasing and positive.",
    )
    pump = Float64(pump_frequency_hz)
    isfinite(pump) && pump > 0 || error(
        "D3 HB qubit-admittance pump frequency must be finite and positive.",
    )

    diagnostic_built = deepcopy(stage.built)
    external_port!(
        diagnostic_built.plan;
        id=:qubit_left_probe,
        index=3,
        endpoint=diagnostic_built.component.qubit.island_1,
        resistance=50.0,
        role=:probe,
    )
    external_port!(
        diagnostic_built.plan;
        id=:qubit_right_probe,
        index=4,
        endpoint=diagnostic_built.component.qubit.island_2,
        resistance=50.0,
        role=:probe,
    )
    compiled = compile_to_josephson(diagnostic_built.plan)
    probe_shunt_evidence = compiled_port_shunt_evidence(
        compiled;
        port_indices=(3, 4),
    )
    retained_feedline_shunt_evidence = compiled_port_shunt_evidence(
        compiled;
        port_indices=(1, 2),
    )

    result = run_hbsolve(
        compiled.netlist,
        compiled.component_values,
        frequencies;
        pump_frequencies_hz=(pump,),
        sources=[(mode=(1,), port=1, current=0.0)],
        n_modulation_harmonics=(1,),
        n_pump_harmonics=(1,),
        port_indices=[1, 2, 3, 4],
        returnS=false,
        returnZ=true,
        returnQE=false,
        returnCM=false,
        fourwavemixing=true,
    )
    raw_z_solver = zero_mode_z_matrix_stack(result; ports=[1, 2, 3, 4])
    raw_z = PortMatrixStack(
        labels=raw_z_solver.labels,
        frequencies_hz=raw_z_solver.frequencies_hz,
        values=conj.(raw_z_solver.values),
        quantity_kind=:impedance,
        source_kind=:hb_z_exp_minus_i_omega_t,
    )
    raw_y = invert_port_matrix_stack(raw_z; source_kind=:z_inverse)
    compensated_y = apply_port_termination_compensation(
        raw_y,
        compiled;
        compensate_port_indices=(3, 4),
        removal_intent=:unloaded_floating_qubit_differential_observable,
    )

    direct_model = d3_exact_n_compiled_model(stage.built)
    a = direct_model.common_charge_reduction.a_f
    b = direct_model.common_charge_reduction.b_f
    s = direct_model.common_charge_reduction.s_f
    alpha = a / s
    beta = b / s
    transform = common_differential_transform(
        4,
        3,
        4;
        alpha=alpha,
        beta=beta,
    )
    transformed_y = apply_coordinate_transform(
        compensated_y,
        transform;
        labels=["f1", "f2", "Sigma", "q"],
    )
    keep = [4]
    drop = [1, 2, 3]
    kron_condition_number = Float64[
        cond(transformed_y.values[drop, drop, index])
        for index in axes(transformed_y.values, 3)
    ]
    all(isfinite, kron_condition_number) || error(
        "D3 HB qubit-admittance eliminated block is singular within the sweep.",
    )
    reduced_y = kron_reduce(transformed_y; keep_indices=keep)
    hb_admittance = vec(reduced_y.values[1, 1, :])
    all(isfinite, hb_admittance) || error(
        "D3 HB qubit-admittance reduction produced non-finite values.",
    )

    direct = d3_qubit_differential_admittance(direct_model, frequencies)
    real_hb = real.(hb_admittance)
    c_q_eff = direct.effective_differential_capacitance_f
    hb_t1_defined = real_hb .> 0
    hb_t1_s = [
        hb_t1_defined[index] ? c_q_eff / real_hb[index] : NaN
        for index in eachindex(real_hb)
    ]
    residual = abs.(hb_admittance .- direct.differential_admittance_s)
    worst_condition_index = argmax(kron_condition_number)

    return (
        contract_id="d3-stage2-hb-qubit-differential-admittance.candidate-v1",
        model_identity=direct_model.provenance,
        frequency_hz=frequencies,
        hb_differential_admittance_s=hb_admittance,
        hb_real_admittance_s=real_hb,
        hb_imaginary_admittance_s=imag.(hb_admittance),
        hb_purcell_t1_s=hb_t1_s,
        hb_purcell_t1_defined=hb_t1_defined,
        direct=direct,
        hb_direct_abs_y_residual_s=residual,
        effective_differential_capacitance_f=c_q_eff,
        t1_convention=(
            formula=:T1_equals_Cq_eff_over_real_Yq_eff,
            capacitance_source=:neutral_common_charge_reduced_Cqq,
            valid_only_for_strictly_positive_real_admittance=true,
            approximation=:weak_loading_harmonic_candidate,
            status=:candidate_not_human_accepted,
        ),
        alpha=alpha,
        beta=beta,
        kron_condition_number=kron_condition_number,
        evidence=(
            probe_shunts_removed=probe_shunt_evidence,
            feedline_shunts_retained=retained_feedline_shunt_evidence,
            removal_intent=:unloaded_floating_qubit_differential_observable,
            phasor_conversion=:elementwise_conjugated_complete_z_before_z_to_y,
            raw_quantity=:z_parameter_mode,
            transformed_quantity=:admittance,
            transformed_labels=copy(transformed_y.labels),
            retained_label=:q,
            eliminated_labels=Symbol.(transformed_y.labels[drop]),
            eliminated_external_current=:zero,
        ),
        diagnostics=(
            all_finite_hb_admittance=all(isfinite, hb_admittance),
            hb_passive_at_every_sample=all(real_hb .>= 0),
            hb_minimum_real_admittance_s=minimum(real_hb),
            hb_negative_real_admittance_sample_count=
                count(value -> value < 0, real_hb),
            maximum_kron_condition_number=
                kron_condition_number[worst_condition_index],
            worst_kron_condition_frequency_hz=frequencies[worst_condition_index],
            maximum_hb_direct_abs_y_residual_s=maximum(residual),
        ),
        compiled=compiled,
    )
end

"""Return numeric report rows with the D3 Stage-2 CSV field contract."""
function d3_qubit_admittance_report_rows(result)
    required = (
        :frequency_hz,
        :hb_differential_admittance_s,
        :hb_purcell_t1_s,
        :direct,
        :effective_differential_capacitance_f,
        :alpha,
        :beta,
        :kron_condition_number,
        :hb_direct_abs_y_residual_s,
    )
    all(name -> hasproperty(result, name), required) || error(
        "D3 qubit-admittance report rows require the HB/direct comparison result.",
    )
    return [
        (
            frequency_hz=result.frequency_hz[index],
            hb_y_eff_real_s=real(result.hb_differential_admittance_s[index]),
            hb_y_eff_imag_s=imag(result.hb_differential_admittance_s[index]),
            direct_y_eff_real_s=
                result.direct.real_admittance_s[index],
            direct_y_eff_imag_s=
                result.direct.imaginary_admittance_s[index],
            hb_t1_s=result.hb_purcell_t1_s[index],
            direct_t1_s=result.direct.purcell_t1_s[index],
            c_q_eff_f=result.effective_differential_capacitance_f,
            alpha=result.alpha,
            beta=result.beta,
            kron_condition_number=result.kron_condition_number[index],
            hb_direct_abs_y_residual_s=
                result.hb_direct_abs_y_residual_s[index],
        )
        for index in eachindex(result.frequency_hz)
    ]
end
