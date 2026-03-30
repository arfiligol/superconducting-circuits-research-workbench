using JosephsonCircuits
using PlotlyJS
using Printf
using CSV
using DataFrames

include(joinpath(@__DIR__, "..", "src", "QubitExternalCouplingAnalysis.jl"))
using .QubitExternalCouplingAnalysis

include(joinpath(@__DIR__, "user_editable.jl"))
include(joinpath(@__DIR__, "circuit_definition.jl"))
include(joinpath(@__DIR__, "simulation_post_processing.jl"))
include(joinpath(@__DIR__, "plot_and_data_persisted_saving.jl"))

inputs = build_user_editable_inputs()
persisted_outputs = load_persisted_outputs()
display_persisted_plots_and_summary(inputs, persisted_outputs)
