#!/usr/bin/env python3
from __future__ import annotations

import argparse
import difflib
import importlib.util
import re
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any

import matplotlib
import yaml

matplotlib.use("Agg")

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
CIRCUIT_DRAW_DIR = ROOT / "docs" / "assets" / "circuit_draw"
REGISTRY_PATH = CIRCUIT_DRAW_DIR / "registry.yml"
THEMES = ("light", "dark")
FORMATS = ("svg", "png")


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path.relative_to(ROOT)} must contain a YAML mapping.")
    return data


def _registry_entries() -> list[dict[str, str]]:
    registry = _load_yaml(REGISTRY_PATH)
    diagrams = registry.get("diagrams")
    if not isinstance(diagrams, list):
        raise ValueError("docs/assets/circuit_draw/registry.yml must contain diagrams list.")
    entries: list[dict[str, str]] = []
    for item in diagrams:
        if not isinstance(item, dict):
            raise ValueError("Each registry diagram entry must be a mapping.")
        diagram_id = item.get("diagram_id")
        manifest = item.get("manifest")
        if not isinstance(diagram_id, str) or not isinstance(manifest, str):
            raise ValueError("Each registry entry needs diagram_id and manifest strings.")
        entries.append({"diagram_id": diagram_id, "manifest": manifest})
    return entries


def _load_module(source_path: Path, diagram_id: str) -> ModuleType:
    module_name = "circuit_draw_" + "".join(
        character if character.isalnum() else "_" for character in diagram_id
    )
    spec = importlib.util.spec_from_file_location(module_name, source_path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot load {source_path.relative_to(ROOT)}.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _manifest_outputs(manifest: dict[str, Any]) -> dict[str, dict[str, str]]:
    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict):
        raise ValueError("Diagram manifest needs outputs mapping.")
    output_paths: dict[str, dict[str, str]] = {}
    for theme in THEMES:
        theme_outputs = outputs.get(theme)
        if not isinstance(theme_outputs, dict):
            raise ValueError(f"Diagram manifest needs outputs.{theme} mapping.")
        output_paths[theme] = {}
        for output_format in FORMATS:
            output_path = theme_outputs.get(output_format)
            if not isinstance(output_path, str):
                raise ValueError(
                    f"Diagram manifest needs outputs.{theme}.{output_format} string."
                )
            output_paths[theme][output_format] = output_path
    return output_paths


def _render_manifest(manifest: dict[str, Any], output_path: Path, *, theme: str) -> None:
    diagram_id = manifest.get("diagram_id")
    source_path_value = manifest.get("source_path")
    if not isinstance(diagram_id, str) or not isinstance(source_path_value, str):
        raise ValueError("Diagram manifest needs diagram_id and source_path strings.")

    source_path = ROOT / source_path_value
    module = _load_module(source_path, diagram_id)
    build_drawing = getattr(module, "build_drawing", None)
    if not callable(build_drawing):
        raise ValueError(f"{source_path.relative_to(ROOT)} must define build_drawing().")

    drawing = build_drawing(theme=theme)
    save = getattr(drawing, "save", None)
    if not callable(save):
        source = source_path.relative_to(ROOT)
        raise ValueError(f"{source} build_drawing() did not return a drawing.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if output_path.suffix == ".png":
            save(str(output_path), transparent=True, dpi=384)
        else:
            save(str(output_path), transparent=True)
            _normalize_svg_file(output_path)
    finally:
        from matplotlib import pyplot as plt

        plt.close("all")


def _normalize_svg_file(path: Path) -> None:
    normalized_lines = _normalize_svg(path.read_text(encoding="utf-8"))
    path.write_text("\n".join(normalized_lines) + "\n", encoding="utf-8")


def _normalize_svg(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n")
    normalized = re.sub(
        r"<dc:date>.*?</dc:date>",
        "<dc:date>normalized</dc:date>",
        normalized,
    )
    normalized = re.sub(r"p[0-9a-f]{10,}", "pNORMALIZED", normalized)
    return [line.rstrip() for line in normalized.splitlines()]


def _check_svg_output(expected_path: Path, rendered_path: Path) -> str | None:
    expected = _normalize_svg(expected_path.read_text(encoding="utf-8"))
    rendered = _normalize_svg(rendered_path.read_text(encoding="utf-8"))
    if expected == rendered:
        return None

    diff = "\n".join(
        difflib.unified_diff(
            expected,
            rendered,
            fromfile=str(expected_path.relative_to(ROOT)),
            tofile="rendered",
            lineterm="",
        )
    )
    return f"Rendered SVG differs for {expected_path.relative_to(ROOT)}:\n{diff}"


def _check_binary_output(expected_path: Path, rendered_path: Path) -> str | None:
    if expected_path.read_bytes() == rendered_path.read_bytes():
        return None
    file_type = expected_path.suffix[1:].upper()
    return f"Rendered {file_type} differs for {expected_path.relative_to(ROOT)}."


def _check_output(expected_path: Path, rendered_path: Path) -> str | None:
    if not expected_path.exists():
        return f"Missing committed output: {expected_path.relative_to(ROOT)}"
    if expected_path.suffix == ".svg":
        return _check_svg_output(expected_path, rendered_path)
    return _check_binary_output(expected_path, rendered_path)


def _selected_entries(diagram_ids: set[str] | None) -> list[dict[str, str]]:
    entries = _registry_entries()
    if diagram_ids is None:
        return entries
    selected = [entry for entry in entries if entry["diagram_id"] in diagram_ids]
    missing = diagram_ids.difference({entry["diagram_id"] for entry in selected})
    if missing:
        raise ValueError(f"Unknown diagram id(s): {', '.join(sorted(missing))}")
    return selected


def run(*, check: bool, diagram_ids: set[str] | None) -> int:
    if str(CIRCUIT_DRAW_DIR) not in sys.path:
        sys.path.insert(0, str(CIRCUIT_DRAW_DIR))

    failures: list[str] = []
    entries = _selected_entries(diagram_ids)

    with tempfile.TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        for entry in entries:
            manifest_path = ROOT / entry["manifest"]
            manifest = _load_yaml(manifest_path)
            try:
                output_paths = _manifest_outputs(manifest)
            except ValueError as exc:
                failures.append(f"{entry['manifest']}: {exc}")
                continue

            for theme, theme_outputs in output_paths.items():
                for output_format, output_path_value in theme_outputs.items():
                    output_path = ROOT / output_path_value
                    if check:
                        render_target = (
                            temp_dir
                            / entry["diagram_id"]
                            / f"diagram.{theme}.{output_format}"
                        )
                    else:
                        render_target = output_path

                    try:
                        _render_manifest(manifest, render_target, theme=theme)
                    except Exception as exc:
                        output_name = f"{theme}/{output_format}"
                        failures.append(f"{entry['diagram_id']} ({output_name}): {exc}")
                        continue

                    if check:
                        diff = _check_output(output_path, render_target)
                        if diff is not None:
                            failures.append(diff)
                    else:
                        print(f"wrote {output_path.relative_to(ROOT)}")

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Render Schemdraw docs corpus files.")
    parser.add_argument("--check", action="store_true", help="Render to a temp dir and compare.")
    parser.add_argument(
        "--diagram",
        action="append",
        dest="diagrams",
        help="Render one diagram id. Can be passed more than once.",
    )
    args = parser.parse_args()
    return run(check=bool(args.check), diagram_ids=set(args.diagrams) if args.diagrams else None)


if __name__ == "__main__":
    raise SystemExit(main())
