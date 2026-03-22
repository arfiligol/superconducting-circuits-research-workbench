import sys
from importlib import import_module
from pathlib import Path

from sc_core.execution import TaskResultHandle
from src.app.domain.circuit_definitions import CircuitDefinitionDraft
from src.app.infrastructure.rewrite_app_state_repository import InMemoryRewriteAppStateRepository
from src.app.infrastructure.rewrite_catalog_repository import InMemoryRewriteCatalogRepository

_WORKSPACE_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_WORKSPACE_SRC) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE_SRC))

parse_circuit_definition_source = import_module(
    "core.simulation.domain.circuit"
).parse_circuit_definition_source


def test_packaged_sc_core_import_is_available_to_backend() -> None:
    parsed = parse_circuit_definition_source(
        """{
        "name": "backend_probe",
        "components": [
            {"name": "R1", "default": 50.0, "unit": "Ohm"},
            {"name": "C1", "default": 100.0, "unit": "fF"},
            {"name": "Lj1", "default": 1000.0, "unit": "pH"},
            {"name": "C2", "default": 1000.0, "unit": "fF"}
        ],
        "topology": [
            ("P1", "1", "0", 1),
            ("R1", "1", "0", "R1"),
            ("C1", "1", "2", "C1"),
            ("Lj1", "2", "0", "Lj1"),
            ("C2", "2", "0", "C2")
        ]
    }"""
    )

    assert parsed.name == "backend_probe"
    assert parsed.available_port_indices == [1]
    assert parsed.effective_layout_profile == "jpa"


def test_repository_creation_uses_sc_core_inspection_contract() -> None:
    repository = InMemoryRewriteCatalogRepository()
    source_text = """{
        "name": "PackagedBoundary",
        "components": [
            {"name": "R1", "default": 50.0, "unit": "Ohm"},
            {"name": "C1", "default": 100.0, "unit": "fF"},
            {"name": "Lj1", "default": 1000.0, "unit": "pH"},
            {"name": "C2", "default": 1000.0, "unit": "fF"}
        ],
        "topology": [
            ("P1", "1", "0", 1),
            ("R1", "1", "0", "R1"),
            ("C1", "1", "2", "C1"),
            ("Lj1", "2", "0", "Lj1"),
            ("C2", "2", "0", "C2")
        ]
    }"""

    created = repository.create_circuit_definition(
        workspace_id="ws-device-lab",
        owner_user_id="researcher-01",
        owner_display_name="Ari",
        draft=CircuitDefinitionDraft(name="PackagedBoundary", source_text=source_text),
    )
    parsed = parse_circuit_definition_source(source_text)

    assert created.workspace_id == "ws-device-lab"
    assert created.visibility_scope == "private"
    assert created.name == "PackagedBoundary"
    assert "expanded" in created.normalized_output
    assert created.preview_artifacts == (
        "expanded-netlist.json",
        "validation-summary.json",
        "schemdraw-preview.svg",
    )
    assert created.validation_summary.status == "valid"
    assert created.validation_notices[0].code == "definition_parsed"
    assert parsed.name == "PackagedBoundary"


def test_backend_task_result_refs_use_shared_execution_and_storage_contracts() -> None:
    repository = InMemoryRewriteAppStateRepository()

    task = repository.get_task(303)

    assert task is not None
    assert task.result_refs.result_handle == TaskResultHandle(trace_batch_id=88)
    assert task.result_refs.storage_linkage().to_payload() == {"trace_batch_id": 88}
