#!/usr/bin/env julia

using SuperconductingCircuitsRunner

length(ARGS) == 2 || error("usage: circuit_workbench_runtime.jl REQUEST_JSON RECEIPT_JSON")
SuperconductingCircuitsRunner.execute_circuit_workbench_action(ARGS[1], ARGS[2])
