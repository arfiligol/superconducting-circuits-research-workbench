from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import time
from http.client import RemoteDisconnected
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import pytest
from playwright.sync_api import Locator, Page, expect, sync_playwright


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        return int(sock.getsockname()[1])


def _wait_for_server(url: str, timeout_seconds: float = 90.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=10.0):
                return
        except (HTTPError, RemoteDisconnected, URLError, TimeoutError):
            time.sleep(0.5)
    raise TimeoutError(f"Timed out waiting for server at {url}")


def _ensure_frontend_dependencies(frontend_dir: Path) -> None:
    next_binary = frontend_dir / "node_modules" / ".bin" / "next"
    if next_binary.exists():
        return
    subprocess.run(["npm", "ci"], cwd=frontend_dir, check=True)


def _terminate_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)


def _surface_panel(page: Page, title: str) -> Locator:
    return page.locator("section").filter(
        has=page.get_by_role("heading", name=title, exact=True)
    ).first


def _capture_console_errors(page: Page) -> list[str]:
    console_errors: list[str] = []
    ignored_prefixes = ("Failed to load resource:",)
    ignored_substrings = ("useInsertionEffect must not schedule updates.",)

    def _listener(message) -> None:  # type: ignore[no-untyped-def]
        if message.type != "error":
            return
        if message.text.startswith(ignored_prefixes):
            return
        if any(segment in message.text for segment in ignored_substrings):
            return
        console_errors.append(message.text)

    page.on("console", _listener)
    return console_errors


def _seed_completed_simulation_fixture(
    *,
    backend_dir: Path,
    database_path: Path,
    audit_database_path: Path,
) -> dict[str, int]:
    output_path = database_path.parent / "fixture.json"
    env = os.environ.copy()
    env["SC_DATABASE_PATH"] = str(database_path)
    env["SC_AUDIT_DATABASE_PATH"] = str(audit_database_path)
    env["SC_RQ_REDIS_URL"] = "fakeredis://frontend-simulation-e2e"
    subprocess.run(
        [
            "uv",
            "run",
            "python",
            "../scripts/seed_simulation_e2e_fixture.py",
            "--database-path",
            str(database_path),
            "--audit-database-path",
            str(audit_database_path),
            "--output-path",
            str(output_path),
        ],
        cwd=backend_dir,
        env=env,
        check=True,
    )
    return json.loads(output_path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def simulation_stack(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str | int]:
    repo_root = Path(__file__).resolve().parents[2]
    backend_dir = repo_root / "backend"
    frontend_dir = repo_root / "frontend"
    output_dir = frontend_dir / "e2e" / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    _ensure_frontend_dependencies(frontend_dir)

    run_dir = tmp_path_factory.mktemp("frontend_simulation_smoke")
    database_path = run_dir / "database.db"
    audit_database_path = run_dir / "audit-log.db"
    fixture = _seed_completed_simulation_fixture(
        backend_dir=backend_dir,
        database_path=database_path,
        audit_database_path=audit_database_path,
    )

    backend_port = _find_free_port()
    frontend_port = _find_free_port()
    backend_base_url = f"http://127.0.0.1:{backend_port}"
    frontend_base_url = f"http://127.0.0.1:{frontend_port}"

    backend_log = (output_dir / "backend.log").open("w", encoding="utf-8")
    frontend_log = (output_dir / "frontend.log").open("w", encoding="utf-8")

    backend_env = os.environ.copy()
    backend_env["SC_DATABASE_PATH"] = str(database_path)
    backend_env["SC_AUDIT_DATABASE_PATH"] = str(audit_database_path)
    backend_env["SC_RQ_REDIS_URL"] = "fakeredis://frontend-simulation-e2e"
    backend_process = subprocess.Popen(
        [
            "uv",
            "run",
            "uvicorn",
            "src.app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(backend_port),
        ],
        cwd=backend_dir,
        env=backend_env,
        stdout=backend_log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        text=True,
    )

    frontend_env = os.environ.copy()
    frontend_env["BACKEND_BASE_URL"] = backend_base_url
    frontend_process = subprocess.Popen(
        [
            "npm",
            "run",
            "dev",
            "--",
            "--hostname",
            "127.0.0.1",
            "--port",
            str(frontend_port),
        ],
        cwd=frontend_dir,
        env=frontend_env,
        stdout=frontend_log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        text=True,
    )

    try:
        _wait_for_server(f"{backend_base_url}/session")
        _wait_for_server(f"{frontend_base_url}/circuit-simulation")
        _wait_for_server(f"{frontend_base_url}/api/backend/session")

        yield {
            "frontend_base_url": frontend_base_url,
            "definition_id": fixture["definition_id"],
            "simulation_task_id": fixture["simulation_task_id"],
            "screenshot_path": str(output_dir / "simulation-workflow-smoke.png"),
        }
    finally:
        _terminate_process(frontend_process)
        _terminate_process(backend_process)
        backend_log.close()
        frontend_log.close()


def test_circuit_simulation_page_smoke_loads_compare_axis_and_saves_visible_traces(
    simulation_stack: dict[str, str | int],
) -> None:
    frontend_base_url = str(simulation_stack["frontend_base_url"])
    definition_id = int(simulation_stack["definition_id"])
    simulation_task_id = int(simulation_stack["simulation_task_id"])
    screenshot_path = Path(str(simulation_stack["screenshot_path"]))
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1600, "height": 1200})
        console_errors = _capture_console_errors(page)

        page.goto(
            (
                f"{frontend_base_url}/circuit-simulation"
                f"?datasetId=local-dataset-001&definitionId={definition_id}&taskId={simulation_task_id}"
            ),
            wait_until="domcontentloaded",
        )

        simulation_panel = _surface_panel(page, "Simulation Result Explorer")
        expect(
            simulation_panel.get_by_role("heading", name="Simulation Result Explorer")
        ).to_be_visible(timeout=120_000)
        expect(
            simulation_panel.locator("span").filter(has_text=f"Task #{simulation_task_id}").first
        ).to_be_visible()
        expect(
            simulation_panel.get_by_text("Comparing Lj traces", exact=False)
        ).to_be_visible()
        expect(simulation_panel.get_by_text("3 traces", exact=True)).to_be_visible()

        simulation_panel.get_by_role("button", name="Save Traces", exact=True).click()
        dialog = page.get_by_role("dialog", name="Save Traces")
        expect(dialog).to_be_visible()
        expect(
            dialog.get_by_text(
                "3 visible traces will be saved as separate traces",
                exact=False,
            )
        ).to_be_visible()

        dialog.get_by_placeholder("Enter the saved parameter name").fill("Compare Sweep")
        dialog.get_by_role("button", name="New Design", exact=True).click()
        dialog.get_by_placeholder("Enter a design name").fill("E2E Visible Trace Save")
        dialog.get_by_role("button", name="Create Design", exact=True).click()
        dialog.get_by_role("button", name="Save Traces", exact=True).click()

        expect(
            simulation_panel.get_by_text(
                "Saved 3 traces to E2E Visible Trace Save",
                exact=False,
            )
        ).to_be_visible(timeout=30_000)
        expect(
            simulation_panel.get_by_role(
                "link",
                name="Open Saved Traces in Raw Data",
                exact=True,
            )
        ).to_be_visible()

        page.screenshot(path=str(screenshot_path), full_page=True)
        browser.close()

        assert console_errors == []
