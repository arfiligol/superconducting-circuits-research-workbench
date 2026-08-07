# Task-local executable for one Rev10 direct-Hybridized diagnostic slot.
# It owns orchestration and evidence persistence only; Circuit-owned equations,
# cared outputs, and Objective semantics are consumed without redefinition.

const WORKBENCH_ROOT = normpath(joinpath(@__DIR__, "..", "..", ".."))
const CORE_ROOT = joinpath(
    WORKBENCH_ROOT,
    "core",
    "julia",
    "SuperconductingCircuitsCore",
)
pushfirst!(LOAD_PATH, CORE_ROOT)

using SHA
using SuperconductingCircuitsCore

const JSON3 = SuperconductingCircuitsCore.JSON3
const EXPECTED_MANIFEST_SHA256 =
    "d3b78e9c839ff1e68a1236f762f438fdafe9c5a92d06d28a7d593f5e8787a586"
const EXPECTED_CORE_ENTRY = realpath(joinpath(
    CORE_ROOT,
    "src",
    "SuperconductingCircuitsCore.jl",
))
realpath(pathof(SuperconductingCircuitsCore)) == EXPECTED_CORE_ENTRY || error(
    "Rev10 run must load SuperconductingCircuitsCore from this exact Workbench checkout.",
)

include(joinpath(@__DIR__, "d3_circuit_plans.jl"))
include(joinpath(@__DIR__, "d3_exact_n_response.jl"))
include(joinpath(@__DIR__, "d3_stage_models.jl"))
include(joinpath(@__DIR__, "d3_stage_objectives.jl"))
include(joinpath(@__DIR__, "d3_coupled_optimizer.jl"))
include(joinpath(@__DIR__, "d3_direct_hybridized_spatial_receipt.jl"))

using .D3CoupledOptimizer
using .D3DirectHybridizedSpatialReceipt
using .D3FloatingQubitInput: load_floating_qubit_nominal_input
using .D3IDCInput: d3_idc_mapping_semantic_sha256, load_d3_idc_mapping
using .D3ResonatorInput:
    bind_d3_rev10_q2d_input, load_d3_continuous_ground_q2d_input

file_sha256(path) = open(path, "r") do io
    bytes2hex(SHA.sha256(io))
end

function command_output(args...)
    command = Cmd(collect(String.(args)))
    return strip(read(Cmd(command; dir=WORKBENCH_ROOT), String))
end

function write_new_json(path, payload)
    destination = abspath(String(path))
    ispath(destination) && error("Refusing to overwrite run evidence: $(destination)")
    mkpath(dirname(destination))
    temporary, io = mktemp(dirname(destination); cleanup=false)
    try
        JSON3.pretty(io, payload)
        println(io)
        close(io)
        mv(temporary, destination; force=false)
    catch
        isopen(io) && close(io)
        isfile(temporary) && rm(temporary; force=true)
        rethrow()
    end
    return destination
end

function append_jsonl(path, payload)
    open(path, "a") do io
        JSON3.write(io, payload)
        println(io)
        flush(io)
    end
    return nothing
end

function write_candidate_events(path, history, l0_by_candidate)
    ispath(path) && error("Refusing to overwrite candidate events: $(path)")
    for record in history
        record.cache_hit && continue
        candidate_sha = candidate_sha256(record.candidate)
        if record.evaluation isa ValidEvaluation
            l0 = l0_by_candidate[candidate_sha]
            append_jsonl(path, (
                event="VALID",
                record_id=record.record_id,
                stage=record.stage,
                inner_loop_level=0,
                candidate_sha256=candidate_sha,
                candidate=record.candidate,
                l0_objective_receipt=l0.receipt,
                objective=l0.objective,
            ))
        else
            rejection = record.evaluation
            append_jsonl(path, (
                event="NOT_EVALUABLE",
                record_id=record.record_id,
                stage=record.stage,
                candidate_sha256=candidate_sha,
                candidate=record.candidate,
                code=rejection.code,
                reason=rejection.reason,
                details=rejection.details,
                cost=nothing,
            ))
        end
    end
    return path
end

function candidate_sha256(candidate)
    return bytes2hex(SHA.sha256(codeunits(JSON3.write(candidate))))
end

function exact_namedtuple(mapping, names)
    Set(String.(keys(mapping))) == Set(String.(names)) || error(
        "Mapping fields differ from required fields $(names).",
    )
    return NamedTuple{names}(Tuple(
        Float64(mapping[String(name)]) for name in names
    ))
end

function extraction_profile(manifest, slot_hz)
    extraction = manifest["extraction"]
    policy = extraction["effective_operator_gate_policy"]
    gate_names = (
        :maximum_elimination_condition_number,
        :maximum_relative_elimination_solve_residual,
        :maximum_relative_reciprocity_error,
        :maximum_relative_passivity_violation,
        :maximum_relative_root_residual,
        :maximum_root_growth_rate_hz,
        :minimum_normalized_residue_slope,
        :maximum_relative_coupling_spread,
        :maximum_relative_determinant_closure_error,
    )
    gate_policy = NamedTuple{gate_names}(Tuple(
        Float64(policy[String(name)]) for name in gate_names
    ))
    band = (slot_hz - 50.0e6, slot_hz + 50.0e6)
    bracket = Tuple(Float64.(extraction["notch_bracket_hz"]))
    disposition = extraction["numeric_control_disposition"]
    return (
        readout_effective_root_band_hz=band,
        filter_effective_root_band_hz=band,
        effective_operator_gate_policy=gate_policy,
        notch_frequency_bracket_hz=bracket,
        minimum_q_reference_overlap=
            Float64(extraction["minimum_q_reference_overlap"]),
        minimum_each_rp_subspace_overlap=
            Float64(extraction["minimum_each_rp_subspace_overlap"]),
        minimum_unordered_set_assignment_margin=
            Float64(extraction["minimum_unordered_set_assignment_margin"]),
        numeric_control_disposition=(
            authority=Symbol(disposition["authority"]),
            root_windows=Symbol(disposition["root_windows"]),
            effective_operator_controls=
                Symbol(disposition["effective_operator_controls"]),
            notch_window=Symbol(disposition["notch_window"]),
            overlap_and_assignment_controls=
                Symbol(disposition["overlap_and_assignment_controls"]),
        ),
        complement=:complete_hybridized_complement,
    )
end

function metric_specs(slot_hz)
    return [
        MetricSpec(:fr_eff_complete_complement_rp_hz, slot_hz, 0.5e6, 1.0),
        MetricSpec(:fp_eff_complete_complement_rp_hz, slot_hz, 0.5e6, 1.0),
        MetricSpec(:J_eff_complete_complement_rp_coherent_hz, 5.0e6, 2.0e6, 1.0),
        MetricSpec(:notch_distributed_rp_on_hz, 5.0e9, 10.0e6, 1.0),
        MetricSpec(:kappa_sum_unordered_rp_subspace_hz, 20.0e6, 1.0e6, 1.0),
        MetricSpec(:linewidth_fraction_min_unordered_rp_subspace, 0.5, 0.2, 1.0),
    ]
end

function objective_metrics(cared)
    source = cared["source_profile_identity"]
    model = source["model_identity"]
    return (
        stage_id=:stage2_direct_hybridized,
        model_family=:hybridized_distributed_lumped,
        circuit_plan_sha256=String(model["circuit_plan_sha256"]),
        capacitance_sha256=String(model["capacitance_sha256"]),
        inverse_inductance_sha256=String(model["inverse_inductance_sha256"]),
        selector_sha256=String(model["selector_sha256"]),
        effective_diagonal_frequency_extraction=
            :complete_complement_rp_complex_operator,
        effective_exchange_extraction=
            :complete_complement_rp_complex_midpoint_residue,
        notch_authority=:distributed_rp_on,
        linewidth_pole_scope=:unordered_rp_two_pole_subspace,
        primary_linewidth_extraction=:exact_open_unordered_rp_poles,
        fr_eff_complete_complement_rp_hz=Float64(cared["f_r_eff_hz"]),
        fp_eff_complete_complement_rp_hz=Float64(cared["f_p_eff_hz"]),
        J_eff_complete_complement_rp_coherent_hz=
            Float64(cared["abs_real_J_eff_hz"]),
        notch_distributed_rp_on_hz=Float64(cared["f_n_hz"]),
        kappa_sum_unordered_rp_subspace_hz=
            Float64(cared["unordered_rp_kappa_sum_hz"]),
        linewidth_fraction_min_unordered_rp_subspace=
            Float64(cared["unordered_rp_linewidth_fraction_min"]),
        linewidth_fraction_max_unordered_rp_subspace=
            Float64(cared["unordered_rp_linewidth_fraction_max"]),
    )
end

function optimizer_metrics(metrics)
    return ValidEvaluation((
        fr_eff_complete_complement_rp_hz=
            metrics.fr_eff_complete_complement_rp_hz,
        fp_eff_complete_complement_rp_hz=
            metrics.fp_eff_complete_complement_rp_hz,
        J_eff_complete_complement_rp_coherent_hz=
            metrics.J_eff_complete_complement_rp_coherent_hz,
        notch_distributed_rp_on_hz=metrics.notch_distributed_rp_on_hz,
        kappa_sum_unordered_rp_subspace_hz=
            metrics.kappa_sum_unordered_rp_subspace_hz,
        linewidth_fraction_min_unordered_rp_subspace=
            metrics.linewidth_fraction_min_unordered_rp_subspace,
    ))
end

function bind_inputs(manifest, q2d_path, q3d_path, idc_path)
    sources = manifest["sources"]
    for (path, key) in (
        (q2d_path, "q2d_artifact_sha256"),
        (q3d_path, "q3d_input_sha256"),
        (idc_path, "idc_mapping_sha256"),
    )
        isfile(path) || error("Required Rev10 input does not exist: $(path)")
        file_sha256(path) == String(sources[key]) || error(
            "Required Rev10 input bytes disagree with manifest field $(key).",
        )
    end
    fixed = manifest["fixed_physical_inputs"]
    idc_model = manifest["idc_length_model"]
    idc_model["model"] == "capacitance_fF=a_fF_per_um*length_um+b_fF" &&
        idc_model["fit_method"] == "ordinary_least_squares_at_selected_gap" &&
        idc_model["outside_source_support"] == "linear_extrapolation" || error(
        "Rev10 IDC length model does not match the Human-directed linear-fit contract.",
    )
    source_support = Tuple(Float64.(idc_model["source_support_um"]))
    evaluation_range = Tuple(Float64.(idc_model["evaluation_range_um"]))
    Float64(idc_model["source_gap_um"]) == Float64(fixed["idc_gap_um"]) || error(
        "Rev10 IDC fit gap and fixed physical gap disagree.",
    )
    idc_variable = only(filter(
        item -> String(item["name"]) == "u_IDC",
        manifest["variables"],
    ))
    evaluation_range == (
        Float64(idc_variable["lower"]),
        Float64(idc_variable["upper"]),
    ) || error("Rev10 IDC evaluation range and optimizer bounds disagree.")
    q2d = bind_d3_rev10_q2d_input(
        load_d3_continuous_ground_q2d_input(q2d_path);
        section_length_m=Float64(fixed["q2d_section_length_m"]),
        mtl_section_length_m=Float64(fixed["q2d_mtl_section_length_m"]),
    )
    q3d = load_floating_qubit_nominal_input(
        q3d_path,
        (; kwargs...) -> (; kwargs...);
        gap_um=Float64(fixed["q3d_gap_um"]),
    )
    idc = load_d3_idc_mapping(
        idc_path;
        gap_um=Float64(fixed["idc_gap_um"]),
        evaluation_length_range_um=evaluation_range,
    )
    idc.source_length_range_um == source_support || error(
        "Rev10 IDC Q3D source-support range disagrees with the manifest.",
    )
    idc.mapping_id == String(sources["idc_runtime_mapping_id"]) || error(
        "Rev10 IDC runtime mapping id disagrees with the manifest.",
    )
    d3_idc_mapping_semantic_sha256(idc) ==
        String(sources["idc_mapping_semantic_sha256"]) || error(
        "Rev10 IDC linear mapping semantics disagree with the manifest.",
    )
    inputs = bind_d3_stage2_direct_hybridized_inputs(
        q2d,
        q3d,
        idc;
        feedline_length_m=Float64(fixed["feedline_length_m"]),
        feedline_n_sections=Int(fixed["feedline_n_sections"]),
        feedline_l_per_m_h=Float64(fixed["feedline_l_per_m_h"]),
        feedline_c_per_m_f=Float64(fixed["feedline_c_per_m_f"]),
        port_resistance_ohm=Float64(fixed["port_resistance_ohm"]),
    )
    inputs.source_identity.canonical_sha256 ==
        String(sources["fixed_input_canonical_sha256"]) || error(
            "Canonical direct-Hybridized fixed input identity is wrong.",
        )
    return inputs
end

function make_evaluator(
    inputs,
    profile,
    slot_hz,
    specs,
    restart_dir,
)
    l0_by_candidate = Dict{String,Any}()
    metadata_lock = ReentrantLock()

    function evaluator(candidate)
        candidate_sha = candidate_sha256(candidate)
        l0 = try
            plan = d3_stage2_direct_hybridized_grid_plan(
                candidate,
                inputs;
                refinement_level=0,
            )
            request = d3_direct_hybridized_spatial_level_request(
                inputs,
                plan,
                profile,
            )
            cared = validate_d3_direct_hybridized_cared_output(
                evaluate_d3_direct_hybridized_cared_output_request(
                    candidate,
                    slot_hz,
                    request.evaluation_input,
                ),
            )
            (
                cared_output=cared,
                request_identity=d3_direct_hybridized_spatial_cache_key(
                    candidate,
                    slot_hz,
                    request,
                ),
            )
        catch exception
            exception isa InterruptException && rethrow()
            if exception isa D3DirectHybridizedSpatialNotEvaluable
                return RejectedEvaluation(
                    exception.code,
                    exception.reason,
                    exception.details,
                )
            end
            if exception isa ErrorException
                return RejectedEvaluation(
                    "direct_l0_candidate_not_evaluable",
                    "Candidate-local direct-Hybridized L0 evaluation failed.",
                    (
                        candidate_sha256=candidate_sha,
                        refinement_level=0,
                        exception_type=string(typeof(exception)),
                        exception=sprint(showerror, exception),
                    ),
                )
            end
            rethrow()
        end

        metrics = objective_metrics(l0.cared_output)
        expected_model = (
            circuit_plan_sha256=metrics.circuit_plan_sha256,
            capacitance_sha256=metrics.capacitance_sha256,
            inverse_inductance_sha256=metrics.inverse_inductance_sha256,
            selector_sha256=metrics.selector_sha256,
        )
        evaluation = optimizer_metrics(metrics)
        objective = d3_stage2_objective(
            metrics,
            slot_hz,
            D3_HUMAN_APPROVED_OBJECTIVE_AUTHORITY,
            expected_model,
        )
        breakdown = cost_breakdown(specs, evaluation)
        isapprox(objective.cost, breakdown.total; rtol=1.0e-14, atol=0.0) ||
            error("Circuit Objective and optimizer scalarization disagree.")
        objective_path = write_new_json(joinpath(
            restart_dir,
            "l0_objective_receipts",
            "$(candidate_sha).json",
        ), (
            schema_version="d3-rev10-direct-hybridized-l0-objective-receipt.v1",
            candidate_sha256=candidate_sha,
            candidate=candidate,
            slot_hz=slot_hz,
            inner_loop_level=0,
            request_identity=l0.request_identity,
            cared_output=l0.cared_output,
            objective=objective,
            promotion="none",
            publication="none",
        ))
        receipt_record = (
            locator=relpath(objective_path, restart_dir),
            sha256=file_sha256(objective_path),
            inner_loop_level=0,
        )
        lock(metadata_lock) do
            l0_by_candidate[candidate_sha] = (
                cared_output=l0.cared_output,
                objective=objective,
                receipt=receipt_record,
            )
        end
        return evaluation
    end
    return evaluator, l0_by_candidate
end

function best_valid(restarts)
    best = nothing
    ordinal = 0
    for restart in restarts
        for record in restart.result.history
            ordinal += 1
            isnothing(record.cost) && continue
            candidate_sha = candidate_sha256(record.candidate)
            l0 = restart.l0_by_candidate[candidate_sha]
            candidate = (
                restart_index=restart.restart_index,
                restart_name=restart.restart_name,
                ordinal=ordinal,
                record=record,
                l0_cared_output=l0.cared_output,
                l0_objective=l0.objective,
                l0_receipt=l0.receipt,
                cma_state=restart.result.cma.state,
            )
            if isnothing(best) || record.cost < best.record.cost
                best = candidate
            end
        end
    end
    return best
end

function validate_selected_candidate_spatially(
    candidate,
    l0_cared_output,
    inputs,
    profile,
    slot_hz,
    authority,
    specs,
    destination,
)
    l0_plan = d3_stage2_direct_hybridized_grid_plan(
        candidate,
        inputs;
        refinement_level=0,
    )
    l0_request = d3_direct_hybridized_spatial_level_request(
        inputs,
        l0_plan,
        profile,
    )
    l0_key = d3_direct_hybridized_spatial_cache_key(candidate, slot_hz, l0_request)
    spatial_cache = Dict{String,Any}(
        l0_key => Dict(
            "cared_output" => deepcopy(l0_cared_output),
            "cared_output_sha256" =>
                D3SemanticHash.semantic_value_sha256(l0_cared_output),
        ),
    )
    evidence = try
        produce_d3_direct_hybridized_spatial_evidence(
            candidate;
            slot_hz=slot_hz,
            objective_authority=authority,
            level_request=(values, slot, level) -> begin
                plan = d3_stage2_direct_hybridized_grid_plan(
                    values,
                    inputs;
                    refinement_level=level,
                )
                d3_direct_hybridized_spatial_level_request(
                    inputs,
                    plan,
                    profile,
                )
            end,
            cache=spatial_cache,
        )
    catch exception
        exception isa InterruptException && rethrow()
        if exception isa D3DirectHybridizedSpatialNotEvaluable
            return (
                status="NOT_VALIDATED",
                spatial_receipt=nothing,
                validated_finest_objective=nothing,
                validated_finest_objective_receipt=nothing,
                failure=(
                    code=exception.code,
                    reason=exception.reason,
                    details=exception.details,
                    cost=nothing,
                ),
            )
        end
        rethrow()
    end

    validation_dir = joinpath(destination, "winner_spatial_validation")
    receipt = write_d3_direct_hybridized_spatial_receipt(
        joinpath(validation_dir, "spatial_receipt.json"),
        evidence,
    )
    authorization = authorize_d3_direct_hybridized_spatial_receipt(
        receipt,
        candidate;
        slot_hz=slot_hz,
        objective_authority=authority,
    )
    metrics = objective_metrics(authorization.cared_output)
    expected_model = (
        circuit_plan_sha256=metrics.circuit_plan_sha256,
        capacitance_sha256=metrics.capacitance_sha256,
        inverse_inductance_sha256=metrics.inverse_inductance_sha256,
        selector_sha256=metrics.selector_sha256,
    )
    evaluation = optimizer_metrics(metrics)
    objective = evaluate_d3_direct_hybridized_objective_with_spatial_evidence(
        authorization,
        candidate,
        authorization.cared_output;
        slot_hz=slot_hz,
        objective_authority=authority,
        objective_evaluator=renewed -> d3_stage2_objective(
            metrics,
            slot_hz,
            D3_HUMAN_APPROVED_OBJECTIVE_AUTHORITY,
            expected_model,
        ),
    )
    breakdown = cost_breakdown(specs, evaluation)
    isapprox(objective.cost, breakdown.total; rtol=1.0e-14, atol=0.0) ||
        error("Spatially validated Objective and optimizer scalarization disagree.")
    identity = d3_direct_hybridized_spatial_receipt_identity(authorization)
    objective_path = write_new_json(
        joinpath(validation_dir, "validated_finest_objective.json"),
        (
            schema_version="d3-rev10-direct-hybridized-validated-finest-objective.v1",
            candidate_sha256=candidate_sha256(candidate),
            candidate=candidate,
            slot_hz=slot_hz,
            spatial_receipt_identity=identity,
            cared_output=authorization.cared_output,
            objective=objective,
            promotion="none",
            publication="none",
        ),
    )
    return (
        status="PASS",
        spatial_receipt=(
            locator=relpath(receipt.path, destination),
            identity=identity,
        ),
        validated_finest_objective=objective,
        validated_finest_objective_receipt=(
            locator=relpath(objective_path, destination),
            sha256=file_sha256(objective_path),
        ),
        failure=nothing,
    )
end

function run_single_slot(manifest_path, q3d_path, idc_path, output_dir, slot_hz)
    manifest_absolute = abspath(String(manifest_path))
    file_sha256(manifest_absolute) == EXPECTED_MANIFEST_SHA256 || error(
        "Run manifest bytes differ from the Human-approved task manifest.",
    )
    manifest = JSON3.read(read(manifest_absolute, String), Dict{String,Any})
    manifest["approval_status"] == "human_approved" || error(
        "Rev10 diagnostic execution manifest is not Human-approved.",
    )
    slots = Float64.(manifest["slots_hz"])
    slot_hz in slots || error("Requested slot is outside the accepted Rev10 tuple.")
    manifest["execution_order"] == "ascending_slots" || error(
        "Rev10 manifest execution order is not ascending_slots.",
    )
    Int(manifest["inner_loop_level"]) == 0 || error(
        "Rev10 CMA inner loop must use fixed refinement level zero.",
    )
    manifest["spatial_refinement"]["application"] ==
        "selected_best_candidate_only" || error(
            "Rev10 spatial refinement must apply only to the selected best candidate.",
        )
    gate_reconciliation = manifest["human_gate_reconciliation"]
    gate_reconciliation_path = joinpath(
        @__DIR__,
        String(gate_reconciliation["path"]),
    )
    isfile(gate_reconciliation_path) || error(
        "Rev10 Human-gate reconciliation ledger is missing.",
    )
    file_sha256(gate_reconciliation_path) ==
        String(gate_reconciliation["sha256"]) || error(
            "Rev10 Human-gate reconciliation ledger bytes changed.",
        )

    workbench_head = command_output("git", "rev-parse", "HEAD")
    base = String(manifest["sources"]["workbench_commit"])
    ancestry_command = Cmd([
        "git", "merge-base", "--is-ancestor", base, workbench_head,
    ])
    success(run(Cmd(ancestry_command; dir=WORKBENCH_ROOT))) || error(
            "Current Workbench task commit does not descend from integrated authority.",
        )
    isempty(command_output("git", "status", "--porcelain=v1")) || error(
        "Rev10 scientific run requires a clean exact Workbench task commit.",
    )
    destination = abspath(String(output_dir))
    ispath(destination) && error("Refusing to reuse existing slot output: $(destination)")
    mkpath(destination)

    q2d_path = joinpath(
        @__DIR__,
        "d3_continuous_ground_q2d_maxwell_lc.v4.json",
    )
    inputs = bind_inputs(manifest, q2d_path, abspath(q3d_path), abspath(idc_path))
    profile = extraction_profile(manifest, slot_hz)
    authority = d3_direct_hybridized_objective_authority(
        D3_HUMAN_APPROVED_OBJECTIVE_AUTHORITY,
    )
    variable_names = Tuple(Symbol(item["name"]) for item in manifest["variables"])
    variables = [
        VariableSpec(
            Symbol(item["name"]),
            String(item["unit"]),
            Float64(item["lower"]),
            Float64(item["upper"]),
        )
        for item in manifest["variables"]
    ]
    specs = metric_specs(slot_hz)
    cma = manifest["cma_es"]
    worker_count = min(Int(cma["population"]), Threads.nthreads())
    restart_results = Any[]
    starts = manifest["starts"]
    restart_indices = Int.(cma["restart_indices"])
    length(starts) == length(restart_indices) || error(
        "Rev10 start and restart-index counts differ.",
    )

    run_identity = (
        contract_id=String(manifest["contract_id"]),
        manifest_sha256=EXPECTED_MANIFEST_SHA256,
        human_gate_reconciliation=(
            locator=basename(gate_reconciliation_path),
            sha256=String(gate_reconciliation["sha256"]),
        ),
        slot_hz=slot_hz,
        workbench_task_commit=workbench_head,
        source_commits=manifest["sources"],
        fixed_input_canonical_sha256=inputs.source_identity.canonical_sha256,
        input_files=(
            q2d=(name=basename(q2d_path), sha256=file_sha256(q2d_path)),
            q3d=(name=basename(q3d_path), sha256=file_sha256(q3d_path)),
            idc=(name=basename(idc_path), sha256=file_sha256(idc_path)),
        ),
        data_classification="project-internal",
        evidence_status="diagnostic_non_promotable",
        runtime_resources=(
            julia_thread_count=Threads.nthreads(),
            cma_generation_worker_count=worker_count,
        ),
        search_discretization=(
            inner_loop_level=0,
            winner_spatial_refinement="selected_best_candidate_only",
        ),
    )
    write_new_json(joinpath(destination, "run_identity.json"), run_identity)

    for (start, restart_index) in zip(starts, restart_indices)
        restart_name = String(start["name"])
        restart_dir = joinpath(destination, "restart-$(restart_index)-$(restart_name)")
        mkpath(restart_dir)
        initial = exact_namedtuple(start["candidate"], variable_names)
        evaluator, l0_records = make_evaluator(
            inputs,
            profile,
            slot_hz,
            specs,
            restart_dir,
        )
        seed = round(Int, slot_hz / 1.0e6) + 10000 * restart_index
        settings = CMASettings(
            seed=seed,
            sigma=Float64(cma["sigma_normalized"]),
            popsize=Int(cma["population"]),
            maxiter=Int(cma["maximum_iterations"]),
            maxfevals=Int(cma["maximum_evaluations"]),
            ftol=Float64(cma["ftol_cost"]),
            xtol=Float64(cma["xtol_normalized"]),
        )
        println(
            "START slot=$(slot_hz / 1e9)GHz restart=$(restart_index) " *
            "seed=$(seed)",
        )
        flush(stdout)
        result = optimize_d3(
            evaluator,
            variables,
            specs,
            initial,
            settings,
            nothing;
            condition_manifest_id=String(manifest["contract_id"]),
            condition_manifest_sha256=EXPECTED_MANIFEST_SHA256,
            condition_manifest_approval_status=String(manifest["approval_status"]),
            worker_count=worker_count,
        )
        write_candidate_events(
            joinpath(restart_dir, "candidate_events.jsonl"),
            result.history,
            l0_records,
        )
        write_new_json(joinpath(restart_dir, "optimization.json"), result)
        push!(restart_results, (
            restart_index=restart_index,
            restart_name=restart_name,
            settings=settings,
            worker_count=worker_count,
            result=result,
            l0_by_candidate=l0_records,
        ))
        println(
            "END slot=$(slot_hz / 1e9)GHz restart=$(restart_index) " *
            "state=$(result.cma.state) valid=$(result.cma.valid_candidate_count) " *
            "rejected=$(result.cma.rejected_candidate_count)",
        )
        flush(stdout)
    end

    selected = best_valid(restart_results)
    outcome = if isnothing(selected)
        (
            status="NO_FINITE_L0_CANDIDATE",
            selected_best_candidate=nothing,
            winner_spatial_validation=(
                status="NOT_RUN_NO_FINITE_L0_CANDIDATE",
                spatial_receipt=nothing,
                failure=nothing,
            ),
            validated_finest_objective=nothing,
            validated_finest_objective_receipt=nothing,
        )
    else
        spatial = validate_selected_candidate_spatially(
            selected.record.candidate,
            selected.l0_cared_output,
            inputs,
            profile,
            slot_hz,
            authority,
            specs,
            destination,
        )
        validated_target_pass = spatial.status == "PASS" &&
            Bool(spatial.validated_finest_objective.target_gates_pass)
        status = if spatial.status != "PASS"
            "BEST_FINITE_L0_CANDIDATE_SPATIAL_NOT_VALIDATED"
        elseif validated_target_pass
            "SLOT_WINNER"
        else
            "SPATIALLY_VALIDATED_BEST_CANDIDATE_TARGET_MISS"
        end
        (
            status=status,
            selected_best_candidate=(
                restart_index=selected.restart_index,
                restart_name=selected.restart_name,
                record_id=selected.record.record_id,
                candidate=selected.record.candidate,
                cost=selected.record.cost,
                l0_search_objective=(
                    cared_output=selected.l0_cared_output,
                    objective=selected.l0_objective,
                    receipt=selected.l0_receipt,
                ),
                cma_state=selected.cma_state,
                cma_convergence_required_for_reporting=false,
                l0_target_gates_pass=Bool(selected.l0_objective.target_gates_pass),
            ),
            winner_spatial_validation=(
                status=spatial.status,
                spatial_receipt=spatial.spatial_receipt,
                failure=spatial.failure,
            ),
            validated_finest_objective=spatial.validated_finest_objective,
            validated_finest_objective_receipt=
                spatial.validated_finest_objective_receipt,
        )
    end
    summary = (
        schema_version="d3-rev10-single-slot-direct-hybridized-diagnostic.v1",
        final_status=outcome.status,
        run_identity=run_identity,
        restart_summaries=[(
            restart_index=item.restart_index,
            restart_name=item.restart_name,
            worker_count=item.worker_count,
            cma=item.result.cma,
            cache_summary=item.result.cache_summary,
            optimization_locator=joinpath(
                "restart-$(item.restart_index)-$(item.restart_name)",
                "optimization.json",
            ),
        ) for item in restart_results],
        selected_best_candidate=outcome.selected_best_candidate,
        winner_spatial_validation=outcome.winner_spatial_validation,
        validated_finest_objective=outcome.validated_finest_objective,
        validated_finest_objective_receipt=
            outcome.validated_finest_objective_receipt,
        winner_closure="PENDING_ALLOWED",
        promotion="none",
        publication="none",
    )
    write_new_json(joinpath(destination, "slot_result.json"), summary)
    println(
        "RESULT slot=$(slot_hz / 1e9)GHz status=$(summary.final_status) " *
        "path=$(joinpath(destination, "slot_result.json"))",
    )
    return summary
end

function main(args)
    length(args) == 5 || error(
        "usage: julia d3_rev10_single_slot_diagnostic_run.jl " *
        "MANIFEST Q3D_INPUT IDC_INPUT OUTPUT_DIR SLOT_HZ",
    )
    slot_hz = parse(Float64, args[5])
    run_single_slot(args[1], args[2], args[3], args[4], slot_hz)
    return nothing
end

if abspath(PROGRAM_FILE) == @__FILE__
    main(ARGS)
end
