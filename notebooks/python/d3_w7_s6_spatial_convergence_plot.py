#!/usr/bin/env python3
"""Render the Task-local W7/S6 spatial-convergence receipt."""

from __future__ import annotations

import argparse
import csv
import json
from collections import OrderedDict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

QUANTITIES = (
    ("f_r", "#1f77b4", r"$f_r$"),
    ("f_p", "#ff7f0e", r"$f_p$"),
    ("f_n", "#2ca02c", r"$f_n$"),
)
AXES = ("mtl_first", "single_trace", "mtl_recheck", "joint")
AXIS_TITLES = {
    "mtl_first": "1. MTL-window refinement (Single Trace fixed)",
    "single_trace": "2. Four Single-Trace regions (MTL fixed)",
    "mtl_recheck": "3. MTL-window recheck (selected Single Trace fixed)",
    "joint": "4. Final joint operational/reference check",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence_directory", type=Path)
    return parser.parse_args()


def read_rows(path: Path) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, OrderedDict[str, dict[str, str]]] = {axis: OrderedDict() for axis in AXES}
    with path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            grouped[row["axis"]][row["state_id"]] = row
    rows = {axis: list(items.values()) for axis, items in grouped.items()}
    for axis in ("mtl_first", "mtl_recheck"):
        rows[axis].sort(key=lambda row: int(row["mtl_count"]))
    rows["single_trace"].sort(key=lambda row: int(row["outer_total"]))
    rows["joint"].sort(key=lambda row: int(row["outer_total"]) + 2 * int(row["mtl_count"]))
    return rows


def counts_label(row: dict[str, str]) -> str:
    return (
        f"{row['outer_total']}\n[{row['r_short']},{row['r_open']},{row['p_short']},{row['p_open']}]"
    )


def x_values(axis: str, rows: list[dict[str, str]]) -> tuple[list[int], list[str]]:
    if axis in ("mtl_first", "mtl_recheck"):
        values = [int(row["mtl_count"]) for row in rows]
        return values, [str(value) for value in values]
    if axis == "single_trace":
        values = [int(row["outer_total"]) for row in rows]
        return values, [counts_label(row) for row in rows]
    values = [int(row["outer_total"]) + 2 * int(row["mtl_count"]) for row in rows]
    labels = [
        f"CPW={row['outer_total']}\nMTL={row['mtl_count']}\n"
        f"[{row['r_short']},{row['r_open']},{row['p_short']},{row['p_open']}]"
        for row in rows
    ]
    return values, labels


def style_axis(axis: plt.Axes, title: str) -> None:
    axis.set_title(title, loc="left", fontsize=12, fontweight="bold")
    axis.grid(True, which="both", color="#d9d9d9", linewidth=0.7, alpha=0.8)
    axis.spines[["top", "right"]].set_visible(False)


def render_values(
    output_path: Path,
    rows_by_axis: dict[str, list[dict[str, str]]],
    status: str,
) -> None:
    figure, axes = plt.subplots(4, 1, figsize=(10, 18), constrained_layout=True)
    for axis_name, axis in zip(AXES, axes, strict=True):
        rows = rows_by_axis[axis_name]
        style_axis(axis, AXIS_TITLES[axis_name])
        if not rows:
            axis.text(0.5, 0.5, "No evaluable points", ha="center", va="center")
            continue
        x, labels = x_values(axis_name, rows)
        if axis_name != "joint":
            axis.set_xscale("log", base=2)
        for quantity, color, label in QUANTITIES:
            y = [float(row[f"{quantity}_hz"]) / 1e9 for row in rows]
            axis.plot(x, y, "o-", color=color, label=label, linewidth=1.8, markersize=5)
        axis.set_xticks(x, labels)
        axis.tick_params(axis="x", labelsize=9)
        axis.set_ylabel("Extracted frequency (GHz)")
        axis.legend(ncols=3, loc="best")
        if axis_name in ("mtl_first", "mtl_recheck"):
            axis.set_xlabel("MTL-window section count")
        elif axis_name == "single_trace":
            axis.set_xlabel(
                "Total Single-Trace sections\n"
                "[readout short, readout open, filter short, filter open]"
            )
        else:
            axis.set_xlabel("Joint line-section count = Single-Trace total + 2 * MTL")
    figure.suptitle(
        "D3 Rev10 W7/S6 local distributed intrinsic-pair spatial convergence\n"
        f"Extracted values · status={status}",
        fontsize=14,
    )
    figure.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(figure)


def render_deltas(
    output_path: Path,
    rows_by_axis: dict[str, list[dict[str, str]]],
    status: str,
) -> None:
    floor = 1e-9
    figure, axes = plt.subplots(4, 1, figsize=(10, 18), constrained_layout=True)
    for axis_name, axis in zip(AXES, axes, strict=True):
        rows = rows_by_axis[axis_name]
        style_axis(axis, AXIS_TITLES[axis_name])
        if not rows:
            axis.text(0.5, 0.5, "No evaluable points", ha="center", va="center")
            continue
        x, labels = x_values(axis_name, rows)
        if axis_name != "joint":
            axis.set_xscale("log", base=2)
        axis.axhline(
            0.1,
            color="#666666",
            linestyle="--",
            linewidth=1.0,
            label=r"0.1% gate ($f_r$/$f_p$)",
        )
        axis.axhline(
            1.0,
            color="#111111",
            linestyle=":",
            linewidth=1.2,
            label=r"1% gate ($f_n$)",
        )
        for quantity, color, label in QUANTITIES:
            y = [max(float(row[f"delta_{quantity}_percent"]), floor) for row in rows]
            axis.plot(x, y, "o-", color=color, label=label, linewidth=1.8, markersize=5)
        axis.set_yscale("log")
        axis.set_xticks(x, labels)
        axis.tick_params(axis="x", labelsize=9)
        axis.set_ylabel("Change to retained fine reference (%)")
        axis.legend(ncols=3, loc="best", fontsize=8)
        if axis_name in ("mtl_first", "mtl_recheck"):
            axis.set_xlabel("MTL-window section count")
        elif axis_name == "single_trace":
            axis.set_xlabel(
                "Total Single-Trace sections\n"
                "[readout short, readout open, filter short, filter open]"
            )
        else:
            axis.set_xlabel("Joint line-section count = Single-Trace total + 2 * MTL")
    figure.suptitle(
        "D3 Rev10 W7/S6 local distributed intrinsic-pair spatial convergence\n"
        f"Grid-change Gate · status={status} · exact zero changes shown at 1e-9%",
        fontsize=14,
    )
    figure.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(figure)


def main() -> None:
    args = parse_args()
    evidence_directory = args.evidence_directory.resolve()
    receipt_path = evidence_directory / "spatial-discretization-evidence.v1.json"
    points_path = evidence_directory / "convergence-points.csv"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    rows = read_rows(points_path)
    status = receipt["experiment"]["status"]
    render_values(evidence_directory / "frequency-values.png", rows, status)
    render_deltas(evidence_directory / "delta-percent.png", rows, status)
    print(evidence_directory / "frequency-values.png")
    print(evidence_directory / "delta-percent.png")


if __name__ == "__main__":
    main()
