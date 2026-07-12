# This focused test validates nominal persisted identities and exact-six output
# with a synthetic evaluator. It never loads Notebook 07, HB, the physical
# evaluator, an optimizer history candidate, or an existing D3 run.

using Test
using SuperconductingCircuitsCore

const JSON3 = SuperconductingCircuitsCore.JSON3
include(joinpath(@__DIR__, "..", "..", "notebooks", "pluto", "D3 Intrinsic Purcell Filter Design", "d3_nominal_validation.jl"))
using .D3NominalValidation

function write_test_json(path, value)
    mkpath(dirname(path))
    open(path, "w") do io
        JSON3.write(io, value)
        write(io, '\n')
    end
end

function make_sources(root)
    paths = Dict{String,String}()
    paths["target"] = joinpath(root, "docs", "target.json")
    write_test_json(paths["target"], Dict("target_id" => "synthetic-target", "targets" => Dict(
        "filter_loaded_bare_offset" => Dict("value" => 1.0),
        "readout_loaded_bare_offset" => Dict("value" => -1.0),
        "interference_notch_frequency" => Dict("value" => 4.5),
        "filter_loaded_bare_linewidth" => Dict("value" => 25.0),
        "readout_filter_exchange_coupling" => Dict("value" => 20.0),
        "qubit_readout_coupling" => Dict("value" => 90.0),
        "qubit_transition_frequency" => Dict("value" => 4.7, "unit" => "GHz"),
        "qubit_junction_inductance" => Dict("value" => 23.0, "unit" => "nH_per_junction", "parallel_junction_count" => 2),
        "readout_minus_filter_detuning" => Dict("value" => -2.0),
    )))
    specs = Dict(
        "filter_loaded_bare_hz" => Dict("scale" => 1e6, "weight" => 1.0),
        "readout_loaded_bare_hz" => Dict("scale" => 1e6, "weight" => 1.0),
        "notch_hz" => Dict("scale" => 1e6, "weight" => 1.0),
        "filter_loaded_linewidth_hz" => Dict("scale" => 1e6, "weight" => 1.0),
        "j_hz" => Dict("scale" => 1e6, "weight" => 1.0),
        "g_hz" => Dict("scale" => 1e6, "weight" => 1.0),
        "readout_minus_filter_detuning_hz" => Dict("scale" => 0.5e6, "weight" => 0.0),
    )
    paths["conditions"] = joinpath(root, "workbench", "d3_optimizer_conditions.json")
    write_test_json(paths["conditions"], Dict("metric_specs" => specs, "sol_review" => Dict("status" => "pending", "hash_framing" => SEMANTIC_HASH_FRAMING)))
    for id in ("q2d", "seed", "common", "evaluator", "semantic_hash", "qubit_input_loader", "runner", "nominal_runtime")
        paths[id] = joinpath(root, "workbench", "$(id).txt")
        mkpath(dirname(paths[id]))
        write(paths[id], "synthetic $(id) source\n")
    end
    paths["qubit_input"] = joinpath(root, "workbench", "private", "floating-qubit.json")
    write_test_json(paths["qubit_input"], Dict(
        "schema_version" => "d3-floating-qubit-maxwell.v1",
        "model_id" => "synthetic-floating-qubit",
        "readout_self_capacitance_ownership" => "distributed_resonator_owns_self_capacitance",
        "L_J_per_junction_nH" => 23.0,
    ))
    return paths
end

function make_optimizer_fixture(root, paths)
    config = Dict(
        "target_contract" => Dict(
            "workspace_relative_path" => workspace_relative(paths["target"], root),
            "expected_sha256" => D3NominalValidation.file_sha256(paths["target"]),
        ),
        "orpen_case_json_workspace_path" => workspace_relative(paths["q2d"], root),
        "design_csv_workspace_root" => workspace_relative(dirname(paths["seed"]), root),
        "design_csv_filename" => basename(paths["seed"]),
        "floating_qubit_nominal_workspace_path" => workspace_relative(paths["qubit_input"], root),
    )
    source_ids = Dict(
        "target_contract" => "target",
        "optimizer_conditions" => "conditions",
        "seed_csv" => "seed",
        "orpen_case_json" => "q2d",
        "d3_purcell_common" => "common",
        "d3_coupled_evaluator" => "evaluator",
        "d3_semantic_hash" => "semantic_hash",
        "floating_qubit_nominal" => "qubit_input",
        "d3_floating_qubit_input_loader" => "qubit_input_loader",
    )
    consumed = [
        Dict(
            "id" => inventory_id,
            "path" => workspace_relative(paths[source_id], root),
            "sha256" => D3NominalValidation.file_sha256(paths[source_id]),
        )
        for (inventory_id, source_id) in sort!(collect(source_ids); by = first)
    ]
    conditions = JSON3.read(read(paths["conditions"], String), Dict{String,Any})
    conditions_contract = Dict(key => value for (key, value) in conditions if key != "sol_review")
    contract = Dict(
        "manifest_id" => "synthetic-d3-optimizer-v1",
        "target_contract" => Dict("sha256" => D3NominalValidation.file_sha256(paths["target"])),
        "optimizer_conditions" => Dict("sha256" => semantic_value_sha256(conditions_contract), "hash_framing" => SEMANTIC_HASH_FRAMING),
        "selection" => Dict(
            "case_id" => "height7",
            "target_set_id" => "d3",
            "slot_target_ghz" => 6.0,
            "source_row" => Dict("id" => "synthetic-row"),
        ),
        "consumed_files" => consumed,
        "floating_qubit_nominal" => Dict(
            "schema_version" => "d3-floating-qubit-maxwell.v1",
            "model_id" => "synthetic-floating-qubit",
            "input_sha256" => D3NominalValidation.file_sha256(paths["qubit_input"]),
            "readout_self_capacitance_ownership" => "distributed_resonator_owns_self_capacitance",
            "readout_diagonal_instantiated" => false,
            "L_J_per_junction_nH" => 23.0,
            "canonical_targets" => Dict(
                "target_contract_id" => "synthetic-target",
                "target_contract_sha256" => D3NominalValidation.file_sha256(paths["target"]),
                "qubit_transition_frequency" => Dict("value" => 4.7e9, "unit" => "Hz"),
                "qubit_junction_inductance" => Dict("value" => 23.0, "unit" => "nH_per_junction"),
            ),
        ),
    )
    schema = "d3-slot-execution-manifest.v1"
    contract = JSON3.read(JSON3.write(contract), Dict{String,Any})
    identity = semantic_value_sha256(Dict("schema_version" => schema, "semantic_hash_framing" => SEMANTIC_HASH_FRAMING, "contract" => contract))
    run = joinpath(root, "workbench", "optimizer", "persisted-run__$(first(identity, 12))")
    mkpath(run)
    config_path = joinpath(run, "config_snapshot.json")
    write_test_json(config_path, config)
    paths["config_snapshot"] = config_path
    write_test_json(joinpath(run, "condition_manifest.json"), Dict(
        "schema_version" => schema,
        "semantic_hash_framing" => SEMANTIC_HASH_FRAMING,
        "execution_sha256" => identity,
        "contract" => contract,
    ))
    write_test_json(joinpath(run, "status.json"), Dict("state" => "completed", "execution_sha256" => identity))
    write_test_json(joinpath(run, "optimization_result.json"), Dict(
        "condition_manifest_id" => "synthetic-d3-optimizer-v1",
        "condition_manifest_sha256" => identity,
    ))
    variables = [
        Dict("id" => "lc_um", "value" => 193.0, "unit" => "um"),
        Dict("id" => "lp_short_um", "value" => 3492.0, "unit" => "um"),
        Dict("id" => "lr_short_um", "value" => 3327.0, "unit" => "um"),
        Dict("id" => "lp_open_um", "value" => 1144.0, "unit" => "um"),
        Dict("id" => "lr_open_um", "value" => 1641.0, "unit" => "um"),
        Dict("id" => "filter_to_line_capacitance_fF", "value" => 39.4, "unit" => "fF"),
    ]
    write_test_json(joinpath(run, "layout_specs.json"), Dict(
        "state" => "best_valid_candidate",
        "candidate_record_id" => "synthetic-candidate-1",
        "condition_manifest_sha256" => identity,
        "variables" => variables,
    ))
    write_test_json(joinpath(run, "hash_inventory.json"), Dict(
        "execution_sha256" => identity,
        "config_snapshot_sha256" => D3NominalValidation.file_sha256(config_path),
        "files" => consumed,
    ))
    write(joinpath(run, "evaluations.jsonl"), "")
    write_test_json(joinpath(run, "final_diagnostics.json"), Dict(
        "analysis_kind" => "optimizer_internal_final_reproduction",
        "independent_validation" => false,
        "execution_sha256" => identity,
        "state" => "captured",
    ))
    return run
end

function mark_isolated_optimizer_fixture(run)
    status_path = joinpath(run, "status.json")
    status = JSON3.read(read(status_path, String), Dict{String,Any})
    status["execution_mode"] = "isolated_direct_optimize_d3_after_legacy_governance_block"
    write_test_json(status_path, status)

    isolated_execution = Dict(
        "reason" => "formal_runner_blocked_by_legacy_completed_artifact_reuse",
        "formal_blocker" => "Synthetic formal runner rejected completed artifact reuse.",
        "optimizer_settings" => "unchanged_from_runtime",
        "initial_candidate_override" => Dict(
            "field" => "lr_open_um",
            "unit" => "um",
            "value" => 1414.25,
        ),
    )
    inventory_path = joinpath(run, "hash_inventory.json")
    inventory = JSON3.read(read(inventory_path, String), Dict{String,Any})
    inventory["isolated_execution"] = isolated_execution
    write_test_json(inventory_path, inventory)

    final_path = joinpath(run, "final_diagnostics.json")
    final_diagnostics = JSON3.read(read(final_path, String), Dict{String,Any})
    final_diagnostics["analysis_kind"] = "isolated_direct_optimizer_final_reproduction"
    final_diagnostics["record"] = Dict(
        "status" => "valid",
        "physical_evaluation_status" => "valid",
    )
    write_test_json(final_path, final_diagnostics)
    return isolated_execution
end

function synthetic_factory(factory_calls, evaluation_calls)
    metrics = (
        filter_loaded_bare_hz = 6.001e9,
        readout_loaded_bare_hz = 5.999e9,
        readout_minus_filter_detuning_hz = -2e6,
        loaded_bare_center_hz = 6e9,
        model_paired_pole_center_hz = 6e9,
        vector_paired_pole_center_hz = 6e9,
        pair_pole_center_offset_hz = 0.0,
        notch_hz = 4.5e9,
        filter_loaded_linewidth_hz = 25e6,
        j_hz = 20e6,
        g_hz = 90e6,
    )
    return () -> begin
        factory_calls[] += 1
        candidate_records -> begin
            evaluation_calls[] += 1
            @test String[item["id"] for item in candidate_records] == VARIABLE_IDS
            return (status = :valid, metrics = metrics, traces = (synthetic = [1.0, 2.0],))
        end
    end
end

@testset "D3 nominal validation identity contract" begin
    mktempdir() do root
        paths = make_sources(root)
        optimizer_run = make_optimizer_fixture(root, paths)
        preflight = preflight_optimizer_run(optimizer_run)
        @test preflight.is_current
        @test preflight.config_snapshot_sha256 == D3NominalValidation.file_sha256(paths["config_snapshot"])

        # Canonical execution-payload and final-diagnostics role tampering fail.
        manifest_path = joinpath(optimizer_run, "condition_manifest.json")
        optimizer_manifest = JSON3.read(read(manifest_path, String), Dict{String,Any})
        optimizer_manifest["contract"]["selection"]["case_id"] = "tampered"
        write_test_json(manifest_path, optimizer_manifest)
        @test_throws ErrorException preflight_optimizer_run(optimizer_run)
        optimizer_manifest["contract"]["selection"]["case_id"] = "height7"
        write_test_json(manifest_path, optimizer_manifest)

        final_path = joinpath(optimizer_run, "final_diagnostics.json")
        final_diagnostics = JSON3.read(read(final_path, String), Dict{String,Any})
        final_diagnostics["independent_validation"] = true
        write_test_json(final_path, final_diagnostics)
        @test_throws ErrorException preflight_optimizer_run(optimizer_run)
        final_diagnostics["independent_validation"] = false
        write_test_json(final_path, final_diagnostics)

        # Cross-artifact identity tampering must fail before evaluation.
        layout_path = joinpath(optimizer_run, "layout_specs.json")
        layout = JSON3.read(read(layout_path, String), Dict{String,Any})
        layout["condition_manifest_sha256"] = repeat("b", 64)
        write_test_json(layout_path, layout)
        @test_throws ErrorException preflight_optimizer_run(optimizer_run)
        layout["condition_manifest_sha256"] = preflight.optimizer_contract_sha256
        write_test_json(layout_path, layout)

        factory_calls = Ref(0)
        evaluation_calls = Ref(0)
        factory = synthetic_factory(factory_calls, evaluation_calls)
        output_root = joinpath(root, "workbench", "nominal-output")
        result = run_nominal_validation(
            optimizer_run;
            output_root = output_root,
            source_paths = paths,
            workspace_root = root,
            evaluator_factory = factory,
            fresh_process = true,
            fresh_evaluator = true,
        )
        @test factory_calls[] == evaluation_calls[] == 1
        @test Set(readdir(result.run_directory)) == VALIDATION_OUTPUT_FILES
        manifest = JSON3.read(read(joinpath(result.run_directory, "validation_manifest.json"), String), Dict{String,Any})
        @test !haskey(manifest["contract"], "source_optimizer_provenance")
        @test !isabspath(manifest["contract"]["source_optimizer"]["run_directory"])
        @test !occursin("..", manifest["contract"]["source_optimizer"]["run_directory"])
        @test all(!isabspath(item["path"]) && !occursin("..", item["path"]) for item in manifest["contract"]["source_hashes"])
        @test manifest["contract"]["bound_identities"]["config_snapshot_sha256"] == preflight.config_snapshot_sha256
        for name in VALIDATION_OUTPUT_FILES
            payload = JSON3.read(read(joinpath(result.run_directory, name), String), Dict{String,Any})
            @test payload["validation_contract_sha256"] == result.validation_contract_sha256
        end

        # Exact same validation fingerprint is view-only and blocks before factory creation.
        @test_throws ErrorException run_nominal_validation(
            optimizer_run;
            output_root = output_root,
            source_paths = paths,
            workspace_root = root,
            evaluator_factory = factory,
            fresh_process = true,
            fresh_evaluator = true,
        )
        @test factory_calls[] == evaluation_calls[] == 1

        # A changed runner hash is a different explicit validation contract.
        write(paths["runner"], "synthetic runner source revision 2\n")
        second = run_nominal_validation(
            optimizer_run;
            output_root = output_root,
            source_paths = paths,
            workspace_root = root,
            evaluator_factory = factory,
            fresh_process = true,
            fresh_evaluator = true,
        )
        @test second.validation_contract_sha256 != result.validation_contract_sha256
        @test factory_calls[] == evaluation_calls[] == 2

        malformed = joinpath(output_root, "20260711T000000000Z__nominal__malformed")
        mkpath(malformed)
        write_test_json(joinpath(malformed, "status.json"), Dict("state" => "completed"))
        @test_throws ErrorException run_nominal_validation(
            optimizer_run;
            output_root = output_root,
            source_paths = paths,
            workspace_root = root,
            evaluator_factory = factory,
            fresh_process = true,
            fresh_evaluator = true,
        )
        @test factory_calls[] == evaluation_calls[] == 2
        rm(malformed; recursive = true)

        # Persisted snapshot/path and Q2D drift cannot be replaced silently.
        wrong_config = joinpath(root, "workbench", "wrong-config.json")
        write_test_json(wrong_config, Dict("wrong" => true))
        wrong_paths = copy(paths)
        wrong_paths["config_snapshot"] = wrong_config
        @test_throws ErrorException run_nominal_validation(
            optimizer_run;
            output_root = output_root,
            source_paths = wrong_paths,
            workspace_root = root,
            evaluator_factory = factory,
            fresh_process = true,
            fresh_evaluator = true,
        )
        write(paths["q2d"], "tampered q2d\n")
        @test_throws ErrorException run_nominal_validation(
            optimizer_run;
            output_root = output_root,
            source_paths = paths,
            workspace_root = root,
            evaluator_factory = factory,
            fresh_process = true,
            fresh_evaluator = true,
        )
        @test factory_calls[] == evaluation_calls[] == 2
    end


    mktempdir() do root
        paths = make_sources(root)
        optimizer_run = make_optimizer_fixture(root, paths)
        isolated_execution = mark_isolated_optimizer_fixture(optimizer_run)
        preflight = preflight_optimizer_run(optimizer_run)
        expected_provenance = Dict(
            "analysis_kind" => "isolated_direct_optimizer_final_reproduction",
            "execution_mode" => "isolated_direct_optimize_d3_after_legacy_governance_block",
            "isolated_execution" => isolated_execution,
        )
        @test preflight.source_optimizer_provenance == expected_provenance

        output_root = joinpath(root, "workbench", "isolated-nominal-output")
        result = run_nominal_validation(
            optimizer_run;
            output_root = output_root,
            source_paths = paths,
            workspace_root = root,
            evaluator_factory = synthetic_factory(Ref(0), Ref(0)),
            fresh_process = true,
            fresh_evaluator = true,
        )
        manifest = JSON3.read(read(joinpath(result.run_directory, "validation_manifest.json"), String), Dict{String,Any})
        summary = JSON3.read(read(joinpath(result.run_directory, "validation_summary.json"), String), Dict{String,Any})
        @test manifest["contract"]["analysis_kind"] == "nominal"
        @test manifest["contract"]["source_optimizer_provenance"] == expected_provenance
        @test summary["source_optimizer_provenance"] == expected_provenance

        status_path = joinpath(optimizer_run, "status.json")
        status = JSON3.read(read(status_path, String), Dict{String,Any})
        status["execution_mode"] = "unsupported"
        write_test_json(status_path, status)
        @test_throws ErrorException preflight_optimizer_run(optimizer_run)
        status["execution_mode"] = "isolated_direct_optimize_d3_after_legacy_governance_block"
        write_test_json(status_path, status)

        inventory_path = joinpath(optimizer_run, "hash_inventory.json")
        inventory = JSON3.read(read(inventory_path, String), Dict{String,Any})
        delete!(inventory, "isolated_execution")
        write_test_json(inventory_path, inventory)
        @test_throws ErrorException preflight_optimizer_run(optimizer_run)
        inventory["isolated_execution"] = isolated_execution
        write_test_json(inventory_path, inventory)

        for (key, bad_value) in (
            ("reason", "unsupported"),
            ("formal_blocker", ""),
            ("optimizer_settings", "changed"),
        )
            inventory = JSON3.read(read(inventory_path, String), Dict{String,Any})
            inventory["isolated_execution"][key] = bad_value
            write_test_json(inventory_path, inventory)
            @test_throws ErrorException preflight_optimizer_run(optimizer_run)
            inventory["isolated_execution"][key] = isolated_execution[key]
            write_test_json(inventory_path, inventory)
        end
        inventory = JSON3.read(read(inventory_path, String), Dict{String,Any})
        inventory["isolated_execution"]["initial_candidate_override"] = Dict(
            "field" => "lr_open_um",
            "unit" => "fF",
            "value" => 1414.25,
        )
        write_test_json(inventory_path, inventory)
        @test_throws ErrorException preflight_optimizer_run(optimizer_run)
        inventory["isolated_execution"] = isolated_execution
        write_test_json(inventory_path, inventory)

        final_path = joinpath(optimizer_run, "final_diagnostics.json")
        final_diagnostics = JSON3.read(read(final_path, String), Dict{String,Any})
        final_diagnostics["analysis_kind"] = "unsupported"
        write_test_json(final_path, final_diagnostics)
        @test_throws ErrorException preflight_optimizer_run(optimizer_run)
    end
end
