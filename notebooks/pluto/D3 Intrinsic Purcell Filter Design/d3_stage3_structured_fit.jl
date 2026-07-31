# D3 Stage-3 topology-constrained complex-S21 witness fit.
#
# This CONVERGING candidate owns only the inverse bridge from one compiled
# Hybridized response to one response-equivalent finite-order witness. Its six
# LC values describe the fitted response only; fabrication realizability
# remains owned by the physical CPW/MTL coordinates and response-match map.

using LinearAlgebra
import CMAEvolutionStrategy

const D3_STAGE3_WITNESS_VARIABLE_ORDER = (
    :Cr_f,
    :Lr_h,
    :Cp_f,
    :Lp_h,
    :Cn_f,
    :Ln_h,
)

function _d3_stage3_structured_exact_fields(value, expected, label)
    actual = Tuple(propertynames(value))
    Set(actual) == Set(expected) || error(
        "$(label) fields must be exactly $(collect(expected)); received $(collect(actual)).",
    )
    return nothing
end

function _d3_stage3_structured_finite_positive(value, label)
    value isa Real || error("$(label) must be real.")
    result = Float64(value)
    isfinite(result) && result > 0 ||
        error("$(label) must be finite and positive.")
    return result
end

function _d3_stage3_structured_positive_integer(value, label)
    value isa Real && isfinite(value) && value == round(value) && value > 0 ||
        error("$(label) must be a positive integer-valued number.")
    return Int(round(value))
end

function _d3_stage3_structured_band(value, label)
    values = Float64.(collect(value))
    length(values) == 2 && all(isfinite, values) &&
        0 < values[1] < values[2] ||
        error("$(label) must contain two finite increasing positive frequencies.")
    return (values[1], values[2])
end

function _d3_stage3_structured_candidate(value, label)
    _d3_stage3_structured_exact_fields(
        value,
        D3_STAGE3_WITNESS_VARIABLE_ORDER,
        label,
    )
    return NamedTuple{D3_STAGE3_WITNESS_VARIABLE_ORDER}(Tuple(
        _d3_stage3_structured_finite_positive(
            getproperty(value, name),
            "$(label) $(name)",
        )
        for name in D3_STAGE3_WITNESS_VARIABLE_ORDER
    ))
end

function _d3_stage3_structured_bounds(value)
    _d3_stage3_structured_exact_fields(
        value,
        D3_STAGE3_WITNESS_VARIABLE_ORDER,
        "D3 Stage-3 witness bounds",
    )
    return NamedTuple{D3_STAGE3_WITNESS_VARIABLE_ORDER}(Tuple(
        begin
            raw = Float64.(collect(getproperty(value, name)))
            length(raw) == 2 && all(isfinite, raw) &&
                0 < raw[1] < raw[2] ||
                error(
                    "D3 Stage-3 witness bound $(name) must contain finite positive lower/upper values.",
                )
            (raw[1], raw[2])
        end
        for name in D3_STAGE3_WITNESS_VARIABLE_ORDER
    ))
end

function _d3_stage3_structured_with_u_idc(candidate, u_idc)
    return (
        Cr_f=candidate.Cr_f,
        Lr_h=candidate.Lr_h,
        Cp_f=candidate.Cp_f,
        Lp_h=candidate.Lp_h,
        Cn_f=candidate.Cn_f,
        Ln_h=candidate.Ln_h,
        u_IDC=u_idc,
    )
end

"""
    d3_stage3_structured_fit_settings(; ...)

Validate all caller-owned numerical choices for one Stage-3 structured witness
fit. There are deliberately no numerical defaults: fit window, resolution,
weights, recovery tolerances, and identifiability gates remain CONVERGING D3
semantics.
"""
function d3_stage3_structured_fit_settings(;
    frequency_hz,
    reference_bright_poles_hz,
    pole_guard_band_hz,
    pole_capture_radius_hz,
    pole_passivity_tolerance_hz,
    branch_window_half_width_hz,
    fit_window_margin_hz,
    region_weights,
    minimum_branch_samples,
    minimum_baseline_samples_per_side,
    witness_bounds,
    witness_starts,
    loaded_bare_frequency_band_hz,
    optimizer_iterations,
    optimizer_function_calls,
    optimizer_x_abstol,
    optimizer_f_abstol,
    maximum_weighted_complex_rmse,
    maximum_complex_max_abs,
    minimum_bound_margin_fraction,
    maximum_normalized_parameter_start_spread,
    maximum_fr_start_spread_hz,
    maximum_fp_start_spread_hz,
    maximum_J_start_spread_hz,
    jacobian_step_fraction,
    minimum_jacobian_singular_value,
    maximum_jacobian_condition,
)
    frequencies = Float64.(collect(frequency_hz))
    !isempty(frequencies) && all(value -> isfinite(value) && value > 0, frequencies) &&
        all(diff(frequencies) .> 0) ||
        error(
            "D3 Stage-3 structured-fit frequency grid must be finite, positive, and strictly increasing.",
        )
    reference_poles = sort(
        ComplexF64.(collect(reference_bright_poles_hz));
        by=real,
    )
    length(reference_poles) == 2 ||
        error("D3 Stage-3 structured fit requires exactly two reference bright poles.")
    all(real.(reference_poles) .> 0) ||
        error("D3 Stage-3 reference bright poles must have positive frequency.")

    guard_band = _d3_stage3_structured_band(
        pole_guard_band_hz,
        "D3 Stage-3 pole guard band",
    )
    loaded_bare_band = _d3_stage3_structured_band(
        loaded_bare_frequency_band_hz,
        "D3 Stage-3 loaded-bare extraction band",
    )
    capture_radius = _d3_stage3_structured_finite_positive(
        pole_capture_radius_hz,
        "D3 Stage-3 pole-capture radius",
    )
    passivity_tolerance = _d3_stage3_structured_finite_positive(
        pole_passivity_tolerance_hz,
        "D3 Stage-3 pole-passivity tolerance",
    )
    branch_half_width = _d3_stage3_structured_finite_positive(
        branch_window_half_width_hz,
        "D3 Stage-3 branch-window half width",
    )
    fit_margin = _d3_stage3_structured_finite_positive(
        fit_window_margin_hz,
        "D3 Stage-3 fit-window margin",
    )
    all(
        guard_band[1] <= real(pole) <= guard_band[2] &&
        imag(pole) <= passivity_tolerance
        for pole in reference_poles
    ) || error(
        "D3 Stage-3 reference bright poles must be passive and inside the guard band.",
    )

    _d3_stage3_structured_exact_fields(
        region_weights,
        (:baseline, :branch_1, :branch_2),
        "D3 Stage-3 structured-fit region weights",
    )
    weights = (
        baseline=_d3_stage3_structured_finite_positive(
            region_weights.baseline,
            "D3 Stage-3 baseline weight",
        ),
        branch_1=_d3_stage3_structured_finite_positive(
            region_weights.branch_1,
            "D3 Stage-3 branch-1 weight",
        ),
        branch_2=_d3_stage3_structured_finite_positive(
            region_weights.branch_2,
            "D3 Stage-3 branch-2 weight",
        ),
    )
    isapprox(sum(values(weights)), 1.0; atol=64eps(Float64), rtol=0.0) ||
        error("D3 Stage-3 structured-fit region weights must sum to one.")

    bounds = _d3_stage3_structured_bounds(witness_bounds)
    starts = [
        _d3_stage3_structured_candidate(
            start,
            "D3 Stage-3 witness start $(index)",
        )
        for (index, start) in enumerate(witness_starts)
    ]
    length(starts) >= 2 ||
        error("D3 Stage-3 structured fit requires at least two deterministic starts.")
    length(unique(Tuple(values(start)) for start in starts)) == length(starts) ||
        error("D3 Stage-3 structured-fit starts must be distinct.")
    for (index, start) in enumerate(starts), name in D3_STAGE3_WITNESS_VARIABLE_ORDER
        lower, upper = getproperty(bounds, name)
        lower < getproperty(start, name) < upper || error(
            "D3 Stage-3 witness start $(index) $(name) must lie strictly inside its bounds.",
        )
    end

    bound_margin = Float64(minimum_bound_margin_fraction)
    isfinite(bound_margin) && 0 < bound_margin < 0.5 ||
        error("D3 Stage-3 minimum bound margin must lie strictly between zero and 0.5.")
    jacobian_step = Float64(jacobian_step_fraction)
    isfinite(jacobian_step) && 0 < jacobian_step < bound_margin ||
        error(
            "D3 Stage-3 Jacobian step must be positive and smaller than the bound-margin gate.",
        )

    return (
        contract_id="d3-stage3-structured-fit-settings.v1",
        frequency_hz=frequencies,
        reference_bright_poles_hz=reference_poles,
        pole_guard_band_hz=guard_band,
        pole_capture_radius_hz=capture_radius,
        pole_passivity_tolerance_hz=passivity_tolerance,
        branch_window_half_width_hz=branch_half_width,
        fit_window_margin_hz=fit_margin,
        region_weights=weights,
        minimum_branch_samples=_d3_stage3_structured_positive_integer(
            minimum_branch_samples,
            "D3 Stage-3 minimum branch samples",
        ),
        minimum_baseline_samples_per_side=
            _d3_stage3_structured_positive_integer(
                minimum_baseline_samples_per_side,
                "D3 Stage-3 minimum baseline samples per side",
            ),
        witness_bounds=bounds,
        witness_starts=starts,
        loaded_bare_frequency_band_hz=loaded_bare_band,
        optimizer_iterations=_d3_stage3_structured_positive_integer(
            optimizer_iterations,
            "D3 Stage-3 optimizer iteration limit",
        ),
        optimizer_function_calls=_d3_stage3_structured_positive_integer(
            optimizer_function_calls,
            "D3 Stage-3 optimizer function-call limit",
        ),
        optimizer_x_abstol=_d3_stage3_structured_finite_positive(
            optimizer_x_abstol,
            "D3 Stage-3 optimizer x tolerance",
        ),
        optimizer_f_abstol=_d3_stage3_structured_finite_positive(
            optimizer_f_abstol,
            "D3 Stage-3 optimizer objective tolerance",
        ),
        maximum_weighted_complex_rmse=
            _d3_stage3_structured_finite_positive(
                maximum_weighted_complex_rmse,
                "D3 Stage-3 weighted complex-RMSE gate",
            ),
        maximum_complex_max_abs=_d3_stage3_structured_finite_positive(
            maximum_complex_max_abs,
            "D3 Stage-3 complex maximum-residual gate",
        ),
        minimum_bound_margin_fraction=bound_margin,
        maximum_normalized_parameter_start_spread=
            _d3_stage3_structured_finite_positive(
                maximum_normalized_parameter_start_spread,
                "D3 Stage-3 normalized parameter-cluster gate",
            ),
        maximum_fr_start_spread_hz=_d3_stage3_structured_finite_positive(
            maximum_fr_start_spread_hz,
            "D3 Stage-3 fr start-spread gate",
        ),
        maximum_fp_start_spread_hz=_d3_stage3_structured_finite_positive(
            maximum_fp_start_spread_hz,
            "D3 Stage-3 fp start-spread gate",
        ),
        maximum_J_start_spread_hz=_d3_stage3_structured_finite_positive(
            maximum_J_start_spread_hz,
            "D3 Stage-3 J start-spread gate",
        ),
        jacobian_step_fraction=jacobian_step,
        minimum_jacobian_singular_value=
            _d3_stage3_structured_finite_positive(
                minimum_jacobian_singular_value,
                "D3 Stage-3 minimum scaled-Jacobian singular value",
            ),
        maximum_jacobian_condition=_d3_stage3_structured_finite_positive(
            maximum_jacobian_condition,
            "D3 Stage-3 maximum scaled-Jacobian condition",
        ),
    )
end

function _d3_stage3_structured_unidentified(code, message; diagnostics...)
    return (
        contract_id="d3-stage3-structured-witness-fit.v1",
        semantic_state=:CONVERGING,
        status=:quantity_unidentified,
        rejection=(code=Symbol(code), message=String(message)),
        diagnostics=(; diagnostics...),
    )
end

function _d3_stage3_structured_pole_gate(candidate_poles, settings)
    tolerance = settings.pole_passivity_tolerance_hz
    guard = settings.pole_guard_band_hz
    positive_in_guard = ComplexF64[
        pole for pole in candidate_poles
        if guard[1] <= real(pole) <= guard[2]
    ]
    any(imag(pole) > tolerance for pole in positive_in_guard) &&
        return _d3_stage3_structured_unidentified(
            :candidate_nonpassive_bright_band,
            "A positive-frequency candidate pole inside the guard band violates the passivity tolerance.";
            observed_poles_hz=positive_in_guard,
        )
    observed = ComplexF64[
        pole for pole in positive_in_guard
        if imag(pole) <= tolerance
    ]
    length(observed) >= 2 || return _d3_stage3_structured_unidentified(
        :candidate_response_branch_missing,
        "The Hybridized candidate exposes fewer than two passive poles inside the declared guard band.";
        observed_poles_hz=observed,
        required_reference_poles_hz=settings.reference_bright_poles_hz,
    )

    reference = settings.reference_bright_poles_hz
    best = nothing
    best_cost = Inf
    for first_index in eachindex(observed), second_index in eachindex(observed)
        first_index == second_index && continue
        matched = ComplexF64[observed[first_index], observed[second_index]]
        cost = sum(abs2, matched - reference)
        if cost < best_cost
            best_cost = cost
            best = (
                assignment=(first_index, second_index),
                matched_poles_hz=matched,
                complex_distances_hz=abs.(matched - reference),
            )
        end
    end
    isnothing(best) && return _d3_stage3_structured_unidentified(
        :candidate_response_branch_missing,
        "No injective two-branch pole assignment exists.";
        observed_poles_hz=observed,
    )
    maximum(best.complex_distances_hz) <= settings.pole_capture_radius_hz ||
        return _d3_stage3_structured_unidentified(
            :candidate_response_branch_outside_capture,
            "At least one Hybridized bright branch lies outside the declared capture radius.";
            reference_poles_hz=reference,
            matched_poles_hz=best.matched_poles_hz,
            complex_distances_hz=best.complex_distances_hz,
            capture_radius_hz=settings.pole_capture_radius_hz,
        )

    fit_lower = first(settings.frequency_hz)
    fit_upper = last(settings.frequency_hz)
    required_clearance =
        settings.branch_window_half_width_hz + settings.fit_window_margin_hz
    clearances = [
        (
            left=real(pole) - fit_lower,
            right=fit_upper - real(pole),
        )
        for pole in best.matched_poles_hz
    ]
    all(
        clearance.left >= required_clearance &&
        clearance.right >= required_clearance
        for clearance in clearances
    ) || return _d3_stage3_structured_unidentified(
        :candidate_response_branch_lacks_window_margin,
        "A matched Hybridized bright branch lacks the declared fit-window clearance.";
        matched_poles_hz=best.matched_poles_hz,
        clearances_hz=clearances,
        required_clearance_hz=required_clearance,
    )

    return (
        contract_id="d3-stage3-bright-pole-presence-gate.v1",
        status=:passed,
        reference_poles_hz=reference,
        observed_guard_band_poles_hz=observed,
        matched_poles_hz=best.matched_poles_hz,
        complex_distances_hz=best.complex_distances_hz,
        assignment=best.assignment,
        extra_observed_pole_count=length(observed) - 2,
        clearances_hz=clearances,
        higher_order_poles_allowed=true,
    )
end

function _d3_stage3_structured_regions(settings, centers_hz)
    frequencies = settings.frequency_hz
    centers = real.(centers_hz)
    half_width = settings.branch_window_half_width_hz
    branch_1 = Int[]
    branch_2 = Int[]
    baseline = Int[]
    for index in eachindex(frequencies)
        distances = abs.(frequencies[index] .- centers)
        eligible = findall(distance -> distance <= half_width, distances)
        if isempty(eligible)
            push!(baseline, index)
        else
            selected = eligible[argmin(distances[eligible])]
            push!(selected == 1 ? branch_1 : branch_2, index)
        end
    end
    length(branch_1) >= settings.minimum_branch_samples ||
        return _d3_stage3_structured_unidentified(
            :candidate_branch_1_unresolved,
            "The structured-fit grid does not resolve bright branch 1.";
            observed_samples=length(branch_1),
            required_samples=settings.minimum_branch_samples,
        )
    length(branch_2) >= settings.minimum_branch_samples ||
        return _d3_stage3_structured_unidentified(
            :candidate_branch_2_unresolved,
            "The structured-fit grid does not resolve bright branch 2.";
            observed_samples=length(branch_2),
            required_samples=settings.minimum_branch_samples,
        )
    left_boundary = minimum(centers) - half_width
    right_boundary = maximum(centers) + half_width
    left_baseline = count(index -> frequencies[index] < left_boundary, baseline)
    right_baseline = count(index -> frequencies[index] > right_boundary, baseline)
    minimum_side = settings.minimum_baseline_samples_per_side
    left_baseline >= minimum_side && right_baseline >= minimum_side ||
        return _d3_stage3_structured_unidentified(
            :candidate_baseline_unresolved,
            "The structured-fit grid lacks the declared baseline samples on both sides.";
            left_samples=left_baseline,
            right_samples=right_baseline,
            required_samples_per_side=minimum_side,
        )
    return (
        contract_id="d3-stage3-structured-fit-regions.v1",
        status=:passed,
        baseline=baseline,
        branch_1=branch_1,
        branch_2=branch_2,
        centers_hz=centers,
        branch_window_half_width_hz=half_width,
        baseline_samples_per_side=(left=left_baseline, right=right_baseline),
    )
end

function _d3_stage3_structured_sample_weights(settings, regions)
    weights = zeros(Float64, length(settings.frequency_hz))
    for name in (:baseline, :branch_1, :branch_2)
        indices = getproperty(regions, name)
        weights[indices] .= getproperty(settings.region_weights, name) / length(indices)
    end
    isapprox(sum(weights), 1.0; atol=128eps(Float64), rtol=0.0) ||
        error("D3 Stage-3 structured-fit sample weights do not close to one.")
    return weights
end

function _d3_stage3_structured_decode_unit(unit_coordinates, bounds)
    length(unit_coordinates) == length(D3_STAGE3_WITNESS_VARIABLE_ORDER) ||
        error("D3 Stage-3 structured-fit unit-coordinate dimension is invalid.")
    all(value -> isfinite(value) && 0 < value < 1, unit_coordinates) ||
        error("D3 Stage-3 structured-fit unit coordinates must lie strictly inside (0,1).")
    return NamedTuple{D3_STAGE3_WITNESS_VARIABLE_ORDER}(Tuple(
        begin
            lower, upper = getproperty(bounds, name)
            lower + (upper - lower) * unit_coordinates[index]
        end
        for (index, name) in enumerate(D3_STAGE3_WITNESS_VARIABLE_ORDER)
    ))
end

function _d3_stage3_structured_unit(candidate, bounds)
    return Float64[
        (getproperty(candidate, name) - first(getproperty(bounds, name))) /
        (last(getproperty(bounds, name)) - first(getproperty(bounds, name)))
        for name in D3_STAGE3_WITNESS_VARIABLE_ORDER
    ]
end

function _d3_stage3_structured_response_metrics(residual, sample_weights, regions, settings)
    weighted_mse = sum(sample_weights .* abs2.(residual))
    region_metrics = NamedTuple{(:baseline, :branch_1, :branch_2)}(Tuple(
        begin
            indices = getproperty(regions, name)
            values = residual[indices]
            (
                sample_count=length(indices),
                complex_rmse=sqrt(sum(abs2, values) / length(values)),
                complex_max_abs=maximum(abs, values),
                fixed_total_weight=getproperty(settings.region_weights, name),
            )
        end
        for name in (:baseline, :branch_1, :branch_2)
    ))
    weighted_region_max_abs = maximum(
        sqrt(getproperty(settings.region_weights, name)) *
        getproperty(region_metrics, name).complex_max_abs
        for name in (:baseline, :branch_1, :branch_2)
    )
    return (
        weighted_complex_mse=weighted_mse,
        weighted_complex_rmse=sqrt(weighted_mse),
        complex_max_abs=maximum(abs, residual),
        weighted_complex_max_abs=weighted_region_max_abs,
        weighted_region_max_abs=weighted_region_max_abs,
        regions=region_metrics,
    )
end

function _d3_stage3_structured_extract(candidate, fixed, idc_mapping, settings; id)
    full_candidate = _d3_stage3_structured_with_u_idc(candidate, id.u_idc)
    stage = d3_response_equivalent_model_from_lc(
        full_candidate,
        fixed,
        idc_mapping;
        id=id.label,
    )
    model = d3_exact_n_compiled_model(stage.built)
    cqed_handoff = d3_numerical_cqed_handoff(model)
    matrix_metrics = d3_stage2_matrix_metrics(
        model;
        cqed_handoff=cqed_handoff,
    )
    loaded_bare = d3_feedline_downfolded_loaded_bare_roots(
        model,
        settings.loaded_bare_frequency_band_hz,
    )
    return (
        candidate=full_candidate,
        stage=stage,
        model=model,
        cqed_handoff=cqed_handoff,
        s21=d3_cqed_port_trace(
            cqed_handoff,
            settings.frequency_hz,
        ).exact.s21,
        extracted=(
            fr_qrp_on_hz=loaded_bare.readout.frequency_hz,
            fp_qrp_on_hz=loaded_bare.filter.frequency_hz,
            J_qrp_on_hz=matrix_metrics.J_qrp_on_hz,
        ),
        loaded_bare=loaded_bare,
        matrix_metrics=matrix_metrics,
    )
end

function _d3_stage3_structured_port_identity(hybridized_model, witness_model)
    hybridized_model.port_ids == witness_model.port_ids ||
        error("D3 Stage-3 Hybridized and witness ordered Port IDs disagree.")
    hybridized_model.port_nodes == witness_model.port_nodes ||
        error("D3 Stage-3 Hybridized and witness physical reference planes disagree.")
    hybridized_model.reference_impedance_ohm ==
        witness_model.reference_impedance_ohm ||
        error("D3 Stage-3 Hybridized and witness reference impedances disagree.")
    hybridized_model.provenance.time_convention ==
        witness_model.provenance.time_convention ||
        error("D3 Stage-3 Hybridized and witness phasor conventions disagree.")
    return (
        port_ids=copy(witness_model.port_ids),
        port_nodes=copy(witness_model.port_nodes),
        reference_impedance_ohm=copy(witness_model.reference_impedance_ohm),
        time_convention=witness_model.provenance.time_convention,
        status=:closed,
    )
end

"""
    d3_stage3_structured_witness_fit(
        stage3_candidate,
        fixed,
        idc_mapping,
        settings;
        id=...,
    )

Build the Hybridized candidate from the same fixed Q3D/feedline inputs and IDC
mapping used by its witness, then execute the structured fit. This is the
preferred public entry point because it closes input ownership before fitting.
"""
function d3_stage3_structured_witness_fit(
    stage3_candidate,
    fixed,
    idc_mapping,
    settings;
    id="d3-stage3-structured-witness",
)
    stage = d3_stage3_hybridized_model(
        stage3_candidate,
        fixed,
        idc_mapping;
        id="$(String(id))-hybridized",
    )
    hybridized_model = d3_hybridized_compiled_model(stage.built)
    return d3_stage3_structured_witness_fit(
        hybridized_model,
        stage3_candidate,
        fixed,
        idc_mapping,
        settings;
        id=id,
    )
end

"""
    d3_stage3_structured_witness_fit(
        hybridized_model,
        stage3_candidate,
        fixed,
        idc_mapping,
        settings;
        id=...,
    )

Fit one response-effective six-element Equivalent witness to the direct complex
S21 of one compiled Hybridized candidate. `u_IDC`, Q3D inputs, finite feedline,
Port order, reference impedances, and reference planes remain fixed.

Bright-branch presence and resolution are hard pre-gates. A fit that reproduces
the response but fails multi-start, bound-margin, or scaled-Jacobian gates
returns `status=:quantity_unidentified`; it never publishes `fr`, `fp`, or `J`
as identified quantities.
"""
function d3_stage3_structured_witness_fit(
    hybridized_model,
    stage3_candidate,
    fixed,
    idc_mapping,
    settings;
    id="d3-stage3-structured-witness",
)
    settings.contract_id == "d3-stage3-structured-fit-settings.v1" ||
        error("D3 Stage-3 structured fit requires validated V1 settings.")
    hasproperty(stage3_candidate, :u_IDC) ||
        error("D3 Stage-3 candidate must expose its fixed u_IDC.")
    u_idc = _d3_stage3_structured_finite_positive(
        stage3_candidate.u_IDC,
        "D3 Stage-3 candidate u_IDC",
    )

    hybridized_trace = d3_compiled_port_trace(
        hybridized_model,
        settings.frequency_hz,
    )
    pole_gate = _d3_stage3_structured_pole_gate(
        hybridized_trace.poles.frequencies_hz,
        settings,
    )
    pole_gate.status == :passed || return pole_gate
    regions = _d3_stage3_structured_regions(
        settings,
        pole_gate.matched_poles_hz,
    )
    regions.status == :passed || return regions
    sample_weights = _d3_stage3_structured_sample_weights(settings, regions)
    target_s21 = hybridized_trace.s21
    cache = Dict{NTuple{6,Float64},Vector{ComplexF64}}()
    identity = (u_idc=u_idc, label=String(id))

    function predicted_s21(candidate)
        key = Tuple(values(candidate))
        return get!(cache, key) do
            _d3_stage3_structured_extract(
                candidate,
                fixed,
                idc_mapping,
                settings;
                id=identity,
            ).s21
        end
    end
    function cost(unit_coordinates)
        candidate = _d3_stage3_structured_decode_unit(
            unit_coordinates,
            settings.witness_bounds,
        )
        residual = predicted_s21(candidate) - target_s21
        return sum(sample_weights .* abs2.(residual))
    end

    function cma_start_record(start, index)
        initial_unit = _d3_stage3_structured_unit(
            start,
            settings.witness_bounds,
        )
        initial_cost = cost(initial_unit)
        best = Ref((cost=initial_cost, unit=copy(initial_unit)))
        calls = Ref(1)
        function tracked_cost(unit_coordinates)
            calls[] += 1
            observed = cost(unit_coordinates)
            if observed < best[].cost
                best[] = (cost=observed, unit=copy(unit_coordinates))
            end
            return observed
        end
        result = CMAEvolutionStrategy.minimize(
            tracked_cost,
            initial_unit,
            0.12;
            lower=fill(eps(Float64), length(initial_unit)),
            upper=fill(1.0 - eps(Float64), length(initial_unit)),
            popsize=12,
            seed=20260900 + index,
            maxiter=settings.optimizer_iterations,
            maxfevals=settings.optimizer_function_calls,
            xtol=nothing,
            ftol=nothing,
            parallel_evaluation=false,
            multi_threading=false,
            noise_handling=nothing,
            verbosity=0,
        )
        recent_ranges = last(
            Float64.(result.logger.frange),
            min(3, length(result.logger.frange)),
        )
        observed_ftol = isempty(recent_ranges) ?
            Inf : maximum(recent_ranges)
        observed_xtol = maximum(abs.(
            CMAEvolutionStrategy.sigma(result.p) .* result.p.cov.p
        ))
        joint_convergence =
            observed_ftol <= settings.optimizer_f_abstol &&
            observed_xtol <= settings.optimizer_x_abstol
        candidate = _d3_stage3_structured_decode_unit(
            best[].unit,
            settings.witness_bounds,
        )
        residual = predicted_s21(candidate) - target_s21
        return (
            start_index=index,
            optimizer_algorithm=:cma_es,
            optimizer_converged=joint_convergence,
            iteration_limit_reached=result.stop.reason in
                (:maxiter, :maxfevals),
            termination_reason=result.stop.reason,
            observed_ftol=observed_ftol,
            observed_xtol=observed_xtol,
            iterations=Int(result.stop.it),
            function_calls=calls[],
            minimum_weighted_complex_mse=best[].cost,
            candidate=candidate,
            response=_d3_stage3_structured_response_metrics(
                residual,
                sample_weights,
                regions,
                settings,
            )
        )
    end
    start_records = [
        cma_start_record(start, index)
        for (index, start) in enumerate(settings.witness_starts)
    ]
    converged = filter(record -> record.optimizer_converged, start_records)
    length(converged) >= 2 || return _d3_stage3_structured_unidentified(
        :fit_multistart_not_converged,
        "Fewer than two deterministic witness starts converged.";
        pole_gate=pole_gate,
        regions=regions,
        starts=start_records,
    )

    extracted_starts = NamedTuple[]
    for record in converged
        extracted = try
            _d3_stage3_structured_extract(
                record.candidate,
                fixed,
                idc_mapping,
                settings;
                id=identity,
            )
        catch exception
            message = sprint(showerror, exception)
            if occursin("feedline-downfolded", message) ||
               occursin("loaded-bare", message)
                return _d3_stage3_structured_unidentified(
                    :fit_loaded_bare_quantity_unidentified,
                    "A converged witness does not expose unique loaded-bare roots in the declared extraction band.";
                    pole_gate=pole_gate,
                    regions=regions,
                    starts=start_records,
                    failed_start_index=record.start_index,
                    extraction_error=message,
                )
            end
            rethrow()
        end
        push!(extracted_starts, merge(record, (extracted=extracted.extracted,)))
    end
    normalized_parameters = [
        _d3_stage3_structured_unit(record.candidate, settings.witness_bounds)
        for record in extracted_starts
    ]
    parameter_spread = maximum(
        maximum(values) - minimum(values)
        for values in eachrow(reduce(hcat, normalized_parameters))
    )
    fr_spread = maximum(record.extracted.fr_qrp_on_hz for record in extracted_starts) -
        minimum(record.extracted.fr_qrp_on_hz for record in extracted_starts)
    fp_spread = maximum(record.extracted.fp_qrp_on_hz for record in extracted_starts) -
        minimum(record.extracted.fp_qrp_on_hz for record in extracted_starts)
    J_spread = maximum(record.extracted.J_qrp_on_hz for record in extracted_starts) -
        minimum(record.extracted.J_qrp_on_hz for record in extracted_starts)
    cluster = (
        converged_start_count=length(extracted_starts),
        maximum_normalized_parameter_spread=parameter_spread,
        fr_spread_hz=fr_spread,
        fp_spread_hz=fp_spread,
        J_spread_hz=J_spread,
    )
    cluster_pass =
        parameter_spread <= settings.maximum_normalized_parameter_start_spread &&
        fr_spread <= settings.maximum_fr_start_spread_hz &&
        fp_spread <= settings.maximum_fp_start_spread_hz &&
        J_spread <= settings.maximum_J_start_spread_hz
    cluster_pass || return _d3_stage3_structured_unidentified(
        :fit_multistart_cluster_unresolved,
        "Converged witness starts do not identify one common parameter/quantity cluster.";
        pole_gate=pole_gate,
        regions=regions,
        starts=start_records,
        converged_starts=extracted_starts,
        cluster=cluster,
    )

    best = first(sort(extracted_starts; by=record -> record.minimum_weighted_complex_mse))
    best_full = _d3_stage3_structured_extract(
        best.candidate,
        fixed,
        idc_mapping,
        settings;
        id=identity,
    )
    port_identity = _d3_stage3_structured_port_identity(
        hybridized_model,
        best_full.model,
    )
    best_residual = best_full.s21 - target_s21
    response = _d3_stage3_structured_response_metrics(
        best_residual,
        sample_weights,
        regions,
        settings,
    )
    response_pass =
        response.weighted_complex_rmse <=
            settings.maximum_weighted_complex_rmse &&
        response.complex_max_abs <= settings.maximum_complex_max_abs
    response_pass || return _d3_stage3_structured_unidentified(
        :fit_response_gate_failed,
        "The best structured witness does not reproduce the Hybridized complex S21 within the declared gates.";
        pole_gate=pole_gate,
        regions=regions,
        starts=start_records,
        converged_starts=extracted_starts,
        cluster=cluster,
        response=response,
        fitted_candidate=best_full.candidate,
    )

    best_unit = _d3_stage3_structured_unit(
        best.candidate,
        settings.witness_bounds,
    )
    bound_margins = min.(best_unit, 1 .- best_unit)
    minimum_bound_margin = minimum(bound_margins)
    bound_diagnostics = (
        normalized_coordinates=best_unit,
        margins=NamedTuple{D3_STAGE3_WITNESS_VARIABLE_ORDER}(
            Tuple(bound_margins),
        ),
        minimum_margin=minimum_bound_margin,
        required_minimum_margin=settings.minimum_bound_margin_fraction,
    )
    minimum_bound_margin >= settings.minimum_bound_margin_fraction ||
        return _d3_stage3_structured_unidentified(
            :fit_bound_pinned,
            "At least one fitted witness parameter is too close to a declared bound.";
            pole_gate=pole_gate,
            regions=regions,
            starts=start_records,
            converged_starts=extracted_starts,
            cluster=cluster,
            response=response,
            fitted_candidate=best_full.candidate,
            bound=bound_diagnostics,
        )

    residual_dimension = 2length(settings.frequency_hz)
    parameter_count = length(D3_STAGE3_WITNESS_VARIABLE_ORDER)
    jacobian = zeros(Float64, residual_dimension, parameter_count)
    step = settings.jacobian_step_fraction
    sqrt_weights = sqrt.(sample_weights)
    function scaled_residual_vector(unit_coordinates)
        candidate = _d3_stage3_structured_decode_unit(
            unit_coordinates,
            settings.witness_bounds,
        )
        residual = predicted_s21(candidate) - target_s21
        return vcat(
            sqrt_weights .* real.(residual),
            sqrt_weights .* imag.(residual),
        )
    end
    for parameter in 1:parameter_count
        plus = copy(best_unit)
        minus = copy(best_unit)
        plus[parameter] += step
        minus[parameter] -= step
        jacobian[:, parameter] .=
            (scaled_residual_vector(plus) - scaled_residual_vector(minus)) /
            (2step)
    end
    singular_values = svdvals(jacobian)
    minimum_singular = minimum(singular_values)
    maximum_singular = maximum(singular_values)
    condition_number =
        minimum_singular > 0 ? maximum_singular / minimum_singular : Inf
    numerical_rank = count(
        value -> value >= settings.minimum_jacobian_singular_value,
        singular_values,
    )
    jacobian_diagnostics = (
        coordinate=:normalized_response_equivalent_witness_parameter,
        finite_difference_step_fraction=step,
        residual=:fixed_region_weighted_complex_s21,
        shape=size(jacobian),
        singular_values=singular_values,
        minimum_singular_value=minimum_singular,
        maximum_singular_value=maximum_singular,
        condition_number=condition_number,
        numerical_rank=numerical_rank,
        required_rank=parameter_count,
        minimum_singular_value_gate=
            settings.minimum_jacobian_singular_value,
        maximum_condition_gate=settings.maximum_jacobian_condition,
    )
    jacobian_pass =
        numerical_rank == parameter_count &&
        condition_number <= settings.maximum_jacobian_condition
    jacobian_pass || return _d3_stage3_structured_unidentified(
        :fit_local_identifiability_failed,
        "The scaled complex-S21 Jacobian does not identify all six witness parameters.";
        pole_gate=pole_gate,
        regions=regions,
        starts=start_records,
        converged_starts=extracted_starts,
        cluster=cluster,
        response=response,
        fitted_candidate=best_full.candidate,
        bound=bound_diagnostics,
        jacobian=jacobian_diagnostics,
    )

    return (
        contract_id="d3-stage3-structured-witness-fit.v1",
        semantic_state=:CONVERGING,
        status=:identified_candidate,
        fitted_candidate=best_full.candidate,
        extracted=best_full.extracted,
        response=response,
        fit=(
            starts=start_records,
            converged_starts=extracted_starts,
            cluster=cluster,
            selected_start_index=best.start_index,
            cache_entry_count=length(cache),
        ),
        gates=(
            pole_presence=pole_gate,
            regions=regions,
            port_identity=port_identity,
            bound=bound_diagnostics,
            jacobian=jacobian_diagnostics,
        ),
        provenance=(
            hybridized_model_identity=(
                circuit_plan_sha256=
                    hybridized_model.provenance.circuit_plan_sha256,
                capacitance_sha256=
                    hybridized_model.provenance.capacitance_sha256,
                inverse_inductance_sha256=
                    hybridized_model.provenance.inverse_inductance_sha256,
                selector_sha256=hybridized_model.provenance.selector_sha256,
            ),
            witness_model_identity=(
                circuit_plan_sha256=
                    best_full.model.provenance.circuit_plan_sha256,
                capacitance_sha256=
                    best_full.model.provenance.capacitance_sha256,
                inverse_inductance_sha256=
                    best_full.model.provenance.inverse_inductance_sha256,
                selector_sha256=best_full.model.provenance.selector_sha256,
            ),
            u_IDC_fixed=u_idc,
            loaded_bare=best_full.loaded_bare,
            matrix_metrics=best_full.matrix_metrics,
        ),
    )
end
