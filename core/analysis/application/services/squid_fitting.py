#!/usr/bin/env python3
"""Service for SQUID model fitting workflows."""

from collections.abc import Sequence
from enum import Enum

import pandas as pd

from core.analysis.application.analysis.extraction.admittance import extract_modes_from_dataframe
from core.analysis.application.analysis.extraction.cleaning import normalize_mode_columns
from core.analysis.application.analysis.fitting.modes import (
    fit_squid_model,
    fit_squid_model_with_Ls,
    fit_squid_model_with_Ls_fixed_C,
)
from core.analysis.application.services.trace_record_materializer import materialize_trace_record
from core.analysis.domain.schemas.fitting import AnalysisEntry
from core.analysis.domain.services.data_conversion import convert_data_record_to_dataframe
from core.analysis.infrastructure.visualization.dataframe_display import print_dataframe_table
from core.shared.logging import get_logger
from core.shared.persistence import DataRecord, DatasetRecord, get_unit_of_work

logger = get_logger(__name__)


class FitModel(Enum):
    """Fit model types for SQUID analysis."""

    NO_LS = "no_ls"
    WITH_LS = "with_ls"
    FIXED_C = "fixed_c"


def resolve_dataset(candidate: str) -> DatasetRecord | None:
    """Resolve dataset by ID or name."""
    with get_unit_of_work() as uow:
        dataset = None
        if candidate.isdigit():
            dataset = uow.datasets.get(int(candidate))
        if dataset is None:
            dataset = uow.datasets.get_by_name(candidate)
        if dataset is None:
            logger.warning("Dataset not found: %s", candidate)
        return dataset


def find_data_record(records: list[DataRecord]) -> DataRecord | None:
    """Find Y11 imaginary data record for fitting."""
    for record in records:
        if (
            record.data_type.lower() == "y_parameters"
            and record.parameter.upper() == "Y11"
            and record.representation.lower() == "imaginary"
        ):
            return record
    return None


def extract_modes(dataset: DatasetRecord) -> pd.DataFrame | None:
    """Load dataset from DB and extract resonant modes."""
    with get_unit_of_work() as uow:
        records = uow.data_records.list_by_dataset(dataset.id) if dataset.id else []

    data_record = find_data_record(records)
    if not data_record:
        logger.error("Y11 imaginary data record not found in %s", dataset.name)
        return None

    df_raw = convert_data_record_to_dataframe(
        materialize_trace_record(data_record),
        value_label="im(Y) []",
    )
    df_modes = extract_modes_from_dataframe(df_raw)
    if df_modes is None:
        return None
    df_modes = normalize_mode_columns(df_modes)
    return df_modes


def analyze_file(
    dataset: DatasetRecord,
    modes_to_highlight: Sequence[str] | None,
    parameter_bounds: dict[str, tuple[float | None, float | None]],
    fit_model: FitModel,
    fixed_c: float | None,
    fit_window: tuple[float | None, float | None],
) -> AnalysisEntry | None:
    """Execute the full SQUID fitting workflow for a single dataset."""
    logger.info("Processing %s", dataset.name)
    df_modes = extract_modes(dataset)
    if df_modes is None or df_modes.empty:
        logger.warning("Extraction failed for %s", dataset.name)
        return None

    # Filter columns if specific modes are requested
    if modes_to_highlight:
        # Keep non-mode columns (like L_jun, flux, etc.) + requested modes
        available_modes = [c for c in df_modes.columns if "Mode" in c]
        keep_modes = [m for m in available_modes if m in modes_to_highlight]
        other_cols = [c for c in df_modes.columns if "Mode" not in c]

        if keep_modes:
            df_modes = df_modes[other_cols + keep_modes]
        else:
            logger.warning(
                "Requested modes %s not found in dataset. Available: %s",
                modes_to_highlight,
                available_modes,
            )

    print_dataframe_table(f"Extracted Resonant Modes ({dataset.name})", df_modes)

    if fit_model == FitModel.NO_LS:
        fit_results = fit_squid_model(df_modes, parameter_bounds, fit_window)
    elif fit_model == FitModel.WITH_LS:
        fit_results = fit_squid_model_with_Ls(df_modes, parameter_bounds, fit_window)
    elif fit_model == FitModel.FIXED_C:
        if fixed_c is None:
            logger.error("fixed_c required for fixed-c model")
            return None
        fit_results = fit_squid_model_with_Ls_fixed_C(
            df_modes, fixed_c, parameter_bounds, fit_window
        )
    else:
        raise ValueError("Unknown fit model")

    return AnalysisEntry(filename=dataset.name, fits=fit_results)
