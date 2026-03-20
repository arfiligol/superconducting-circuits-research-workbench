"""Service for importing HFSS data into design/trace-first persistence."""

from pathlib import Path

from core.analysis.application.preprocessing.admittance import process_hfss_admittance_file
from core.analysis.application.preprocessing.naming import strip_dataset_suffix
from core.analysis.application.preprocessing.s_parameters import process_hfss_s_parameters
from core.analysis.application.services.database_service import save_dataset_payload_to_db
from core.analysis.infrastructure.paths import RAW_LAYOUT_SIMULATION_DIR
from core.shared.logging import get_logger

logger = get_logger(__name__)


def resolve_input_path(raw_path: Path, search_dir: Path) -> Path | None:
    """Resolve input path, checking search_dir if raw_path doesn't exist."""
    if raw_path.exists():
        return raw_path
    candidate = search_dir / raw_path
    if candidate.exists():
        return candidate
    return None


def import_hfss_to_database(
    file_path: Path,
    file_type: str,
    dataset_name: str | None = None,
    tags: list[str] | None = None,
    l_jun: float | None = None,
) -> None:
    """
    Import an HFSS file into the design/trace persistence path.

    Args:
        file_path: Path to the HFSS CSV file
        file_type: Either 'admittance' or 'scattering'
        dataset_name: Optional dataset name override (defaults to filename)
        tags: Optional list of tags to attach to the dataset
        l_jun: Optional manual L_jun value (nH) when CSV lacks an L_jun column
    """
    # Determine paths and processor
    search_dir = RAW_LAYOUT_SIMULATION_DIR
    if file_type == "admittance":
        processor = process_hfss_admittance_file
    elif file_type == "scattering":
        processor = process_hfss_s_parameters
    else:
        raise ValueError(f"Unknown file_type: {file_type}")

    # Resolve file path
    resolved_path = resolve_input_path(file_path, search_dir)
    if not resolved_path:
        logger.warning("File not found: %s", file_path)
        return

    # Determine dataset name
    name = dataset_name or strip_dataset_suffix(resolved_path.stem)

    try:
        # Process the file to dataset payload
        payload = processor(resolved_path, l_jun=l_jun)

        # Save to database
        dataset = save_dataset_payload_to_db(
            payload=payload,
            dataset_name=name,
            tags=tags,
        )

        # Auto-Analysis: Admittance Extraction
        has_admittance = any(
            ds.data_type == "y_parameters" and ds.representation in ("imaginary", "imag")
            for ds in payload.data_records
        )
        if has_admittance:
            try:
                logger.info("Auto-running Admittance Extraction for %s...", name)
                from core.analysis.application.services.resonance_extract_service import (
                    ResonanceExtractService,
                )

                service = ResonanceExtractService()
                service.extract_admittance(str(dataset.id))
                logger.info("Auto-analysis complete for %s.", name)
            except Exception as extract_err:
                logger.warning(
                    "Auto-analysis (Admittance Extraction) failed for %s: %s", name, extract_err
                )

    except Exception as e:
        logger.error("Failed to import %s: %s", resolved_path, e)
        logger.debug("Traceback:", exc_info=True)
