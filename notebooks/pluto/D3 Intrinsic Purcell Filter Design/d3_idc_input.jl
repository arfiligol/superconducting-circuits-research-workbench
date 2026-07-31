# D3 project-specific Q3D IDC mapping. It preserves the complete three-branch
# component and binds the Human-declared terminal orientation to Stage 2/3.

module D3IDCInput

using LinearAlgebra
using SHA
using SuperconductingCircuitsCore

const JSON3 = SuperconductingCircuitsCore.JSON3
const D3_IDC_MAPPING_SCHEMA = "d3-three-branch-idc-gap-length-mapping.v1"
const D3_IDC_COEFFICIENT_NAMES = ("C_12_fF", "C_1G_fF", "C_2G_fF")

export D3IDCMapping, d3_idc_mapping_semantic_sha256, load_d3_idc_mapping

struct D3IDCMapping
    gap_um::Float64
    valid_gap_range_um::NTuple{2,Float64}
    valid_length_range_um::NTuple{2,Float64}
    length_center_um::Float64
    length_half_range_um::Float64
    coefficients_fF::Dict{String,Vector{Float64}}
    raw_samples_fF::Dict{Tuple{Float64,Float64},NamedTuple}
    mapping_id::String
    mapping_sha256::String
    source_artifact::Dict{String,Any}
    fit::Dict{String,Any}
end

function _d3_idc_basis(gap_um, length_um, center_um, half_range_um)
    h = Float64(gap_um)
    x = (Float64(length_um) - Float64(center_um)) / Float64(half_range_um)
    return Float64[
        1,
        1 / h,
        1 / h^2,
        x,
        x / h,
        x / h^2,
        x^2,
        x^2 / h,
        x^2 / h^2,
    ]
end

function (mapping::D3IDCMapping)(length_um)
    length_value = Float64(length_um)
    isfinite(length_value) || error("D3 IDC length must be finite.")
    mapping.valid_length_range_um[1] <= length_value <=
        mapping.valid_length_range_um[2] || error(
        "D3 IDC length $(length_value) um is outside the declared mapping domain.",
    )
    key = (mapping.gap_um, length_value)
    values = if haskey(mapping.raw_samples_fF, key)
        mapping.raw_samples_fF[key]
    else
        basis = _d3_idc_basis(
            mapping.gap_um,
            length_value,
            mapping.length_center_um,
            mapping.length_half_range_um,
        )
        NamedTuple{
            (:C_12_fF, :C_1G_fF, :C_2G_fF),
        }(Tuple(
            dot(mapping.coefficients_fF[name], basis)
            for name in D3_IDC_COEFFICIENT_NAMES
        ))
    end
    all(value -> isfinite(value) && value > 0, Base.values(values)) || error(
        "D3 IDC mapping produced a nonpositive capacitance.",
    )
    return (
        idc_filter_ground_capacitance_f=values.C_2G_fF * 1e-15,
        idc_feedline_ground_capacitance_f=values.C_1G_fF * 1e-15,
        idc_mutual_capacitance_f=values.C_12_fF * 1e-15,
        mapping_id=mapping.mapping_id,
        mapping_sha256=mapping.mapping_sha256,
        evaluation_gap_um=mapping.gap_um,
        evaluation_length_um=length_value,
        evaluation_source=haskey(mapping.raw_samples_fF, key) ?
            "raw_q3d_sample" : "tensor_product_formula_fit",
    )
end

"""
Return a deterministic hash of every `D3IDCMapping` field that can change its
three capacitance outputs, together with the selected source identity.
"""
function d3_idc_mapping_semantic_sha256(mapping::D3IDCMapping)
    coefficients = NamedTuple{
        Tuple(Symbol.(D3_IDC_COEFFICIENT_NAMES)),
    }(Tuple(
        Tuple(mapping.coefficients_fF[name])
        for name in D3_IDC_COEFFICIENT_NAMES
    ))
    sample_keys = sort!(collect(keys(mapping.raw_samples_fF)))
    samples = [
        begin
            values = mapping.raw_samples_fF[key]
            (
                gap_um=key[1],
                length_um=key[2],
                C_12_fF=values.C_12_fF,
                C_1G_fF=values.C_1G_fF,
                C_2G_fF=values.C_2G_fF,
            )
        end
        for key in sample_keys
    ]
    source_sha256 = get(mapping.source_artifact, "sha256", nothing)
    identity = (
        contract_id="d3-three-branch-idc-effective-mapping.v1",
        gap_um=mapping.gap_um,
        valid_gap_range_um=mapping.valid_gap_range_um,
        valid_length_range_um=mapping.valid_length_range_um,
        length_center_um=mapping.length_center_um,
        length_half_range_um=mapping.length_half_range_um,
        coefficients_fF=coefficients,
        raw_samples_fF=samples,
        mapping_id=mapping.mapping_id,
        source_artifact_sha256=source_sha256,
    )
    return bytes2hex(SHA.sha256(codeunits(JSON3.write(identity))))
end

function _d3_idc_required_range(raw, label)
    values = Float64.(collect(raw))
    length(values) == 2 && all(isfinite, values) && 0 < values[1] < values[2] ||
        error("$(label) must contain two increasing positive bounds.")
    return (values[1], values[2])
end

"""Load and independently validate one persisted Q3D IDC mapping."""
function load_d3_idc_mapping(path; gap_um=8.0)
    input_path = abspath(String(path))
    isfile(input_path) || error("D3 IDC mapping does not exist: $(input_path)")
    payload = JSON3.read(read(input_path, String), Dict{String,Any})
    Set(keys(payload)) == Set([
        "schema_version",
        "mapping_id",
        "capacitance_unit",
        "gap_unit",
        "length_unit",
        "nominal_gap_um",
        "valid_gap_range_um",
        "valid_length_range_um",
        "terminal_mapping",
        "coefficient_mapping",
        "evaluation_policy",
        "source_artifact",
        "samples",
        "fit",
    ]) || error("D3 IDC mapping fields do not match its v1 contract.")
    payload["schema_version"] == D3_IDC_MAPPING_SCHEMA || error(
        "D3 IDC mapping schema is unsupported.",
    )
    payload["capacitance_unit"] == "fF" &&
        payload["gap_unit"] == "um" &&
        payload["length_unit"] == "um" ||
        error("D3 IDC mapping units must be fF and um.")
    payload["evaluation_policy"] ==
        "exact_tabulated_point_uses_raw_q3d_sample__other_in_domain_points_use_persisted_tensor_fit" ||
        error("D3 IDC evaluation policy is invalid.")
    terminal_mapping = payload["terminal_mapping"]
    Set(keys(terminal_mapping)) ==
        Set(["authority", "terminal_1", "terminal_2"]) &&
        terminal_mapping["authority"] == "human" &&
        terminal_mapping["terminal_1"] == "f_c" &&
        terminal_mapping["terminal_2"] == "p" ||
        error("D3 IDC terminal orientation must be terminal 1=f_c, terminal 2=p.")
    coefficient_mapping = payload["coefficient_mapping"]
    coefficient_mapping == Dict(
        "C_12_fF" => "C_pf_c_IDC",
        "C_1G_fF" => "C_f_cG_IDC",
        "C_2G_fF" => "C_pG_IDC",
    ) || error("D3 IDC coefficient-to-circuit mapping is invalid.")

    valid_gap_range = _d3_idc_required_range(
        payload["valid_gap_range_um"],
        "D3 IDC gap range",
    )
    valid_length_range = _d3_idc_required_range(
        payload["valid_length_range_um"],
        "D3 IDC length range",
    )
    selected_gap = Float64(gap_um)
    isfinite(selected_gap) &&
        valid_gap_range[1] <= selected_gap <= valid_gap_range[2] ||
        error("Requested D3 IDC gap is outside the declared mapping domain.")

    samples = payload["samples"]
    length(samples) >= 9 || error("D3 IDC mapping requires multiple raw samples.")
    raw_samples = Dict{Tuple{Float64,Float64},NamedTuple}()
    sample_gaps = Float64[]
    sample_lengths = Float64[]
    sample_columns = Dict(
        name => Float64[] for name in D3_IDC_COEFFICIENT_NAMES
    )
    for sample in samples
        Set(keys(sample)) == Set([
            "gap_um",
            "length_um",
            "C_12_fF",
            "C_1G_fF",
            "C_2G_fF",
        ]) || error("D3 IDC raw sample fields are invalid.")
        sample_gap = Float64(sample["gap_um"])
        sample_length = Float64(sample["length_um"])
        values = (
            C_12_fF=Float64(sample["C_12_fF"]),
            C_1G_fF=Float64(sample["C_1G_fF"]),
            C_2G_fF=Float64(sample["C_2G_fF"]),
        )
        all(value -> isfinite(value) && value > 0, Base.values(values)) || error(
            "D3 IDC raw samples must be finite and positive.",
        )
        key = (sample_gap, sample_length)
        haskey(raw_samples, key) && error("D3 IDC raw sample keys must be unique.")
        raw_samples[key] = values
        push!(sample_gaps, sample_gap)
        push!(sample_lengths, sample_length)
        for name in D3_IDC_COEFFICIENT_NAMES
            push!(sample_columns[name], getproperty(values, Symbol(name)))
        end
    end

    fit = payload["fit"]
    Set(keys(fit)) == Set([
        "model",
        "basis",
        "normalized_length",
        "least_squares_rank",
        "design_matrix_condition_number",
        "coefficient_fits",
        "validation",
    ]) || error("D3 IDC fit fields are invalid.")
    fit["model"] ==
        "tensor_product_quadratic_in_normalized_length_and_quadratic_in_inverse_gap" ||
        error("D3 IDC fit model is invalid.")
    collect(fit["basis"]) == [
        "1",
        "1/h_um",
        "1/h_um^2",
        "x",
        "x/h_um",
        "x/h_um^2",
        "x^2",
        "x^2/h_um",
        "x^2/h_um^2",
    ] || error("D3 IDC fit basis is invalid.")
    Int(fit["least_squares_rank"]) == 9 || error(
        "D3 IDC fit must have rank nine.",
    )
    normalization = fit["normalized_length"]
    normalization["definition"] == "x=(length_um-center_um)/half_range_um" ||
        error("D3 IDC normalized-length definition is invalid.")
    center_um = Float64(normalization["center_um"])
    half_range_um = Float64(normalization["half_range_um"])
    isfinite(center_um) && isfinite(half_range_um) && half_range_um > 0 ||
        error("D3 IDC normalized-length parameters are invalid.")
    design = reduce(vcat, (
        permutedims(_d3_idc_basis(h, l, center_um, half_range_um))
        for (h, l) in zip(sample_gaps, sample_lengths)
    ))
    rank(design) == 9 || error("D3 IDC recomputed fit basis is rank deficient.")
    coefficients_fF = Dict{String,Vector{Float64}}()
    coefficient_fits = fit["coefficient_fits"]
    Set(keys(coefficient_fits)) == Set(D3_IDC_COEFFICIENT_NAMES) || error(
        "D3 IDC fit must preserve all three capacitance coefficients.",
    )
    for name in D3_IDC_COEFFICIENT_NAMES
        fit_record = coefficient_fits[name]
        Set(keys(fit_record)) == Set([
            "coefficients_fF",
            "rms_residual_fF",
            "max_abs_residual_fF",
            "max_abs_relative_residual",
        ]) || error("D3 IDC coefficient-fit fields are invalid.")
        coefficients = Float64.(collect(fit_record["coefficients_fF"]))
        length(coefficients) == 9 && all(isfinite, coefficients) || error(
            "D3 IDC coefficient fit must contain nine finite coefficients.",
        )
        actual = sample_columns[name]
        recomputed = design \ actual
        isapprox(coefficients, recomputed; rtol=1e-10, atol=1e-10) || error(
            "D3 IDC serialized coefficients disagree with an independent least-squares solve.",
        )
        residual = design * coefficients - actual
        rms = sqrt(sum(abs2, residual) / length(residual))
        max_abs = maximum(abs, residual)
        max_relative = maximum(abs.(residual) ./ actual)
        isapprox(
            rms,
            Float64(fit_record["rms_residual_fF"]);
            rtol=1e-10,
            atol=1e-12,
        ) && isapprox(
            max_abs,
            Float64(fit_record["max_abs_residual_fF"]);
            rtol=1e-10,
            atol=1e-12,
        ) && isapprox(
            max_relative,
            Float64(fit_record["max_abs_relative_residual"]);
            rtol=1e-10,
            atol=1e-14,
        ) || error("D3 IDC serialized fit residuals are inconsistent.")
        coefficients_fF[name] = coefficients
    end

    source = Dict{String,Any}(
        String(key) => value for (key, value) in payload["source_artifact"]
    )
    occursin(r"^[0-9a-f]{64}$", String(source["sha256"])) || error(
        "D3 IDC source artifact must carry a lowercase SHA-256.",
    )
    mapping_id = strip(String(payload["mapping_id"]))
    isempty(mapping_id) && error("D3 IDC mapping id must not be empty.")
    mapping_sha256 = open(input_path, "r") do io
        bytes2hex(SHA.sha256(io))
    end
    return D3IDCMapping(
        selected_gap,
        valid_gap_range,
        valid_length_range,
        center_um,
        half_range_um,
        coefficients_fF,
        raw_samples,
        mapping_id,
        mapping_sha256,
        source,
        Dict{String,Any}(String(key) => value for (key, value) in fit),
    )
end

end
