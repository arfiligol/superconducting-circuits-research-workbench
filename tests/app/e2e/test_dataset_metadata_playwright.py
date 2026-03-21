"""Playwright E2E tests for dataset metadata editing across pages."""

from __future__ import annotations

import os
import re
import signal
import subprocess
import time
import uuid
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import numpy as np
import pytest
from playwright.sync_api import Page, expect, sync_playwright

from core.analysis.application.analysis.physics.admittance import calculate_y11_imaginary
from core.shared.persistence import get_unit_of_work
from core.shared.persistence.models import CircuitRecord, DataRecord, DatasetRecord

_RUN_PLAYWRIGHT_E2E = os.getenv("RUN_PLAYWRIGHT_DATASET_METADATA_E2E") == "1"

pytestmark = pytest.mark.skipif(
    not _RUN_PLAYWRIGHT_E2E,
    reason=(
        "Set RUN_PLAYWRIGHT_DATASET_METADATA_E2E=1 to run Playwright E2E tests "
        "for dataset metadata editing flows."
    ),
)


def _wait_for_server(url: str, timeout_seconds: float = 60.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=2.0):
                return
        except URLError:
            time.sleep(0.5)
    raise TimeoutError(f"Timed out waiting for app server at {url}")


def _stable_series_lc_definition() -> str:
    return str(
        {
            "name": "E2E Metadata Stable Series LC",
            "components": [
                {"name": "R50", "default": 50.0, "unit": "Ohm"},
                {"name": "L1", "default": 10.0, "unit": "nH"},
                {"name": "C1", "default": 1.0, "unit": "pF"},
            ],
            "topology": [
                ("P1", "1", "0", 1),
                ("R50", "1", "0", "R50"),
                ("L1", "1", "2", "L1"),
                ("C1", "2", "0", "C1"),
            ],
        }
    )


def _seed_dataset(dataset_name: str) -> None:
    freq_ghz = np.linspace(4.0, 8.0, 201)
    l_jun_nh = np.linspace(0.8, 2.8, 9)
    values_matrix = [
        [
            float(
                calculate_y11_imaginary(
                    float(l_value),
                    float(freq_value),
                    Ls1_nH=0.02,
                    Ls2_nH=0.03,
                    C_pF=1.0,
                )
            )
            for l_value in l_jun_nh
        ]
        for freq_value in freq_ghz
    ]

    with get_unit_of_work() as uow:
        existing = uow.datasets.get_by_name(dataset_name)
        if existing is not None:
            uow.datasets.delete(existing)
            uow.commit()

        dataset = DatasetRecord(
            name=dataset_name,
            source_meta={
                "origin": "measurement",
                "dataset_profile": {
                    "schema_version": "1.0",
                    "device_type": "squid",
                    "capabilities": [
                        "y_parameter_characterization",
                        "y11_response_fitting",
                        "squid_characterization",
                    ],
                    "source": "manual_override",
                },
            },
            parameters={},
        )
        uow.datasets.add(dataset)
        uow.flush()
        if dataset.id is None:
            raise ValueError("Failed to allocate dataset id.")

        common_axes = [
            {"name": "Freq", "unit": "GHz", "values": [float(x) for x in freq_ghz]},
            {"name": "L_jun", "unit": "nH", "values": [float(x) for x in l_jun_nh]},
        ]
        uow.data_records.add(
            DataRecord(
                dataset_id=int(dataset.id),
                data_type="y_parameters",
                parameter="Y11",
                representation="imaginary",
                axes=common_axes,
                values=values_matrix,
            )
        )
        uow.commit()


def _seed_schema(schema_name: str) -> None:
    with get_unit_of_work() as uow:
        existing = uow.circuits.get_by_name(schema_name)
        if existing is None:
            uow.circuits.add(
                CircuitRecord(name=schema_name, definition_json=_stable_series_lc_definition())
            )
        else:
            existing.definition_json = _stable_series_lc_definition()
            uow.circuits.update(existing)
        uow.commit()


@pytest.fixture(scope="session")
def seeded_names() -> dict[str, str]:
    suffix = uuid.uuid4().hex[:8]
    return {
        "dataset": f"E2E-Metadata-{suffix}",
        "schema": f"E2E-Metadata-Schema-{suffix}",
    }


@pytest.fixture(scope="session", autouse=True)
def seed_data(seeded_names: dict[str, str]) -> None:
    _seed_dataset(seeded_names["dataset"])
    _seed_schema(seeded_names["schema"])
    yield
    with get_unit_of_work() as uow:
        dataset = uow.datasets.get_by_name(seeded_names["dataset"])
        if dataset is not None:
            uow.datasets.delete(dataset)
            uow.commit()

        schema = uow.circuits.get_by_name(seeded_names["schema"])
        if schema is not None and schema.id is not None:
            uow.circuits.delete(schema.id)
            uow.commit()


@pytest.fixture(scope="session")
def app_base_url(tmp_path_factory: pytest.TempPathFactory) -> str:
    port = int(os.getenv("PLAYWRIGHT_DATASET_METADATA_APP_PORT", "8095"))
    base_url = f"http://127.0.0.1:{port}"

    log_dir = tmp_path_factory.mktemp("playwright_dataset_metadata_app")
    log_path = log_dir / "sc_app.log"
    log_file = log_path.open("w", encoding="utf-8")

    env = os.environ.copy()
    env["SC_APP_PORT"] = str(port)
    env["NICEGUI_SCREEN_TEST_PORT"] = str(port)
    process = subprocess.Popen(
        ["uv", "run", "sc-legacy-nicegui"],
        cwd=Path(__file__).resolve().parents[3],
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    try:
        _wait_for_server(f"{base_url}/raw-data")
        yield base_url
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
        if not log_file.closed:
            log_file.close()


@pytest.fixture
def page(app_base_url: str) -> Page:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1400})
        page = context.new_page()
        yield page
        context.close()
        browser.close()


def _select_option(page: Page, label: str, option_text: str, index: int = 0) -> None:
    select = page.get_by_role("combobox", name=label).nth(index)
    expect(select).to_be_visible(timeout=15000)
    last_error: Exception | None = None
    for _ in range(3):
        try:
            select = page.get_by_role("combobox", name=label).nth(index)
            select.click(timeout=5000)
            last_error = None
            break
        except Exception as exc:  # pragma: no cover - flaky detach protection
            last_error = exc
            time.sleep(0.2)
    if last_error is not None:
        raise last_error
    page.get_by_role("option", name=re.compile(rf"^{re.escape(option_text)}")).first.click()


def _select_active_dataset_in_characterization(page: Page, dataset_name: str) -> None:
    active_selector = page.get_by_role("combobox", name="Active Datasets")
    if active_selector.count() == 0:
        active_selector = page.get_by_role("combobox").first
    expect(active_selector).to_be_visible(timeout=15000)
    active_selector.click()
    page.get_by_role("option", name=dataset_name, exact=True).click()
    page.keyboard.press("Escape")


def test_dataset_metadata_dashboard_single_entry_flow(
    page: Page,
    app_base_url: str,
    seeded_names: dict[str, str],
) -> None:
    console_errors: list[str] = []

    def _capture_console(msg) -> None:  # type: ignore[no-untyped-def]
        if msg.type == "error":
            console_errors.append(msg.text)

    page.on("console", _capture_console)

    # Step 1: choose active dataset, then edit metadata in Dashboard (single editable entry)
    page.goto(f"{app_base_url}/raw-data", wait_until="networkidle")
    _select_active_dataset_in_characterization(page, seeded_names["dataset"])
    page.goto(f"{app_base_url}/dashboard", wait_until="networkidle")
    expect(page.get_by_role("main").get_by_text("Dashboard", exact=True)).to_be_visible(
        timeout=30000
    )
    _select_option(page, "Device Type", "Single Junction")
    page.get_by_role("button", name="Auto Suggest").first.click()
    page.get_by_role("button", name="Save Metadata").first.click()
    expect(page.get_by_text("Dataset metadata saved.")).to_be_visible(timeout=30000)

    # Step 2: Raw Data shows read-only metadata summary only
    page.goto(f"{app_base_url}/raw-data", wait_until="networkidle")
    expect(page.get_by_text("Raw Data Browser")).to_be_visible(timeout=30000)
    page.get_by_role("cell", name=seeded_names["dataset"], exact=True).click()
    expect(page.get_by_text("Dataset Metadata Summary", exact=True)).to_be_visible(timeout=30000)
    expect(page.get_by_role("button", name="Auto Suggest")).to_have_count(0)
    expect(page.get_by_role("button", name="Save Metadata")).to_have_count(0)

    # Step 3: Simulation shows read-only metadata summary only
    page.goto(f"{app_base_url}/simulation", wait_until="networkidle")
    expect(page.get_by_text("Dataset Metadata Summary", exact=True).first).to_be_visible(
        timeout=30000
    )
    _select_option(page, "Target Dataset", seeded_names["dataset"])
    expect(page.get_by_text("Device Type: single_junction")).to_be_visible(timeout=30000)
    expect(page.get_by_role("button", name="Auto Suggest")).to_have_count(0)
    expect(page.get_by_role("button", name="Save Metadata")).to_have_count(0)

    # Step 4: Characterization trace-first availability keeps profile hints non-blocking
    page.goto(f"{app_base_url}/characterization", wait_until="networkidle")
    _select_active_dataset_in_characterization(page, seeded_names["dataset"])
    expect(page.get_by_text("Source Scope")).to_be_visible(timeout=30000)
    expect(page.get_by_role("combobox", name="Result Bundle")).to_have_count(0)
    expect(
        page.get_by_text(re.compile(r"^(Available|Recommended|Unavailable) for current scope$"))
    ).to_be_visible(timeout=30000)

    # Step 5: basic stability assertions
    connection_lost = page.get_by_text("Connection lost", exact=False)
    if connection_lost.count() > 0:
        expect(connection_lost.first).not_to_be_visible(timeout=30000)
    assert not console_errors
