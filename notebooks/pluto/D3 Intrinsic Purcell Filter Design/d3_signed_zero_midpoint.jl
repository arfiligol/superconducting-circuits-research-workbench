# Shared D3 signed-zero extraction on one predeclared frequency grid. This file
# owns only the adjacent-bracket midpoint and its evidence receipt; response
# construction, branch qualification, grid eligibility, and objectives remain
# with their existing owners.

module D3SignedZeroMidpoint

include(joinpath(@__DIR__, "d3_semantic_hash.jl"))
using .D3SemanticHash: semantic_value_sha256

export d3_signed_zero_grid_identity, d3_signed_zero_midpoint

const CONTRACT_ID = "d3-signed-zero-midpoint-extraction.v1"
const GRID_IDENTITY_SCHEMA = "d3-signed-zero-frequency-grid.v1"
const OBSERVABLES = (
    f_r=(response_family=:admittance, response_component=:Y_rr, signed_value_unit=:siemens),
    f_p=(response_family=:admittance, response_component=:Y_pp, signed_value_unit=:siemens),
    f_n=(response_family=:impedance, response_component=:Z21, signed_value_unit=:ohm),
)

function _d3_signed_zero_text(value, label)
    value isa Union{AbstractString,Symbol} || error("$(label) must be text.")
    text = strip(String(value))
    isempty(text) && error("$(label) must not be empty.")
    return text
end

function _d3_signed_zero_positive(value, label)
    value isa Real && !(value isa Bool) || error("$(label) must be real.")
    number = Float64(value)
    isfinite(number) && number > 0 || error("$(label) must be finite and positive.")
    return number
end

function _d3_signed_zero_grid(frequency_grid_hz)
    raw = collect(frequency_grid_hz)
    length(raw) >= 2 || error("D3 signed-zero grid must contain at least two points.")
    frequencies = map(enumerate(raw)) do (index, value)
        _d3_signed_zero_positive(value, "D3 signed-zero grid point $(index)")
    end
    steps = diff(frequencies)
    all(>(0), steps) || error("D3 signed-zero grid must be strictly increasing.")
    step = first(steps)
    all(==(step), steps) || error("D3 signed-zero grid must have one exact step.")
    return frequencies, step, (first(frequencies), last(frequencies))
end

function d3_signed_zero_grid_identity(frequency_grid_hz)
    frequencies, _, _ = _d3_signed_zero_grid(frequency_grid_hz)
    return semantic_value_sha256(Dict(
        "schema_version" => GRID_IDENTITY_SCHEMA,
        "frequency_hz" => frequencies,
    ))
end

function _d3_signed_zero_receipt(
    base;
    status,
    failure_reason,
    bracket_count=nothing,
    lower_endpoint=nothing,
    upper_endpoint=nothing,
    midpoint_frequency_hz=nothing,
    half_width_hz=nothing,
    checks,
)
    return merge(base, (
        bracket_count=bracket_count,
        lower_endpoint=lower_endpoint,
        upper_endpoint=upper_endpoint,
        midpoint_frequency_hz=midpoint_frequency_hz,
        half_width_hz=half_width_hz,
        checks=checks,
        status=status,
        failure_reason=failure_reason,
    ))
end

_d3_signed_zero_failure(base, reason, checks; kwargs...) =
    _d3_signed_zero_receipt(
        base;
        status="FAIL",
        failure_reason=reason,
        checks=checks,
        kwargs...,
    )

"""
    d3_signed_zero_midpoint(frequency_grid_hz, response; ...)

Evaluate one complex response on a declared uniform grid, require exactly one
strict adjacent sign change of its imaginary part, qualify that bracket, and
return its frequency midpoint without refinement. A failed receipt has no
midpoint and cannot initialize a downstream frequency operand.

`bracket_qualifier(lower_hz, upper_hz, lower_response, upper_response)` must
return exactly `(pole_free, branch_unambiguous, branch_identity)`.
"""
function d3_signed_zero_midpoint(
    frequency_grid_hz,
    response;
    observable_id,
    grid_identity,
    grid_step_hz,
    grid_window_hz,
    branch_identity,
    bracket_qualifier,
)
    observable = Symbol(observable_id)
    hasproperty(OBSERVABLES, observable) || error(
        "D3 signed-zero observable must be one of $(propertynames(OBSERVABLES)).",
    )
    mapping = getproperty(OBSERVABLES, observable)
    declared_identity = lowercase(_d3_signed_zero_text(
        grid_identity,
        "D3 signed-zero grid identity",
    ))
    occursin(r"^[0-9a-f]{64}$", declared_identity) || error(
        "D3 signed-zero grid identity must be a lowercase SHA-256.",
    )
    declared_step = _d3_signed_zero_positive(
        grid_step_hz,
        "D3 signed-zero grid step",
    )
    declared_window = map(enumerate(collect(grid_window_hz))) do (index, value)
        _d3_signed_zero_positive(value, "D3 signed-zero grid window endpoint $(index)")
    end
    length(declared_window) == 2 && declared_window[1] < declared_window[2] || error(
        "D3 signed-zero grid window must contain two finite increasing endpoints.",
    )
    branch = _d3_signed_zero_text(branch_identity, "D3 signed-zero branch identity")

    frequencies, actual_step, actual_window = _d3_signed_zero_grid(frequency_grid_hz)
    actual_identity = d3_signed_zero_grid_identity(frequencies)
    base = (
        contract_id=CONTRACT_ID,
        observable=(
            id=observable,
            response_family=mapping.response_family,
            response_component=mapping.response_component,
            signed_projection=:imaginary,
            signed_value_unit=mapping.signed_value_unit,
        ),
        branch_identity=branch,
        grid=(
            identity=actual_identity,
            declared_identity=declared_identity,
            count=length(frequencies),
            step_hz=actual_step,
            declared_step_hz=declared_step,
            window_hz=actual_window,
            declared_window_hz=Tuple(declared_window),
        ),
    )
    checks = (
        grid_identity_match=actual_identity == declared_identity,
        grid_step_match=actual_step == declared_step,
        grid_window_match=actual_window == Tuple(declared_window),
        finite_response_samples=nothing,
        exact_grid_zero_absent=nothing,
        unique_bracket=nothing,
        pole_free=nothing,
        branch_unambiguous=nothing,
        branch_identity_match=nothing,
    )
    all((checks.grid_identity_match, checks.grid_step_match, checks.grid_window_match)) ||
        return _d3_signed_zero_failure(
            base,
            "grid_identity_step_or_window_mismatch",
            checks,
        )

    responses = ComplexF64[]
    for frequency in frequencies
        raw = try
            response(frequency)
        catch
            return _d3_signed_zero_failure(base, "response_evaluation_failed", checks)
        end
        raw isa Complex ||
            return _d3_signed_zero_failure(base, "response_is_not_complex", checks)
        value = ComplexF64(raw)
        isfinite(real(value)) && isfinite(imag(value)) ||
            return _d3_signed_zero_failure(
                base,
                "nonfinite_response_sample",
                merge(checks, (finite_response_samples=false,)),
            )
        push!(responses, value)
    end
    signed_values = imag.(responses)
    checks = merge(checks, (finite_response_samples=true,))
    bracket_indices = findall(
        index -> begin
            lower = signed_values[index]
            upper = signed_values[index + 1]
            (lower < 0 && upper > 0) || (lower > 0 && upper < 0)
        end,
        1:(length(frequencies) - 1),
    )
    bracket_count = length(bracket_indices)
    any(iszero, signed_values) && return _d3_signed_zero_failure(
        base,
        "exact_zero_on_declared_grid",
        merge(checks, (exact_grid_zero_absent=false, unique_bracket=false));
        bracket_count,
    )
    checks = merge(checks, (exact_grid_zero_absent=true,))

    bracket_count == 1 || return _d3_signed_zero_failure(
        base,
        iszero(bracket_count) ? "no_sign_change_bracket" :
            "multiple_sign_change_brackets",
        merge(checks, (unique_bracket=false,));
        bracket_count,
    )
    checks = merge(checks, (unique_bracket=true,))
    index = only(bracket_indices)
    lower_endpoint = (
        frequency_hz=frequencies[index],
        signed_value=signed_values[index],
    )
    upper_endpoint = (
        frequency_hz=frequencies[index + 1],
        signed_value=signed_values[index + 1],
    )
    bracket_evidence = (
        bracket_count=1,
        lower_endpoint=lower_endpoint,
        upper_endpoint=upper_endpoint,
    )

    qualification = try
        bracket_qualifier(
            lower_endpoint.frequency_hz,
            upper_endpoint.frequency_hz,
            responses[index],
            responses[index + 1],
        )
    catch
        return _d3_signed_zero_failure(
            base,
            "bracket_qualification_failed",
            checks;
            bracket_evidence...,
        )
    end
    qualification isa NamedTuple &&
        Set(propertynames(qualification)) ==
            Set((:pole_free, :branch_unambiguous, :branch_identity)) ||
        return _d3_signed_zero_failure(
            base,
            "invalid_bracket_qualification",
            checks;
            bracket_evidence...,
        )
    qualification.pole_free isa Bool && qualification.branch_unambiguous isa Bool ||
        return _d3_signed_zero_failure(
            base,
            "invalid_bracket_qualification",
            checks;
            bracket_evidence...,
        )
    qualified_branch = try
        _d3_signed_zero_text(
            qualification.branch_identity,
            "D3 signed-zero qualified branch identity",
        )
    catch
        return _d3_signed_zero_failure(
            base,
            "invalid_bracket_qualification",
            checks;
            bracket_evidence...,
        )
    end
    checks = merge(checks, (
        pole_free=qualification.pole_free,
        branch_unambiguous=qualification.branch_unambiguous,
        branch_identity_match=qualified_branch == branch,
    ))
    qualification.pole_free || return _d3_signed_zero_failure(
        base,
        "pole_inside_sign_change_bracket",
        checks;
        bracket_evidence...,
    )
    qualification.branch_unambiguous || return _d3_signed_zero_failure(
        base,
        "branch_ambiguity_inside_sign_change_bracket",
        checks;
        bracket_evidence...,
    )
    checks.branch_identity_match || return _d3_signed_zero_failure(
        base,
        "branch_identity_mismatch",
        checks;
        bracket_evidence...,
    )

    half_width_hz = (upper_endpoint.frequency_hz - lower_endpoint.frequency_hz) / 2
    midpoint_frequency_hz = lower_endpoint.frequency_hz + half_width_hz
    return _d3_signed_zero_receipt(
        base;
        status="PASS",
        failure_reason=nothing,
        bracket_evidence...,
        midpoint_frequency_hz=midpoint_frequency_hz,
        half_width_hz=half_width_hz,
        checks=checks,
    )
end

end
