# D3 Stage-3 coupling-on research comparison. This file deliberately compares
# the direct Hybridized response with one hash-bound Stage-2 direct-response
# receipt; it does not define loaded-bare coordinates, optimizer bounds, or a
# promotable Stage-3 objective.

using LinearAlgebra
using SHA
using SuperconductingCircuitsCore

const D3_DIRECT_JSON3 = SuperconductingCircuitsCore.JSON3
const D3_STAGE2_FULL_RECEIPT_SCHEMA = "d3-stage2-full-direct-receipt.v1"

function _d3_direct_sha256_file(path)
    open(path, "r") do io
        bytes2hex(SHA.sha256(io))
    end
end

function _d3_direct_sha256(value, label)
    text = lowercase(strip(String(value)))
    occursin(r"^[0-9a-f]{64}$", text) ||
        error("$(label) must be one lowercase SHA-256.")
    return text
end

function _d3_direct_complex(raw, label)
    values = Float64.(collect(raw))
    length(values) == 2 && all(isfinite, values) ||
        error("$(label) must contain finite [real, imaginary] values.")
    return ComplexF64(values[1], values[2])
end

function _d3_direct_model_identity(raw)
    fields = (
        :circuit_plan_sha256,
        :capacitance_sha256,
        :inverse_inductance_sha256,
        :selector_sha256,
    )
    return NamedTuple{fields}(Tuple(
        _d3_direct_sha256(raw[String(field)], "Stage-2 $(field)")
        for field in fields
    ))
end

"""
    d3_load_stage2_full_receipt(path)

Load and validate the complete Stage-2 direct-response reference consumed by
the coupling-on Stage-3 research route. File identity is byte-for-byte SHA-256;
the numerical arrays additionally carry the same matrix hashes used by the D3
finite-order implementation.
"""
function d3_load_stage2_full_receipt(path)
    input_path = abspath(String(path))
    isfile(input_path) ||
        error("D3 Stage-2 full receipt does not exist: $(input_path)")
    raw = D3_DIRECT_JSON3.read(read(input_path, String), Dict{String,Any})
    raw["schema_version"] == D3_STAGE2_FULL_RECEIPT_SCHEMA ||
        error("D3 Stage-2 full receipt schema is unsupported.")
    status = Symbol(raw["status"])
    status in (
        :stage2_gate_passing_nonpromotable,
        :stage2_pareto_nonpromotable,
    ) || error("D3 Stage-2 full receipt status is unsupported.")

    grid = Float64.(collect(raw["grid"]["frequency_hz"]))
    !isempty(grid) && all(isfinite, grid) && all(diff(grid) .> 0) ||
        error("D3 Stage-2 receipt frequency grid must be increasing and finite.")
    grid_hash = _d3_exact_n_matrix_sha256(
        "d3-stage2-direct-frequency-grid-hz",
        reshape(grid, :, 1),
    )
    grid_hash == _d3_direct_sha256(
        raw["grid"]["sha256"],
        "D3 Stage-2 frequency-grid hash",
    ) || error("D3 Stage-2 receipt frequency-grid hash does not match.")
    grid_spec = raw["condition"]["response_grid"]
    grid_count = Int(grid_spec["count"])
    replayed_grid = collect(range(
        Float64(grid_spec["start_hz"]),
        Float64(grid_spec["stop_hz"]);
        length=grid_count,
    ))
    replayed_grid == grid ||
        error("D3 Stage-2 receipt grid disagrees with its replay specification.")

    s21 = ComplexF64[
        _d3_direct_complex(value, "D3 Stage-2 S21 sample")
        for value in raw["direct_response"]["s21"]
    ]
    length(s21) == length(grid) ||
        error("D3 Stage-2 receipt S21 length disagrees with its grid.")
    s21_hash = _d3_exact_n_complex_matrix_sha256(
        "d3-stage2-direct-s21",
        reshape(s21, :, 1),
    )
    s21_hash == _d3_direct_sha256(
        raw["direct_response"]["s21_sha256"],
        "D3 Stage-2 S21 hash",
    ) || error("D3 Stage-2 receipt S21 hash does not match.")

    poles = ComplexF64[]
    linewidths = Float64[]
    for record in raw["positive_open_poles"]
        pole = _d3_direct_complex(
            record["frequency_hz"],
            "D3 Stage-2 positive open pole",
        )
        real(pole) > 0 && imag(pole) <= 0 ||
            error("D3 Stage-2 receipt contains a non-passive positive pole.")
        linewidth = Float64(record["linewidth_hz"])
        isfinite(linewidth) && linewidth >= 0 ||
            error("D3 Stage-2 pole linewidth must be finite and nonnegative.")
        isapprox(linewidth, max(-2 * imag(pole), 0.0); rtol=1e-12, atol=1e-6) ||
            error("D3 Stage-2 pole linewidth disagrees with its complex pole.")
        push!(poles, pole)
        push!(linewidths, linewidth)
    end
    !isempty(poles) || error("D3 Stage-2 receipt must contain positive open poles.")

    ports = raw["ports"]
    Symbol.(collect(ports["ids"])) == [:input_port, :output_port] ||
        error("D3 Stage-2 receipt must bind ordered input/output ports.")
    reference_impedance = Float64.(collect(ports["reference_impedance_ohm"]))
    reference_impedance == [50.0, 50.0] ||
        error("D3 Stage-2 direct research reference requires two 50-ohm ports.")
    time_convention = String(ports["time_convention"])
    time_convention == "exp(-i*omega*t)" ||
        error("D3 Stage-2 receipt time convention is unsupported.")

    gates_pass = Bool(raw["objective"]["target_gates_pass"])
    gates_pass == (status == :stage2_gate_passing_nonpromotable) ||
        error("D3 Stage-2 receipt status disagrees with its target gates.")
    notch_hz = Float64(raw["notch"]["frequency_hz"])
    isfinite(notch_hz) && notch_hz > 0 ||
        error("D3 Stage-2 receipt notch must be finite and positive.")

    slot_hz = Float64(raw["slot_hz"])
    isfinite(slot_hz) && slot_hz > 0 ||
        error("D3 Stage-2 receipt Slot must be finite and positive.")
    return (
        schema_version=D3_STAGE2_FULL_RECEIPT_SCHEMA,
        receipt_path=input_path,
        receipt_sha256=_d3_direct_sha256_file(input_path),
        status=status,
        slot_hz=slot_hz,
        target_contract_sha256=_d3_direct_sha256(
            raw["target_contract_sha256"],
            "D3 Stage-2 target-contract hash",
        ),
        model_identity=_d3_direct_model_identity(raw["model_identity"]),
        grid=(frequency_hz=grid, sha256=grid_hash),
        ports=(
            ids=[:input_port, :output_port],
            reference_impedance_ohm=reference_impedance,
            time_convention=time_convention,
        ),
        direct_response=(s21=s21, s21_sha256=s21_hash),
        positive_open_poles=(
            frequencies_hz=poles,
            linewidths_hz=linewidths,
        ),
        notch=(frequency_hz=notch_hz,),
        stage2_target_gates_pass=gates_pass,
        raw=raw,
    )
end

function _d3_direct_in_band_poles(poles, band_hz, label)
    band = Float64.(collect(band_hz))
    length(band) == 2 && all(isfinite, band) && 0 < band[1] < band[2] ||
        error("$(label) pole band must contain increasing positive bounds.")
    selected = ComplexF64[
        pole for pole in poles
        if band[1] <= real(pole) <= band[2]
    ]
    !isempty(selected) || error("$(label) has no positive pole in the declared band.")
    length(selected) <= 20 || error(
        "$(label) pole band contains more than the exact set matcher supports.",
    )
    return selected, band
end

# Exact O(n*2^n) minimum-cost bijection. D3 research bands contain only a
# handful of physical poles, so a general assignment dependency is unnecessary.
function _d3_direct_pole_set_match(reference, observed, scale_hz)
    count = length(reference)
    count == length(observed) ||
        error("D3 Stage-2/3 in-band positive-pole counts disagree.")
    scale = Float64(scale_hz)
    isfinite(scale) && scale > 0 ||
        error("D3 pole-distance scale must be finite and positive.")
    state_count = 1 << count
    costs = fill(Inf, state_count)
    paths = [Int[] for _ in 1:state_count]
    costs[1] = 0.0
    for mask in 0:(state_count - 1)
        row = count_ones(mask) + 1
        row > count && continue
        current = costs[mask + 1]
        isfinite(current) || continue
        for column in 1:count
            bit = 1 << (column - 1)
            mask & bit == 0 || continue
            next_mask = mask | bit
            distance = abs2((observed[column] - reference[row]) / scale)
            candidate = current + distance
            if candidate < costs[next_mask + 1]
                costs[next_mask + 1] = candidate
                paths[next_mask + 1] = vcat(paths[mask + 1], column)
            end
        end
    end
    assignment = paths[end]
    length(assignment) == count ||
        error("D3 complex-pole set assignment did not close.")
    matched = observed[assignment]
    residual = matched - reference
    reference_linewidths = max.(-2 .* imag.(reference), 0.0)
    observed_linewidths = max.(-2 .* imag.(matched), 0.0)
    reference_sum = sum(reference_linewidths)
    observed_sum = sum(observed_linewidths)
    return (
        assignment=assignment,
        reference_frequencies_hz=reference,
        observed_frequencies_hz=matched,
        complex_residual_hz=residual,
        rms_complex_distance_hz=sqrt(sum(abs2, residual) / count),
        max_complex_distance_hz=maximum(abs, residual),
        reference_linewidths_hz=reference_linewidths,
        observed_linewidths_hz=observed_linewidths,
        linewidth_residual_hz=observed_linewidths - reference_linewidths,
        reference_anonymous_linewidth_share=
            reference_sum > 0 ? reference_linewidths ./ reference_sum : nothing,
        observed_anonymous_linewidth_share=
            observed_sum > 0 ? observed_linewidths ./ observed_sum : nothing,
        role=:report_only_unordered_pole_set,
        physical_mode_labels=:not_assigned,
    )
end

"""
    d3_stage3_direct_research_evaluation(reference, candidate, fixed, idc_mapping; ...)

Evaluate one complete coupling-on Hybridized candidate against one complete
Stage-2 direct-response receipt. The only cost residuals are complex-S21 RMSE
and the independent intrinsic-pair RP-on notch delta. Pole-set matching is
permutation invariant and report-only. Loaded-bare `fr`, `fp`, and `J` are
intentionally excluded.
"""
function d3_stage3_direct_research_evaluation(
    reference,
    candidate,
    fixed,
    idc_mapping;
    notch_frequency_bracket_hz,
    pole_band_hz,
    complex_s21_scale,
    notch_frequency_scale_hz,
    pole_distance_scale_hz,
    exact_closure_tolerance,
    passivity_tolerance_hz,
    expected_target_contract_sha256,
    id="d3-stage3-direct-research-candidate",
)
    s21_scale = Float64(complex_s21_scale)
    notch_scale = Float64(notch_frequency_scale_hz)
    closure_tolerance = Float64(exact_closure_tolerance)
    passive_tolerance = Float64(passivity_tolerance_hz)
    all(value -> isfinite(value) && value > 0, (
        s21_scale,
        notch_scale,
        closure_tolerance,
        passive_tolerance,
    )) || error("D3 Stage-3 direct research scales must be finite and positive.")
    expected_target = _d3_direct_sha256(
        expected_target_contract_sha256,
        "D3 Stage-3 expected target-contract hash",
    )
    reference.target_contract_sha256 == expected_target ||
        error("D3 Stage-2 receipt belongs to a different target contract.")

    stage = d3_stage3_hybridized_model(
        candidate,
        fixed,
        idc_mapping;
        id=id,
    )
    model = d3_hybridized_compiled_model(stage.built)
    model.port_ids == reference.ports.ids ||
        error("D3 Stage-2/3 ordered port IDs disagree.")
    model.reference_impedance_ohm == reference.ports.reference_impedance_ohm ||
        error("D3 Stage-2/3 reference impedances disagree.")
    model.provenance.time_convention == reference.ports.time_convention ||
        error("D3 Stage-2/3 time conventions disagree.")
    cqed_handoff = d3_numerical_cqed_handoff(model)
    closure = _d3_stage_response_closure(
        model,
        cqed_handoff,
        reference.grid.frequency_hz,
    )
    closure.frequency_hz == reference.grid.frequency_hz ||
        error("D3 Stage-3 response grid differs from the Stage-2 receipt.")
    closure.residuals.max_abs_exact_s21 <= closure_tolerance ||
        error(
            "D3 Stage-3 exact/direct S21 closure " *
            "$(closure.residuals.max_abs_exact_s21) exceeds its " *
            "caller-owned gate $(closure_tolerance).",
        )

    open_eigenvalues =
        eigvals(cqed_handoff.port_response.exact.open_generator_per_s)
    maximum(real.(open_eigenvalues)) / (2π) <= passive_tolerance ||
        error("D3 Stage-3 exact-open generator violates its passivity gate.")
    observed_s21 = closure.direct.s21
    length(observed_s21) == length(reference.direct_response.s21) ||
        error("D3 Stage-2/3 S21 lengths disagree.")
    s21_residual = observed_s21 - reference.direct_response.s21
    s21_rmse = sqrt(sum(abs2, s21_residual) / length(s21_residual))

    notch = d3_intrinsic_pair_notch_frequency(
        stage.auxiliary.notch,
        notch_frequency_bracket_hz,
    )
    notch_target_hz = 5.0e9
    notch_delta_hz = notch.frequency_hz - notch_target_hz

    reference_poles, band = _d3_direct_in_band_poles(
        reference.positive_open_poles.frequencies_hz,
        pole_band_hz,
        "D3 Stage-2 reference",
    )
    observed_poles, _ = _d3_direct_in_band_poles(
        closure.direct.poles.frequencies_hz,
        band,
        "D3 Stage-3 candidate",
    )
    pole_set = if length(reference_poles) == length(observed_poles)
        merge(
            _d3_direct_pole_set_match(
                reference_poles,
                observed_poles,
                pole_distance_scale_hz,
            ),
            (
                comparison_status=:matched,
                reference_count=length(reference_poles),
                observed_count=length(observed_poles),
            ),
        )
    else
        (
            comparison_status=:count_mismatch_report_only,
            reference_count=length(reference_poles),
            observed_count=length(observed_poles),
            assignment=nothing,
            reference_frequencies_hz=reference_poles,
            observed_frequencies_hz=observed_poles,
            complex_residual_hz=nothing,
            rms_complex_distance_hz=nothing,
            max_complex_distance_hz=nothing,
            reference_linewidths_hz=
                max.(-2 .* imag.(reference_poles), 0.0),
            observed_linewidths_hz=
                max.(-2 .* imag.(observed_poles), 0.0),
            linewidth_residual_hz=nothing,
            reference_anonymous_linewidth_share=nothing,
            observed_anonymous_linewidth_share=nothing,
            role=:report_only_unordered_pole_set,
            physical_mode_labels=:not_assigned,
        )
    end
    normalized_residuals = (
        r_complex_s21=s21_rmse / s21_scale,
        r_intrinsic_pair_notch=notch_delta_hz / notch_scale,
    )
    inherited_failure = !reference.stage2_target_gates_pass
    return (
        contract_id="d3-stage3-direct-coupling-on-research.v1",
        status=inherited_failure ?
            :research_nonpromotable_inherits_stage2_failure :
            :research_nonpromotable,
        stage_id=:stage3_hybridized_direct_research,
        model_family=:hybridized_distributed_lumped,
        stage2_reference=(
            receipt_sha256=reference.receipt_sha256,
            status=reference.status,
            model_identity=reference.model_identity,
            target_contract_sha256=reference.target_contract_sha256,
        ),
        stage=stage,
        model=model,
        cqed_handoff=cqed_handoff,
        response_closure=closure,
        direct_comparison=(
            frequency_hz=reference.grid.frequency_hz,
            reference_s21=reference.direct_response.s21,
            observed_s21=observed_s21,
            complex_s21_residual=s21_residual,
            complex_s21_rmse=s21_rmse,
        ),
        notch_comparison=(
            target_frequency_hz=notch_target_hz,
            stage2_reference_frequency_hz=reference.notch.frequency_hz,
            observed=notch,
            delta_hz=notch_delta_hz,
        ),
        pole_set_comparison=merge(
            pole_set,
            (frequency_band_hz=band,),
        ),
        normalized_residuals=normalized_residuals,
        cost=sum(abs2, values(normalized_residuals)),
        optimizer_metrics=normalized_residuals,
        promotion_eligible=false,
        excluded_quantities=(
            :fr_qrp_on_hz,
            :fp_qrp_on_hz,
            :J_qrp_on_hz,
            :eta_r_qrp_on,
            :eta_p_qrp_on,
        ),
        quantity_scope=(
            coupling_state=:qrp_on,
            complex_s21=:cost,
            intrinsic_pair_notch=:cost,
            unordered_open_poles=:report_only,
            anonymous_linewidth_share=:report_only,
            loaded_bare_parameter_realization=:not_claimed,
        ),
    )
end
