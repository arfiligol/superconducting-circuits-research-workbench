using JSON3
using SuperconductingCircuitsRunner
using Test

@testset "runner task contract" begin
    payload = Dict(
        "task" => Dict(
            "task_id" => "306",
            "task_kind" => "julia_runner_smoke",
            "input" => Dict{String,Any}(),
            "output_target" => Dict(
                "dataset_id" => "local-dataset-001",
                "design_id" => "design_runner_smoke",
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
    @test claim.task_kind == "julia_runner_smoke"
    @test claim.dataset_id == "local-dataset-001"
    @test claim.design_id == "design_runner_smoke"
end

@testset "runner dispatch" begin
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
        manifest_path = execute_task(smoke_claim)
        @test isfile(manifest_path)
        @test isdir(joinpath(dir, "result.zarr"))
        @test isfile(joinpath(dir, "result.zarr", ".zgroup"))
        @test isfile(joinpath(dir, "result.zarr", "axes", "frequency", ".zarray"))
        @test isfile(joinpath(dir, "result.zarr", "traces", "S11", "real", ".zarray"))
        @test isfile(joinpath(dir, "result.zarr", "traces", "S11", "imag", ".zarray"))
        @test isfile(joinpath(dir, "result.zarr", "traces", "S11", "real", "0"))
        @test isfile(joinpath(dir, "logs", "runner.log"))

        manifest = JSON3.read(read(manifest_path, String))
        @test manifest.schema_version == "sc.runner.result.v1"
        @test manifest.task_id == "task_smoke"
        @test manifest.array_store.zarr_format == 2
        @test manifest.traces[1].real_path == "/traces/S11/real"
        @test manifest.traces[1].imag_path == "/traces/S11/imag"
        @test manifest.traces[1].shape == [5]
        @test manifest_sha256(manifest_path) isa String

        frequency_claim = SuperconductingCircuitsRunner.RunnerClaim(
            "task_frequency",
            "julia_simulation_frequency_sweep",
            Dict{String,Any}(),
            nothing,
            nothing,
            dir,
            joinpath(dir, "result.zarr"),
            joinpath(dir, "manifest.json"),
        )
        @test_throws ErrorException execute_task(frequency_claim)

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
        @test_throws ErrorException execute_task(unknown_claim)
    end
end

@testset "trace zarr package writer" begin
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
