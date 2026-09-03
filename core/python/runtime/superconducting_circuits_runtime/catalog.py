"""Small public catalog backed by the existing Julia Core component authority."""

from .runtime import ComponentInstance

__all__ = [
    "intrinsic_interferometric_purcell_filter",
    "linearized_floating_qubit",
    "parallel_lc_resonator",
    "series_capacitor",
    "transmission_line",
]


def parallel_lc_resonator(
    *, id: str, capacitance_f: float, inductance_h: float, conductance_s: float = 0.0
) -> ComponentInstance:
    """Create one visible one-pin grounded parallel-LC-G resonator instance."""

    return ComponentInstance(
        id=id,
        type_id="workbench.parallel_lc_resonator.v1",
        parameters={
            "capacitance_f": capacitance_f,
            "inductance_h": inductance_h,
            "conductance_s": conductance_s,
        },
    )


def series_capacitor(*, id: str, capacitance_f: float) -> ComponentInstance:
    """Create one visible two-terminal series capacitor instance."""

    return ComponentInstance(
        id=id,
        type_id="workbench.series_capacitor.v1",
        parameters={"capacitance_f": capacitance_f},
    )


def transmission_line(
    *,
    id: str,
    length_m: float,
    n_sections: int,
    l_per_m_h: float,
    c_per_m_f: float,
    r_per_m_ohm: float = 0.0,
    g_per_m_s: float = 0.0,
) -> ComponentInstance:
    """Create one scalar RLGC ladder line with exposed head and tail nodes."""

    return ComponentInstance(
        id=id,
        type_id="workbench.transmission_line.v1",
        parameters={
            "length_m": length_m,
            "n_sections": n_sections,
            "l_per_m_h": l_per_m_h,
            "c_per_m_f": c_per_m_f,
            "r_per_m_ohm": r_per_m_ohm,
            "g_per_m_s": g_per_m_s,
        },
    )


def linearized_floating_qubit(
    *,
    id: str,
    c01_f: float,
    c02_f: float,
    c12_f: float,
    cr1_f: float,
    cr2_f: float,
    l_j_per_junction_h: float,
    josephson_branch_count: int = 2,
) -> ComponentInstance:
    """Create a floating linearized-qubit leaf with one or two junction branches."""

    return ComponentInstance(
        id=id,
        type_id="workbench.linearized_floating_qubit.v1",
        parameters={
            "c01_f": c01_f,
            "c02_f": c02_f,
            "c12_f": c12_f,
            "cr1_f": cr1_f,
            "cr2_f": cr2_f,
            "l_j_per_junction_h": l_j_per_junction_h,
            "josephson_branch_count": josephson_branch_count,
        },
    )


def intrinsic_interferometric_purcell_filter(
    *,
    id: str,
    readout_open_length_m: float,
    shared_short_length_m: float,
    coupled_length_m: float,
    filter_open_length_m: float,
    readout_short_sections: int,
    readout_open_sections: int,
    coupled_sections: int,
    filter_short_sections: int,
    filter_open_sections: int,
    readout_l_per_m_h: float,
    readout_c_per_m_f: float,
    filter_l_per_m_h: float,
    filter_c_per_m_f: float,
    mtl_l11_per_m_h: float,
    mtl_l12_per_m_h: float,
    mtl_l21_per_m_h: float,
    mtl_l22_per_m_h: float,
    mtl_c11_per_m_f: float,
    mtl_c12_per_m_f: float,
    mtl_c21_per_m_f: float,
    mtl_c22_per_m_f: float,
    idc_finger_length_um: float,
    idc_source_min_um: float,
    idc_source_max_um: float,
    idc_filter_ground_slope_f_per_um: float,
    idc_filter_ground_intercept_f: float,
    idc_feedline_ground_slope_f_per_um: float,
    idc_feedline_ground_intercept_f: float,
    idc_mutual_slope_f_per_um: float,
    idc_mutual_intercept_f: float,
    c0r_f: float = 0.0,
) -> ComponentInstance:
    """Create the intrinsic IPF leaf with explicit fixed discretization and IDC fit."""

    return ComponentInstance(
        id=id,
        type_id="workbench.intrinsic_interferometric_purcell_filter.v1",
        parameters={
            "readout_open_length_m": readout_open_length_m,
            "shared_short_length_m": shared_short_length_m,
            "coupled_length_m": coupled_length_m,
            "filter_open_length_m": filter_open_length_m,
            "readout_short_sections": readout_short_sections,
            "readout_open_sections": readout_open_sections,
            "coupled_sections": coupled_sections,
            "filter_short_sections": filter_short_sections,
            "filter_open_sections": filter_open_sections,
            "readout_l_per_m_h": readout_l_per_m_h,
            "readout_c_per_m_f": readout_c_per_m_f,
            "filter_l_per_m_h": filter_l_per_m_h,
            "filter_c_per_m_f": filter_c_per_m_f,
            "mtl_l11_per_m_h": mtl_l11_per_m_h,
            "mtl_l12_per_m_h": mtl_l12_per_m_h,
            "mtl_l21_per_m_h": mtl_l21_per_m_h,
            "mtl_l22_per_m_h": mtl_l22_per_m_h,
            "mtl_c11_per_m_f": mtl_c11_per_m_f,
            "mtl_c12_per_m_f": mtl_c12_per_m_f,
            "mtl_c21_per_m_f": mtl_c21_per_m_f,
            "mtl_c22_per_m_f": mtl_c22_per_m_f,
            "idc_finger_length_um": idc_finger_length_um,
            "idc_source_min_um": idc_source_min_um,
            "idc_source_max_um": idc_source_max_um,
            "idc_filter_ground_slope_f_per_um": idc_filter_ground_slope_f_per_um,
            "idc_filter_ground_intercept_f": idc_filter_ground_intercept_f,
            "idc_feedline_ground_slope_f_per_um": idc_feedline_ground_slope_f_per_um,
            "idc_feedline_ground_intercept_f": idc_feedline_ground_intercept_f,
            "idc_mutual_slope_f_per_um": idc_mutual_slope_f_per_um,
            "idc_mutual_intercept_f": idc_mutual_intercept_f,
            "c0r_f": c0r_f,
        },
    )
