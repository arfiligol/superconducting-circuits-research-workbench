#!/usr/bin/env julia

using Pkg

const REPO_ROOT = normpath(joinpath(@__DIR__, "..", ".."))
const LOCAL_DEV_TOOLS = ["Revise"]
const LOCAL_PACKAGES = [
    (
        name = "SuperconductingCircuitsCore",
        path = joinpath(REPO_ROOT, "core", "julia", "SuperconductingCircuitsCore"),
    ),
    (
        name = "SuperconductingCircuitsVisualizer",
        path = joinpath(REPO_ROOT, "core", "julia", "SuperconductingCircuitsVisualizer"),
    ),
]
const LOCAL_PACKAGE_PROJECT_FILES = Set(
    normpath(joinpath(package.path, "Project.toml")) for package in LOCAL_PACKAGES
)

function require_project(package)
    project_file = joinpath(package.path, "Project.toml")
    isfile(project_file) || error("Expected $(package.name) Project.toml at $(project_file)")
    return package.path
end

active_project = Base.active_project()
active_project_file = isnothing(active_project) ? nothing : normpath(active_project)
if active_project_file in LOCAL_PACKAGE_PROJECT_FILES
    error(
        "Refusing to install dev tools into a package environment. " *
        "Run with --project=@v1.12 or another developer environment instead.",
    )
end

println("Installing local Julia dev packages into active environment:")
println("  ", isnothing(active_project) ? "(Julia default environment)" : active_project)

for tool in LOCAL_DEV_TOOLS
    println("  add ", tool)
    Pkg.add(Pkg.PackageSpec(name=tool))
end

for package in LOCAL_PACKAGES
    project_path = require_project(package)
    println("  dev ", package.name, " => ", project_path)
    Pkg.develop(Pkg.PackageSpec(path=project_path))
end

Pkg.resolve()
Pkg.instantiate()
Pkg.precompile()

@eval using Revise
@eval using SuperconductingCircuitsCore
@eval using SuperconductingCircuitsVisualizer

println("Installed package paths:")
println("  Revise => ", pathof(Revise))
println("  SuperconductingCircuitsCore => ", pathof(SuperconductingCircuitsCore))
println("  SuperconductingCircuitsVisualizer => ", pathof(SuperconductingCircuitsVisualizer))
