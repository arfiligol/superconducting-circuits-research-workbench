# This focused test freezes only the final-capture wide intrinsic PTC range
# contract. It stubs evaluator-owned runtime types and never invokes HB.

using Test

struct D3FeedlineRLGC end
struct D3HBSettings end
struct D3FloatingQubitNominal end

const D3_HZ_PER_GHZ = 1.0e9

function frequency_range_with_step(start_hz, stop_hz, step_hz)
	step = Float64(step_hz)
	step > 0 || error("frequency step must be positive.")
	point_count = round(Int, (Float64(stop_hz) - Float64(start_hz)) / step) + 1
	point_count >= 2 || error("frequency range must contain at least two points.")
	return collect(range(Float64(start_hz), Float64(stop_hz); length = point_count))
end

include(joinpath(
	@__DIR__,
	"..",
	"..",
	"notebooks",
	"pluto",
	"D3 Intrinsic Purcell Filter Design",
	"d3_coupled_evaluator.jl",
))

@testset "D3 intrinsic wide final-capture range" begin
	capture = _intrinsic_wide_capture_grid(
		(scan_stop_ghz = 7.3,),
		4.5e9,
		6.001e9,
		0.2e6,
	)
	@test first(capture.frequencies_hz) == 4.0e9
	@test last(capture.frequencies_hz) == 7.3e9
	@test length(capture.frequencies_hz) == 16_501
	@test capture.range_provenance.scope == "final_capture_only"
	@test capture.range_provenance.start_margin_below_notch_hz == 500.0e6
	@test capture.range_provenance.required_minimum_stop_hz == 6.501e9
	@test capture.range_provenance.stop_role == "conservative_no_cext_intrinsic_resonator_upper_bound"

	@test_throws ErrorException _intrinsic_wide_capture_grid(
		(scan_stop_ghz = 6.5,),
		4.5e9,
		6.001e9,
		0.2e6,
	)
	@test_throws ErrorException _intrinsic_wide_capture_grid(
		(scan_stop_ghz = 7.3,),
		4.5e9,
		6.001e9,
		0.0,
	)
end
