# Task-local root/derivative and deterministic-LC qualification for the exact
# W7/S6 historical-length witness. It consumes the immutable spatial receipt
# and does not build the Equivalent or Full-QRP arms.

using Dates

const LC_SOURCE_DIR = @__DIR__
const LC_SOURCE_PATH = abspath(@__FILE__)
const LC_EVIDENCE_ID = "d3-w7s6-singleton-frequency-priority-lc-readback-v1"
const REQUIRED_LC_WORKBENCH_ANCESTOR = "54ff16a70d9cbbc89b83d635d64767fded02802e"
const REQUIRED_SPATIAL_RECEIPT_SHA256 =
    "8917bd26e96c57711e56f8388bdc6e54cb2fc5a150a559e546717e53770d2566"
const ROOT_ABSOLUTE_TOLERANCE_RAD_S = 2π * 1.25
const ROOT_RELATIVE_TOLERANCE = 1.0e-13
const ROOT_MAX_ITERATIONS = 128
const DERIVATIVE_STEP_FRACTION = 1.0e-6
const DIAGONAL_DERIVATIVE_TOLERANCE = 1.0e-3
const NOTCH_DERIVATIVE_TOLERANCE = 5.0e-2
const REACTIVE_PURITY_TOLERANCE = 1.0e-7
const ROOT_RESIDUAL_TOLERANCE = 2.0e-3
const DIAGONAL_EXTRACTION_TOLERANCE = 1.0e-3
const NOTCH_EXTRACTION_TOLERANCE = 5.0e-2
const Z21_RESIDUAL_OHM = 0.01

include(joinpath(LC_SOURCE_DIR, "d3_w7_s6_nonmonotonicity_falsification.jl"))

const LC_OPERATIONAL_COUNTS = (r_short=61, r_open=39, p_short=45, p_open=52)
const LC_REFERENCE_COUNTS = (r_short=974, r_open=610, p_short=706, p_open=827)
const LC_OPERATIONAL_STATE = grid_state(
    LC_OPERATIONAL_COUNTS,
    18;
    origin="lc-readback-operational",
)
const LC_REFERENCE_STATE = grid_state(
    LC_REFERENCE_COUNTS,
    576;
    origin="lc-readback-retained-reference",
)

complex_record(value) = (
    real=real(ComplexF64(value)),
    imag=imag(ComplexF64(value)),
    abs=abs(ComplexF64(value)),
)

function expected_state_record(spatial, state)
    matches = [record for record in spatial.experiment.states if String(record.state.id) == state.id]
    length(matches) == 1 || error("Spatial receipt does not contain exactly one $(state.id) state.")
    record = only(matches)
    String(record.status) == "COMPLETE" || error("Spatial state $(state.id) is incomplete.")
    return record
end

function verify_spatial_receipt(path)
    sha256_file(path) == REQUIRED_SPATIAL_RECEIPT_SHA256 ||
        error("Spatial receipt SHA mismatch.")
    spatial = JSON3.read(read(path, String))
    String(spatial.schema_version) == "spatial-discretization-evidence.v1" ||
        error("Unexpected spatial receipt schema.")
    String(spatial.evidence_id) == EVIDENCE_ID || error("Unexpected spatial evidence identity.")
    String(spatial.experiment.status) == "SPATIAL_DISCRETIZATION_ELIGIBLE" ||
        error("Spatial receipt is not eligible.")
    String(spatial.source.q2d_artifact_sha256) == REQUIRED_Q2D_SHA256 ||
        error("Spatial receipt Q2D identity mismatch.")
    String(spatial.source.extractor_sha256) ==
        sha256_file(joinpath(SOURCE_DIR, "d3_signed_zero_midpoint.jl")) ||
        error("Spatial receipt extractor identity mismatch.")
    sha256_file(SOURCE_PATH) == REQUIRED_CONVERGENCE_RUNNER_SHA256 ||
        error("Integrated convergence runner differs from the spatial receipt source.")
    minimum = spatial.experiment.minimum_operational_grid
    reference = spatial.experiment.retained_joint_reference
    String(minimum.state_id) == LC_OPERATIONAL_STATE.id ||
        error("Spatial receipt operational state changed.")
    String(reference.state_id) == LC_REFERENCE_STATE.id ||
        error("Spatial receipt reference state changed.")
    return spatial
end

function verify_lc_sources(spatial_path)
    sources = verify_sources()
    head = sources.workbench_revision
    success(`git -C $REPOSITORY_ROOT merge-base --is-ancestor $REQUIRED_LC_WORKBENCH_ANCESTOR $head`) ||
        error("Workbench HEAD does not contain the integrated W7/S6 evidence package.")
    return (sources=sources, spatial=verify_spatial_receipt(spatial_path))
end

function state_identity_checks(record, state, diagonal, physical)
    actual = actual_grid_record(state, diagonal, physical)
    checks = (
        state_id=String(record.state.id) == state.id,
        outer_counts=all(
            Int(getproperty(record.state.outer_counts, name)) == getproperty(state.outer_counts, name)
            for name in OUTER_NAMES
        ),
        mtl_count=Int(record.state.mtl_count) == state.mtl_count,
        breakpoint_sha256=String(record.grid.breakpoint_sha256) == actual.breakpoint_sha256,
        diagonal_capacitance_sha256=
            String(record.invariants.diagonal.capacitance_sha256) ==
            diagonal.probe.matrix_gate.capacitance_sha256,
        diagonal_inverse_inductance_sha256=
            String(record.invariants.diagonal.inverse_inductance_sha256) ==
            diagonal.probe.matrix_gate.inverse_inductance_sha256,
        physical_capacitance_sha256=
            String(record.invariants.physical.capacitance_sha256) ==
            physical.probe.matrix_gate.capacitance_sha256,
        physical_inverse_inductance_sha256=
            String(record.invariants.physical.inverse_inductance_sha256) ==
            physical.probe.matrix_gate.inverse_inductance_sha256,
        terminal_order=Tuple(String.(record.grid.terminal_order)) == ("P_r", "P_p"),
        matrix_validation=all(
            String(invariant.status) == "PASS" &&
            Bool(invariant.capacitance_positive_definite) &&
            Bool(invariant.inverse_inductance_positive_semidefinite)
            for invariant in (record.invariants.diagonal, record.invariants.physical)
        ),
    )
    return actual, checks
end

function angular_responses(diagonal, physical)
    y(omega) = terminal_admittance(diagonal.probe, Float64(omega) / (2π))
    z21(omega) = inv(terminal_admittance(physical.probe, Float64(omega) / (2π)))[2, 1]
    return (
        f_r=omega -> y(omega)[1, 1],
        f_p=omega -> y(omega)[2, 2],
        f_n=z21,
        y=y,
    )
end

function root_and_derivative(observable, response, midpoint_receipt)
    String(midpoint_receipt.status) == "PASS" || error("Midpoint receipt is not PASS.")
    lower_hz = Float64(midpoint_receipt.lower_endpoint.frequency_hz)
    upper_hz = Float64(midpoint_receipt.upper_endpoint.frequency_hz)
    lower = 2π * lower_hz
    upper = 2π * upper_hz
    root = bracketed_bisection(
        omega -> imag(response(omega)),
        [lower, upper];
        absolute_tolerance=ROOT_ABSOLUTE_TOLERANCE_RAD_S,
        relative_tolerance=ROOT_RELATIVE_TOLERANCE,
        max_iterations=ROOT_MAX_ITERATIONS,
    )
    h = DERIVATIVE_STEP_FRACTION * root
    sample_omegas = (minus_h=root - h, minus_h2=root - h / 2, plus_h2=root + h / 2, plus_h=root + h)
    samples_inside = all(lower <= omega <= upper for omega in values(sample_omegas))
    samples = NamedTuple{keys(sample_omegas)}(Tuple(response(omega) for omega in values(sample_omegas)))
    finite_samples = all(value -> isfinite(real(value)) && isfinite(imag(value)), values(samples))
    d_h = (samples.plus_h - samples.minus_h) / (2h)
    d_h2 = (samples.plus_h2 - samples.minus_h2) / h
    step_change = abs(d_h2 - d_h) / max(abs(d_h2), floatmin(Float64))
    step_tolerance = observable == :f_n ?
        NOTCH_DERIVATIVE_TOLERANCE : DIAGONAL_DERIVATIVE_TOLERANCE
    purity = abs(real(d_h2)) / max(abs(imag(d_h2)), floatmin(Float64))
    root_value = response(root)
    residual_scale = max(
        abs(samples.minus_h2),
        abs(samples.plus_h2),
        abs(d_h2) * h / 2,
        floatmin(Float64),
    )
    residual = abs(root_value) / residual_scale
    midpoint_hz = Float64(midpoint_receipt.midpoint_frequency_hz)
    checks = (
        same_bracket=lower <= root <= upper,
        midpoint_distance_hz=abs(root / (2π) - midpoint_hz) <= Float64(midpoint_receipt.half_width_hz),
        stencil_inside_bracket=samples_inside,
        finite_samples=finite_samples,
        derivative_step_convergence=step_change <= step_tolerance,
        reactive_purity=purity <= REACTIVE_PURITY_TOLERANCE,
        normalized_root_residual=residual <= ROOT_RESIDUAL_TOLERANCE,
    )
    return (
        observable=String(observable),
        authoritative_midpoint_receipt=midpoint_receipt,
        construction_anchor_frequency_hz=root / (2π),
        bracket_hz=(lower_hz, upper_hz),
        h_rad_s=h,
        samples=(
            minus_h=complex_record(samples.minus_h),
            minus_h2=complex_record(samples.minus_h2),
            plus_h2=complex_record(samples.plus_h2),
            plus_h=complex_record(samples.plus_h),
        ),
        root_value=complex_record(root_value),
        derivative_h=complex_record(d_h),
        derivative_h2=complex_record(d_h2),
        derivative_step_relative_change=step_change,
        derivative_step_tolerance=step_tolerance,
        reactive_purity_relative=purity,
        normalized_root_residual=residual,
        checks=checks,
        passed=all(value -> value isa Bool ? value : true, values(checks)),
        root_rad_s=root,
        derivative=d_h2,
    )
end

function full_dynamic_pole_certificate(model, lower_hz, upper_hz)
    omega_upper = 2π * Float64(upper_hz)
    blocks = dynamic_blocks(model, upper_hz)
    dynamic = Symmetric([sparse(blocks.dtt) blocks.dti; blocks.dit blocks.dii])
    factor = cholesky(dynamic; check=false)
    passed = issuccess(factor)
    return (
        status=passed ? "PASS" : "FAIL",
        method="sparse Cholesky of full K - omega_upper^2*C",
        lower_frequency_hz=Float64(lower_hz),
        upper_frequency_hz=Float64(upper_hz),
        dimension=size(dynamic, 1),
        upper_dynamic_positive_definite=passed,
        full_capacitance_spd=true,
    )
end

function physical_formulation_gate(model, bracket, anchor)
    frequencies = unique(Float64[
        bracket.lower_endpoint.frequency_hz,
        bracket.upper_endpoint.frequency_hz,
        anchor.construction_anchor_frequency_hz - anchor.h_rad_s / (2π),
        anchor.construction_anchor_frequency_hz - anchor.h_rad_s / (4π),
        anchor.construction_anchor_frequency_hz + anchor.h_rad_s / (4π),
        anchor.construction_anchor_frequency_hz + anchor.h_rad_s / (2π),
    ])
    points = [formulation_point(model, frequency) for frequency in frequencies]
    endpoints = points[1:2]
    checks = (
        operator_agreement=all(point.checks.operator_agreement for point in points),
        backward_residual=all(point.checks.backward_residual for point in points),
        determinant_finite_nonzero=all(point.checks.determinant_finite_nonzero for point in points),
        y21_signed_crossing=strict_opposite_sign(endpoints[1].y21.imag, endpoints[2].y21.imag),
        z21_signed_crossing=strict_opposite_sign(
            endpoints[1].terminal_schur_z21.imag,
            endpoints[2].terminal_schur_z21.imag,
        ),
        determinant_side_consistent=signbit(endpoints[1].determinant_y.real) ==
            signbit(endpoints[2].determinant_y.real),
    )
    return (points=points, checks=checks, passed=all(values(checks)))
end

function qualify_lc_state(lines, spatial_record, state)
    diagonal = build_model(lines, state; diagonal=true)
    physical = build_model(lines, state; diagonal=false)
    actual_grid, identity_checks = state_identity_checks(
        spatial_record,
        state,
        diagonal,
        physical,
    )
    responses = angular_responses(diagonal, physical)
    anchors = (
        f_r=root_and_derivative(:f_r, responses.f_r, spatial_record.extraction.f_r),
        f_p=root_and_derivative(:f_p, responses.f_p, spatial_record.extraction.f_p),
        f_n=root_and_derivative(:f_n, responses.f_n, spatial_record.extraction.f_n),
    )
    diagonal_poles = (
        f_r=interior_pole_certificate(
            diagonal.probe,
            anchors.f_r.bracket_hz[1],
            anchors.f_r.bracket_hz[2],
        ),
        f_p=interior_pole_certificate(
            diagonal.probe,
            anchors.f_p.bracket_hz[1],
            anchors.f_p.bracket_hz[2],
        ),
    )
    physical_pole = full_dynamic_pole_certificate(
        physical.probe,
        anchors.f_n.bracket_hz[1],
        anchors.f_n.bracket_hz[2],
    )
    formulations = physical_formulation_gate(
        physical.probe,
        spatial_record.extraction.f_n,
        anchors.f_n,
    )
    omega_r = anchors.f_r.root_rad_s
    omega_p = anchors.f_p.root_rad_s
    omega_n = anchors.f_n.root_rad_s
    c_r = -imag(anchors.f_r.derivative) / 2
    c_p = -imag(anchors.f_p.derivative) / 2
    l_r = 1 / (omega_r^2 * c_r)
    l_p = 1 / (omega_p^2 * c_p)
    y_at_n = responses.y(omega_n)
    y_r_at_n = y_at_n[1, 1]
    y_p_at_n = y_at_n[2, 2]
    y_r_purity = abs(real(y_r_at_n)) / max(abs(imag(y_r_at_n)), floatmin(Float64))
    y_p_purity = abs(real(y_p_at_n)) / max(abs(imag(y_p_at_n)), floatmin(Float64))
    c_n_star = anchors.f_n.derivative * y_r_at_n * y_p_at_n / (-2im)
    c_n_purity = abs(imag(c_n_star)) / max(abs(real(c_n_star)), floatmin(Float64))
    c_n = real(c_n_star)
    l_n = 1 / (omega_n^2 * c_n)
    z_root = ComplexF64(
        anchors.f_n.root_value.real + im * anchors.f_n.root_value.imag,
    )
    lc = (Cr_f=c_r, Lr_h=l_r, Cp_f=c_p, Lp_h=l_p, Cn_f=c_n, Ln_h=l_n)
    checks = (
        identity=all(values(identity_checks)),
        anchor_and_derivative=all(anchor.passed for anchor in values(anchors)),
        diagonal_poles=all(String(pole.status) == "PASS" for pole in values(diagonal_poles)),
        physical_pole=String(physical_pole.status) == "PASS",
        physical_formulations=formulations.passed,
        y_r_at_notch_purity=y_r_purity <= REACTIVE_PURITY_TOLERANCE,
        y_p_at_notch_purity=y_p_purity <= REACTIVE_PURITY_TOLERANCE,
        c_n_star_purity=c_n_purity <= REACTIVE_PURITY_TOLERANCE,
        z21_real_residual=abs(real(z_root)) <= Z21_RESIDUAL_OHM,
        z21_imag_residual=abs(imag(z_root)) <= Z21_RESIDUAL_OHM,
        z21_abs_residual=abs(z_root) <= Z21_RESIDUAL_OHM,
        positive_finite_lc=all(value -> isfinite(value) && value > 0, values(lc)),
    )
    passed = all(values(checks))
    return (
        status=passed ? "PASS" : "NOT_EVALUABLE",
        state=state,
        actual_grid=actual_grid,
        identity_checks=identity_checks,
        midpoint_receipts=(
            f_r=spatial_record.extraction.f_r,
            f_p=spatial_record.extraction.f_p,
            f_n=spatial_record.extraction.f_n,
        ),
        anchors=anchors,
        pole_certificates=(diagonal=diagonal_poles, physical=physical_pole),
        physical_formulation=formulations,
        bridge_inputs=(
            y_r_diag_at_notch=complex_record(y_r_at_n),
            y_p_diag_at_notch=complex_record(y_p_at_n),
            y_r_purity_relative=y_r_purity,
            y_p_purity_relative=y_p_purity,
            Cn_star=complex_record(c_n_star),
            Cn_star_purity_relative=c_n_purity,
        ),
        lc_readback=lc,
        checks=checks,
    )
end

function relative_delta(reference, operational)
    isfinite(abs(operational)) && !iszero(abs(operational)) || return Inf
    return abs(reference - operational) / abs(operational)
end

function extraction_comparison(operational, reference)
    derivative_deltas = (
        dY_r_domega=relative_delta(
            reference.anchors.f_r.derivative,
            operational.anchors.f_r.derivative,
        ),
        dY_p_domega=relative_delta(
            reference.anchors.f_p.derivative,
            operational.anchors.f_p.derivative,
        ),
        dZ21_domega=relative_delta(
            reference.anchors.f_n.derivative,
            operational.anchors.f_n.derivative,
        ),
        Cn_star=relative_delta(
            ComplexF64(
                reference.bridge_inputs.Cn_star.real + im * reference.bridge_inputs.Cn_star.imag,
            ),
            ComplexF64(
                operational.bridge_inputs.Cn_star.real + im * operational.bridge_inputs.Cn_star.imag,
            ),
        ),
    )
    lc_deltas = NamedTuple{keys(operational.lc_readback)}(
        Tuple(
            relative_delta(
                getproperty(reference.lc_readback, name),
                getproperty(operational.lc_readback, name),
            )
            for name in keys(operational.lc_readback)
        ),
    )
    derivative_checks = (
        dY_r_domega=derivative_deltas.dY_r_domega <= DIAGONAL_EXTRACTION_TOLERANCE,
        dY_p_domega=derivative_deltas.dY_p_domega <= DIAGONAL_EXTRACTION_TOLERANCE,
        dZ21_domega=derivative_deltas.dZ21_domega <= NOTCH_EXTRACTION_TOLERANCE,
        Cn_star=derivative_deltas.Cn_star <= NOTCH_EXTRACTION_TOLERANCE,
    )
    diagonal_lc_checks = (
        Cr_f=lc_deltas.Cr_f <= DIAGONAL_EXTRACTION_TOLERANCE,
        Lr_h=lc_deltas.Lr_h <= DIAGONAL_EXTRACTION_TOLERANCE,
        Cp_f=lc_deltas.Cp_f <= DIAGONAL_EXTRACTION_TOLERANCE,
        Lp_h=lc_deltas.Lp_h <= DIAGONAL_EXTRACTION_TOLERANCE,
    )
    notch_lc_checks = (
        Cn_f=lc_deltas.Cn_f <= NOTCH_EXTRACTION_TOLERANCE,
        Ln_h=lc_deltas.Ln_h <= NOTCH_EXTRACTION_TOLERANCE,
    )
    return (
        derivative_and_c_n_star_deltas_fraction=derivative_deltas,
        derivative_and_c_n_star_deltas_percent=map(value -> 100value, derivative_deltas),
        derivative_and_c_n_star_checks=derivative_checks,
        lc_deltas_fraction=lc_deltas,
        lc_deltas_percent=map(value -> 100value, lc_deltas),
        diagonal_lc_checks=diagonal_lc_checks,
        notch_lc_checks=notch_lc_checks,
        passed=all(values(derivative_checks)) &&
               all(values(diagonal_lc_checks)) &&
               all(values(notch_lc_checks)),
    )
end

function first_blocker(operational, reference, comparison)
    operational.status == "PASS" || return "operational root/derivative/LC qualification failed"
    reference.status == "PASS" || return "retained-reference root/derivative/LC qualification failed"
    comparison.passed || return "operational-to-reference quantity-specific stability gate failed"
    return nothing
end

function write_lc_output(output_directory, receipt)
    ispath(output_directory) && error("LC qualification output already exists: $(output_directory)")
    parent = dirname(output_directory)
    mkpath(parent)
    temporary = mktempdir(parent; prefix=".$(basename(output_directory)).building-", cleanup=false)
    try
        open(joinpath(temporary, "root-derivative-lc-readback.v1.json"), "w") do io
            JSON3.pretty(io, receipt)
            println(io)
        end
        mv(temporary, output_directory)
    catch
        isdir(temporary) && rm(temporary; recursive=true, force=true)
        rethrow()
    end
end

function lc_readback_main()
    length(ARGS) == 2 || error(
        "Usage: julia d3_w7_s6_lc_readback_qualification.jl <spatial-receipt> <output-directory>",
    )
    spatial_path = abspath(ARGS[1])
    output_directory = abspath(ARGS[2])
    verified = verify_lc_sources(spatial_path)
    authority = load_d3_continuous_ground_q2d_input(Q2D_PATH)
    lines = bind_d3_rev10_q2d_input(
        authority;
        section_length_m=BASE_CPW_SECTION_M,
        mtl_section_length_m=BASE_MTL_SECTION_M,
    )
    operational_record = expected_state_record(verified.spatial, LC_OPERATIONAL_STATE)
    reference_record = expected_state_record(verified.spatial, LC_REFERENCE_STATE)
    operational = qualify_lc_state(lines, operational_record, LC_OPERATIONAL_STATE)
    reference = qualify_lc_state(lines, reference_record, LC_REFERENCE_STATE)
    comparison = extraction_comparison(operational, reference)
    blocker = first_blocker(operational, reference, comparison)
    passed = isnothing(blocker)
    receipt = (
        schema_version="d3-root-derivative-lc-readback.v1",
        evidence_id=LC_EVIDENCE_ID,
        generated_at_utc=string(now(UTC)),
        lifecycle_state="ACCEPTED",
        data_class="project-internal",
        authority_status="diagnostic_only",
        promotion_eligible=false,
        final_status=passed ? "PASS" : "NOT_EVALUABLE",
        first_blocker=blocker,
        source=(
            root_revision="0ae83b506c5c0ce357eeb707c6d1c54cdacce857",
            workbench_revision=verified.sources.workbench_revision,
            runner_sha256=sha256_file(LC_SOURCE_PATH),
            spatial_receipt_sha256=sha256_file(spatial_path),
            convergence_runner_sha256=sha256_file(SOURCE_PATH),
            extractor_sha256=sha256_file(joinpath(SOURCE_DIR, "d3_signed_zero_midpoint.jl")),
            q2d_artifact_sha256=verified.sources.q2d_sha256,
            q2d_payload_sha256=lines.q2d_authority.payload_sha256,
            orpen_producer_revision=REQUIRED_ORPEN_PRODUCER_REVISION,
        ),
        contract=(
            authoritative_frequency_observable="accepted 0.25-MHz signed-bracket midpoint",
            construction_anchor="same-bracket 1.25-Hz bisection root",
            derivative_step_fraction=DERIVATIVE_STEP_FRACTION,
            diagonal_derivative_step_tolerance=DIAGONAL_DERIVATIVE_TOLERANCE,
            notch_derivative_step_tolerance=NOTCH_DERIVATIVE_TOLERANCE,
            reactive_purity_tolerance=REACTIVE_PURITY_TOLERANCE,
            root_residual_tolerance=ROOT_RESIDUAL_TOLERANCE,
            diagonal_extraction_stability_tolerance=DIAGONAL_EXTRACTION_TOLERANCE,
            notch_extraction_stability_tolerance=NOTCH_EXTRACTION_TOLERANCE,
            c_n_l_n_extraction_stability_tolerance=NOTCH_EXTRACTION_TOLERANCE,
            terminal_order=("P_r", "P_p"),
            time_convention="exp(-i*omega*t)",
            loss_model="R'=G'=0 downstream lossless-circuit assumption",
        ),
        candidate=(id=CANDIDATE_ID, lengths=LENGTHS, u_idc="NOT_SUPPLIED_AND_UNCONSUMED"),
        operational=operational,
        retained_reference=reference,
        comparison=comparison,
        operational_lc_tuple=passed ? operational.lc_readback : nothing,
        nonclaims=(
            "not a replacement for the accepted midpoint frequency observables",
            "not Equivalent-arm or Experiment-A comparison evidence",
            "not optimizer or Full-QRP grid eligibility",
            "not Stage-2/Stage-3 closure",
            "not a Rev10 slot result",
            "not promotion or publication evidence",
        ),
    )
    write_lc_output(output_directory, receipt)
    progress("LC_READBACK_DONE $(output_directory) status=$(receipt.final_status)")
end

if abspath(PROGRAM_FILE) == abspath(@__FILE__)
    lc_readback_main()
end
