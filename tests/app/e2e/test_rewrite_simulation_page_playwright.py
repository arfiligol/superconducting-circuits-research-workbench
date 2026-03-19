"""Playwright E2E coverage for the rewrite Simulation page."""

from __future__ import annotations

import json
import os
import re
import signal
import socket
import subprocess
import shutil
import time
import uuid
from http.client import RemoteDisconnected
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pytest
from playwright.sync_api import Locator, Page, expect, sync_playwright

_RUN_REWRITE_SIMULATION_E2E = os.getenv("RUN_REWRITE_SIMULATION_PAGE_E2E") == "1"

pytestmark = pytest.mark.skipif(
    not _RUN_REWRITE_SIMULATION_E2E,
    reason=(
        "Set RUN_REWRITE_SIMULATION_PAGE_E2E=1 to run rewrite frontend "
        "Simulation page Playwright coverage."
    ),
)


FLOATING_QUBIT_WITH_XY_LINE: dict[str, object] = {
    "name": "FloatingQubitWithXYLine",
    "components": [
        {"name": "R50", "unit": "Ohm", "default": 50},
        {"name": "C_q", "unit": "pF", "default": 0.05814},
        {"name": "C_g1", "unit": "pF", "default": 0.10254},
        {"name": "C_g2", "unit": "pF", "default": 0.10189},
        {"name": "C_xy1", "unit": "pF", "default": 0.00017},
        {"name": "C_xy2", "unit": "pF", "default": 0.00075},
        {"name": "L_jun", "unit": "nH", "value_ref": "L_jun"},
    ],
    "topology": [
        ["P1", "1", "0", 1],
        ["R_p1", "1", "0", "R50"],
        ["P2", "2", "0", 2],
        ["R_p2", "2", "0", "R50"],
        ["P3", "3", "0", 3],
        ["R_p3", "3", "0", "R50"],
        ["C_q", "1", "2", "C_q"],
        ["L_jun1", "1", "2", "L_jun"],
        ["L_jun2", "1", "2", "L_jun"],
        ["C_g1", "1", "0", "C_g1"],
        ["C_g2", "2", "0", "C_g2"],
        ["C_xy1", "1", "3", "C_xy1"],
        ["C_xy2", "2", "3", "C_xy2"],
    ],
    "parameters": [
        {"name": "L_jun", "default": 24, "unit": "nH"},
    ],
}


def _wait_for_server(url: str, timeout_seconds: float = 90.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=10.0):
                return
        except (HTTPError, RemoteDisconnected, URLError, TimeoutError):
            time.sleep(0.5)
    raise TimeoutError(f"Timed out waiting for server at {url}")


def _json_request(url: str, payload: dict[str, object] | None = None, *, method: str = "PATCH") -> dict[str, object]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    with urlopen(request, timeout=10.0) as response:
        return json.loads(response.read().decode("utf-8"))


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        return int(sock.getsockname()[1])


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


def _surface_panel(page: Page, title: str) -> Locator:
    return page.locator("section").filter(has=page.get_by_role("heading", name=title, exact=True)).first


def _set_switch_state(toggle: Locator, *, checked: bool) -> None:
    aria_checked = toggle.get_attribute("aria-checked")
    if (aria_checked == "true") != checked:
        toggle.click()


def _select_menu_option(page: Page, button: Locator, option_name: str) -> None:
    button.click()
    page.get_by_role("option", name=option_name, exact=True).click()


def _select_sweep_value(page: Page, *, test_id: str, next_value: str) -> None:
    page.get_by_test_id(test_id).click()
    numeric_value = re.escape(next_value.split(" ", maxsplit=1)[0])
    page.get_by_role(
        "option",
        name=re.compile(rf"^{numeric_value}(?:\b|\.0+\b)(?:\s+\w+)?$", re.IGNORECASE),
    ).click()


@pytest.fixture(scope="session")
def rewrite_simulation_stack(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    repo_root = Path(__file__).resolve().parents[3]
    backend_dir = repo_root / "backend"
    source_frontend_dir = repo_root / "frontend"
    _ensure_frontend_dependencies(source_frontend_dir)

    backend_port = int(os.getenv("REWRITE_SIMULATION_PAGE_BACKEND_PORT", "0")) or _find_free_port()
    frontend_port = int(os.getenv("REWRITE_SIMULATION_PAGE_FRONTEND_PORT", "0")) or _find_free_port()
    backend_base_url = f"http://127.0.0.1:{backend_port}"
    frontend_base_url = f"http://127.0.0.1:{frontend_port}"

    log_dir = tmp_path_factory.mktemp("rewrite_simulation_page")
    backend_log = (log_dir / "backend.log").open("w", encoding="utf-8")
    frontend_log = (log_dir / "frontend.log").open("w", encoding="utf-8")
    database_dir = log_dir / "db"
    database_dir.mkdir(parents=True, exist_ok=True)
    frontend_dir = log_dir / "frontend-copy"
    shutil.copytree(
        source_frontend_dir,
        frontend_dir,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(".next", "node_modules", ".git", "test-results", "output"),
    )
    node_modules_link = frontend_dir / "node_modules"
    if not node_modules_link.exists():
        node_modules_link.symlink_to(source_frontend_dir / "node_modules", target_is_directory=True)

    backend_env = os.environ.copy()
    backend_env["SC_DATABASE_PATH"] = str(database_dir / "database.db")
    backend_env["SC_AUDIT_DATABASE_PATH"] = str(database_dir / "audit-log.db")
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

        _json_request(
            f"{backend_base_url}/session/active-dataset",
            {"dataset_id": "local-dataset-001"},
            method="PATCH",
        )
        create_response = _json_request(
            f"{backend_base_url}/circuit-definitions",
            {
                "name": "FloatingQubitWithXYLine",
                "source_text": json.dumps(FLOATING_QUBIT_WITH_XY_LINE, indent=2),
                "visibility_scope": "local",
            },
            method="POST",
        )
        definition_id = str(create_response["data"]["definition"]["definition_id"])

        yield {
            "backend_base_url": backend_base_url,
            "frontend_base_url": frontend_base_url,
            "definition_id": definition_id,
        }
    finally:
        _terminate_process(frontend_process)
        _terminate_process(backend_process)
        backend_log.close()
        frontend_log.close()


@pytest.fixture
def page(rewrite_simulation_stack: dict[str, str]) -> Page:
    _ = rewrite_simulation_stack
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1600, "height": 1800})
        page = context.new_page()
        yield page
        context.close()
        browser.close()


def test_rewrite_simulation_page_handles_sweeps_toasts_ptc_and_post_processing(
    page: Page,
    rewrite_simulation_stack: dict[str, str],
) -> None:
    console_errors = _capture_console_errors(page)
    frontend_base_url = rewrite_simulation_stack["frontend_base_url"]
    definition_id = rewrite_simulation_stack["definition_id"]

    page.goto(
        f"{frontend_base_url}/circuit-simulation?definitionId={definition_id}",
        wait_until="domcontentloaded",
    )

    expect(page.get_by_role("heading", name="Circuit Simulation")).to_be_visible(timeout=60_000)
    expect(page.get_by_role("button", name=re.compile(r"Runtime Mode\s+Local Mode", re.IGNORECASE | re.DOTALL))).to_be_visible(timeout=60_000)
    expect(page.get_by_role("button", name=re.compile(r"Active Dataset\s+Local Space Flux Sandbox", re.IGNORECASE | re.DOTALL))).to_be_visible(timeout=60_000)
    expect(page.get_by_text("FloatingQubitWithXYLine", exact=True)).to_be_visible(timeout=60_000)

    simulation_setup = _surface_panel(page, "Simulation Setup")
    _set_switch_state(
        simulation_setup.get_by_role("switch", name=re.compile(r"Enable parameter sweeps", re.IGNORECASE)),
        checked=True,
    )
    axis_heading = simulation_setup.get_by_text("Axis 1", exact=True)
    if axis_heading.count() == 0:
        simulation_setup.get_by_role("button", name="Add Axis").click()
    expect(axis_heading).to_be_visible(timeout=30_000)
    axis_mode_button = simulation_setup.get_by_role(
        "button",
        name="Simulation parameter sweep axis 1 mode",
    )
    if "explicit values" not in (axis_mode_button.text_content() or "").lower():
        _select_menu_option(page, axis_mode_button, "Explicit values")
    explicit_values = simulation_setup.get_by_role(
        "textbox",
        name=re.compile(r"Explicit Values", re.IGNORECASE),
    )
    expect(explicit_values).to_be_visible(timeout=30_000)
    explicit_values.fill("20, 22, 24, 26, 28")

    _set_switch_state(
        simulation_setup.get_by_role("switch", name=re.compile(r"Enable PTC", re.IGNORECASE)),
        checked=True,
    )
    for port_name in ("Port 1", "Port 2", "Port 3"):
        simulation_setup.get_by_role("button", name=port_name, exact=True).click()

    simulation_setup.get_by_role("button", name="Run Simulation").click()

    expect(page.get_by_text("Run submission accepted", exact=True)).to_be_visible(timeout=60_000)
    expect(page.get_by_text("Run submission failed", exact=True)).to_have_count(0)
    expect(page.get_by_text("Simulation Setup · Completed", exact=True)).to_have_count(0)

    simulation_result = _surface_panel(page, "Simulation Result")
    expect(simulation_result.get_by_text("Simulation Result Explorer", exact=True)).to_be_visible(timeout=60_000)
    expect(simulation_result.get_by_text("Parameter Sweep Point", exact=True)).to_be_visible(timeout=60_000)
    expect(simulation_result.get_by_text("Point 1 of 5", exact=True)).to_be_visible(timeout=60_000)

    _select_sweep_value(page, test_id="simulation-result-sweep-axis-0", next_value="28 nH")
    expect(simulation_result.get_by_text("Point 5 of 5", exact=True)).to_be_visible(timeout=30_000)

    simulation_result.get_by_role("button", name="Y Matrix").click()
    _select_menu_option(
        page,
        simulation_result.get_by_role("button", name="Simulation result source"),
        "PTC",
    )
    expect(simulation_result.get_by_role("button", name="Simulation result source")).to_contain_text("PTC")

    simulation_result.get_by_role("button", name="Save Current Trace").click()
    save_dialog = page.get_by_role("dialog", name="Save Current Trace")
    design_name = f"Overnight Trace {uuid.uuid4().hex[:6]}"
    save_dialog.get_by_role("button", name="New Design").click()
    save_dialog.get_by_role("textbox", name="Design Name").fill(design_name)
    save_dialog.get_by_role("button", name="Create Design").click()
    save_dialog.get_by_role("textbox", name="Parameter").fill("S11_sweep_ptc")
    save_dialog.get_by_role("button", name="Save Current Trace").click()
    expect(simulation_result.get_by_text(f"Saved to {design_name}", exact=False)).to_be_visible(timeout=30_000)
    expect(simulation_result.get_by_role("link", name="Open Saved Trace in Raw Data")).to_be_visible(timeout=30_000)

    post_processing_setup = _surface_panel(page, "Post Processing Setup")
    post_processing_setup.get_by_role("button", name="Add Step").click()
    _select_menu_option(
        page,
        post_processing_setup.get_by_role("button", name="Post-processing step type to add"),
        "Kron Reduction",
    )
    post_processing_setup.get_by_role("button", name="Add Step").click()

    expect(post_processing_setup.get_by_role("button", name="Port CM", exact=True)).to_be_visible(timeout=30_000)
    expect(post_processing_setup.get_by_role("button", name="Port DM", exact=True)).to_be_visible(timeout=30_000)
    expect(post_processing_setup.get_by_role("button", name="Port 3", exact=True)).to_be_visible(timeout=30_000)
    post_processing_setup.get_by_role("button", name="Port CM", exact=True).click()
    post_processing_setup.get_by_role("button", name="Port 3", exact=True).click()

    post_processing_setup.get_by_role("button", name="Run Post Processing").click()
    expect(page.get_by_text("Run submission accepted", exact=True)).to_be_visible(timeout=60_000)
    expect(page.get_by_text("Run submission failed", exact=True)).to_have_count(0)
    expect(page.get_by_text("Post Processing Setup · Completed", exact=True)).to_have_count(0)

    post_processing_result = _surface_panel(page, "Post Processing Result")
    expect(post_processing_result.get_by_text("Post Processing Result Explorer", exact=True)).to_be_visible(timeout=60_000)
    expect(post_processing_result.get_by_text("Parameter Sweep Point", exact=True)).to_be_visible(timeout=60_000)

    _select_sweep_value(page, test_id="post-processing-result-sweep-axis-0", next_value="28 nH")
    expect(post_processing_result.get_by_text("Point 5 of 5", exact=True)).to_be_visible(timeout=30_000)

    post_processing_result.get_by_role("button", name="Y Matrix").click()
    _select_menu_option(
        page,
        post_processing_result.get_by_role("button", name="Simulation result source"),
        "PTC",
    )
    expect(post_processing_result.get_by_role("button", name="Simulation result source")).to_contain_text("PTC")

    post_processing_result.get_by_role("button", name="S Matrix").click()
    expect(post_processing_result.get_by_text("Raw S_MATRIX", exact=False)).to_be_visible(timeout=30_000)
    expect(post_processing_result.get_by_text("PTC", exact=True)).to_have_count(0)

    assert not console_errors, f"Unexpected console errors: {console_errors}"
