const SCC = SuperconductingCircuitsCore

const DIAGNOSTIC_API_NAMES = (
    :DiagnosticIssue,
    :DiagnosticReport,
    :diagnostic_errors,
    :diagnostic_warnings,
    :has_diagnostic_errors,
    :diagnose_plan,
    :diagnose_compile,
    :diagnose_sweep,
    :explain_topology_key,
    :diff_topology_keys,
    :debug_bundle,
)

function require_diagnostics_api(name::Symbol)
    in_module = isdefined(SCC, name)
    exported = isdefined(@__MODULE__, name)
    @test in_module
    @test exported
    return in_module ? getproperty(SCC, name) : nothing
end

function diagnostic_get(container, key::Symbol)
    if container isa AbstractDict
        return get(container, key, nothing)
    elseif hasproperty(container, key)
        return getproperty(container, key)
    end
    return nothing
end

function diagnostic_issue_codes(report, diagnostic_errors_fn)
    issues = diagnostic_errors_fn(report)
    return [issue.code for issue in issues if hasproperty(issue, :code)]
end

function topology_diff_entries(diff, fields)
    entries = Any[]
    for field in fields
        @test hasproperty(diff, field)
        hasproperty(diff, field) || continue
        append!(entries, collect(getproperty(diff, field)))
    end
    return entries
end

function assert_structured_topology_entries(diff, fields)
    entries = topology_diff_entries(diff, fields)
    @test !isempty(entries)
    for entry in entries
        @test !(entry isa AbstractString)
    end
    return entries
end

function diagnostic_plan(; id="diagnostics", tap_m=0.1e-3, numeric_domain=(1.0e-15, 2.0e-15))
    plan = CircuitPlan(id)
    qwr = register_component!(plan, MinimalComponentLibrary.TestLineComponent("qwr", [:main], :main))
    lc = register_component!(plan, MinimalComponentLibrary.TestGroundedComponent("lc"))
    register_parameter!(
        plan,
        ParameterMetadata(
            name=:diagnostic_numeric_capacitance,
            role=NumericParameter(),
            owner="lc",
            targets=[:capacitance],
            sweep_name=:diagnostic_numeric_capacitance,
            units="F",
            valid_domain=numeric_domain,
        ),
    )
    register_parameter!(
        plan,
        ParameterMetadata(
            name=:diagnostic_n_sections,
            role=StructuralParameter(),
            owner="qwr",
            targets=[:n_sections],
            sweep_name=:diagnostic_n_sections,
        ),
    )
    couple_capacitive!(
        plan;
        id="diagnostic_coupling",
        from=pin(lc, :signal),
        to=line_tap(qwr; at_m=tap_m),
        capacitance=1.0e-15,
    )
    return plan
end

function diagnostic_span_plan(; id="span-diagnostics", span_from_m=0.1e-3, span_to_m=0.2e-3)
    plan = CircuitPlan(id)
    line_a_component = register_component!(plan, MinimalComponentLibrary.TestLineComponent("qwr_a", [:main], :main))
    line_b_component = register_component!(plan, MinimalComponentLibrary.TestLineComponent("qwr_b", [:main], :main))
    couple_window!(
        plan;
        id="diagnostic_window",
        line_a=line_span(line_a_component; from_m=span_from_m, to_m=span_to_m),
        line_b=line_span(line_b_component; from_m=span_from_m, to_m=span_to_m),
        spec=base_window_spec(length_m=span_to_m - span_from_m),
    )
    return plan
end

function diagnostic_bad_plan()
    plan = CircuitPlan("bad-diagnostics")
    connect!(plan, pin("missing", :signal), ground())
    return plan
end

function diagnostic_sweep_plan(params)
    tap_m = get(params, :tap_m, 0.1e-3)
    coupling_f = get(params, :coupling_f, 1.0e-15)
    return diagnostic_plan(; id="diagnostic-sweep", tap_m=tap_m, numeric_domain=(coupling_f, coupling_f))
end

@testset "diagnostics public API is exported" begin
    for name in DIAGNOSTIC_API_NAMES
        require_diagnostics_api(name)
    end
end

@testset "DiagnosticIssue carries structured debug fields" begin
    DiagnosticIssueType = require_diagnostics_api(:DiagnosticIssue)
    if !isnothing(DiagnosticIssueType)
        issue = DiagnosticIssueType(
            severity=:error,
            code=:unresolved_endpoint,
            message="Endpoint references missing component.",
            path=[:relations, :diagnostic_coupling],
            stage=:endpoint_resolution,
            object_id="missing",
            expected="registered component id",
            actual="missing component id",
            hint="Register the component before connecting to its pin.",
            related_ids=["lc", "qwr"],
            metadata=Dict{Symbol,Any}(:endpoint => :signal),
        )

        @test issue.severity == :error
        @test issue.code == :unresolved_endpoint
        @test issue.message == "Endpoint references missing component."
        @test issue.path == [:relations, :diagnostic_coupling]
        @test issue.stage == :endpoint_resolution
        @test issue.object_id == "missing"
        @test issue.expected == "registered component id"
        @test issue.actual == "missing component id"
        @test issue.hint == "Register the component before connecting to its pin."
        @test issue.related_ids == ["lc", "qwr"]
        @test issue.metadata[:endpoint] == :signal
    end
end

@testset "ValidationIssue exposes diagnostic-grade metadata" begin
    plan = CircuitPlan("validation-diagnostics")
    register_component!(plan, MinimalComponentLibrary.TestGroundedComponent("lc"))
    register_component!(plan, MinimalComponentLibrary.TestGroundedComponent("lc"))
    report = validate_authoring(plan)

    @test has_errors(report)
    duplicate = first(issue for issue in errors(report) if issue.code == :duplicate_component_id)
    @test duplicate.code == :duplicate_component_id
    @test hasproperty(duplicate, :stage)
    hasproperty(duplicate, :stage) && @test duplicate.stage == :authoring
    @test hasproperty(duplicate, :object_id) || hasproperty(duplicate, :related_ids)
    if hasproperty(duplicate, :object_id) || hasproperty(duplicate, :related_ids)
        object_id = hasproperty(duplicate, :object_id) ? duplicate.object_id : nothing
        related_ids = hasproperty(duplicate, :related_ids) ? duplicate.related_ids : String[]
        @test object_id == "lc" || "lc" in related_ids
    end
    @test occursin("Duplicate component id", duplicate.message)
end

@testset "diagnose_plan reports unresolved endpoints" begin
    required = (:DiagnosticReport, :diagnostic_errors, :has_diagnostic_errors, :diagnose_plan)
    if all(name -> !isnothing(require_diagnostics_api(name)), required)
        DiagnosticReportType = getproperty(SCC, :DiagnosticReport)
        diagnostic_errors_fn = getproperty(SCC, :diagnostic_errors)
        has_diagnostic_errors_fn = getproperty(SCC, :has_diagnostic_errors)
        diagnose_plan_fn = getproperty(SCC, :diagnose_plan)

        report = diagnose_plan_fn(diagnostic_bad_plan())
        @test report isa DiagnosticReportType
        @test hasproperty(report, :stage)
        if hasproperty(report, :stage)
            @test report.stage == :authoring
            @test haskey(report.summary, :stage)
            haskey(report.summary, :stage) && @test report.summary[:stage] == report.stage
        end
        @test has_diagnostic_errors_fn(report)
        @test :unresolved_endpoint in diagnostic_issue_codes(report, diagnostic_errors_fn)
    end
end

@testset "diagnose_compile reports compile readiness failure without crashing" begin
    required = (:DiagnosticReport, :diagnostic_errors, :has_diagnostic_errors, :diagnose_compile)
    if all(name -> !isnothing(require_diagnostics_api(name)), required)
        DiagnosticReportType = getproperty(SCC, :DiagnosticReport)
        diagnostic_errors_fn = getproperty(SCC, :diagnostic_errors)
        has_diagnostic_errors_fn = getproperty(SCC, :has_diagnostic_errors)
        diagnose_compile_fn = getproperty(SCC, :diagnose_compile)

        report = diagnose_compile_fn(diagnostic_bad_plan())
        @test report isa DiagnosticReportType
        @test hasproperty(report, :stage)
        if hasproperty(report, :stage)
            @test report.stage in (:compile_validation, :compile_lowering)
            @test haskey(report.summary, :stage)
            haskey(report.summary, :stage) && @test report.summary[:stage] == report.stage
        end
        @test has_diagnostic_errors_fn(report)
        issues = diagnostic_errors_fn(report)
        @test any(issue -> hasproperty(issue, :stage) && issue.stage == :compile_validation, issues)
        @test :unresolved_endpoint in [issue.code for issue in issues if hasproperty(issue, :code)]
    end
end

@testset "explain_topology_key distinguishes included structural and excluded numeric parameters" begin
    explain_topology_key_fn = require_diagnostics_api(:explain_topology_key)
    if !isnothing(explain_topology_key_fn)
        explanation = explain_topology_key_fn(diagnostic_plan())
        @test !isempty(String(diagnostic_get(explanation, :digest)))
        @test diagnostic_get(explanation, :components_included) !== nothing
        @test diagnostic_get(explanation, :relations_included) !== nothing
        @test diagnostic_get(explanation, :line_taps_included) !== nothing

        structural = diagnostic_get(explanation, :structural_parameters_included)
        numeric = diagnostic_get(explanation, :numeric_parameters_excluded)
        @test structural !== nothing
        @test numeric !== nothing
        @test occursin("diagnostic_n_sections", repr(structural))
        @test occursin("diagnostic_numeric_capacitance", repr(numeric))
    end
end

@testset "diff_topology_keys reports structured line tap changes" begin
    diff_topology_keys_fn = require_diagnostics_api(:diff_topology_keys)
    if !isnothing(diff_topology_keys_fn)
        tap_a = diagnostic_plan(; id="tap-a", tap_m=0.1e-3)
        tap_b = diagnostic_plan(; id="tap-b", tap_m=0.2e-3)
        before_a = topology_key(tap_a).digest
        before_b = topology_key(tap_b).digest

        tap_diff = diff_topology_keys_fn(tap_a, tap_b)
        @test diagnostic_get(tap_diff, :same_digest) == false
        assert_structured_topology_entries(
            tap_diff,
            (:changed_line_taps, :added_line_taps, :removed_line_taps),
        )
        @test topology_key(tap_a).digest == before_a
        @test topology_key(tap_b).digest == before_b
    end
end

@testset "diff_topology_keys reports structured line span changes" begin
    diff_topology_keys_fn = require_diagnostics_api(:diff_topology_keys)
    if !isnothing(diff_topology_keys_fn)
        span_a = diagnostic_span_plan(; id="span-a", span_from_m=0.1e-3, span_to_m=0.2e-3)
        span_b = diagnostic_span_plan(; id="span-b", span_from_m=0.1e-3, span_to_m=0.3e-3)
        before_a = topology_key(span_a).digest
        before_b = topology_key(span_b).digest

        span_diff = diff_topology_keys_fn(span_a, span_b)
        @test diagnostic_get(span_diff, :same_digest) == false
        assert_structured_topology_entries(
            span_diff,
            (:changed_line_spans, :added_line_spans, :removed_line_spans),
        )
        @test topology_key(span_a).digest == before_a
        @test topology_key(span_b).digest == before_b
    end
end

@testset "diff_topology_keys treats numeric-only differences as reusable" begin
    diff_topology_keys_fn = require_diagnostics_api(:diff_topology_keys)
    if !isnothing(diff_topology_keys_fn)
        numeric_a = diagnostic_plan(; id="numeric-a", tap_m=0.1e-3, numeric_domain=(1.0e-15, 2.0e-15))
        numeric_b = diagnostic_plan(; id="numeric-b", tap_m=0.1e-3, numeric_domain=(9.0e-15, 10.0e-15))
        before_a = topology_key(numeric_a).digest
        before_b = topology_key(numeric_b).digest

        numeric_diff = diff_topology_keys_fn(numeric_a, numeric_b)
        @test diagnostic_get(numeric_diff, :same_digest) == true
        for field in (:changed_line_taps, :changed_line_spans, :changed_structural_parameters)
            @test hasproperty(numeric_diff, field)
            hasproperty(numeric_diff, field) && @test isempty(getproperty(numeric_diff, field))
        end
        @test hasproperty(numeric_diff, :ignored_numeric_parameters)
        @test topology_key(numeric_a).digest == before_a
        @test topology_key(numeric_b).digest == before_b
    end
end

@testset "diagnose_sweep exposes preflight estimates and executor" begin
    required = (:DiagnosticReport, :diagnose_sweep)
    if all(name -> !isnothing(require_diagnostics_api(name)), required)
        DiagnosticReportType = getproperty(SCC, :DiagnosticReport)
        diagnose_sweep_fn = getproperty(SCC, :diagnose_sweep)
        sweep = SweepSpec(
            axes=(
                tap_m=StructuralAxis([0.1e-3, 0.2e-3]),
                coupling_f=NumericAxis([1.0e-15, 2.0e-15]),
            ),
            compile_policy=CompileByTopologyKey(),
            executor=SerialExecutor(),
        )

        report = diagnose_sweep_fn(diagnostic_sweep_plan, sweep)
        @test report isa DiagnosticReportType
        @test hasproperty(report, :stage)
        if hasproperty(report, :stage)
            @test report.stage == :sweep_preflight
            @test haskey(report.summary, :stage)
            haskey(report.summary, :stage) && @test report.summary[:stage] == report.stage
        end
        @test diagnostic_get(report.summary, :axis_count) == 2
        @test diagnostic_get(report.summary, :estimated_simulations) == 4
        @test diagnostic_get(report.summary, :estimated_compiles) == 2
        @test diagnostic_get(report.summary, :topology_group_count) == 2
        @test occursin("SerialExecutor", repr(diagnostic_get(report.summary, :executor)))
    end
end

@testset "debug_bundle includes required sections and diagnostics do not mutate inputs" begin
    required = (:debug_bundle, :explain_topology_key, :diagnose_plan, :diagnose_compile)
    if all(name -> !isnothing(require_diagnostics_api(name)), required)
        debug_bundle_fn = getproperty(SCC, :debug_bundle)
        plan = diagnostic_plan()
        compiled = compile_to_josephson(plan)
        sweep = SweepSpec(axes=(coupling_f=NumericAxis([1.0e-15, 2.0e-15]),), compile_policy=CompileOnce())
        preflight = preflight_sweep(diagnostic_sweep_plan, sweep)
        result = run_parameter_sweep(diagnostic_sweep_plan, sweep)

        before = (
            component_count=length(plan.components),
            relation_count=length(plan.relations),
            endpoint_count=length(plan.endpoints),
            parameter_count=length(plan.parameters),
            topology_digest=topology_key(plan).digest,
            result_statuses=copy(result.point_statuses),
        )

        bundle = debug_bundle_fn(plan; compiled=compiled, preflight=preflight, result=result)

        for key in (
            :plan_summary,
            :parameter_summary,
            :endpoint_summary,
            :authoring_diagnostics,
            :compile_diagnostics,
            :diagnostic_stages,
            :topology_explanation,
            :compiled_summary,
            :preflight_summary,
            :sweep_result_summary,
            :recommended_next_checks,
        )
            @test diagnostic_get(bundle, key) !== nothing
        end
        @test bundle.diagnostic_stages.authoring == :authoring
        @test bundle.diagnostic_stages.compile in (:compile_validation, :compile_lowering)

        after = (
            component_count=length(plan.components),
            relation_count=length(plan.relations),
            endpoint_count=length(plan.endpoints),
            parameter_count=length(plan.parameters),
            topology_digest=topology_key(plan).digest,
            result_statuses=copy(result.point_statuses),
        )
        @test after == before
    end
end
