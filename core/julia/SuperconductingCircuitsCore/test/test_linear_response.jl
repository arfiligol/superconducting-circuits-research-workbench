using LinearAlgebra

@testset "linear terminal response follows exp(-i omega t)" begin
    capacitance = 92.0e-15
    inductance = 12.0e-9
    angular_root = 1 / sqrt(inductance * capacitance)
    angular_frequency = 0.83 * angular_root
    expected_admittance = im * (1 / (angular_frequency * inductance) - angular_frequency * capacitance)
    response = linear_terminal_response(
        reshape([capacitance], 1, 1),
        reshape([1 / inductance], 1, 1),
        angular_frequency,
        [1],
    )
    @test response.admittance[1, 1] ≈ expected_admittance rtol=1.0e-14
    @test response.impedance[1, 1] ≈ 1 / expected_admittance rtol=1.0e-14

    admittance = angular_frequency_value ->
        im * (1 / (angular_frequency_value * inductance) - angular_frequency_value * capacitance)
    found_root = bracketed_bisection(
        angular_frequency_value -> imag(admittance(angular_frequency_value)),
        (0.8 * angular_root, 1.2 * angular_root),
    )
    @test found_root ≈ angular_root rtol=1.0e-12
    step = angular_root * 1.0e-6
    matched = match_parallel_lc(
        admittance,
        angular_root;
        derivative_step_rad_s=step,
    )
    matrix_matched = match_parallel_lc(
        reshape([capacitance], 1, 1),
        reshape([1 / inductance], 1, 1),
        1,
        angular_root;
        derivative_step_rad_s=step,
    )
    @test matched.capacitance_f ≈ capacitance rtol=2.0e-10
    @test matched.inductance_h ≈ inductance rtol=2.0e-10
    @test matrix_matched.capacitance_f ≈ capacitance rtol=2.0e-10
    @test matrix_matched.inductance_h ≈ inductance rtol=2.0e-10
    @test matched.admittance_derivative_s_per_rad_s ≈ -2im * capacitance rtol=2.0e-10
end

function two_node_bridge_fixture()
    readout_capacitance = 120.0e-15
    filter_capacitance = 160.0e-15
    bridge_capacitance = 8.0e-15
    readout_root = 2π * 5.0e9
    filter_root = 2π * 7.0e9
    bridge_root = 2π * 6.0e9
    readout_inductance = 1 / (readout_root^2 * readout_capacitance)
    filter_inductance = 1 / (filter_root^2 * filter_capacitance)
    bridge_inductance = 1 / (bridge_root^2 * bridge_capacitance)
    capacitance = [
        readout_capacitance + bridge_capacitance -bridge_capacitance
        -bridge_capacitance filter_capacitance + bridge_capacitance
    ]
    inverse_inductance = [
        1 / readout_inductance + 1 / bridge_inductance -1 / bridge_inductance
        -1 / bridge_inductance 1 / filter_inductance + 1 / bridge_inductance
    ]
    readout_admittance = angular_frequency ->
        im * (1 / (angular_frequency * readout_inductance) - angular_frequency * readout_capacitance)
    filter_admittance = angular_frequency ->
        im * (1 / (angular_frequency * filter_inductance) - angular_frequency * filter_capacitance)
    transfer_impedance = angular_frequency -> linear_terminal_response(
        capacitance,
        inverse_inductance,
        angular_frequency,
        [1, 2],
    ).impedance[2, 1]
    return (
        capacitance=capacitance,
        inverse_inductance=inverse_inductance,
        readout_capacitance=readout_capacitance,
        filter_capacitance=filter_capacitance,
        bridge_capacitance=bridge_capacitance,
        readout_inductance=readout_inductance,
        filter_inductance=filter_inductance,
        bridge_inductance=bridge_inductance,
        readout_root=readout_root,
        filter_root=filter_root,
        bridge_root=bridge_root,
        readout_admittance=readout_admittance,
        filter_admittance=filter_admittance,
        transfer_impedance=transfer_impedance,
    )
end

@testset "two-node bridge response recovers all parallel LC branches" begin
    fixture = two_node_bridge_fixture()
    found_notch = bracketed_bisection(
        angular_frequency -> imag(fixture.transfer_impedance(angular_frequency)),
        (0.98 * fixture.bridge_root, 1.02 * fixture.bridge_root),
        relative_tolerance=1.0e-13,
    )
    @test found_notch ≈ fixture.bridge_root rtol=1.0e-12
    readout = match_parallel_lc(
        fixture.readout_admittance,
        fixture.readout_root;
        derivative_step_rad_s=fixture.readout_root * 1.0e-6,
    )
    filter = match_parallel_lc(
        fixture.filter_admittance,
        fixture.filter_root;
        derivative_step_rad_s=fixture.filter_root * 1.0e-6,
    )
    bridge = match_bridge_lc(
        fixture.transfer_impedance,
        fixture.readout_admittance,
        fixture.filter_admittance,
        fixture.bridge_root;
        derivative_step_rad_s=fixture.bridge_root * 1.0e-6,
    )
    @test readout.capacitance_f ≈ fixture.readout_capacitance rtol=2.0e-10
    @test readout.inductance_h ≈ fixture.readout_inductance rtol=2.0e-10
    @test filter.capacitance_f ≈ fixture.filter_capacitance rtol=2.0e-10
    @test filter.inductance_h ≈ fixture.filter_inductance rtol=2.0e-10
    @test bridge.capacitance_f ≈ fixture.bridge_capacitance rtol=2.0e-9
    @test bridge.inductance_h ≈ fixture.bridge_inductance rtol=2.0e-9
    @test abs(bridge.capacitance_imaginary_residual_f) < 1.0e-24
end

@testset "matched lossless response is unitary and closes S to Z" begin
    fixture = two_node_bridge_fixture()
    angular_frequency = 2π * 5.6e9
    selector = Matrix{Float64}(I, 2, 2)
    reference_impedance = [50.0, 73.0]
    matched = matched_port_response(
        fixture.capacitance,
        fixture.inverse_inductance,
        angular_frequency,
        selector,
        reference_impedance,
    )
    closed = linear_terminal_response(
        fixture.capacitance,
        fixture.inverse_inductance,
        angular_frequency,
        [1, 2],
    )
    @test matched.scattering' * matched.scattering ≈ Matrix{ComplexF64}(I, 2, 2) atol=2.0e-13
    @test matched.impedance ≈ closed.impedance rtol=2.0e-13 atol=1.0e-11
    @test scattering_to_impedance(matched.scattering, Diagonal(reference_impedance)) ≈
        closed.impedance rtol=2.0e-13 atol=1.0e-11
    @test impedance_to_scattering(closed.impedance, reference_impedance) ≈
        matched.scattering rtol=2.0e-13 atol=2.0e-13
end

@testset "matched response includes the internal G matrix" begin
    capacitance = reshape([100.0e-15], 1, 1)
    inverse_inductance = reshape([1 / 10.0e-9], 1, 1)
    internal_conductance = reshape([2.0e-3], 1, 1)
    angular_frequency = 2π * 4.0e9
    reference_impedance = 50.0
    matched = matched_port_response(
        capacitance,
        inverse_inductance,
        angular_frequency,
        reshape([1.0], 1, 1),
        reference_impedance;
        internal_conductance=internal_conductance,
    )
    expected_conductance = internal_conductance[1, 1] + 1 / reference_impedance
    expected_dynamic_stiffness = inverse_inductance[1, 1] -
        angular_frequency^2 * capacitance[1, 1] - im * angular_frequency * expected_conductance
    expected_scattering = -1 - 2im * angular_frequency / reference_impedance / expected_dynamic_stiffness
    @test matched.conductance == reshape([expected_conductance], 1, 1)
    @test matched.open_dynamic_stiffness[1, 1] ≈ expected_dynamic_stiffness rtol=1.0e-14
    @test matched.scattering[1, 1] ≈ expected_scattering rtol=1.0e-14
    @test abs2(matched.scattering[1, 1]) < 1
end

@testset "matched response preserves an exact direct connection" begin
    response = matched_port_response(
        zeros(1, 1),
        zeros(1, 1),
        2π * 5.0e9,
        [1.0 1.0],
        [50.0, 50.0];
        allow_semidefinite_capacitance=true,
        allow_dependent_ports=true,
        include_impedance=false,
    )
    @test response.scattering ≈ ComplexF64[0 1; 1 0] atol=1.0e-14
    @test isnothing(response.impedance)
end

@testset "matched single-LC open pole follows the state eigenvalue" begin
    capacitance = 100.0e-15
    inductance = 10.0e-9
    reference_impedance = 1.0e6
    conductance = 1 / reference_impedance
    expected_angular_frequency = sqrt(1 / (inductance * capacitance) - (conductance / (2 * capacitance))^2)
    expected_linewidth_hz = conductance / (2π * capacitance)
    poles = matched_open_poles(
        reshape([capacitance], 1, 1),
        reshape([1 / inductance], 1, 1),
        reshape([1.0], 1, 1),
        reference_impedance,
    )
    @test length(poles.frequencies_hz) == 1
    @test real(only(poles.frequencies_hz)) ≈ expected_angular_frequency / (2π) rtol=1.0e-13
    @test imag(only(poles.frequencies_hz)) ≈ -expected_linewidth_hz / 2 rtol=1.0e-13
    @test only(poles.linewidths_hz) ≈ expected_linewidth_hz rtol=1.0e-13
    @test length(poles.raw_eigenvalues) == 2
    @test all(length(hash) == 64 for hash in values(poles.hashes))
    @test poles.provenance.time_convention == "exp(-i*omega*t)"
end

@testset "linear response fails loudly on invalid inputs" begin
    capacitance = Matrix{Float64}(I, 2, 2)
    inverse_inductance = [2.0 0.0; 0.0 1.0]
    @test_throws FrameworkValidationError schur_dynamic_stiffness(
        capacitance,
        inverse_inductance,
        1.0,
        [1, 1],
    )
    @test_throws FrameworkValidationError schur_dynamic_stiffness(
        capacitance,
        inverse_inductance,
        1.0,
        [3],
    )
    nonfinite_capacitance = copy(capacitance)
    nonfinite_capacitance[1, 1] = NaN
    @test_throws FrameworkValidationError schur_dynamic_stiffness(
        nonfinite_capacitance,
        inverse_inductance,
        0.8,
        [1],
    )
    @test_throws FrameworkValidationError schur_dynamic_stiffness(
        capacitance,
        inverse_inductance,
        1.0,
        [1],
    )
    @test_throws FrameworkValidationError matched_port_response(
        capacitance,
        inverse_inductance,
        0.8,
        [1.0 1.0; 0.0 0.0],
        [50.0, 50.0],
    )
    @test_throws FrameworkValidationError scattering_to_impedance(
        zeros(ComplexF64, 1, 1),
        ComplexF64[50.0 + 1.0im],
    )
    @test_throws FrameworkValidationError bracketed_bisection(value -> value^2 + 1, (-1.0, 1.0))
    angular_root = 2π * 6.0e9
    @test_throws FrameworkValidationError match_parallel_lc(
        angular_frequency -> 2im * 10.0e-15 * (angular_frequency - angular_root),
        angular_root;
        derivative_step_rad_s=angular_root * 1.0e-6,
    )
end
