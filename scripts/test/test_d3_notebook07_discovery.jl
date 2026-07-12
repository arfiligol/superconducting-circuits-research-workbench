using Test

const NOTEBOOK_07_PATH = normpath(joinpath(
	@__DIR__, "..", "..", "notebooks", "pluto",
	"D3 Intrinsic Purcell Filter Design", "07_coupled_cost_optimization.jl",
))

include(NOTEBOOK_07_PATH)

function synthetic_completed_run(runtime, directory; extraction_contract = D3_EXTRACTION_CONTRACT)
	mkdir(directory)
	metrics = d3_target_values(d3_contracts.target, runtime.slot_ghz)
	diagnostics = Dict{String,Any}()
	if !isnothing(extraction_contract)
		diagnostics["extraction_contract"] = extraction_contract
	end
	d3_write_json(joinpath(directory, "final_diagnostics.json"), Dict(
		"state" => "captured",
		"record" => Dict(
			"metrics" => metrics,
			"diagnostics" => diagnostics,
		),
	))
	d3_write_json(joinpath(directory, "layout_specs.json"), Dict(
		"artifact_approval" => "unapproved_exploration",
	))
	status = Dict(
		"state" => "completed",
		"execution_sha256" => runtime.execution_sha256,
		"execution_fingerprint_sha256" => runtime.execution_fingerprint_sha256,
		"nelder_mead_state" => "converged",
	)
	d3_write_json(joinpath(directory, "status.json"), status)
	d3_write_json(joinpath(directory, "condition_manifest.json"), runtime.manifest)
	for filename in ("config_snapshot.json", "hash_inventory.json", "optimization_result.json")
		d3_write_json(joinpath(directory, filename), Dict("synthetic_test_fixture" => true))
	end
	open(joinpath(directory, "evaluations.jsonl"), "w") do _ end
	@test Set(readdir(directory)) == D3_OUTPUT_FILES
	return d3_run_identity(directory)
end

@testset "Notebook 07 current-evidence discovery" begin
	runtime = d3_build_runtime(d3_contracts, d3_seed_catalog, 6.0)
	expected_fingerprint = d3_execution_fingerprint(d3_contracts, d3_seed_catalog, 6.0)
	@test runtime.execution_fingerprint_sha256 == expected_fingerprint

	mktempdir() do root
		missing_contract = synthetic_completed_run(
			runtime,
			joinpath(root, "missing-contract");
			extraction_contract = nothing,
		)
		v3_contract = synthetic_completed_run(
			runtime,
			joinpath(root, "v3-contract");
			extraction_contract = "d3-three-circuit-model-physical-vs-reduced-eligibility.v3",
		)

		for historical_run in (missing_contract, v3_contract)
			@test !d3_target_satisfying(
				historical_run,
				d3_contracts.target,
				d3_contracts.conditions,
				expected_fingerprint,
			)
			row = only(
				item for item in d3_discover_slots(
					d3_contracts,
					d3_seed_catalog;
					discovered_runs = [historical_run],
				) if item.slot_ghz == 6.0
			)
			@test row.state == "unfinished"
			@test !row.target_satisfying
			@test !row.reusable
			@test !row.rerun_blocked
			@test isnothing(d3_require_slot_runnable(6.0; discovered_runs = [historical_run]))
		end
	end

	mktempdir() do root
		current_run = synthetic_completed_run(runtime, joinpath(root, "current-v4"))
		@test d3_target_satisfying(
			current_run,
			d3_contracts.target,
			d3_contracts.conditions,
			expected_fingerprint,
		)
		row = only(
			item for item in d3_discover_slots(
				d3_contracts,
				d3_seed_catalog;
				discovered_runs = [current_run],
			) if item.slot_ghz == 6.0
		)
		@test row.state == "completed"
		@test row.target_satisfying
		@test row.reusable
		@test row.rerun_blocked
		@test_throws ErrorException d3_require_slot_runnable(
			6.0;
			discovered_runs = [current_run],
		)

		wrong_execution_status = merge(
			current_run,
			(status = merge(current_run.status, Dict("execution_sha256" => repeat("0", 64))),),
		)
		wrong_fingerprint_status = merge(
			current_run,
			(status = merge(
				current_run.status,
				Dict("execution_fingerprint_sha256" => repeat("0", 64)),
			),),
		)
		@test !d3_current_run_identity_matches(wrong_execution_status, expected_fingerprint)
		@test !d3_current_run_identity_matches(wrong_fingerprint_status, expected_fingerprint)
		@test !d3_current_run_identity_matches(current_run, repeat("f", 64))
	end
end
