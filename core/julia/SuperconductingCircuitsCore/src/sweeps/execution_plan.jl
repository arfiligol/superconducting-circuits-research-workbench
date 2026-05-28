struct SweepExecutionPlan
    sweep_spec::SweepSpec
    compile_policy::Any
    executor::Any
    acceleration_policy::Any
    axes::Dict{Symbol,AbstractSweepAxis}
    role_report::Dict{Symbol,Any}
    topology_groups::Dict{String,Vector{Int}}
    estimated_compiles::Int
    estimated_simulations::Int
    warnings::Vector{String}
end

