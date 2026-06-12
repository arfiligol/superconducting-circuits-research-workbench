import Pkg

const REPO_ROOT = normpath(joinpath(@__DIR__, "..", "..", ".."))
const REPO_PYTHON = joinpath(REPO_ROOT, ".venv", "bin", "python")

if !haskey(ENV, "JULIA_PYTHONCALL_EXE") && isfile(REPO_PYTHON)
    ENV["JULIA_PYTHONCALL_EXE"] = REPO_PYTHON
end
ENV["JULIA_CONDAPKG_BACKEND"] = get(ENV, "JULIA_CONDAPKG_BACKEND", "Null")

Pkg.instantiate()

using Documenter
using SuperconductingCircuitsAnalysisBridge
using SuperconductingCircuitsCore
using SuperconductingCircuitsRunner
using SuperconductingCircuitsVisualizer

makedocs(
    sitename = "Superconducting Circuits Julia API",
    authors = "Superconducting Circuits Research Workbench contributors",
    modules = [
        SuperconductingCircuitsCore,
        SuperconductingCircuitsVisualizer,
        SuperconductingCircuitsRunner,
        SuperconductingCircuitsAnalysisBridge,
    ],
    format = Documenter.HTML(
        prettyurls = true,
        inventory_version = "0.1.0",
    ),
    doctest = false,
    checkdocs = :none,
    source = "src",
    build = "../../../build/api-reference/julia/html",
    pages = [
        "Overview" => "index.md",
        "SuperconductingCircuitsCore" => "core.md",
        "SuperconductingCircuitsVisualizer" => "visualizer.md",
        "SuperconductingCircuitsRunner" => "runner.md",
        "SuperconductingCircuitsAnalysisBridge" => "analysis-bridge.md",
    ],
)
