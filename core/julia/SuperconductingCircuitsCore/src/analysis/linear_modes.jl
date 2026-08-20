# This file owns conservative closed-circuit matrix extraction, free-charge
# coordinate reduction, generalized normal modes, and projection of a physical
# quadratic Hamiltonian into a coupling-off modal basis. It does not own lossy
# ports, harmonic-balance response extraction, nonlinear operating points, or
# design-specific mode ownership.

struct LinearNodalModel
    node_names::Vector{String}
    capacitance::Matrix{Float64}
    inverse_inductance::Matrix{Float64}
    source_sha256::String
    node_order_sha256::String
    capacitance_sha256::String
    inverse_inductance_sha256::String
    provenance
end

struct LinearNodalCKGModel
    node_names::Vector{String}
    capacitance::Matrix{Float64}
    inverse_inductance::Matrix{Float64}
    conductance::Matrix{Float64}
    source_sha256::String
    node_order_sha256::String
    capacitance_sha256::String
    inverse_inductance_sha256::String
    conductance_sha256::String
    provenance
end

struct ReducedLinearModel
    source::LinearNodalModel
    retained_basis::Matrix{Float64}
    free_charge_basis::Matrix{Float64}
    node_flux_transform::Matrix{Float64}
    capacitance::Matrix{Float64}
    inverse_inductance::Matrix{Float64}
    free_charge_capacitance::Matrix{Float64}
    stiffness_null_tolerance::Float64
    free_charge_constraint_residual::Float64
    capacitance_sha256::String
    inverse_inductance_sha256::String
end

struct GeneralizedModeSolution
    model::ReducedLinearModel
    angular_frequencies_rad_s::Vector{Float64}
    frequencies_hz::Vector{Float64}
    vectors::Matrix{Float64}
    node_flux_vectors::Matrix{Float64}
    residuals::Vector{Float64}
    c_orthogonality_error::Float64
    sign_anchor_indices::Vector{Int}
end

struct SelectedModeProjection
    selected_mode_indices::Vector{Int}
    loaded_bare_angular_frequencies_rad_s::Vector{Float64}
    kinetic_matrix::Matrix{Float64}
    potential_matrix_rad_s2::Matrix{Float64}
    x_matrix_rad_s::Matrix{Float64}
    y_matrix_rad_s::Matrix{Float64}
    number_conserving_matrix_rad_s::Matrix{Float64}
    pairing_matrix_rad_s::Matrix{Float64}
    coupling_matrix_hz::Matrix{Float64}
    diagonal_shifts_hz::Vector{Float64}
    projected_bdg_frequencies_hz::Vector{Float64}
    projected_rwa_frequencies_hz::Vector{Float64}
end

function _linear_sha256(parts)
    buffer = IOBuffer()
    for (index, part) in enumerate(parts)
        index > 1 && write(buffer, UInt8('|'))
        write(buffer, String(part))
    end
    return bytes2hex(SHA.sha256(take!(buffer)))
end

function _linear_string_vector_sha256(label, values)
    parts = String["linear-string-vector-v1", String(label), "count=$(length(values))"]
    append!(parts, ["$(ncodeunits(String(value))):$(String(value))" for value in values])
    return _linear_sha256(parts)
end

function _linear_matrix_sha256(label, matrix)
    values = Matrix{Float64}(matrix)
    header = String[
        "linear-float64-matrix-v1",
        String(label),
        "rows=$(size(values, 1))",
        "cols=$(size(values, 2))",
    ]
    buffer = IOBuffer()
    for (index, part) in enumerate(header)
        index > 1 && write(buffer, UInt8('|'))
        write(buffer, part)
    end
    for row in axes(values, 1), column in axes(values, 2)
        value = iszero(values[row, column]) ? 0.0 : values[row, column]
        write(buffer, UInt8('|'))
        write(buffer, bitstring(value))
    end
    return bytes2hex(SHA.sha256(take!(buffer)))
end

function _compiled_linear_source_sha256(compiled, parsed, resolved_values)
    length(parsed.componentnames) == length(resolved_values) == length(compiled.netlist) ||
        _validation_error("Closed linear source provenance rows and resolved values disagree in length.")
    rows_by_name = Dict{String,Any}()
    for row in compiled.netlist
        row isa Tuple && length(row) == 4 || _validation_error(
            "Closed linear extraction requires four-field JosephsonCircuits netlist rows.",
        )
        name = String(row[1])
        haskey(rows_by_name, name) && _validation_error(
            "Closed linear extraction requires unique component names for source provenance.",
        )
        rows_by_name[name] = row
    end
    parsed_names = String.(parsed.componentnames)
    length(unique(parsed_names)) == length(parsed_names) || _validation_error(
        "JosephsonCircuits parsed component names must be unique for source provenance.",
    )
    resolved_by_name = Dict(
        name => Float64(resolved_values[index])
        for (index, name) in enumerate(parsed_names)
    )
    canonical_names = sort(parsed_names)
    parts = String["compiled-closed-linear-source-v2", "rows=$(length(canonical_names))"]
    for (index, name) in enumerate(canonical_names)
        haskey(rows_by_name, name) || _validation_error(
            "Parsed component $(name) is missing from the compiled source netlist.",
        )
        row = rows_by_name[name]
        append!(parts, [
            "row=$(index)",
            "name=$(name)",
            "node_a=$(row[2])",
            "node_b=$(row[3])",
            "value=$(bitstring(resolved_by_name[name]))",
        ])
    end
    return _linear_sha256(parts)
end

function _matrix_relative_tolerance(matrix; multiplier=64.0)
    values = Matrix{Float64}(matrix)
    scale = opnorm(values, Inf)
    scale > 0 || return 0.0
    return Float64(multiplier) * max(size(values)...) * eps(Float64) * scale
end

function _spectral_tolerance(values; multiplier=64.0)
    spectrum = Float64.(collect(values))
    scale = isempty(spectrum) ? 0.0 : maximum(abs, spectrum)
    scale > 0 || return 0.0
    return Float64(multiplier) * max(length(spectrum), 1) * eps(Float64) * scale
end

function _require_symmetric(matrix, label)
    values = Matrix{Float64}(matrix)
    tolerance = _matrix_relative_tolerance(values)
    norm(values - transpose(values), Inf) <= tolerance || _validation_error(
        "$(label) must be symmetric within its Float64 numerical tolerance.",
    )
    return Matrix{Float64}(Symmetric((values + transpose(values)) / 2))
end

function _require_positive_definite(matrix, label)
    values = _require_symmetric(matrix, label)
    spectrum = eigvals(Symmetric(values))
    tolerance = _spectral_tolerance(spectrum)
    minimum(spectrum) > tolerance || _validation_error(
        "$(label) must be positive definite on the declared coordinate space.",
    )
    return values
end

function _require_positive_semidefinite(matrix, label)
    values = _require_symmetric(matrix, label)
    spectrum = eigvals(Symmetric(values))
    tolerance = _spectral_tolerance(spectrum)
    minimum(spectrum) >= -tolerance || _validation_error(
        "$(label) must be passive positive semidefinite.",
    )
    return values, spectrum, tolerance
end

"""Extract one finite passive nodal C/K/G model from a compiled closed plan.

The JosephsonCircuits parser owns netlist-to-matrix lowering. This boundary
adds Workbench node ordering, provenance, semantic hashes, and strict rejection
of ports, sources, nonlinear junction rows, and unresolved values.
"""
function extract_linear_nodal_ckg_model(compiled::JosephsonCompiledCircuit)
    isempty(compiled.port_map) || _validation_error(
        "Closed linear extraction does not accept external ports.",
    )
    isempty(compiled.netlist) && _validation_error(
        "Closed linear extraction requires a nonempty compiled netlist.",
    )

    parsed = try
        JosephsonCircuits.parsesortcircuit(compiled.netlist; sorting=:name)
    catch exception
        _validation_error(
            "JosephsonCircuits could not parse the closed linear netlist: $(sprint(showerror, exception))",
        )
    end
    forbidden = Set([:P, :I, :Lj, :NL])
    forbidden_rows = [
        parsed.componentnames[index]
        for index in eachindex(parsed.componenttypes)
        if parsed.componenttypes[index] in forbidden
    ]
    isempty(forbidden_rows) || _validation_error(
        "Direct linear extraction rejects ports, sources, and nonlinear rows: $(join(forbidden_rows, ", ")).",
    )
    all(type -> type in (:C, :L, :K, :R), parsed.componenttypes) || _validation_error(
        "Direct linear extraction supports only C, L, mutual-K, and R rows.",
    )

    graph = JosephsonCircuits.calccircuitgraph(parsed)
    matrices = try
        JosephsonCircuits.numericmatrices(
            parsed,
            graph,
            compiled.component_values;
            Nmodes=1,
        )
    catch exception
        _validation_error(
            "JosephsonCircuits could not assemble closed linear matrices: $(sprint(showerror, exception))",
        )
    end
    resolved_values = collect(matrices.vvn)
    all(value -> value isa Real && isfinite(value), resolved_values) || _validation_error(
        "Closed linear extraction requires finite real frequency-independent component values.",
    )
    isempty(matrices.portindices) && isempty(matrices.portnumbers) || _validation_error(
        "Closed linear extraction found undeclared port rows.",
    )
    isempty(matrices.Ljb.nzval) || _validation_error(
        "Closed linear extraction v1 does not linearize Josephson junction rows; use ordinary L rows or provide a reviewed operating-point Hessian.",
    )

    parsed.nodenames[1] == "0" || _validation_error(
        "JosephsonCircuits closed linear node ordering must place ground first.",
    )
    node_names = String.(parsed.nodenames[2:end])
    capacitance = Matrix{Float64}(matrices.Cnm)
    inverse_inductance = Matrix{Float64}(matrices.invLnm)
    conductance = zeros(Float64, size(capacitance))
    for column in axes(conductance, 2)
        for index in matrices.Gnm.colptr[column]:(matrices.Gnm.colptr[column + 1] - 1)
            conductance[matrices.Gnm.rowval[index], column] = Float64(matrices.Gnm.nzval[index])
        end
    end
    size(capacitance) == size(inverse_inductance) == size(conductance) ==
        (length(node_names), length(node_names)) ||
        _validation_error("Direct linear C/K/G matrices and ordered node names disagree in size.")
    all(isfinite, capacitance) && all(isfinite, inverse_inductance) && all(isfinite, conductance) || _validation_error(
        "Direct linear C/K/G matrices must contain only finite values.",
    )
    capacitance = _require_positive_definite(capacitance, "Closed linear capacitance matrix")
    inverse_inductance, _, _ = _require_positive_semidefinite(
        inverse_inductance,
        "Closed linear inverse-inductance matrix",
    )
    conductance, _, _ = _require_positive_semidefinite(
        conductance,
        "Direct linear conductance matrix",
    )

    plan_id = String(get(compiled.provenance, :plan_id, "unknown"))
    topology_digest = String(get(compiled.provenance, :topology_key, "unknown"))
    return LinearNodalCKGModel(
        node_names,
        capacitance,
        inverse_inductance,
        conductance,
        _compiled_linear_source_sha256(compiled, parsed, resolved_values),
        _linear_string_vector_sha256("ordered-nodes", node_names),
        _linear_matrix_sha256("capacitance-f", capacitance),
        _linear_matrix_sha256("inverse-inductance-h^-1", inverse_inductance),
        _linear_matrix_sha256("conductance-s", conductance),
        (
            contract_id="direct-linear-nodal-ckg-model-v1",
            plan_id=plan_id,
            topology_key=topology_digest,
            compiler=get(compiled.provenance, :compiler, :unknown),
            node_count=length(node_names),
            netlist_row_count=length(compiled.netlist),
        ),
    )
end

"""Extract the conservative zero-G view used by existing closed-mode solvers."""
function extract_linear_nodal_model(compiled::JosephsonCompiledCircuit)
    model = extract_linear_nodal_ckg_model(compiled)
    all(iszero, model.conductance) || _validation_error(
        "Closed linear extraction requires an exactly lossless zero-conductance model.",
    )
    return LinearNodalModel(
        model.node_names,
        model.capacitance,
        model.inverse_inductance,
        model.source_sha256,
        model.node_order_sha256,
        model.capacitance_sha256,
        model.inverse_inductance_sha256,
        merge(model.provenance, (contract_id="closed-linear-nodal-model-v1",)),
    )
end

function _stiffness_coordinate_bases(inverse_inductance)
    spectrum = eigen(Symmetric(Matrix{Float64}(inverse_inductance)))
    tolerance = _spectral_tolerance(spectrum.values)
    minimum(spectrum.values) >= -tolerance || _validation_error(
        "Closed linear inverse-inductance matrix has an active negative eigendirection.",
    )
    null_indices = findall(value -> abs(value) <= tolerance, spectrum.values)
    positive_indices = findall(value -> value > tolerance, spectrum.values)
    isempty(positive_indices) && _validation_error(
        "Closed linear model has no positive-stiffness dynamical coordinates.",
    )
    free_charge_basis = Matrix{Float64}(spectrum.vectors[:, null_indices])
    retained_basis = isempty(null_indices) ?
        Matrix{Float64}(I, size(inverse_inductance, 1), size(inverse_inductance, 1)) :
        Matrix{Float64}(spectrum.vectors[:, positive_indices])
    return retained_basis, free_charge_basis, tolerance
end

function _reduce_with_bases(model, retained_basis, free_charge_basis, null_tolerance)
    capacitance = model.capacitance
    inverse_inductance = model.inverse_inductance
    if isempty(free_charge_basis)
        free_charge_capacitance = zeros(Float64, 0, 0)
        transform = retained_basis
    else
        free_charge_capacitance = transpose(free_charge_basis) * capacitance * free_charge_basis
        free_charge_capacitance = _require_positive_definite(
            free_charge_capacitance,
            "Free-charge/common-coordinate capacitance block",
        )
        cross = transpose(free_charge_basis) * capacitance * retained_basis
        transform = retained_basis - free_charge_basis * (free_charge_capacitance \ cross)
    end
    reduced_capacitance = transpose(transform) * capacitance * transform
    # K annihilates the free-charge basis, so the retained operator is owned by
    # the shared U frame and must not acquire topology-dependent roundoff from
    # the capacitance-dependent node-flux reconstruction.
    reduced_inverse_inductance =
        transpose(retained_basis) * inverse_inductance * retained_basis
    reduced_capacitance = _require_positive_definite(
        reduced_capacitance,
        "Schur-reduced capacitance matrix",
    )
    reduced_inverse_inductance = _require_positive_definite(
        reduced_inverse_inductance,
        "Schur-reduced inverse-inductance matrix",
    )
    constraint_residual = isempty(free_charge_basis) ? 0.0 : norm(
        transpose(free_charge_basis) * capacitance * transform,
        Inf,
    ) / max(opnorm(capacitance, Inf), floatmin(Float64))
    return ReducedLinearModel(
        model,
        retained_basis,
        free_charge_basis,
        transform,
        reduced_capacitance,
        reduced_inverse_inductance,
        free_charge_capacitance,
        null_tolerance,
        Float64(constraint_residual),
        _linear_matrix_sha256("schur-reduced-capacitance-f", reduced_capacitance),
        _linear_matrix_sha256("schur-reduced-inverse-inductance-h^-1", reduced_inverse_inductance),
    )
end

"""Remove passive K-null coordinates in the zero conserved-charge sector."""
function reduce_free_charge_coordinates(model::LinearNodalModel)
    retained_basis, free_charge_basis, tolerance = _stiffness_coordinate_bases(
        model.inverse_inductance,
    )
    return _reduce_with_bases(model, retained_basis, free_charge_basis, tolerance)
end

function _require_shared_stiffness_nullspace(
    coupling_off::LinearNodalModel,
    physical_on::LinearNodalModel,
    retained_basis,
    free_charge_basis,
)
    on_retained_basis, on_free_charge_basis, on_tolerance = _stiffness_coordinate_bases(
        physical_on.inverse_inductance,
    )
    size(free_charge_basis, 2) == size(on_free_charge_basis, 2) || _validation_error(
        "Coupling-off and physical-on stiffness operators must have the same number of free-charge coordinates.",
    )
    size(retained_basis, 2) == size(on_retained_basis, 2) || _validation_error(
        "Coupling-off and physical-on stiffness operators must have the same number of positive-stiffness coordinates.",
    )

    if !isempty(free_charge_basis)
        annihilation_residual = norm(
            physical_on.inverse_inductance * free_charge_basis,
            Inf,
        )
        annihilation_tolerance = max(
            on_tolerance,
            _matrix_relative_tolerance(
                physical_on.inverse_inductance;
                multiplier=256.0,
            ),
        )
        annihilation_residual <= annihilation_tolerance || _validation_error(
            "Physical-on stiffness must annihilate the coupling-off free-charge basis in the shared coordinate frame.",
        )

        off_null_projector = free_charge_basis * transpose(free_charge_basis)
        on_null_projector = on_free_charge_basis * transpose(on_free_charge_basis)
        projector_tolerance = 1024.0 * max(size(off_null_projector)...) * eps(Float64)
        norm(off_null_projector - on_null_projector, Inf) <= projector_tolerance ||
            _validation_error(
                "Coupling-off and physical-on stiffness operators must have the same free-charge nullspace.",
            )
    end
    return nothing
end

function _require_shared_reduction_frame(
    coupling_off::ReducedLinearModel,
    physical_on::ReducedLinearModel,
)
    coupling_off.source.node_names == physical_on.source.node_names || _validation_error(
        "Selected modal projection requires identical off/on ordered nodes.",
    )
    coupling_off.retained_basis == physical_on.retained_basis || _validation_error(
        "Selected modal projection requires one shared off/on retained-coordinate basis.",
    )
    coupling_off.free_charge_basis == physical_on.free_charge_basis || _validation_error(
        "Selected modal projection requires one shared off/on free-charge basis.",
    )
    coupling_off.stiffness_null_tolerance == physical_on.stiffness_null_tolerance ||
        _validation_error(
            "Selected modal projection requires one shared off/on stiffness-null frame tolerance.",
        )
    return nothing
end

"""Reduce coupling-off and physical-on models in one shared K-null frame.

The ordered nodes must match. The physical stiffness may differ from the
coupling-off stiffness, but it must have exactly the same numerical nullspace.
The coupling-off eigenspaces then own the retained and free-charge coordinate
frame used to reduce both capacitance/stiffness pairs.
"""
function reduce_linear_model_pair(
    coupling_off::LinearNodalModel,
    physical_on::LinearNodalModel,
)
    coupling_off.node_names == physical_on.node_names || _validation_error(
        "Coupling-off and physical-on closed models must have identical ordered nodes.",
    )
    retained_basis, free_charge_basis, tolerance = _stiffness_coordinate_bases(
        coupling_off.inverse_inductance,
    )
    _require_shared_stiffness_nullspace(
        coupling_off,
        physical_on,
        retained_basis,
        free_charge_basis,
    )
    return (
        coupling_off=_reduce_with_bases(
            coupling_off,
            retained_basis,
            free_charge_basis,
            tolerance,
        ),
        physical_on=_reduce_with_bases(
            physical_on,
            retained_basis,
            free_charge_basis,
            tolerance,
        ),
    )
end

"""Solve and C-normalize all positive modes of one reduced conservative model."""
function solve_generalized_modes(model::ReducedLinearModel)
    result = eigen(
        Symmetric(model.inverse_inductance),
        Symmetric(model.capacitance),
    )
    tolerance = _spectral_tolerance(result.values)
    minimum(result.values) > tolerance || _validation_error(
        "Reduced generalized eigenproblem must contain only positive finite modes.",
    )
    vectors = Matrix{Float64}(result.vectors)
    node_vectors = model.node_flux_transform * vectors
    anchors = Int[]
    residuals = Float64[]
    for index in axes(vectors, 2)
        norm_c = sqrt(dot(vectors[:, index], model.capacitance * vectors[:, index]))
        isfinite(norm_c) && norm_c > 0 || _validation_error(
            "Generalized eigenvector has no finite positive C norm.",
        )
        vectors[:, index] ./= norm_c
        node_vectors[:, index] = model.node_flux_transform * vectors[:, index]
        anchor = argmax(abs.(node_vectors[:, index]))
        if node_vectors[anchor, index] < 0
            vectors[:, index] .*= -1
            node_vectors[:, index] .*= -1
        end
        push!(anchors, anchor)
        left = model.inverse_inductance * vectors[:, index]
        right = result.values[index] * (model.capacitance * vectors[:, index])
        denominator = norm(left) + norm(right)
        push!(residuals, norm(left - right) / max(denominator, floatmin(Float64)))
    end
    orthogonality_error = norm(
        transpose(vectors) * model.capacitance * vectors - I,
        Inf,
    )
    angular_frequencies = sqrt.(Float64.(result.values))
    return GeneralizedModeSolution(
        model,
        angular_frequencies,
        angular_frequencies ./ (2π),
        vectors,
        node_vectors,
        residuals,
        Float64(orthogonality_error),
        anchors,
    )
end

"""Project a physical-on quadratic Hamiltonian into selected off modes."""
function project_selected_modes(
    coupling_off_modes::GeneralizedModeSolution,
    physical_on::ReducedLinearModel,
    selected_mode_indices,
)
    indices = Int.(collect(selected_mode_indices))
    !isempty(indices) && length(unique(indices)) == length(indices) || _validation_error(
        "Selected modal projection indices must be nonempty and unique.",
    )
    all(index -> 1 <= index <= length(coupling_off_modes.frequencies_hz), indices) ||
        _validation_error("Selected modal projection index is out of bounds.")
    off_model = coupling_off_modes.model
    _require_shared_reduction_frame(off_model, physical_on)

    vectors = coupling_off_modes.vectors[:, indices]
    angular_frequencies = coupling_off_modes.angular_frequencies_rad_s[indices]
    rhs = off_model.capacitance * vectors
    solved = physical_on.capacitance \ rhs
    kinetic = transpose(vectors) * off_model.capacitance * solved
    potential = transpose(vectors) * physical_on.inverse_inductance * vectors
    kinetic = _require_positive_definite(kinetic, "Projected kinetic Hamiltonian block")
    potential = _require_positive_definite(potential, "Projected potential Hamiltonian block")

    sqrt_frequency = Diagonal(sqrt.(angular_frequencies))
    inverse_sqrt_frequency = Diagonal(1 ./ sqrt.(angular_frequencies))
    x_matrix = Matrix{Float64}(sqrt_frequency * kinetic * sqrt_frequency)
    y_matrix = Matrix{Float64}(inverse_sqrt_frequency * potential * inverse_sqrt_frequency)
    number_conserving = _require_symmetric(
        (x_matrix + y_matrix) / 2,
        "Projected number-conserving Hamiltonian block",
    )
    pairing = _require_symmetric(
        (y_matrix - x_matrix) / 2,
        "Projected pairing Hamiltonian block",
    )

    kinetic_cholesky = cholesky(Symmetric(kinetic))
    bdg_squared = transpose(kinetic_cholesky.L) * potential * kinetic_cholesky.L
    bdg_eigenvalues = eigvals(Symmetric(bdg_squared))
    minimum(bdg_eigenvalues) > _spectral_tolerance(bdg_eigenvalues) || _validation_error(
        "Projected non-RWA Hamiltonian has a non-positive mode.",
    )
    projected_bdg_hz = sort(sqrt.(bdg_eigenvalues) ./ (2π))
    projected_rwa_hz = sort(eigvals(Symmetric(number_conserving)) ./ (2π))
    coupling_hz = copy(number_conserving) ./ (2π)
    for index in axes(coupling_hz, 1)
        coupling_hz[index, index] = 0.0
    end
    diagonal_shifts_hz = diag(number_conserving) ./ (2π) .-
        angular_frequencies ./ (2π)
    return SelectedModeProjection(
        indices,
        angular_frequencies,
        kinetic,
        potential,
        x_matrix,
        y_matrix,
        number_conserving,
        pairing,
        coupling_hz,
        Float64.(diagonal_shifts_hz),
        Float64.(projected_bdg_hz),
        Float64.(projected_rwa_hz),
    )
end

"""Compare exact physical frequencies with projected BdG and RWA closures."""
function linear_projection_closure(projection::SelectedModeProjection, exact_frequencies_hz)
    exact = sort(Float64.(collect(exact_frequencies_hz)))
    length(exact) == length(projection.projected_bdg_frequencies_hz) || _validation_error(
        "Projection closure requires one exact frequency per selected mode.",
    )
    all(value -> isfinite(value) && value > 0, exact) || _validation_error(
        "Projection closure exact frequencies must be finite and positive.",
    )
    bdg_residuals = projection.projected_bdg_frequencies_hz .- exact
    rwa_residuals = projection.projected_rwa_frequencies_hz .- exact
    rwa_minus_bdg = projection.projected_rwa_frequencies_hz .-
        projection.projected_bdg_frequencies_hz
    return (
        exact_frequencies_hz=exact,
        projected_bdg_residuals_hz=bdg_residuals,
        projected_rwa_residuals_hz=rwa_residuals,
        rwa_minus_bdg_hz=rwa_minus_bdg,
        max_abs_bdg_residual_hz=maximum(abs, bdg_residuals),
        max_abs_rwa_residual_hz=maximum(abs, rwa_residuals),
        max_abs_rwa_minus_bdg_hz=maximum(abs, rwa_minus_bdg),
    )
end
