"""Flux Dependence data parsing logic."""

from pathlib import Path

from core.analysis.application.preprocessing.dataset_payload import DatasetPayload


def parse_flux_dependence_txt(file_path: Path, name: str) -> DatasetPayload:
    """
    Parse Linköping VNA Flux Dependence TXT file.

    Expected format:
    - Frequency, Bias, Amplitude, Phase matrices

    Args:
        file_path: Path to the raw TXT file.
        name: Name of the component/dataset.

    Returns:
        DatasetPayload containing the parsed data.
    """
    # TODO: Implement actual parsing logic when sample data is available.
    # TODO: Implement actual parsing logic when sample data is available.
    # Fail loudly to prevent database pollution with dummy data.
    raise NotImplementedError(
        "Flux Dependence parsing is not yet implemented. "
        "Please provide sample .txt files to the development team to enable this feature."
    )
