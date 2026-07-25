# This CLI dispatches the auditable D3 circuit-forward workflow. It accepts
# every consumed artifact explicitly, activates the owning Core Julia project,
# and delegates all research semantics to the notebook-owned execution file.
# It does not fit bare QRP parameters or infer private-layout paths.

import Pkg

const WORKBENCH_ROOT = dirname(dirname(abspath(@__DIR__)))
const D3_NOTEBOOK_ROOT = joinpath(
    WORKBENCH_ROOT,
    "notebooks",
    "pluto",
    "D3 Intrinsic Purcell Filter Design",
)
const CORE_PROJECT = joinpath(WORKBENCH_ROOT, "core", "julia", "SuperconductingCircuitsCore")

Pkg.activate(CORE_PROJECT; io = devnull)

using LinearAlgebra
using SuperconductingCircuitsCore

include(joinpath(D3_NOTEBOOK_ROOT, "d3_purcell_common.jl"))
include(joinpath(D3_NOTEBOOK_ROOT, "d3_floating_qubit_input.jl"))
include(joinpath(D3_NOTEBOOK_ROOT, "d3_forward_validation_common.jl"))
include(joinpath(D3_NOTEBOOK_ROOT, "d3_forward_response_common.jl"))
include(joinpath(D3_NOTEBOOK_ROOT, "d3_forward_execution.jl"))

const D3_FORWARD_REQUIRED_FLAGS = (
    "--target",
    "--initializer",
    "--q2d-pair",
    "--q2d-single",
    "--qubit",
    "--config",
    "--output",
)

function d3_forward_usage()
    return join(
        [
            "Usage:",
            "  julia scripts/build/run_d3_forward_circuit_validation.jl \\",
            "    --target PATH --initializer PATH --q2d-pair PATH --q2d-single PATH \\",
            "    --qubit PATH --config PATH --output PATH [--run-bare-fit]",
            "",
            "--run-bare-fit is accepted only to exercise the required fail-fast boundary.",
        ],
        '\n',
    )
end

function parse_d3_forward_arguments(arguments)
    values = Dict{String,String}()
    bare_fit_requested = false
    index = 1
    while index <= length(arguments)
        flag = String(arguments[index])
        if flag == "--run-bare-fit"
            bare_fit_requested && error("--run-bare-fit may be supplied at most once.")
            bare_fit_requested = true
            index += 1
            continue
        end
        flag in D3_FORWARD_REQUIRED_FLAGS || error(
            "Unknown D3 forward argument $(flag).\n$(d3_forward_usage())",
        )
        haskey(values, flag) && error("Duplicate D3 forward argument $(flag).")
        index < length(arguments) || error("Missing value for $(flag).")
        value = String(arguments[index + 1])
        startswith(value, "--") && error("Missing value for $(flag).")
        isempty(strip(value)) && error("Value for $(flag) must be nonempty.")
        values[flag] = value
        index += 2
    end
    missing = [flag for flag in D3_FORWARD_REQUIRED_FLAGS if !haskey(values, flag)]
    isempty(missing) || error(
        "Missing required D3 forward arguments: $(join(missing, ", ")).\n$(d3_forward_usage())",
    )
    return (values = values, bare_fit_requested = bare_fit_requested)
end

function main(arguments)
    parsed = parse_d3_forward_arguments(arguments)
    values = parsed.values
    result = run_d3_forward_circuit_validation(
        target_path = values["--target"],
        initializer_path = values["--initializer"],
        q2d_pair_path = values["--q2d-pair"],
        q2d_single_path = values["--q2d-single"],
        qubit_path = values["--qubit"],
        config_path = values["--config"],
        output_path = values["--output"],
        bare_fit_requested = parsed.bare_fit_requested,
    )
    println(result.primary)
    println(result.search_evidence)
    return nothing
end

main(ARGS)
