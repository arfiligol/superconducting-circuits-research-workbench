### A Pluto.jl notebook ###
# v0.20.21

using Markdown
using InteractiveUtils

# ╔═╡ 94ed89c1-116c-49f8-8708-79ce737ca3e8
md"""
# D3 Rev10 — fixed-node numeric-kernel experiment

This task-local experiment asks one narrow question: after fixing every CPW,
MTL, and feedline section count, can candidate-dependent `C` and `K` matrices
be reconstructed by changing numerical values only?

It does not change the Rev10 Objective, optimizer, production grid contract,
or shared Circuit APIs. Results are project-internal diagnostic evidence.
"""

# ╔═╡ d825b7dc-5849-4ced-b50e-26f452bb5a12
begin
    using LinearAlgebra
    using SHA
    using Statistics

    WORKBENCH_ROOT = normpath(get(
        ENV,
        "D3_FIXED_NODE_WORKBENCH_ROOT",
        joinpath(@__DIR__, "..", "..", ".."),
    ))
    D3_SOURCE_DIR = joinpath(
        WORKBENCH_ROOT,
        "notebooks",
        "pluto",
        "D3 Intrinsic Purcell Filter Design",
    )
    CORE_ROOT = joinpath(
        WORKBENCH_ROOT,
        "core",
        "julia",
        "SuperconductingCircuitsCore",
    )
    pushfirst!(LOAD_PATH, CORE_ROOT)
    using SuperconductingCircuitsCore
    JSON3 = SuperconductingCircuitsCore.JSON3

    include(joinpath(D3_SOURCE_DIR, "d3_circuit_plans.jl"))
    include(joinpath(D3_SOURCE_DIR, "d3_exact_n_response.jl"))
    include(joinpath(D3_SOURCE_DIR, "d3_stage_models.jl"))
    using .D3FloatingQubitInput: load_floating_qubit_nominal_input
    using .D3IDCInput: load_d3_idc_mapping
    using .D3ResonatorInput:
        bind_d3_rev10_q2d_input, load_d3_continuous_ground_q2d_input
end

# ╔═╡ 982d10d4-8c5d-44b7-bb7c-d2c2804927c7
begin
    # All artifact-changing controls live here, before construction.
    Q3D_INPUT_PATH = get(ENV, "D3_Q3D_INPUT", "")
    IDC_INPUT_PATH = get(ENV, "D3_IDC_INPUT", "")
    OUTPUT_DIRECTORY = get(ENV, "D3_FIXED_NODE_OUTPUT_DIR", "")

    REFERENCE_CANDIDATE = (
        lr_open_m=3014.87e-6,
        lr_short_m=2100.74e-6,
        lc_m=645.30e-6,
        lp_open_m=3014.87e-6,
        lp_short_m=2100.74e-6,
        u_IDC=62.68,
    )
    VALIDATION_CANDIDATE = (
        lr_open_m=0.95 * REFERENCE_CANDIDATE.lr_open_m,
        lr_short_m=1.05 * REFERENCE_CANDIDATE.lr_short_m,
        lc_m=0.90 * REFERENCE_CANDIDATE.lc_m,
        lp_open_m=1.08 * REFERENCE_CANDIDATE.lp_open_m,
        lp_short_m=1.05 * REFERENCE_CANDIDATE.lp_short_m,
        u_IDC=55.0,
    )

    env_count(name, default) = parse(Int, get(ENV, name, string(default)))
    READOUT_AGGREGATE_COUNT = env_count("D3_FIXED_NODE_READOUT_COUNT", 380)
    FILTER_AGGREGATE_COUNT = env_count("D3_FIXED_NODE_FILTER_COUNT", 380)
    MTL_COUNT = env_count("D3_FIXED_NODE_MTL_COUNT", 196)
    FEEDLINE_LEFT_COUNT = env_count("D3_FIXED_NODE_FEEDLINE_LEFT_COUNT", 20)
    FEEDLINE_RIGHT_COUNT = env_count("D3_FIXED_NODE_FEEDLINE_RIGHT_COUNT", 20)
    FEEDLINE_LEFT_COUNT == FEEDLINE_RIGHT_COUNT || error(
        "The split feedline requires equal left/right section counts.",
    )

    function split_cpw_count(aggregate_count, mtl_count, short_m, open_m)
        remaining = aggregate_count - mtl_count
        remaining >= 2 || error("Aggregate line count must leave two or more CPW sections.")
        short_count = clamp(
            round(Int, remaining * short_m / (short_m + open_m)),
            1,
            remaining - 1,
        )
        return (short=short_count, open=remaining - short_count)
    end

    readout_cpw_counts = split_cpw_count(
        READOUT_AGGREGATE_COUNT,
        MTL_COUNT,
        REFERENCE_CANDIDATE.lr_short_m,
        REFERENCE_CANDIDATE.lr_open_m,
    )
    filter_cpw_counts = split_cpw_count(
        FILTER_AGGREGATE_COUNT,
        MTL_COUNT,
        REFERENCE_CANDIDATE.lp_short_m,
        REFERENCE_CANDIDATE.lp_open_m,
    )
    FIXED_COUNTS = (
        readout_short=readout_cpw_counts.short,
        mtl=MTL_COUNT,
        readout_open=readout_cpw_counts.open,
        filter_short=filter_cpw_counts.short,
        filter_open=filter_cpw_counts.open,
        feedline_left=FEEDLINE_LEFT_COUNT,
        feedline_right=FEEDLINE_RIGHT_COUNT,
    )
    AGGREGATE_COUNTS = (
        readout=READOUT_AGGREGATE_COUNT,
        filter=FILTER_AGGREGATE_COUNT,
        mtl=MTL_COUNT,
        feedline_left=FEEDLINE_LEFT_COUNT,
        feedline_right=FEEDLINE_RIGHT_COUNT,
    )
    TRAINING_SCALE = 1.10
    WARM_REBUILD_SAMPLES = 3
    KERNEL_MATRIX_SAMPLES = 1000
    KERNEL_EIGEN_SAMPLES = 10
end

# ╔═╡ 24d06593-4cee-4f4a-b2ae-1de72f52cc54
md"""
## What Julia “warm” execution means

The first call includes parsing, method specialization, and LLVM compilation.
Later calls with the same argument types reuse that machine code. Array sizes
are not Julia types, so merely keeping the same matrix dimension does not cause
another JIT specialization; fixed dimensions help because topology, indices,
storage, and workspaces can also be reused.
"""

# ╔═╡ 16539c27-bfb9-4a75-b89d-253bb9369c7a
begin
    file_sha256(path) = open(path, "r") do io
        bytes2hex(SHA.sha256(io))
    end

    function exact_segment(start_m, length_m, count)
        isfinite(start_m) && start_m >= 0 || error("Segment start must be finite and nonnegative.")
        isfinite(length_m) && length_m > 0 || error("Segment length must be finite and positive.")
        count isa Integer && count > 0 || error("Segment count must be a positive integer.")
        return collect(range(start_m, stop=start_m + length_m, length=count + 1))
    end

    function fixed_line_boundaries(short_m, coupling_m, open_m, n_short, n_mtl, n_open)
        short = exact_segment(0.0, short_m, n_short)
        coupling = exact_segment(short_m, coupling_m, n_mtl)
        open = exact_segment(short_m + coupling_m, open_m, n_open)
        boundaries = vcat(short, coupling[2:end], open[2:end])
        all(diff(boundaries) .> 0) || error("Fixed-node line boundaries must increase strictly.")
        return boundaries
    end

    function with_coordinate(candidate, name, value)
        isfinite(value) && value > 0 || error("Candidate coordinate must remain finite and positive.")
        if name == :l_short_m
            return merge(candidate, (lr_short_m=value, lp_short_m=value))
        end
        return merge(candidate, NamedTuple{(name,)}((value,)))
    end

    compact_coordinate(candidate, name) = name == :l_short_m ?
        candidate.lr_short_m : getproperty(candidate, name)
end

# ╔═╡ 53cc352f-8032-4a49-bd27-1d22491a2187
begin
    isempty(Q3D_INPUT_PATH) && error("Set D3_Q3D_INPUT to the authorized project-internal Q3D JSON.")
    isempty(IDC_INPUT_PATH) && error("Set D3_IDC_INPUT to the authorized project-internal IDC JSON.")
    isfile(Q3D_INPUT_PATH) || error("D3_Q3D_INPUT does not exist.")
    isfile(IDC_INPUT_PATH) || error("D3_IDC_INPUT does not exist.")

    q2d_path = joinpath(D3_SOURCE_DIR, "d3_continuous_ground_q2d_maxwell_lc.v4.json")
    q2d = bind_d3_rev10_q2d_input(
        load_d3_continuous_ground_q2d_input(q2d_path);
        section_length_m=50e-6,
        mtl_section_length_m=10e-6,
    )
    q3d = load_floating_qubit_nominal_input(
        Q3D_INPUT_PATH,
        (; kwargs...) -> (; kwargs...);
        gap_um=8.0,
    )
    idc = load_d3_idc_mapping(IDC_INPUT_PATH; gap_um=8.0)
    fixed_inputs = bind_d3_stage2_direct_hybridized_inputs(
        q2d,
        q3d,
        idc;
        feedline_length_m=1.0e-3,
        feedline_n_sections=FEEDLINE_LEFT_COUNT + FEEDLINE_RIGHT_COUNT,
        feedline_l_per_m_h=4.04313e-7,
        feedline_c_per_m_f=1.7986e-10,
        port_resistance_ohm=50.0,
    )
end

# ╔═╡ ba2ce926-accc-402a-92b0-f420422d54f5
function build_fixed_node_model(candidate, inputs, counts)
    candidate.lr_short_m == candidate.lp_short_m || error(
        "This experiment requires exact shared-short equality.",
    )
    idc_values = _d3_stage_idc_triplet(inputs.idc_mapping, candidate.u_IDC)
    qubit = _d3_stage_fixed_qubit_keywords(inputs.qubit)
    selected_lines = _d3_selected_q2d_line_input(inputs.q2d_input)
    lines = _d3_hybridized_fixed_line_keywords(selected_lines)
    feedline = _d3_distributed_feedline_keywords(inputs.feedline)

    readout_boundaries = fixed_line_boundaries(
        candidate.lr_short_m,
        candidate.lc_m,
        candidate.lr_open_m,
        counts.readout_short,
        counts.mtl,
        counts.readout_open,
    )
    filter_boundaries = fixed_line_boundaries(
        candidate.lp_short_m,
        candidate.lc_m,
        candidate.lp_open_m,
        counts.filter_short,
        counts.mtl,
        counts.filter_open,
    )
    feedline_left = exact_segment(0.0, feedline.feedline_length_m / 2, counts.feedline_left)
    feedline_right = exact_segment(0.0, feedline.feedline_length_m / 2, counts.feedline_right)

    built = build_d3_intrinsic_purcell_hybridized_circuit_plan(;
        id="d3-rev10-fixed-node-experiment",
        idc_filter_ground_capacitance_f=idc_values.idc_filter_ground_capacitance_f,
        idc_feedline_ground_capacitance_f=idc_values.idc_feedline_ground_capacitance_f,
        idc_mutual_capacitance_f=idc_values.idc_mutual_capacitance_f,
        readout_length_m=candidate.lr_short_m + candidate.lc_m + candidate.lr_open_m,
        filter_length_m=candidate.lp_short_m + candidate.lc_m + candidate.lp_open_m,
        window_start_readout_m=candidate.lr_short_m,
        window_start_filter_m=candidate.lp_short_m,
        window_length_m=candidate.lc_m,
        mtl_section_length_m=candidate.lc_m / counts.mtl,
        readout_l_per_m_h=lines.readout_l_per_m_h,
        readout_c_per_m_f=lines.readout_c_per_m_f,
        filter_l_per_m_h=lines.filter_l_per_m_h,
        filter_c_per_m_f=lines.filter_c_per_m_f,
        l_matrix_per_m_h=lines.l_matrix_per_m_h,
        c_matrix_per_m_f=lines.c_matrix_per_m_f,
        coupling_orientation=lines.coupling_orientation,
        qubit...,
        feedline...,
        readout_breakpoints_m=readout_boundaries,
        filter_breakpoints_m=filter_boundaries,
        feedline_left_breakpoints_m=feedline_left,
        feedline_right_breakpoints_m=feedline_right,
    )
    return d3_hybridized_compiled_model(built)
end

# ╔═╡ d154fc5d-1cdf-43cf-9d1e-20b75e3d44c5
begin
    LENGTH_COORDINATES = (:lr_open_m, :l_short_m, :lc_m, :lp_open_m)
    ALL_COORDINATES = (LENGTH_COORDINATES..., :u_IDC)

    function assert_same_structure(reference, candidate)
        reference.coordinate_order == candidate.coordinate_order || error("Coordinate order changed.")
        reference.anchored_coordinate_indices == candidate.anchored_coordinate_indices || error(
            "Anchored indices changed.",
        )
        reference.selector == candidate.selector || error("Port selector changed.")
        size(reference.capacitance) == size(candidate.capacitance) || error("Matrix size changed.")
        return nothing
    end

    function train_fixed_node_kernel(reference_candidate, inputs, counts; scale=1.10)
        started = time_ns()
        reference_model = build_fixed_node_model(reference_candidate, inputs, counts)
        c_terms = Dict{Symbol,Matrix{Float64}}()
        k_terms = Dict{Symbol,Matrix{Float64}}()
        builds = Dict{Symbol,Any}()

        for name in ALL_COORDINATES
            x0 = compact_coordinate(reference_candidate, name)
            x1 = x0 * scale
            perturbed = with_coordinate(reference_candidate, name, x1)
            model = build_fixed_node_model(perturbed, inputs, counts)
            assert_same_structure(reference_model, model)
            c_terms[name] = (model.capacitance - reference_model.capacitance) / (x1 - x0)
            if name in LENGTH_COORDINATES
                k_terms[name] = (model.inverse_inductance - reference_model.inverse_inductance) /
                    (inv(x1) - inv(x0))
            end
            builds[name] = model
        end

        c0 = copy(reference_model.capacitance)
        for name in ALL_COORDINATES
            c0 .-= compact_coordinate(reference_candidate, name) .* c_terms[name]
        end
        k0 = copy(reference_model.inverse_inductance)
        for name in LENGTH_COORDINATES
            k0 .-= inv(compact_coordinate(reference_candidate, name)) .* k_terms[name]
        end
        idc_k_delta = maximum(abs, builds[:u_IDC].inverse_inductance - reference_model.inverse_inductance)
        return (
            reference_model=reference_model,
            c0=c0,
            k0=k0,
            c_terms=c_terms,
            k_terms=k_terms,
            idc_k_delta=idc_k_delta,
            training_seconds=(time_ns() - started) / 1e9,
        )
    end

    function kernel_matrices!(capacitance, inverse_inductance, kernel, candidate)
        copyto!(capacitance, kernel.c0)
        for name in ALL_COORDINATES
            capacitance .+= compact_coordinate(candidate, name) .* kernel.c_terms[name]
        end
        copyto!(inverse_inductance, kernel.k0)
        for name in LENGTH_COORDINATES
            inverse_inductance .+= inv(compact_coordinate(candidate, name)) .* kernel.k_terms[name]
        end
        return capacitance, inverse_inductance
    end
end

# ╔═╡ ca67ec5d-b4a0-4ce3-9804-5089efe46f08
kernel = train_fixed_node_kernel(
    REFERENCE_CANDIDATE,
    fixed_inputs,
    FIXED_COUNTS;
    scale=TRAINING_SCALE,
)

# ╔═╡ 530654da-a815-48cc-b14c-c41bed785dd1
begin
    validation_started = time_ns()
    validation_model = build_fixed_node_model(VALIDATION_CANDIDATE, fixed_inputs, FIXED_COUNTS)
    assert_same_structure(kernel.reference_model, validation_model)
    c_workspace = similar(kernel.c0)
    k_workspace = similar(kernel.k0)
    kernel_matrices!(c_workspace, k_workspace, kernel, VALIDATION_CANDIDATE)
    validation_build_seconds = (time_ns() - validation_started) / 1e9

    c_scale = max(maximum(abs, validation_model.capacitance), floatmin(Float64))
    k_scale = max(maximum(abs, validation_model.inverse_inductance), floatmin(Float64))
    matrix_comparison = (
        capacitance_max_relative_error=
            maximum(abs, c_workspace - validation_model.capacitance) / c_scale,
        inverse_inductance_max_relative_error=
            maximum(abs, k_workspace - validation_model.inverse_inductance) / k_scale,
        idc_to_inverse_inductance_max_abs_delta=kernel.idc_k_delta,
    )

    direct_squared = eigvals(
        Symmetric(validation_model.inverse_inductance),
        Symmetric(validation_model.capacitance),
    )
    kernel_squared = eigvals(Symmetric(k_workspace), Symmetric(c_workspace))
    squared_frequency_scale = max(
        maximum(abs, direct_squared),
        maximum(abs, kernel_squared),
        floatmin(Float64),
    )
    squared_frequency_resolution =
        eps(Float64) * length(direct_squared) * squared_frequency_scale
    positive_direct = sort(sqrt.(direct_squared[
        direct_squared .> squared_frequency_resolution
    ]) ./ (2π))
    positive_kernel = sort(sqrt.(kernel_squared[
        kernel_squared .> squared_frequency_resolution
    ]) ./ (2π))
    length(positive_direct) == length(positive_kernel) || error("Kernel changed mode count.")
    spectrum_comparison = (
        mode_count=length(positive_direct),
        raw_positive_mode_count_direct=count(>(0), direct_squared),
        raw_positive_mode_count_kernel=count(>(0), kernel_squared),
        squared_frequency_machine_resolution=squared_frequency_resolution,
        maximum_absolute_frequency_error_hz=maximum(abs, positive_kernel - positive_direct),
        maximum_relative_frequency_error=maximum(
            abs.(positive_kernel - positive_direct) ./ positive_direct,
        ),
    )
end

# ╔═╡ 8781e746-3d71-4b98-b8f7-b4fec1d431f6
begin
    function elapsed_samples(action, count)
        action() # warm the exact callable under measurement
        return [@elapsed action() for _ in 1:count]
    end

    warm_rebuild_seconds = elapsed_samples(
        () -> build_fixed_node_model(VALIDATION_CANDIDATE, fixed_inputs, FIXED_COUNTS),
        WARM_REBUILD_SAMPLES,
    )
    kernel_matrix_seconds = elapsed_samples(
        () -> kernel_matrices!(c_workspace, k_workspace, kernel, VALIDATION_CANDIDATE),
        KERNEL_MATRIX_SAMPLES,
    )
    kernel_eigen_seconds = elapsed_samples(
        () -> eigvals(Symmetric(k_workspace), Symmetric(c_workspace)),
        KERNEL_EIGEN_SAMPLES,
    )
    timing = (
        one_time_kernel_training_seconds=kernel.training_seconds,
        validation_direct_build_seconds=validation_build_seconds,
        warm_full_rebuild_median_seconds=median(warm_rebuild_seconds),
        numeric_matrix_injection_median_seconds=median(kernel_matrix_seconds),
        generalized_eigensolve_median_seconds=median(kernel_eigen_seconds),
        rebuild_to_injection_ratio=
            median(warm_rebuild_seconds) / median(kernel_matrix_seconds),
    )
end

# ╔═╡ 5f881a0c-4c31-47aa-aedb-fe136535c8f3
md"""
## Result

- **Fixed matrix dimension:** $(size(kernel.reference_model.capacitance, 1)) coordinates
- **One-time coefficient training:** $(round(timing.one_time_kernel_training_seconds; digits=3)) s
- **Warm full Plan → compile → matrix rebuild:** $(round(timing.warm_full_rebuild_median_seconds; digits=6)) s
- **Numeric `C/K` injection only:** $(round(1e6 * timing.numeric_matrix_injection_median_seconds; digits=3)) µs
- **Generalized eigensolve:** $(round(1e3 * timing.generalized_eigensolve_median_seconds; digits=3)) ms
**Rebuild / injection ratio:** $(round(timing.rebuild_to_injection_ratio; digits=1))×

Matrix reconstruction errors:

- `C`: $(matrix_comparison.capacitance_max_relative_error)
- `K`: $(matrix_comparison.inverse_inductance_max_relative_error)
- closed-mode maximum frequency difference: $(spectrum_comparison.maximum_absolute_frequency_error_hz) Hz

This times only the fixed-node matrix kernel and generalized eigenproblem. It
does not claim the same speedup for the complete Rev10 roots, open poles,
notch, or Objective until those existing consumers are connected to the same
fixed-node matrices.
"""

# ╔═╡ a6416d7b-a423-4a47-a248-3d5183c01a8a
begin
    result = (
        contract_id="d3-rev10-fixed-node-numeric-kernel-experiment.v1",
        semantic_state="CONVERGING",
        data_classification="project-internal",
        evidence_status="diagnostic_non_promotable",
        source=(
            workbench_commit=strip(read(`git -C $WORKBENCH_ROOT rev-parse HEAD`, String)),
            q2d_sha256=file_sha256(q2d_path),
            q3d_sha256=file_sha256(Q3D_INPUT_PATH),
            idc_sha256=file_sha256(IDC_INPUT_PATH),
        ),
        reference_candidate=REFERENCE_CANDIDATE,
        validation_candidate=VALIDATION_CANDIDATE,
        aggregate_counts=AGGREGATE_COUNTS,
        fixed_counts=FIXED_COUNTS,
        matrix_dimension=size(kernel.reference_model.capacitance, 1),
        matrix_comparison=matrix_comparison,
        spectrum_comparison=spectrum_comparison,
        timing=timing,
        exclusions=(
            "not_connected_to_rev10_objective",
            "not_a_production_grid_contract",
            "not_promotion_eligible",
        ),
    )
    if !isempty(OUTPUT_DIRECTORY)
        mkpath(OUTPUT_DIRECTORY)
        output_path = joinpath(OUTPUT_DIRECTORY, "fixed_node_numeric_kernel_result.json")
        ispath(output_path) && error("Refusing to overwrite existing diagnostic evidence.")
        open(output_path, "w") do io
            JSON3.pretty(io, result)
            println(io)
        end
    end
    result
end

# ╔═╡ Cell order:
# ╟─94ed89c1-116c-49f8-8708-79ce737ca3e8
# ╠═d825b7dc-5849-4ced-b50e-26f452bb5a12
# ╠═982d10d4-8c5d-44b7-bb7c-d2c2804927c7
# ╟─24d06593-4cee-4f4a-b2ae-1de72f52cc54
# ╠═16539c27-bfb9-4a75-b89d-253bb9369c7a
# ╠═53cc352f-8032-4a49-bd27-1d22491a2187
# ╠═ba2ce926-accc-402a-92b0-f420422d54f5
# ╠═d154fc5d-1cdf-43cf-9d1e-20b75e3d44c5
# ╠═ca67ec5d-b4a0-4ce3-9804-5089efe46f08
# ╠═530654da-a815-48cc-b14c-c41bed785dd1
# ╠═8781e746-3d71-4b98-b8f7-b4fec1d431f6
# ╟─5f881a0c-4c31-47aa-aedb-fe136535c8f3
# ╠═a6416d7b-a423-4a47-a248-3d5183c01a8a
