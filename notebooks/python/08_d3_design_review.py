# ---
# jupyter:
#   jupytext:
#     cell_metadata_filter: -all
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.4
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# # 08 D3 Design Review
#
# ## Goal and tl;dr
#
# This is the reader-facing Human review surface for one persisted D3 intrinsic
# interferometric Purcell-filter optimization run and, when available, one
# independent exact-six nominal validation. It explains how the optimizer froze
# the final Layout Specs, then keeps optimizer-time reproduction distinct from
# Final Validation. Opening and running the notebook is read-only by default.
#
# The final Layout Specs are deliberately last. Every preceding table and figure
# exists to explain their physical characteristics, fit quality, provenance, and
# limitations. A good numerical candidate remains unapproved exploration until a
# Human accepts the evidence.
#
# Canonical semantics:
#
# - [D3 Design Target](https://github.com/arfiligol/SCQ_Design/blob/main/docs/design-targets/d3-intrinsic-interferometric-purcell-filter.qmd)
# - [Loaded-Bare References](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/readout/loaded-bare-readout-filter-references.qmd)
# - [Readout-Filter Complex-S21 J Fit](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/readout/readout-filter-s21-j-fit.qmd)
# - [Bare vs Hybridized Readout / Filter Modes](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/readout/bare-vs-hybridized-readout-filter-modes.qmd)
# - [Port-Termination Compensation](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/simulation/port-termination-compensation.qmd)
# - [Auditable Scientific Optimization](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/numerical-methods/auditable-scientific-optimization.qmd)

# %% [markdown]
# ## Inputs and provenance
#
# Edit the Design Target and optimizer paths to review another result. An
# explicit nominal directory is optional; leave it `None` for discovery. The
# guarded run flag is `False` by default and never invokes the optimizer.

# %%
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import subprocess
from collections import Counter
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from IPython.display import Image, Markdown, display


def find_repo_root(start: Path) -> Path:
    """Find this Workbench checkout without relying on shell environment state."""
    for candidate in (start, *start.parents):
        if (candidate / "notebooks/python").is_dir() and (
            candidate / "scripts/build/plot_d3_final_diagnostics.py"
        ).is_file():
            return candidate
    raise FileNotFoundError("Open this notebook from inside the Circuit Workbench checkout.")


REPO_ROOT = find_repo_root(Path.cwd().resolve())
WORKSPACE_ROOT = REPO_ROOT.parent

DESIGN_TARGET_JSON = WORKSPACE_ROOT / (
    "docs/design-targets/contracts/d3-intrinsic-interferometric-purcell-filter.v1.json"
)
OPTIMIZER_RUN_DIRECTORY = REPO_ROOT / (
    "build/research/d3_coupled_optimizer_v1/"
    "20260710T213955009Z__d3-coupled-optimization-6ghz-design-target-v1__0c16418e6d15"
)
NOMINAL_VALIDATION_DIRECTORY: Path | None = None
RUN_NOMINAL_VALIDATION = False

NOMINAL_OUTPUT_ROOT = REPO_ROOT / "build/research/d3_nominal_validation_v1"
NOMINAL_VALIDATION_RUNNER = REPO_ROOT / "scripts/build/run_d3_nominal_validation.jl"

# %%
VALIDATOR_PATH = REPO_ROOT / "scripts/build/plot_d3_final_diagnostics.py"
validator_spec = importlib.util.spec_from_file_location("d3_artifact_validator", VALIDATOR_PATH)
if validator_spec is None or validator_spec.loader is None:
    raise ImportError(f"Could not load D3 artifact validator: {VALIDATOR_PATH}")
validator = importlib.util.module_from_spec(validator_spec)
validator_spec.loader.exec_module(validator)

# %% [markdown]
# ### Explicit nominal-validation action (guarded)
#
# This is the notebook's only write-capable cell. It calls the nominal runner in
# a fresh Julia process only when `RUN_NOMINAL_VALIDATION=True`. It cannot run
# CMA-ES or Nelder–Mead. Selection is cleared before the request, so a failed
# process can never leave an older validation selected.

# %%
selected_nominal_validation: dict[str, Any] | None = None
selected_nominal_directory: Path | None = None
if RUN_NOMINAL_VALIDATION:
    selected_nominal_validation = None
    selected_nominal_directory = None
    NOMINAL_VALIDATION_DIRECTORY = None
    subprocess.run(
        [
            "julia",
            "--startup-file=no",
            str(NOMINAL_VALIDATION_RUNNER),
            str(OPTIMIZER_RUN_DIRECTORY),
        ],
        check=True,
        shell=False,
        cwd=REPO_ROOT,
    )

# %%


def read_json(path: Path) -> dict[str, Any]:
    """Read one finite JSON object and make malformed evidence fail fast."""

    def reject_constant(value: str) -> None:
        raise ValueError(f"{path.name} contains non-finite JSON constant {value!r}.")

    value = json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=reject_constant,
        parse_float=validator.json3_any_float,
    )
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain one JSON object.")
    return value


optimizer_validated = validator.validate_artifacts(OPTIMIZER_RUN_DIRECTORY)
target_contract = read_json(DESIGN_TARGET_JSON)
run_manifest = read_json(OPTIMIZER_RUN_DIRECTORY / "condition_manifest.json")
design_config = read_json(
    REPO_ROOT / "notebooks/pluto/D3 Intrinsic Purcell Filter Design/d3_design_config.json"
)
optimizer_conditions = read_json(
    REPO_ROOT / "notebooks/pluto/D3 Intrinsic Purcell Filter Design/d3_optimizer_conditions.json"
)
target_binding = design_config["target_contract"]
target_sha256 = hashlib.sha256(DESIGN_TARGET_JSON.read_bytes()).hexdigest()
expected_target_path = WORKSPACE_ROOT / target_binding["workspace_relative_path"]
if DESIGN_TARGET_JSON.resolve() != expected_target_path.resolve():
    raise ValueError("DESIGN_TARGET_JSON does not match d3_design_config.json target_contract path.")
if target_sha256 != target_binding["expected_sha256"]:
    raise ValueError("DESIGN_TARGET_JSON SHA-256 does not match d3_design_config.json.")
if (
    target_contract["target_id"] != target_binding["expected_target_id"]
    or target_contract["revision"] != target_binding["expected_revision"]
):
    raise ValueError("DESIGN_TARGET_JSON identity or revision does not match d3_design_config.json.")

artifacts = {
    name: read_json(OPTIMIZER_RUN_DIRECTORY / name)
    for name in validator.EXPECTED_RUN_FILES
    if name.endswith(".json")
}
optimizer_reproduction_record = artifacts["final_diagnostics.json"]["record"]
layout_specs = artifacts["layout_specs.json"]
optimization = artifacts["optimization_result.json"]
contract = run_manifest["contract"]
review_contract = validator.normalize_review_contract(
    run_manifest,
    artifacts["config_snapshot.json"],
    target_contract,
    target_sha256,
    optimizer_conditions,
)
selected_case_id = review_contract["selected_case_id"]
selected_slot_ghz = review_contract["selected_slot_ghz"]
source_row = review_contract["source_row"]
metric_specs = review_contract["metric_specs"]
optimizer_metric_fields = review_contract["optimizer_metric_fields"]
variable_spec_records = review_contract["variable_specs"]
feedline = review_contract["feedline"]

if NOMINAL_VALIDATION_DIRECTORY is not None:
    selected_nominal_directory = Path(NOMINAL_VALIDATION_DIRECTORY).expanduser().resolve(strict=True)
    selected_nominal_validation = validator.validate_nominal_artifacts(
        selected_nominal_directory,
        OPTIMIZER_RUN_DIRECTORY,
        WORKSPACE_ROOT,
    )
    nominal_discovery = {
        "valid": [(selected_nominal_directory, selected_nominal_validation)],
        "rejected": [],
        "unrelated": [],
    }
else:
    nominal_discovery = validator.discover_nominal_validations(
        NOMINAL_OUTPUT_ROOT,
        OPTIMIZER_RUN_DIRECTORY,
        WORKSPACE_ROOT,
    )
    valid_nominal_matches = nominal_discovery["valid"]
    if len(valid_nominal_matches) == 1:
        selected_nominal_directory, selected_nominal_validation = valid_nominal_matches[0]
    elif len(valid_nominal_matches) > 1:
        matching_directories = "\n".join(f"- {path}" for path, _ in valid_nominal_matches)
        raise validator.ArtifactContractError(
            "Multiple valid nominal validations match this optimizer candidate. "
            "Set NOMINAL_VALIDATION_DIRECTORY explicitly:\n" + matching_directories
        )

if selected_nominal_validation is None:
    evidence_record = optimizer_reproduction_record
    validation_state = "not_performed"
    evidence_heading = "Historical optimizer-time reproduction"
    evidence_caveat = (
        "Independent nominal validation: not performed. The persisted optimizer-time "
        "reproduction is narrow, unapproved_exploration evidence only."
    )
else:
    evidence_record = selected_nominal_validation["record"]
    validation_state = "completed"
    evidence_heading = "Final Validation — independent nominal reproduction"
    evidence_caveat = (
        "Independent nominal validation completed once in a fresh evaluator; Human acceptance "
        "and tolerance acceptance remain separate decisions."
    )
diagnostics = evidence_record["diagnostics"]
traces = evidence_record["traces"]


def inventory_source_path(item: dict[str, Any]) -> Path:
    path = Path(item["path"])
    return path if path.is_absolute() else WORKSPACE_ROOT / path

# Historical evidence is bound to hashes observed at run time. Current source
# drift is expected after refactoring, so it is visible but never rewrites history.
hash_rows = []
for item in artifacts["hash_inventory.json"]["files"]:
    source_path = inventory_source_path(item)
    hash_rows.append(
        {
            "input": item["id"],
            "current file exists": source_path.is_file(),
            "expected SHA-256": item["expected_sha256"],
            "observed at run": item["observed_sha256"],
            "matched at run": item["observed_sha256"] == item["expected_sha256"],
        }
    )
journal_records = [
    json.loads(line)
    for line in (OPTIMIZER_RUN_DIRECTORY / "evaluations.jsonl").read_text(encoding="utf-8").splitlines()
    if line.strip()
]
if not journal_records or not all(isinstance(record, dict) for record in journal_records):
    raise ValueError("evaluations.jsonl must contain JSON objects.")

# The OrPen payload may be interpreted only while its current bytes still match
# the run-bound identity. Otherwise the notebook reports its quantities unavailable.
orpen_inventory = next(
    item
    for item in artifacts["hash_inventory.json"]["files"]
    if item["id"] == "orpen_case_json"
)
orpen_path = inventory_source_path(orpen_inventory)
orpen_hash_matches = (
    orpen_path.is_file()
    and hashlib.sha256(orpen_path.read_bytes()).hexdigest() == orpen_inventory["expected_sha256"]
)
orpen_case = None
if orpen_hash_matches:
    orpen_payload = read_json(orpen_path)
    matching_cases = [
        case
        for case in orpen_payload["cases"]
        if case.get("id") == selected_case_id
    ]
    if len(matching_cases) != 1:
        raise ValueError("Hash-bound OrPen payload must contain exactly one selected case.")
    orpen_case = matching_cases[0]

# %%
provenance_table = pd.DataFrame(
    [
        ("Design Target", DESIGN_TARGET_JSON.relative_to(WORKSPACE_ROOT), target_contract["title"]),
        ("Target identity", target_contract["target_id"], f"revision {target_contract['revision']}"),
        ("Target SHA-256", target_sha256, "matches current Workbench binding"),
        ("Optimizer run", OPTIMIZER_RUN_DIRECTORY.relative_to(REPO_ROOT), artifacts["status.json"]["state"]),
        ("Run manifest", contract["manifest_id"], f"{optimizer_validated['artifact_hash_label']} {optimizer_validated['artifact_hash']}"),
        (
            "Independent nominal validation",
            selected_nominal_directory.relative_to(REPO_ROOT) if selected_nominal_directory else "not performed",
            validation_state,
        ),
        ("Rejected nominal directories", len(nominal_discovery["rejected"]), "never used as Final Validation"),
        ("Unrelated nominal directories", len(nominal_discovery["unrelated"]), "other source runs / Slots; ignored"),
        ("Sol review", review_contract["sol_review"].get("reviewer_identity"), review_contract["sol_review"]["status"]),
        ("Human review", review_contract["human_review"].get("reviewer_identity"), review_contract["human_review"]["status"]),
        ("Artifact approval", layout_specs["artifact_approval"], layout_specs["review_state"]),
        ("Evidence files", len(validator.EXPECTED_RUN_FILES), "exact-eight contract passed"),
        ("Journal evaluations", len(journal_records), "read-only; includes final reproduction"),
    ],
    columns=["Item", "Identity / value", "State"],
)
display(provenance_table.style.hide(axis="index"))

# %% [markdown]
# The short hashes below are the run-time identities. `current file exists` is
# informational only: source code may legitimately move after an immutable run.

# %%
hash_table = pd.DataFrame(hash_rows).assign(
    **{
        "expected SHA-256": lambda frame: frame["expected SHA-256"].str.slice(0, 12),
        "observed at run": lambda frame: frame["observed at run"].str.slice(0, 12),
    }
)
display(hash_table.style.hide(axis="index"))

# %% [markdown]
# ## Target Design
#
# The target table below comes from `DESIGN_TARGET_JSON`, not from handwritten
# notebook constants. The current slot-specific frequencies are resolved from the
# selected slot and the target's loaded-bare offsets.

# %%
def display_frequency(value_hz: float, metric_id: str) -> tuple[float, str]:
    if metric_id in {"filter_loaded_bare_hz", "readout_loaded_bare_hz", "notch_hz"}:
        return value_hz / 1e9, "GHz"
    return value_hz / 1e6, "MHz"


targets = target_contract["targets"]
target_rows = []
for parameter_id, target in targets.items():
    value = target.get("value", target.get("values"))
    if parameter_id == "filter_loaded_bare_offset":
        resolved = selected_slot_ghz + float(value) / 1e3
    elif parameter_id == "readout_loaded_bare_offset":
        resolved = selected_slot_ghz + float(value) / 1e3
    else:
        resolved = None
    target_rows.append(
        {
            "Parameter": parameter_id,
            "Target": value,
            "Unit": target["unit"],
            "Selected slot resolved target": resolved,
            "Resolved unit": "GHz" if resolved is not None else None,
            "Decision state": target["status"],
            "Source": target["source"],
        }
    )
target_table = pd.DataFrame(target_rows)
display(
    target_table.style.hide(axis="index").format(
        {
            "Selected slot resolved target": lambda value: "—" if pd.isna(value) else f"{value:.6f}",
        }
    )
)

# %%
qubit_inventory = next(
    (
        item
        for item in artifacts["hash_inventory.json"]["files"]
        if item["id"] == "floating_qubit_nominal"
    ),
    None,
)
if qubit_inventory is None:
    display(Markdown("> **Fixed nominal floating qubit:** unavailable in this historical run."))
else:
    qubit_path = inventory_source_path(qubit_inventory)
    if not qubit_path.is_file() or hashlib.sha256(qubit_path.read_bytes()).hexdigest() != qubit_inventory["expected_sha256"]:
        raise ValueError("The hash-bound private floating-qubit input is missing or stale.")
    qubit_input = read_json(qubit_path)
    qubit_contract = contract["floating_qubit_nominal"]
    if qubit_contract.get("schema_version") == "d3-floating-qubit-maxwell.v1":
        branches = qubit_contract["mapped_branches_fF"]
        qubit_rows = [(name, branches[name], "fF") for name in ("C01_fF", "C02_fF", "C12_fF", "Cr1_fF", "Cr2_fF")]
        qubit_rows.append(("L_J_per_junction_nH", qubit_contract["L_J_per_junction_nH"], "nH"))
        partition = qubit_contract["partition"]
        display(
            pd.DataFrame(
                [
                    ("Reference", partition["reference_label"]),
                    ("Eliminated floating Coupler pads", partition["floating_labels"]),
                    ("Retained order", partition["retained_labels"]),
                    ("Readout self-capacitance owner", qubit_contract["readout_self_capacitance_ownership"]),
                    ("Readout diagonal instantiated", qubit_contract["readout_diagonal_instantiated"]),
                ],
                columns=["Kron reduction", "Value"],
            ).style.hide(axis="index")
        )
        display(
            pd.DataFrame(
                qubit_contract["reduced_maxwell_matrix_fF"],
                index=partition["retained_labels"],
                columns=partition["retained_labels"],
            ).style.format("{:.6f}").set_caption("Kron-reduced Maxwell matrix (fF)")
        )
        physics = qubit_contract["physics_diagnostics"]
        display(
            pd.DataFrame(
                [(name, value, "fF" if "capacitance" in name else "Hz") for name, value in physics.items()],
                columns=["Fixed-qubit diagnostic", "Value", "Unit"],
            ).style.hide(axis="index").format({"Value": "{:.6f}"})
        )
    else:
        qubit_rows = [
            (name, qubit_input[name], "nH" if name == "L_J_per_junction_nH" else "fF")
            for name in ("C01_fF", "C02_fF", "C12_fF", "Cr1_fF", "Cr2_fF", "L_J_per_junction_nH")
        ]
    display(
        pd.DataFrame(
            qubit_rows,
            columns=["Fixed qubit input", "Value", "Unit"],
        ).style.hide(axis="index").format({"Value": "{:.6f}"})
    )

# The immutable run must have used the same numerical Design Target.
expected_metric_targets = {
    "filter_loaded_bare_hz": (selected_slot_ghz + targets["filter_loaded_bare_offset"]["value"] / 1e3) * 1e9,
    "readout_loaded_bare_hz": (selected_slot_ghz + targets["readout_loaded_bare_offset"]["value"] / 1e3) * 1e9,
    "notch_hz": targets["interference_notch_frequency"]["value"] * 1e9,
    "filter_loaded_linewidth_hz": targets["filter_loaded_bare_linewidth"]["value"] * 1e6,
    "j_hz": targets["readout_filter_exchange_coupling"]["value"] * 1e6,
    "g_hz": targets["qubit_readout_coupling"]["value"] * 1e6,
    "readout_minus_filter_detuning_hz": targets["readout_minus_filter_detuning"]["value"] * 1e6,
}
run_metric_targets = {
    metric["name"]: float(metric["target"])
    for metric in layout_specs["breakdown"]["metrics"]
}
semantic_fingerprint_matches = (
    selected_case_id == target_contract["implementation_case"]["id"]
    and selected_slot_ghz in targets["slot_frequencies"]["values"]
    and run_metric_targets == expected_metric_targets
)
if not semantic_fingerprint_matches:
    raise ValueError("The selected run's metric targets disagree with DESIGN_TARGET_JSON.")

# The run snapshot supplies slot-resolved numerical scales and optimizer weights.
resolved_run_target_rows = []
for spec in metric_specs:
    value, unit = display_frequency(float(spec["value"]), spec["id"])
    scale, scale_unit = display_frequency(float(spec["scale"]), spec["id"])
    resolved_run_target_rows.append(
        {
            "Run metric": spec["id"],
            "Resolved target": value,
            "Unit": unit,
            "Residual scale": scale,
            "Scale unit": scale_unit,
            "Weight": spec["weight"],
            "Role": spec["role"],
        }
    )
resolved_run_target_table = pd.DataFrame(resolved_run_target_rows)
display(
    resolved_run_target_table.style.hide(axis="index").format(
        {"Resolved target": "{:.6f}", "Residual scale": "{:.6f}"}
    )
)

# %%
scope_table = pd.DataFrame(
    [
        ("Execution scope", review_contract["execution_scope"], "design scope"),
        ("Selected case", selected_case_id, "case id"),
        ("Current slot", selected_slot_ghz, "GHz"),
        ("Configured slots", targets["slot_frequencies"]["values"], "GHz"),
        ("Target notch", targets["interference_notch_frequency"]["value"], "GHz"),
        ("Feedline target impedance", feedline["target_impedance_ohm"], "ohm"),
        ("Feedline LC-derived impedance", feedline["extracted_lc_impedance_ohm"], "ohm"),
    ],
    columns=["Design condition", "Value", "Unit"],
)
display(scope_table.style.hide(axis="index"))

# %% [markdown]
# ## Seed to final Layout parameters
#
# These are the only six optimizer-controlled Layout variables. The seed is a
# geometry starting point; the final candidate is the best valid persisted
# record, not a claim of optimizer convergence.

# %%
variable_specs = {item["id"]: item for item in variable_spec_records}
final_variables = {item["id"]: item for item in layout_specs["variables"]}
parameter_rows = []
for parameter_id, spec in variable_specs.items():
    final_value = float(final_variables[parameter_id]["value"])
    seed_value = float(spec["value"])
    parameter_rows.append(
        {
            "Layout parameter": parameter_id,
            "Seed": seed_value,
            "Final": final_value,
            "Change": final_value - seed_value,
            "Lower bound": spec["lower_bound"],
            "Upper bound": spec["upper_bound"],
            "Unit": spec["unit"],
        }
    )
seed_to_final_table = pd.DataFrame(parameter_rows)
display(
    seed_to_final_table.style.hide(axis="index").format(
        {column: "{:.6f}" for column in ["Seed", "Final", "Change", "Lower bound", "Upper bound"]}
    )
)

# %% [markdown]
# ## Performance evidence
#
# The label below is part of the evidence contract. **Final Validation** appears
# only when the values come from `nominal_evaluation.record`; otherwise this is
# explicitly the historical optimizer-time reproduction.

# %%
display(Markdown(f"### {evidence_heading}\n\n{evidence_caveat}"))

evidence_kind = {
    "filter_loaded_bare_hz": "extracted",
    "readout_loaded_bare_hz": "fitted",
    "notch_hz": "extracted",
    "filter_loaded_linewidth_hz": "fitted",
    "j_hz": "fitted",
    "g_hz": "fitted",
    "readout_minus_filter_detuning_hz": "calculated",
}
performance_rows = []
for metric in layout_specs["breakdown"]["metrics"]:
    target_value, unit = display_frequency(float(metric["target"]), metric["name"])
    observed_hz = float(evidence_record["metrics"][metric["name"]])
    observed_value, _ = display_frequency(observed_hz, metric["name"])
    performance_rows.append(
        {
            "Parameter": metric["name"],
            "Evidence": evidence_kind[metric["name"]],
            "Target": target_value,
            "Observed": observed_value,
            "Error": observed_value - target_value,
            "Unit": unit,
            "Normalized residual": (observed_hz - float(metric["target"])) / float(metric["scale"]),
            "Evidence source": evidence_heading,
        }
    )
performance_table = pd.DataFrame(performance_rows)
display(
    performance_table.style.hide(axis="index").format(
        {
            "Target": "{:.6f}",
            "Observed": "{:.6f}",
            "Error": "{:+.6f}",
            "Normalized residual": "{:+.6f}",
        }
    )
)

# %% [markdown]
# ## Design-target physical parameters
#
# `Unavailable` is evidence, not an empty cell. In particular, this single-slot
# lossless exploration did not solve a qubit-state-dependent model and did not
# publish readout-like versus filter-like ownership for the two hybridized poles.

# %%
metrics = evidence_record["metrics"]
j_fit = diagnostics["j_fit"]
model_poles = sorted(j_fit["derived_poles"], key=lambda pole: pole["frequency_hz"])
hybrid_spacing_hz = model_poles[1]["frequency_hz"] - model_poles[0]["frequency_hz"]

physical_parameter_rows = [
    ("f_p,LB", "loaded-bare filter frequency", metrics["filter_loaded_bare_hz"] / 1e9, "GHz", "extracted", "filter-only vector pole"),
    ("f_r,LB^g", "loaded-bare readout frequency", metrics["readout_loaded_bare_hz"] / 1e9, "GHz", "fitted", "C_ext probe → 0 quadratic intercept"),
    ("Delta_rp,LB", "readout minus filter detuning", metrics["readout_minus_filter_detuning_hz"] / 1e6, "MHz", "calculated", "f_r,LB^g - f_p,LB"),
    ("f_n", "interference notch", metrics["notch_hz"] / 1e9, "GHz", "extracted", "PTC zero crossing"),
    ("kappa_p,LB / 2pi", "loaded filter linewidth", metrics["filter_loaded_linewidth_hz"] / 1e6, "MHz", "fitted", "filter-only complex response"),
    ("J / 2pi", "readout-filter exchange coupling", metrics["j_hz"] / 1e6, "MHz", "fitted", "fixed-reference complex S21 fit"),
    (
        "g / 2pi",
        "linearized qubit-readout coupling",
        metrics.get("g_hz", float("nan")) / 1e6,
        "MHz",
        "fitted" if "g_hz" in metrics else "unavailable",
        "finite-probe q/r poles → zero-probe quadratic intercept" if "g_hz" in metrics else "no qubit model in this historical run",
    ),
    ("tilde f lower", "lower hybridized model pole", model_poles[0]["frequency_hz"] / 1e9, "GHz", "calculated", "J-fit pole; mode ownership not assigned"),
    ("tilde f upper", "upper hybridized model pole", model_poles[1]["frequency_hz"] / 1e9, "GHz", "calculated", "J-fit pole; mode ownership not assigned"),
    ("tilde f_r^g / tilde f_p^g", "readout-like / filter-like owned frequencies", None, "GHz", "unavailable", "pair poles persisted without mode-ownership labels"),
    ("Delta tilde f_rp^g", "hybridized model-pole spacing", hybrid_spacing_hz / 1e6, "MHz", "calculated", "upper minus lower J-fit pole"),
    ("tilde kappa lower", "lower-pole linewidth", model_poles[0]["linewidth_hz"] / 1e6, "MHz", "calculated", "J-fit pole; mode ownership not assigned"),
    ("tilde kappa upper", "upper-pole linewidth", model_poles[1]["linewidth_hz"] / 1e6, "MHz", "calculated", "J-fit pole; mode ownership not assigned"),
    ("tilde kappa_r^g / tilde kappa_p^g", "owned hybridized linewidths", None, "MHz", "unavailable", "mode ownership not published"),
    ("tilde chi_r / tilde chi_p", "hybridized dispersive shifts", None, "MHz", "unavailable", "no qubit-state-dependent normal-mode solve"),
]
physical_parameter_table = pd.DataFrame(
    physical_parameter_rows,
    columns=["Parameter", "Meaning", "Value", "Unit", "Evidence state", "Source / caveat"],
)
display(
    physical_parameter_table.style.hide(axis="index").format(
        {"Value": lambda value: "—" if pd.isna(value) else f"{value:.6f}"}
    )
)

# %%
if "reference_notch" in diagnostics:
    reference_notch = diagnostics["reference_notch"]
    loaded_notch = diagnostics["notch"]
    display(
        pd.DataFrame(
            [
                ("No-qubit intrinsic reference", reference_notch["frequency_hz"] / 1e9, len(reference_notch["all_roots"]), reference_notch["ownership"], None),
                ("Qubit-loaded owned notch", loaded_notch["frequency_hz"] / 1e9, len(loaded_notch["all_roots"]), loaded_notch["ownership"], loaded_notch["assignment_margin_hz"] / 1e6),
            ],
            columns=["Notch evidence", "Frequency (GHz)", "Roots retained", "Ownership", "Assignment margin (MHz)"],
        ).style.hide(axis="index").format(
            {"Frequency (GHz)": "{:.9f}", "Assignment margin (MHz)": lambda value: "—" if pd.isna(value) else f"{value:.6f}"}
        )
    )

# %% [markdown]
# ## Calculated engineering parameters

# %%
design = diagnostics["design"]
engineering_rows = [
    ("l_p,total", design["lp_total_um"], "um", "calculated", "l_p,short + l_c + l_p,open"),
    ("l_r,total", design["lr_total_um"], "um", "calculated", "l_r,short + l_c + l_r,open"),
    ("notch path length", design["notch_length_um"], "um", "calculated", "persisted evaluator design"),
    ("loaded-bare center", metrics["loaded_bare_center_hz"] / 1e9, "GHz", "calculated", "mean of loaded-bare references"),
    ("model paired-pole center", metrics["model_paired_pole_center_hz"] / 1e9, "GHz", "calculated", "J-fit model poles"),
    ("vector paired-pole center", metrics["vector_paired_pole_center_hz"] / 1e9, "GHz", "extracted", "independent vector cross-check"),
    ("pair-pole center offset", metrics["pair_pole_center_offset_hz"] / 1e6, "MHz", "calculated", "vector center - loaded-bare center"),
    ("Z0 feedline", feedline["extracted_lc_impedance_ohm"], "ohm", "calculated", "sqrt(L/C); LC-only extraction"),
    ("feedline return loss", feedline["actual_return_loss_db"], "dB", "calculated", "lossless LC impedance mismatch"),
    ("R' feedline", None, "ohm/m", "unavailable", feedline["r_per_m_ohm"]["meaning"]),
    ("G' feedline", None, "S/m", "unavailable", feedline["g_per_m_s"]["meaning"]),
]
engineering_table = pd.DataFrame(
    engineering_rows,
    columns=["Parameter", "Value", "Unit", "Evidence state", "Source / caveat"],
)
display(
    engineering_table.style.hide(axis="index").format(
        {"Value": lambda value: "—" if pd.isna(value) else f"{value:.6f}"}
    )
)

# %%
if orpen_case is None:
    orpen_rows = [
        (
            "OrPen matrix and geometry evidence",
            "—",
            "unavailable",
            "current OrPen case bytes no longer match this run's hash-bound payload",
        )
    ]
else:
    mtl_l = np.asarray(orpen_case["mtl"]["l_matrix_h_per_m"], dtype=float)
    mtl_c = np.asarray(orpen_case["mtl"]["c_matrix_f_per_m"], dtype=float)
    single = orpen_case["single"]
    diagonal_reference_ohm = np.sqrt(np.diag(mtl_l) / np.diag(mtl_c))
    single_phase_velocity_m_per_s = 1.0 / math.sqrt(
        single["l_per_m_h"] * single["c_per_m_f"]
    )
    orpen_rows = [
        ("MTL geometry", orpen_case["mtl_point"], "extracted", "um fields in hash-bound OrPen case"),
        ("Single-trace geometry", orpen_case["single_trace_point"], "extracted", "um fields in hash-bound OrPen case"),
        ("MTL L matrix", np.array2string(mtl_l * 1e9, precision=6), "extracted", "nH/m"),
        ("MTL Maxwell C matrix", np.array2string(mtl_c * 1e12, precision=6), "extracted", "pF/m; negative off-diagonal retained"),
        ("Single-trace L'", single["l_per_m_h"] * 1e9, "extracted", "nH/m"),
        ("Single-trace C'", single["c_per_m_f"] * 1e12, "extracted", "pF/m"),
        ("Single-trace Z0", single["zo_effective_ohm"], "calculated", "ohm"),
        ("MTL screening Zm", orpen_case["mtl"]["zm_ohm"], "calculated", "ohm; D3 screening heuristic, not general modal impedance"),
        ("MTL diagonal-reference impedances", np.array2string(diagonal_reference_ohm, precision=6), "calculated", "ohm; artificial off-diagonal-zero reference"),
        ("Single-trace phase velocity", single_phase_velocity_m_per_s, "calculated", "m/s from scalar lossless L'C'"),
        ("MTL modal phase velocity", "—", "unavailable", "basis/direction contract is insufficient for promotion-grade modal interpretation"),
    ]
orpen_engineering_table = pd.DataFrame(
    orpen_rows,
    columns=["OrPen quantity", "Value", "Evidence state", "Unit / caveat"],
)
display(orpen_engineering_table.style.hide(axis="index"))

# %% [markdown]
# ## Intermediate optimization evidence

# %%
history_by_id = {record["record_id"]: record for record in optimization["history"]}
initial_record = history_by_id[optimization["initial_seed_record_id"]]
final_record_history = history_by_id[layout_specs["candidate_record_id"]]

stage_rows = []
for stage_name in ("cma", "nelder_mead"):
    stage = optimization[stage_name]
    stage_rows.append(
        {
            "Stage": "CMA-ES" if stage_name == "cma" else "Nelder–Mead",
            "State": stage["state"],
            "Termination": stage["termination_reason"],
            "Iterations": f"{stage['observed_iterations']} / {stage['declared_iteration_budget']}",
            "Evaluations": f"{stage['observed_evaluations']} / {stage['declared_evaluation_budget']}",
            "Valid": stage["valid_candidate_count"],
            "Rejected": stage["rejected_candidate_count"],
            "Best record": stage["best_valid_record_id"],
        }
    )
display(pd.DataFrame(stage_rows).style.hide(axis="index"))

# %%
comparison_rows = []
initial_metrics = initial_record["evaluation"].get("metrics")
final_metrics = final_record_history["evaluation"]["metrics"]
for metric_id in optimizer_metric_fields:
    final_value, _ = display_frequency(float(final_metrics[metric_id]), metric_id)
    if initial_metrics is None:
        initial_value, change = float("nan"), float("nan")
        _, unit = display_frequency(float(final_metrics[metric_id]), metric_id)
    else:
        initial_value, unit = display_frequency(float(initial_metrics[metric_id]), metric_id)
        change = final_value - initial_value
    comparison_rows.append((metric_id, initial_value, final_value, change, unit))
initial_cost = float("nan") if initial_record["cost"] is None else initial_record["cost"]
comparison_rows.append(
    (
        "weighted cost",
        initial_cost,
        final_record_history["cost"],
        float("nan") if math.isnan(initial_cost) else final_record_history["cost"] - initial_cost,
        "normalized squared cost",
    )
)
comparison_table = pd.DataFrame(comparison_rows, columns=["Metric", "Seed", "Final", "Change", "Unit"])
display(
    comparison_table.style.hide(axis="index").format(
        {"Seed": "{:.6g}", "Final": "{:.6g}", "Change": "{:+.6g}"}
    )
)

# %%
journal_counts = Counter(record.get("status", "missing") for record in journal_records)
promotion = optimization["promotion"]
decision_table = pd.DataFrame(
    [
        ("Journal valid evaluations", journal_counts.get("valid", 0), "persisted evaluator records"),
        ("Journal rejected evaluations", len(journal_records) - journal_counts.get("valid", 0), "physical or numerical fail-fast records"),
        ("CMA → local handoff", optimization["handoff"]["state"], optimization["handoff"]["reason"]),
        ("Promotion", promotion["state"], promotion["reason"]),
        ("Unmet promotion conditions", promotion["unmet_condition_ids"], "Human decision remains separate"),
    ],
    columns=["Evidence", "Observed", "Meaning"],
)
display(decision_table.style.hide(axis="index"))

# %% [markdown]
# ## Fit-quality tables

# %%
def fit_quality_rows(label: str, fit: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    metrics_local = fit["metrics"]
    gates = fit["gates"]
    for metric_id, observed in metrics_local.items():
        if metric_id == "phase_valid_sample_count":
            continue
        min_gate = f"min_{metric_id}"
        max_gate = f"max_{metric_id}"
        if min_gate in gates:
            comparator, threshold, passed = ">=", gates[min_gate], observed >= gates[min_gate]
        elif max_gate in gates:
            comparator, threshold, passed = "<=", gates[max_gate], observed <= gates[max_gate]
        else:
            comparator, threshold, passed = "diagnostic", None, None
        rows.append(
            {
                "Fit": label,
                "Metric": metric_id,
                "Observed": observed,
                "Comparator": comparator,
                "Gate": threshold,
                "Pass": passed,
            }
        )
    return rows


fit_quality_table = pd.DataFrame(
    fit_quality_rows("Filter channel calibration", diagnostics["channel_calibration"])
    + fit_quality_rows("Paired complex-S21 J fit", j_fit)
)
display(
    fit_quality_table.style.hide(axis="index").format(
        {
            "Observed": "{:.8g}",
            "Gate": lambda value: "—" if pd.isna(value) else f"{value:.8g}",
        }
    )
)

# %%
frequency_fit = diagnostics["readout_zero_probe_frequency_fit"]
linewidth_fit = diagnostics["readout_zero_probe_linewidth_fit"]
g_fit = diagnostics.get("g_zero_probe_fit")
regression_rows = [
    ("Readout frequency intercept", frequency_fit["intercept"] / 1e9, "GHz", "fitted", "quadratic in probe capacitance"),
    ("Frequency linear coefficient", frequency_fit["coefficients"]["linear_per_fF"] / 1e6, "MHz/fF", "fitted", "stored coefficient"),
    ("Frequency quadratic coefficient", frequency_fit["coefficients"]["quadratic_per_fF2"] / 1e6, "MHz/fF²", "fitted", "stored coefficient"),
    ("Readout linewidth intercept", linewidth_fit["intercept"] / 1e6, "MHz", "calculated", "constrained to zero by model"),
    ("Linewidth quadratic coefficient", linewidth_fit["coefficients"]["quadratic_per_fF2"] / 1e6, "MHz/fF²", "fitted", "stored coefficient"),
    ("Linewidth quartic coefficient", linewidth_fit["coefficients"]["quartic_per_fF4"] / 1e6, "MHz/fF⁴", "fitted", "stored coefficient"),
    ("Filter vector-fit RMS", diagnostics["filter_loaded_bare"]["vector_rms_error"], "complex response", "fitted", "filter-only vector fit"),
    ("J multi-seed spread", j_fit["diagnostics"]["j_seed_spread_hz"], "Hz", "calculated", "three successful seeds"),
]
if g_fit is not None:
    regression_rows.extend(
        [
            ("g intercept", g_fit["intercept"] / 1e6, "MHz", "fitted", "zero-probe quadratic intercept"),
            ("g extrapolation R²", g_fit["r2"], "fraction", "calculated", "configured Sol gate"),
        ]
    )
regression_table = pd.DataFrame(
    regression_rows,
    columns=["Quantity", "Value", "Unit", "Evidence state", "Meaning"],
)
display(regression_table.style.hide(axis="index").format({"Value": "{:.8g}"}))

# %% [markdown]
# ## Diagnostic evidence coverage
#
# The preferred PTC trace is `intrinsic_wide`, because it must cover both the
# notch and resonator region. Legacy runs contain only `intrinsic`; the notebook
# will plot that evidence but will not pretend it covers the resonators.

# %%
def complex_array(items: list[dict[str, float]], label: str) -> np.ndarray:
    if not items or not all(set(item) == {"real", "imag"} for item in items):
        raise ValueError(f"{label} must contain non-empty real/imag objects.")
    values = np.asarray([complex(item["real"], item["imag"]) for item in items], dtype=complex)
    if not np.all(np.isfinite(values)):
        raise ValueError(f"{label} must be finite.")
    return values


def validated_trace(
    trace: dict[str, Any],
    complex_key: str,
    label: str,
) -> tuple[np.ndarray, np.ndarray]:
    frequencies = np.asarray(trace["frequencies_hz"], dtype=float)
    values = complex_array(trace[complex_key], f"{label}.{complex_key}")
    if len(frequencies) != len(values) or len(frequencies) == 0:
        raise ValueError(f"{label} arrays must have one matching non-empty length.")
    if not np.all(np.isfinite(frequencies)) or not np.all(np.diff(frequencies) > 0):
        raise ValueError(f"{label} frequencies must be finite and strictly increasing.")
    return frequencies, values


ptc_trace_name = "intrinsic_wide" if "intrinsic_wide" in traces else "intrinsic"
ptc_frequency_hz, ptc_z21 = validated_trace(traces[ptc_trace_name], "z21_ptc", ptc_trace_name)
wide_evidence_available = ptc_trace_name == "intrinsic_wide"
reference_ptc = (
    validated_trace(traces["intrinsic_reference"], "z21_ptc", "intrinsic_reference")
    if "intrinsic_reference" in traces
    else None
)

filter_frequency_hz, filter_s21 = validated_trace(traces["filter"], "s21", "filter")
filter_reference = complex_array(traces["filter"]["reference_s21"], "filter.reference_s21")
if len(filter_reference) != len(filter_s21) or np.any(np.abs(filter_reference) == 0):
    raise ValueError("filter reference_s21 must match the trace and remain nonzero.")
filter_normalized = filter_s21 / filter_reference
pair_frequency_hz = np.asarray(traces["pair"]["frequencies_hz"], dtype=float)
pair_fit_frequency_hz = np.asarray(traces["pair"]["fit_frequencies_hz"], dtype=float)
pair_measured_fit = complex_array(traces["pair"]["fit_normalized_s21"], "pair.fit_normalized_s21")
pair_fitted = complex_array(traces["pair"]["fitted_s21"], "pair.fitted_s21")
if not (
    len(pair_fit_frequency_hz) == len(pair_measured_fit) == len(pair_fitted)
    and len(pair_fit_frequency_hz) > 0
    and np.all(np.diff(pair_fit_frequency_hz) > 0)
):
    raise ValueError("Paired fit arrays must share one non-empty increasing frequency grid.")

frequency_x = np.asarray(frequency_fit["x_values"], dtype=float)
frequency_y = np.asarray(frequency_fit["y_values"], dtype=float)
frequency_coefficients = frequency_fit["coefficients"]
frequency_intercept = float(frequency_fit["intercept"])
frequency_linear = float(frequency_coefficients["linear_per_fF"])
frequency_quadratic = float(frequency_coefficients["quadratic_per_fF2"])
linewidth_x = np.asarray(linewidth_fit["x_values"], dtype=float)
linewidth_y = np.asarray(linewidth_fit["y_values"], dtype=float)
linewidth_coefficients = linewidth_fit["coefficients"]
linewidth_quadratic = float(linewidth_coefficients["quadratic_per_fF2"])
linewidth_quartic = float(linewidth_coefficients["quartic_per_fF4"])
coverage_rows = [
        (
            ptc_trace_name,
            ptc_frequency_hz[0] / 1e9,
            ptc_frequency_hz[-1] / 1e9,
            len(ptc_frequency_hz),
            "notch + resonators" if wide_evidence_available else "notch only; wide evidence unavailable",
        ),
        (
            "filter",
            filter_frequency_hz[0] / 1e9,
            filter_frequency_hz[-1] / 1e9,
            len(filter_frequency_hz),
            "loaded-bare filter",
        ),
        (
            "pair",
            pair_frequency_hz[0] / 1e9,
            pair_frequency_hz[-1] / 1e9,
            len(pair_frequency_hz),
            "paired response and J fit",
        ),
        (
            "readout probes",
            min(frequency_fit["x_values"]),
            max(frequency_fit["x_values"]),
            len(frequency_fit["x_values"]),
            "x-axis is probe capacitance in fF",
        ),
    ]
if reference_ptc is not None:
    coverage_rows.append((
        "intrinsic_reference",
        reference_ptc[0][0] / 1e9,
        reference_ptc[0][-1] / 1e9,
        len(reference_ptc[0]),
        "narrow no-qubit notch ownership reference",
    ))
coverage_table = pd.DataFrame(
    coverage_rows,
    columns=["Trace", "Start", "Stop", "Samples", "Coverage / caveat"],
)
display(
    coverage_table.style.hide(axis="index").format(
        {"Start": "{:.6f}", "Stop": "{:.6f}"}
    )
)

if not wide_evidence_available:
    display(
        Markdown(
            "> **Wide PTC evidence unavailable in this legacy run.** The Log-scale "
            f"`|Im(Z21 PTC)|` figure below honestly shows only "
            f"{ptc_frequency_hz[0] / 1e9:.6g}–{ptc_frequency_hz[-1] / 1e9:.6g} GHz. It supports "
            "the notch but cannot show the resonator features near 6 GHz. A future run "
            "must persist `intrinsic_wide`; this notebook does not extrapolate or resimulate it."
        )
    )

# %% [markdown]
# ## Diagnostic plots
#
# Blue curves are always labeled **Simulated**. Orange curves are stored fits;
# neither is measurement data.

# %%
import matplotlib.pyplot as plt


BLUE = "#2764a5"
ORANGE = "#d67828"
GOLD = "#a77a13"
GREY = "#737b86"
INK = "#20242b"


def db20(values: np.ndarray) -> np.ndarray:
    return 20.0 * np.log10(np.maximum(np.abs(values), np.finfo(float).tiny))


def reference_line(
    axis: plt.Axes,
    frequency_hz: float,
    label: str,
    color: str,
    style: Any,
) -> None:
    axis.axvline(
        frequency_hz / 1e9,
        color=color,
        linestyle=style,
        linewidth=1.2,
        label=label,
    )


def style_axis(axis: plt.Axes) -> None:
    axis.set_facecolor("#fbfcfd")
    axis.grid(True, which="both", color="#e3e6e9", linewidth=0.7, alpha=0.85)
    axis.spines[["top", "right"]].set_visible(False)


figure, axes = plt.subplots(3, 2, figsize=(16, 15))
for axis in axes.flat:
    style_axis(axis)

metric_breakdown = {
    metric["name"]: metric for metric in layout_specs["breakdown"]["metrics"]
}

axis = axes[0, 0]
axis.plot(
    ptc_frequency_hz / 1e9,
    np.maximum(np.abs(ptc_z21.imag), np.finfo(float).tiny),
    color=BLUE,
    linewidth=1.5,
    label=f"Simulated |Im(Z21 PTC)| — {ptc_trace_name}",
)
if reference_ptc is not None:
    axis.plot(
        reference_ptc[0] / 1e9,
        np.maximum(np.abs(reference_ptc[1].imag), np.finfo(float).tiny),
        color=GREY,
        linestyle="--",
        linewidth=1.2,
        label="No-qubit intrinsic notch reference",
    )
axis.set_yscale("log")
reference_line(axis, metric_breakdown["notch_hz"]["target"], "Target notch", GREY, "--")
reference_line(axis, metrics["notch_hz"], "Found notch", ORANGE, ":")
if wide_evidence_available:
    reference_line(axis, metrics["filter_loaded_bare_hz"], "Filter loaded-bare", GOLD, "-.")
    reference_line(axis, metrics["readout_loaded_bare_hz"], "Readout loaded-bare", INK, (0, (2, 2)))
else:
    axis.text(
        0.02,
        0.04,
        "Wide evidence unavailable: resonator band is not covered",
        transform=axis.transAxes,
        color="#8a3f22",
        fontsize=9,
        weight="bold",
    )
axis.set(
    title="Intrinsic compensated transfer response",
    xlabel="Frequency (GHz)",
    ylabel="|Im(Z21 PTC)| (ohm, log scale)",
)
axis.legend(loc="best", fontsize=8, frameon=False)

axis = axes[0, 1]
axis.plot(
    filter_frequency_hz / 1e9,
    db20(filter_normalized),
    color=BLUE,
    linewidth=1.5,
    label="Simulated filter / empty-feedline reference",
)
reference_line(
    axis,
    metric_breakdown["filter_loaded_bare_hz"]["target"],
    "Target loaded-bare filter",
    GREY,
    "--",
)
reference_line(
    axis,
    metrics["filter_loaded_bare_hz"],
    "Found loaded-bare filter",
    ORANGE,
    ":",
)
axis.set(
    title="Normalized filter-only transmission",
    xlabel="Frequency (GHz)",
    ylabel="20 log10 |S21 / reference| (dB)",
)
axis.legend(loc="best", fontsize=8, frameon=False)

fit_frequency_ghz = pair_fit_frequency_hz / 1e9
axis = axes[1, 0]
axis.plot(
    fit_frequency_ghz,
    db20(pair_measured_fit),
    color=BLUE,
    linewidth=1.5,
    label="Simulated normalized |S21|",
)
axis.plot(
    fit_frequency_ghz,
    db20(pair_fitted),
    color=ORANGE,
    linewidth=1.3,
    linestyle="--",
    label="Complex-S21 fit",
)
reference_line(axis, metrics["readout_loaded_bare_hz"], "Readout loaded-bare", GREY, "--")
reference_line(axis, metrics["filter_loaded_bare_hz"], "Filter loaded-bare", GREY, ":")
for index, pole in enumerate(model_poles):
    reference_line(
        axis,
        pole["frequency_hz"],
        "Model poles" if index == 0 else "_nolegend_",
        GOLD,
        "-.",
    )
for index, pole_hz in enumerate(diagnostics["vector_crosscheck_poles_hz"]):
    reference_line(
        axis,
        pole_hz,
        "Vector poles" if index == 0 else "_nolegend_",
        INK,
        (0, (2, 2)),
    )
axis.set(
    title="Paired normalized transmission magnitude",
    xlabel="Frequency (GHz)",
    ylabel="|S21| (dB)",
)
axis.legend(loc="best", fontsize=7.5, frameon=False, ncols=2)

axis = axes[1, 1]
simulated_phase = np.unwrap(np.angle(pair_measured_fit)) * 180.0 / np.pi
relative_phase = np.unwrap(
    np.angle(pair_fitted * np.conjugate(pair_measured_fit))
) * 180.0 / np.pi
relative_phase -= 360.0 * round(float(np.median(relative_phase)) / 360.0)
axis.plot(
    fit_frequency_ghz,
    simulated_phase,
    color=BLUE,
    linewidth=1.5,
    label="Simulated normalized phase",
)
axis.plot(
    fit_frequency_ghz,
    simulated_phase + relative_phase,
    color=ORANGE,
    linewidth=1.3,
    linestyle="--",
    label="Fitted phase",
)
axis.set(
    title="Paired normalized transmission phase",
    xlabel="Frequency (GHz)",
    ylabel="Unwrapped phase (deg)",
)
axis.legend(loc="best", fontsize=8, frameon=False)

fit_x = np.linspace(0.0, max(frequency_x) * 1.05, 400)
frequency_curve = (
    frequency_intercept
    + frequency_linear * fit_x
    + frequency_quadratic * fit_x**2
)
axis = axes[2, 0]
axis.scatter(
    frequency_x,
    frequency_y / 1e9,
    color=BLUE,
    s=36,
    zorder=3,
    label="Simulated finite-probe poles",
)
axis.plot(
    fit_x,
    frequency_curve / 1e9,
    color=ORANGE,
    linewidth=1.5,
    label="Stored quadratic fit",
)
axis.scatter(
    [0.0],
    [frequency_intercept / 1e9],
    facecolors="white",
    edgecolors=ORANGE,
    linewidths=1.5,
    s=55,
    zorder=4,
    label="C → 0 intercept",
)
axis.axhline(
    metric_breakdown["readout_loaded_bare_hz"]["target"] / 1e9,
    color=GREY,
    linestyle="--",
    linewidth=1.2,
    label="Target loaded-bare readout",
)
axis.set(
    title="Readout loaded-bare frequency extrapolation",
    xlabel="Probe capacitance (fF)",
    ylabel="Frequency (GHz)",
)
axis.legend(loc="best", fontsize=8, frameon=False)

linewidth_curve = (
    linewidth_quadratic * fit_x**2
    + linewidth_quartic * fit_x**4
)
axis = axes[2, 1]
if g_fit is None:
    axis.scatter(linewidth_x, linewidth_y / 1e6, color=BLUE, s=36, zorder=3, label="Simulated finite-probe linewidths")
    axis.plot(fit_x, linewidth_curve / 1e6, color=ORANGE, linewidth=1.5, label="Stored C²+C⁴ fit")
    axis.scatter([0.0], [0.0], facecolors="white", edgecolors=ORANGE, linewidths=1.5, s=55, zorder=4, label="Constrained zero intercept")
    axis.axhline(0.0, color=INK, linewidth=0.9, alpha=0.8)
    axis.set(title="Readout linewidth extrapolation", xlabel="Probe capacitance (fF)", ylabel="Linewidth (MHz)")
else:
    g_x = np.asarray(g_fit["x_values"], dtype=float)
    g_y = np.asarray(g_fit["y_values"], dtype=float)
    g_coefficients = g_fit["coefficients"]
    g_curve = (
        float(g_coefficients["intercept"])
        + float(g_coefficients["linear_per_fF"]) * fit_x
        + float(g_coefficients["quadratic_per_fF2"]) * fit_x**2
    )
    axis.scatter(g_x, g_y / 1e6, color=BLUE, s=36, zorder=3, label="Simulated finite-probe g")
    axis.plot(fit_x, g_curve / 1e6, color=ORANGE, linewidth=1.5, label="Stored quadratic fit")
    axis.scatter([0.0], [g_fit["intercept"] / 1e6], facecolors="white", edgecolors=ORANGE, linewidths=1.5, s=55, zorder=4, label="C → 0 intercept")
    axis.axhline(metric_breakdown["g_hz"]["target"] / 1e6, color=GREY, linestyle="--", linewidth=1.2, label="Target g")
    axis.set(title="Qubit-readout g extrapolation", xlabel="Probe capacitance (fF)", ylabel="g / 2π (MHz)")
axis.legend(loc="best", fontsize=8, frameon=False)

evidence_identity = (
    selected_nominal_validation["validation_hash"]
    if selected_nominal_validation is not None
    else optimizer_validated["artifact_hash"]
)
figure.suptitle(
    f"D3 design review — {evidence_heading}\n"
    f"evidence {evidence_identity[:12]} | "
    f"kappa_p,LB {metrics['filter_loaded_linewidth_hz'] / 1e6:.6f} MHz | "
    f"J {metrics['j_hz'] / 1e6:.6f} MHz"
    + (f" | g {metrics['g_hz'] / 1e6:.6f} MHz" if "g_hz" in metrics else ""),
    fontsize=13,
    y=0.99,
)
figure.subplots_adjust(
    left=0.075,
    right=0.975,
    bottom=0.06,
    top=0.925,
    hspace=0.34,
    wspace=0.23,
)
figure_buffer = BytesIO()
figure.savefig(figure_buffer, format="png", dpi=180, facecolor="white")
display(Image(data=figure_buffer.getvalue()))
plt.close(figure)

# %% [markdown]
# ## Takeaways and caveats

# %%
max_positive_residual = performance_table["Normalized residual"].abs().max()
fit_gate_results = fit_quality_table["Pass"].dropna()
wide_summary = (
    "The wide PTC trace covers both the notch and resonator region."
    if wide_evidence_available
    else "Wide PTC evidence is unavailable; the persisted narrow trace supports the notch only."
)
display(
    Markdown(
        f"""
- The optimizer selected the frozen Layout Specs with search cost
  **{layout_specs['cost']:.6g}**. That number remains optimizer provenance; the
  largest absolute normalized residual in the displayed evidence is
  **{max_positive_residual:.6g}**.
- Persisted fit gates are **{'all satisfied' if fit_gate_results.all() else 'not all satisfied'}**.
  The J fit reports **{j_fit['diagnostics']['successful_seed_count']}** successful
  seeds and a spread of **{j_fit['diagnostics']['j_seed_spread_hz']:.6g} Hz**.
- CMA-ES state is **{optimization['cma']['state']}** and Nelder–Mead state is
  **{optimization['nelder_mead']['state']}**. Promotion remains
  **{optimization['promotion']['state']}**; Human acceptance is separate.
- This run is LC-only and lossless: source R/G are unavailable and runtime zeros
  are assumptions. Qubit-state dispersive shifts, multi-slot shared-readout
  closure, and mode-ownership labels were not produced.
- {wide_summary} No missing evidence is reconstructed.
"""
    )
)

# %% [markdown]
# ## Tolerance Validation
#
# Tolerance validation is deliberately outside the Cost Function. The optimizer
# answers “which nominal candidate best satisfies the weighted targets”; it does
# not decide fabrication acceptance. Perturbation variables, distributions,
# sample count, yield statistic, and Condition Threshold must be reviewed by a
# Human or a Sol-level semantic reviewer before a tolerance run is authorized.

# %%
tolerance_validation_state = "condition_required"
display(
    pd.DataFrame(
        [
            ("Tolerance Validation", tolerance_validation_state, "outside Cost Function"),
            ("Perturbation execution", "not performed", "no sweep is run by this notebook"),
            ("Condition Threshold", "Human / Sol review required", "no pass threshold inferred"),
            ("Tolerance pass claim", "unavailable", "future evidence is absent"),
        ],
        columns=["Decision surface", "State", "Meaning"],
    ).style.hide(axis="index")
)

# %% [markdown]
# ## Validation status before handoff

# %%
display(
    Markdown(
        f"**Nominal validation:** `{validation_state}` — {evidence_caveat}  \n"
        f"**Tolerance validation:** `{tolerance_validation_state}` — no tolerance pass is claimed."
    )
)

# %% [markdown]
# ## Final handoff: Layout Specs
#
# This is the output of the notebook. The table is copied from the validated
# `layout_specs.json`; it is the geometry/capacitance handoff whose performance
# was explained above. Its approval remains `unapproved_exploration` until the
# Human review state changes through the owning contract workflow.

# %%
hero_rows = [
    {
        "Layout parameter": item["id"],
        "Final value": item["value"],
        "Unit": item["unit"],
        "Candidate record": layout_specs["candidate_record_id"],
        "Approval": layout_specs["artifact_approval"],
    }
    for item in layout_specs["variables"]
]
hero_table = pd.DataFrame(hero_rows)
display(hero_table.style.hide(axis="index").format({"Final value": "{:.9f}"}))
