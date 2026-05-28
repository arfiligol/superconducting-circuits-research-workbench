using SuperconductingCircuitsCore
using Test

include("fixtures/minimal_component_library.jl")
using .MinimalComponentLibrary

const mm = 1e-3

function base_line_spec(; length_m=1.0mm, n_sections=4)
    return RLGCSpec(
        length_m=length_m,
        n_sections=n_sections,
        l_per_m_h=4.2e-7,
        c_per_m_f=1.7e-10,
    )
end

function base_window_spec(; length_m=0.1mm, n_sections=2)
    return CoupledWindowSpec(
        length_m=length_m,
        n_sections=n_sections,
        l11_per_m_h=4.2e-7,
        l22_per_m_h=4.2e-7,
        lm_per_m_h=0.5e-7,
        c1g_per_m_f=1.7e-10,
        c2g_per_m_f=1.7e-10,
        cm_per_m_f=1.0e-12,
    )
end

include("test_low_level_helpers.jl")
include("test_circuit_plan.jl")
include("test_endpoints.jl")
include("test_relations.jl")
include("test_parameters.jl")
include("test_compiler_skeleton.jl")
include("test_compiler_lumped_lowering.jl")
include("test_sweeps.jl")
include("test_inspection.jl")
include("test_diagnostics.jl")
