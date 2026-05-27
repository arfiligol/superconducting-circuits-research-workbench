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

@testset "smoke result package" begin
    mktempdir() do dir
        manifest_path = write_smoke_result_package(dir; task_id="task_smoke")
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
    end
end
