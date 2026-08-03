"""Physics-agnostic composer for one-page, Human-reviewable simulation reports.

The producer owns every plotted value, unit, label, and availability reason.
This module only validates the declared evidence, lays out the approved V1
blocks, and atomically publishes a PNG plus a sanitized register.
"""

from __future__ import annotations

import base64
import hashlib
import html
import importlib.metadata
import json
import math
import re
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

import plotly.graph_objects as go
from plotly.subplots import make_subplots

SCHEMA_VERSION = "human-reviewable-simulation-report.v1"
REGISTER_SCHEMA_VERSION = "human-reviewable-simulation-report-register.v1"
REPORT_FILENAME = "report.png"
REGISTER_FILENAME = "report_register.json"
REPORT_WIDTH_PX = 1800
_REPORT_ID = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_BLOCK_SIGNATURE = (
    ("media", None),
    ("optimization_history", None),
    ("table", "metrics"),
    ("table", "parameters"),
    ("table", "fixed_specifications"),
    ("table", "provenance"),
)


def render_simulation_report(manifest: Mapping[str, Any], output_directory: Path) -> Path:
    """Validate, render, and atomically publish one V1 report.

    ``output_directory`` must not exist. The returned path is the completed,
    sanitized register; source filesystem paths never enter that register.
    """

    normalized = _validate_manifest(manifest)
    destination = output_directory.resolve()
    if destination.exists():
        raise FileExistsError(f"Output directory already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}.building-", dir=destination.parent)
    )
    try:
        report_path = temporary / REPORT_FILENAME
        figure, report_height = _build_figure(normalized)
        figure.write_image(
            report_path,
            format="png",
            width=REPORT_WIDTH_PX,
            height=report_height,
            scale=1,
        )
        register = _build_register(normalized, report_path, report_height)
        _assert_no_private_absolute_paths(register)
        (temporary / REGISTER_FILENAME).write_text(
            json.dumps(register, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        if destination.exists():
            raise FileExistsError(f"Output directory appeared during rendering: {destination}")
        temporary.rename(destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination / REGISTER_FILENAME


def file_sha256(path: Path) -> str:
    """Return the lowercase SHA-256 digest of a file."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    value = _mapping(manifest, "manifest")
    _exact_keys(
        value,
        {
            "schema_version",
            "report_id",
            "title",
            "producer_id",
            "publication_visibility",
            "source_files",
            "blocks",
        },
        "manifest",
    )
    if value["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"manifest.schema_version must be {SCHEMA_VERSION!r}.")
    report_id = _text(value["report_id"], "manifest.report_id")
    if not _REPORT_ID.fullmatch(report_id):
        raise ValueError("manifest.report_id must be lowercase and filesystem-safe.")
    title = _text(value["title"], "manifest.title")
    producer_id = _text(value["producer_id"], "manifest.producer_id")
    visibility = _enum(
        value["publication_visibility"],
        {"private", "public"},
        "manifest.publication_visibility",
    )

    sources: list[dict[str, Any]] = []
    source_ids: set[str] = set()
    for index, source_value in enumerate(_sequence(value["source_files"], "manifest.source_files")):
        path = f"manifest.source_files[{index}]"
        source = _mapping(source_value, path)
        _exact_keys(source, {"id", "path", "locator", "sha256", "visibility"}, path)
        source_id = _text(source["id"], f"{path}.id")
        if source_id in source_ids:
            raise ValueError(f"Duplicate source id {source_id!r}.")
        source_ids.add(source_id)
        source_path = Path(_text(source["path"], f"{path}.path")).resolve()
        if not source_path.is_file():
            raise ValueError(f"{path}.path is not a readable file: {source_path}")
        locator = _relative_locator(source["locator"], f"{path}.locator")
        expected_sha = _digest(source["sha256"], f"{path}.sha256")
        actual_sha = file_sha256(source_path)
        if actual_sha != expected_sha:
            raise ValueError(
                f"{path}.sha256 mismatch: expected {expected_sha}, got {actual_sha}."
            )
        source_visibility = _enum(
            source["visibility"], {"private", "public"}, f"{path}.visibility"
        )
        if visibility == "public" and source_visibility != "public":
            raise ValueError(
                f"Public report cannot cite non-public source {source_id!r}."
            )
        sources.append(
            {
                "id": source_id,
                "path": source_path,
                "locator": locator,
                "sha256": actual_sha,
                "size_bytes": source_path.stat().st_size,
                "visibility": source_visibility,
            }
        )

    raw_blocks = _sequence(value["blocks"], "manifest.blocks")
    if len(raw_blocks) != len(_REQUIRED_BLOCK_SIGNATURE):
        raise ValueError(
            "manifest.blocks must contain exactly media, optimization_history, "
            "metrics, parameters, fixed_specifications, and provenance in V1 order."
        )
    blocks: list[dict[str, Any]] = []
    block_ids: set[str] = set()
    for index, (raw_block, expected) in enumerate(
        zip(raw_blocks, _REQUIRED_BLOCK_SIGNATURE, strict=True)
    ):
        block_path = f"manifest.blocks[{index}]"
        block = _mapping(raw_block, block_path)
        block_type = _text(block.get("type"), f"{block_path}.type")
        role = block.get("role")
        actual_signature = (block_type, role)
        if actual_signature != expected:
            raise ValueError(
                f"{block_path} must have signature {expected}, got {actual_signature}."
            )
        block_id = _text(block.get("id"), f"{block_path}.id")
        if block_id in block_ids:
            raise ValueError(f"Duplicate block id {block_id!r}.")
        block_ids.add(block_id)
        if block_type == "media":
            normalized_block = _validate_media_block(block, block_path, source_ids)
        elif block_type == "optimization_history":
            normalized_block = _validate_history_block(block, block_path, source_ids)
        else:
            normalized_block = _validate_table_block(block, block_path, source_ids)
        blocks.append(normalized_block)

    return {
        "schema_version": SCHEMA_VERSION,
        "report_id": report_id,
        "title": title,
        "producer_id": producer_id,
        "publication_visibility": visibility,
        "source_files": sources,
        "blocks": blocks,
    }


def _validate_media_block(
    block: Mapping[str, Any], path: str, source_ids: set[str]
) -> dict[str, Any]:
    _exact_keys(block, {"type", "id", "title", "path", "sha256", "source_ids"}, path)
    media_path = Path(_text(block["path"], f"{path}.path")).resolve()
    if not media_path.is_file():
        raise ValueError(f"{path}.path is not a readable file: {media_path}")
    expected_sha = _digest(block["sha256"], f"{path}.sha256")
    actual_sha = file_sha256(media_path)
    if actual_sha != expected_sha:
        raise ValueError(f"{path}.sha256 mismatch: expected {expected_sha}, got {actual_sha}.")
    if media_path.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path}.path must be a PNG image.")
    return {
        "type": "media",
        "id": _text(block["id"], f"{path}.id"),
        "title": _text(block["title"], f"{path}.title"),
        "path": media_path,
        "sha256": actual_sha,
        "size_bytes": media_path.stat().st_size,
        "source_ids": _source_ids(block["source_ids"], f"{path}.source_ids", source_ids),
    }


def _validate_history_block(
    block: Mapping[str, Any], path: str, source_ids: set[str]
) -> dict[str, Any]:
    _exact_keys(
        block,
        {
            "type",
            "id",
            "title",
            "x_label",
            "y_label",
            "x_values",
            "y_values",
            "y_scale",
            "source_ids",
        },
        path,
    )
    x_values = _finite_numbers(block["x_values"], f"{path}.x_values")
    y_values = _finite_numbers(block["y_values"], f"{path}.y_values")
    if not x_values or len(x_values) != len(y_values):
        raise ValueError(f"{path} must contain equally sized, non-empty x/y arrays.")
    y_scale = _enum(block["y_scale"], {"linear", "log"}, f"{path}.y_scale")
    if y_scale == "log" and any(value <= 0 for value in y_values):
        raise ValueError(f"{path}.y_values must be positive for log scale.")
    return {
        "type": "optimization_history",
        "id": _text(block["id"], f"{path}.id"),
        "title": _text(block["title"], f"{path}.title"),
        "x_label": _text(block["x_label"], f"{path}.x_label"),
        "y_label": _text(block["y_label"], f"{path}.y_label"),
        "x_values": x_values,
        "y_values": y_values,
        "y_scale": y_scale,
        "source_ids": _source_ids(block["source_ids"], f"{path}.source_ids", source_ids),
    }


def _validate_table_block(
    block: Mapping[str, Any], path: str, source_ids: set[str]
) -> dict[str, Any]:
    _exact_keys(
        block,
        {
            "type",
            "id",
            "role",
            "title",
            "columns",
            "rows",
            "column_widths",
            "source_ids",
        },
        path,
    )
    columns = [
        _text(value, f"{path}.columns[{index}]")
        for index, value in enumerate(_sequence(block["columns"], f"{path}.columns"))
    ]
    if not columns or len(set(columns)) != len(columns):
        raise ValueError(f"{path}.columns must be non-empty and unique.")
    rows: list[list[str]] = []
    for row_index, raw_row in enumerate(_sequence(block["rows"], f"{path}.rows")):
        raw_cells = _sequence(raw_row, f"{path}.rows[{row_index}]")
        if len(raw_cells) != len(columns):
            raise ValueError(
                f"{path}.rows[{row_index}] has {len(raw_cells)} cells; expected {len(columns)}."
            )
        rows.append(
            [
                _display_cell(cell, f"{path}.rows[{row_index}][{column_index}]")
                for column_index, cell in enumerate(raw_cells)
            ]
        )
    if not rows:
        raise ValueError(f"{path}.rows must not be empty.")
    widths = _finite_numbers(block["column_widths"], f"{path}.column_widths")
    if len(widths) != len(columns) or any(value <= 0 for value in widths):
        raise ValueError(f"{path}.column_widths must contain one positive value per column.")
    return {
        "type": "table",
        "id": _text(block["id"], f"{path}.id"),
        "role": block["role"],
        "title": _text(block["title"], f"{path}.title"),
        "columns": columns,
        "rows": rows,
        "column_widths": widths,
        "source_ids": _source_ids(block["source_ids"], f"{path}.source_ids", source_ids),
    }


def _build_figure(manifest: Mapping[str, Any]) -> tuple[go.Figure, int]:
    media, history, *tables = manifest["blocks"]
    pixel_heights = [900, 470] + [
        105 + (68 if len(table["columns"]) > 4 else 42) * len(table["rows"])
        for table in tables
    ]
    report_height = 190 + sum(pixel_heights) + 38 * (len(pixel_heights) - 1)
    figure = make_subplots(
        rows=6,
        cols=1,
        specs=[
            [{"type": "xy"}],
            [{"type": "xy"}],
            [{"type": "table"}],
            [{"type": "table"}],
            [{"type": "table"}],
            [{"type": "table"}],
        ],
        row_heights=pixel_heights,
        vertical_spacing=0.024,
        subplot_titles=[block["title"] for block in manifest["blocks"]],
    )

    media_uri = "data:image/png;base64," + base64.b64encode(media["path"].read_bytes()).decode(
        "ascii"
    )
    figure.add_layout_image(
        source=media_uri,
        xref="x domain",
        yref="y domain",
        x=0,
        y=1,
        sizex=1,
        sizey=1,
        sizing="contain",
        layer="above",
    )
    figure.update_xaxes(visible=False, range=(0, 1), row=1, col=1)
    figure.update_yaxes(visible=False, range=(0, 1), row=1, col=1)

    figure.add_trace(
        go.Scatter(
            x=history["x_values"],
            y=history["y_values"],
            mode="lines",
            line={"color": "#6f42c1", "width": 3},
            name=history["y_label"],
            showlegend=False,
            hovertemplate="%{x}<br>%{y:.6g}<extra></extra>",
        ),
        row=2,
        col=1,
    )
    figure.add_trace(
        go.Scatter(
            x=[history["x_values"][-1]],
            y=[history["y_values"][-1]],
            mode="markers",
            marker={"color": "#6f42c1", "size": 11},
            showlegend=False,
            hoverinfo="skip",
        ),
        row=2,
        col=1,
    )
    figure.update_xaxes(title_text=history["x_label"], showgrid=True, row=2, col=1)
    figure.update_yaxes(
        title_text=history["y_label"],
        type=history["y_scale"],
        showgrid=True,
        row=2,
        col=1,
    )

    for row_index, table in enumerate(tables, start=3):
        columns = list(zip(*table["rows"], strict=True))
        font_colors = [
            [_status_color(value) for value in column]
            for column in columns
        ]
        figure.add_trace(
            go.Table(
                columnwidth=table["column_widths"],
                header={
                    "values": [f"<b>{_escaped(value)}</b>" for value in table["columns"]],
                    "align": "left",
                    "fill_color": "#e7edf5",
                    "font": {"color": "#182235", "size": 19},
                    "height": 40,
                },
                cells={
                    "values": [[_escaped(value) for value in column] for column in columns],
                    "align": "left",
                    "fill_color": "#ffffff",
                    "font": {"color": font_colors, "size": 17},
                    "height": 34,
                },
            ),
            row=row_index,
            col=1,
        )

    figure.update_layout(
        title={
            "text": manifest["title"],
            "x": 0.5,
            "xanchor": "center",
            "font": {"size": 30, "color": "#111827"},
        },
        width=REPORT_WIDTH_PX,
        height=report_height,
        margin={"l": 90, "r": 90, "t": 110, "b": 70},
        paper_bgcolor="white",
        plot_bgcolor="white",
        font={"family": "DejaVu Sans, Arial, sans-serif", "size": 17, "color": "#182235"},
        template="plotly_white",
    )
    for annotation in figure.layout.annotations:
        annotation.font = {"size": 22, "color": "#182235"}
    return figure, report_height


def _build_register(
    manifest: Mapping[str, Any], report_path: Path, report_height: int
) -> dict[str, Any]:
    block_records: list[dict[str, Any]] = []
    for block in manifest["blocks"]:
        record = {
            "id": block["id"],
            "type": block["type"],
            "title": block["title"],
            "source_ids": block["source_ids"],
        }
        if block["type"] == "media":
            record["embedded_sha256"] = block["sha256"]
            record["embedded_size_bytes"] = block["size_bytes"]
        elif block["type"] == "optimization_history":
            record.update(
                {
                    "point_count": len(block["x_values"]),
                    "x_label": block["x_label"],
                    "y_label": block["y_label"],
                    "y_scale": block["y_scale"],
                    "first_y": block["y_values"][0],
                    "last_y": block["y_values"][-1],
                    "minimum_y": min(block["y_values"]),
                }
            )
        else:
            record.update(
                {
                    "role": block["role"],
                    "columns": block["columns"],
                    "rows": block["rows"],
                }
            )
        block_records.append(record)
    return {
        "schema_version": REGISTER_SCHEMA_VERSION,
        "status": "complete",
        "report_id": manifest["report_id"],
        "title": manifest["title"],
        "producer_id": manifest["producer_id"],
        "publication_visibility": manifest["publication_visibility"],
        "physical_promotion_claim": False,
        "human_acceptance_claim": False,
        "source_files": [
            {
                "id": source["id"],
                "locator": source["locator"],
                "sha256": source["sha256"],
                "size_bytes": source["size_bytes"],
                "visibility": source["visibility"],
            }
            for source in manifest["source_files"]
        ],
        "blocks": block_records,
        "artifacts": [
            {
                "filename": REPORT_FILENAME,
                "sha256": file_sha256(report_path),
                "size_bytes": report_path.stat().st_size,
                "width_px": REPORT_WIDTH_PX,
                "height_px": report_height,
                "media_type": "image/png",
            }
        ],
        "renderer": {
            "plotly_version": importlib.metadata.version("plotly"),
            "kaleido_version": importlib.metadata.version("kaleido"),
        },
    }


def _display_cell(value: Any, path: str) -> str:
    if isinstance(value, str):
        return _text(value, path)
    if isinstance(value, Mapping):
        cell = _mapping(value, path)
        _exact_keys(cell, {"status", "reason"}, path)
        if cell["status"] != "NOT_AVAILABLE":
            raise ValueError(f"{path}.status must be 'NOT_AVAILABLE'.")
        return f"NOT_AVAILABLE — {_text(cell['reason'], f'{path}.reason')}"
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{path} must be finite text/number or NOT_AVAILABLE with a reason.")
    return str(value)


def _source_ids(value: Any, path: str, known: set[str]) -> list[str]:
    values = [_text(item, f"{path}[{index}]") for index, item in enumerate(_sequence(value, path))]
    if not values or len(values) != len(set(values)):
        raise ValueError(f"{path} must be non-empty and unique.")
    unknown = sorted(set(values) - known)
    if unknown:
        raise ValueError(f"{path} contains unknown source ids: {unknown}.")
    return values


def _finite_numbers(value: Any, path: str) -> list[float]:
    numbers: list[float] = []
    for index, item in enumerate(_sequence(value, path)):
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(f"{path}[{index}] must be numeric.")
        number = float(item)
        if not math.isfinite(number):
            raise ValueError(f"{path}[{index}] must be finite.")
        numbers.append(number)
    return numbers


def _relative_locator(value: Any, path: str) -> str:
    locator = _text(value, path)
    pure = PurePosixPath(locator)
    if pure.is_absolute() or ".." in pure.parts or locator != pure.as_posix():
        raise ValueError(f"{path} must be a normalized relative POSIX locator.")
    return locator


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must be an object.")
    return value


def _sequence(value: Any, path: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{path} must be an array.")
    return value


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path} must be non-empty text.")
    return value.strip()


def _enum(value: Any, choices: set[str], path: str) -> str:
    text = _text(value, path)
    if text not in choices:
        raise ValueError(f"{path} must be one of {sorted(choices)}.")
    return text


def _digest(value: Any, path: str) -> str:
    text = _text(value, path)
    if not _SHA256.fullmatch(text):
        raise ValueError(f"{path} must be a lowercase SHA-256 digest.")
    return text


def _exact_keys(value: Mapping[str, Any], expected: set[str], path: str) -> None:
    actual = set(value)
    if actual != expected:
        raise ValueError(
            f"{path} fields mismatch; missing={sorted(expected - actual)}, "
            f"unexpected={sorted(actual - expected)}."
        )


def _escaped(value: str) -> str:
    return html.escape(value).replace("\n", "<br>")


def _status_color(value: str) -> str:
    if value == "PASS":
        return "#16835b"
    if value == "FAIL":
        return "#b42318"
    if value.startswith("NOT_AVAILABLE"):
        return "#9a6700"
    return "#182235"


def _assert_no_private_absolute_paths(value: Any, path: str = "register") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            _assert_no_private_absolute_paths(child, f"{path}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for index, child in enumerate(value):
            _assert_no_private_absolute_paths(child, f"{path}[{index}]")
    elif isinstance(value, str):
        if "/home/" in value or "\\Users\\" in value or re.search(
            r"(^|[\s(])/(?:tmp|var|root|etc)/", value
        ):
            raise ValueError(f"{path} contains a private absolute filesystem path.")


__all__ = [
    "REGISTER_FILENAME",
    "REGISTER_SCHEMA_VERSION",
    "REPORT_FILENAME",
    "SCHEMA_VERSION",
    "file_sha256",
    "render_simulation_report",
]
