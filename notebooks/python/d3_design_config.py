from __future__ import annotations

import json
from pathlib import Path


CONFIG_JSON = (
    Path(__file__).resolve().parents[1]
    / "pluto"
    / "D3 Intrinsic Purcell Filter Design"
    / "d3_design_config.json"
)


def load_d3_design_config() -> dict[str, object]:
    return json.loads(CONFIG_JSON.read_text())


def variant_suffix(variant_id: str) -> str:
    return "" if variant_id == "baseline" else f"__{variant_id}"
