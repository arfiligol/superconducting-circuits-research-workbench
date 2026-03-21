"""Focused WS10 checks for pages that should remain unaffected by the migration."""

from __future__ import annotations

import importlib
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from legacy.legacy_nicegui_archived.services.auth_service import ensure_bootstrap_admin
from core.shared.persistence import database, get_unit_of_work
from core.shared.persistence.models import CircuitRecord


def _configure_test_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SC_DATABASE_PATH", str(tmp_path / "database.db"))
    monkeypatch.setenv("SC_RQ_REDIS_URL", f"fakeredis://pages-{tmp_path.name}")
    monkeypatch.setenv("SC_TRACE_STORE_ROOT", str(tmp_path / "trace_store"))
    monkeypatch.setenv("SC_SESSION_SECRET", "ws10-page-routes-secret")
    database.get_engine.cache_clear()


def _create_circuit(name: str) -> int:
    with get_unit_of_work() as uow:
        circuit = uow.circuits.add(
            CircuitRecord(
                name=name,
                definition_json="""{
    "name": "WS10RouteCircuit",
    "components": [
        {"name": "R1", "default": 50.0, "unit": "Ohm"},
        {"name": "L1", "default": 10.0, "unit": "nH"},
        {"name": "C1", "default": 1.0, "unit": "pF"}
    ],
    "topology": [
        ("P1", "1", "0", 1),
        ("R1", "1", "0", "R1"),
        ("L1", "1", "2", "L1"),
        ("C1", "2", "0", "C1")
    ]
}""",
            )
        )
        uow.flush()
        assert circuit.id is not None
        uow.commit()
        return int(circuit.id)


@pytest.fixture()
def authenticated_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    _configure_test_environment(tmp_path, monkeypatch)
    app_main = importlib.import_module("legacy.legacy_nicegui_archived.main")
    ensure_bootstrap_admin()
    with TestClient(app_main.ui_app) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin"},
        )
        assert login.status_code == 200
        yield client
    database.get_engine.cache_clear()


@pytest.mark.parametrize(
    ("path", "expected_text"),
    [
        ("/raw-data", "Raw Data Browser"),
        ("/dashboard", "Dashboard"),
        ("/schemas", "Circuit Schemas"),
        ("/schemdraw-live-preview", "Schemdraw Live Preview"),
    ],
)
def test_unaffected_page_routes_load_after_migration(
    authenticated_client: TestClient,
    path: str,
    expected_text: str,
) -> None:
    response = authenticated_client.get(path)
    assert response.status_code == 200
    assert expected_text in response.text


def test_schema_editor_routes_load(
    authenticated_client: TestClient,
) -> None:
    circuit_id = _create_circuit("WS10 Existing Schema")
    for path in ("/schemas/new", f"/schemas/{circuit_id}"):
        response = authenticated_client.get(path)
        assert response.status_code == 200
        assert "<title>SC Tutorial App</title>" in response.text
