"""Run the thesis PF6FQ Q3D+JosephsonCircuits XY external-coupling workflow."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from rich.progress import (
    BarColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

STUDY_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from q3d_xy_external_coupling import (  # noqa: E402
    DEFAULT_L_JUN_NH_VALUES,
    DEFAULT_QUBITS,
    SweepProgressEvent,
    run_q3d_xy_simulation_sweep,
)


def parse_args() -> argparse.Namespace:
    """Parse notebook-compatible sweep controls."""
    parser = argparse.ArgumentParser(
        description="Run PF6FQ thesis Q3D+JC XY external-coupling simulation."
    )
    parser.add_argument("--smoke", action="store_true", help="Run only Q0, L_jun=24 nH.")
    parser.add_argument(
        "--qubits",
        default=",".join(DEFAULT_QUBITS),
        help="Comma-separated qubits for the simulation sweep.",
    )
    parser.add_argument(
        "--capacitance-qubits",
        default=",".join(DEFAULT_QUBITS),
        help="Comma-separated qubits included in the capacitance summary table.",
    )
    parser.add_argument(
        "--l-jun-nh",
        default=",".join(str(value) for value in DEFAULT_L_JUN_NH_VALUES),
        help="Comma-separated L_jun values in nH.",
    )
    parser.add_argument("--sweep-start-ghz", type=float, default=None)
    parser.add_argument("--sweep-stop-ghz", type=float, default=None)
    parser.add_argument("--sweep-step-ghz", type=float, default=None)
    parser.add_argument("--pump-freq-ghz", type=float, default=8.001)
    parser.add_argument("--source-current-amp", type=float, default=0.0)
    parser.add_argument("--n-modulation-harmonics", type=int, default=10)
    parser.add_argument("--n-pump-harmonics", type=int, default=20)
    parser.add_argument(
        "--raw-layout-dir",
        type=Path,
        default=REPO_ROOT / "data/raw/layout_simulation/PF6FQ",
    )
    parser.add_argument("--output-dir", type=Path, default=STUDY_DIR / "outputs")
    return parser.parse_args()


def main() -> None:
    """Run the workflow and persist thesis CSV artifacts."""
    args = parse_args()
    qubits = ["Q0"] if args.smoke else _parse_csv_strings(args.qubits)
    capacitance_qubits = _parse_csv_strings(args.capacitance_qubits)
    l_jun_nh_values = [24.0] if args.smoke else _parse_csv_floats(args.l_jun_nh)
    sweep_start_ghz = (
        args.sweep_start_ghz if args.sweep_start_ghz is not None else (3.0 if args.smoke else 1.0)
    )
    sweep_stop_ghz = (
        args.sweep_stop_ghz if args.sweep_stop_ghz is not None else (5.5 if args.smoke else 10.0)
    )
    sweep_step_ghz = (
        args.sweep_step_ghz if args.sweep_step_ghz is not None else (0.01 if args.smoke else 0.002)
    )

    raw_output_dir = args.output_dir / "raw"
    table_output_dir = args.output_dir / "tables"
    raw_output_dir.mkdir(parents=True, exist_ok=True)
    table_output_dir.mkdir(parents=True, exist_ok=True)

    print(
        "Running Q3D+JC sweep: "
        f"qubits={qubits}, L_jun={l_jun_nh_values}, "
        f"frequency={sweep_start_ghz:g}:{sweep_step_ghz:g}:{sweep_stop_ghz:g} GHz"
    )
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TextColumn("[dim]{task.fields[current]}"),
        TimeElapsedColumn(),
    ) as progress:
        task_id = progress.add_task(
            "Q3D+JC sweep",
            total=len(qubits) * len(l_jun_nh_values),
            current="starting",
        )

        def on_progress(event: SweepProgressEvent) -> None:
            progress.update(
                task_id,
                completed=event.completed_cases,
                description=f"[{event.case_index}/{event.case_total}] {event.stage}",
                current=event.message,
            )

        sweep = run_q3d_xy_simulation_sweep(
            raw_layout_dir=args.raw_layout_dir,
            qubits=qubits,
            l_jun_nh_values=l_jun_nh_values,
            sweep_start_ghz=sweep_start_ghz,
            sweep_stop_ghz=sweep_stop_ghz,
            sweep_step_ghz=sweep_step_ghz,
            capacitance_summary_qubits=capacitance_qubits,
            repo_root=REPO_ROOT,
            pump_freq_ghz=args.pump_freq_ghz,
            source_current_amp=args.source_current_amp,
            n_modulation_harmonics=args.n_modulation_harmonics,
            n_pump_harmonics=args.n_pump_harmonics,
            progress=on_progress,
        )

    cap_df = pd.DataFrame(sweep.capacitance_rows)
    observables_df = pd.DataFrame(sweep.observable_rows)
    traces_df = pd.DataFrame(sweep.trace_rows)

    _write_csv(cap_df, raw_output_dir / "q3d_capacitance_parameters.csv")
    _write_csv(cap_df, table_output_dir / "thesis_q3d_capacitance_summary.csv")
    _write_csv(observables_df, raw_output_dir / "q3d_jc_xy_reduced_observables.csv")
    _write_csv(traces_df, raw_output_dir / "q3d_jc_xy_reduced_y_traces.csv")

    comparison = _build_hfss_comparison(
        selected_path=raw_output_dir / "selected_qubit_resonances.csv",
        observables_df=observables_df,
    )
    if comparison is not None:
        _write_csv(
            comparison,
            table_output_dir / "thesis_q3d_vs_hfss_frequency_comparison.csv",
        )


def _parse_csv_strings(value: str) -> list[str]:
    values = [part.strip() for part in str(value).split(",") if part.strip()]
    if not values:
        raise ValueError("Expected at least one comma-separated value.")
    return values


def _parse_csv_floats(value: str) -> list[float]:
    return [float(part) for part in _parse_csv_strings(value)]


def _write_csv(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False)
    print(f"Wrote {_display_path(path)}")


def _display_path(path: Path) -> Path:
    try:
        return path.relative_to(REPO_ROOT)
    except ValueError:
        return path


def _build_hfss_comparison(
    *,
    selected_path: Path,
    observables_df: pd.DataFrame,
) -> pd.DataFrame | None:
    if not selected_path.exists():
        print(f"Skipped HFSS comparison because {_display_path(selected_path)} is missing.")
        return None

    selected_df = pd.read_csv(selected_path)
    selected_xy = selected_df[selected_df["condition"] == "XY"].copy()
    if selected_xy.empty or observables_df.empty:
        return None

    comparison = selected_xy.merge(
        observables_df,
        left_on=["qubit", "L_jun_nH"],
        right_on=["qubit", "l_jun_nh"],
        how="inner",
        suffixes=("_hfss", "_q3d_jc"),
    )
    if comparison.empty:
        return None
    comparison["delta_frequency_mhz"] = (
        comparison["frequency_ghz_q3d_jc"] - comparison["frequency_ghz_hfss"]
    ) * 1000.0
    return comparison


if __name__ == "__main__":
    main()
