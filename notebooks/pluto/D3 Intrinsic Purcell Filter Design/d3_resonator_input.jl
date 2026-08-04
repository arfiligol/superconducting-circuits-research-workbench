# D3 fixed CPW/MTL input. This loader validates one caller-selected,
# continuous-upper-ground Q2D artifact and binds its exact geometry and
# matrices to the physical Stage-2/3 candidate.

module D3ResonatorInput

using LinearAlgebra
using SHA
using SuperconductingCircuitsCore

const JSON3 = SuperconductingCircuitsCore.JSON3
const D3_Q2D_RLGC_SCHEMA = "d3-fixed-q2d-rlgc-input.v1"
const D3_MAX_LINE_SECTION_LENGTH_M = 50e-6

export load_d3_continuous_ground_q2d_input

function _d3_q2d_positive(value, label)
    number = Float64(value)
    isfinite(number) && number > 0 || error("$(label) must be finite and positive.")
    return number
end

function _d3_q2d_nonnegative(value, label)
    number = Float64(value)
    isfinite(number) && number >= 0 || error("$(label) must be finite and nonnegative.")
    return number
end

function _d3_q2d_hash(value, label)
    hash = lowercase(strip(String(value)))
    occursin(r"^[0-9a-f]{64}$", hash) ||
        error("$(label) must contain 64 lowercase hexadecimal characters.")
    return hash
end

function _d3_q2d_text(value, label)
    text = strip(String(value))
    isempty(text) && error("$(label) must not be empty.")
    return text
end

function _d3_q2d_matrix(raw, label)
    rows = collect(raw)
    length(rows) == 2 && all(row -> length(row) == 2, rows) ||
        error("$(label) must be a 2x2 matrix.")
    matrix = Float64[rows[row][column] for row in 1:2, column in 1:2]
    all(isfinite, matrix) && isposdef(Symmetric(matrix)) ||
        error("$(label) must be finite, symmetric, and positive definite.")
    isapprox(matrix, transpose(matrix); rtol=1e-12, atol=0.0) ||
        error("$(label) must be symmetric.")
    return matrix
end

"""Load one provenance-bearing continuous-ground Q2D RLGC artifact."""
function load_d3_continuous_ground_q2d_input(path; section_length_m)
    input_path = abspath(String(path))
    isfile(input_path) || error("D3 Q2D RLGC input does not exist: $(input_path)")
    artifact_bytes = read(input_path)
    artifact_sha256 = bytes2hex(SHA.sha256(artifact_bytes))
    payload = JSON3.read(String(artifact_bytes), Dict{String,Any})
    Set(keys(payload)) == Set([
        "schema_version",
        "artifact_id",
        "topology_id",
        "geometry_um",
        "single_line",
        "coupled_pair",
        "solver",
        "loss_model",
        "coupling_orientation",
    ]) || error("D3 Q2D RLGC fields do not match its v1 contract.")
    payload["schema_version"] == D3_Q2D_RLGC_SCHEMA ||
        error("D3 Q2D RLGC schema is unsupported.")
    payload["topology_id"] == "continuous_upper_ground" ||
        error("D3 requires the Human-selected continuous upper ground.")
    payload["loss_model"] == "lossless_R_equals_G_equals_zero" ||
        error("D3 Q2D RLGC input must use the declared lossless model.")
    payload["coupling_orientation"] == "same_direction" ||
        error("D3 Q2D RLGC input must use same-direction coupling.")

    geometry = payload["geometry_um"]
    geometry_names = Set([
        "trace_width",
        "trace_gap",
        "inter_trace_ground_width",
        "flip_chip_gap_height",
        "upper_ground_clearance_width",
        "metal_thickness",
    ])
    Set(keys(geometry)) == geometry_names ||
        error("D3 Q2D geometry fields do not match the continuous-ground contract.")
    geometry_values = (
        w=_d3_q2d_positive(geometry["trace_width"], "D3 Q2D trace width"),
        s=_d3_q2d_positive(geometry["trace_gap"], "D3 Q2D trace gap"),
        d=_d3_q2d_positive(
            geometry["inter_trace_ground_width"],
            "D3 Q2D inter-trace ground width",
        ),
        h=_d3_q2d_positive(
            geometry["flip_chip_gap_height"],
            "D3 Q2D flip-chip gap height",
        ),
        upper_ground_clearance=_d3_q2d_nonnegative(
            geometry["upper_ground_clearance_width"],
            "D3 Q2D upper-ground clearance width",
        ),
        metal_thickness=_d3_q2d_positive(
            geometry["metal_thickness"],
            "D3 Q2D metal thickness",
        ),
    )
    geometry_values.upper_ground_clearance == 0.0 || error(
        "D3 continuous-upper-ground Q2D input requires zero upper-ground clearance.",
    )

    single = payload["single_line"]
    pair = payload["coupled_pair"]
    Set(keys(single)) == Set([
        "l_per_m_h",
        "c_per_m_f",
        "source_cache_key",
        "source_case_id",
        "cross_section_sha256",
        "capacitance_matrix_sha256",
        "inductance_matrix_sha256",
    ]) || error("D3 Q2D single-line fields do not match its v1 contract.")
    Set(keys(pair)) == Set([
        "l_matrix_per_m_h",
        "c_matrix_per_m_f",
        "source_cache_key",
        "source_case_id",
        "cross_section_sha256",
        "capacitance_matrix_sha256",
        "inductance_matrix_sha256",
    ]) || error("D3 Q2D coupled-pair fields do not match its v1 contract.")
    for (label, record) in (("single-line", single), ("coupled-pair", pair))
        for name in (
            "source_cache_key",
            "cross_section_sha256",
            "capacitance_matrix_sha256",
            "inductance_matrix_sha256",
        )
            _d3_q2d_hash(record[name], "D3 Q2D $(name)")
        end
        _d3_q2d_text(record["source_case_id"], "D3 Q2D $(label) source case id")
    end
    l_matrix = _d3_q2d_matrix(pair["l_matrix_per_m_h"], "D3 Q2D MTL L'")
    c_matrix = _d3_q2d_matrix(pair["c_matrix_per_m_f"], "D3 Q2D MTL C'")
    section = _d3_q2d_positive(section_length_m, "D3 line section length")
    section <= D3_MAX_LINE_SECTION_LENGTH_M || error(
        "D3 physical CPW/MTL section length must not exceed 50 um.",
    )
    artifact_id = _d3_q2d_text(payload["artifact_id"], "D3 Q2D artifact id")
    solver = payload["solver"]
    Set(keys(solver)) == Set([
        "aedt_version",
        "pyaedt_version",
        "adaptive_frequency_hz",
        "runtime_bundle_sha256",
    ]) || error("D3 Q2D solver fields do not match its v1 contract.")
    return (
        section_length_m=section,
        readout_l_per_m_h=_d3_q2d_positive(
            single["l_per_m_h"],
            "D3 single-line L'",
        ),
        readout_c_per_m_f=_d3_q2d_positive(
            single["c_per_m_f"],
            "D3 single-line C'",
        ),
        filter_l_per_m_h=_d3_q2d_positive(
            single["l_per_m_h"],
            "D3 single-line L'",
        ),
        filter_c_per_m_f=_d3_q2d_positive(
            single["c_per_m_f"],
            "D3 single-line C'",
        ),
        l_matrix_per_m_h=l_matrix,
        c_matrix_per_m_f=c_matrix,
        coupling_orientation=:same_direction,
        q2d_artifact_id=artifact_id,
        q2d_artifact_sha256=artifact_sha256,
        q2d_topology_id=:continuous_upper_ground,
        q2d_geometry_um=geometry_values,
        q2d_single_case_id=_d3_q2d_text(
            single["source_case_id"],
            "D3 Q2D single-line source case id",
        ),
        q2d_pair_case_id=_d3_q2d_text(
            pair["source_case_id"],
            "D3 Q2D coupled-pair source case id",
        ),
        q2d_solver=(
            adaptive_frequency_hz=_d3_q2d_positive(
                solver["adaptive_frequency_hz"],
                "D3 Q2D adaptive frequency",
            ),
            aedt_version=_d3_q2d_text(
                solver["aedt_version"],
                "D3 Q2D AEDT version",
            ),
            pyaedt_version=_d3_q2d_text(
                solver["pyaedt_version"],
                "D3 Q2D PyAEDT version",
            ),
            runtime_bundle_sha256=_d3_q2d_hash(
                solver["runtime_bundle_sha256"],
                "D3 Q2D runtime bundle SHA-256",
            ),
        ),
        q2d_loss_model=String(payload["loss_model"]),
    )
end

end
