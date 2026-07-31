# D3 fixed CPW/MTL input. This loader binds the continuous-upper-ground
# cross-section selected by the Human to its public Q2D matrices.

module D3ResonatorInput

using LinearAlgebra
using SHA
using SuperconductingCircuitsCore

const JSON3 = SuperconductingCircuitsCore.JSON3
const D3_Q2D_RLGC_SCHEMA = "d3-fixed-q2d-rlgc-input.v1"

export load_d3_continuous_ground_q2d_input

function _d3_q2d_positive(value, label)
    number = Float64(value)
    isfinite(number) && number > 0 || error("$(label) must be finite and positive.")
    return number
end

function _d3_q2d_hash(value, label)
    hash = lowercase(strip(String(value)))
    occursin(r"^[0-9a-f]{64}$", hash) ||
        error("$(label) must contain 64 lowercase hexadecimal characters.")
    return hash
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

"""Load the Human-selected continuous-ground 8-um Q2D RLGC artifact."""
function load_d3_continuous_ground_q2d_input(path; section_length_m)
    input_path = abspath(String(path))
    isfile(input_path) || error("D3 Q2D RLGC input does not exist: $(input_path)")
    payload = JSON3.read(read(input_path, String), Dict{String,Any})
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
    expected_geometry = Dict(
        "trace_width" => 3.0,
        "trace_gap" => 3.0,
        "inter_trace_ground_width" => 3.0,
        "flip_chip_gap_height" => 8.0,
        "upper_ground_clearance_width" => 0.0,
        "metal_thickness" => 0.2,
    )
    Set(keys(geometry)) == Set(keys(expected_geometry)) &&
        all(Float64(geometry[name]) == value for (name, value) in expected_geometry) ||
        error("D3 Q2D geometry must be the selected w=s=d=3 um, h=8 um continuous-ground point.")

    single = payload["single_line"]
    pair = payload["coupled_pair"]
    for record in (single, pair)
        for name in (
            "source_cache_key",
            "cross_section_sha256",
            "capacitance_matrix_sha256",
            "inductance_matrix_sha256",
        )
            _d3_q2d_hash(record[name], "D3 Q2D $(name)")
        end
        isempty(strip(String(record["source_case_id"]))) &&
            error("D3 Q2D source case id must not be empty.")
    end
    l_matrix = _d3_q2d_matrix(pair["l_matrix_per_m_h"], "D3 Q2D MTL L'")
    c_matrix = _d3_q2d_matrix(pair["c_matrix_per_m_f"], "D3 Q2D MTL C'")
    artifact_sha256 = open(input_path, "r") do io
        bytes2hex(SHA.sha256(io))
    end
    section = _d3_q2d_positive(section_length_m, "D3 line section length")
    artifact_id = strip(String(payload["artifact_id"]))
    isempty(artifact_id) && error("D3 Q2D artifact id must not be empty.")
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
        q2d_geometry_um=(
            w=3.0,
            s=3.0,
            d=3.0,
            h=8.0,
            upper_ground_clearance=0.0,
        ),
    )
end

end
