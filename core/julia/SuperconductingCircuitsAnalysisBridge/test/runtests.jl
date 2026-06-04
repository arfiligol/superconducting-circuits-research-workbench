using SuperconductingCircuitsAnalysisBridge
using Test

@testset "bridge status" begin
    status = analysis_bridge_status()
    @test status isa BridgeStatus
    @test status.python_executable isa String
    @test status.message isa String
end
