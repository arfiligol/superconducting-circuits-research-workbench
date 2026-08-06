# Task-local W7/S6 spatial-convergence experiment for the local distributed
# intrinsic pair. It does not build the Equivalent arm or any Full-QRP model.

using Dates
using LinearAlgebra
using Serialization
using SHA
using SparseArrays
using SuperconductingCircuitsCore

const JSON3 = SuperconductingCircuitsCore.JSON3
const SOURCE_DIR = @__DIR__
const REPOSITORY_ROOT = normpath(joinpath(SOURCE_DIR, "..", "..", ".."))
const SOURCE_PATH = abspath(@__FILE__)
const Q2D_PATH = joinpath(SOURCE_DIR, "d3_continuous_ground_q2d_maxwell_lc.v4.json")
const REQUIRED_WORKBENCH_ANCESTOR = "4ac63965398929b065e737b622a76478d51d3647"
const REQUIRED_ORPEN_PRODUCER_REVISION = "80576910d596dbf4720335188e66b6a520cc2e36"
const REQUIRED_Q2D_SHA256 = "301d3501a30614b994cf3f28d46eb75b545620a164bbb346fa557120d643fe6c"
const EVIDENCE_ID = "d3-w7s6-local-intrinsic-pair-spatial-convergence-v1"
const CANDIDATE_ID = "d3-w7s6-historical-length-alignment-witness-v1"
const LENGTHS = (
    lr_open_m=1.90530e-3,
    lr_short_m=3.04226e-3,
    lc_m=0.17605e-3,
    lp_open_m=2.58184e-3,
    lp_short_m=2.20526e-3,
)
const OUTER_NAMES = (:r_short, :r_open, :p_short, :p_open)
const OUTER_LENGTHS_M = (
    r_short=LENGTHS.lr_short_m,
    r_open=LENGTHS.lr_open_m,
    p_short=LENGTHS.lp_short_m,
    p_open=LENGTHS.lp_open_m,
)
const BASE_CPW_SECTION_M = 50.0e-6
const BASE_MTL_SECTION_M = 10.0e-6
const FREQUENCY_MIN_HZ = 3.5e9
const FREQUENCY_MAX_HZ = 7.0e9
const FREQUENCY_STEP_HZ = 0.25e6
const REQUIRED_CONSECUTIVE_PASSES = 2
const MAX_DISCOVERY_LEVELS = 10
const THRESHOLDS = (f_r=1.0e-3, f_p=1.0e-3, f_n=1.0e-2)

include(joinpath(SOURCE_DIR, "d3_circuit_plans.jl"))
include(joinpath(SOURCE_DIR, "d3_resonator_input.jl"))
include(joinpath(SOURCE_DIR, "d3_exact_n_response.jl"))
include(joinpath(SOURCE_DIR, "d3_signed_zero_midpoint.jl"))
using .D3ResonatorInput: bind_d3_rev10_q2d_input,
    load_d3_continuous_ground_q2d_input
using .D3SignedZeroMidpoint: d3_signed_zero_grid_identity,
    d3_signed_zero_midpoint

struct ProbeModel
    ctt::Matrix{Float64}
    cti::SparseMatrixCSC{Float64,Int}
    cit::SparseMatrixCSC{Float64,Int}
    cii::SparseMatrixCSC{Float64,Int}
    ktt::Matrix{Float64}
    kti::SparseMatrixCSC{Float64,Int}
    kit::SparseMatrixCSC{Float64,Int}
    kii::SparseMatrixCSC{Float64,Int}
    coordinate_order::Vector{Symbol}
    port_indices::Vector{Int}
    provenance
    matrix_gate
end

sha256_file(path) = bytes2hex(SHA.sha256(read(path)))
canonical_sha256(value) = bytes2hex(SHA.sha256(codeunits(JSON3.write(value))))
git_text(arguments...) = readchomp(Cmd(["git", "-C", REPOSITORY_ROOT, arguments...]))
function progress(message)
    println(message)
    flush(stdout)
end

function exact_count(length_m, maximum_section_m)
    raw = Float64(length_m) / Float64(maximum_section_m)
    nearest = round(Int, raw)
    return isapprox(raw, nearest; atol=1.0e-12, rtol=1.0e-9) ? nearest : ceil(Int, raw)
end

function density_outer_counts(maximum_section_m)
    h = Float64(maximum_section_m)
    h > 0 || error("Maximum Single-Trace section length must be positive.")
    return NamedTuple{OUTER_NAMES}(
        Tuple(exact_count(getproperty(OUTER_LENGTHS_M, name), h) for name in OUTER_NAMES),
    )
end

function allocate_outer_counts(total_count)
    base = density_outer_counts(BASE_CPW_SECTION_M)
    minimum = sum(values(base))
    total = Int(total_count)
    total >= minimum || error("Single-Trace total count must be at least $(minimum).")
    counts = Dict(name => getproperty(base, name) for name in OUTER_NAMES)
    for _ in (minimum + 1):total
        selected = OUTER_NAMES[1]
        longest = getproperty(OUTER_LENGTHS_M, selected) / counts[selected]
        for name in OUTER_NAMES[2:end]
            cell = getproperty(OUTER_LENGTHS_M, name) / counts[name]
            if cell > longest
                selected = name
                longest = cell
            end
        end
        counts[selected] += 1
    end
    return NamedTuple{OUTER_NAMES}(Tuple(counts[name] for name in OUTER_NAMES))
end

function grid_state(outer_counts, mtl_count; origin)
    counts = NamedTuple{OUTER_NAMES}(
        Tuple(Int(getproperty(outer_counts, name)) for name in OUTER_NAMES),
    )
    all(>(0), values(counts)) || error("Every Single-Trace region needs sections.")
    mtl = Int(mtl_count)
    mtl > 0 || error("MTL count must be positive.")
    total = sum(values(counts))
    id = "cpw$(total)-$(join(values(counts), '-'))__mtl$(mtl)"
    return (id=id, outer_counts=counts, outer_total=total, mtl_count=mtl, origin=String(origin))
end

function inclusive_grid(lower_hz, upper_hz)
    lower = ceil(Int, Float64(lower_hz) / FREQUENCY_STEP_HZ) * FREQUENCY_STEP_HZ
    upper = floor(Int, Float64(upper_hz) / FREQUENCY_STEP_HZ) * FREQUENCY_STEP_HZ
    lower < upper || error("Frequency window contains fewer than two grid points.")
    return collect(lower:FREQUENCY_STEP_HZ:upper)
end

function matrix_gate(raw, label)
    return (
        label=label,
        status="PASS",
        validator="SuperconductingCircuitsCore.extract_linear_nodal_model",
        dimension=size(raw.capacitance, 1),
        capacitance_positive_definite=true,
        inverse_inductance_positive_semidefinite=true,
        capacitance_sha256=raw.provenance.capacitance_sha256,
        inverse_inductance_sha256=raw.provenance.inverse_inductance_sha256,
    )
end

function probe_model(built, contract_id, expected_endpoints)
    graph = engineering_graph(built.plan)
    ordered_ports = sort(collect(graph.ports); by=entry -> entry.second.port_index)
    [(entry.first, entry.second.port_index, entry.second.endpoint) for entry in ordered_ports] == [
        (:input_port, 1, expected_endpoints[1]),
        (:output_port, 2, expected_endpoints[2]),
    ] || error("Circuit Plan does not preserve [P_r,P_p].")
    raw = d3_auxiliary_compiled_port_model(built; contract_id)
    raw.provenance.removed_boundary_rows == ["P1", "P2", "R_port_1", "R_port_2"] ||
        error("Unexpected auxiliary-port boundary removal.")
    terminals = raw.port_indices
    interior = [index for index in axes(raw.capacitance, 1) if !(index in terminals)]
    c = raw.capacitance
    k = raw.inverse_inductance
    return ProbeModel(
        Matrix(c[terminals, terminals]),
        sparse(c[terminals, interior]),
        sparse(c[interior, terminals]),
        sparse(c[interior, interior]),
        Matrix(k[terminals, terminals]),
        sparse(k[terminals, interior]),
        sparse(k[interior, terminals]),
        sparse(k[interior, interior]),
        Symbol.(raw.coordinate_order),
        Vector{Int}(raw.port_indices),
        raw.provenance,
        matrix_gate(raw, contract_id),
    )
end

function terminal_admittance(model::ProbeModel, frequency_hz)
    omega = 2π * Float64(frequency_hz)
    dtt = model.ktt - omega^2 * model.ctt
    reduced = if isempty(model.kii)
        dtt
    else
        dti = model.kti - omega^2 * model.cti
        dit = model.kit - omega^2 * model.cit
        dii = model.kii - omega^2 * model.cii
        dtt - Matrix(dti * (dii \ Matrix(dit)))
    end
    all(isfinite, reduced) || error("Conservative Schur reduction is nonfinite.")
    return ComplexF64.(reduced ./ (-im * omega))
end

function interval_breakpoints(start_m, length_m, count)
    points = [Float64(start_m) + Float64(length_m) * index / Int(count) for index in 0:Int(count)]
    points[1] = Float64(start_m)
    points[end] = Float64(start_m + length_m)
    return points
end

function explicit_line_breakpoints(head_length_m, window_length_m, tail_length_m, head_count, mtl_count, tail_count)
    head = interval_breakpoints(0.0, head_length_m, head_count)
    window = interval_breakpoints(head_length_m, window_length_m, mtl_count)
    tail = interval_breakpoints(head_length_m + window_length_m, tail_length_m, tail_count)
    return vcat(head[1:(end - 1)], window[1:(end - 1)], tail)
end

function build_explicit_intrinsic_pair_plan(lines, state, l_matrix, c_matrix, contract_id)
    readout_breakpoints = explicit_line_breakpoints(
        LENGTHS.lr_short_m,
        LENGTHS.lc_m,
        LENGTHS.lr_open_m,
        state.outer_counts.r_short,
        state.mtl_count,
        state.outer_counts.r_open,
    )
    filter_breakpoints = explicit_line_breakpoints(
        LENGTHS.lp_short_m,
        LENGTHS.lc_m,
        LENGTHS.lp_open_m,
        state.outer_counts.p_short,
        state.mtl_count,
        state.outer_counts.p_open,
    )
    reference_section_length = max(
        maximum(diff(readout_breakpoints)),
        maximum(diff(filter_breakpoints)),
    ) * (1 + 8eps(Float64))
    mtl_section_length = LENGTHS.lc_m / state.mtl_count
    plan = CircuitPlan(contract_id)
    readout_grounded_head = external_node("intrinsic_pair_readout_grounded_head")
    readout_open_tail = external_node("intrinsic_pair_readout_open_tail")
    filter_grounded_head = external_node("intrinsic_pair_filter_grounded_head")
    filter_open_tail = external_node("intrinsic_pair_filter_open_tail")
    mtl_model = MTLCoupledRLGCSpec(
        start1_m=LENGTHS.lr_short_m,
        start2_m=LENGTHS.lp_short_m,
        length_m=LENGTHS.lc_m,
        section_length_m=mtl_section_length,
        l_matrix_per_m_h=l_matrix,
        c_matrix_per_m_f=c_matrix,
    )
    readout = add_quarter_wave_resonator!(
        plan;
        id=:intrinsic_pair_readout_resonator,
        grounded_head=readout_grounded_head,
        open_tail=readout_open_tail,
        spec=_d3_line_spec(
            length_m=LENGTHS.lr_short_m + LENGTHS.lc_m + LENGTHS.lr_open_m,
            section_length_m=reference_section_length,
            l_per_m_h=lines.readout_l_per_m_h,
            c_per_m_f=lines.readout_c_per_m_f,
        ),
        breakpoints_m=readout_breakpoints,
        section_overrides=[coupled_line_section_override(mtl_model, 1)],
    )
    filter = add_quarter_wave_resonator!(
        plan;
        id=:intrinsic_pair_filter_resonator,
        grounded_head=filter_grounded_head,
        open_tail=filter_open_tail,
        spec=_d3_line_spec(
            length_m=LENGTHS.lp_short_m + LENGTHS.lc_m + LENGTHS.lp_open_m,
            section_length_m=reference_section_length,
            l_per_m_h=lines.filter_l_per_m_h,
            c_per_m_f=lines.filter_c_per_m_f,
        ),
        breakpoints_m=filter_breakpoints,
        section_overrides=[coupled_line_section_override(mtl_model, 2)],
    )
    window = couple_transmission_window!(
        plan;
        id=:intrinsic_pair_mtl_window,
        line1=readout.line,
        line2=filter.line,
        start1=LENGTHS.lr_short_m,
        start2=LENGTHS.lp_short_m,
        length=LENGTHS.lc_m,
        model=mtl_model,
        coupling_orientation=:same_direction,
    )
    _d3_auxiliary_ports(plan, readout_open_tail, filter_open_tail, 50.0)
    return (
        plan=plan,
        component=(
            readout_open_tail=readout_open_tail,
            filter_open_tail=filter_open_tail,
            readout=readout,
            filter=filter,
            window=window,
        ),
        requested_breakpoints=(readout=readout_breakpoints, filter=filter_breakpoints),
    )
end

function build_model(lines, state; diagonal)
    l_matrix = diagonal ? Matrix(Diagonal(diag(lines.l_matrix_per_m_h))) : lines.l_matrix_per_m_h
    c_matrix = diagonal ? Matrix(Diagonal(diag(lines.c_matrix_per_m_f))) : lines.c_matrix_per_m_f
    contract_id = "d3-w7s6-grid-$(state.id)-$(diagonal ? "diagonal" : "distributed")"
    built = build_explicit_intrinsic_pair_plan(lines, state, l_matrix, c_matrix, contract_id)
    return (
        built=built,
        probe=probe_model(
            built,
            contract_id,
            (built.component.readout_open_tail, built.component.filter_open_tail),
        ),
    )
end

function actual_grid_record(state, diagonal, physical)
    diagonal.probe.coordinate_order == physical.probe.coordinate_order ||
        error("Diagonal and distributed node orders differ.")
    readout = physical.built.component.readout.line.section_boundaries_m
    filter = physical.built.component.filter.line.section_boundaries_m
    all(isapprox.(
        readout,
        physical.built.requested_breakpoints.readout;
        atol=1.0e-12,
        rtol=1.0e-9,
    )) ||
        error("Readout assembled grid differs from requested breakpoints.")
    all(isapprox.(
        filter,
        physical.built.requested_breakpoints.filter;
        atol=1.0e-12,
        rtol=1.0e-9,
    )) ||
        error("Filter assembled grid differs from requested breakpoints.")
    return (
        outer_counts=state.outer_counts,
        outer_total=state.outer_total,
        mtl_count=state.mtl_count,
        outer_maximum_section_m=maximum(
            getproperty(OUTER_LENGTHS_M, name) / getproperty(state.outer_counts, name) for name in OUTER_NAMES
        ),
        mtl_section_m=LENGTHS.lc_m / state.mtl_count,
        readout_breakpoints_m=readout,
        filter_breakpoints_m=filter,
        breakpoint_sha256=canonical_sha256((readout=readout, filter=filter)),
        physical_node_count=length(physical.probe.coordinate_order),
        terminal_order=("P_r", "P_p"),
        terminal_indices=physical.probe.port_indices,
    )
end

function evaluate_y_grid(model, frequencies)
    values = Vector{Matrix{ComplexF64}}(undef, length(frequencies))
    Threads.@threads for index in eachindex(frequencies)
        values[index] = terminal_admittance(model, frequencies[index])
    end
    return Dict(frequencies[index] => values[index] for index in eachindex(frequencies))
end

function strict_opposite_sign(left, right)
    return !iszero(left) && !iszero(right) && ((left < 0 && right > 0) || (left > 0 && right < 0))
end

function diagonal_receipt(observable, grid, y_by_frequency, index, branch_identity)
    response(frequency) = y_by_frequency[frequency][index, index]
    qualifier = (lower, upper, left, right) -> (
        pole_free=all(value -> isfinite(real(value)) && isfinite(imag(value)), (left, right)),
        branch_unambiguous=strict_opposite_sign(imag(left), imag(right)),
        branch_identity=branch_identity,
    )
    return d3_signed_zero_midpoint(
        grid,
        response;
        observable_id=observable,
        grid_identity=d3_signed_zero_grid_identity(grid),
        grid_step_hz=FREQUENCY_STEP_HZ,
        grid_window_hz=(first(grid), last(grid)),
        branch_identity,
        bracket_qualifier=qualifier,
    )
end

function notch_receipt(grid, y_by_frequency)
    response(frequency) = inv(y_by_frequency[frequency])[2, 1]
    qualifier = function(lower, upper, left, right)
        y_lower = y_by_frequency[lower]
        y_upper = y_by_frequency[upper]
        determinant_lower = det(y_lower)
        determinant_upper = det(y_upper)
        determinant_finite = all(
            value -> isfinite(real(value)) && isfinite(imag(value)) && !iszero(real(value)),
            (determinant_lower, determinant_upper),
        )
        pole_free = determinant_finite &&
            signbit(real(determinant_lower)) == signbit(real(determinant_upper))
        numerator_crossing = strict_opposite_sign(imag(y_lower[2, 1]), imag(y_upper[2, 1]))
        return (
            pole_free=pole_free,
            branch_unambiguous=numerator_crossing,
            branch_identity="intrinsic-pair-transfer-zero-below-diagonal-modes",
        )
    end
    return d3_signed_zero_midpoint(
        grid,
        response;
        observable_id=:f_n,
        grid_identity=d3_signed_zero_grid_identity(grid),
        grid_step_hz=FREQUENCY_STEP_HZ,
        grid_window_hz=(first(grid), last(grid)),
        branch_identity="intrinsic-pair-transfer-zero-below-diagonal-modes",
        bracket_qualifier=qualifier,
    )
end

function evaluate_state(lines, state)
    started = time()
    progress("STATE_BEGIN $(state.id)")
    diagonal = build_model(lines, state; diagonal=true)
    physical = build_model(lines, state; diagonal=false)
    grid_record = actual_grid_record(state, diagonal, physical)
    readout_total = LENGTHS.lr_short_m + LENGTHS.lc_m + LENGTHS.lr_open_m
    filter_total = LENGTHS.lp_short_m + LENGTHS.lc_m + LENGTHS.lp_open_m
    readout_seed = 1 / (4readout_total * sqrt(lines.readout_l_per_m_h * lines.readout_c_per_m_f))
    filter_seed = 1 / (4filter_total * sqrt(lines.filter_l_per_m_h * lines.filter_c_per_m_f))
    readout_grid = inclusive_grid(max(FREQUENCY_MIN_HZ, 0.85readout_seed), min(FREQUENCY_MAX_HZ, 1.15readout_seed))
    filter_grid = inclusive_grid(max(FREQUENCY_MIN_HZ, 0.85filter_seed), min(FREQUENCY_MAX_HZ, 1.15filter_seed))
    diagonal_grid = sort(unique(vcat(readout_grid, filter_grid)))
    diagonal_y = evaluate_y_grid(diagonal.probe, diagonal_grid)
    f_r = diagonal_receipt(:f_r, readout_grid, diagonal_y, 1, "readout-diagonal-quarter-wave-root")
    f_p = diagonal_receipt(:f_p, filter_grid, diagonal_y, 2, "filter-diagonal-quarter-wave-root")
    if f_r.status != "PASS" || f_p.status != "PASS"
        result = (
            status="NOT_EVALUABLE",
            state=state,
            grid=grid_record,
            reason="diagonal midpoint extraction failed",
            extraction=(f_r=f_r, f_p=f_p, f_n=nothing),
            values_hz=nothing,
            elapsed_seconds=time() - started,
        )
        progress("STATE_FAIL $(state.id) $(result.reason)")
        return result
    end
    notch_upper = min(f_r.midpoint_frequency_hz, f_p.midpoint_frequency_hz) - 1.0e6
    notch_grid = inclusive_grid(FREQUENCY_MIN_HZ, notch_upper)
    physical_y = evaluate_y_grid(physical.probe, notch_grid)
    f_n = notch_receipt(notch_grid, physical_y)
    status = f_n.status == "PASS" ? "COMPLETE" : "NOT_EVALUABLE"
    values = status == "COMPLETE" ? (
        f_r=f_r.midpoint_frequency_hz,
        f_p=f_p.midpoint_frequency_hz,
        f_n=f_n.midpoint_frequency_hz,
    ) : nothing
    result = (
        status=status,
        state=state,
        grid=grid_record,
        reason=status == "COMPLETE" ? nothing : "notch midpoint extraction failed",
        extraction=(f_r=f_r, f_p=f_p, f_n=f_n),
        values_hz=values,
        invariants=(diagonal=diagonal.probe.matrix_gate, physical=physical.probe.matrix_gate),
        elapsed_seconds=time() - started,
    )
    progress(
        status == "COMPLETE" ?
            "STATE_DONE $(state.id) fr=$(values.f_r) fp=$(values.f_p) fn=$(values.f_n) seconds=$(round(result.elapsed_seconds; digits=1))" :
            "STATE_FAIL $(state.id) $(result.reason)",
    )
    return result
end

function cached_state!(states, lines, state, cache_directory, cache_identity)
    haskey(states, state.id) && return states[state.id]
    mkpath(cache_directory)
    path = joinpath(cache_directory, "$(state.id).jls")
    record = if isfile(path)
        cached = deserialize(path)
        cached.identity == cache_identity || error("State cache identity mismatch: $(path)")
        progress("STATE_CACHE_HIT $(state.id)")
        cached.record
    else
        value = evaluate_state(lines, state)
        temporary = "$(path).tmp-$(getpid())"
        serialize(temporary, (identity=cache_identity, record=value))
        mv(temporary, path; force=false)
        value
    end
    states[state.id] = record
    return record
end

function comparison(candidate, reference; axis, phase)
    candidate.status == "COMPLETE" && reference.status == "COMPLETE" || return (
        status="NOT_EVALUABLE",
        axis=axis,
        phase=phase,
        candidate_state=candidate.state,
        reference_state=reference.state,
        reason="candidate or reference state is incomplete",
    )
    changes = NamedTuple{(:f_r, :f_p, :f_n)}(Tuple(
        begin
            candidate_value = getproperty(candidate.values_hz, quantity)
            reference_value = getproperty(reference.values_hz, quantity)
            delta_fraction = abs(reference_value - candidate_value) / abs(candidate_value)
            threshold = getproperty(THRESHOLDS, quantity)
            (
                candidate_hz=candidate_value,
                reference_hz=reference_value,
                raw_difference_hz=reference_value - candidate_value,
                delta_fraction=delta_fraction,
                delta_percent=100delta_fraction,
                threshold_fraction=threshold,
                threshold_percent=100threshold,
                pass=delta_fraction <= threshold,
            )
        end for quantity in (:f_r, :f_p, :f_n)
    ))
    return (
        status=all(getproperty(changes, quantity).pass for quantity in (:f_r, :f_p, :f_n)) ? "PASS" : "FAIL",
        axis=axis,
        phase=phase,
        candidate_state=candidate.state,
        reference_state=reference.state,
        changes=changes,
    )
end

function discovery!(states, lines, cache_directory, cache_identity, state_at_level; axis, phase)
    levels = Any[]
    transitions = Any[]
    pass_streak = 0
    for level in 0:MAX_DISCOVERY_LEVELS
        state = state_at_level(level)
        record = cached_state!(states, lines, state, cache_directory, cache_identity)
        push!(levels, record)
        record.status == "COMPLETE" || return (
            status="NOT_EVALUABLE",
            reason="$(axis) discovery state is incomplete",
            levels=levels,
            transitions=transitions,
        )
        if length(levels) > 1
            transition = comparison(levels[end - 1], levels[end]; axis, phase="$(phase)-adjacent")
            push!(transitions, transition)
            pass_streak = transition.status == "PASS" ? pass_streak + 1 : 0
            progress("TRANSITION $(axis) $(levels[end - 1].state.id) -> $(record.state.id) $(transition.status)")
            if pass_streak == REQUIRED_CONSECUTIVE_PASSES
                reference = record
                points = [comparison(item, reference; axis, phase="$(phase)-to-reference") for item in levels]
                return (
                    status="PASS",
                    levels=levels,
                    transitions=transitions,
                    reference=reference,
                    plot_points=points,
                )
            end
        end
    end
    return (
        status="NOT_EVALUABLE",
        reason="$(axis) discovery reached its level cap before two passes",
        levels=levels,
        transitions=transitions,
    )
end

function direct_threshold_search!(
    states,
    lines,
    cache_directory,
    cache_identity,
    state_at_coordinate,
    discovery;
    axis,
    coordinate,
    phase,
)
    discovery.status == "PASS" || return (
        status="NOT_EVALUABLE",
        reason="$(axis) discovery did not pass",
    )
    reference = discovery.reference
    trials = copy(discovery.plot_points)
    ordered = sort(unique((coordinate(item.state) for item in discovery.levels)))
    direct = Dict(item.candidate_state.id => item for item in trials)
    first_pass_index = findfirst(value -> begin
        state = only(item for item in discovery.levels if coordinate(item.state) == value)
        direct[state.state.id].status == "PASS"
    end, ordered)
    isnothing(first_pass_index) && return (
        status="NOT_EVALUABLE",
        reason="$(axis) has no direct-to-reference PASS coordinate",
        trials=trials,
    )
    first_pass = ordered[first_pass_index]
    failing = [value for value in ordered if value < first_pass && begin
        state = only(item for item in discovery.levels if coordinate(item.state) == value)
        direct[state.state.id].status == "FAIL"
    end]
    if isempty(failing)
        selected_state = state_at_coordinate(first_pass, "$(phase)-selected")
        selected = cached_state!(states, lines, selected_state, cache_directory, cache_identity)
        selected_trial = comparison(
            selected,
            reference;
            axis,
            phase="$(phase)-selected-to-reference",
        )
        if !any(item -> item.candidate_state.id == selected.state.id, trials)
            push!(trials, selected_trial)
        end
        selected_trial.status == "PASS" || return (
            status="NOT_EVALUABLE",
            reason="$(axis) selected integer coordinate did not pass its retained reference",
            trials=trials,
        )
        return (
            status="PASS",
            selected=selected,
            selected_coordinate=first_pass,
            last_fail_coordinate=nothing,
            reference=reference,
            trials=trials,
        )
    end
    low = maximum(failing)
    high = first_pass
    while high - low > 1
        middle = (low + high) ÷ 2
        state = state_at_coordinate(middle, "$(phase)-binary")
        record = cached_state!(states, lines, state, cache_directory, cache_identity)
        trial = comparison(record, reference; axis, phase="$(phase)-binary-to-reference")
        push!(trials, trial)
        progress("BINARY $(axis) N=$(middle) $(trial.status)")
        if trial.status == "PASS"
            high = middle
        elseif trial.status == "FAIL"
            low = middle
        else
            return (
                status="NOT_EVALUABLE",
                reason="$(axis) binary state is incomplete",
                trials=trials,
            )
        end
    end
    selected_state = state_at_coordinate(high, "$(phase)-selected")
    selected = cached_state!(states, lines, selected_state, cache_directory, cache_identity)
    selected_trial = comparison(
        selected,
        reference;
        axis,
        phase="$(phase)-selected-to-reference",
    )
    if !any(item -> item.candidate_state.id == selected.state.id, trials)
        push!(trials, selected_trial)
    end
    selected_trial.status == "PASS" || return (
        status="NOT_EVALUABLE",
        reason="$(axis) selected integer coordinate did not pass its retained reference",
        trials=trials,
    )
    return (
        status="PASS",
        selected=selected,
        selected_coordinate=high,
        last_fail_coordinate=low,
        reference=reference,
        trials=sort(trials; by=item -> coordinate(item.candidate_state)),
    )
end

function run_experiment(lines, cache_directory, cache_identity)
    states = Dict{String,Any}()
    base_outer = density_outer_counts(BASE_CPW_SECTION_M)
    mtl_state(level) = grid_state(
        base_outer,
        exact_count(LENGTHS.lc_m, BASE_MTL_SECTION_M / 2.0^level);
        origin="mtl-first-density-level-$(level)",
    )
    mtl_discovery = discovery!(
        states,
        lines,
        cache_directory,
        cache_identity,
        mtl_state;
        axis="mtl_first",
        phase="mtl-first",
    )
    mtl_search = direct_threshold_search!(
        states,
        lines,
        cache_directory,
        cache_identity,
        (count, origin) -> grid_state(base_outer, count; origin);
        axis="mtl_first",
        coordinate=state -> state.mtl_count,
        phase="mtl-first",
        discovery=mtl_discovery,
    )
    mtl_search.status == "PASS" || return (
        status="NOT_EVALUABLE",
        blocker="MTL-first qualification failed",
        mtl_first=(discovery=mtl_discovery, search=mtl_search),
        states=collect(values(states)),
    )
    selected_mtl = mtl_search.selected_coordinate

    cpw_state(level) = grid_state(
        density_outer_counts(BASE_CPW_SECTION_M / 2.0^level),
        selected_mtl;
        origin="single-trace-density-level-$(level)",
    )
    cpw_discovery = discovery!(
        states,
        lines,
        cache_directory,
        cache_identity,
        cpw_state;
        axis="single_trace",
        phase="single-trace",
    )
    cpw_search = direct_threshold_search!(
        states,
        lines,
        cache_directory,
        cache_identity,
        (count, origin) -> grid_state(allocate_outer_counts(count), selected_mtl; origin);
        axis="single_trace",
        coordinate=state -> state.outer_total,
        phase="single-trace",
        discovery=cpw_discovery,
    )
    cpw_search.status == "PASS" || return (
        status="NOT_EVALUABLE",
        blocker="Single-Trace qualification failed",
        mtl_first=(discovery=mtl_discovery, search=mtl_search),
        single_trace=(discovery=cpw_discovery, search=cpw_search),
        states=collect(values(states)),
    )
    selected_outer = cpw_search.selected.state.outer_counts

    recheck_base_h = LENGTHS.lc_m / selected_mtl
    recheck_state(level) = grid_state(
        selected_outer,
        exact_count(LENGTHS.lc_m, recheck_base_h / 2.0^level);
        origin="mtl-recheck-density-level-$(level)",
    )
    recheck_discovery = discovery!(
        states,
        lines,
        cache_directory,
        cache_identity,
        recheck_state;
        axis="mtl_recheck",
        phase="mtl-recheck",
    )
    recheck_search = direct_threshold_search!(
        states,
        lines,
        cache_directory,
        cache_identity,
        (count, origin) -> grid_state(selected_outer, count; origin);
        axis="mtl_recheck",
        coordinate=state -> state.mtl_count,
        phase="mtl-recheck",
        discovery=recheck_discovery,
    )
    recheck_search.status == "PASS" || return (
        status="NOT_EVALUABLE",
        blocker="MTL recheck failed",
        mtl_first=(discovery=mtl_discovery, search=mtl_search),
        single_trace=(discovery=cpw_discovery, search=cpw_search),
        mtl_recheck=(discovery=recheck_discovery, search=recheck_search),
        states=collect(values(states)),
    )

    final_candidate = recheck_search.selected
    joint_reference_state = grid_state(
        cpw_discovery.reference.state.outer_counts,
        recheck_discovery.reference.state.mtl_count;
        origin="joint-retained-reference",
    )
    joint_reference = cached_state!(states, lines, joint_reference_state, cache_directory, cache_identity)
    joint_comparison = comparison(
        final_candidate,
        joint_reference;
        axis="joint",
        phase="final-joint-to-reference",
    )
    return (
        status=joint_comparison.status == "PASS" ? "SPATIAL_DISCRETIZATION_ELIGIBLE" : "DISCRETIZATION_INELIGIBLE",
        blocker=joint_comparison.status == "PASS" ? nothing : "final joint comparison failed",
        minimum_operational_grid=(
            outer_counts=final_candidate.state.outer_counts,
            outer_total=final_candidate.state.outer_total,
            mtl_count=final_candidate.state.mtl_count,
            state_id=final_candidate.state.id,
        ),
        retained_joint_reference=(
            outer_counts=joint_reference.state.outer_counts,
            outer_total=joint_reference.state.outer_total,
            mtl_count=joint_reference.state.mtl_count,
            state_id=joint_reference.state.id,
        ),
        mtl_first=(discovery=mtl_discovery, search=mtl_search),
        single_trace=(discovery=cpw_discovery, search=cpw_search),
        mtl_recheck=(discovery=recheck_discovery, search=recheck_search),
        joint=(
            status=joint_comparison.status,
            comparison=joint_comparison,
            plot_points=(
                comparison(final_candidate, joint_reference; axis="joint", phase="final-joint-to-reference"),
                comparison(joint_reference, joint_reference; axis="joint", phase="joint-reference"),
            ),
        ),
        states=sort(collect(values(states)); by=item -> item.state.id),
    )
end

function csv_escape(value)
    text = String(value)
    occursin(r"[\",\n]", text) || return text
    escaped = replace(text, "\"" => "\"\"")
    return string('\"', escaped, '\"')
end

function write_points_csv(path, experiment)
    open(path, "w") do io
        println(io, "axis,phase,state_id,outer_total,r_short,r_open,p_short,p_open,mtl_count,f_r_hz,f_p_hz,f_n_hz,delta_f_r_percent,delta_f_p_percent,delta_f_n_percent,status")
        for axis_name in (:mtl_first, :single_trace, :mtl_recheck)
            hasproperty(experiment, axis_name) || continue
            axis_result = getproperty(experiment, axis_name)
            axis_result.search.status == "PASS" || continue
            for point in axis_result.search.trials
                state = point.candidate_state
                changes = point.changes
                row = (
                    String(axis_name),
                    point.phase,
                    state.id,
                    state.outer_total,
                    state.outer_counts.r_short,
                    state.outer_counts.r_open,
                    state.outer_counts.p_short,
                    state.outer_counts.p_open,
                    state.mtl_count,
                    changes.f_r.candidate_hz,
                    changes.f_p.candidate_hz,
                    changes.f_n.candidate_hz,
                    changes.f_r.delta_percent,
                    changes.f_p.delta_percent,
                    changes.f_n.delta_percent,
                    point.status,
                )
                println(io, join(csv_escape.(string.(row)), ','))
            end
        end
        if hasproperty(experiment, :joint)
            for point in experiment.joint.plot_points
                state = point.candidate_state
                changes = point.changes
                row = (
                    "joint",
                    point.phase,
                    state.id,
                    state.outer_total,
                    state.outer_counts.r_short,
                    state.outer_counts.r_open,
                    state.outer_counts.p_short,
                    state.outer_counts.p_open,
                    state.mtl_count,
                    changes.f_r.candidate_hz,
                    changes.f_p.candidate_hz,
                    changes.f_n.candidate_hz,
                    changes.f_r.delta_percent,
                    changes.f_p.delta_percent,
                    changes.f_n.delta_percent,
                    point.status,
                )
                println(io, join(csv_escape.(string.(row)), ','))
            end
        end
    end
end

function verify_sources()
    head = git_text("rev-parse", "HEAD")
    success(`git -C $REPOSITORY_ROOT merge-base --is-ancestor $REQUIRED_WORKBENCH_ANCESTOR $head`) ||
        error("Workbench HEAD does not contain the integrated midpoint extractor.")
    isempty(git_text("status", "--porcelain", "--untracked-files=all")) ||
        error("The evidence run requires a clean committed Task checkout.")
    q2d_sha = sha256_file(Q2D_PATH)
    q2d_sha == REQUIRED_Q2D_SHA256 || error("W7/S6 Q2D artifact SHA mismatch.")
    return (workbench_revision=head, q2d_sha256=q2d_sha)
end

function write_output(output_directory, receipt)
    ispath(output_directory) && error("Evidence output already exists: $(output_directory)")
    parent = dirname(output_directory)
    mkpath(parent)
    temporary = mktempdir(parent; prefix=".$(basename(output_directory)).building-", cleanup=false)
    try
        open(joinpath(temporary, "spatial-discretization-evidence.v1.json"), "w") do io
            JSON3.pretty(io, receipt)
            println(io)
        end
        write_points_csv(joinpath(temporary, "convergence-points.csv"), receipt.experiment)
        mv(temporary, output_directory)
    catch
        isdir(temporary) && rm(temporary; recursive=true, force=true)
        rethrow()
    end
end

function main()
    length(ARGS) == 1 || error("Usage: julia d3_w7_s6_spatial_convergence.jl <output-directory>")
    output_directory = abspath(ARGS[1])
    sources = verify_sources()
    authority = load_d3_continuous_ground_q2d_input(Q2D_PATH)
    lines = bind_d3_rev10_q2d_input(
        authority;
        section_length_m=BASE_CPW_SECTION_M,
        mtl_section_length_m=BASE_MTL_SECTION_M,
    )
    runner_sha = sha256_file(SOURCE_PATH)
    cache_identity = canonical_sha256((
        evidence_id=EVIDENCE_ID,
        workbench_revision=sources.workbench_revision,
        runner_sha256=runner_sha,
        q2d_sha256=sources.q2d_sha256,
        lengths=LENGTHS,
        frequency=(FREQUENCY_MIN_HZ, FREQUENCY_MAX_HZ, FREQUENCY_STEP_HZ),
        thresholds=THRESHOLDS,
    ))
    cache_directory = get(
        ENV,
        "D3_W7_GRID_CACHE",
        joinpath("/tmp", "d3-w7-grid-cache-$(cache_identity[1:16])"),
    )
    started_at = now(UTC)
    experiment = run_experiment(lines, cache_directory, cache_identity)
    receipt = (
        schema_version="spatial-discretization-evidence.v1",
        evidence_id=EVIDENCE_ID,
        generated_at_utc=string(now(UTC)),
        lifecycle_state="CONVERGING",
        data_class="project-internal",
        authority_status="diagnostic_only",
        promotion_eligible=false,
        candidate=(id=CANDIDATE_ID, lengths=LENGTHS, u_idc="NOT_SUPPLIED_AND_UNCONSUMED"),
        model=(
            topology="local distributed intrinsic pair",
            included=("readout Single Trace CPW", "filter Single Trace CPW", "same-direction coupled MTL window"),
            excluded=("qubit", "C0r/Q3D", "IDC electrical element", "feedline", "regularizer", "P1/P2", "Equivalent arm"),
            terminals=(order=("P_r", "P_p"), z21="V_p/I_r at I_p=0", termination="nonterminating"),
            time_convention="exp(-i*omega*t)",
        ),
        source=(
            workbench_revision=sources.workbench_revision,
            runner_sha256=runner_sha,
            extractor_sha256=sha256_file(joinpath(SOURCE_DIR, "d3_signed_zero_midpoint.jl")),
            q2d_artifact_id=lines.q2d_artifact_id,
            q2d_artifact_sha256=sources.q2d_sha256,
            q2d_payload_sha256=lines.q2d_authority.payload_sha256,
            orpen_producer_revision=REQUIRED_ORPEN_PRODUCER_REVISION,
            material_profile_id=lines.q2d_authority.material_profile_id,
            material_profile_sha256=lines.q2d_authority.material_profile_sha256,
            material_authority_sha256=lines.q2d_authority.material_authority_sha256,
            publication_state=lines.q2d_authority.publication_state,
        ),
        contract=(
            search_order=("MTL first", "four Single-Trace regions", "MTL recheck", "joint"),
            frequency_grid=(min_hz=FREQUENCY_MIN_HZ, max_hz=FREQUENCY_MAX_HZ, step_hz=FREQUENCY_STEP_HZ),
            extraction="unique strict adjacent signed bracket midpoint",
            outputs=(f_r="Im(Y_rr)", f_p="Im(Y_pp)", f_n="Im(Z21)"),
            thresholds_fraction=THRESHOLDS,
            thresholds_percent=(f_r=0.1, f_p=0.1, f_n=1.0),
            required_consecutive_discovery_passes=REQUIRED_CONSECUTIVE_PASSES,
            operational_search="integer binary search against retained same-input fine reference",
        ),
        runtime=(
            julia_version=string(VERSION),
            julia_threads=Threads.nthreads(),
            started_at_utc=string(started_at),
            finished_at_utc=string(now(UTC)),
            cache_identity=cache_identity,
        ),
        experiment=experiment,
        nonclaims=(
            "not Equivalent agreement",
            "not Stage-2/Stage-3 closure",
            "not a Rev10 slot result",
            "not optimizer-wide envelope evidence",
            "not promotion or publication evidence",
        ),
    )
    write_output(output_directory, receipt)
    progress("EVIDENCE_DONE $(output_directory) status=$(experiment.status)")
end

if abspath(PROGRAM_FILE) == abspath(@__FILE__)
    main()
end
