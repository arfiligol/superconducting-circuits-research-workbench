# This file owns the auditable D3 forward-circuit execution lane. It screens
# public Q2D cases, adjusts only physical lengths and Cext, constructs the
# canonical response-matched two-pi full-coordinate Hamiltonian, evaluates its
# exact six-coordinate matched-port response, and packages distributed and
# equivalent comparison evidence. It never fits bare QRP parameters, runs
# Vector Fitting, or claims Human promotion.

using LinearAlgebra
using SHA

if !isdefined(@__MODULE__, :D3SemanticHash)
    include(joinpath(@__DIR__, "d3_semantic_hash.jl"))
end

const D3_FORWARD_RUN_SCHEMA = "d3-forward-circuit-run.v2"
const D3_FORWARD_INITIALIZER_SCHEMA = "purcell.spring2025-initial-spec.v1"
const D3_FORWARD_FULL_COORDINATE_CONTRACT =
    "d3-forward-response-matched-two-pi-full-coordinate-handoff-v1"
const D3_FORWARD_EXACT_SIX_RESPONSE_CONTRACT =
    "d3-exact-six-coordinate-open-response.v1"
const D3_FORWARD_SLOT_HZ = Float64[5.52e9, 5.76e9, 6.00e9, 6.24e9, 6.48e9]
const D3_FORWARD_Q2D_ROUTE = "public_q2d_cpw_spec_simulation_only"
const D3_FORWARD_AGENT_SCALES_HZ = (
    fr = 10.0e6,
    fp = 10.0e6,
    notch = 10.0e6,
    g = 10.0e6,
    J = 2.0e6,
    kappa = 1.0e6,
)
const D3_FORWARD_START_GUIDANCE = (
    coupling_length_scale = 490.0 / 318.0,
    readout_total_scale = 0.98,
    filter_total_scale = 1.0,
    notch_path_scale = 1.0064,
)
const D3_FORWARD_GRID_LINEWIDTH_FLOOR_HZ = 30.0e3
const D3_FORWARD_FINE_SAMPLES_PER_LINEWIDTH = 12.0
const D3_FORWARD_COARSE_SAMPLES_PER_LINEWIDTH = 6.0
const D3_FORWARD_LOCAL_HALF_WIDTHS = 6.0
const D3_FORWARD_LOCAL_MINIMUM_HALF_WIDTH_HZ = 0.5e6
const D3_FORWARD_LOCAL_MAXIMUM_HALF_WIDTH_HZ = 60.0e6
const D3_FORWARD_FINE_MAXIMUM_LOCAL_INTERVALS = 400
const D3_FORWARD_COARSE_MAXIMUM_LOCAL_INTERVALS = 200
const D3_FORWARD_CLOSED_POLE_MODE_RESIDUAL_MAX = 1.0e-9
const D3_FORWARD_CLOSED_POLE_MAX_EXCLUSION_SCALE_STEPS = 6
const D3_FORWARD_Z_CLOSURE_ABSOLUTE_TOLERANCE_OHM = 1.0e-4
const D3_FORWARD_S_CLOSURE_ABSOLUTE_TOLERANCE = 1.0e-8
const D3_FORWARD_CLOSURE_RELATIVE_TOLERANCE = 1.0e-8

function d3_forward_file_sha256(path)
    return open(String(path), "r") do io
        bytes2hex(SHA.sha256(io))
    end
end

function d3_forward_string_sha256(value)
    return bytes2hex(SHA.sha256(codeunits(String(value))))
end

function d3_forward_require_exact_keys(value, expected, context)
    value isa AbstractDict || error("$(context) must be a JSON object.")
    Set(String.(keys(value))) == Set(String.(expected)) || error(
        "$(context) keys do not exactly match its contract.",
    )
    return value
end

function d3_forward_positive(value, context)
    numeric = Float64(value)
    isfinite(numeric) && numeric > 0 || error("$(context) must be finite and positive.")
    return numeric
end

function d3_forward_require_bare_fit_disabled(requested)
    requested === false || error(
        "bare_fit_disabled_not_implemented: topology-constrained bare fitting must not run.",
    )
    return nothing
end

function load_d3_forward_target(path)
    input_path = abspath(String(path))
    isfile(input_path) || error("Missing D3 target contract: $(input_path)")
    payload = SuperconductingCircuitsCore.JSON3.read(
        read(input_path, String), Dict{String,Any},
    )
    d3_forward_require_exact_keys(
        payload,
        ["schema_version", "target_id", "revision", "title", "target_set",
            "implementation_case", "targets", "governance"],
        "D3 target",
    )
    payload["schema_version"] == "scq-design-target.v1" || error(
        "D3 target schema must be scq-design-target.v1.",
    )
    payload["target_id"] == "d3-intrinsic-interferometric-purcell-filter" || error(
        "D3 target_id is incompatible.",
    )
    Int(payload["revision"]) == 3 || error("D3 target revision must be 3.")
    targets = payload["targets"]
    d3_forward_require_exact_keys(
        targets,
        ["slot_frequencies", "filter_loaded_bare_offset", "readout_loaded_bare_offset",
            "readout_minus_filter_detuning", "interference_notch_frequency",
            "qubit_transition_frequency", "qubit_junction_inductance",
            "filter_loaded_bare_linewidth", "readout_filter_exchange_coupling",
            "qubit_readout_coupling"],
        "D3 target quantities",
    )
    slot_record = targets["slot_frequencies"]
    slot_record["unit"] == "GHz" || error("D3 slots must use GHz.")
    slots_hz = Float64.(slot_record["values"]) .* 1.0e9
    slots_hz == D3_FORWARD_SLOT_HZ || error("D3 target must contain the fixed five-slot grid.")
    function scalar(record_name, unit, multiplier)
        record = targets[record_name]
        record["unit"] == unit || error("D3 $(record_name) must use $(unit).")
        return Float64(record["value"]) * multiplier
    end
    lj = targets["qubit_junction_inductance"]
    lj["unit"] == "nH_per_junction" && Int(lj["parallel_junction_count"]) == 2 || error(
        "D3 qubit junction target must declare two nH_per_junction branches.",
    )
    return (
        payload = payload,
        input_path = input_path,
        input_sha256 = d3_forward_file_sha256(input_path),
        target_id = String(payload["target_id"]),
        revision = Int(payload["revision"]),
        slot_hz = slots_hz,
        readout_offset_hz = scalar("readout_loaded_bare_offset", "MHz", 1.0e6),
        filter_offset_hz = scalar("filter_loaded_bare_offset", "MHz", 1.0e6),
        notch_hz = scalar("interference_notch_frequency", "GHz", 1.0e9),
        qubit_f01_hz = scalar("qubit_transition_frequency", "GHz", 1.0e9),
        lj_per_junction_nH = Float64(lj["value"]),
        kappa_hz = scalar("filter_loaded_bare_linewidth", "MHz", 1.0e6),
        J_hz = scalar("readout_filter_exchange_coupling", "MHz", 1.0e6),
        g_hz = scalar("qubit_readout_coupling", "MHz", 1.0e6),
        g_tolerance_hz = Float64(
            targets["qubit_readout_coupling"]["objective_tolerance"]["value"],
        ) * 1.0e6,
    )
end

function load_d3_forward_initializer(path, target)
    input_path = abspath(String(path))
    isfile(input_path) || error("Missing D3 Spring2025 initializer: $(input_path)")
    payload = SuperconductingCircuitsCore.JSON3.read(
        read(input_path, String), Dict{String,Any},
    )
    d3_forward_require_exact_keys(
        payload,
        ["schema_version", "status", "source", "assumptions", "reference_geometry", "slots"],
        "D3 Spring2025 initializer",
    )
    payload["schema_version"] == D3_FORWARD_INITIALIZER_SCHEMA || error(
        "D3 Spring2025 initializer schema is incompatible.",
    )
    payload["status"] == "initializer_only" || error(
        "D3 Spring2025 values must remain initializer_only.",
    )
    slots = payload["slots"]
    length(slots) == 5 || error("D3 Spring2025 initializer must contain exactly five slots.")
    by_slot = Dict{Float64,Any}()
    for record in slots
        d3_forward_require_exact_keys(
            record,
            ["slot_hz", "target_frequencies_hz", "lengths_um", "round_trip_check_hz", "status"],
            "D3 initializer slot",
        )
        record["status"] == "initializer_only" || error(
            "Every D3 initializer slot must remain initializer_only.",
        )
        slot_hz = Float64(record["slot_hz"])
        haskey(by_slot, slot_hz) && error("D3 initializer contains a duplicate slot.")
        lengths = record["lengths_um"]
        d3_forward_require_exact_keys(
            lengths,
            ["lr_open_um", "lr_short_um", "lc_um", "lp_short_um", "lp_open_um",
                "lr_total_um", "lp_total_um", "notch_path_um"],
            "D3 initializer lengths",
        )
        all(value -> isfinite(Float64(value)) && Float64(value) > 0, values(lengths)) || error(
            "D3 initializer lengths must be finite and positive.",
        )
        frequencies = record["target_frequencies_hz"]
        Float64(frequencies["readout_loaded_bare_hz"]) == slot_hz + target.readout_offset_hz || error(
            "D3 initializer readout target disagrees with revision-3 target.",
        )
        Float64(frequencies["filter_loaded_bare_hz"]) == slot_hz + target.filter_offset_hz || error(
            "D3 initializer filter target disagrees with revision-3 target.",
        )
        Float64(frequencies["intrinsic_notch_hz"]) == target.notch_hz || error(
            "D3 initializer notch target disagrees with revision-3 target.",
        )
        by_slot[slot_hz] = record
    end
    sort(collect(keys(by_slot))) == target.slot_hz || error(
        "D3 initializer slots do not match the revision-3 target.",
    )
    assumptions = payload["assumptions"]
    assumptions["readout_length_reference"] ==
        "initializer_for_shorted_end_to_open_side_local_cut_plane" || error(
        "D3 initializer readout lengths must target the open-side local cut plane.",
    )
    assumptions["open_side_local_loading_included_in_formula"] === false || error(
        "The Spring2025 length formula must remain an unloaded initializer; " *
        "the open-side Maxwell block is added by the physical forward model.",
    )
    return (
        payload = payload,
        by_slot = by_slot,
        source_velocity_m_per_s = d3_forward_positive(
            assumptions["single_line_velocity_m_per_s"],
            "Spring2025 source velocity",
        ),
        input_path = input_path,
        input_sha256 = d3_forward_file_sha256(input_path),
    )
end

function d3_forward_target_for_slot(target, slot_hz)
    slot = Float64(slot_hz)
    slot in target.slot_hz || error("Unknown D3 slot $(slot) Hz.")
    return (
        slot_hz = slot,
        fq_hz = target.qubit_f01_hz,
        fr_hz = slot + target.readout_offset_hz,
        fp_hz = slot + target.filter_offset_hz,
        notch_hz = target.notch_hz,
        g_hz = target.g_hz,
        J_hz = target.J_hz,
        kappa_hz = target.kappa_hz,
    )
end

function d3_forward_design(; id, lr_open_um, lr_short_um, lc_um, lp_short_um, lp_open_um)
    values = Float64[lr_open_um, lr_short_um, lc_um, lp_short_um, lp_open_um]
    all(value -> isfinite(value) && value > 0, values) || error(
        "D3 physical section lengths must be finite and positive.",
    )
    return (
        id = Symbol(id),
        lr_open_um = values[1],
        lr_short_um = values[2],
        lc_um = values[3],
        lp_short_um = values[4],
        lp_open_um = values[5],
        lr_total_um = sum(values[1:3]),
        lp_total_um = sum(values[3:5]),
        notch_path_um = sum(values[2:4]),
    )
end

function d3_forward_design_from_initializer(record, case; guided, id)
    lengths = record["lengths_um"]
    # The source velocity is carried explicitly by the artifact assumptions;
    # callers attach it to the record before this physical scaling step.
    velocity_source = d3_forward_positive(record["source_velocity_m_per_s"], "source velocity")
    single_velocity = 1 / sqrt(case.single_l_per_m_h * case.single_c_per_m_f)
    coupled_velocities = [
        1 / sqrt(case.mtl_l_matrix_h_per_m[index, index] *
            case.mtl_c_matrix_f_per_m[index, index]) for index in 1:2
    ]
    single_scale = single_velocity / velocity_source
    coupled_scale = sqrt(prod(coupled_velocities)) / velocity_source
    base = d3_forward_design(
        id = id,
        lr_open_um = Float64(lengths["lr_open_um"]) * single_scale,
        lr_short_um = Float64(lengths["lr_short_um"]) * single_scale,
        lc_um = Float64(lengths["lc_um"]) * coupled_scale,
        lp_short_um = Float64(lengths["lp_short_um"]) * single_scale,
        lp_open_um = Float64(lengths["lp_open_um"]) * single_scale,
    )
    guided || return base
    guidance = D3_FORWARD_START_GUIDANCE
    new_lc = base.lc_um * guidance.coupling_length_scale
    desired_path = base.notch_path_um * guidance.notch_path_scale
    remaining_short = desired_path - new_lc
    remaining_short > 0 || error("D3 start guidance leaves a nonpositive short path.")
    split = base.lr_short_um / (base.lr_short_um + base.lp_short_um)
    lr_short = split * remaining_short
    lp_short = (1 - split) * remaining_short
    lr_total = base.lr_total_um * guidance.readout_total_scale
    lp_total = base.lp_total_um * guidance.filter_total_scale
    return d3_forward_design(
        id = id,
        lr_open_um = lr_total - lr_short - new_lc,
        lr_short_um = lr_short,
        lc_um = new_lc,
        lp_short_um = lp_short,
        lp_open_um = lp_total - lp_short - new_lc,
    )
end

function d3_forward_with_source_velocity(record, velocity)
    copied = Dict{String,Any}(String(key) => value for (key, value) in record)
    copied["source_velocity_m_per_s"] = Float64(velocity)
    return copied
end

function d3_forward_match_settings(target)
    slot = target.slot_hz
    return (
        readout_root_bracket_hz = (slot - 0.35e9, slot + 0.35e9),
        filter_root_bracket_hz = (slot - 0.35e9, slot + 0.35e9),
        notch_root_bracket_hz = (target.notch_hz - 0.30e9, target.notch_hz + 0.30e9),
        parallel_derivative_step_rad_s = 2π * 1.0e4,
        bridge_derivative_step_rad_s = 2π * 1.0e4,
        bisection_absolute_tolerance_rad_s = 2π * 10.0,
        bisection_relative_tolerance = 1.0e-13,
        bisection_max_iterations = 128,
        match_root_relative_tolerance = 2.0e-3,
        derivative_relative_tolerance = 1.0e-7,
    )
end

function d3_forward_two_pi_feedline(feedline, feedline_length_m)
    length_m = d3_forward_positive(feedline_length_m, "D3 feedline length")
    half = length_m / 2
    return (
        capacitance_f = feedline.c_per_m_f * half,
        inductance_h = feedline.l_per_m_h * half,
        half_length_m = half,
    )
end

function d3_forward_isolated_filter_matrices(elements, feedline, feedline_length_m, cext_f)
    cext = d3_forward_positive(cext_f, "D3 Cext")
    line = d3_forward_two_pi_feedline(feedline, feedline_length_m)
    capacitance = zeros(Float64, 4, 4)
    inverse_inductance = zeros(Float64, 4, 4)
    # Coupling-Off removes only the r-p off-diagonal bridge stamps.  Its
    # diagonal Cn/Ln loading remains part of the loaded-bare filter estimator.
    capacitance[1, 1] = elements.Cp_f + elements.Cn_f + cext
    capacitance[1, 3] = capacitance[3, 1] = -cext
    capacitance[2, 2] = line.capacitance_f / 2
    capacitance[3, 3] = cext + line.capacitance_f
    capacitance[4, 4] = line.capacitance_f / 2
    inverse_inductance[1, 1] = 1 / elements.Lp_h + 1 / elements.Ln_h
    for (left, right) in ((2, 3), (3, 4))
        inverse_inductance[left, left] += 1 / line.inductance_h
        inverse_inductance[right, right] += 1 / line.inductance_h
        inverse_inductance[left, right] -= 1 / line.inductance_h
        inverse_inductance[right, left] -= 1 / line.inductance_h
    end
    selector = zeros(Float64, 4, 2)
    selector[2, 1] = 1
    selector[4, 2] = 1
    return (capacitance = capacitance, inverse_inductance = inverse_inductance, selector = selector)
end

function d3_forward_filter_open_pole(elements, feedline, feedline_length_m, cext_f; target_hz)
    matrices = d3_forward_isolated_filter_matrices(
        elements, feedline, feedline_length_m, cext_f,
    )
    poles = matched_open_poles(
        matrices.capacitance,
        matrices.inverse_inductance,
        matrices.selector,
        feedline.target_impedance_ohm,
    )
    candidates = [
        index for index in eachindex(poles.frequencies_hz)
        if abs(real(poles.frequencies_hz[index]) - Float64(target_hz)) <= 0.75e9
    ]
    length(candidates) == 1 || error(
        "Isolated response-matched filter must have exactly one open pole in its declared window; " *
        "found $(length(candidates)) at $([real(poles.frequencies_hz[index]) for index in candidates]) Hz; " *
        "all positive pole frequencies are $(real.(poles.frequencies_hz)) Hz; " *
        "target=$(Float64(target_hz)) Hz and parallel-LC frequency=" *
        "$(1 / (2π * sqrt(elements.Lp_h * elements.Cp_f))) Hz.",
    )
    index = only(candidates)
    return (
        frequency_hz = poles.frequencies_hz[index],
        linewidth_hz = poles.linewidths_hz[index],
        hashes = poles.hashes,
    )
end

function d3_forward_tune_cext(elements, feedline, feedline_length_m; target_frequency_hz, target_kappa_hz)
    evaluations = Dict{String,Any}[]
    function objective(cext_f)
        pole = d3_forward_filter_open_pole(
            elements,
            feedline,
            feedline_length_m,
            cext_f;
            target_hz = target_frequency_hz,
        )
        push!(evaluations, Dict(
            "cext_f" => Float64(cext_f),
            "pole_frequency_real_hz" => real(pole.frequency_hz),
            "pole_frequency_imag_hz" => imag(pole.frequency_hz),
            "kappa_hz" => pole.linewidth_hz,
            "normalized_cost" => ((pole.linewidth_hz - target_kappa_hz) /
                D3_FORWARD_AGENT_SCALES_HZ.kappa)^2,
        ))
        return pole.linewidth_hz - target_kappa_hz
    end
    scan_fF = Float64[0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200]
    scan_f = scan_fF .* 1.0e-15
    lower_f = first(scan_f)
    lower_residual = objective(lower_f)
    bracket = nothing
    for upper_f in scan_f[2:end]
        upper_residual = objective(upper_f)
        if iszero(lower_residual) || signbit(lower_residual) != signbit(upper_residual)
            bracket = (lower_f, upper_f)
            break
        end
        lower_f = upper_f
        lower_residual = upper_residual
    end
    isnothing(bracket) && error(
        "Forward Cext scan did not bracket the requested filter linewidth.",
    )
    cext_f = bracketed_bisection(
        objective,
        something(bracket);
        absolute_tolerance = 1.0e-21,
        relative_tolerance = 1.0e-6,
        max_iterations = 80,
    )
    selected = d3_forward_filter_open_pole(
        elements,
        feedline,
        feedline_length_m,
        cext_f;
        target_hz = target_frequency_hz,
    )
    return (
        cext_f = cext_f,
        kappa_hz = selected.linewidth_hz,
        pole = selected,
        evidence = Dict(
            "contract_id" => "d3-forward-coupling-off-diagonal-loaded-filter-two-pi-kappa-v2",
            "method" => "forward_only_open_pole_log_scan_plus_bracketed_bisection",
            "reduction_role" => "coupling_off_estimator_with_bridge_diagonal_loading_retained",
            "target_kappa_hz" => Float64(target_kappa_hz),
            "target_frequency_hz" => Float64(target_frequency_hz),
            "bracket_f" => collect(something(bracket)),
            "selected_cext_f" => cext_f,
            "selected_pole" => Dict(
                "frequency_real_hz" => real(selected.frequency_hz),
                "frequency_imag_hz" => imag(selected.frequency_hz),
                "linewidth_hz" => selected.linewidth_hz,
            ),
            "open_pole_hashes" => Dict(String(name) => value for (name, value) in pairs(selected.hashes)),
            "evaluations" => evaluations,
        ),
    )
end

function d3_forward_full_coordinate_matrices(
    elements,
    floating_qubit_nominal,
    feedline,
    feedline_length_m,
    cext_f,
)
    cext = d3_forward_positive(cext_f, "D3 Cext")
    layers = floating_qubit_capacitance_layers(floating_qubit_nominal)
    line = d3_forward_two_pi_feedline(feedline, feedline_length_m)
    capacitance = zeros(Float64, 6, 6)
    inverse_inductance = zeros(Float64, 6, 6)
    capacitance[1, 1] = layers.Cq_LB_fF * D3_FARADS_PER_FF
    capacitance[1, 2] = capacitance[2, 1] =
        layers.Cdr_physical_fF * D3_FARADS_PER_FF
    capacitance[2, 2] = elements.Cr_f +
        layers.Cr_attach_LB_fF * D3_FARADS_PER_FF + elements.Cn_f
    capacitance[2, 3] = capacitance[3, 2] = -elements.Cn_f
    capacitance[3, 3] = elements.Cp_f + elements.Cn_f + cext
    capacitance[3, 5] = capacitance[5, 3] = -cext
    capacitance[4, 4] = line.capacitance_f / 2
    capacitance[5, 5] = cext + line.capacitance_f
    capacitance[6, 6] = line.capacitance_f / 2

    equivalent_qubit_inductance_h =
        floating_qubit_nominal.L_J_per_junction_nH * D3_HENRIES_PER_NH / 2
    inverse_inductance[1, 1] = 1 / equivalent_qubit_inductance_h
    inverse_inductance[2, 2] = 1 / elements.Lr_h + 1 / elements.Ln_h
    inverse_inductance[2, 3] = inverse_inductance[3, 2] = -1 / elements.Ln_h
    inverse_inductance[3, 3] = 1 / elements.Lp_h + 1 / elements.Ln_h
    for (left, right) in ((4, 5), (5, 6))
        inverse_inductance[left, left] += 1 / line.inductance_h
        inverse_inductance[right, right] += 1 / line.inductance_h
        inverse_inductance[left, right] -= 1 / line.inductance_h
        inverse_inductance[right, left] -= 1 / line.inductance_h
    end
    return (capacitance = capacitance, inverse_inductance = inverse_inductance)
end

"""Evaluate the canonical matched-port response of the physical six-coordinate model."""
function d3_forward_exact_six_trace(
    elements,
    floating_qubit_nominal,
    feedline,
    feedline_length_m,
    cext_f,
    frequency_grid_hz,
)
    matrices = d3_forward_full_coordinate_matrices(
        elements,
        floating_qubit_nominal,
        feedline,
        feedline_length_m,
        cext_f,
    )
    frequencies = Float64.(collect(frequency_grid_hz))
    length(frequencies) >= 2 && all(isfinite, frequencies) && all(>(0), frequencies) &&
        all(diff(frequencies) .> 0) || error(
        "D3 exact-six frequency grid must be finite, positive, and strictly increasing.",
    )
    selector = zeros(Float64, 6, 2)
    selector[4, 1] = 1.0
    selector[6, 2] = 1.0
    z0 = _d3_forward_reference_impedance(feedline)
    s21 = ComplexF64[
        matched_port_response(
            matrices.capacitance,
            matrices.inverse_inductance,
            2π * frequency,
            selector,
            z0,
        ).scattering[2, 1]
        for frequency in frequencies
    ]
    poles = matched_open_poles(
        matrices.capacitance,
        matrices.inverse_inductance,
        selector,
        z0,
    )
    length(poles.frequencies_hz) == 5 || error(
        "D3 exact-six response must have five positive open poles and one free coordinate.",
    )
    matrix_hash = SuperconductingCircuitsCore._linear_matrix_sha256
    return (
        contract_id = D3_FORWARD_EXACT_SIX_RESPONSE_CONTRACT,
        coordinate_order = ["q", "r", "p", "f1", "fc", "f2"],
        frequency_hz = frequencies,
        s21 = s21,
        poles = poles,
        capacitance = matrices.capacitance,
        inverse_inductance = matrices.inverse_inductance,
        selector = selector,
        reference_impedance_ohm = z0,
        hashes = (
            capacitance_sha256 = matrix_hash(
                "d3-full-coordinate-capacitance-f", matrices.capacitance,
            ),
            inverse_inductance_sha256 = matrix_hash(
                "d3-full-coordinate-inverse-inductance-h^-1",
                matrices.inverse_inductance,
            ),
            selector_sha256 = matrix_hash("d3-exact-six-port-selector", selector),
            open_pole_state_matrix_sha256 = poles.hashes.state_matrix_sha256,
        ),
    )
end

function d3_forward_positive_generalized_frequencies(capacitance, inverse_inductance)
    values = eigvals(Symmetric(inverse_inductance), Symmetric(capacitance))
    scale = max(maximum(abs, values), floatmin(Float64))
    tolerance = 1024 * length(values) * eps(Float64) * scale
    minimum(values) >= -tolerance || error("D3 full-coordinate K/C spectrum is not passive.")
    positive = sort(Float64[value for value in values if value > tolerance])
    length(positive) == 5 || error(
        "D3 two-pi full coordinate must have five positive modes and one free feedline coordinate.",
    )
    return sqrt.(positive) ./ (2π)
end

function d3_forward_bdg_frequencies(number_conserving, pairing)
    dimension = size(number_conserving, 1)
    charge_block = Symmetric(number_conserving - pairing)
    flux_block = Symmetric(number_conserving + pairing)
    charge_factor = cholesky(charge_block).L
    squared = eigvals(Symmetric(transpose(charge_factor) * flux_block * charge_factor))
    scale = max(maximum(abs, squared), floatmin(Float64))
    tolerance = 4096 * dimension * eps(Float64) * scale
    minimum(squared) >= -tolerance || error(
        "D3 doubled oscillator squared spectrum is not positive semidefinite.",
    )
    count(value -> abs(value) <= tolerance, squared) == 1 || error(
        "D3 doubled oscillator spectrum must contain exactly one free coordinate.",
    )
    positive = sort(Float64[value for value in squared if value > tolerance])
    length(positive) == 5 || error(
        "D3 doubled oscillator model must reproduce five positive modes and one free coordinate.",
    )
    return sqrt.(positive) ./ (2π)
end

function d3_forward_match_rwa_subset(rwa_hz, exact_hz)
    rwa = sort(Float64.(collect(rwa_hz)))
    exact = sort(Float64.(collect(exact_hz)))
    length(rwa) == length(exact) + 1 || error(
        "D3 RWA/free-coordinate comparison expects one extra positive local oscillator.",
    )
    candidates = [rwa[[index for index in eachindex(rwa) if index != dropped]] for dropped in eachindex(rwa)]
    scores = [sum(abs2, candidate .- exact) for candidate in candidates]
    return candidates[argmin(scores)]
end

function d3_forward_full_coordinate_handoff(
    elements,
    floating_qubit_nominal,
    feedline,
    feedline_length_m,
    cext_f,
)
    matrices = d3_forward_full_coordinate_matrices(
        elements,
        floating_qubit_nominal,
        feedline,
        feedline_length_m,
        cext_f,
    )
    capacitance = matrices.capacitance
    inverse_inductance = matrices.inverse_inductance
    isposdef(Symmetric(capacitance)) || error("D3 full-coordinate capacitance must be positive definite.")
    stiffness_eigenvalues = eigvals(Symmetric(inverse_inductance))
    stiffness_tolerance = 1024 * eps(Float64) * maximum(abs, stiffness_eigenvalues)
    minimum(stiffness_eigenvalues) >= -stiffness_tolerance || error(
        "D3 full-coordinate inverse inductance must be positive semidefinite.",
    )
    inverse_capacitance = capacitance \ Matrix{Float64}(I, 6, 6)
    impedance = sqrt.(diag(inverse_capacitance) ./ diag(inverse_inductance))
    all(value -> isfinite(value) && value > 0, impedance) || error(
        "D3 full-coordinate local oscillator impedances must be finite and positive.",
    )
    sqrt_impedance = Diagonal(sqrt.(impedance))
    inverse_sqrt_impedance = Diagonal(1 ./ sqrt.(impedance))
    charge_block = inverse_sqrt_impedance * inverse_capacitance * inverse_sqrt_impedance
    flux_block = sqrt_impedance * inverse_inductance * sqrt_impedance
    number_conserving = Matrix{Float64}((charge_block + flux_block) / 2)
    pairing = Matrix{Float64}((-charge_block + flux_block) / 2)
    isapprox(number_conserving, transpose(number_conserving); rtol = 1e-12, atol = 0) || error(
        "D3 full-coordinate number-conserving matrix must be symmetric.",
    )
    isapprox(pairing, transpose(pairing); rtol = 1e-12, atol = 0) || error(
        "D3 full-coordinate pairing matrix must be symmetric.",
    )

    qrp_gauge = _d3_forward_gauge(
        number_conserving[1:3, 1:3] ./ (2π),
        pairing[1:3, 1:3] ./ (2π),
    )
    full_gauge_signs = vcat(qrp_gauge.signs, ones(Float64, 3))
    gauge = Diagonal(full_gauge_signs)
    number_conserving = Matrix{Float64}(gauge * number_conserving * gauge)
    pairing = Matrix{Float64}(gauge * pairing * gauge)

    reconstructed_inverse_capacitance = sqrt_impedance *
        (number_conserving - pairing) * sqrt_impedance
    reconstructed_inverse_inductance = inverse_sqrt_impedance *
        (number_conserving + pairing) * inverse_sqrt_impedance
    inverse_capacitance_residual = maximum(abs,
        reconstructed_inverse_capacitance - gauge * inverse_capacitance * gauge)
    inverse_inductance_residual = maximum(abs,
        reconstructed_inverse_inductance - gauge * inverse_inductance * gauge)
    inverse_capacitance_residual <= 1e-11 * maximum(abs, inverse_capacitance) || error(
        "D3 oscillator reconstruction failed for the full inverse capacitance.",
    )
    inverse_inductance_residual <= 1e-11 * maximum(abs, inverse_inductance) || error(
        "D3 oscillator reconstruction failed for the full inverse inductance.",
    )

    exact_hz = d3_forward_positive_generalized_frequencies(capacitance, inverse_inductance)
    bdg_hz = d3_forward_bdg_frequencies(number_conserving, pairing)
    rwa_hz = eigvals(Symmetric(number_conserving)) ./ (2π)
    matched_rwa_hz = d3_forward_match_rwa_subset(rwa_hz, exact_hz)
    max_abs_bdg_residual_hz = maximum(abs, bdg_hz .- exact_hz)
    max_abs_rwa_residual_hz = maximum(abs, matched_rwa_hz .- exact_hz)
    max_abs_rwa_minus_bdg_hz = maximum(abs, matched_rwa_hz .- bdg_hz)
    max_abs_bdg_residual_hz <= 1e-5 * maximum(exact_hz) || error(
        "D3 doubled-BdG and flux spectra do not close.",
    )

    full_hz = number_conserving ./ (2π)
    full_pairing_hz = pairing ./ (2π)
    qrp_hz = full_hz[1:3, 1:3]
    qrp_pairing_hz = full_pairing_hz[1:3, 1:3]
    matrix_hash = SuperconductingCircuitsCore._linear_matrix_sha256
    return Dict{String,Any}(
        "contract_id" => D3_FORWARD_FULL_COORDINATE_CONTRACT,
        "basis" => "response_matched_two_pi_full_capacitance_inverse",
        "full_mode_order" => ["q", "r", "p", "f1", "fc", "f2"],
        "qrp_mode_order" => ["q", "r", "p"],
        "gauge_convention" => "q_fixed__g_qr_nonnegative__j_rp_nonnegative",
        "gauge_signs" => Int.(full_gauge_signs),
        "feedline_inclusion" => "cext_and_two_pi_feedline_included_before_full_capacitance_inverse",
        "cext_stamp_count" => 1,
        "cext_stamp_provenance" => "cext_included_once_in_full_coordinate_capacitance_before_inverse",
        "fq_hz" => qrp_hz[1, 1],
        "fr_hz" => qrp_hz[2, 2],
        "fp_hz" => qrp_hz[3, 3],
        "g_hz" => qrp_hz[1, 2],
        "g_qp_signed_hz" => qrp_hz[1, 3],
        "J_hz" => qrp_hz[2, 3],
        "qrp_number_conserving_matrix_hz" => [collect(row) for row in eachrow(qrp_hz)],
        "qrp_pairing_matrix_hz" => [collect(row) for row in eachrow(qrp_pairing_hz)],
        "full_number_conserving_matrix_hz" => [collect(row) for row in eachrow(full_hz)],
        "full_pairing_matrix_hz" => [collect(row) for row in eachrow(full_pairing_hz)],
        "full_coordinate_hashes" => Dict(
            "capacitance_sha256" => matrix_hash("d3-full-coordinate-capacitance-f", capacitance),
            "inverse_inductance_sha256" => matrix_hash(
                "d3-full-coordinate-inverse-inductance-h^-1", inverse_inductance,
            ),
            "number_conserving_matrix_sha256" => matrix_hash(
                "d3-full-coordinate-number-conserving-rad-s", number_conserving,
            ),
            "pairing_matrix_sha256" => matrix_hash(
                "d3-full-coordinate-pairing-rad-s", pairing,
            ),
        ),
        "projection_closure" => Dict(
            "max_abs_bdg_residual_hz" => max_abs_bdg_residual_hz,
            "max_abs_rwa_residual_hz" => max_abs_rwa_residual_hz,
            "max_abs_rwa_minus_bdg_hz" => max_abs_rwa_minus_bdg_hz,
        ),
    )
end

function d3_forward_cost(metrics, target; scales = D3_FORWARD_AGENT_SCALES_HZ)
    residuals = (
        fr = (metrics.fr_hz - target.fr_hz) / scales.fr,
        fp = (metrics.fp_hz - target.fp_hz) / scales.fp,
        notch = (metrics.notch_hz - target.notch_hz) / scales.notch,
        g = (metrics.g_hz - target.g_hz) / scales.g,
        J = (metrics.J_hz - target.J_hz) / scales.J,
        kappa = (metrics.kappa_hz - target.kappa_hz) / scales.kappa,
    )
    return (cost = sum(abs2, values(residuals)), normalized_residuals = residuals)
end

function d3_forward_candidate_metrics(handoff, matching, kappa_hz)
    return (
        fq_hz = Float64(handoff["fq_hz"]),
        fr_hz = Float64(handoff["fr_hz"]),
        fp_hz = Float64(handoff["fp_hz"]),
        g_hz = Float64(handoff["g_hz"]),
        g_qp_signed_hz = Float64(handoff["g_qp_signed_hz"]),
        J_hz = Float64(handoff["J_hz"]),
        notch_hz = Float64(matching.roots.notch.frequency_hz),
        kappa_hz = Float64(kappa_hz),
    )
end

function d3_forward_evaluate_candidate(
    case,
    design,
    target;
    section_length_m,
    floating_qubit_nominal,
    feedline,
    feedline_length_m,
)
    settings = d3_forward_match_settings(target)
    matching = _d3_forward_match_elements(
        case,
        design;
        section_length_m = section_length_m,
        settings...,
    )
    kappa = d3_forward_tune_cext(
        matching.elements,
        feedline,
        feedline_length_m;
        target_frequency_hz = matching.roots.filter.frequency_hz,
        target_kappa_hz = target.kappa_hz,
    )
    handoff = d3_forward_full_coordinate_handoff(
        matching.elements,
        floating_qubit_nominal,
        feedline,
        feedline_length_m,
        kappa.cext_f,
    )
    metrics = d3_forward_candidate_metrics(handoff, matching, kappa.kappa_hz)
    objective = d3_forward_cost(metrics, target)
    return (
        design = design,
        matching = matching,
        kappa = kappa,
        handoff = handoff,
        metrics = metrics,
        cost = objective.cost,
        normalized_residuals = objective.normalized_residuals,
    )
end

function d3_forward_design_record(design)
    return Dict(
        "lr_open_um" => design.lr_open_um,
        "lr_short_um" => design.lr_short_um,
        "lc_um" => design.lc_um,
        "lp_short_um" => design.lp_short_um,
        "lp_open_um" => design.lp_open_um,
        "lr_total_um" => design.lr_total_um,
        "lp_total_um" => design.lp_total_um,
        "notch_path_um" => design.notch_path_um,
    )
end

function d3_forward_evaluation_record(result; iteration)
    return Dict(
        "iteration" => Int(iteration),
        "status" => "complete",
        "design" => d3_forward_design_record(result.design),
        "cext_f" => result.kappa.cext_f,
        "cost" => result.cost,
        "normalized_residuals" => Dict(
            String(name) => value for (name, value) in pairs(result.normalized_residuals)
        ),
        "metrics" => Dict(String(name) => value for (name, value) in pairs(result.metrics)),
        "response_match" => Dict(
            "Cr_f" => result.matching.elements.Cr_f,
            "Lr_h" => result.matching.elements.Lr_h,
            "Cp_f" => result.matching.elements.Cp_f,
            "Lp_h" => result.matching.elements.Lp_h,
            "Cn_f" => result.matching.elements.Cn_f,
            "Ln_h" => result.matching.elements.Ln_h,
            "readout_root_hz" => result.matching.roots.readout.frequency_hz,
            "filter_root_hz" => result.matching.roots.filter.frequency_hz,
            "notch_root_hz" => result.matching.roots.notch.frequency_hz,
        ),
        "kappa_search" => result.kappa.evidence,
    )
end

function d3_forward_next_design(design, metrics, target, initial; iteration)
    maximum_step = 0.15
    bounded_factor(value) = clamp(Float64(value), 1 - maximum_step, 1 + maximum_step)
    new_lc = design.lc_um * bounded_factor(target.J_hz / metrics.J_hz)
    desired_path = design.notch_path_um * bounded_factor(metrics.notch_hz / target.notch_hz)
    remaining_short = desired_path - new_lc
    remaining_short > 0 || error("D3 bounded update leaves a nonpositive short path.")
    split = design.lr_short_um / (design.lr_short_um + design.lp_short_um)
    lr_short = split * remaining_short
    lp_short = (1 - split) * remaining_short
    desired_lr_total = design.lr_total_um * bounded_factor(metrics.fr_hz / target.fr_hz)
    desired_lp_total = design.lp_total_um * bounded_factor(metrics.fp_hz / target.fp_hz)
    candidate = d3_forward_design(
        id = "$(design.id)_iteration_$(iteration)",
        lr_open_um = desired_lr_total - lr_short - new_lc,
        lr_short_um = lr_short,
        lc_um = new_lc,
        lp_short_um = lp_short,
        lp_open_um = desired_lp_total - lp_short - new_lc,
    )
    for field in (:lr_open_um, :lr_short_um, :lc_um, :lp_short_um, :lp_open_um)
        value = getproperty(candidate, field)
        baseline = getproperty(initial, field)
        0.45 * baseline <= value <= 1.8 * baseline || error(
            "D3 bounded physical update exceeded the declared 0.45x--1.8x seed envelope.",
        )
    end
    return candidate
end

function d3_forward_bounded_search(
    initial,
    target,
    evaluate;
    max_iterations = 4,
)
    iterations = Int(max_iterations)
    iterations >= 0 || error("D3 bounded search max_iterations must be nonnegative.")
    history = Dict{String,Any}[]
    results = Any[]
    design = initial
    for iteration in 0:iterations
        result = evaluate(design)
        push!(results, result)
        push!(history, d3_forward_evaluation_record(result; iteration = iteration))
        iteration == iterations && break
        design = d3_forward_next_design(
            design,
            result.metrics,
            target,
            initial;
            iteration = iteration + 1,
        )
    end
    best_index = argmin([result.cost for result in results])
    return (
        best = results[best_index],
        history = history,
        best_iteration = best_index - 1,
        policy = Dict(
            "method" => "bounded_physical_fixed_point_search",
            "maximum_fractional_step" => 0.15,
            "seed_relative_bounds" => [0.45, 1.8],
            "max_iterations" => iterations,
            "bare_parameter_fit" => false,
            "s21_fit" => false,
        ),
    )
end

function d3_forward_case_record(case)
    return Dict(
        "case_id" => String(case.id),
        "pair_case_id" => case.pair_case_id,
        "single_case_id" => case.single_case_id,
        "inter_trace_ground_width_um" => case.inter_trace_ground_width_um,
        "upper_ground_clearance_width_um" => case.upper_ground_clearance_width_um,
        "trace_width_um" => case.trace_width_um,
        "trace_gap_um" => case.trace_gap_um,
        "q2d_route" => D3_FORWARD_Q2D_ROUTE,
    )
end

function d3_forward_screen_cases(
    cases,
    initializer,
    target;
    floating_qubit_nominal,
    feedline,
    feedline_length_m,
    section_length_m = 80.0e-6,
)
    case_results = Dict{String,Any}[]
    eligible = Any[]
    for case in cases
        @info "Screening public Q2D case" case_id = String(case.id)
        slot_rows = Dict{String,Any}[]
        case_cost = 0.0
        complete = true
        for slot_hz in target.slot_hz
            slot_target = d3_forward_target_for_slot(target, slot_hz)
            record = d3_forward_with_source_velocity(
                initializer.by_slot[slot_hz], initializer.source_velocity_m_per_s,
            )
            design = d3_forward_design_from_initializer(
                record,
                case;
                guided = true,
                id = "screen_$(case.id)_$(round(Int, slot_hz))",
            )
            try
                result = d3_forward_evaluate_candidate(
                    case,
                    design,
                    slot_target;
                    section_length_m = section_length_m,
                    floating_qubit_nominal = floating_qubit_nominal,
                    feedline = feedline,
                    feedline_length_m = feedline_length_m,
                )
                case_cost += result.cost
                push!(slot_rows, merge(
                    d3_forward_evaluation_record(result; iteration = 0),
                    Dict("slot_hz" => slot_hz),
                ))
            catch exception
                complete = false
                case_cost += 1.0e30
                push!(slot_rows, Dict(
                    "slot_hz" => slot_hz,
                    "status" => "rejected",
                    "rejected_gate" => "forward_candidate_evaluation_failed",
                    "error_type" => string(typeof(exception)),
                    "design" => d3_forward_design_record(design),
                    "cost" => 1.0e30,
                ))
            end
        end
        aggregate = case_cost / length(target.slot_hz)
        row = Dict(
            "public_q2d_case" => d3_forward_case_record(case),
            "section_length_m" => Float64(section_length_m),
            "slot_evaluations" => slot_rows,
            "aggregate_normalized_cost" => aggregate,
            "status" => complete ? "complete" : "rejected",
        )
        push!(case_results, row)
        complete && push!(eligible, (case = case, cost = aggregate))
    end
    length(case_results) == 9 || error("D3 public-Q2D screening must attempt exactly nine cases.")
    length(eligible) == length(case_results) || error(
        "Every public Q2D case must complete all five finite forward screening slots.",
    )
    selected = eligible[argmin([entry.cost for entry in eligible])]
    return (
        selected_case = selected.case,
        selected_cost = selected.cost,
        evidence = Dict(
            "method" => "global_minimum_mean_five_slot_normalized_forward_cost",
            "case_count" => length(case_results),
            "slot_count_per_case" => 5,
            "selected_case_id" => String(selected.case.id),
            "selected_aggregate_normalized_cost" => selected.cost,
            "cases" => case_results,
        ),
    )
end

function d3_forward_frequency_grid(slot_hz; fine)
    slot = Float64(slot_hz)
    overview_step = fine ? 25.0e6 : 50.0e6
    notch_step = fine ? 2.5e6 : 5.0e6
    slot_step = fine ? 2.5e6 : 5.0e6
    values = vcat(
        collect(4.25e9:overview_step:(slot + 0.25e9)),
        collect(4.5e9 - 50.0e6:notch_step:4.5e9 + 50.0e6),
        collect(slot - 100.0e6:slot_step:slot + 100.0e6),
    )
    return sort!(unique(Float64.(round.(Int, values))))
end

function d3_forward_in_band_poles(poles, target)
    lower_hz = min(target.fq_hz, target.fr_hz, target.fp_hz) - 0.35e9
    upper_hz = max(target.fq_hz, target.fr_hz, target.fp_hz) + 0.35e9
    rows = [
        (
            source_index = index - 1,
            frequency_hz = real(poles.frequencies_hz[index]),
            imaginary_frequency_hz = min(imag(poles.frequencies_hz[index]), 0.0),
            linewidth_hz = max(poles.linewidths_hz[index], 0.0),
        )
        for index in eachindex(poles.frequencies_hz)
        if lower_hz <= real(poles.frequencies_hz[index]) <= upper_hz
    ]
    sort!(rows; by = row -> row.frequency_hz)
    length(rows) == 3 || error(
        "D3 preliminary distributed solve must identify exactly three in-band q/r/p open poles; " *
        "found $(length(rows)) in [$(lower_hz), $(upper_hz)] Hz.",
    )
    return rows
end

function d3_forward_ordinary_closure_metrics(trace, frequency_hz)
    frequency = Float64(frequency_hz)
    isfinite(frequency) && frequency > 0 || error(
        "D3 ordinary closure frequency must be finite and positive.",
    )
    angular_frequency = 2π * frequency
    z0 = Float64(trace.reference_plane.reference_impedance_ohm)
    matched = matched_port_response(
        trace.model.capacitance,
        trace.model.inverse_inductance,
        angular_frequency,
        trace.selector,
        z0,
    )
    closed = linear_terminal_response(
        trace.model.capacitance,
        trace.model.inverse_inductance,
        angular_frequency,
        trace.terminal_indices,
    )
    z_from_s = scattering_to_impedance(matched.scattering, z0)
    s_from_z = impedance_to_scattering(closed.impedance, z0)
    z_residual = maximum(abs, z_from_s - closed.impedance)
    s_residual = maximum(abs, matched.scattering - s_from_z)
    z_scale = max(
        maximum(abs, z_from_s),
        maximum(abs, closed.impedance),
        floatmin(Float64),
    )
    s_scale = max(
        maximum(abs, matched.scattering),
        maximum(abs, s_from_z),
        floatmin(Float64),
    )
    z_tolerance = D3_FORWARD_Z_CLOSURE_ABSOLUTE_TOLERANCE_OHM +
        D3_FORWARD_CLOSURE_RELATIVE_TOLERANCE * z_scale
    s_tolerance = D3_FORWARD_S_CLOSURE_ABSOLUTE_TOLERANCE +
        D3_FORWARD_CLOSURE_RELATIVE_TOLERANCE * s_scale
    z_ratio = z_residual / z_tolerance
    s_ratio = s_residual / s_tolerance
    return (
        z_from_s_residual_ohm = z_residual,
        z_from_s_tolerance_ohm = z_tolerance,
        z_from_s_normalized_closure_ratio = z_ratio,
        s_from_z_residual = s_residual,
        s_from_z_tolerance = s_tolerance,
        s_from_z_normalized_closure_ratio = s_ratio,
        max_normalized_closure_ratio = max(z_ratio, s_ratio),
    )
end

function d3_forward_closed_pole_group(trace; model_role, section_length_m)
    role = String(model_role)
    role in ("distributed", "equivalent", "feedline_reference") || error(
        "D3 closed-pole model role is unsupported.",
    )
    section = Float64(section_length_m)
    isfinite(section) && section > 0 || error(
        "D3 closed-pole section length must be finite and positive.",
    )
    reduced = reduce_free_charge_coordinates(trace.model)
    modes = solve_generalized_modes(reduced)
    return (
        model_role = role,
        section_length_m = section,
        frequencies_hz = copy(modes.frequencies_hz),
        residuals = copy(modes.residuals),
        closure_evaluator = (_, boundary_frequency_hz) ->
            d3_forward_ordinary_closure_metrics(trace, boundary_frequency_hz),
        hashes = (
            source_sha256 = trace.model.source_sha256,
            node_order_sha256 = trace.model.node_order_sha256,
            capacitance_sha256 = trace.model.capacitance_sha256,
            inverse_inductance_sha256 = trace.model.inverse_inductance_sha256,
            reduced_capacitance_sha256 = reduced.capacitance_sha256,
            reduced_inverse_inductance_sha256 = reduced.inverse_inductance_sha256,
        ),
    )
end

function _d3_forward_closed_boundary_attempt(
    closure_evaluator,
    pole_frequency_hz,
    boundary_frequency_hz,
)
    try
        metrics = closure_evaluator(pole_frequency_hz, boundary_frequency_hz)
        ratio = Float64(metrics.max_normalized_closure_ratio)
        if isfinite(ratio) && ratio >= 0
            return (normalized_closure_ratio = ratio, failure = nothing)
        end
        return (
            normalized_closure_ratio = Inf,
            failure = "non-finite or negative normalized closure ratio $(ratio)",
        )
    catch exception
        return (
            normalized_closure_ratio = Inf,
            failure = sprint(showerror, exception),
        )
    end
end

function _d3_forward_adaptive_closed_pole_exclusion(group, source_index, pole_frequency_hz)
    hasproperty(group, :closure_evaluator) || error(
        "D3 closed-pole group must provide an ordinary-closure evaluator.",
    )
    last_negative = nothing
    last_positive = nothing
    last_half_width_hz = D3_FORWARD_GRID_LINEWIDTH_FLOOR_HZ
    for scale_steps in 0:D3_FORWARD_CLOSED_POLE_MAX_EXCLUSION_SCALE_STEPS
        half_width_hz = D3_FORWARD_GRID_LINEWIDTH_FLOOR_HZ * (2.0 ^ scale_steps)
        boundaries = _d3_forward_outward_symmetric_boundaries(
            pole_frequency_hz,
            half_width_hz,
        )
        negative = _d3_forward_closed_boundary_attempt(
            group.closure_evaluator,
            pole_frequency_hz,
            boundaries[1],
        )
        positive = _d3_forward_closed_boundary_attempt(
            group.closure_evaluator,
            pole_frequency_hz,
            boundaries[2],
        )
        if negative.normalized_closure_ratio <= 1.0 &&
            positive.normalized_closure_ratio <= 1.0
            return (
                exclusion_half_width_hz = half_width_hz,
                exclusion_scale_steps = scale_steps,
                boundaries = boundaries,
                negative_boundary_max_normalized_closure_ratio =
                    negative.normalized_closure_ratio,
                positive_boundary_max_normalized_closure_ratio =
                    positive.normalized_closure_ratio,
            )
        end
        last_negative = negative
        last_positive = positive
        last_half_width_hz = half_width_hz
    end
    error(
        "D3 closed-pole ordinary closure did not pass at both symmetric boundaries " *
        "through the finite adaptive exclusion limit: model_role=$(group.model_role), " *
        "section_length_m=$(group.section_length_m), source_index=$(source_index), " *
        "pole_frequency_hz=$(pole_frequency_hz), maximum_half_width_hz=$(last_half_width_hz), " *
        "negative_ratio=$(last_negative.normalized_closure_ratio), " *
        "positive_ratio=$(last_positive.normalized_closure_ratio), " *
        "negative_failure=$(last_negative.failure), positive_failure=$(last_positive.failure).",
    )
end

function _d3_forward_outward_symmetric_boundaries(center_hz, half_width_hz)
    center = Float64(center_hz)
    half_width = Float64(half_width_hz)
    lower = center - half_width
    upper = center + half_width
    center - lower >= half_width || (lower = prevfloat(lower))
    upper - center >= half_width || (upper = nextfloat(upper))
    return Float64[lower, upper]
end

function d3_forward_pole_aware_frequency_grid(
    slot_hz,
    pole_rows;
    fine,
    closed_pole_groups = (),
)
    length(pole_rows) == 3 || error("D3 pole-aware grid requires exactly three q/r/p poles.")
    requested_samples_per_linewidth = fine ?
        D3_FORWARD_FINE_SAMPLES_PER_LINEWIDTH :
        D3_FORWARD_COARSE_SAMPLES_PER_LINEWIDTH
    maximum_intervals = fine ?
        D3_FORWARD_FINE_MAXIMUM_LOCAL_INTERVALS :
        D3_FORWARD_COARSE_MAXIMUM_LOCAL_INTERVALS
    frequency_hz = d3_forward_frequency_grid(slot_hz; fine = fine)
    open_plans = Any[]
    protected_centers = Tuple{Float64,Float64}[]
    for pole in pole_rows
        linewidth_hz = max(Float64(pole.linewidth_hz), 0.0)
        pole_frequency_hz = Float64(pole.frequency_hz)
        below_linewidth_floor = linewidth_hz < D3_FORWARD_GRID_LINEWIDTH_FLOOR_HZ
        effective_linewidth_hz = max(linewidth_hz, D3_FORWARD_GRID_LINEWIDTH_FLOOR_HZ)
        half_width_hz = clamp(
            D3_FORWARD_LOCAL_HALF_WIDTHS * effective_linewidth_hz,
            D3_FORWARD_LOCAL_MINIMUM_HALF_WIDTH_HZ,
            D3_FORWARD_LOCAL_MAXIMUM_HALF_WIDTH_HZ,
        )
        desired_step_hz = effective_linewidth_hz / requested_samples_per_linewidth
        half_intervals = clamp(
            ceil(Int, half_width_hz / desired_step_hz),
            1,
            maximum_intervals ÷ 2,
        )
        planned_local_step_hz = half_width_hz / half_intervals
        local_grid = if below_linewidth_floor
            Float64[
                pole_frequency_hz + (offset + 0.5) * planned_local_step_hz
                for offset in -half_intervals:(half_intervals - 1)
            ]
        else
            Float64[
                pole_frequency_hz + offset * planned_local_step_hz
                for offset in -half_intervals:half_intervals
            ]
        end
        if below_linewidth_floor
            push!(
                protected_centers,
                (pole_frequency_hz, minimum(abs.(local_grid .- pole_frequency_hz))),
            )
        end
        append!(frequency_hz, local_grid)
        push!(open_plans, (
            source_index = pole.source_index,
            pole_frequency_hz = pole_frequency_hz,
            pole_linewidth_hz = linewidth_hz,
            effective_linewidth_hz = effective_linewidth_hz,
            planned_local_step_hz = planned_local_step_hz,
            planned_samples_per_physical_linewidth =
                linewidth_hz / planned_local_step_hz,
            planned_samples_per_effective_linewidth =
                effective_linewidth_hz / planned_local_step_hz,
            local_grid = local_grid,
        ))
    end

    planned_lower_hz = first(sort(frequency_hz))
    planned_upper_hz = last(sort(frequency_hz))
    closed_plans = Any[]
    for group in closed_pole_groups
        length(group.frequencies_hz) == length(group.residuals) || error(
            "D3 closed-pole frequencies and residuals must be aligned.",
        )
        for index in eachindex(group.frequencies_hz)
            pole_frequency_hz = Float64(group.frequencies_hz[index])
            if planned_lower_hz - D3_FORWARD_GRID_LINEWIDTH_FLOOR_HZ <=
                pole_frequency_hz <=
                planned_upper_hz + D3_FORWARD_GRID_LINEWIDTH_FLOOR_HZ
                exclusion = _d3_forward_adaptive_closed_pole_exclusion(
                    group,
                    index - 1,
                    pole_frequency_hz,
                )
                append!(frequency_hz, exclusion.boundaries)
                push!(protected_centers, (
                    pole_frequency_hz,
                    exclusion.exclusion_half_width_hz,
                ))
                push!(closed_plans, (
                    model_role = group.model_role,
                    section_length_m = group.section_length_m,
                    source_index = index - 1,
                    pole_frequency_hz = pole_frequency_hz,
                    mode_residual = Float64(group.residuals[index]),
                    exclusion_half_width_hz = exclusion.exclusion_half_width_hz,
                    exclusion_scale_steps = exclusion.exclusion_scale_steps,
                    negative_boundary_max_normalized_closure_ratio =
                        exclusion.negative_boundary_max_normalized_closure_ratio,
                    positive_boundary_max_normalized_closure_ratio =
                        exclusion.positive_boundary_max_normalized_closure_ratio,
                    hashes = group.hashes,
                ))
            end
        end
    end

    filter!(frequency_hz) do value
        all(protected_centers) do (center_hz, protected_half_width_hz)
            abs(value - center_hz) >= protected_half_width_hz
        end
    end
    sort!(unique!(frequency_hz))

    open_rows = Dict{String,Any}[]
    for plan in open_plans
        push!(open_rows, Dict(
            "source_index" => plan.source_index,
            "pole_frequency_hz" => plan.pole_frequency_hz,
            "pole_linewidth_hz" => plan.pole_linewidth_hz,
            "effective_linewidth_hz" => plan.effective_linewidth_hz,
            "planned_local_step_hz" => plan.planned_local_step_hz,
            "planned_samples_per_physical_linewidth" =>
                plan.planned_samples_per_physical_linewidth,
            "planned_samples_per_effective_linewidth" =>
                plan.planned_samples_per_effective_linewidth,
            "planned_local_sample_count" => length(plan.local_grid),
            "retained_planned_local_sample_count" =>
                count(value -> value in frequency_hz, plan.local_grid),
            "center_sampled" => plan.pole_frequency_hz in frequency_hz,
            "minimum_center_detuning_hz" =>
                minimum(abs.(frequency_hz .- plan.pole_frequency_hz)),
        ))
    end

    closed_rows = Dict{String,Any}[]
    for plan in closed_plans
        minimum_detuning_hz = minimum(abs.(frequency_hz .- plan.pole_frequency_hz))
        minimum_detuning_hz >= plan.exclusion_half_width_hz || error(
            "D3 merged grid entered a protected lossless closed-pole interval.",
        )
        plan.pole_frequency_hz in frequency_hz && error(
            "D3 merged grid sampled a lossless closed-pole center.",
        )
        push!(closed_rows, Dict(
            "model_role" => plan.model_role,
            "section_length_m" => plan.section_length_m,
            "source_index" => plan.source_index,
            "pole_frequency_hz" => plan.pole_frequency_hz,
            "mode_residual" => plan.mode_residual,
            "exclusion_half_width_hz" => plan.exclusion_half_width_hz,
            "exclusion_scale_steps" => plan.exclusion_scale_steps,
            "negative_boundary_max_normalized_closure_ratio" =>
                plan.negative_boundary_max_normalized_closure_ratio,
            "positive_boundary_max_normalized_closure_ratio" =>
                plan.positive_boundary_max_normalized_closure_ratio,
            "center_sampled" => false,
            "minimum_center_detuning_hz" => minimum_detuning_hz,
            "source_sha256" => plan.hashes.source_sha256,
            "node_order_sha256" => plan.hashes.node_order_sha256,
            "capacitance_sha256" => plan.hashes.capacitance_sha256,
            "inverse_inductance_sha256" => plan.hashes.inverse_inductance_sha256,
            "reduced_capacitance_sha256" => plan.hashes.reduced_capacitance_sha256,
            "reduced_inverse_inductance_sha256" =>
                plan.hashes.reduced_inverse_inductance_sha256,
        ))
    end
    sort!(closed_rows; by = row -> (
        row["section_length_m"],
        row["model_role"],
        row["pole_frequency_hz"],
    ))

    return (
        frequency_hz = frequency_hz,
        evidence = Dict(
            "contract_id" => "d3-open-closed-pole-aware-frequency-grid.v2",
            "requested_samples_per_linewidth" => requested_samples_per_linewidth,
            "linewidth_floor_hz" => D3_FORWARD_GRID_LINEWIDTH_FLOOR_HZ,
            "open_pole_center_sampling_policy" =>
                "resolved_center__subfloor_symmetric_half_step__closed_exclusion_union_may_override",
            "closed_pole_exclusion_policy" =>
                "lossless_closed_z_pole__symmetric_adaptive_power_of_two_ordinary_closure_exclusion",
            "maximum_local_intervals_per_open_pole" => maximum_intervals,
            "total_sample_count" => length(frequency_hz),
            "open_poles" => open_rows,
            "closed_pole_exclusions" => closed_rows,
        ),
    )
end

function d3_forward_response_result(
    case,
    design,
    target;
    section_length_m,
    frequency_grid_hz,
    floating_qubit_nominal,
    feedline,
    feedline_length_m,
    cext_f,
)
    settings = d3_forward_match_settings(target)
    return evaluate_d3_forward_response(
        case,
        design;
        section_length_m = section_length_m,
        floating_qubit_nominal = floating_qubit_nominal,
        feedline = feedline,
        feedline_length_m = feedline_length_m,
        cext_f = cext_f,
        frequency_grid_hz = frequency_grid_hz,
        settings...,
        z_closure_absolute_tolerance_ohm =
            D3_FORWARD_Z_CLOSURE_ABSOLUTE_TOLERANCE_OHM,
        s_closure_absolute_tolerance = D3_FORWARD_S_CLOSURE_ABSOLUTE_TOLERANCE,
        closure_relative_tolerance = D3_FORWARD_CLOSURE_RELATIVE_TOLERANCE,
        calibration_minimum_reference_magnitude = 0.5,
    )
end

function d3_forward_complex_payload(values)
    complex_values = ComplexF64.(collect(values))
    return Dict(
        "real" => Float64.(real.(complex_values)),
        "imag" => Float64.(imag.(complex_values)),
    )
end

function d3_forward_open_poles_payload(poles)
    return [
        Dict(
            "source_index" => index - 1,
            "frequency_hz" => real(poles.frequencies_hz[index]),
            "imaginary_frequency_hz" => min(imag(poles.frequencies_hz[index]), 0.0),
            "linewidth_hz" => max(-2 * imag(poles.frequencies_hz[index]), 0.0),
        )
        for index in eachindex(poles.frequencies_hz)
    ]
end

function d3_forward_trace_hashes(trace)
    return Dict(
        "source_sha256" => trace.hashes.source_sha256,
        "node_order_sha256" => trace.hashes.node_order_sha256,
        "capacitance_sha256" => trace.hashes.capacitance_sha256,
        "inverse_inductance_sha256" => trace.hashes.inverse_inductance_sha256,
        "open_pole_state_matrix_sha256" => trace.hashes.open_poles.state_matrix_sha256,
    )
end

function d3_forward_residual_payload(lhs, rhs)
    length(lhs) == length(rhs) > 0 || error("D3 response residual traces must be aligned.")
    residual = ComplexF64.(lhs .- rhs)
    return Dict(
        "complex_residual" => d3_forward_complex_payload(residual),
        "complex_rmse" => sqrt(sum(abs2, residual) / length(residual)),
        "max_abs" => maximum(abs, residual),
    )
end

"""Package exact six-coordinate authority beside the existing equivalent trace."""
function d3_forward_exact_six_response_payload(
    exact,
    exact_feedline_reference,
    existing_response,
    full_coordinate_handoff,
)
    exact.contract_id == D3_FORWARD_EXACT_SIX_RESPONSE_CONTRACT || error(
        "D3 exact-six trace contract is incompatible.",
    )
    exact.frequency_hz == exact_feedline_reference.frequency_hz ==
        existing_response.equivalent.frequency_hz || error(
        "D3 exact-six, calibration-reference, and equivalent grids must match exactly.",
    )
    existing_response.calibration.frequency_hz == exact.frequency_hz || error(
        "D3 exact-six and existing calibrated-equivalent grids must match exactly.",
    )
    exact_feedline_reference.reference_plane.reference_impedance_ohm ==
        existing_response.equivalent.reference_plane.reference_impedance_ohm ==
        exact.reference_impedance_ohm || error(
        "D3 exact-six and existing equivalent responses must share one reference impedance.",
    )
    exact_feedline_reference.terminal_names == existing_response.equivalent.terminal_names || error(
        "D3 exact-six and existing equivalent responses must share ordered terminal planes.",
    )
    exact_sections = exact_feedline_reference.reference_plane.section_lengths_m
    length(exact_sections) == 2 && exact_sections[1] == exact_sections[2] || error(
        "D3 exact-six calibration reference must be the same two-pi feedline model.",
    )
    handoff_hashes = full_coordinate_handoff["full_coordinate_hashes"]
    exact.hashes.capacitance_sha256 == handoff_hashes["capacitance_sha256"] || error(
        "D3 exact-six capacitance hash disagrees with its full-coordinate handoff.",
    )
    exact.hashes.inverse_inductance_sha256 ==
        handoff_hashes["inverse_inductance_sha256"] || error(
        "D3 exact-six inverse-inductance hash disagrees with its full-coordinate handoff.",
    )
    calibration = _d3_forward_calibrate_s21(
        exact.s21,
        exact.s21,
        exact_feedline_reference.s21,
        0.5,
    )
    existing_sections = existing_response.feedline_reference.reference_plane.section_lengths_m
    return Dict{String,Any}(
        "contract_id" => D3_FORWARD_EXACT_SIX_RESPONSE_CONTRACT,
        "response_authority" => "canonical_exact_six_coordinate_open_response",
        "model_role" => "response_matched_two_pi_full_coordinate_equivalent",
        "coordinate_order" => copy(exact.coordinate_order),
        "frequency_hz" => copy(exact.frequency_hz),
        "raw_s21" => d3_forward_complex_payload(exact.s21),
        "calibrated_s21" => d3_forward_complex_payload(calibration.distributed_s21),
        "open_poles" => d3_forward_open_poles_payload(exact.poles),
        "reference_impedance_ohm" => exact.reference_impedance_ohm,
        "port_selector" => Dict(
            "port_coordinates" => ["f1", "f2"],
            "coordinate_indices_zero_based" => [3, 5],
            "matrix" => [collect(row) for row in eachrow(exact.selector)],
            "current_orientation" => "both port currents oriented into the finite network",
            "reference_plane" => "local matched terminals at f1 and f2",
        ),
        "hashes" => Dict(
            "capacitance_sha256" => exact.hashes.capacitance_sha256,
            "inverse_inductance_sha256" => exact.hashes.inverse_inductance_sha256,
            "selector_sha256" => exact.hashes.selector_sha256,
            "open_pole_state_matrix_sha256" =>
                exact.hashes.open_pole_state_matrix_sha256,
            "calibration_reference" => d3_forward_trace_hashes(exact_feedline_reference),
        ),
        "calibration" => Dict(
            "contract_id" => calibration.provenance.contract_id,
            "operation" => "pointwise_complex_s21_division_by_same_two_pi_feedline_reference",
            "reference_s21" => d3_forward_complex_payload(exact_feedline_reference.s21),
            "reference_section_lengths_m" => copy(exact_sections),
            "minimum_reference_magnitude" => calibration.minimum_reference_magnitude,
            "minimum_observed_reference_magnitude" =>
                calibration.minimum_observed_reference_magnitude,
        ),
        "residual_vs_existing_equivalent" => Dict(
            "sign" => "exact_six_minus_existing_equivalent",
            "existing_equivalent_contract_id" => existing_response.contract_id,
            "raw_s21" => d3_forward_residual_payload(
                exact.s21,
                existing_response.equivalent.s21,
            ),
            "calibrated_s21" => d3_forward_residual_payload(
                calibration.distributed_s21,
                existing_response.calibration.equivalent_s21,
            ),
            "raw_comparison" => "same_matched_terminal_planes_and_reference_impedance",
            "calibrated_comparison" =>
                "each_model_divided_by_its_own_feedline_only_reference_at_the_same_terminal_planes",
            "exact_six_feedline_section_lengths_m" => copy(exact_sections),
            "existing_equivalent_feedline_section_lengths_m" => copy(existing_sections),
            "formula_identity_claimed" => false,
            "formula_identity_blocker" =>
                "exact_six_uses_two_pi_sections_while_existing_equivalent_uses_the_declared_finer_ladder",
        ),
        "provenance" => Dict(
            "time_convention" => "exp(-i*omega*t)",
            "dynamic_operator" => "K-omega^2*C-i*omega*B*Y0*B^T",
            "source_full_coordinate_handoff_contract_id" =>
                full_coordinate_handoff["contract_id"],
            "source_full_coordinate_handoff_semantic_sha256" =>
                D3SemanticHash.semantic_value_sha256(full_coordinate_handoff),
            "cext_stamp_count" => 1,
            "port_loading" => "matched_semi_infinite_lines_on_physical_f1_and_f2",
            "qrp_projection_applied" => false,
            "fixed_kappa_applied" => false,
            "three_mode_role" => "comparison_only_not_response_authority",
        ),
    )
end

function d3_forward_frequency_grid_policy(evidence)
    open_row_keys = [
        "source_index",
        "pole_frequency_hz",
        "pole_linewidth_hz",
        "effective_linewidth_hz",
        "planned_local_step_hz",
        "planned_samples_per_physical_linewidth",
        "planned_samples_per_effective_linewidth",
        "planned_local_sample_count",
        "retained_planned_local_sample_count",
        "center_sampled",
        "minimum_center_detuning_hz",
    ]
    closed_row_keys = [
        "model_role",
        "section_length_m",
        "source_index",
        "pole_frequency_hz",
        "mode_residual",
        "exclusion_half_width_hz",
        "exclusion_scale_steps",
        "negative_boundary_max_normalized_closure_ratio",
        "positive_boundary_max_normalized_closure_ratio",
        "center_sampled",
        "minimum_center_detuning_hz",
        "source_sha256",
        "node_order_sha256",
        "capacitance_sha256",
        "inverse_inductance_sha256",
        "reduced_capacitance_sha256",
        "reduced_inverse_inductance_sha256",
    ]
    open_rows = evidence["open_poles"]
    closed_rows = evidence["closed_pole_exclusions"]
    length(open_rows) == 3 || error(
        "D3 frequency-grid policy requires exactly three open-pole rows.",
    )
    length(closed_rows) == 12 || error(
        "D3 frequency-grid policy requires exactly twelve in-span closed-pole rows.",
    )
    policy_open_rows = Dict{String,Any}[]
    for (index, source_row) in enumerate(open_rows)
        d3_forward_require_exact_keys(
            source_row,
            open_row_keys,
            "D3 frequency-grid open-pole row $(index)",
        )
        push!(policy_open_rows, Dict{String,Any}(
            key => source_row[key] for key in open_row_keys
        ))
    end
    policy_closed_rows = Dict{String,Any}[]
    for (index, source_row) in enumerate(closed_rows)
        d3_forward_require_exact_keys(
            source_row,
            closed_row_keys,
            "D3 frequency-grid closed-pole row $(index)",
        )
        push!(policy_closed_rows, Dict{String,Any}(
            key => source_row[key] for key in closed_row_keys
        ))
    end
    policy = Dict{String,Any}(
        "contract_id" => evidence["contract_id"],
        "requested_samples_per_linewidth" => evidence["requested_samples_per_linewidth"],
        "linewidth_floor_hz" => evidence["linewidth_floor_hz"],
        "open_pole_center_sampling_policy" => evidence["open_pole_center_sampling_policy"],
        "closed_pole_exclusion_policy" => evidence["closed_pole_exclusion_policy"],
        "maximum_local_intervals_per_open_pole" =>
            evidence["maximum_local_intervals_per_open_pole"],
        "open_poles" => policy_open_rows,
        "closed_pole_exclusions" => policy_closed_rows,
    )
    d3_forward_require_exact_keys(
        policy,
        [
            "contract_id",
            "requested_samples_per_linewidth",
            "linewidth_floor_hz",
            "open_pole_center_sampling_policy",
            "closed_pole_exclusion_policy",
            "maximum_local_intervals_per_open_pole",
            "open_poles",
            "closed_pole_exclusions",
        ],
        "D3 frequency-grid policy",
    )
    policy["contract_id"] == "d3-open-closed-pole-aware-frequency-grid.v2" || error(
        "D3 frequency-grid policy contract is unsupported.",
    )
    policy["open_pole_center_sampling_policy"] ==
        "resolved_center__subfloor_symmetric_half_step__closed_exclusion_union_may_override" ||
        error("D3 open-pole center-sampling policy is unsupported.")
    policy["closed_pole_exclusion_policy"] ==
        "lossless_closed_z_pole__symmetric_adaptive_power_of_two_ordinary_closure_exclusion" || error(
        "D3 closed-pole exclusion policy is unsupported.",
    )
    linewidth_floor_hz = Float64(policy["linewidth_floor_hz"])
    linewidth_floor_hz == D3_FORWARD_GRID_LINEWIDTH_FLOOR_HZ || error(
        "D3 frequency-grid linewidth floor is inconsistent.",
    )
    expected_identities = Set(
        (role, section, source_index)
        for role in ("distributed", "equivalent")
        for section in (40.0e-6, 80.0e-6)
        for source_index in 0:2
    )
    actual_identities = Set(
        (
            String(row["model_role"]),
            Float64(row["section_length_m"]),
            Int(row["source_index"]),
        )
        for row in policy_closed_rows
    )
    actual_identities == expected_identities || error(
        "D3 closed-pole rows must uniquely cover three modes for distributed/equivalent at 40/80 um.",
    )
    for (index, row) in enumerate(policy_closed_rows)
        scale_steps_numeric = Float64(row["exclusion_scale_steps"])
        isfinite(scale_steps_numeric) && isinteger(scale_steps_numeric) || error(
            "D3 closed-pole row $(index) exclusion scale steps must be an integer.",
        )
        scale_steps = Int(scale_steps_numeric)
        0 <= scale_steps <= D3_FORWARD_CLOSED_POLE_MAX_EXCLUSION_SCALE_STEPS || error(
            "D3 closed-pole row $(index) exclusion scale steps exceed the finite bound.",
        )
        exclusion_half_width_hz = Float64(row["exclusion_half_width_hz"])
        exclusion_half_width_hz == linewidth_floor_hz * (2.0 ^ scale_steps) || error(
            "D3 closed-pole row $(index) exclusion half-width is not its exact power-of-two radius.",
        )
        for key in (
            "negative_boundary_max_normalized_closure_ratio",
            "positive_boundary_max_normalized_closure_ratio",
        )
            ratio = Float64(row[key])
            isfinite(ratio) && 0 <= ratio <= 1 || error(
                "D3 closed-pole row $(index) $(key) must be finite and within [0, 1].",
            )
        end
        row["center_sampled"] === false || error(
            "D3 closed-pole row $(index) must not sample its center.",
        )
        pole_frequency_hz = Float64(row["pole_frequency_hz"])
        detuning_roundoff_hz = 16 * eps(max(abs(pole_frequency_hz), linewidth_floor_hz))
        Float64(row["minimum_center_detuning_hz"]) + detuning_roundoff_hz >=
            exclusion_half_width_hz || error(
            "D3 closed-pole row $(index) violates its protected half-width.",
        )
        residual = Float64(row["mode_residual"])
        isfinite(residual) && 0 <= residual <= D3_FORWARD_CLOSED_POLE_MODE_RESIDUAL_MAX ||
            error("D3 closed-pole row $(index) mode residual exceeds its numerical bound.")
        for key in (
            "source_sha256",
            "node_order_sha256",
            "capacitance_sha256",
            "inverse_inductance_sha256",
            "reduced_capacitance_sha256",
            "reduced_inverse_inductance_sha256",
        )
            hash = String(row[key])
            length(hash) == 64 && all(character ->
                isdigit(character) || 'a' <= character <= 'f', hash) || error(
                "D3 closed-pole row $(index) $(key) must be lowercase SHA-256 hex.",
            )
        end
    end
    return policy
end

function d3_forward_response_payload(result, frequency_grid_evidence)
    return Dict{String,Any}(
        "contract_id" => D3_FORWARD_RESPONSE_CONTRACT_ID,
        "frequency_hz" => copy(result.distributed.frequency_hz),
		"frequency_grid_policy" => d3_forward_frequency_grid_policy(frequency_grid_evidence),
        "calibrated_distributed_s21" => d3_forward_complex_payload(
            result.calibration.distributed_s21,
        ),
        "calibrated_equivalent_s21" => d3_forward_complex_payload(
            result.calibration.equivalent_s21,
        ),
        "raw_distributed_s21" => d3_forward_complex_payload(result.distributed.s21),
        "raw_equivalent_s21" => d3_forward_complex_payload(result.equivalent.s21),
        "feedline_reference_s21" => d3_forward_complex_payload(result.feedline_reference.s21),
        "distributed_z21_ohm" => d3_forward_complex_payload(result.distributed.z21_ohm),
        "equivalent_z21_ohm" => d3_forward_complex_payload(result.equivalent.z21_ohm),
        "distributed_open_poles" => d3_forward_open_poles_payload(result.distributed.poles),
        "equivalent_open_poles" => d3_forward_open_poles_payload(result.equivalent.poles),
        "reference_impedance_ohm" => result.distributed.reference_plane.reference_impedance_ohm,
        "reference_plane" => "matched terminal planes of the shared finite feedline ladder",
        "calibration" => Dict(
            "contract_id" => result.calibration.provenance.contract_id,
            "operation" => "pointwise_complex_s21_division_by_feedline_reference",
            "minimum_reference_magnitude" => result.calibration.minimum_reference_magnitude,
            "minimum_observed_reference_magnitude" =>
                result.calibration.minimum_observed_reference_magnitude,
        ),
        "closure" => Dict(
            "distributed_z_from_s_max_residual_ohm" =>
                result.distributed.closure.z_from_s_max_residual_ohm,
            "distributed_s_from_z_max_residual" =>
                result.distributed.closure.s_from_z_max_residual,
            "equivalent_z_from_s_max_residual_ohm" =>
                result.equivalent.closure.z_from_s_max_residual_ohm,
            "equivalent_s_from_z_max_residual" =>
                result.equivalent.closure.s_from_z_max_residual,
            "reference_z_from_s_max_residual_ohm" =>
                result.feedline_reference.closure.z_from_s_max_residual_ohm,
            "reference_s_from_z_max_residual" =>
                result.feedline_reference.closure.s_from_z_max_residual,
        ),
        "hashes" => Dict(
            "distributed" => d3_forward_trace_hashes(result.distributed),
            "equivalent" => d3_forward_trace_hashes(result.equivalent),
            "feedline_reference" => d3_forward_trace_hashes(result.feedline_reference),
        ),
    )
end

function d3_forward_complex_residual_metrics(lhs, rhs)
    length(lhs) == length(rhs) > 0 || error("D3 refinement traces must be aligned.")
    residual = ComplexF64.(lhs .- rhs)
    return (
        rmse = sqrt(sum(abs2, residual) / length(residual)),
        max_abs = maximum(abs, residual),
    )
end

function d3_forward_interpolate_complex(source_x, source_y, target_x)
    x = Float64.(source_x)
    y = ComplexF64.(source_y)
    interpolated = ComplexF64[]
    for target in Float64.(target_x)
        index = searchsortedlast(x, target)
        value = if index <= 0
            y[1]
        elseif index >= length(x)
            y[end]
        else
            fraction = (target - x[index]) / (x[index + 1] - x[index])
            y[index] + fraction * (y[index + 1] - y[index])
        end
        push!(interpolated, value)
    end
    return interpolated
end

function d3_forward_open_pole_deltas(coarse, fine, frequency_span)
    lower, upper = extrema(Float64.(frequency_span))
    coarse_rows = [
        (frequency = real(coarse.frequencies_hz[index]), linewidth = coarse.linewidths_hz[index])
        for index in eachindex(coarse.frequencies_hz)
        if lower <= real(coarse.frequencies_hz[index]) <= upper
    ]
    fine_rows = [
        (frequency = real(fine.frequencies_hz[index]), linewidth = fine.linewidths_hz[index])
        for index in eachindex(fine.frequencies_hz)
        if lower <= real(fine.frequencies_hz[index]) <= upper
    ]
    length(coarse_rows) >= 3 && length(fine_rows) >= 3 || error(
        "D3 refinement band must contain at least three open poles.",
    )
    frequency_deltas = Float64[]
    linewidth_deltas = Float64[]
    for fine_row in fine_rows
        nearest = coarse_rows[argmin([abs(row.frequency - fine_row.frequency) for row in coarse_rows])]
        push!(frequency_deltas, abs(nearest.frequency - fine_row.frequency))
        push!(linewidth_deltas, abs(nearest.linewidth - fine_row.linewidth))
    end
    return (
        frequency_hz = maximum(frequency_deltas),
        linewidth_hz = maximum(linewidth_deltas),
    )
end

function d3_forward_refinement_payload(coarse_section, coarse_grid, fine)
    section_residual = d3_forward_complex_residual_metrics(
        coarse_section.calibration.distributed_s21,
        fine.calibration.distributed_s21,
    )
    section_poles = d3_forward_open_pole_deltas(
        coarse_section.distributed.poles,
        fine.distributed.poles,
        fine.distributed.frequency_hz,
    )
    interpolated = d3_forward_interpolate_complex(
        coarse_grid.distributed.frequency_hz,
        coarse_grid.calibration.distributed_s21,
        fine.distributed.frequency_hz,
    )
    grid_residual = d3_forward_complex_residual_metrics(
        interpolated,
        fine.calibration.distributed_s21,
    )
    maximum_step(values) = maximum(diff(Float64.(values)))
    return Dict(
        "section" => [
            Dict(
                "section_length_m" => 80.0e-6,
                "distributed_s21_complex_rmse_to_finest" => section_residual.rmse,
                "distributed_s21_max_abs_to_finest" => section_residual.max_abs,
                "max_open_pole_frequency_delta_hz_to_finest" => section_poles.frequency_hz,
                "max_open_pole_linewidth_delta_hz_to_finest" => section_poles.linewidth_hz,
            ),
            Dict(
                "section_length_m" => 40.0e-6,
                "distributed_s21_complex_rmse_to_finest" => 0.0,
                "distributed_s21_max_abs_to_finest" => 0.0,
                "max_open_pole_frequency_delta_hz_to_finest" => 0.0,
                "max_open_pole_linewidth_delta_hz_to_finest" => 0.0,
            ),
        ],
        "frequency_grid" => [
            Dict(
                "sample_count" => length(coarse_grid.distributed.frequency_hz),
                "maximum_frequency_step_hz" => maximum_step(coarse_grid.distributed.frequency_hz),
                "distributed_s21_complex_rmse_to_finest" => grid_residual.rmse,
                "distributed_s21_max_abs_to_finest" => grid_residual.max_abs,
                "max_open_pole_frequency_delta_hz_to_finest" => 0.0,
                "max_open_pole_linewidth_delta_hz_to_finest" => 0.0,
            ),
            Dict(
                "sample_count" => length(fine.distributed.frequency_hz),
                "maximum_frequency_step_hz" => maximum_step(fine.distributed.frequency_hz),
                "distributed_s21_complex_rmse_to_finest" => 0.0,
                "distributed_s21_max_abs_to_finest" => 0.0,
                "max_open_pole_frequency_delta_hz_to_finest" => 0.0,
                "max_open_pole_linewidth_delta_hz_to_finest" => 0.0,
            ),
        ],
    )
end

function d3_forward_search_cost_terms(metrics, target)
    specifications = (
        ("fr_hz", metrics["fr_hz"], target.fr_hz, D3_FORWARD_AGENT_SCALES_HZ.fr,
            "agent_declared_for_search_only"),
        ("fp_hz", metrics["fp_hz"], target.fp_hz, D3_FORWARD_AGENT_SCALES_HZ.fp,
            "agent_declared_for_search_only"),
        ("notch_hz", metrics["notch_hz"], target.notch_hz, D3_FORWARD_AGENT_SCALES_HZ.notch,
            "agent_declared_for_search_only"),
        ("kappa_p_external_hz", metrics["kappa_hz"], target.kappa_hz,
            D3_FORWARD_AGENT_SCALES_HZ.kappa, "agent_declared_for_search_only"),
        ("j_hz", metrics["J_hz"], target.J_hz, D3_FORWARD_AGENT_SCALES_HZ.J,
            "agent_declared_for_search_only"),
        ("g_hz", metrics["g_hz"], target.g_hz, D3_FORWARD_AGENT_SCALES_HZ.g,
            "human_decided"),
    )
    return Dict(
        name => begin
            residual = Float64(raw) - Float64(target_value)
            Dict(
                "raw_value" => Float64(raw),
                "target_value" => Float64(target_value),
                "residual" => residual,
                "scale" => Float64(scale),
                "scaled_value" => residual / Float64(scale),
                "scale_authority" => authority,
            )
        end
        for (name, raw, target_value, scale, authority) in specifications
    )
end

function d3_forward_search_candidate(
    row,
    target,
    case;
    stage,
    candidate_id,
    selected,
    grid_evidence = nothing,
)
    row["status"] == "complete" || error(
        "Only completed forward evaluations may enter finite design-search evidence.",
    )
    parameters = Dict{String,Any}(
        String(key) => Float64(value) for (key, value) in row["design"]
    )
    parameters["cext_f"] = Float64(row["cext_f"])
    parameters["inter_trace_ground_width_um"] = Float64(case.inter_trace_ground_width_um)
    parameters["upper_ground_clearance_width_um"] =
        Float64(case.upper_ground_clearance_width_um)
    for (key, value) in row["response_match"]
        parameters["response_match_$(key)"] = Float64(value)
    end
    if grid_evidence !== nothing
        fine = grid_evidence.fine
        coarse = grid_evidence.coarse
        parameters["frequency_grid_linewidth_floor_hz"] =
            Float64(fine["linewidth_floor_hz"])
        parameters["frequency_grid_fine_requested_samples_per_linewidth"] =
            Float64(fine["requested_samples_per_linewidth"])
        parameters["frequency_grid_coarse_requested_samples_per_linewidth"] =
            Float64(coarse["requested_samples_per_linewidth"])
        parameters["frequency_grid_fine_sample_count"] = Float64(fine["total_sample_count"])
        parameters["frequency_grid_coarse_sample_count"] =
            Float64(coarse["total_sample_count"])
        parameters["frequency_grid_fine_minimum_planned_samples_per_physical_linewidth"] =
            minimum(
                Float64(pole["planned_samples_per_physical_linewidth"])
                for pole in fine["open_poles"]
            )
        parameters["frequency_grid_coarse_minimum_planned_samples_per_physical_linewidth"] =
            minimum(
                Float64(pole["planned_samples_per_physical_linewidth"])
                for pole in coarse["open_poles"]
            )
        parameters["frequency_grid_fine_minimum_retained_planned_local_fraction"] =
            minimum(
                Float64(pole["retained_planned_local_sample_count"]) /
                    Float64(pole["planned_local_sample_count"])
                for pole in fine["open_poles"]
            )
        parameters["frequency_grid_coarse_minimum_retained_planned_local_fraction"] =
            minimum(
                Float64(pole["retained_planned_local_sample_count"]) /
                    Float64(pole["planned_local_sample_count"])
                for pole in coarse["open_poles"]
            )
        parameters["frequency_grid_fine_closed_pole_exclusion_count"] =
            Float64(length(fine["closed_pole_exclusions"]))
        parameters["frequency_grid_coarse_closed_pole_exclusion_count"] =
            Float64(length(coarse["closed_pole_exclusions"]))
    end
    terms = d3_forward_search_cost_terms(row["metrics"], target)
    total = sum(Float64(term["scaled_value"])^2 for term in values(terms))
    return Dict(
        "candidate_id" => String(candidate_id),
        "slot_hz" => target.slot_hz,
        "stage" => String(stage),
        "parameters" => parameters,
        "cost_terms" => terms,
        "total_scaled_cost" => total,
        "hard_gates" => Dict(
            "finite_physical_geometry" => true,
            "notch_path_identity" => true,
            "forward_evaluation_complete" => true,
            "bare_fit_disabled" => true,
            "public_q2d_route" => true,
        ),
        "rejection_reasons" => selected ? String[] : ["not_selected_by_deterministic_search"],
        "selected" => Bool(selected),
    )
end

function d3_forward_assert_json_finite(value, context = "artifact")
    if value isa AbstractDict
        for (key, child) in value
            d3_forward_assert_json_finite(child, "$(context).$(key)")
        end
    elseif value isa AbstractVector || value isa Tuple
        for (index, child) in enumerate(value)
            d3_forward_assert_json_finite(child, "$(context)[$(index)]")
        end
    elseif value isa Bool || value isa AbstractString
        return nothing
    elseif value isa Number
        isfinite(Float64(value)) || error("$(context) contains a non-finite number.")
    else
        error("$(context) contains unsupported JSON value $(typeof(value)).")
    end
    return nothing
end

function d3_forward_atomic_write_json(path, payload)
    output = abspath(String(path))
    mkpath(dirname(output))
    d3_forward_assert_json_finite(payload)
    temporary_path, stream = mktemp(dirname(output))
    try
        SuperconductingCircuitsCore.JSON3.write(stream, payload)
        write(stream, '\n')
        flush(stream)
        close(stream)
        mv(temporary_path, output; force = true)
    catch
        isopen(stream) && close(stream)
        isfile(temporary_path) && rm(temporary_path)
        rethrow()
    end
    return output
end

function d3_forward_validate_exact_six_response_payload(payload, expected_frequency_hz)
    d3_forward_require_exact_keys(
        payload,
        ["contract_id", "response_authority", "model_role", "coordinate_order",
            "frequency_hz", "raw_s21", "calibrated_s21", "open_poles",
            "reference_impedance_ohm", "port_selector", "hashes", "calibration",
            "residual_vs_existing_equivalent", "provenance"],
        "D3 exact-six response",
    )
    payload["contract_id"] == D3_FORWARD_EXACT_SIX_RESPONSE_CONTRACT || error(
        "D3 exact-six response contract is invalid.",
    )
    payload["response_authority"] == "canonical_exact_six_coordinate_open_response" || error(
        "D3 exact-six response authority is invalid.",
    )
    payload["coordinate_order"] == ["q", "r", "p", "f1", "fc", "f2"] || error(
        "D3 exact-six coordinate order is invalid.",
    )
    frequencies = Float64.(payload["frequency_hz"])
    frequencies == Float64.(expected_frequency_hz) || error(
        "D3 exact-six response grid must equal the existing response grid.",
    )
    function validate_complex(record, context)
        d3_forward_require_exact_keys(record, ["real", "imag"], context)
        length(record["real"]) == length(record["imag"]) == length(frequencies) || error(
            "$(context) must align with the exact-six frequency grid.",
        )
    end
    validate_complex(payload["raw_s21"], "D3 exact-six raw S21")
    validate_complex(payload["calibrated_s21"], "D3 exact-six calibrated S21")
    length(payload["open_poles"]) == 5 || error(
        "D3 exact-six response must publish five positive open poles.",
    )
    selector = payload["port_selector"]
    selector["port_coordinates"] == ["f1", "f2"] &&
        selector["coordinate_indices_zero_based"] == [3, 5] &&
        selector["matrix"] == [
            [0.0, 0.0],
            [0.0, 0.0],
            [0.0, 0.0],
            [1.0, 0.0],
            [0.0, 0.0],
            [0.0, 1.0],
        ] || error("D3 exact-six physical f1/f2 port selector is invalid.")
    hashes = payload["hashes"]
    for key in (
        "capacitance_sha256",
        "inverse_inductance_sha256",
        "selector_sha256",
        "open_pole_state_matrix_sha256",
    )
        occursin(r"^[0-9a-f]{64}$", String(hashes[key])) || error(
            "D3 exact-six $(key) must be a lowercase SHA-256 digest.",
        )
    end
    validate_complex(
        payload["calibration"]["reference_s21"],
        "D3 exact-six calibration reference S21",
    )
    for role in ("raw_s21", "calibrated_s21")
        residual = payload["residual_vs_existing_equivalent"][role]
        validate_complex(
            residual["complex_residual"],
            "D3 exact-six $(role) residual",
        )
    end
    provenance = payload["provenance"]
    provenance["qrp_projection_applied"] === false &&
        provenance["fixed_kappa_applied"] === false || error(
        "D3 exact-six authority must not project q/r/p or apply fixed kappa.",
    )
    return payload
end

function d3_forward_validate_primary_payload(payload)
    d3_forward_require_exact_keys(
        payload,
        ["schema_version", "status", "bare_fit_node_state", "bare_fit_execution_policy",
            "vf_settings", "slots", "provenance", "design_search_evidence"],
        "D3 forward primary artifact",
    )
    payload["schema_version"] == D3_FORWARD_RUN_SCHEMA || error("D3 run schema is invalid.")
    payload["status"] == "complete" || error("D3 run status must be complete.")
    payload["bare_fit_node_state"] == "disabled_not_implemented" || error(
        "D3 bare-fit state is invalid.",
    )
    payload["bare_fit_execution_policy"] == "must_not_run" || error(
        "D3 bare-fit policy is invalid.",
    )
    slots = payload["slots"]
    length(slots) == 5 || error("D3 run must contain exactly five slots.")
    Float64[slot["slot_hz"] for slot in slots] == D3_FORWARD_SLOT_HZ || error(
        "D3 run slots must use the canonical order.",
    )
    for slot in slots
        d3_forward_require_exact_keys(
            slot,
            ["slot_hz", "full_coordinate_handoff", "exact_six_coordinate_response",
                "kappa_p_external_hz", "kappa_provenance", "response", "refinement",
                "provenance"],
            "D3 forward slot",
        )
        d3_forward_validate_exact_six_response_payload(
            slot["exact_six_coordinate_response"],
            slot["response"]["frequency_hz"],
        )
    end
    d3_forward_assert_json_finite(payload)
    return payload
end

function d3_forward_load_inputs(; target_path, initializer_path, q2d_pair_path,
    q2d_single_path, qubit_path, config_path, expected_q2d_pair_cases = 9,
    expected_q2d_single_cases = 3)
    target = load_d3_forward_target(target_path)
    initializer = load_d3_forward_initializer(initializer_path, target)
    cases = load_d3_forward_q2d_cases(
        q2d_pair_path,
        q2d_single_path;
        expected_pair_cases = expected_q2d_pair_cases,
        expected_single_cases = expected_q2d_single_cases,
    )
    length(cases) == expected_q2d_pair_cases || error(
        "D3 forward execution produced an unexpected joined Q2D case count.",
    )
    qubit_input = D3FloatingQubitInput.load_floating_qubit_nominal_input(
        qubit_path,
        D3FloatingQubitNominal,
        require_open_side_contract = true,
    )
    qubit_input.model.L_J_per_junction_nH == target.lj_per_junction_nH || error(
        "Private qubit L_J disagrees with the revision-3 target.",
    )
    configuration_path = abspath(String(config_path))
    isfile(configuration_path) || error("Missing D3 design config: $(configuration_path)")
    config = SuperconductingCircuitsCore.JSON3.read(
        read(configuration_path, String), Dict{String,Any},
    )
    feedline = load_d3_feedline_rlgc(config)
    return (
        target = target,
        initializer = initializer,
        cases = cases,
        qubit_input = qubit_input,
        feedline = feedline,
        hashes = Dict(
            "target" => target.input_sha256,
            "initializer" => initializer.input_sha256,
            "q2d_pair" => d3_forward_file_sha256(q2d_pair_path),
            "q2d_single" => d3_forward_file_sha256(q2d_single_path),
            "qubit" => qubit_input.input_sha256,
            "config" => d3_forward_file_sha256(configuration_path),
        ),
    )
end

function d3_forward_input_identity(hashes)
    ordered = join(["$(key)=$(hashes[key])" for key in sort(collect(keys(hashes)))], ";")
    return "input-sha256-set:" * ordered
end

function run_d3_forward_circuit_validation(;
    target_path,
    initializer_path,
    q2d_pair_path,
    q2d_single_path,
    qubit_path,
    config_path,
    output_path,
    bare_fit_requested = false,
)
    d3_forward_require_bare_fit_disabled(bare_fit_requested)
    inputs = d3_forward_load_inputs(
        target_path = target_path,
        initializer_path = initializer_path,
        q2d_pair_path = q2d_pair_path,
        q2d_single_path = q2d_single_path,
        qubit_path = qubit_path,
        config_path = config_path,
    )
    feedline_length_m = 1.0e-3
    screening = d3_forward_screen_cases(
        inputs.cases,
        inputs.initializer,
        inputs.target;
        floating_qubit_nominal = inputs.qubit_input.model,
        feedline = inputs.feedline,
        feedline_length_m = feedline_length_m,
    )
    selected_case = screening.selected_case
    slots = Dict{String,Any}[]
    search_candidates = Dict{String,Any}[]

    for case_row in screening.evidence["cases"]
        case = only(filter(item -> String(item.id) == case_row["public_q2d_case"]["case_id"],
            inputs.cases))
        for row in case_row["slot_evaluations"]
            row["status"] == "complete" || continue
            slot_target = d3_forward_target_for_slot(inputs.target, row["slot_hz"])
            push!(search_candidates, d3_forward_search_candidate(
                row,
                slot_target,
                case;
                stage = "q2d_screening",
                candidate_id = "screen__$(case.id)__$(round(Int, slot_target.slot_hz))",
                selected = false,
            ))
        end
    end

    for slot_hz in inputs.target.slot_hz
        @info "Fine-tuning selected public Q2D case" case_id = String(selected_case.id) slot_hz
        slot_target = d3_forward_target_for_slot(inputs.target, slot_hz)
        source_record = d3_forward_with_source_velocity(
            inputs.initializer.by_slot[slot_hz], inputs.initializer.source_velocity_m_per_s,
        )
        initial = d3_forward_design_from_initializer(
            source_record,
            selected_case;
            guided = true,
            id = "d3_slot_$(round(Int, slot_hz))_guided_seed",
        )
        search = d3_forward_bounded_search(
            initial,
            slot_target,
            design -> d3_forward_evaluate_candidate(
                selected_case,
                design,
                slot_target;
                section_length_m = 40.0e-6,
                floating_qubit_nominal = inputs.qubit_input.model,
                feedline = inputs.feedline,
                feedline_length_m = feedline_length_m,
            );
            max_iterations = 4,
        )
        final = search.best
        preliminary_response = d3_forward_response_result(
            selected_case,
            final.design,
            slot_target;
            section_length_m = 40.0e-6,
            frequency_grid_hz = d3_forward_frequency_grid(slot_hz; fine = false),
            floating_qubit_nominal = inputs.qubit_input.model,
            feedline = inputs.feedline,
            feedline_length_m = feedline_length_m,
            cext_f = final.kappa.cext_f,
        )
        in_band_poles = d3_forward_in_band_poles(
            preliminary_response.distributed.poles,
            slot_target,
        )
        base_frequency_grid_hz = d3_forward_frequency_grid(slot_hz; fine = false)
        section_refinement_probe = d3_forward_response_result(
            selected_case,
            final.design,
            slot_target;
            section_length_m = 80.0e-6,
            frequency_grid_hz = Float64[
                first(base_frequency_grid_hz),
                last(base_frequency_grid_hz),
            ],
            floating_qubit_nominal = inputs.qubit_input.model,
            feedline = inputs.feedline,
            feedline_length_m = feedline_length_m,
            cext_f = final.kappa.cext_f,
        )
        closed_pole_groups = [
            d3_forward_closed_pole_group(
                preliminary_response.distributed;
                model_role = "distributed",
                section_length_m = 40.0e-6,
            ),
            d3_forward_closed_pole_group(
                preliminary_response.equivalent;
                model_role = "equivalent",
                section_length_m = 40.0e-6,
            ),
            d3_forward_closed_pole_group(
                preliminary_response.feedline_reference;
                model_role = "feedline_reference",
                section_length_m = 40.0e-6,
            ),
            d3_forward_closed_pole_group(
                section_refinement_probe.distributed;
                model_role = "distributed",
                section_length_m = 80.0e-6,
            ),
            d3_forward_closed_pole_group(
                section_refinement_probe.equivalent;
                model_role = "equivalent",
                section_length_m = 80.0e-6,
            ),
            d3_forward_closed_pole_group(
                section_refinement_probe.feedline_reference;
                model_role = "feedline_reference",
                section_length_m = 80.0e-6,
            ),
        ]
        fine_grid = d3_forward_pole_aware_frequency_grid(
            slot_hz,
            in_band_poles;
            fine = true,
            closed_pole_groups = closed_pole_groups,
        )
        coarse_grid = d3_forward_pole_aware_frequency_grid(
            slot_hz,
            in_band_poles;
            fine = false,
            closed_pole_groups = closed_pole_groups,
        )
        grid_diagnostic = (
            slot_hz = slot_hz,
            fine_samples = length(fine_grid.frequency_hz),
            coarse_samples = length(coarse_grid.frequency_hz),
            pole_frequency_hz = [row.frequency_hz for row in in_band_poles],
            pole_linewidth_hz = [row.linewidth_hz for row in in_band_poles],
            fine_planned_local_step_hz = [
                row["planned_local_step_hz"] for row in fine_grid.evidence["open_poles"]
            ],
            fine_planned_samples_per_linewidth = [
                row["planned_samples_per_physical_linewidth"]
                for row in fine_grid.evidence["open_poles"]
            ],
            fine_planned_effective_samples_per_linewidth = [
                row["planned_samples_per_effective_linewidth"]
                for row in fine_grid.evidence["open_poles"]
            ],
            fine_open_minimum_center_detuning_hz = [
                row["minimum_center_detuning_hz"] for row in fine_grid.evidence["open_poles"]
            ],
            fine_closed_pole_exclusion_count =
                length(fine_grid.evidence["closed_pole_exclusions"]),
            linewidth_floor_hz = fine_grid.evidence["linewidth_floor_hz"],
        )
        @info "Built pole-aware response grids" grid_diagnostic
        selected_search_candidate = nothing
        for (index, row) in enumerate(search.history)
            selected = index - 1 == search.best_iteration
            candidate = d3_forward_search_candidate(
                row,
                slot_target,
                selected_case;
                stage = "physical_fine_tuning",
                candidate_id = "fine__$(selected_case.id)__$(round(Int, slot_hz))__$(index - 1)",
                selected = selected,
                grid_evidence = selected ?
                    (fine = fine_grid.evidence, coarse = coarse_grid.evidence) : nothing,
            )
            push!(search_candidates, candidate)
            selected && (selected_search_candidate = candidate)
        end
        selected_candidate = something(selected_search_candidate)

        fine_response = d3_forward_response_result(
            selected_case,
            final.design,
            slot_target;
            section_length_m = 40.0e-6,
            frequency_grid_hz = fine_grid.frequency_hz,
            floating_qubit_nominal = inputs.qubit_input.model,
            feedline = inputs.feedline,
            feedline_length_m = feedline_length_m,
            cext_f = final.kappa.cext_f,
        )
        coarse_section_response = d3_forward_response_result(
            selected_case,
            final.design,
            slot_target;
            section_length_m = 80.0e-6,
            frequency_grid_hz = fine_grid.frequency_hz,
            floating_qubit_nominal = inputs.qubit_input.model,
            feedline = inputs.feedline,
            feedline_length_m = feedline_length_m,
            cext_f = final.kappa.cext_f,
        )
        coarse_grid_response = d3_forward_response_result(
            selected_case,
            final.design,
            slot_target;
            section_length_m = 40.0e-6,
            frequency_grid_hz = coarse_grid.frequency_hz,
            floating_qubit_nominal = inputs.qubit_input.model,
            feedline = inputs.feedline,
            feedline_length_m = feedline_length_m,
            cext_f = final.kappa.cext_f,
        )
        response_payload = d3_forward_response_payload(fine_response, fine_grid.evidence)
        handoff = final.handoff
        exact_six_trace = d3_forward_exact_six_trace(
            final.matching.elements,
            inputs.qubit_input.model,
            inputs.feedline,
            feedline_length_m,
            final.kappa.cext_f,
            fine_response.equivalent.frequency_hz,
        )
        exact_six_reference = _d3_forward_response_trace(
            _d3_forward_feedline_reference_plan(
                final.design;
                section_length_m = feedline_length_m / 2,
                feedline = inputs.feedline,
                feedline_length_m = feedline_length_m,
            ),
            fine_response.equivalent.frequency_hz;
            z_closure_absolute_tolerance_ohm =
                D3_FORWARD_Z_CLOSURE_ABSOLUTE_TOLERANCE_OHM,
            s_closure_absolute_tolerance = D3_FORWARD_S_CLOSURE_ABSOLUTE_TOLERANCE,
            closure_relative_tolerance = D3_FORWARD_CLOSURE_RELATIVE_TOLERANCE,
        )
        exact_six_payload = d3_forward_exact_six_response_payload(
            exact_six_trace,
            exact_six_reference,
            fine_response,
            handoff,
        )
        kappa_provenance = Dict(
            "method" => "filter_only_matched_open_pole_linewidth",
            "source_model_id" => "response-matched-filter-two-pi-$(round(Int, slot_hz))",
            "source_pole_frequency_hz" => real(final.kappa.pole.frequency_hz),
            "source_pole_linewidth_hz" => final.kappa.kappa_hz,
            "source_sha256" => final.kappa.pole.hashes.state_matrix_sha256,
        )
        design_id = String(final.design.id)
        push!(slots, Dict(
            "slot_hz" => slot_hz,
            "full_coordinate_handoff" => handoff,
            "exact_six_coordinate_response" => exact_six_payload,
            "kappa_p_external_hz" => final.kappa.kappa_hz,
            "kappa_provenance" => kappa_provenance,
            "response" => response_payload,
            "refinement" => d3_forward_refinement_payload(
                coarse_section_response,
                coarse_grid_response,
                fine_response,
            ),
            "provenance" => Dict(
                "case_id" => String(selected_case.id),
                "design_id" => design_id,
				"full_coordinate_handoff_semantic_sha256" =>
					D3SemanticHash.semantic_value_sha256(handoff),
				"exact_six_coordinate_response_semantic_sha256" =>
					D3SemanticHash.semantic_value_sha256(exact_six_payload),
				"response_semantic_sha256" =>
					D3SemanticHash.semantic_value_sha256(response_payload),
                "q2d_pair_artifact_sha256" => inputs.hashes["q2d_pair"],
                "q2d_single_artifact_sha256" => inputs.hashes["q2d_single"],
                "selected_search_candidate_id" => selected_candidate["candidate_id"],
                "selected_search_candidate_semantic_sha256" =>
                    D3SemanticHash.semantic_value_sha256(selected_candidate),
            ),
        ))
    end

    output = abspath(String(output_path))
    evidence_path = joinpath(dirname(output), "$(splitext(basename(output))[1]).search-evidence.json")
    input_identity = d3_forward_input_identity(inputs.hashes)
    run_digest = d3_forward_string_sha256(input_identity)
    run_id = "d3-forward-$(run_digest[1:16])"
    evidence = Dict(
        "schema_version" => "d3-forward-design-search-evidence.v1",
        "artifact_id" => "$(run_id)-design-search-evidence",
        "status" => "complete",
        "candidates" => search_candidates,
    )
    d3_forward_atomic_write_json(evidence_path, evidence)
    execution_sha = d3_forward_file_sha256(@__FILE__)
    payload = Dict(
        "schema_version" => D3_FORWARD_RUN_SCHEMA,
        "status" => "complete",
        "bare_fit_node_state" => "disabled_not_implemented",
        "bare_fit_execution_policy" => "must_not_run",
        "vf_settings" => Dict(
            "n_resonators" => 3,
            "background_poles" => [0, 1, 2],
            "max_iterations" => 50,
            "min_q" => 0.0,
            "restrict_to_input_span" => true,
        ),
        "slots" => slots,
        "provenance" => Dict(
            "run_id" => run_id,
            "source_artifact_id" => input_identity,
            "runtime_revision" => execution_sha,
            "q2d_route" => D3_FORWARD_Q2D_ROUTE,
        ),
        "design_search_evidence" => Dict(
            "schema_version" => "d3-forward-design-search-evidence.v1",
            "artifact_id" => evidence["artifact_id"],
            "relative_path" => relpath(evidence_path, dirname(output)),
            "sha256" => d3_forward_file_sha256(evidence_path),
        ),
    )
    d3_forward_validate_primary_payload(payload)
    d3_forward_atomic_write_json(output, payload)
    return (primary = output, search_evidence = evidence_path)
end
