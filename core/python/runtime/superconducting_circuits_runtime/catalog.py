"""Small public catalog backed by the existing Julia Core component authority."""

from .runtime import ComponentInstance

__all__ = ["parallel_lc_resonator"]


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
