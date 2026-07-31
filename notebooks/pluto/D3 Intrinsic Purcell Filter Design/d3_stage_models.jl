# D3 Stage 2 and Stage 3 model construction. Both physical stages own the
# same fabrication coordinates. Stage 2 response-matches those coordinates to
# a finite Equivalent Circuit; Stage 3 retains the distributed realization.
# Cost semantics and optimizer orchestration remain outside this file.

using LinearAlgebra
using SHA
using SuperconductingCircuitsCore

isdefined(@__MODULE__, :D3IDCInput) ||
    include(joinpath(@__DIR__, "d3_idc_input.jl"))
using .D3IDCInput: D3IDCMapping, d3_idc_mapping_semantic_sha256

const D3_PHYSICAL_VARIABLE_ORDER = (
    :lr_open_m,
    :lr_short_m,
    :lc_m,
    :lp_open_m,
    :lp_short_m,
    :u_IDC,
)

const D3_STAGE2_VARIABLE_ORDER = D3_PHYSICAL_VARIABLE_ORDER
const D3_STAGE3_VARIABLE_ORDER = D3_PHYSICAL_VARIABLE_ORDER

const D3_RESPONSE_EQUIVALENT_VARIABLE_ORDER = (
    :Cr_f,
    :Lr_h,
    :Cp_f,
    :Lp_h,
    :Cn_f,
    :Ln_h,
    :u_IDC,
)

const D3_SELECTED_Q2D_ARTIFACT_ID =
    "d3-continuous-upper-ground-w3-s3-d3-h8-q2d-rlgc"
const D3_SELECTED_Q2D_ARTIFACT_SHA256 =
    "6c22cd3c2721214ac0d1afaaaf8b40b396435bb413638da5ae889b6973166825"
const D3_SELECTED_Q2D_TOPOLOGY = :continuous_upper_ground
const D3_SELECTED_IDC_MAPPING_ID =
    "d3-same-die-filter-feedline-idc-q3d-tensor-fit-v1"
const D3_SELECTED_IDC_MAPPING_SHA256 =
    "db549a78564ab1dd25aba4cd0004304651ea3da7a1e66ce92bbb31bceb79e66c"
const D3_SELECTED_IDC_SOURCE_SHA256 =
    "6a54fec0669c01dacf433f3cc639192e5e5202ae232aa5b1e786ac7147b172e3"
const D3_SELECTED_IDC_SEMANTIC_SHA256 =
    "dba6ffcfc442860151c4cad5b27bf6259a5ba1ca532637b2ce0c0c741d97d152"
const D3_SELECTED_Q2D_GEOMETRY_UM = (
    w=3.0,
    s=3.0,
    d=3.0,
    h=8.0,
    upper_ground_clearance=0.0,
)
const D3_SELECTED_SINGLE_LINE = (
    l_per_m_h=4.3575290933454624e-7,
    c_per_m_f=1.491527564537374e-10,
)
const D3_SELECTED_PAIR_L_PER_M_H = [
    4.3671399663877326e-7 1.6193473670985894e-8
    1.6193473670985894e-8 4.367005829380964e-7
]
const D3_SELECTED_PAIR_C_PER_M_F = [
    1.488725856649626e-10 -9.051719790144461e-12
    -9.051719790144461e-12 1.4886285191111777e-10
]

struct D3Stage2ResonatorMapping{L,S,C}
    fixed_line_input::L
    settings::S
    contract::C
    mapping_sha256::String
end

function (mapping::D3Stage2ResonatorMapping)(lengths)
    return _d3_stage2_evaluate_response_match(mapping, lengths)
end

function _d3_stage_positive(candidate, name, label)
    hasproperty(candidate, name) || error("$(label) is missing $(name).")
    raw = getproperty(candidate, name)
    raw isa Real || error("$(label) $(name) must be real.")
    value = Float64(raw)
    isfinite(value) && value > 0 || error(
        "$(label) $(name) must be finite and positive.",
    )
    return value
end

function _d3_stage_require_exact_fields(candidate, expected, label)
    actual = Tuple(propertynames(candidate))
    Set(actual) == Set(expected) || error(
        "$(label) fields must be exactly $(collect(expected)); received $(collect(actual)).",
    )
    return nothing
end

function _d3_stage_idc_triplet(idc_mapping, u_idc)
    applicable(idc_mapping, u_idc) || error(
        "D3 IDC mapping must be callable with the scalar u_IDC coordinate.",
    )
    raw = idc_mapping(u_idc)
    required = (
        :idc_filter_ground_capacitance_f,
        :idc_feedline_ground_capacitance_f,
        :idc_mutual_capacitance_f,
        :mapping_id,
        :mapping_sha256,
    )
    all(name -> hasproperty(raw, name), required) || error(
        "D3 IDC mapping must return all three capacitances plus mapping id and SHA-256.",
    )
    values = (
        idc_filter_ground_capacitance_f=_d3_stage_positive(
            raw,
            :idc_filter_ground_capacitance_f,
            "D3 IDC mapping result",
        ),
        idc_feedline_ground_capacitance_f=_d3_stage_positive(
            raw,
            :idc_feedline_ground_capacitance_f,
            "D3 IDC mapping result",
        ),
        idc_mutual_capacitance_f=_d3_stage_positive(
            raw,
            :idc_mutual_capacitance_f,
            "D3 IDC mapping result",
        ),
    )
    mapping_id = strip(String(raw.mapping_id))
    mapping_sha256 = lowercase(strip(String(raw.mapping_sha256)))
    isempty(mapping_id) && error("D3 IDC mapping id must not be empty.")
    occursin(r"^[0-9a-f]{64}$", mapping_sha256) || error(
        "D3 IDC mapping SHA-256 must contain 64 lowercase hexadecimal characters.",
    )
    return merge(
        values,
        (
            u_IDC=Float64(u_idc),
            mapping_id=mapping_id,
            mapping_sha256=mapping_sha256,
        ),
    )
end

function _d3_stage_require_physical_idc_mapping(idc_mapping::D3IDCMapping)
    idc_mapping.gap_um == 8.0 || error(
        "D3 physical stages require the Q3D IDC mapping evaluated at the accepted 8 um gap.",
    )
    idc_mapping.mapping_id == D3_SELECTED_IDC_MAPPING_ID || error(
        "D3 physical stages require the selected three-branch IDC mapping id.",
    )
    lowercase(strip(idc_mapping.mapping_sha256)) ==
        D3_SELECTED_IDC_MAPPING_SHA256 || error(
        "D3 physical IDC mapping SHA-256 does not match the selected artifact.",
    )
    get(idc_mapping.source_artifact, "sha256", nothing) ==
        D3_SELECTED_IDC_SOURCE_SHA256 || error(
        "D3 physical IDC mapping source SHA-256 does not match the selected Q3D workbook.",
    )
    idc_mapping.valid_gap_range_um == (5.0, 10.0) &&
        idc_mapping.valid_length_range_um == (35.0, 75.0) &&
        idc_mapping.length_center_um == 55.0 &&
        idc_mapping.length_half_range_um == 20.0 || error(
        "D3 physical IDC mapping domain or normalization is not the selected v1 contract.",
    )
    d3_idc_mapping_semantic_sha256(idc_mapping) ==
        D3_SELECTED_IDC_SEMANTIC_SHA256 || error(
        "D3 physical IDC effective mapping contents do not match the selected v1 artifact.",
    )
    return idc_mapping
end

function _d3_stage_require_physical_idc_mapping(idc_mapping)
    error(
        "D3 Stage-2/3 physical candidates require D3IDCInput.D3IDCMapping " *
        "loaded from the validated three-branch Q3D artifact; raw callables are diagnostic-only.",
    )
end

function _d3_stage_fixed_qubit_keywords(fixed)
    required = (
        :c0r_f,
        :c01_f,
        :c02_f,
        :c12_qubit_f,
        :cr1_f,
        :cr2_f,
        :l_j_per_junction_h,
    )
    return NamedTuple{
        required,
    }(Tuple(_d3_stage_positive(fixed, name, "D3 fixed qubit input") for name in required))
end

function _d3_stage_physical_lengths(candidate, label)
    return (
        lr_open_m=_d3_stage_positive(candidate, :lr_open_m, label),
        lr_short_m=_d3_stage_positive(candidate, :lr_short_m, label),
        lc_m=_d3_stage_positive(candidate, :lc_m, label),
        lp_open_m=_d3_stage_positive(candidate, :lp_open_m, label),
        lp_short_m=_d3_stage_positive(candidate, :lp_short_m, label),
    )
end

function _d3_stage2_response_matched_resonators(
    resonator_mapping::D3Stage2ResonatorMapping,
    lengths,
)
    applicable(resonator_mapping, lengths) || error(
        "D3 Stage-2 resonator mapping must be callable with the five physical lengths.",
    )
    raw = resonator_mapping(lengths)
    required = (
        :Cr_f,
        :Lr_h,
        :Cp_f,
        :Lp_h,
        :Cn_f,
        :Ln_h,
        :mapping_id,
        :mapping_sha256,
        :q2d_artifact_id,
        :q2d_artifact_sha256,
        :topology_id,
        :match_contract_id,
        :fixed_line_input_sha256,
        :match_evidence,
    )
    all(name -> hasproperty(raw, name), required) || error(
        "D3 Stage-2 resonator mapping must return six response-matched LC values, " *
        "Q2D/topology provenance, its match contract, and fixed-line identity.",
    )
    contract = resonator_mapping.contract
    for (name, expected) in (
        (:mapping_id, "d3-continuous-ground-response-match"),
        (:q2d_artifact_id, contract.q2d_artifact_id),
        (:q2d_artifact_sha256, contract.q2d_artifact_sha256),
        (:topology_id, contract.topology_id),
        (:match_contract_id, contract.match_contract_id),
        (:fixed_line_input_sha256, contract.fixed_line_input_sha256),
    )
        String(getproperty(raw, name)) == String(expected) || error(
            "D3 Stage-2 response match $(name) disagrees with its attested mapping contract.",
        )
    end
    values = NamedTuple{
        (:Cr_f, :Lr_h, :Cp_f, :Lp_h, :Cn_f, :Ln_h),
    }(Tuple(
        _d3_stage_positive(raw, name, "D3 Stage-2 response match")
        for name in (:Cr_f, :Lr_h, :Cp_f, :Lp_h, :Cn_f, :Ln_h)
    ))
    strings = NamedTuple{
        (:mapping_id, :q2d_artifact_id, :topology_id, :match_contract_id),
    }(Tuple(
        begin
            value = strip(String(getproperty(raw, name)))
            isempty(value) && error("D3 Stage-2 $(name) must not be empty.")
            value
        end
        for name in (
            :mapping_id,
            :q2d_artifact_id,
            :topology_id,
            :match_contract_id,
        )
    ))
    hashes = NamedTuple{
        (
            :mapping_sha256,
            :q2d_artifact_sha256,
            :fixed_line_input_sha256,
        ),
    }(Tuple(
        begin
            value = lowercase(strip(String(getproperty(raw, name))))
            occursin(r"^[0-9a-f]{64}$", value) || error(
                "D3 Stage-2 $(name) must contain 64 lowercase hexadecimal characters.",
            )
            value
        end
        for name in (
            :mapping_sha256,
            :q2d_artifact_sha256,
            :fixed_line_input_sha256,
        )
    ))
    return merge(
        values,
        strings,
        hashes,
        (
            physical_lengths=lengths,
            match_evidence=raw.match_evidence,
        ),
    )
end

function _d3_stage2_response_matched_resonators(resonator_mapping, lengths)
    error(
        "D3 Stage-2 requires D3Stage2ResonatorMapping from the selected Q2D " *
        "response-match constructor; raw callables cannot enter the physical evaluator.",
    )
end

function _d3_stage2_validate_resonator_mapping(
    resonator_mapping::D3Stage2ResonatorMapping,
    fixed,
)
    selected = _d3_selected_q2d_line_input(fixed)
    mapping_selected = _d3_selected_q2d_line_input(
        resonator_mapping.fixed_line_input,
    )
    selected.fixed_line_input_sha256 ==
        mapping_selected.fixed_line_input_sha256 || error(
        "D3 Stage-2 resonator mapping does not use the supplied selected fixed input.",
    )
    contract = resonator_mapping.contract
    expected = (
        match_contract_id="d3-cpw-mtl-response-match.v1",
        q2d_artifact_id=selected.q2d_artifact_id,
        q2d_artifact_sha256=selected.q2d_artifact_sha256,
        topology_id=String(selected.q2d_topology_id),
        fixed_line_input_sha256=selected.fixed_line_input_sha256,
        settings=resonator_mapping.settings,
    )
    contract == expected || error(
        "D3 Stage-2 resonator mapping contract is not bound to the selected fixed input and settings.",
    )
    expected_sha256 = bytes2hex(SHA.sha256(codeunits(
        SuperconductingCircuitsCore.JSON3.write(expected),
    )))
    resonator_mapping.mapping_sha256 == expected_sha256 || error(
        "D3 Stage-2 resonator mapping SHA-256 disagrees with its effective contract.",
    )
    return resonator_mapping
end

function _d3_stage2_resonator_response_model(lengths, lines; diagonal)
    l_matrix = diagonal ?
        Matrix(Diagonal(LinearAlgebra.diag(lines.l_matrix_per_m_h))) :
        lines.l_matrix_per_m_h
    c_matrix = diagonal ?
        Matrix(Diagonal(LinearAlgebra.diag(lines.c_matrix_per_m_f))) :
        lines.c_matrix_per_m_f
    plan = CircuitPlan(
        diagonal ?
            "d3-stage2-diagonal-response-reference" :
            "d3-stage2-physical-response-reference",
    )
    readout_grounded_head = external_node("d3_stage2_readout_grounded_head")
    readout_open_tail = external_node("d3_stage2_readout_open_tail")
    filter_grounded_head = external_node("d3_stage2_filter_grounded_head")
    filter_open_tail = external_node("d3_stage2_filter_open_tail")
    mtl_model = MTLCoupledRLGCSpec(
        start1_m=lengths.lr_short_m,
        start2_m=lengths.lp_short_m,
        length_m=lengths.lc_m,
        section_length_m=lines.section_length_m,
        l_matrix_per_m_h=l_matrix,
        c_matrix_per_m_f=c_matrix,
    )
    readout = add_quarter_wave_resonator!(
        plan;
        id=:d3_stage2_readout_resonator,
        grounded_head=readout_grounded_head,
        open_tail=readout_open_tail,
        spec=_d3_line_spec(
            length_m=
                lengths.lr_short_m + lengths.lc_m + lengths.lr_open_m,
            section_length_m=lines.section_length_m,
            l_per_m_h=lines.readout_l_per_m_h,
            c_per_m_f=lines.readout_c_per_m_f,
        ),
        breakpoints_m=(
            lengths.lr_short_m,
            lengths.lr_short_m + lengths.lc_m,
        ),
        section_overrides=[coupled_line_section_override(mtl_model, 1)],
    )
    filter = add_quarter_wave_resonator!(
        plan;
        id=:d3_stage2_filter_resonator,
        grounded_head=filter_grounded_head,
        open_tail=filter_open_tail,
        spec=_d3_line_spec(
            length_m=
                lengths.lp_short_m + lengths.lc_m + lengths.lp_open_m,
            section_length_m=lines.section_length_m,
            l_per_m_h=lines.filter_l_per_m_h,
            c_per_m_f=lines.filter_c_per_m_f,
        ),
        breakpoints_m=(
            lengths.lp_short_m,
            lengths.lp_short_m + lengths.lc_m,
        ),
        section_overrides=[coupled_line_section_override(mtl_model, 2)],
    )
    couple_transmission_window!(
        plan;
        id=:d3_stage2_mtl_window,
        line1=readout.line,
        line2=filter.line,
        start1=lengths.lr_short_m,
        start2=lengths.lp_short_m,
        length=lengths.lc_m,
        model=mtl_model,
        coupling_orientation=lines.coupling_orientation,
    )
    compiled = compile_to_josephson(plan)
    model = extract_linear_nodal_model(compiled)
    endpoints = (
        readout_open_tail,
        filter_open_tail,
    )
    terminal_indices = [
        begin
        node_name = compiled.node_map[endpoint]
        matches = findall(==(node_name), model.node_names)
        length(matches) == 1 || error(
            "D3 Stage-2 response-match terminal $(node_name) must resolve exactly once.",
        )
        only(matches)
        end
        for endpoint in endpoints
    ]
    return (
        plan=plan,
        compiled=compiled,
        model=model,
        terminal_indices=terminal_indices,
    )
end

function _d3_stage2_terminal_admittance(
    reference,
    terminal_position,
    angular_frequency,
)
    reduced = schur_dynamic_stiffness(
        reference.model.capacitance,
        reference.model.inverse_inductance,
        angular_frequency,
        reference.terminal_indices,
    )
    return reduced.dynamic_stiffness[terminal_position, terminal_position] /
        (-im * angular_frequency)
end

"""
    d3_stage2_response_matched_resonator_mapping(fixed; ...)

Create the physical-length-to-LC map shared by the Stage-2 optimizer. The map
keeps the declared Q2D diagonal loading when mutual terms are disabled,
matches `Cr/Lr` and `Cp/Lp` from terminal-admittance roots/slopes, and matches
`Cn/Ln` from the physical-pair `Z21` notch and slope.
"""
function d3_stage2_response_matched_resonator_mapping(
    fixed;
    readout_root_bracket_hz,
    filter_root_bracket_hz,
    notch_root_bracket_hz,
    parallel_derivative_step_rad_s,
    bridge_derivative_step_rad_s,
    bisection_absolute_tolerance_rad_s=2π * 10.0,
    bisection_relative_tolerance=1.0e-13,
    bisection_max_iterations=128,
    match_root_relative_tolerance=2.0e-3,
    derivative_relative_tolerance=1.0e-7,
)
    selected_lines = _d3_selected_q2d_line_input(fixed)
    settings = (
        readout_root_bracket_hz=Tuple(Float64.(collect(readout_root_bracket_hz))),
        filter_root_bracket_hz=Tuple(Float64.(collect(filter_root_bracket_hz))),
        notch_root_bracket_hz=Tuple(Float64.(collect(notch_root_bracket_hz))),
        parallel_derivative_step_rad_s=Float64(parallel_derivative_step_rad_s),
        bridge_derivative_step_rad_s=Float64(bridge_derivative_step_rad_s),
        bisection_absolute_tolerance_rad_s=
            Float64(bisection_absolute_tolerance_rad_s),
        bisection_relative_tolerance=Float64(bisection_relative_tolerance),
        bisection_max_iterations=Int(bisection_max_iterations),
        match_root_relative_tolerance=Float64(match_root_relative_tolerance),
        derivative_relative_tolerance=Float64(derivative_relative_tolerance),
    )
    all(bracket -> length(bracket) == 2 && 0 < bracket[1] < bracket[2], (
        settings.readout_root_bracket_hz,
        settings.filter_root_bracket_hz,
        settings.notch_root_bracket_hz,
    )) || error("D3 Stage-2 response-match root brackets must be positive and increasing.")
    mapping_contract = (
        match_contract_id="d3-cpw-mtl-response-match.v1",
        q2d_artifact_id=selected_lines.q2d_artifact_id,
        q2d_artifact_sha256=selected_lines.q2d_artifact_sha256,
        topology_id=String(selected_lines.q2d_topology_id),
        fixed_line_input_sha256=selected_lines.fixed_line_input_sha256,
        settings=settings,
    )
    mapping_sha256 = bytes2hex(SHA.sha256(codeunits(
        SuperconductingCircuitsCore.JSON3.write(mapping_contract),
    )))
    return D3Stage2ResonatorMapping(
        selected_lines,
        settings,
        mapping_contract,
        mapping_sha256,
    )
end

function _d3_stage2_evaluate_response_match(
    mapping::D3Stage2ResonatorMapping,
    lengths,
)
    selected_lines = _d3_selected_q2d_line_input(mapping.fixed_line_input)
    lines = _d3_stage3_fixed_line_keywords(selected_lines)
    settings = mapping.settings
    diagonal = _d3_stage2_resonator_response_model(
        lengths,
        lines;
        diagonal=true,
    )
    physical = _d3_stage2_resonator_response_model(
        lengths,
        lines;
        diagonal=false,
    )
    yr = angular_frequency -> _d3_stage2_terminal_admittance(
        diagonal,
        1,
        angular_frequency,
    )
    yp = angular_frequency -> _d3_stage2_terminal_admittance(
        diagonal,
        2,
        angular_frequency,
    )
    z21 = angular_frequency -> linear_terminal_response(
        physical.model.capacitance,
        physical.model.inverse_inductance,
        angular_frequency,
        physical.terminal_indices,
    ).impedance[2, 1]
    bisection = (
        absolute_tolerance=settings.bisection_absolute_tolerance_rad_s,
        relative_tolerance=settings.bisection_relative_tolerance,
        max_iterations=settings.bisection_max_iterations,
    )
    root(response, bracket_hz) = bracketed_bisection(
        angular_frequency -> imag(response(angular_frequency)),
        2π .* collect(bracket_hz);
        bisection...,
    )
    readout_root = root(yr, settings.readout_root_bracket_hz)
    filter_root = root(yp, settings.filter_root_bracket_hz)
    notch_root = root(z21, settings.notch_root_bracket_hz)
    readout = match_parallel_lc(
        yr,
        readout_root;
        derivative_step_rad_s=settings.parallel_derivative_step_rad_s,
        root_relative_tolerance=settings.match_root_relative_tolerance,
        imaginary_derivative_relative_tolerance=
            settings.derivative_relative_tolerance,
    )
    filter = match_parallel_lc(
        yp,
        filter_root;
        derivative_step_rad_s=settings.parallel_derivative_step_rad_s,
        root_relative_tolerance=settings.match_root_relative_tolerance,
        imaginary_derivative_relative_tolerance=
            settings.derivative_relative_tolerance,
    )
    bridge = match_bridge_lc(
        z21,
        yr,
        yp,
        notch_root;
        derivative_step_rad_s=settings.bridge_derivative_step_rad_s,
        root_relative_tolerance=settings.match_root_relative_tolerance,
        imaginary_capacitance_relative_tolerance=
            settings.derivative_relative_tolerance,
    )
    return (
        Cr_f=readout.capacitance_f,
        Lr_h=readout.inductance_h,
        Cp_f=filter.capacitance_f,
        Lp_h=filter.inductance_h,
        Cn_f=bridge.capacitance_f,
        Ln_h=bridge.inductance_h,
        mapping_id="d3-continuous-ground-response-match",
        mapping_sha256=mapping.mapping_sha256,
        q2d_artifact_id=selected_lines.q2d_artifact_id,
        q2d_artifact_sha256=selected_lines.q2d_artifact_sha256,
        topology_id=String(selected_lines.q2d_topology_id),
        fixed_line_input_sha256=selected_lines.fixed_line_input_sha256,
        match_contract_id=mapping.contract.match_contract_id,
        match_evidence=(
            readout=readout,
            filter=filter,
            bridge=bridge,
            settings=settings,
        ),
    )
end

function _d3_stage2_fixed_feedline_keywords(fixed)
    obsolete = (
        :separator_inductance_h,
        :separator_model,
        :separator_characteristic_impedance_ohm,
        :separator_phase_velocity_m_per_s,
        :feedline_length_m,
        :feedline_l_per_m_h,
        :feedline_c_per_m_f,
        :feedline_n_sections,
    )
    stale = filter(name -> hasproperty(fixed, name), obsolete)
    isempty(stale) || error(
        "D3 Stage-2 fixed input contains obsolete feedline fields $(collect(stale)); " *
        "the matched two-section port regularizer is fixed by its CircuitPlan.",
    )
    port_resistance_ohm = _d3_stage_positive(
        fixed,
        :port_resistance_ohm,
        "D3 fixed feedline input",
    )
    port_resistance_ohm == 50.0 || error(
        "D3 Stage-2 matched ports are fixed at exactly 50 ohm.",
    )
    return (port_resistance_ohm=port_resistance_ohm,)
end

function d3_stage2_matched_port_regularizer_contract(port_resistance_ohm=50.0)
    resistance = Float64(port_resistance_ohm)
    isfinite(resistance) && resistance == 50.0 || error(
        "D3 Stage-2 matched ports are fixed at exactly 50 ohm.",
    )
    return (
        feedline_model=:matched_port_regularizer_two_pi,
        regularizer_series_inductance_h=
            D3_PORT_REGULARIZER_SERIES_INDUCTANCE_H,
        regularizer_section_capacitance_f=
            D3_PORT_REGULARIZER_SECTION_CAPACITANCE_F,
        regularizer_characteristic_impedance_ohm=
            D3_PORT_REGULARIZER_CHARACTERISTIC_IMPEDANCE_OHM,
        regularizer_phase_velocity_m_per_s=
            D3_PORT_REGULARIZER_PHASE_VELOCITY_M_PER_S,
        regularizer_section_length_m=
            D3_PORT_REGULARIZER_SECTION_LENGTH_M,
        regularizer_section_count=2,
        port_resistance_ohm=resistance,
    )
end

function d3_stage2_validate_matched_port_regularizer_contract(raw)
    expected = d3_stage2_matched_port_regularizer_contract()
    names = propertynames(expected)
    Set(Symbol.(keys(raw))) == Set(names) || error(
        "D3 Stage-2 fixed-feedline fields must be exactly $(collect(names)).",
    )
    Symbol(raw["feedline_model"]) == expected.feedline_model || error(
        "D3 Stage-2 fixed feedline must use the matched two-pi port regularizer.",
    )
    for name in names
        name === :feedline_model && continue
        value = Float64(raw[String(name)])
        value == Float64(getproperty(expected, name)) || error(
            "D3 Stage-2 fixed-feedline $(name) disagrees with its CircuitPlan constant.",
        )
    end
    return expected
end

function _d3_stage3_fixed_feedline_keywords(fixed)
    required = (
        :feedline_length_m,
        :feedline_l_per_m_h,
        :feedline_c_per_m_f,
        :port_resistance_ohm,
    )
    values = NamedTuple{
        required,
    }(Tuple(_d3_stage_positive(fixed, name, "D3 Stage-3 fixed feedline input") for name in required))
    values.port_resistance_ohm == 50.0 || error(
        "D3 Stage-3 matched ports are fixed at exactly 50 ohm.",
    )
    hasproperty(fixed, :feedline_n_sections) || error(
        "D3 Stage-3 fixed input is missing feedline_n_sections.",
    )
    raw = fixed.feedline_n_sections
    raw isa Real && isfinite(raw) && raw == round(raw) && raw >= 2 || error(
        "D3 Stage-3 feedline_n_sections must be an integer-valued count of at least two.",
    )
    return merge(values, (feedline_n_sections=Int(round(raw)),))
end

"""
    d3_response_equivalent_model_from_lc(candidate, fixed, idc_mapping; id=...)

Build a finite response-equivalent diagnostic from six explicit LC values.
This is the topology-constrained fitter realization; it is not a fabrication
witness and must not be passed to the Stage-2 optimizer.
"""
function d3_response_equivalent_model_from_lc(
    candidate,
    fixed,
    idc_mapping;
    id="d3-response-equivalent-diagnostic",
)
    _d3_stage_require_exact_fields(
        candidate,
        D3_RESPONSE_EQUIVALENT_VARIABLE_ORDER,
        "D3 response-equivalent diagnostic",
    )
    u_idc = _d3_stage_positive(
        candidate,
        :u_IDC,
        "D3 response-equivalent diagnostic",
    )
    idc = _d3_stage_idc_triplet(idc_mapping, u_idc)
    qubit = _d3_stage_fixed_qubit_keywords(fixed)
    feedline = _d3_stage2_fixed_feedline_keywords(fixed)
    built = build_d3_intrinsic_purcell_equivalent_circuit_plan(;
        id=String(id),
        idc_filter_ground_capacitance_f=
            idc.idc_filter_ground_capacitance_f,
        idc_feedline_ground_capacitance_f=
            idc.idc_feedline_ground_capacitance_f,
        idc_mutual_capacitance_f=idc.idc_mutual_capacitance_f,
        readout_capacitance_f=
            _d3_stage_positive(candidate, :Cr_f, "D3 response-equivalent diagnostic"),
        readout_inductance_h=
            _d3_stage_positive(candidate, :Lr_h, "D3 response-equivalent diagnostic"),
        filter_capacitance_f=
            _d3_stage_positive(candidate, :Cp_f, "D3 response-equivalent diagnostic"),
        filter_inductance_h=
            _d3_stage_positive(candidate, :Lp_h, "D3 response-equivalent diagnostic"),
        bridge_capacitance_f=
            _d3_stage_positive(candidate, :Cn_f, "D3 response-equivalent diagnostic"),
        bridge_inductance_h=
            _d3_stage_positive(candidate, :Ln_h, "D3 response-equivalent diagnostic"),
        qubit...,
        feedline...,
    )
    auxiliary = (
        linewidth_la=build_d3_linewidth_la_equivalent_circuit_plan(;
            id="$(id)-linewidth-la",
            idc_filter_ground_capacitance_f=
                idc.idc_filter_ground_capacitance_f,
            idc_feedline_ground_capacitance_f=
                idc.idc_feedline_ground_capacitance_f,
            idc_mutual_capacitance_f=idc.idc_mutual_capacitance_f,
            filter_capacitance_f=
                _d3_stage_positive(candidate, :Cp_f, "D3 response-equivalent diagnostic"),
            filter_inductance_h=
                _d3_stage_positive(candidate, :Lp_h, "D3 response-equivalent diagnostic"),
            bridge_capacitance_f=
                _d3_stage_positive(candidate, :Cn_f, "D3 response-equivalent diagnostic"),
            bridge_inductance_h=
                _d3_stage_positive(candidate, :Ln_h, "D3 response-equivalent diagnostic"),
            feedline...,
        ),
        notch=build_d3_intrinsic_pair_notch_equivalent_circuit_plan(;
            id="$(id)-intrinsic-pair-notch",
            readout_capacitance_f=
                _d3_stage_positive(candidate, :Cr_f, "D3 response-equivalent diagnostic"),
            readout_inductance_h=
                _d3_stage_positive(candidate, :Lr_h, "D3 response-equivalent diagnostic"),
            filter_capacitance_f=
                _d3_stage_positive(candidate, :Cp_f, "D3 response-equivalent diagnostic"),
            filter_inductance_h=
                _d3_stage_positive(candidate, :Lp_h, "D3 response-equivalent diagnostic"),
            bridge_capacitance_f=
                _d3_stage_positive(candidate, :Cn_f, "D3 response-equivalent diagnostic"),
            bridge_inductance_h=
                _d3_stage_positive(candidate, :Ln_h, "D3 response-equivalent diagnostic"),
            port_resistance_ohm=feedline.port_resistance_ohm,
        ),
    )
    return (
        stage_id=:response_equivalent_diagnostic,
        model_family=:finite_order_response_equivalent,
        variable_order=D3_RESPONSE_EQUIVALENT_VARIABLE_ORDER,
        candidate=candidate,
        idc=idc,
        built=built,
        auxiliary=auxiliary,
    )
end

"""
    d3_stage2_equivalent_model(
        candidate, fixed, resonator_mapping, idc_mapping; id=...)

Build one physically constrained Stage-2 Equivalent candidate. The optimizer
owns the five CPW/MTL lengths and `u_IDC`; the six LC values are read-only
outputs of one provenance-bearing response-match map.
"""
function d3_stage2_equivalent_model(
    candidate,
    fixed,
    resonator_mapping::D3Stage2ResonatorMapping,
    idc_mapping::D3IDCMapping;
    id="d3-stage2-equivalent-candidate",
)
    _d3_stage_require_exact_fields(
        candidate,
        D3_STAGE2_VARIABLE_ORDER,
        "D3 Stage-2 physical candidate",
    )
    _d3_stage2_validate_resonator_mapping(resonator_mapping, fixed)
    _d3_stage_require_physical_idc_mapping(idc_mapping)
    lengths = _d3_stage_physical_lengths(
        candidate,
        "D3 Stage-2 physical candidate",
    )
    response_match = _d3_stage2_response_matched_resonators(
        resonator_mapping,
        lengths,
    )
    resolved_candidate = (
        Cr_f=response_match.Cr_f,
        Lr_h=response_match.Lr_h,
        Cp_f=response_match.Cp_f,
        Lp_h=response_match.Lp_h,
        Cn_f=response_match.Cn_f,
        Ln_h=response_match.Ln_h,
        u_IDC=_d3_stage_positive(
            candidate,
            :u_IDC,
            "D3 Stage-2 physical candidate",
        ),
    )
    diagnostic = d3_response_equivalent_model_from_lc(
        resolved_candidate,
        fixed,
        idc_mapping;
        id=id,
    )
    return merge(
        diagnostic,
        (
            stage_id=:stage2_equivalent,
            model_family=:equivalent_exact_n,
            variable_order=D3_STAGE2_VARIABLE_ORDER,
            candidate=candidate,
            lengths=lengths,
            response_match=response_match,
            resolved_equivalent_candidate=resolved_candidate,
        ),
    )
end

function d3_stage2_equivalent_model(
    candidate,
    fixed,
    resonator_mapping,
    idc_mapping;
    kwargs...,
)
    error(
        "D3 Stage-2 formal evaluation requires the attested selected-Q2D " *
        "resonator mapping and a validated D3IDCMapping; raw callables are diagnostic-only.",
    )
end

function d3_stage2_equivalent_model(candidate, fixed, idc_mapping; kwargs...)
    error(
        "D3 Stage-2 no longer accepts six independently fitted LC values. " *
        "Pass physical lengths, a provenance-bearing CPW/MTL resonator mapping, " *
        "and the IDC mapping. Use d3_response_equivalent_model_from_lc only for " *
        "explicit response-fit diagnostics.",
    )
end

"""
    d3_stage2_hb_trace(stage, frequency_hz; pump_frequency_hz)

Replay one Stage-2 Equivalent candidate through JosephsonCircuits.jl pump-off
HB and return its two-port scattering trace in the project
`exp(-i*omega*t)` convention.
"""
function d3_stage2_hb_trace(stage, frequency_hz; pump_frequency_hz)
    stage.stage_id in (
        :stage2_equivalent,
        :response_equivalent_diagnostic,
    ) || error(
        "D3 Equivalent HB replay requires a physical Stage-2 candidate or an " *
        "explicit response-equivalent diagnostic.",
    )
    frequencies = Float64.(collect(frequency_hz))
    !isempty(frequencies) &&
        all(value -> isfinite(value) && value > 0, frequencies) &&
        all(diff(frequencies) .> 0) ||
        error("D3 Stage-2 HB frequencies must be strictly increasing and positive.")
    pump = Float64(pump_frequency_hz)
    isfinite(pump) && pump > 0 ||
        error("D3 Stage-2 pump-off HB frequency must be finite and positive.")

    compiled = compile_to_josephson(stage.built.plan)
    get(compiled.port_map, :input_port, nothing) == (index=1,) &&
        get(compiled.port_map, :output_port, nothing) == (index=2,) ||
        error("D3 Stage-2 HB replay requires ordered input/output ports 1 and 2.")
    result = run_hbsolve(
        compiled.netlist,
        compiled.component_values,
        frequencies;
        pump_frequencies_hz=(pump,),
        sources=[(mode=(1,), port=1, current=0.0)],
        n_modulation_harmonics=(1,),
        n_pump_harmonics=(1,),
        port_indices=[1, 2],
        returnS=true,
        returnZ=false,
        returnQE=false,
        returnCM=false,
        fourwavemixing=true,
    )
    raw = result.traces[:zero_mode_s]
    required = ("S11", "S12", "S21", "S22")
    all(haskey(raw, name) for name in required) ||
        error("D3 Stage-2 HB replay did not return the complete two-port S matrix.")
    scattering = [
        ComplexF64[
            conj(raw["S11"][index]) conj(raw["S12"][index])
            conj(raw["S21"][index]) conj(raw["S22"][index])
        ]
        for index in eachindex(frequencies)
    ]
    return (
        frequency_hz=frequencies,
        scattering=scattering,
        s21=ComplexF64[matrix[2, 1] for matrix in scattering],
        raw_solver_s21=ComplexF64.(raw["S21"]),
        phasor_conversion=:conjugated_from_solver_to_exp_minus_iwt,
        pump_state=:off,
        pump_frequency_hz=pump,
        source_current_a=0.0,
        compiled=compiled,
    )
end

function _d3_stage3_fixed_line_keywords(fixed)
    required = (
        :section_length_m,
        :readout_l_per_m_h,
        :readout_c_per_m_f,
        :filter_l_per_m_h,
        :filter_c_per_m_f,
        :l_matrix_per_m_h,
        :c_matrix_per_m_f,
        :coupling_orientation,
    )
    all(name -> hasproperty(fixed, name), required) || error(
        "D3 Stage-3 fixed input is missing one or more CPW/MTL fields.",
    )
    section_length_m = _d3_stage_positive(
        fixed,
        :section_length_m,
        "D3 Stage-3 fixed input",
    )
    for name in (
        :readout_l_per_m_h,
        :readout_c_per_m_f,
        :filter_l_per_m_h,
        :filter_c_per_m_f,
    )
        _d3_stage_positive(fixed, name, "D3 Stage-3 fixed input")
    end
    for (name, matrix) in (
        (:l_matrix_per_m_h, fixed.l_matrix_per_m_h),
        (:c_matrix_per_m_f, fixed.c_matrix_per_m_f),
    )
        matrix isa AbstractMatrix && size(matrix) == (2, 2) ||
            error("D3 Stage-3 $(name) must be a 2x2 matrix.")
        all(value -> value isa Real && isfinite(value), matrix) ||
            error("D3 Stage-3 $(name) must contain finite real values.")
        isposdef(Symmetric(Matrix{Float64}(matrix))) ||
            error("D3 Stage-3 $(name) must be positive definite.")
    end
    fixed.coupling_orientation in (:same_direction, :opposite_direction) ||
        error("D3 Stage-3 coupling orientation is unsupported.")
    return (
        section_length_m=section_length_m,
        readout_l_per_m_h=Float64(fixed.readout_l_per_m_h),
        readout_c_per_m_f=Float64(fixed.readout_c_per_m_f),
        filter_l_per_m_h=Float64(fixed.filter_l_per_m_h),
        filter_c_per_m_f=Float64(fixed.filter_c_per_m_f),
        l_matrix_per_m_h=Matrix{Float64}(fixed.l_matrix_per_m_h),
        c_matrix_per_m_f=Matrix{Float64}(fixed.c_matrix_per_m_f),
        coupling_orientation=Symbol(fixed.coupling_orientation),
    )
end

function _d3_selected_q2d_line_input(fixed)
    lines = _d3_stage3_fixed_line_keywords(fixed)
    required = (
        :q2d_artifact_id,
        :q2d_artifact_sha256,
        :q2d_topology_id,
        :q2d_geometry_um,
    )
    all(name -> hasproperty(fixed, name), required) || error(
        "D3 fixed line input must come from the selected provenance-bearing Q2D loader.",
    )
    artifact_id = strip(String(fixed.q2d_artifact_id))
    artifact_sha256 = lowercase(strip(String(fixed.q2d_artifact_sha256)))
    topology_id = Symbol(fixed.q2d_topology_id)
    artifact_id == D3_SELECTED_Q2D_ARTIFACT_ID || error(
        "D3 fixed line input does not use the selected continuous-ground Q2D artifact.",
    )
    artifact_sha256 == D3_SELECTED_Q2D_ARTIFACT_SHA256 || error(
        "D3 fixed line input wrapper SHA-256 does not match the selected Q2D artifact.",
    )
    topology_id == D3_SELECTED_Q2D_TOPOLOGY || error(
        "D3 fixed line input must use continuous upper ground.",
    )

    geometry = fixed.q2d_geometry_um
    _d3_stage_require_exact_fields(
        geometry,
        propertynames(D3_SELECTED_Q2D_GEOMETRY_UM),
        "D3 Q2D geometry",
    )
    all(
        name -> Float64(getproperty(geometry, name)) ==
            getproperty(D3_SELECTED_Q2D_GEOMETRY_UM, name),
        propertynames(D3_SELECTED_Q2D_GEOMETRY_UM),
    ) || error(
        "D3 Q2D geometry must equal the selected w=s=d=3 um, h=8 um continuous-ground point.",
    )
    lines.coupling_orientation == :same_direction || error(
        "D3 selected Q2D input requires same-direction MTL coupling.",
    )
    for (actual, expected, label) in (
        (
            lines.readout_l_per_m_h,
            D3_SELECTED_SINGLE_LINE.l_per_m_h,
            "readout L'",
        ),
        (
            lines.readout_c_per_m_f,
            D3_SELECTED_SINGLE_LINE.c_per_m_f,
            "readout C'",
        ),
        (
            lines.filter_l_per_m_h,
            D3_SELECTED_SINGLE_LINE.l_per_m_h,
            "filter L'",
        ),
        (
            lines.filter_c_per_m_f,
            D3_SELECTED_SINGLE_LINE.c_per_m_f,
            "filter C'",
        ),
    )
        actual == expected || error(
            "D3 selected Q2D $(label) does not match the accepted artifact.",
        )
    end
    lines.l_matrix_per_m_h == D3_SELECTED_PAIR_L_PER_M_H || error(
        "D3 selected Q2D MTL L' matrix does not match the accepted artifact.",
    )
    lines.c_matrix_per_m_f == D3_SELECTED_PAIR_C_PER_M_F || error(
        "D3 selected Q2D MTL C' matrix does not match the accepted artifact.",
    )

    identity = (
        contract_id="d3-selected-continuous-ground-fixed-line.v1",
        q2d_artifact_id=artifact_id,
        q2d_artifact_sha256=artifact_sha256,
        q2d_topology_id=String(topology_id),
        q2d_geometry_um=D3_SELECTED_Q2D_GEOMETRY_UM,
        section_length_m=lines.section_length_m,
        readout_l_per_m_h=lines.readout_l_per_m_h,
        readout_c_per_m_f=lines.readout_c_per_m_f,
        filter_l_per_m_h=lines.filter_l_per_m_h,
        filter_c_per_m_f=lines.filter_c_per_m_f,
        l_matrix_per_m_h=(
            Tuple(lines.l_matrix_per_m_h[1, :]),
            Tuple(lines.l_matrix_per_m_h[2, :]),
        ),
        c_matrix_per_m_f=(
            Tuple(lines.c_matrix_per_m_f[1, :]),
            Tuple(lines.c_matrix_per_m_f[2, :]),
        ),
        coupling_orientation=String(lines.coupling_orientation),
    )
    fixed_line_input_sha256 = bytes2hex(SHA.sha256(codeunits(
        SuperconductingCircuitsCore.JSON3.write(identity),
    )))
    return merge(
        lines,
        (
            q2d_artifact_id=artifact_id,
            q2d_artifact_sha256=artifact_sha256,
            q2d_topology_id=topology_id,
            q2d_geometry_um=D3_SELECTED_Q2D_GEOMETRY_UM,
            fixed_line_input_sha256=fixed_line_input_sha256,
            fixed_line_input_identity=identity,
        ),
    )
end

"""
    d3_stage3_hybridized_model(candidate, fixed, idc_mapping; id=...)

Build one independent Stage-3 Hybridized candidate. The six physical
coordinates are consumed together; no Stage-2 metric is reused.
"""
function d3_stage3_hybridized_model(
    candidate,
    fixed,
    idc_mapping::D3IDCMapping;
    id="d3-stage3-hybridized-candidate",
)
    _d3_stage_require_exact_fields(
        candidate,
        D3_STAGE3_VARIABLE_ORDER,
        "D3 Stage-3 candidate",
    )
    _d3_stage_require_physical_idc_mapping(idc_mapping)
    lengths = (
        lr_open_m=_d3_stage_positive(
            candidate,
            :lr_open_m,
            "D3 Stage-3 candidate",
        ),
        lr_short_m=_d3_stage_positive(
            candidate,
            :lr_short_m,
            "D3 Stage-3 candidate",
        ),
        lc_m=_d3_stage_positive(candidate, :lc_m, "D3 Stage-3 candidate"),
        lp_open_m=_d3_stage_positive(
            candidate,
            :lp_open_m,
            "D3 Stage-3 candidate",
        ),
        lp_short_m=_d3_stage_positive(
            candidate,
            :lp_short_m,
            "D3 Stage-3 candidate",
        ),
    )
    u_idc = _d3_stage_positive(candidate, :u_IDC, "D3 Stage-3 candidate")
    idc = _d3_stage_idc_triplet(idc_mapping, u_idc)
    qubit = _d3_stage_fixed_qubit_keywords(fixed)
    feedline = _d3_stage3_fixed_feedline_keywords(fixed)
    selected_lines = _d3_selected_q2d_line_input(fixed)
    lines = _d3_stage3_fixed_line_keywords(selected_lines)
    built = build_d3_intrinsic_purcell_hybridized_circuit_plan(;
        id=String(id),
        idc_filter_ground_capacitance_f=
            idc.idc_filter_ground_capacitance_f,
        idc_feedline_ground_capacitance_f=
            idc.idc_feedline_ground_capacitance_f,
        idc_mutual_capacitance_f=idc.idc_mutual_capacitance_f,
        readout_length_m=
            lengths.lr_short_m + lengths.lc_m + lengths.lr_open_m,
        filter_length_m=
            lengths.lp_short_m + lengths.lc_m + lengths.lp_open_m,
        window_start_readout_m=lengths.lr_short_m,
        window_start_filter_m=lengths.lp_short_m,
        window_length_m=lengths.lc_m,
        lines...,
        qubit...,
        feedline...,
    )
    auxiliary = (
        linewidth_la=build_d3_linewidth_la_hybridized_circuit_plan(;
            id="$(id)-linewidth-la",
            idc_filter_ground_capacitance_f=
                idc.idc_filter_ground_capacitance_f,
            idc_feedline_ground_capacitance_f=
                idc.idc_feedline_ground_capacitance_f,
            idc_mutual_capacitance_f=idc.idc_mutual_capacitance_f,
            filter_length_m=
                lengths.lp_short_m + lengths.lc_m + lengths.lp_open_m,
            section_length_m=lines.section_length_m,
            filter_l_per_m_h=lines.filter_l_per_m_h,
            filter_c_per_m_f=lines.filter_c_per_m_f,
            window_start_filter_m=lengths.lp_short_m,
            window_length_m=lengths.lc_m,
            l_matrix_per_m_h=lines.l_matrix_per_m_h,
            c_matrix_per_m_f=lines.c_matrix_per_m_f,
            feedline...,
        ),
        notch=build_d3_intrinsic_pair_notch_hybridized_circuit_plan(;
            id="$(id)-intrinsic-pair-notch",
            readout_length_m=
                lengths.lr_short_m + lengths.lc_m + lengths.lr_open_m,
            filter_length_m=
                lengths.lp_short_m + lengths.lc_m + lengths.lp_open_m,
            section_length_m=lines.section_length_m,
            readout_l_per_m_h=lines.readout_l_per_m_h,
            readout_c_per_m_f=lines.readout_c_per_m_f,
            filter_l_per_m_h=lines.filter_l_per_m_h,
            filter_c_per_m_f=lines.filter_c_per_m_f,
            window_start_readout_m=lengths.lr_short_m,
            window_start_filter_m=lengths.lp_short_m,
            window_length_m=lengths.lc_m,
            l_matrix_per_m_h=lines.l_matrix_per_m_h,
            c_matrix_per_m_f=lines.c_matrix_per_m_f,
            coupling_orientation=lines.coupling_orientation,
            port_resistance_ohm=feedline.port_resistance_ohm,
        ),
    )
    return (
        stage_id=:stage3_hybridized,
        model_family=:hybridized_distributed_lumped,
        variable_order=D3_STAGE3_VARIABLE_ORDER,
        candidate=candidate,
        lengths=lengths,
        idc=idc,
        feedline_contract=(
            model=:split_distributed_cpw,
            length_m=feedline.feedline_length_m,
            n_sections=feedline.feedline_n_sections,
            l_per_m_h=feedline.feedline_l_per_m_h,
            c_per_m_f=feedline.feedline_c_per_m_f,
            port_resistance_ohm=feedline.port_resistance_ohm,
        ),
        resonator_input_contract=(
            q2d_artifact_id=selected_lines.q2d_artifact_id,
            q2d_artifact_sha256=selected_lines.q2d_artifact_sha256,
            q2d_topology_id=selected_lines.q2d_topology_id,
            q2d_geometry_um=selected_lines.q2d_geometry_um,
            fixed_line_input_sha256=selected_lines.fixed_line_input_sha256,
            fixed_line_input_identity=selected_lines.fixed_line_input_identity,
        ),
        built=built,
        auxiliary=auxiliary,
    )
end

function d3_stage3_hybridized_model(candidate, fixed, idc_mapping; kwargs...)
    error(
        "D3 Stage-3 formal evaluation requires a validated D3IDCMapping; " *
        "raw callables are diagnostic-only.",
    )
end

function _d3_stage_response_closure(model, cqed_handoff, frequency_hz)
    analytical = d3_cqed_port_trace(cqed_handoff, frequency_hz)
    direct = d3_compiled_port_trace(model, analytical.frequency_hz)
    exact_scattering_residual = [
        analytical.exact.scattering[index] - direct.scattering[index]
        for index in eachindex(direct.scattering)
    ]
    return (
        frequency_hz=analytical.frequency_hz,
        direct=direct,
        analytical=analytical,
        residuals=(
            exact_scattering=exact_scattering_residual,
            exact_s21=analytical.exact.s21 - direct.s21,
            rwa_s21=analytical.rwa.s21 - direct.s21,
            max_abs_exact_scattering=maximum(
                maximum(abs, residual)
                for residual in exact_scattering_residual
            ),
            max_abs_exact_s21=maximum(
                abs,
                analytical.exact.s21 - direct.s21,
            ),
            max_abs_rwa_s21=maximum(
                abs,
                analytical.rwa.s21 - direct.s21,
            ),
        ),
        exact_closure_status=:candidate_gate__tolerance_not_human_frozen,
        rwa_closure_status=:report_only,
    )
end

function _d3_stage2_bare_coordinate_reference_states(model, cqed_handoff)
    _d3_exact_n_require_handoff_source(
        model,
        cqed_handoff,
        "D3 Stage-2 coupling-on bare-coordinate q/r/p references",
    )
    coordinate_index = Dict(
        coordinate => index
        for (index, coordinate) in enumerate(model.coordinate_order)
    )
    identities = (:q, :r, :p)
    all(haskey(coordinate_index, identity) for identity in identities) || error(
        "D3 Stage-2 bare-coordinate references require q, r, and p coordinates.",
    )
    state_order = copy(cqed_handoff.port_response.exact.state_order.doubled)
    state_count = length(state_order)
    vectors = NamedTuple{identities}(Tuple(
        begin
            vector = zeros(ComplexF64, state_count)
            vector[coordinate_index[identity]] = 1
            vector
        end
        for identity in identities
    ))
    source_identity = _d3_exact_n_source_model_identity(model)
    return (
        vectors=vectors,
        state_order=state_order,
        construction="coupling_on_canonical_bare_coordinate_unit_vectors",
        source_model_identity=source_identity,
        embedded_target_model_identity=source_identity,
        coupling_state=:qrp_on,
        reference_semantics=:canonical_bare_coordinate,
        frequency_rank_assignment=:forbidden,
    )
end

"""
    d3_stage2_candidate_metrics(
        candidate, fixed, resonator_mapping, idc_mapping; ...)

Compile one complete Equivalent candidate and extract exactly the six raw
revision-7 objective operands. Expensive response-closure and L_A calibration
diagnostics are intentionally outside this optimizer-facing adapter.
"""
function d3_stage2_candidate_metrics(
    candidate,
    fixed,
    resonator_mapping,
    idc_mapping;
    readout_effective_root_band_hz,
    filter_effective_root_band_hz,
    effective_operator_gate_policy,
    notch_frequency_bracket_hz,
    minimum_identity_overlap,
    minimum_identity_assignment_margin,
    id="d3-stage2-equivalent-candidate",
)
    stage = d3_stage2_equivalent_model(
        candidate,
        fixed,
        resonator_mapping,
        idc_mapping;
        id=id,
    )
    model = d3_exact_n_compiled_model(stage.built)
    cqed_handoff = d3_numerical_cqed_handoff(model)
    matrix_metrics = d3_stage2_matrix_metrics(
        model;
        cqed_handoff=cqed_handoff,
    )
    effective_rp = d3_q_feedline_downfolded_rp_metrics(
        model;
        readout_root_band_hz=readout_effective_root_band_hz,
        filter_root_band_hz=filter_effective_root_band_hz,
        gate_policy=effective_operator_gate_policy,
    )
    notch = d3_intrinsic_pair_notch_frequency(
        stage.auxiliary.notch,
        notch_frequency_bracket_hz,
    )
    energy_metric = d3_exact_open_energy_metric(
        model;
        cqed_handoff=cqed_handoff,
    )
    reference_states = _d3_stage2_bare_coordinate_reference_states(
        model,
        cqed_handoff,
    )
    identity_continuation = d3_exact_open_pole_identity_continuation(
        model,
        reference_states,
        energy_metric;
        minimum_overlap=minimum_identity_overlap,
        minimum_assignment_margin=minimum_identity_assignment_margin,
        cqed_handoff=cqed_handoff,
    )
    linewidth_lc = identity_continuation.linewidth_lc
    metrics = merge(
        matrix_metrics,
        (
            fr_eff_q_feedline_downfolded_qrp_on_ext_on_hz=
                effective_rp.readout.frequency_hz,
            fp_eff_q_feedline_downfolded_qrp_on_ext_on_hz=
                effective_rp.filter.frequency_hz,
            J_rp_eff_q_feedline_downfolded_coherent_hz=
                effective_rp.coherent_exchange_hz,
            J_rp_eff_q_feedline_downfolded_total_report_only_hz=
                effective_rp.total_exchange_hz,
            J_rp_eff_q_feedline_downfolded_dissipative_report_only_hz=
                effective_rp.dissipative_cross_coupling_hz,
            J_rp_eff_q_feedline_downfolded_relative_spread_report_only=
                effective_rp.relative_coupling_spread,
            kappa_r_eff_q_feedline_downfolded_qrp_on_ext_on_report_only_hz=
                effective_rp.readout.external_linewidth_hz,
            kappa_p_eff_q_feedline_downfolded_qrp_on_ext_on_report_only_hz=
                effective_rp.filter.external_linewidth_hz,
            notch_rp_on_hz=notch.frequency_hz,
            kappa_sum_qrp_on_ext_on_hz=linewidth_lc.linewidth_hz,
            eta_r_qrp_on=linewidth_lc.eta_r,
            eta_p_qrp_on=linewidth_lc.eta_p,
            effective_diagonal_frequency_extraction=
                :q_feedline_downfolded_rp_complex_operator,
            effective_exchange_extraction=
                :q_feedline_downfolded_rp_complex_midpoint_residue,
            notch_authority=:rp_on,
            linewidth_pole_scope=:qrp_three,
            primary_linewidth_extraction=:L_C,
        ),
    )
    return (
        contract_id="d3-stage2-candidate-metrics.v3",
        stage_id=stage.stage_id,
        model_family=stage.model_family,
        stage=stage,
        model=model,
        cqed_handoff=cqed_handoff,
        matrix_metrics=matrix_metrics,
        extractions=(
            effective_rp=effective_rp,
            notch=notch,
            linewidth_lc=linewidth_lc,
            identity_continuation=identity_continuation,
            bare_coordinate_reference_states=reference_states,
        ),
        metrics=metrics,
        objective_ready=true,
        missing_objective_quantities=(),
    )
end

function d3_stage2_candidate_metrics(candidate, fixed, idc_mapping; kwargs...)
    error(
        "D3 Stage-2 metrics require a provenance-bearing CPW/MTL resonator mapping; " *
        "free LC candidates are response diagnostics, not optimizer candidates.",
    )
end

"""
    d3_stage2_candidate_foundation(
        candidate, fixed, resonator_mapping, idc_mapping; ...)

Execute the complete Stage-2 path that is already physically defined:
candidate construction, compiled seven-node model, neutral `7 -> 6`
reduction, numerical cQED handoff, Exact-12/RWA-6/direct response closure,
matrix-space operands, intrinsic-pair notch, linewidth L_A calibration, and
exact-open q/r/p identity continuation from the coupling-on canonical
bare-coordinate reference basis.

The two overlap gates are required Run inputs. This function owns no hidden
identity-acceptance threshold.
"""
function d3_stage2_candidate_foundation(
    candidate,
    fixed,
    resonator_mapping,
    idc_mapping;
    response_frequency_hz,
    notch_frequency_bracket_hz,
    linewidth_frequency_band_hz,
    readout_effective_root_band_hz,
    filter_effective_root_band_hz,
    effective_operator_gate_policy,
    minimum_identity_overlap,
    minimum_identity_assignment_margin,
    id="d3-stage2-equivalent-candidate",
)
    evaluated = d3_stage2_candidate_metrics(
        candidate,
        fixed,
        resonator_mapping,
        idc_mapping;
        readout_effective_root_band_hz=
            readout_effective_root_band_hz,
        filter_effective_root_band_hz=
            filter_effective_root_band_hz,
        effective_operator_gate_policy=
            effective_operator_gate_policy,
        notch_frequency_bracket_hz=notch_frequency_bracket_hz,
        minimum_identity_overlap=minimum_identity_overlap,
        minimum_identity_assignment_margin=
            minimum_identity_assignment_margin,
        id=id,
    )
    stage = evaluated.stage
    model = evaluated.model
    cqed_handoff = evaluated.cqed_handoff
    response_closure = d3_exact_n_response_closure(
        model,
        response_frequency_hz;
        cqed_handoff=cqed_handoff,
    )
    linewidth_la = d3_linewidth_la_extraction(
        stage.auxiliary.linewidth_la,
        linewidth_frequency_band_hz,
    )
    return (
        contract_id="d3-stage2-candidate-foundation.v3",
        stage_id=stage.stage_id,
        model_family=stage.model_family,
        stage=stage,
        model=model,
        cqed_handoff=cqed_handoff,
        matrix_metrics=evaluated.matrix_metrics,
        response_closure=response_closure,
        extractions=(
            effective_rp=evaluated.extractions.effective_rp,
            notch=evaluated.extractions.notch,
            linewidth_la=linewidth_la,
            linewidth_lc=evaluated.extractions.linewidth_lc,
            identity_continuation=
                evaluated.extractions.identity_continuation,
            bare_coordinate_reference_states=
                evaluated.extractions.bare_coordinate_reference_states,
        ),
        metrics=evaluated.metrics,
        objective_ready=true,
        missing_objective_quantities=(),
        missing_report_only_extractions=(),
    )
end

function d3_stage2_candidate_foundation(candidate, fixed, idc_mapping; kwargs...)
    error(
        "D3 Stage-2 foundation requires a provenance-bearing CPW/MTL resonator " *
        "mapping; legacy free-LC receipts are ineligible.",
    )
end

"""
    d3_stage3_candidate_foundation(candidate, fixed, idc_mapping; ...)

Execute the physically closed Stage-3 construction, compilation, direct
distributed/lumped response, Exact/RWA analytical response closure,
intrinsic-pair notch, and the independent linewidth L_A calibration. The
Full-QRP loaded-bare and pole-identity operators remain fail-closed.
"""
function d3_stage3_candidate_foundation(
    candidate,
    fixed,
    idc_mapping;
    response_frequency_hz,
    notch_frequency_bracket_hz,
    linewidth_frequency_band_hz,
    id="d3-stage3-hybridized-candidate",
)
    stage = d3_stage3_hybridized_model(
        candidate,
        fixed,
        idc_mapping;
        id=id,
    )
    model = d3_hybridized_compiled_model(stage.built)
    cqed_handoff = d3_numerical_cqed_handoff(model)
    response_closure = _d3_stage_response_closure(
        model,
        cqed_handoff,
        response_frequency_hz,
    )
    notch = d3_intrinsic_pair_notch_frequency(
        stage.auxiliary.notch,
        notch_frequency_bracket_hz,
    )
    linewidth_la = d3_linewidth_la_extraction(
        stage.auxiliary.linewidth_la,
        linewidth_frequency_band_hz,
    )
    energy_metric = d3_exact_open_energy_metric(
        model;
        cqed_handoff=cqed_handoff,
    )
    return (
        contract_id="d3-stage3-candidate-foundation.v1",
        stage_id=stage.stage_id,
        model_family=stage.model_family,
        stage=stage,
        model=model,
        cqed_handoff=cqed_handoff,
        response_closure=response_closure,
        energy_metric=energy_metric,
        extractions=(
            notch=notch,
            linewidth_la=linewidth_la,
        ),
        objective_ready=false,
        missing_objective_quantities=(
            :fr_eff_q_feedline_downfolded_qrp_on_ext_on_hz,
            :fp_eff_q_feedline_downfolded_qrp_on_ext_on_hz,
            :J_rp_eff_q_feedline_downfolded_coherent_hz,
            :kappa_sum_qrp_on_ext_on_hz,
            :eta_r_qrp_on,
            :eta_p_qrp_on,
        ),
        missing_report_only_extractions=(),
        blockers=(
            (
                code=:missing_q_feedline_downfolded_rp_effective_operator,
                required_quantities=(
                    :fr_eff_q_feedline_downfolded_qrp_on_ext_on_hz,
                    :fp_eff_q_feedline_downfolded_qrp_on_ext_on_hz,
                    :J_rp_eff_q_feedline_downfolded_coherent_hz,
                ),
                objective_role=:required,
            ),
            (
                code=:missing_full_qrp_exact_open_pole_identity_receipt,
                required_quantities=(
                    :kappa_sum_qrp_on_ext_on_hz,
                    :eta_r_qrp_on,
                    :eta_p_qrp_on,
                ),
                objective_role=:required,
            ),
        ),
    )
end
