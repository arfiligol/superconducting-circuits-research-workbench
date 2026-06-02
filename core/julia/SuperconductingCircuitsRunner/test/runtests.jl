using JSON3
using SuperconductingCircuitsRunner
using Test

const LOCAL_SPACE_RESONATOR_DEFINITION_ID = "c8f08463-bf18-4f8e-a5d5-735f3d7b0d6e"

function thrown_error_message(f)
    try
        f()
    catch err
        return sprint(showerror, err)
    end
    return nothing
end

function valid_frequency_sweep_setup(; solver_family="josephson_circuits")
    return Dict{String,Any}(
        "frequency_sweep" => Dict{String,Any}(
            "start_ghz" => 4.0,
            "stop_ghz" => 6.0,
            "point_count" => 5,
            "spacing" => "linear",
        ),
        "parameter_sweeps" => Any[],
        "solver" => Dict{String,Any}(
            "solver_family" => solver_family,
            "max_iterations" => 1,
            "convergence_tolerance" => 1.0e-6,
        ),
        "sources" => Any[
            Dict{String,Any}(
                "source_id" => "drive-port-a",
                "kind" => "port_drive",
                "target" => "port_1",
                "amplitude" => -35.0,
            ),
        ],
        "ptc" => nothing,
    )
end

function runner_claim(
    dir;
    task_kind="julia_simulation_frequency_sweep",
    input=Dict{String,Any}("simulation_setup" => valid_frequency_sweep_setup()),
    design_id="unsupported_definition",
)
    return SuperconductingCircuitsRunner.RunnerClaim(
        "task_real_boundary",
        task_kind,
        input,
        nothing,
        design_id,
        dir,
        joinpath(dir, "result.zarr"),
        joinpath(dir, "manifest.json"),
    )
end

@testset "runner task contract" begin
    payload = Dict(
        "task" => Dict(
            "task_id" => "306",
            "task_kind" => "julia_simulation_frequency_sweep",
            "input" => Dict{String,Any}(),
            "output_target" => Dict(
                "dataset_id" => "local-dataset-001",
                "design_id" => "design_frequency_fixture",
            ),
        ),
        "staging" => Dict(
            "mode" => "local_filesystem",
            "task_dir" => "data/staging/tasks/306",
            "result_zarr" => "data/staging/tasks/306/result.zarr",
            "manifest" => "data/staging/tasks/306/manifest.json",
        ),
    )

    claim = parse_task_claim(payload)
    @test claim !== nothing
    @test claim.task_id == "306"
    @test claim.task_kind == "julia_simulation_frequency_sweep"
    @test claim.dataset_id == "local-dataset-001"
    @test claim.design_id == "design_frequency_fixture"
end

@testset "runner rejects smoke task kind" begin
    mktempdir() do dir
        smoke_claim = SuperconductingCircuitsRunner.RunnerClaim(
            "task_smoke",
            "julia_runner_smoke",
            Dict{String,Any}(),
            nothing,
            nothing,
            dir,
            joinpath(dir, "result.zarr"),
            joinpath(dir, "manifest.json"),
        )
        message = thrown_error_message(() -> execute_task(smoke_claim))
        @test message !== nothing
        @test occursin("Unsupported Julia Runner task kind: julia_runner_smoke", message)
        @test !isdir(joinpath(dir, "result.zarr"))
        @test !isfile(joinpath(dir, "manifest.json"))
    end
end

@testset "runner public API does not expose smoke writer" begin
    removed_name = Symbol("write_" * "smoke_result_package")
    @test !isdefined(SuperconductingCircuitsRunner, removed_name)
end

@testset "real task kinds fail clearly until implemented" begin
    mktempdir() do dir
        task_kinds = [
            "julia_simulation_parameter_sweep",
            "julia_analysis_trace_summary",
            "julia_postprocess_coordinate_transform",
        ]
        for task_kind in task_kinds
            claim = SuperconductingCircuitsRunner.RunnerClaim(
                "task_real_boundary",
                task_kind,
                Dict{String,Any}(),
                nothing,
                nothing,
                dir,
                joinpath(dir, "result.zarr"),
                joinpath(dir, "manifest.json"),
            )
            message = thrown_error_message(() -> execute_task(claim))
            @test message !== nothing
            @test occursin("not implemented yet", message)
            @test occursin("Refusing to write fixture output", message)
        end
    end
end

@testset "frequency sweep requires simulation setup" begin
    mktempdir() do dir
        claim = runner_claim(dir; input=Dict{String,Any}())
        message = thrown_error_message(() -> execute_task(claim))
        @test message !== nothing
        @test occursin("Missing simulation_setup", message)
        @test !isdir(joinpath(dir, "result.zarr"))
        @test !isfile(joinpath(dir, "manifest.json"))
    end
end

@testset "frequency sweep rejects unsupported solver family" begin
    mktempdir() do dir
        claim = runner_claim(
            dir;
            input=Dict{String,Any}(
                "simulation_setup" => valid_frequency_sweep_setup(; solver_family="not_josephson"),
            ),
        )
        message = thrown_error_message(() -> execute_task(claim))
        @test message !== nothing
        @test occursin("Unsupported solver family: not_josephson", message)
        @test !isdir(joinpath(dir, "result.zarr"))
        @test !isfile(joinpath(dir, "manifest.json"))
    end
end

@testset "frequency sweep rejects unsupported definition path" begin
    mktempdir() do dir
        claim = runner_claim(dir; design_id="unknown_definition")
        message = thrown_error_message(() -> execute_task(claim))
        @test message !== nothing
        @test occursin("Unsupported definition_id/design path", message)
        @test occursin("unknown_definition", message)
        @test !isdir(joinpath(dir, "result.zarr"))
        @test !isfile(joinpath(dir, "manifest.json"))
    end
end

@testset "frequency sweep executes supported Core MVP path" begin
    mktempdir() do dir
        claim = runner_claim(dir; design_id=LOCAL_SPACE_RESONATOR_DEFINITION_ID)
        manifest_path = execute_task(claim)
        @test isfile(manifest_path)
        @test isdir(joinpath(dir, "result.zarr"))

        manifest = JSON3.read(read(manifest_path, String))
        @test manifest.task_id == "task_real_boundary"
        @test manifest.sweep.total_points == 5
        @test manifest.sweep.success_points == 5
        @test manifest.traces[1].trace_key == "S11"
        @test manifest.traces[1].shape == [5]
        @test isfile(joinpath(dir, "result.zarr", "traces", "S11", "real", "0"))
        @test isfile(joinpath(dir, "result.zarr", "traces", "S11", "imag", "0"))
        @test !occursin("fixture", lowercase(read(joinpath(dir, "logs", "runner.log"), String)))
    end
end

@testset "unknown runner task kind fails clearly" begin
    mktempdir() do dir
        unknown_claim = SuperconductingCircuitsRunner.RunnerClaim(
            "task_unknown",
            "unknown_kind",
            Dict{String,Any}(),
            nothing,
            nothing,
            dir,
            joinpath(dir, "result.zarr"),
            joinpath(dir, "manifest.json"),
        )
        message = thrown_error_message(() -> execute_task(unknown_claim))
        @test message !== nothing
        @test occursin("Unsupported Julia Runner task kind: unknown_kind", message)
    end
end

@testset "small trace zarr fixture package writer" begin
    mktempdir() do dir
        frequency = collect(range(4.0e9, 6.0e9; length=5))
        sweep1 = Float64[1.0, 2.0]
        sweep2 = Float64[10.0, 20.0]
        real = reshape(collect(Float64, 1:20), 5, 2, 2)
        imag = zeros(Float64, 5, 2, 2)

        manifest_path = write_trace_zarr_package(
            dir;
            task_id="task_3d",
            axes=[
                Dict{String,Any}(
                    "name" => "frequency",
                    "unit" => "Hz",
                    "path" => "/axes/frequency",
                    "values" => frequency,
                ),
                Dict{String,Any}(
                    "name" => "window_length",
                    "unit" => "m",
                    "path" => "/axes/window_length",
                    "values" => sweep1,
                ),
                Dict{String,Any}(
                    "name" => "coupling_cap",
                    "unit" => "F",
                    "path" => "/axes/coupling_cap",
                    "values" => sweep2,
                ),
            ],
            traces=[
                Dict{String,Any}(
                    "trace_key" => "S21",
                    "family" => "s_matrix",
                    "parameter" => "S21",
                    "representation" => "complex",
                    "real" => real,
                    "imag" => imag,
                    "axes" => ["frequency", "window_length", "coupling_cap"],
                    "chunk_shape" => [5, 1, 1],
                ),
            ],
        )

        manifest = JSON3.read(read(manifest_path, String))
        @test manifest.task_id == "task_3d"
        @test manifest.traces[1].trace_key == "S21"
        @test manifest.traces[1].shape == [5, 2, 2]
        @test manifest.traces[1].chunk_shape == [5, 1, 1]
        @test manifest.traces[1].axes[2].path == "/axes/window_length"
        @test isfile(joinpath(dir, "result.zarr", "traces", "S21", "real", "0.0.0"))
        @test isfile(joinpath(dir, "result.zarr", "traces", "S21", "real", "0.1.1"))
        @test manifest_sha256(manifest_path) isa String
    end
end
