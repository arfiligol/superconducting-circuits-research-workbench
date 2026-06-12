#!/usr/bin/env python3
from __future__ import annotations

import ast
import os
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
CIRCUIT_DRAW_DIR = ROOT / "docs" / "assets" / "circuit_draw"
REGISTRY_PATH = CIRCUIT_DRAW_DIR / "registry.yml"
LEGACY_SCRIPT_DIR = ROOT / "scripts" / "docs"
THEMES = ("light", "dark")
FORMATS = ("svg", "png")

FORBIDDEN_IMPORT_ROOTS = {
    "app_backend",
    "core",
    "julia",
    "juliacall",
    "JuliaCall",
    "sc_core",
}


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path.relative_to(ROOT)} must contain a YAML mapping.")
    return data


def _as_string_list(value: object, field_name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field_name} must be a list of strings.")
    return value


def _frontmatter_status(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    frontmatter = yaml.safe_load(text[4:end]) or {}
    if not isinstance(frontmatter, dict):
        return None
    status = frontmatter.get("status")
    return status if isinstance(status, str) else None


def _docs_route_relative_link(from_doc: Path, to_asset: Path) -> str:
    doc_relative = from_doc.relative_to(ROOT / "docs")
    if from_doc.name in {"index.md", "index.mdx"}:
        doc_route_dir = Path("docs") / doc_relative.parent
    else:
        doc_route_dir = Path("docs") / doc_relative.with_suffix("")

    asset_route = to_asset.relative_to(ROOT)
    return os.path.relpath(asset_route, doc_route_dir).replace(os.sep, "/")


def _source_relative_link(from_doc: Path, to_asset: Path) -> str:
    return os.path.relpath(to_asset, from_doc.parent).replace(os.sep, "/")


def _check_draw_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    failures: list[str] = []
    uses_circuit_drawing = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", maxsplit=1)[0]
                if root in FORBIDDEN_IMPORT_ROOTS:
                    failures.append(
                        f"{path.relative_to(ROOT)} imports forbidden module {alias.name}."
                    )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".", maxsplit=1)[0]
            if root in FORBIDDEN_IMPORT_ROOTS:
                failures.append(f"{path.relative_to(ROOT)} imports forbidden module {module}.")
        elif isinstance(node, ast.Call):
            call_name = ""
            if isinstance(node.func, ast.Name):
                call_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                call_name = node.func.attr
            if call_name == "circuit_drawing":
                uses_circuit_drawing = True
            if call_name in {"push", "pop"}:
                failures.append(
                    f"{path.relative_to(ROOT)} uses {call_name}(); use drawing.hold()."
                )
        elif isinstance(node, ast.AugAssign) and isinstance(node.op, ast.Add):
            failures.append(
                f"{path.relative_to(ROOT)} uses += element placement; use the "
                "circuit_drawing context-manager style."
            )
    if not uses_circuit_drawing:
        failures.append(
            f"{path.relative_to(ROOT)} must use the shared circuit_drawing() context manager."
        )
    return failures


def _check_existing_paths(paths: list[str], field_name: str) -> list[str]:
    failures: list[str] = []
    for path_value in paths:
        path = ROOT / path_value
        if not path.exists():
            failures.append(f"{field_name} path does not exist: {path_value}")
    return failures


def _manifest_outputs(
    manifest: dict[str, Any],
    manifest_rel: Path,
) -> tuple[dict[str, dict[str, str]], list[str]]:
    failures: list[str] = []
    if "output_path" in manifest:
        failures.append(
            f"{manifest_rel} must use outputs.light.svg/png and outputs.dark.svg/png, "
            "not output_path."
        )

    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict):
        return {}, [*failures, f"{manifest_rel} needs outputs mapping."]

    output_paths: dict[str, dict[str, str]] = {}
    for theme in THEMES:
        theme_outputs = outputs.get(theme)
        if not isinstance(theme_outputs, dict):
            failures.append(f"{manifest_rel} needs outputs.{theme} mapping.")
            continue
        output_paths[theme] = {}
        for output_format in FORMATS:
            output_path = theme_outputs.get(output_format)
            if not isinstance(output_path, str):
                failures.append(
                    f"{manifest_rel} needs outputs.{theme}.{output_format} string."
                )
                continue
            output_paths[theme][output_format] = output_path
    return output_paths, failures


def _check_manifest(manifest_path: Path, expected_diagram_id: str) -> list[str]:
    failures: list[str] = []
    manifest_rel = manifest_path.relative_to(ROOT)
    manifest = _load_yaml(manifest_path)

    diagram_id = manifest.get("diagram_id")
    if diagram_id != expected_diagram_id:
        failures.append(f"{manifest_rel} diagram_id {diagram_id!r} does not match registry.")

    source_path_value = manifest.get("source_path")
    if not isinstance(source_path_value, str):
        failures.append(f"{manifest_rel} needs source_path string.")
        source_path_value = ""

    source_path = ROOT / source_path_value
    if source_path_value and not source_path.exists():
        failures.append(f"source_path does not exist: {source_path_value}")

    output_path_values, output_failures = _manifest_outputs(manifest, manifest_rel)
    failures.extend(output_failures)
    output_paths: dict[str, dict[str, Path]] = {}
    for theme, theme_output_values in output_path_values.items():
        output_paths[theme] = {}
        for output_format, output_path_value in theme_output_values.items():
            output_path = ROOT / output_path_value
            output_paths[theme][output_format] = output_path
            if not output_path.exists():
                failures.append(
                    f"outputs.{theme}.{output_format} path does not exist: "
                    f"{output_path_value}"
                )
            expected_name = f"diagram.{theme}.{output_format}"
            if output_path.name != expected_name:
                failures.append(f"{output_path_value} must be named {expected_name}.")
            if CIRCUIT_DRAW_DIR not in output_path.parents:
                failures.append(
                    f"{output_path_value} must live under docs/assets/circuit_draw."
                )

    if source_path.exists():
        failures.extend(_check_draw_imports(source_path))

    try:
        owning_docs = _as_string_list(manifest.get("owning_docs"), "owning_docs")
        physical_model_refs = _as_string_list(
            manifest.get("physical_model_refs"), "physical_model_refs"
        )
        implementation_refs = _as_string_list(
            manifest.get("implementation_refs"), "implementation_refs"
        )
    except ValueError as exc:
        failures.append(f"{manifest_rel}: {exc}")
        owning_docs = []
        physical_model_refs = []
        implementation_refs = []

    semantics = manifest.get("julia_core_semantics")
    if not isinstance(semantics, dict):
        failures.append(f"{manifest_rel} needs julia_core_semantics mapping.")
        semantics_docs: list[str] = []
        semantics_sources: list[str] = []
    else:
        try:
            semantics_docs = _as_string_list(semantics.get("docs"), "julia_core_semantics.docs")
            semantics_sources = _as_string_list(
                semantics.get("source_refs"), "julia_core_semantics.source_refs"
            )
        except ValueError as exc:
            failures.append(f"{manifest_rel}: {exc}")
            semantics_docs = []
            semantics_sources = []

    failures.extend(_check_existing_paths(owning_docs, "owning_docs"))
    failures.extend(_check_existing_paths(physical_model_refs, "physical_model_refs"))
    failures.extend(_check_existing_paths(implementation_refs, "implementation_refs"))
    failures.extend(_check_existing_paths(semantics_docs, "julia_core_semantics.docs"))
    failures.extend(_check_existing_paths(semantics_sources, "julia_core_semantics.source_refs"))

    review = manifest.get("review")
    if not isinstance(review, dict):
        failures.append(f"{manifest_rel} needs review mapping.")
        status = None
    else:
        status = review.get("status")
        if status not in {"draft", "accepted"}:
            failures.append(f"{manifest_rel} review.status must be draft/accepted.")
        if status == "accepted":
            if not isinstance(review.get("verified_by"), str):
                failures.append(f"{manifest_rel} accepted review needs verified_by.")
            if not isinstance(review.get("verified_at"), str):
                failures.append(f"{manifest_rel} accepted review needs verified_at.")

    for owner in owning_docs:
        owner_path = ROOT / owner
        if not owner_path.exists() or owner_path.suffix not in {".md", ".mdx"}:
            continue
        owner_status = _frontmatter_status(owner_path)
        if owner_status == "stable" and status != "accepted":
            failures.append(
                f"{owner} is stable but references non-accepted diagram {expected_diagram_id}."
            )
        svg_output_paths = {
            theme: theme_outputs["svg"]
            for theme, theme_outputs in output_paths.items()
            if "svg" in theme_outputs
        }
        for theme, output_path in svg_output_paths.items():
            expected_links = {
                _source_relative_link(owner_path, output_path),
                _docs_route_relative_link(owner_path, output_path),
            }
            text = owner_path.read_text(encoding="utf-8")
            if not any(expected_link in text for expected_link in expected_links):
                expected = " or ".join(sorted(expected_links))
                failures.append(
                    f"{owner} does not reference expected {theme} diagram output {expected}."
                )

    return failures


def run() -> int:
    failures: list[str] = []

    if LEGACY_SCRIPT_DIR.exists():
        failures.append("scripts/docs must not exist; use scripts/build or scripts/test helpers.")

    registry = _load_yaml(REGISTRY_PATH)
    diagrams = registry.get("diagrams")
    if not isinstance(diagrams, list):
        failures.append("registry.yml must contain diagrams list.")
        diagrams = []

    seen_ids: set[str] = set()
    for item in diagrams:
        if not isinstance(item, dict):
            failures.append("Each registry diagram entry must be a mapping.")
            continue
        diagram_id = item.get("diagram_id")
        manifest = item.get("manifest")
        if not isinstance(diagram_id, str) or not isinstance(manifest, str):
            failures.append("Each registry entry needs diagram_id and manifest strings.")
            continue
        if diagram_id in seen_ids:
            failures.append(f"Duplicate diagram id in registry: {diagram_id}")
            continue
        seen_ids.add(diagram_id)
        manifest_path = ROOT / manifest
        if not manifest_path.exists():
            failures.append(f"Manifest does not exist: {manifest}")
            continue
        failures.extend(_check_manifest(manifest_path, diagram_id))

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    print(f"checked {len(seen_ids)} circuit drawing manifests")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
