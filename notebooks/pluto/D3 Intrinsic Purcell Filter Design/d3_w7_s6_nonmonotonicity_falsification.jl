# Task-local falsification of the anomalous W7/S6 MTL and Single-Trace counts.
# It preserves the authoritative midpoint extractor and compares two independent
# linear-algebra formulations on the identical conservative C/K matrices.

using Dates
using LinearAlgebra
using SHA
using SparseArrays
using SuperconductingCircuitsCore

const FALSIFIER_SOURCE_DIR = @__DIR__
const FALSIFIER_SOURCE_PATH = abspath(@__FILE__)
const REQUIRED_CONVERGENCE_RECEIPT_SHA256 =
    "212ae923c757e21bba0ea045ac775346d79eb882fbe3e783fd3461b4e10bea09"
const REQUIRED_CONVERGENCE_RUNNER_SHA256 =
    "799261f6bd05e1769311f244f4307aec44964872b9230838c7ef6b56815187b2"
const OPERATOR_RELATIVE_TOLERANCE = 1.0e-9
const BACKWARD_RESIDUAL_TOLERANCE = 1.0e-10

include(joinpath(FALSIFIER_SOURCE_DIR, "d3_w7_s6_spatial_convergence.jl"))

function dynamic_blocks(model::ProbeModel, frequency_hz)
    omega = 2π * Float64(frequency_hz)
    return (
        omega=omega,
        dtt=model.ktt - omega^2 * model.ctt,
        dti=model.kti - omega^2 * model.cti,
        dit=model.kit - omega^2 * model.cit,
        dii=model.kii - omega^2 * model.cii,
    )
end

function full_node_current_injection(model::ProbeModel, frequency_hz)
    blocks = dynamic_blocks(model, frequency_hz)
    dynamic = [sparse(blocks.dtt) blocks.dti; blocks.dit blocks.dii]
    source = zeros(ComplexF64, size(dynamic, 1))
    source[1] = -im * blocks.omega
    voltage = dynamic \ source
    residual = dynamic * voltage - source
    residual_scale = max(
        norm(source, Inf),
        opnorm(dynamic, Inf) * norm(voltage, Inf),
        floatmin(Float64),
    )
    return (
        z21=ComplexF64(voltage[2]),
        backward_residual=norm(residual, Inf) / residual_scale,
        dynamic_dimension=size(dynamic, 1),
    )
end

function formulation_point(model::ProbeModel, frequency_hz)
    y = terminal_admittance(model, frequency_hz)
    z_schur = ComplexF64(inv(y)[2, 1])
    full = full_node_current_injection(model, frequency_hz)
    scale = max(abs(z_schur), abs(full.z21), 1.0)
    relative_difference = abs(full.z21 - z_schur) / scale
    determinant = ComplexF64(det(y))
    determinant_scale = max(opnorm(y, Inf)^2, floatmin(Float64))
    return (
        frequency_hz=Float64(frequency_hz),
        terminal_schur_z21=(real=real(z_schur), imag=imag(z_schur), abs=abs(z_schur)),
        full_node_z21=(real=real(full.z21), imag=imag(full.z21), abs=abs(full.z21)),
        operator_relative_difference=relative_difference,
        backward_residual=full.backward_residual,
        y21=(real=real(y[2, 1]), imag=imag(y[2, 1]), abs=abs(y[2, 1]), phase=angle(y[2, 1])),
        determinant_y=(
            real=real(determinant),
            imag=imag(determinant),
            abs=abs(determinant),
            phase=angle(determinant),
            normalized_abs=abs(determinant) / determinant_scale,
        ),
        checks=(
            operator_agreement=relative_difference <= OPERATOR_RELATIVE_TOLERANCE,
            backward_residual=full.backward_residual <= BACKWARD_RESIDUAL_TOLERANCE,
            determinant_finite_nonzero=isfinite(abs(determinant)) && !iszero(abs(determinant)),
        ),
    )
end

function audit_state(lines, state)
    extraction = evaluate_state(lines, state)
    extraction.status == "COMPLETE" || return (
        status="NOT_EVALUABLE",
        state=state,
        extraction=extraction,
        reason="authoritative midpoint extraction failed",
    )
    physical = build_model(lines, state; diagonal=false)
    bracket = extraction.extraction.f_n
    bracket.status == "PASS" || error("Complete state has no passing f_n receipt.")
    lower = bracket.lower_endpoint.frequency_hz
    upper = bracket.upper_endpoint.frequency_hz
    frequencies = Float64[
        lower - FREQUENCY_STEP_HZ,
        lower,
        upper,
        upper + FREQUENCY_STEP_HZ,
    ]
    points = [formulation_point(physical.probe, frequency) for frequency in frequencies]
    endpoint_points = points[2:3]
    y21_crossing = strict_opposite_sign(
        endpoint_points[1].y21.imag,
        endpoint_points[2].y21.imag,
    )
    z21_crossing = strict_opposite_sign(
        endpoint_points[1].terminal_schur_z21.imag,
        endpoint_points[2].terminal_schur_z21.imag,
    )
    determinant_side_consistent = signbit(endpoint_points[1].determinant_y.real) ==
        signbit(endpoint_points[2].determinant_y.real)
    checks = (
        all_operator_points_agree=all(point.checks.operator_agreement for point in points),
        all_backward_residuals_pass=all(point.checks.backward_residual for point in points),
        all_determinants_finite_nonzero=all(
            point.checks.determinant_finite_nonzero for point in points
        ),
        endpoint_y21_signed_crossing=y21_crossing,
        endpoint_z21_signed_crossing=z21_crossing,
        endpoint_determinant_side_consistent=determinant_side_consistent,
        authoritative_unique_bracket=bracket.bracket_count == 1,
        authoritative_branch_identity=bracket.checks.branch_identity_match,
        authoritative_pole_free=bracket.checks.pole_free,
    )
    passed = all(values(checks))
    return (
        status=passed ? "PASS" : "NOT_EVALUABLE",
        state=state,
        values_hz=extraction.values_hz,
        grid=extraction.grid,
        c_k_hashes=extraction.invariants.physical,
        authoritative_notch_receipt=bracket,
        formulation_points=points,
        checks=checks,
    )
end

function audited_states(lines)
    base_outer = density_outer_counts(BASE_CPW_SECTION_M)
    states = [
        grid_state(base_outer, count; origin="mtl-neighbor-falsification")
        for count in 70:73
    ]
    append!(
        states,
        [
            grid_state(allocate_outer_counts(count), 18; origin="single-trace-neighbor-falsification")
            for count in 391:393
        ],
    )
    return [audit_state(lines, state) for state in states]
end

function write_falsification_csv(path, records)
    open(path, "w") do io
        println(
            io,
            "axis,state_id,outer_total,r_short,r_open,p_short,p_open,mtl_count,f_r_hz,f_p_hz,f_n_hz,max_operator_relative_difference,max_backward_residual,status",
        )
        for record in records
            state = record.state
            axis = startswith(state.origin, "mtl") ? "mtl_neighbor" : "single_trace_neighbor"
            maximum_operator = record.status == "PASS" ? maximum(
                point.operator_relative_difference for point in record.formulation_points
            ) : NaN
            maximum_backward = record.status == "PASS" ? maximum(
                point.backward_residual for point in record.formulation_points
            ) : NaN
            values_hz = record.status == "PASS" ? record.values_hz : (f_r=NaN, f_p=NaN, f_n=NaN)
            println(
                io,
                join(
                    (
                        axis,
                        state.id,
                        state.outer_total,
                        state.outer_counts.r_short,
                        state.outer_counts.r_open,
                        state.outer_counts.p_short,
                        state.outer_counts.p_open,
                        state.mtl_count,
                        values_hz.f_r,
                        values_hz.f_p,
                        values_hz.f_n,
                        maximum_operator,
                        maximum_backward,
                        record.status,
                    ),
                    ',',
                ),
            )
        end
    end
end

function write_falsification_output(output_directory, receipt)
    ispath(output_directory) && error("Falsification output already exists: $(output_directory)")
    parent = dirname(output_directory)
    mkpath(parent)
    temporary = mktempdir(parent; prefix=".$(basename(output_directory)).building-", cleanup=false)
    try
        open(joinpath(temporary, "nonmonotonicity-falsification.v1.json"), "w") do io
            JSON3.pretty(io, receipt)
            println(io)
        end
        write_falsification_csv(joinpath(temporary, "neighbor-stencil.csv"), receipt.records)
        mv(temporary, output_directory)
    catch
        isdir(temporary) && rm(temporary; recursive=true, force=true)
        rethrow()
    end
end

function falsification_main()
    length(ARGS) == 2 || error(
        "Usage: julia d3_w7_s6_nonmonotonicity_falsification.jl <convergence-evidence-directory> <output-directory>",
    )
    source_directory = abspath(ARGS[1])
    output_directory = abspath(ARGS[2])
    sources = verify_sources()
    convergence_receipt_path = joinpath(
        source_directory,
        "spatial-discretization-evidence.v1.json",
    )
    sha256_file(convergence_receipt_path) == REQUIRED_CONVERGENCE_RECEIPT_SHA256 ||
        error("The source convergence receipt SHA is wrong.")
    sha256_file(SOURCE_PATH) == REQUIRED_CONVERGENCE_RUNNER_SHA256 ||
        error("The authoritative convergence runner changed after its evidence run.")
    authority = load_d3_continuous_ground_q2d_input(Q2D_PATH)
    lines = bind_d3_rev10_q2d_input(
        authority;
        section_length_m=BASE_CPW_SECTION_M,
        mtl_section_length_m=BASE_MTL_SECTION_M,
    )
    records = audited_states(lines)
    all(record.status == "PASS" for record in records) || error(
        "At least one falsification stencil state is not evaluable.",
    )
    mtl_f_n = [record.values_hz.f_n for record in records if record.state.mtl_count in 70:73]
    cpw_f_n = [record.values_hz.f_n for record in records if record.state.outer_total in 391:393]
    receipt = (
        schema_version="d3-spatial-nonmonotonicity-falsification.v1",
        evidence_id="d3-w7s6-mtl70-73-cpw391-393-nonmonotonicity-falsification-v1",
        generated_at_utc=string(now(UTC)),
        lifecycle_state="CONVERGING",
        data_class="project-internal",
        authority_status="diagnostic_only",
        promotion_eligible=false,
        source=(
            workbench_revision=sources.workbench_revision,
            falsifier_sha256=sha256_file(FALSIFIER_SOURCE_PATH),
            convergence_runner_sha256=sha256_file(SOURCE_PATH),
            convergence_receipt_sha256=sha256_file(convergence_receipt_path),
            q2d_artifact_sha256=sources.q2d_sha256,
            q2d_payload_sha256=lines.q2d_authority.payload_sha256,
            orpen_producer_revision=REQUIRED_ORPEN_PRODUCER_REVISION,
        ),
        contract=(
            mtl_counts=(70, 71, 72, 73),
            single_trace_totals=(391, 392, 393),
            frequency_step_hz=FREQUENCY_STEP_HZ,
            authoritative_extractor="unique adjacent strict signed bracket midpoint",
            independent_formulations=(
                "two-terminal Schur complement",
                "full physical-node current injection",
            ),
            operator_relative_tolerance=OPERATOR_RELATIVE_TOLERANCE,
            backward_residual_tolerance=BACKWARD_RESIDUAL_TOLERANCE,
        ),
        summary=(
            operator_agreement=all(
                record.checks.all_operator_points_agree for record in records
            ),
            branch_and_pole_checks=all(
                record.checks.endpoint_y21_signed_crossing &&
                record.checks.endpoint_z21_signed_crossing &&
                record.checks.endpoint_determinant_side_consistent &&
                record.checks.authoritative_unique_bracket &&
                record.checks.authoritative_branch_identity &&
                record.checks.authoritative_pole_free
                for record in records
            ),
            mtl_neighbor_f_n_hz=mtl_f_n,
            single_trace_neighbor_f_n_hz=cpw_f_n,
            classification="independent-formulation and neighbor-stencil evidence only",
        ),
        records=records,
        nonclaims=(
            "not a change to the authoritative midpoint extractor",
            "not an optimizer envelope",
            "not Full-QRP or Equivalent evidence",
            "not Stage-2/Stage-3 closure",
            "not promotion or publication evidence",
        ),
    )
    write_falsification_output(output_directory, receipt)
    progress("FALSIFICATION_DONE $(output_directory)")
end

if abspath(PROGRAM_FILE) == abspath(@__FILE__)
    falsification_main()
end
