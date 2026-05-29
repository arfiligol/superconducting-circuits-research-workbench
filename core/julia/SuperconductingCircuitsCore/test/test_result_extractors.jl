struct ResultExtractorFullLinearized
    modes::Vector{Tuple{Int}}
    portnumbers::Vector{Int}
    S::Array{ComplexF64,3}
    Z::Array{ComplexF64,3}
    QE::Array{Float64,3}
    QEideal::Array{Float64,3}
    CM::Array{Float64,3}
end

struct ResultExtractorSOnlyLinearized
    modes::Vector{Tuple{Int}}
    portnumbers::Vector{Int}
    S::Array{ComplexF64,3}
end

struct ResultExtractorSolution{T}
    linearized::T
end

function _extractor_complex_cube(base)
    values = ComplexF64[
        base + 1 + 0im,
        base + 2 + 0im,
    ]
    return reshape(values, 1, 1, 2)
end

function _extractor_real_cube(base)
    values = Float64[
        base + 1,
        base + 2,
    ]
    return reshape(values, 1, 1, 2)
end

function _result_extractor_validation_message(f)
    try
        f()
    catch err
        @test err isa FrameworkValidationError
        return sprint(showerror, err)
    end
    @test false
    return ""
end

@testset "result extractors collect requested S/Z/QE/QEideal/CM families" begin
    solution = ResultExtractorSolution(
        ResultExtractorFullLinearized(
            [(0,)],
            [1],
            _extractor_complex_cube(0),
            _extractor_complex_cube(10),
            _extractor_real_cube(20),
            _extractor_real_cube(30),
            _extractor_real_cube(40),
        ),
    )

    traces = extract_linearized_traces(
        solution;
        requested_families=(:S, :Z, :QE, :QEideal, :CM),
    )

    label = "om=0|op=1|im=0|ip=1"
    @test traces[:s_parameter_mode][label] == ComplexF64[1 + 0im, 2 + 0im]
    @test traces[:z_parameter_mode][label] == ComplexF64[11 + 0im, 12 + 0im]
    @test traces[:qe_mode][label] == Float64[21, 22]
    @test traces[:qeideal_mode][label] == Float64[31, 32]
    @test traces[:cm_mode]["om=0|op=1"] == Float64[41, 42]
end

@testset "result extractors fail clearly for missing requested output families" begin
    solution = ResultExtractorSolution(
        ResultExtractorSOnlyLinearized(
            [(0,)],
            [1],
            reshape(ComplexF64[1 + 0im, 2 + 0im], 1, 1, 2),
        ),
    )

    message = _result_extractor_validation_message() do
        extract_linearized_traces(solution; requested_families=(:S, :Z, :QE, :QEideal, :CM))
    end

    @test occursin("requested", lowercase(message))
    @test occursin("Z", message)
    @test occursin("QE", message)
    @test occursin("QEideal", message)
    @test occursin("CM", message)
end

@testset "result extractors reject unknown requested output families" begin
    solution = ResultExtractorSolution(
        ResultExtractorSOnlyLinearized(
            [(0,)],
            [1],
            reshape(ComplexF64[1 + 0im, 2 + 0im], 1, 1, 2),
        ),
    )

    message = _result_extractor_validation_message() do
        extract_linearized_traces(solution; requested_families=(:UnknownThing,))
    end

    @test occursin("unknown", lowercase(message))
    @test occursin("UnknownThing", message)
    @test occursin("S", message)
    @test occursin("Z", message)
    @test occursin("QE", message)
    @test occursin("QEideal", message)
    @test occursin("CM", message)
end

@testset "result extractors allow unrequested output families to be absent" begin
    solution = ResultExtractorSolution(
        ResultExtractorSOnlyLinearized(
            [(0,)],
            [1],
            reshape(ComplexF64[1 + 0im, 2 + 0im], 1, 1, 2),
        ),
    )

    traces = extract_linearized_traces(solution; requested_families=(:S,))

    @test traces[:s_parameter_mode]["om=0|op=1|im=0|ip=1"] == ComplexF64[1 + 0im, 2 + 0im]
    @test !haskey(traces, :z_parameter_mode) || isempty(traces[:z_parameter_mode])
    @test !haskey(traces, :qe_mode) || isempty(traces[:qe_mode])
    @test !haskey(traces, :qeideal_mode) || isempty(traces[:qeideal_mode])
    @test !haskey(traces, :cm_mode) || isempty(traces[:cm_mode])
end

@testset "result extractors preserve solver-returned NaN values" begin
    solution = ResultExtractorSolution(
        ResultExtractorFullLinearized(
            [(0,)],
            [1],
            reshape(ComplexF64[NaN + 0im, 2 + 0im], 1, 1, 2),
            _extractor_complex_cube(10),
            reshape(Float64[NaN, 22], 1, 1, 2),
            _extractor_real_cube(30),
            reshape(Float64[NaN, 42], 1, 1, 2),
        ),
    )

    traces = extract_linearized_traces(
        solution;
        requested_families=(:S, :QE, :CM),
    )

    label = "om=0|op=1|im=0|ip=1"
    @test isnan(real(traces[:s_parameter_mode][label][1]))
    @test isnan(traces[:qe_mode][label][1])
    @test isnan(traces[:cm_mode]["om=0|op=1"][1])
end
