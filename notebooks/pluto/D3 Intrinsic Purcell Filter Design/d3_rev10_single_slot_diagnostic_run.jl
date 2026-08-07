# Task-local Rev10 targeted-Schur CMA runner. Circuit equations and cared-output
# extraction are owned by the shared D3 model files; this file only binds the
# accepted manifest, runs one slot, and persists minimal diagnostic evidence.

const WORKBENCH_ROOT = normpath(get(
    ENV,
    "D3_WORKBENCH_ROOT",
    joinpath(@__DIR__, "..", "..", ".."),
))
const D3_SOURCE_ROOT = joinpath(
    WORKBENCH_ROOT,
    "notebooks",
    "pluto",
    "D3 Intrinsic Purcell Filter Design",
)
const CORE_ROOT = joinpath(
    WORKBENCH_ROOT,
    "core",
    "julia",
    "SuperconductingCircuitsCore",
)
pushfirst!(LOAD_PATH, CORE_ROOT)

using LinearAlgebra
using SHA
using SuperconductingCircuitsCore

const JSON3 = SuperconductingCircuitsCore.JSON3
const EXPECTED_MANIFEST_SHA256 =
    "75eec8ba050455c71927b2a99b4fbee8e0e3cc06e22106e15643fcfcfe2a456e"
const MANIFEST_BASENAME = "d3_rev10_five_slot_search.v1.json"
const EXPANDED_COORDINATES = (
    :lr_open_m,
    :lr_short_m,
    :lc_m,
    :lp_open_m,
    :lp_short_m,
    :u_IDC,
)
const IDC_BOUNDS_UM = (35.0, 75.0)

include(joinpath(D3_SOURCE_ROOT, "d3_circuit_plans.jl"))
include(joinpath(D3_SOURCE_ROOT, "d3_exact_n_response.jl"))
include(joinpath(D3_SOURCE_ROOT, "d3_stage_models.jl"))
include(joinpath(D3_SOURCE_ROOT, "d3_stage_objectives.jl"))
include(joinpath(D3_SOURCE_ROOT, "d3_coupled_optimizer.jl"))

using .D3FloatingQubitInput: load_floating_qubit_nominal_input
using .D3IDCInput: d3_idc_mapping_semantic_sha256, load_d3_idc_mapping
using .D3ResonatorInput:
    bind_d3_rev10_q2d_input, load_d3_continuous_ground_q2d_input
const CMAES = D3CoupledOptimizer.CMAEvolutionStrategy

file_sha256(path) = open(path, "r") do io
    bytes2hex(SHA.sha256(io))
end

function command_output(args...)
    command = Cmd(collect(String.(args)))
    return strip(read(Cmd(command; dir=WORKBENCH_ROOT), String))
end

function write_new_json(path, payload)
    destination = abspath(String(path))
    ispath(destination) && error("Refusing to overwrite evidence: $(destination)")
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

function parse_cli(args)
    options = Dict{String,Any}(
        "manifest" => joinpath(@__DIR__, MANIFEST_BASENAME),
        "slot_ghz" => nothing,
        "q3d_input" => nothing,
        "idc_input" => nothing,
        "output_dir" => nothing,
        "mode" => "cma",
    )
    index = 1
    while index <= length(args)
        argument = args[index]
        if argument in ("--single-point", "--dry-run")
            options["mode"] = argument == "--single-point" ? "single_point" : "dry_run"
            index += 1
            continue
        end
        key = get(Dict(
            "--manifest" => "manifest",
            "--slot-ghz" => "slot_ghz",
            "--q3d-input" => "q3d_input",
            "--idc-input" => "idc_input",
            "--output-dir" => "output_dir",
        ), argument, nothing)
        isnothing(key) && error("Unknown argument $(argument).")
        index < length(args) || error("$(argument) requires one value.")
        options[key] = args[index + 1]
        index += 2
    end
    isnothing(options["slot_ghz"]) && error("--slot-ghz is required.")
    isnothing(options["q3d_input"]) && error("--q3d-input is required.")
    isnothing(options["idc_input"]) && error("--idc-input is required.")
    options["slot_ghz"] = parse(Float64, String(options["slot_ghz"]))
    if options["mode"] != "dry_run" && isnothing(options["output_dir"])
        error("--output-dir is required unless --dry-run is selected.")
    end
    return options
end

function load_manifest(path)
    absolute = abspath(String(path))
    isfile(absolute) || error("Search manifest does not exist: $(absolute)")
    file_sha256(absolute) == EXPECTED_MANIFEST_SHA256 || error(
        "Search manifest bytes differ from the accepted task manifest.",
    )
    manifest = JSON3.read(read(absolute, String), Dict{String,Any})
    manifest["contract_id"] == "d3-rev10-five-slot-targeted-schur-search.v1" ||
        error("Search manifest contract id is wrong.")
    manifest["semantic_state"] == "ACCEPTED" || error(
        "Search manifest semantic state is not ACCEPTED.",
    )
    cma = manifest["cma_es"]
    Int(cma["runs_per_slot"]) == 1 || error(
        "Rev10 targeted-Schur search must contain exactly one CMA run.",
    )
    String(cma["seed_formula"]) == "round(Int,slot_hz/1e6)" || error(
        "Rev10 CMA seed formula is wrong.",
    )
    cma["native_multi_threading"] === true &&
        cma["parallel_evaluation"] === false || error(
            "Rev10 CMA must use native scalar multi-threading only.",
        )
    Int(cma["blas_thread_count"]) == 1 || error("Rev10 CMA requires BLAS=1.")
    cma["cross_slot_state_reuse"] === false || error(
        "Rev10 slots must not reuse CMA state.",
    )
    return absolute, manifest
end

function seed_candidate(manifest, slot_hz)
    matches = filter(
        item -> Float64(item["slot_hz"]) == slot_hz,
        manifest["slot_seeds"],
    )
    length(matches) == 1 || error("Manifest must contain one exact seed for the slot.")
    raw = only(matches)["candidate"]
    short = Float64(raw["l_short_m"])
    candidate = (
        lr_open_m=Float64(raw["lr_open_m"]),
        lr_short_m=short,
        lc_m=Float64(raw["lc_m"]),
        lp_open_m=Float64(raw["lp_open_m"]),
        lp_short_m=short,
        u_IDC=Float64(raw["u_IDC"]),
    )
    propertynames(candidate) == EXPANDED_COORDINATES || error("Seed order is wrong.")
    all(value -> isfinite(value) && value > 0, Tuple(candidate)) || error(
        "Seed values must be finite and positive.",
    )
    IDC_BOUNDS_UM[1] <= candidate.u_IDC <= IDC_BOUNDS_UM[2] || error(
        "Seed IDC value is outside the accepted interpolation interval.",
    )
    return candidate
end

function initial_latent(candidate)
    return [
        0.0,
        0.0,
        0.0,
        0.0,
        (candidate.u_IDC - IDC_BOUNDS_UM[1]) /
            (IDC_BOUNDS_UM[2] - IDC_BOUNDS_UM[1]),
    ]
end

function latent_candidate(seed, latent)
    length(latent) == 5 || throw(ArgumentError("CMA latent vector must have length five."))
    values = Float64.(latent)
    all(isfinite, values) || throw(ArgumentError("CMA latent values must be finite."))
    0.0 <= values[5] <= 1.0 || throw(ArgumentError("IDC latent value left [0,1]."))
    lengths = (
        seed.lr_open_m * exp(values[1]),
        seed.lr_short_m * exp(values[2]),
        seed.lc_m * exp(values[3]),
        seed.lp_open_m * exp(values[4]),
    )
    all(value -> isfinite(value) && value > 0, lengths) || throw(ArgumentError(
        "Log-positive length mapping left the finite positive Float64 domain.",
    ))
    short = lengths[2]
    return (
        lr_open_m=lengths[1],
        lr_short_m=short,
        lc_m=lengths[3],
        lp_open_m=lengths[4],
        lp_short_m=short,
        u_IDC=IDC_BOUNDS_UM[1] +
            (IDC_BOUNDS_UM[2] - IDC_BOUNDS_UM[1]) * values[5],
    )
end

function bind_inputs(manifest, q3d_path, idc_path)
    sources = manifest["sources"]
    q2d_path = joinpath(D3_SOURCE_ROOT, "d3_continuous_ground_q2d_maxwell_lc.v4.json")
    for (path, key) in (
        (q2d_path, "q2d_artifact_sha256"),
        (q3d_path, "q3d_input_sha256"),
        (idc_path, "idc_mapping_sha256"),
    )
        isfile(path) || error("Required input does not exist: $(path)")
        file_sha256(path) == String(sources[key]) || error(
            "Input bytes disagree with manifest field $(key).",
        )
    end
    fixed = manifest["fixed_physical_inputs"]
    q2d = bind_d3_rev10_q2d_input(
        load_d3_continuous_ground_q2d_input(q2d_path);
        section_length_m=Float64(fixed["q2d_section_length_um"]) * 1e-6,
        mtl_section_length_m=Float64(fixed["q2d_mtl_section_length_um"]) * 1e-6,
    )
    q3d = load_floating_qubit_nominal_input(
        q3d_path,
        (; kwargs...) -> (; kwargs...);
        gap_um=Float64(fixed["q3d_gap_um"]),
    )
    idc = load_d3_idc_mapping(idc_path; gap_um=Float64(fixed["idc_gap_um"]))
    d3_idc_mapping_semantic_sha256(idc) ==
        String(sources["idc_mapping_semantic_sha256"]) || error(
            "IDC semantic identity differs from the accepted interpolation-only mapping.",
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
            "Fixed-input canonical identity $(inputs.source_identity.canonical_sha256) " *
            "differs from manifest $(sources["fixed_input_canonical_sha256"]).",
        )
    return inputs
end

function build_context(manifest, inputs; refinement_level)
    topology = manifest["fixed_node_topology"]
    reference_slot = Float64(topology["reference_slot_hz"])
    reference = seed_candidate(manifest, reference_slot)
    plan = d3_stage2_direct_hybridized_grid_plan(
        reference,
        inputs;
        refinement_level=refinement_level,
    )
    context = build_d3_stage2_targeted_schur_objective_context(
        reference,
        inputs;
        grid_plan=plan,
        id="d3-rev10-five-slot-targeted-schur-N$(1 << refinement_level)",
    )
    factor = 1 << refinement_level
    expected = topology["section_counts"]
    counts = context.provenance.topology_counts
    for (actual, key) in (
        (counts.readout.short, "readout_short"),
        (counts.readout.open, "readout_open"),
        (counts.readout.mtl, "coupled_mtl"),
        (counts.filter.short, "filter_short"),
        (counts.filter.open, "filter_open"),
        (counts.filter.mtl, "coupled_mtl"),
        (counts.feedline_left, "feedline_left"),
        (counts.feedline_right, "feedline_right"),
    )
        actual == factor * Int(expected[key]) || error(
            "Targeted-Schur context count $(actual) disagrees with $(factor)x $(key).",
        )
    end
    size(context.full_kernel.c0, 1) == factor * (Int(topology["matrix_dimension"]) - 2) + 2 ||
        error("Targeted-Schur matrix dimension disagrees with the fixed-node manifest.")
    if refinement_level == 0
        plan.canonical_sha256 == String(topology["reference_grid_plan_sha256"]) ||
            error(
                "Reference grid-plan identity $(plan.canonical_sha256) differs " *
                "from manifest $(topology["reference_grid_plan_sha256"]).",
            )
    end
    return context
end

function targeted_metrics(cared)
    return (
        contract_id="d3-stage2-targeted-schur-candidate-metrics.v1",
        stage_id=cared.stage_id,
        model_family=cared.model_family,
        source_profile_identity=cared.source_profile_identity,
        grid_identity=cared.grid_identity,
        fr_eff_complete_complement_rp_hz=cared.f_r_eff_hz,
        fp_eff_complete_complement_rp_hz=cared.f_p_eff_hz,
        J_eff_complete_complement_rp_coherent_hz=cared.abs_real_J_eff_hz,
        notch_distributed_rp_on_hz=cared.f_n_hz,
        kappa_sum_local_hybrid_rp_hz=cared.local_hybrid_kappa_sum_hz,
        linewidth_fraction_min_local_hybrid_rp=
            cared.local_hybrid_linewidth_fraction_min,
        linewidth_fraction_max_local_hybrid_rp=
            cared.local_hybrid_linewidth_fraction_max,
        effective_diagonal_frequency_extraction=
            :complete_complement_rp_complex_operator,
        effective_exchange_extraction=
            :complete_complement_rp_complex_midpoint_residue,
        notch_authority=:distributed_rp_on,
        linewidth_pole_scope=:complete_complement_rp_local_hybrid_two_pole,
        primary_linewidth_extraction=:targeted_schur_determinant_poles,
    )
end

function cared_payload(cared)
    return (
        f_r_eff_hz=cared.f_r_eff_hz,
        f_p_eff_hz=cared.f_p_eff_hz,
        f_n_hz=cared.f_n_hz,
        abs_real_J_eff_hz=cared.abs_real_J_eff_hz,
        local_hybrid_kappa_sum_hz=cared.local_hybrid_kappa_sum_hz,
        local_hybrid_linewidth_fraction_min=
            cared.local_hybrid_linewidth_fraction_min,
        local_hybrid_linewidth_fraction_max=
            cared.local_hybrid_linewidth_fraction_max,
        source_profile_sha256=cared.source_profile_identity.canonical_sha256,
        grid_sha256=cared.grid_identity.canonical_sha256,
        validity=cared.validity,
    )
end

function evaluate_candidate(candidate, context, slot_hz)
    started = time_ns()
    try
        cared = d3_stage2_direct_cared_outputs(
            candidate,
            context;
            slot_hz=slot_hz,
            readout_root_anchor_hz=slot_hz,
            filter_root_anchor_hz=slot_hz,
            notch_zero_anchor_hz=5.0e9,
        )
        metrics = targeted_metrics(cared)
        objective = d3_stage2_objective(
            metrics,
            slot_hz,
            D3_HUMAN_APPROVED_OBJECTIVE_AUTHORITY,
            (
                source_profile_identity=cared.source_profile_identity,
                grid_identity=cared.grid_identity,
            ),
        )
        return (
            status="VALID",
            candidate=candidate,
            cost=Float64(objective.cost),
            cared=cared_payload(cared),
            objective=(
                contract_id=objective.contract_id,
                normalized_residuals=objective.normalized_residuals,
                target_diagnostics=objective.target_diagnostics,
            ),
            rejection=nothing,
            elapsed_seconds=(time_ns() - started) / 1e9,
        )
    catch exception
        exception isa D3TargetedSchurNotEvaluable || rethrow()
        return (
            status="NOT_EVALUABLE",
            candidate=candidate,
            cost=nothing,
            cared=nothing,
            objective=nothing,
            rejection=(
                code=exception.code,
                reason=exception.reason,
                details=exception.details,
            ),
            elapsed_seconds=(time_ns() - started) / 1e9,
        )
    end
end

mutable struct SearchState{C,S}
    context::C
    seed::S
    slot_hz::Float64
    lock::ReentrantLock
    candidate_locks::Dict{NTuple{5,Float64},ReentrantLock}
    cache::Dict{NTuple{5,Float64},Any}
    progress_path::String
    generation::Int
    summaries::Vector{Any}
    best::Any
end

function SearchState(context, seed, slot_hz, progress_path)
    return SearchState(
        context,
        seed,
        slot_hz,
        ReentrantLock(),
        Dict{NTuple{5,Float64},ReentrantLock}(),
        Dict{NTuple{5,Float64},Any}(),
        String(progress_path),
        0,
        Any[],
        nothing,
    )
end

latent_key(latent) = Tuple(Float64.(latent))

function cached_evaluation!(state, latent)
    key = latent_key(latent)
    candidate_lock = lock(state.lock) do
        get!(state.candidate_locks, key) do
            ReentrantLock()
        end
    end
    return lock(candidate_lock) do
        found, value = lock(state.lock) do
            haskey(state.cache, key) ? (true, state.cache[key]) : (false, nothing)
        end
        found && return value
        mapping_failure = nothing
        candidate = try
            latent_candidate(state.seed, key)
        catch exception
            exception isa ArgumentError || rethrow()
            mapping_failure = exception
            nothing
        end
        outcome = if isnothing(candidate)
            (
                status="NOT_EVALUABLE",
                candidate=nothing,
                cost=nothing,
                cared=nothing,
                objective=nothing,
                rejection=(
                    code="invalid_log_positive_candidate",
                    reason=sprint(showerror, mapping_failure),
                    details=(exception_type=string(typeof(mapping_failure)),),
                ),
                elapsed_seconds=0.0,
            )
        else
            # Only the shared typed candidate rejection is converted to +Inf by
            # evaluate_candidate; every unexpected implementation error aborts.
            evaluate_candidate(candidate, state.context, state.slot_hz)
        end
        lock(state.lock) do
            state.cache[key] = outcome
        end
        return outcome
    end
end

function objective_value!(state, latent)
    outcome = cached_evaluation!(state, latent)
    return isnothing(outcome.cost) ? Inf : outcome.cost
end

function record_initial!(state, latent)
    outcome = cached_evaluation!(state, latent)
    row = (
        event="initial_seed",
        generation=0,
        population_index=0,
        latent=collect(latent_key(latent)),
        outcome=outcome,
    )
    append_jsonl(state.progress_path, row)
    if !isnothing(outcome.cost)
        state.best = merge(row, (cost=outcome.cost,))
    end
    return outcome
end

function record_generation!(state, optimizer, y, costs)
    evaluated = CMAES.compute_input(optimizer.p, y)
    size(evaluated, 2) == length(costs) || error("CMA callback population mismatch.")
    state.generation += 1
    generation_best = nothing
    for index in eachindex(costs)
        latent = @view evaluated[:, index]
        outcome = cached_evaluation!(state, latent)
        observed = isnothing(outcome.cost) ? Inf : outcome.cost
        isequal(observed, Float64(costs[index])) || error(
            "CMA callback cost differs from its cached candidate evaluation.",
        )
        row = (
            event="candidate",
            generation=state.generation,
            population_index=index,
            latent=collect(latent_key(latent)),
            outcome=outcome,
        )
        append_jsonl(state.progress_path, row)
        if !isnothing(outcome.cost)
            generation_best = isnothing(generation_best) ||
                outcome.cost < generation_best.cost ?
                merge(row, (cost=outcome.cost,)) : generation_best
            state.best = isnothing(state.best) || outcome.cost < state.best.cost ?
                merge(row, (cost=outcome.cost,)) : state.best
        end
    end
    summary = (
        event="generation_summary",
        generation=state.generation,
        generation_best_cost=
            isnothing(generation_best) ? nothing : generation_best.cost,
        cumulative_best_cost=isnothing(state.best) ? nothing : state.best.cost,
    )
    push!(state.summaries, summary)
    append_jsonl(state.progress_path, summary)
    println(
        "generation=$(state.generation) best=$(summary.generation_best_cost) " *
        "cumulative=$(summary.cumulative_best_cost)",
    )
    flush(stdout)
    return nothing
end

function relative_change(coarse, fine)
    denominator = abs(Float64(coarse))
    denominator > 0 || error("Winner validation encountered a zero cared output.")
    return abs(Float64(fine) - Float64(coarse)) / denominator
end

function validate_winner(manifest, inputs, slot_hz, winner)
    fine_context = build_context(manifest, inputs; refinement_level=1)
    fine = evaluate_candidate(winner.candidate, fine_context, slot_hz)
    fine.status == "VALID" || return (
        status="NOT_EVALUABLE_AT_2N",
        threshold=0.001,
        fine=fine,
        relative_changes=nothing,
        pass=false,
    )
    coarse = winner.cared
    names = (
        :f_r_eff_hz,
        :f_p_eff_hz,
        :f_n_hz,
        :abs_real_J_eff_hz,
        :local_hybrid_kappa_sum_hz,
        :local_hybrid_linewidth_fraction_min,
    )
    changes = NamedTuple{names}(Tuple(
        relative_change(getproperty(coarse, name), getproperty(fine.cared, name))
        for name in names
    ))
    pass = all(value -> value <= 0.001, values(changes))
    return (
        status=pass ? "PASS" : "ABOVE_0P1_PERCENT",
        threshold=0.001,
        fine=fine,
        relative_changes=changes,
        pass=pass,
    )
end

function run(options)
    manifest_path, manifest = load_manifest(options["manifest"])
    slot_hz = Float64(options["slot_ghz"]) * 1e9
    slot_hz in Float64.(manifest["slots"]["ordered_hz"]) || error(
        "Requested slot is outside the accepted ordered Rev10 tuple.",
    )
    BLAS.set_num_threads(1)
    inputs = bind_inputs(
        manifest,
        abspath(String(options["q3d_input"])),
        abspath(String(options["idc_input"])),
    )
    context = build_context(manifest, inputs; refinement_level=0)
    seed = seed_candidate(manifest, slot_hz)
    source = (
        manifest_sha256=EXPECTED_MANIFEST_SHA256,
        manifest_path=manifest_path,
        manifest_sources=manifest["sources"],
        workbench_commit=command_output("git", "rev-parse", "HEAD"),
        workbench_dirty=!isempty(command_output("git", "status", "--porcelain=v1")),
        fixed_input_canonical_sha256=inputs.source_identity.canonical_sha256,
        targeted_context_contract=context.contract_id,
        targeted_context_source_sha256=context.source_profile_identity.canonical_sha256,
        reference_grid_plan_sha256=context.grid_plan.canonical_sha256,
        matrix_dimension=size(context.full_kernel.c0, 1),
        threads=(julia=Threads.nthreads(), blas=BLAS.get_num_threads()),
    )
    mode = String(options["mode"])
    if mode == "dry_run"
        println(JSON3.write((status="DRY_RUN_READY", slot_hz=slot_hz, source=source)))
        return nothing
    end

    destination = abspath(String(options["output_dir"]))
    ispath(destination) && error("Refusing to reuse output directory $(destination).")
    mkpath(destination)
    progress_path = joinpath(destination, "progress.jsonl")
    state = SearchState(context, seed, slot_hz, progress_path)
    initial = initial_latent(seed)
    initial_outcome = record_initial!(state, initial)
    if mode == "single_point"
        result = (
            schema_version="d3-rev10-targeted-schur-search-result.v1",
            status=initial_outcome.status,
            mode=mode,
            slot_hz=slot_hz,
            source=source,
            initial_seed=initial_outcome,
            cma=nothing,
            winner_validation=nothing,
            evidence_status="diagnostic_non_promotable",
        )
        write_new_json(joinpath(destination, "result.json"), result)
        return result
    end

    cma = manifest["cma_es"]
    Threads.nthreads() >= Int(cma["maximum_concurrent_candidate_evaluations"]) || error(
        "Full CMA requires at least $(cma["maximum_concurrent_candidate_evaluations"]) Julia threads.",
    )
    callback = (optimizer, y, costs, _) -> record_generation!(state, optimizer, y, costs)
    result = CMAES.minimize(
        latent -> objective_value!(state, latent),
        initial,
        Float64(cma["sigma_latent_coordinate"]);
        lower=vcat(fill(-Inf, 4), 0.0),
        upper=vcat(fill(Inf, 4), 1.0),
        popsize=Int(cma["population"]),
        seed=round(Int, slot_hz / 1e6),
        maxiter=Int(cma["maximum_iterations"]),
        maxfevals=Int(cma["maximum_evaluations"]),
        ftol=nothing,
        xtol=nothing,
        callback=callback,
        parallel_evaluation=false,
        multi_threading=true,
        noise_handling=nothing,
        verbosity=0,
    )
    winner = isnothing(state.best) ? nothing : state.best.outcome
    validation = isnothing(winner) ? nothing :
        validate_winner(manifest, inputs, slot_hz, winner)
    terminal = (
        schema_version="d3-rev10-targeted-schur-search-result.v1",
        status=isnothing(winner) ? "NO_FINITE_CANDIDATE" : "RAW_BEST_AVAILABLE",
        mode=mode,
        slot_hz=slot_hz,
        source=source,
        initial_seed=initial_outcome,
        cma=(
            seed=round(Int, slot_hz / 1e6),
            population=Int(cma["population"]),
            sigma=Float64(cma["sigma_latent_coordinate"]),
            generations=state.generation,
            stop_reason=String(result.stop.reason),
            stop_iteration=Int(result.stop.it),
            generation_summaries=state.summaries,
        ),
        selected_best=winner,
        winner_validation=validation,
        evidence_status="diagnostic_non_promotable",
        promotion="none",
        publication="none",
    )
    write_new_json(joinpath(destination, "result.json"), terminal)
    return terminal
end

function main(args)
    run(parse_cli(args))
    return nothing
end

if abspath(PROGRAM_FILE) == @__FILE__
    main(ARGS)
end
