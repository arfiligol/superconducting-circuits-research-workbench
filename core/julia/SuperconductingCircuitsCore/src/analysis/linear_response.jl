# This file owns conservative linear frequency-domain response, matched-port
# loading, open poles, and response-at-known-root LC recovery. It does not own
# circuit compilation, fitting, optimization, lossy material models, or
# design-specific mode assignment. All formulas use exp(-i*omega*t).

function _linear_response_real_matrix(matrix, label)
    matrix isa AbstractMatrix || _validation_error("$(label) must be a matrix.")
    size(matrix, 1) == size(matrix, 2) > 0 || _validation_error(
        "$(label) must be a nonempty square matrix.",
    )
    all(value -> value isa Real && isfinite(value), matrix) || _validation_error(
        "$(label) must contain only finite real values.",
    )
    return Matrix{Float64}(matrix)
end

function _linear_response_matrices(capacitance, inverse_inductance)
    capacitance_matrix = _linear_response_real_matrix(capacitance, "Linear-response capacitance")
    stiffness_matrix = _linear_response_real_matrix(inverse_inductance, "Linear-response inverse inductance")
    size(capacitance_matrix) == size(stiffness_matrix) || _validation_error(
        "Linear-response capacitance and inverse-inductance matrices must have identical size.",
    )
    capacitance_matrix = _require_positive_definite(
        capacitance_matrix,
        "Linear-response capacitance matrix",
    )
    stiffness_matrix, _, _ = _require_positive_semidefinite(
        stiffness_matrix,
        "Linear-response inverse-inductance matrix",
    )
    return capacitance_matrix, stiffness_matrix
end

function _positive_angular_frequency(angular_frequency_rad_s)
    angular_frequency_rad_s isa Real || _validation_error(
        "Linear-response angular frequency must be real.",
    )
    frequency = Float64(angular_frequency_rad_s)
    isfinite(frequency) && frequency > 0 || _validation_error(
        "Linear-response angular frequency must be finite and positive.",
    )
    return frequency
end

function _linear_response_partition(dimension, terminal_indices)
    terminals = Int.(collect(terminal_indices))
    !isempty(terminals) || _validation_error("Linear-response terminal indices must be nonempty.")
    length(unique(terminals)) == length(terminals) || _validation_error(
        "Linear-response terminal indices must be unique.",
    )
    all(index -> 1 <= index <= dimension, terminals) || _validation_error(
        "Linear-response terminal index is out of bounds.",
    )
    terminal_set = Set(terminals)
    interior = [index for index in 1:dimension if !(index in terminal_set)]
    return terminals, interior
end

function _linear_response_solve(left, right, label)
    result = try
        left \ right
    catch exception
        _validation_error("$(label) solve failed: $(sprint(showerror, exception))")
    end
    all(value -> isfinite(real(value)) && isfinite(imag(value)), result) || _validation_error(
        "$(label) solve produced non-finite values.",
    )
    return result
end

function _linear_response_right_solve(numerator, denominator, label)
    # X = numerator / denominator, written as a transposed linear solve so no
    # explicit matrix inverse enters an S/Z conversion.
    transposed = _linear_response_solve(
        transpose(denominator),
        transpose(numerator),
        label,
    )
    return Matrix(transpose(transposed))
end

function _schur_dynamic_stiffness(dynamic_stiffness, terminals, interior)
    terminal_block = dynamic_stiffness[terminals, terminals]
    isempty(interior) && return Matrix(terminal_block)
    interior_block = dynamic_stiffness[interior, interior]
    interior_to_terminal = dynamic_stiffness[interior, terminals]
    eliminated = _linear_response_solve(
        interior_block,
        interior_to_terminal,
        "Linear-response interior Schur",
    )
    reduced = terminal_block - dynamic_stiffness[terminals, interior] * eliminated
    all(value -> isfinite(real(value)) && isfinite(imag(value)), reduced) || _validation_error(
        "Linear-response Schur complement produced non-finite values.",
    )
    return Matrix(reduced)
end

"""Schur-reduce `K - omega^2 C` onto ordered terminal indices.

With `exp(-i*omega*t)`, interior nodes carry zero injected current and obey
`Dii*Phi_i = -Dip*Phi_p`. The returned terminal operator is therefore
`Dpp - Dpi*(Dii\\Dip)`. Singular interior blocks fail rather than using a
pseudoinverse.
"""
function schur_dynamic_stiffness(
    capacitance,
    inverse_inductance,
    angular_frequency_rad_s,
    terminal_indices,
)
    capacitance_matrix, stiffness_matrix = _linear_response_matrices(
        capacitance,
        inverse_inductance,
    )
    angular_frequency = _positive_angular_frequency(angular_frequency_rad_s)
    dynamic_stiffness = stiffness_matrix - angular_frequency^2 * capacitance_matrix
    all(isfinite, dynamic_stiffness) || _validation_error(
        "Linear-response dynamic stiffness contains non-finite values.",
    )
    terminals, interior = _linear_response_partition(size(dynamic_stiffness, 1), terminal_indices)
    return (
        dynamic_stiffness = _schur_dynamic_stiffness(dynamic_stiffness, terminals, interior),
        terminal_indices = terminals,
        interior_indices = interior,
        angular_frequency_rad_s = angular_frequency,
    )
end

"""Return terminal `D`, `Y=D/(-i*omega)`, and `Z=Y\\I`.

The sign follows `V = dPhi/dt = -i*omega*Phi`; a parallel LC therefore has
`Y = i/(omega*L) - i*omega*C`. A singular terminal admittance fails loudly.
"""
function linear_terminal_response(
    capacitance,
    inverse_inductance,
    angular_frequency_rad_s,
    terminal_indices,
)
    reduced = schur_dynamic_stiffness(
        capacitance,
        inverse_inductance,
        angular_frequency_rad_s,
        terminal_indices,
    )
    admittance = reduced.dynamic_stiffness / (-im * reduced.angular_frequency_rad_s)
    terminal_count = length(reduced.terminal_indices)
    impedance = _linear_response_solve(
        admittance,
        Matrix{ComplexF64}(I, terminal_count, terminal_count),
        "Linear-response terminal impedance",
    )
    return merge(reduced, (admittance = admittance, impedance = impedance))
end

function _reference_impedance_vector(reference_impedance_ohm, port_count)
    raw_values = if reference_impedance_ohm isa Real
        fill(reference_impedance_ohm, port_count)
    elseif reference_impedance_ohm isa Diagonal
        collect(diag(reference_impedance_ohm))
    elseif reference_impedance_ohm isa AbstractVector
        collect(reference_impedance_ohm)
    else
        _validation_error("Reference impedance must be a positive scalar, vector, or Diagonal matrix.")
    end
    all(value -> value isa Real, raw_values) || _validation_error(
        "Reference impedances must be real.",
    )
    values = Float64.(raw_values)
    length(values) == port_count || _validation_error(
        "Reference impedance count must equal the matched-port count.",
    )
    all(value -> isfinite(value) && value > 0, values) || _validation_error(
        "Reference impedances must be finite and positive.",
    )
    return values
end

function _linear_response_selector(selector, node_count)
    selector isa AbstractMatrix || _validation_error("Matched-port selector B must be a matrix.")
    size(selector, 1) == node_count && size(selector, 2) > 0 || _validation_error(
        "Matched-port selector B must have one row per node and at least one port column.",
    )
    all(value -> value isa Real && isfinite(value), selector) || _validation_error(
        "Matched-port selector B must contain only finite real values.",
    )
    values = Matrix{Float64}(selector)
    rank(values) == size(values, 2) || _validation_error(
        "Matched-port selector B must have linearly independent port columns.",
    )
    return values
end

function _linear_response_complex_square(matrix, label)
    matrix isa AbstractMatrix && size(matrix, 1) == size(matrix, 2) > 0 || _validation_error(
        "$(label) must be a nonempty square matrix.",
    )
    all(value -> value isa Number && isfinite(real(value)) && isfinite(imag(value)), matrix) ||
        _validation_error("$(label) must contain only finite numeric values.")
    return Matrix{ComplexF64}(matrix)
end

"""Convert scattering to impedance with diagonal positive reference impedances."""
function scattering_to_impedance(scattering, reference_impedance_ohm)
    scattering_matrix = _linear_response_complex_square(scattering, "Scattering matrix")
    port_count = size(scattering_matrix, 1)
    z0 = _reference_impedance_vector(reference_impedance_ohm, port_count)
    identity_matrix = Matrix{ComplexF64}(I, port_count, port_count)
    ratio = _linear_response_right_solve(
        identity_matrix + scattering_matrix,
        identity_matrix - scattering_matrix,
        "Scattering-to-impedance",
    )
    square_root_z0 = Diagonal(sqrt.(z0))
    return Matrix{ComplexF64}(square_root_z0 * ratio * square_root_z0)
end

"""Convert impedance to scattering with diagonal positive reference impedances."""
function impedance_to_scattering(impedance, reference_impedance_ohm)
    impedance_matrix = _linear_response_complex_square(impedance, "Impedance matrix")
    port_count = size(impedance_matrix, 1)
    z0 = _reference_impedance_vector(reference_impedance_ohm, port_count)
    square_root_y0 = Diagonal(1 ./ sqrt.(z0))
    normalized = square_root_y0 * impedance_matrix * square_root_y0
    identity_matrix = Matrix{ComplexF64}(I, port_count, port_count)
    return Matrix{ComplexF64}(_linear_response_right_solve(
        normalized - identity_matrix,
        normalized + identity_matrix,
        "Impedance-to-scattering",
    ))
end

"""Evaluate the matched N-port response of one closed linear C/K model.

For selector `B` and `Y0=diag(1/z0)`, the port loading is `G=B*Y0*B'` and
`Dopen=K-omega^2*C-i*omega*G`. The returned scattering matrix implements the
declared `exp(-i*omega*t)` convention directly, without an HB/port simulation.
"""
function matched_port_response(
    capacitance,
    inverse_inductance,
    angular_frequency_rad_s,
    selector,
    reference_impedance_ohm,
)
    capacitance_matrix, stiffness_matrix = _linear_response_matrices(
        capacitance,
        inverse_inductance,
    )
    angular_frequency = _positive_angular_frequency(angular_frequency_rad_s)
    selector_matrix = _linear_response_selector(selector, size(capacitance_matrix, 1))
    port_count = size(selector_matrix, 2)
    z0 = _reference_impedance_vector(reference_impedance_ohm, port_count)
    square_root_y0 = Diagonal(1 ./ sqrt.(z0))
    conductance = selector_matrix * Diagonal(1 ./ z0) * transpose(selector_matrix)
    open_dynamic_stiffness = ComplexF64.(
        stiffness_matrix - angular_frequency^2 * capacitance_matrix,
    ) - im * angular_frequency * conductance
    driven_flux = _linear_response_solve(
        open_dynamic_stiffness,
        selector_matrix,
        "Matched-port open dynamic stiffness",
    )
    identity_matrix = Matrix{ComplexF64}(I, port_count, port_count)
    scattering = -identity_matrix - 2im * angular_frequency *
        square_root_y0 * transpose(selector_matrix) * driven_flux * square_root_y0
    all(value -> isfinite(real(value)) && isfinite(imag(value)), scattering) || _validation_error(
        "Matched-port scattering matrix contains non-finite values.",
    )
    return (
        scattering = Matrix{ComplexF64}(scattering),
        impedance = scattering_to_impedance(scattering, z0),
        conductance = Matrix{Float64}(conductance),
        open_dynamic_stiffness = open_dynamic_stiffness,
        selector = selector_matrix,
        reference_impedance_ohm = z0,
        angular_frequency_rad_s = angular_frequency,
    )
end

"""Return the physical positive-frequency poles of a matched open C/K model."""
function matched_open_poles(capacitance, inverse_inductance, selector, reference_impedance_ohm)
    capacitance_matrix, stiffness_matrix = _linear_response_matrices(
        capacitance,
        inverse_inductance,
    )
    selector_matrix = _linear_response_selector(selector, size(capacitance_matrix, 1))
    z0 = _reference_impedance_vector(reference_impedance_ohm, size(selector_matrix, 2))
    conductance = selector_matrix * Diagonal(1 ./ z0) * transpose(selector_matrix)
    node_count = size(capacitance_matrix, 1)
    state_matrix = [
        zeros(Float64, node_count, node_count) Matrix{Float64}(I, node_count, node_count)
        -_linear_response_solve(capacitance_matrix, stiffness_matrix, "Open-pole C\\K") -_linear_response_solve(capacitance_matrix, conductance, "Open-pole C\\G")
    ]
    raw_eigenvalues = eigvals(state_matrix)
    all(value -> isfinite(real(value)) && isfinite(imag(value)), raw_eigenvalues) ||
        _validation_error("Open-pole state matrix produced non-finite eigenvalues.")
    raw_frequencies = im .* raw_eigenvalues ./ (2π)
    scale_hz = max(maximum(abs, raw_frequencies), floatmin(Float64))
    decay_tolerance_hz = 256.0 * length(raw_frequencies) * eps(Float64) * scale_hz
    physical_indices = [
        index for index in eachindex(raw_frequencies)
        if real(raw_frequencies[index]) > 0 && imag(raw_frequencies[index]) <= decay_tolerance_hz
    ]
    isempty(physical_indices) && _validation_error(
        "Open-pole state matrix has no passive positive-frequency branch.",
    )
    sort!(physical_indices; by=index -> (real(raw_frequencies[index]), imag(raw_frequencies[index])))
    physical_frequencies = ComplexF64.(raw_frequencies[physical_indices])
    linewidths = max.(-2 .* imag.(physical_frequencies), 0.0)
    return (
        frequencies_hz = physical_frequencies,
        linewidths_hz = Float64.(linewidths),
        physical_eigenvalues = ComplexF64.(raw_eigenvalues[physical_indices]),
        raw_eigenvalues = ComplexF64.(raw_eigenvalues),
        state_matrix = state_matrix,
        conductance = Matrix{Float64}(conductance),
        hashes = (
            capacitance_sha256 = _linear_matrix_sha256("open-pole-capacitance-f", capacitance_matrix),
            inverse_inductance_sha256 = _linear_matrix_sha256("open-pole-inverse-inductance-h^-1", stiffness_matrix),
            conductance_sha256 = _linear_matrix_sha256("open-pole-conductance-s", conductance),
            state_matrix_sha256 = _linear_matrix_sha256("open-pole-state-matrix", state_matrix),
        ),
        provenance = (
            contract_id = "matched-open-linear-poles-v1",
            time_convention = "exp(-i*omega*t)",
            ordinary_frequency_definition = "f=i*lambda/(2*pi)",
        ),
    )
end

function _linear_response_scalar(function_value, label)
    function_value isa Number || _validation_error("$(label) must return one numeric scalar.")
    value = ComplexF64(function_value)
    isfinite(real(value)) && isfinite(imag(value)) || _validation_error(
        "$(label) returned a non-finite scalar.",
    )
    return value
end

function _known_root_samples(response, angular_frequency, derivative_step, label)
    step = Float64(derivative_step)
    isfinite(step) && 0 < step < angular_frequency || _validation_error(
        "$(label) derivative step must be finite, positive, and smaller than the root frequency.",
    )
    lower = _linear_response_scalar(response(angular_frequency - step), label)
    center = _linear_response_scalar(response(angular_frequency), label)
    upper = _linear_response_scalar(response(angular_frequency + step), label)
    derivative = (upper - lower) / (2 * step)
    return lower, center, upper, derivative
end

function _require_known_root(center, lower, upper, derivative, step, tolerance, label)
    relative_tolerance = Float64(tolerance)
    isfinite(relative_tolerance) && relative_tolerance >= 0 || _validation_error(
        "$(label) root residual tolerance must be finite and nonnegative.",
    )
    scale = max(abs(lower), abs(upper), abs(derivative) * step, floatmin(Float64))
    abs(center) <= relative_tolerance * scale || _validation_error(
        "$(label) declared frequency is not a response root within tolerance.",
    )
    return nothing
end

"""Recover a parallel LC from one scalar admittance at a known root."""
function match_parallel_lc(
    admittance,
    angular_frequency_rad_s;
    derivative_step_rad_s,
    root_relative_tolerance = 1.0e-8,
    imaginary_derivative_relative_tolerance = 1.0e-8,
)
    angular_frequency = _positive_angular_frequency(angular_frequency_rad_s)
    lower, center, upper, derivative = _known_root_samples(
        admittance,
        angular_frequency,
        derivative_step_rad_s,
        "Parallel-LC admittance",
    )
    _require_known_root(
        center,
        lower,
        upper,
        derivative,
        Float64(derivative_step_rad_s),
        root_relative_tolerance,
        "Parallel-LC admittance",
    )
    derivative_tolerance = Float64(imaginary_derivative_relative_tolerance)
    isfinite(derivative_tolerance) && derivative_tolerance >= 0 || _validation_error(
        "Parallel-LC derivative residual tolerance must be finite and nonnegative.",
    )
    abs(real(derivative)) <= derivative_tolerance * max(abs(imag(derivative)), floatmin(Float64)) ||
        _validation_error("Parallel-LC admittance derivative must be imaginary within tolerance.")
    capacitance = -imag(derivative) / 2
    isfinite(capacitance) && capacitance > 0 || _validation_error(
        "Parallel-LC response match produced a non-positive capacitance.",
    )
    inductance = 1 / (angular_frequency^2 * capacitance)
    return (
        capacitance_f = capacitance,
        inductance_h = inductance,
        angular_frequency_rad_s = angular_frequency,
        frequency_hz = angular_frequency / (2π),
        root_admittance_s = center,
        admittance_derivative_s_per_rad_s = derivative,
        derivative_step_rad_s = Float64(derivative_step_rad_s),
    )
end

function match_parallel_lc(
    capacitance,
    inverse_inductance,
    terminal_index::Integer,
    angular_frequency_rad_s;
    kwargs...,
)
    capacitance_matrix, stiffness_matrix = _linear_response_matrices(
        capacitance,
        inverse_inductance,
    )
    terminals, interior = _linear_response_partition(size(capacitance_matrix, 1), [terminal_index])
    admittance = function (angular_frequency)
        dynamic_stiffness = stiffness_matrix - angular_frequency^2 * capacitance_matrix
        reduced = _schur_dynamic_stiffness(dynamic_stiffness, terminals, interior)
        return reduced[1, 1] / (-im * angular_frequency)
    end
    return match_parallel_lc(admittance, angular_frequency_rad_s; kwargs...)
end

"""Recover a parallel bridge LC from `Z21`, `Yr`, and `Yp` at its notch.

For a bridge admittance `Yn` between two shunt admittances, `Z21=Yn/det(Y)`.
At `Yn(omega_n)=0`, `dZ21/domega=(dYn/domega)/(Yr*Yp)` and a parallel LC has
`dYn/domega=-2i*Cn`, yielding the implemented response-match identity.
"""
function match_bridge_lc(
    transfer_impedance,
    readout_admittance,
    filter_admittance,
    angular_frequency_rad_s;
    derivative_step_rad_s,
    root_relative_tolerance = 1.0e-8,
    imaginary_capacitance_relative_tolerance = 1.0e-8,
)
    angular_frequency = _positive_angular_frequency(angular_frequency_rad_s)
    lower, center, upper, derivative = _known_root_samples(
        transfer_impedance,
        angular_frequency,
        derivative_step_rad_s,
        "Bridge transfer impedance",
    )
    _require_known_root(
        center,
        lower,
        upper,
        derivative,
        Float64(derivative_step_rad_s),
        root_relative_tolerance,
        "Bridge transfer impedance",
    )
    yr = _linear_response_scalar(readout_admittance(angular_frequency), "Readout admittance")
    yp = _linear_response_scalar(filter_admittance(angular_frequency), "Filter admittance")
    abs(yr) > 0 && abs(yp) > 0 || _validation_error(
        "Bridge response match requires nonzero terminal admittances at the notch.",
    )
    complex_capacitance = derivative * yr * yp / (-2im)
    residual_tolerance = Float64(imaginary_capacitance_relative_tolerance)
    isfinite(residual_tolerance) && residual_tolerance >= 0 || _validation_error(
        "Bridge capacitance residual tolerance must be finite and nonnegative.",
    )
    abs(imag(complex_capacitance)) <= residual_tolerance *
        max(abs(real(complex_capacitance)), floatmin(Float64)) || _validation_error(
            "Bridge response match produced a capacitance with excessive imaginary residual.",
        )
    capacitance = real(complex_capacitance)
    isfinite(capacitance) && capacitance > 0 || _validation_error(
        "Bridge response match produced a non-positive capacitance.",
    )
    inductance = 1 / (angular_frequency^2 * capacitance)
    return (
        capacitance_f = capacitance,
        inductance_h = inductance,
        angular_frequency_rad_s = angular_frequency,
        frequency_hz = angular_frequency / (2π),
        root_transfer_impedance_ohm = center,
        transfer_impedance_derivative_ohm_per_rad_s = derivative,
        readout_admittance_s = yr,
        filter_admittance_s = yp,
        capacitance_imaginary_residual_f = imag(complex_capacitance),
        derivative_step_rad_s = Float64(derivative_step_rad_s),
    )
end

"""Find one real root in a sign-changing bracket by dependency-free bisection."""
function bracketed_bisection(
    response,
    bracket;
    absolute_tolerance = 0.0,
    relative_tolerance = 1.0e-12,
    max_iterations = 256,
)
    endpoints = Float64.(collect(bracket))
    length(endpoints) == 2 && all(isfinite, endpoints) && endpoints[1] < endpoints[2] ||
        _validation_error("Bisection bracket must contain two finite increasing endpoints.")
    absolute = Float64(absolute_tolerance)
    relative = Float64(relative_tolerance)
    iterations = Int(max_iterations)
    isfinite(absolute) && absolute >= 0 && isfinite(relative) && relative > 0 ||
        _validation_error("Bisection tolerances must be finite with absolute >= 0 and relative > 0.")
    iterations > 0 || _validation_error("Bisection max_iterations must be positive.")
    lower, upper = endpoints
    lower_value = response(lower)
    upper_value = response(upper)
    lower_value isa Real && isfinite(lower_value) && upper_value isa Real && isfinite(upper_value) ||
        _validation_error("Bisection response must return finite real values.")
    iszero(lower_value) && return lower
    iszero(upper_value) && return upper
    signbit(lower_value) != signbit(upper_value) || _validation_error(
        "Bisection bracket endpoints must have opposite signs.",
    )
    for _ in 1:iterations
        midpoint = lower + (upper - lower) / 2
        midpoint_value = response(midpoint)
        midpoint_value isa Real && isfinite(midpoint_value) || _validation_error(
            "Bisection response returned a non-finite or non-real midpoint value.",
        )
        iszero(midpoint_value) && return midpoint
        tolerance = max(absolute, relative * max(abs(midpoint), floatmin(Float64)))
        (upper - lower) / 2 <= tolerance && return midpoint
        if signbit(midpoint_value) == signbit(lower_value)
            lower = midpoint
            lower_value = midpoint_value
        else
            upper = midpoint
            upper_value = midpoint_value
        end
    end
    _validation_error("Bisection did not converge within max_iterations.")
end
