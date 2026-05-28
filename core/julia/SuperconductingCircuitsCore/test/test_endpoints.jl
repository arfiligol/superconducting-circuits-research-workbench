@testset "endpoint constructors" begin
    lc = MinimalComponentLibrary.TestGroundedComponent("lc")
    qwr = MinimalComponentLibrary.TestLineComponent("qwr", [:main], :main)
    multi = MinimalComponentLibrary.TestLineComponent("multi", [:a, :b], nothing)

    @test pin(lc, :signal) isa PinEndpoint
    @test ground() isa GroundEndpoint
    @test external_node("drive") isa ExternalNodeEndpoint
    @test line_ref(qwr, :main) == LineRef("qwr", :main)
    @test line_tap(qwr; line=:main, at_m=0.2mm) isa LineTapEndpoint
    @test line_tap(qwr; at_m=0.2mm) isa LineTapEndpoint
    @test line_span(qwr; from_m=0.1mm, to_m=0.3mm) isa LineSpanEndpoint
    @test loop_endpoint(lc, :squid_loop) isa LoopEndpoint

    @test_throws FrameworkValidationError line_tap(qwr; at_m=-0.1mm)
    @test_throws FrameworkValidationError line_span(qwr; from_m=0.3mm, to_m=0.2mm)
    @test_throws FrameworkValidationError line_tap(multi; at_m=0.1mm)
end

