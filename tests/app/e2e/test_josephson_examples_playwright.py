"""Playwright E2E smoke tests for JosephsonCircuits-style simulation examples."""

from __future__ import annotations

import importlib.util
import os
import re
import signal
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pytest
from playwright.sync_api import (
    Locator,
    Page,
    expect,
    sync_playwright,
)
from playwright.sync_api import (
    TimeoutError as PlaywrightTimeoutError,
)

from core.shared.persistence import get_unit_of_work
from core.shared.persistence.models import CircuitRecord, ResultBundleRecord
from core.shared.persistence.trace_store import LocalZarrTraceStoreBackend, get_trace_store_path

_RUN_PLAYWRIGHT_E2E = os.getenv("RUN_PLAYWRIGHT_JOSEPHSON_E2E") == "1"

pytestmark = pytest.mark.skipif(
    not _RUN_PLAYWRIGHT_E2E,
    reason=(
        "Set RUN_PLAYWRIGHT_JOSEPHSON_E2E=1 to run Playwright E2E smoke tests "
        "for JosephsonCircuits-style examples."
    ),
)


@dataclass(frozen=True)
class ExampleCase:
    """One simulation flow to execute through the browser UI."""

    slug: str
    schema_name: str
    definition: str
    start_ghz: float
    stop_ghz: float
    points: int
    n_mod: int
    n_pump: int
    sources: tuple[tuple[float, int, float], ...]


@dataclass(frozen=True)
class AppServer:
    """Runtime metadata for the spawned NiceGUI app under test."""

    base_url: str
    log_path: Path


@dataclass(frozen=True)
class ValidationMatrixSavedDataset:
    """One saved-trace dataset materialized by the phase-2 validation matrix."""

    scenario_id: str
    dataset_name: str
    bundle_type: str
    role: str | None
    stage_kind: str
    analysis_label: str
    expects_compatible_analysis: bool


@dataclass(frozen=True)
class BlockedValidationScenario:
    """One planned matrix slot that remains blocked until its product path lands."""

    scenario_id: str
    blocked_reason: str


_VALIDATION_MATRIX_ANALYSIS_LABEL = "Admittance Extraction"
_VALIDATION_MATRIX_SCREENSHOT_PATH = Path("/tmp/phase2_examples_validation_matrix_saved_traces.png")
_BLOCKED_VALIDATION_SCENARIOS = (
    pytest.param(
        BlockedValidationScenario(
            scenario_id="layout_ingest_save_read",
            blocked_reason="Layout ingest save/read is a reserved matrix slot until ingest lands.",
        ),
        marks=pytest.mark.skip(
            reason="Layout ingest path has not landed yet; keep the validation-matrix slot blocked."
        ),
    ),
    pytest.param(
        BlockedValidationScenario(
            scenario_id="measurement_ingest_save_read",
            blocked_reason=(
                "Measurement ingest save/read is a reserved matrix slot until ingest lands."
            ),
        ),
        marks=pytest.mark.skip(
            reason=(
                "Measurement ingest path has not landed yet; keep the validation-matrix "
                "slot blocked."
            )
        ),
    ),
)


def _stable_series_lc_definition() -> str:
    return str(
        {
            "name": "E2E Stable Series LC",
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


def _jpa_definition() -> str:
    return str(
        {
            "name": "E2E JPA Core",
            "components": [
                {"name": "R1", "default": 50.0, "unit": "Ohm"},
                {"name": "Cc", "default": 100.0, "unit": "fF"},
                {"name": "Lj", "default": 1000.0, "unit": "pH"},
                {"name": "Cj", "default": 1000.0, "unit": "fF"},
            ],
            "topology": [
                ("P1", "1", "0", 1),
                ("R1", "1", "0", "R1"),
                ("C1", "1", "2", "Cc"),
                ("Lj1", "2", "0", "Lj"),
                ("C2", "2", "0", "Cj"),
            ],
        }
    )


def _official_seed_definitions() -> dict[str, str]:
    """Load official JosephsonCircuits seeded definitions from local seed script."""
    module_path = (
        Path(__file__).resolve().parents[3] / "tmp" / "seed_josephson_circuits_examples.py"
    )
    spec = importlib.util.spec_from_file_location("seed_josephson_circuits_examples", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return dict(module.build_all())


def _two_port_compensation_definition() -> str:
    return str(
        {
            "name": "E2E Two Port Compensation",
            "components": [
                {"name": "R50", "default": 50.0, "unit": "Ohm"},
                {"name": "R100", "default": 100.0, "unit": "Ohm"},
                {"name": "C12", "default": 200.0, "unit": "fF"},
            ],
            "topology": [
                ("P1", "1", "0", 1),
                ("P2", "2", "0", 2),
                ("R1", "1", "0", "R50"),
                ("R2", "2", "0", "R100"),
                ("C1", "1", "2", "C12"),
            ],
        }
    )


def _three_port_basis_definition() -> str:
    return str(
        {
            "name": "E2E Three Port Basis Labels",
            "components": [
                {"name": "R50", "default": 50.0, "unit": "Ohm"},
                {"name": "C12", "default": 120.0, "unit": "fF"},
                {"name": "C23", "default": 80.0, "unit": "fF"},
                {"name": "Cg1", "default": 30.0, "unit": "fF"},
                {"name": "Cg2", "default": 35.0, "unit": "fF"},
            ],
            "topology": [
                ("P1", "1", "0", 1),
                ("P2", "2", "0", 2),
                ("P3", "3", "0", 3),
                ("R1", "1", "0", "R50"),
                ("R2", "2", "0", "R50"),
                ("R3", "3", "0", "R50"),
                ("C12", "1", "2", "C12"),
                ("C23", "2", "3", "C23"),
                ("Cg1", "1", "0", "Cg1"),
                ("Cg2", "2", "0", "Cg2"),
            ],
        }
    )


@pytest.fixture(scope="session")
def example_cases() -> tuple[ExampleCase, ...]:
    """Representative example categories from JosephsonCircuits README usage."""
    suffix = uuid.uuid4().hex[:8]
    official_seed_definitions = _official_seed_definitions()
    official_flux_name = (
        "JosephsonCircuits Examples: Flux-pumped Josephson Parametric Amplifier (JPA)"
    )

    single_ip = 0.00565e-6
    double_ip = single_ip * 1.7

    return (
        ExampleCase(
            slug="linear_series_lc",
            schema_name=f"E2E-{suffix}-LinearSeriesLC",
            definition=_stable_series_lc_definition(),
            start_ghz=1.0,
            stop_ghz=5.0,
            points=201,
            n_mod=8,
            n_pump=8,
            sources=((5.0, 1, 0.0),),
        ),
        ExampleCase(
            slug="jpa_single_pump",
            schema_name=f"E2E-{suffix}-JPASinglePump",
            definition=_jpa_definition(),
            start_ghz=4.5,
            stop_ghz=5.0,
            points=201,
            n_mod=8,
            n_pump=16,
            sources=((4.75001, 1, single_ip),),
        ),
        ExampleCase(
            slug="jpa_double_pump",
            schema_name=f"E2E-{suffix}-JPADoublePump",
            definition=_jpa_definition(),
            start_ghz=4.5,
            stop_ghz=5.0,
            points=101,
            n_mod=4,
            n_pump=4,
            sources=((4.65001, 1, double_ip), (4.85001, 1, double_ip)),
        ),
        ExampleCase(
            slug="two_port_compensation",
            schema_name=f"E2E-{suffix}-TwoPortCompensation",
            definition=_two_port_compensation_definition(),
            start_ghz=4.8,
            stop_ghz=5.2,
            points=201,
            n_mod=6,
            n_pump=6,
            sources=((5.0, 1, 0.0),),
        ),
        ExampleCase(
            slug="three_port_basis_labels",
            schema_name=f"E2E-{suffix}-ThreePortBasisLabels",
            definition=_three_port_basis_definition(),
            start_ghz=4.8,
            stop_ghz=5.2,
            points=121,
            n_mod=4,
            n_pump=4,
            sources=((5.0, 1, 0.0),),
        ),
        ExampleCase(
            slug="flux_pumped_jpa_bias_sweep",
            schema_name=official_flux_name,
            definition=official_seed_definitions[official_flux_name],
            start_ghz=9.7,
            stop_ghz=9.8,
            points=101,
            n_mod=8,
            n_pump=16,
            sources=((19.50, 2, 140.3e-6), (19.50, 2, 0.7e-6)),
        ),
    )


@pytest.fixture(scope="session", autouse=True)
def seed_example_schemas(example_cases: tuple[ExampleCase, ...]) -> None:
    """Insert/update required schemas so UI tests do not depend on editor interactions."""
    created_schema_names: list[str] = []
    with get_unit_of_work() as uow:
        for case in example_cases:
            existing = uow.circuits.get_by_name(case.schema_name)
            if existing is None:
                uow.circuits.add(
                    CircuitRecord(name=case.schema_name, definition_json=case.definition)
                )
                created_schema_names.append(case.schema_name)
            else:
                existing.definition_json = case.definition
                uow.circuits.update(existing)
        uow.commit()
    yield
    with get_unit_of_work() as uow:
        for schema_name in created_schema_names:
            existing = uow.circuits.get_by_name(schema_name)
            if existing is not None and existing.id is not None:
                uow.circuits.delete(existing.id)
        uow.commit()


def _wait_for_server(url: str, timeout_seconds: float = 60.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=2.0):
                return
        except URLError:
            time.sleep(0.5)
    raise TimeoutError(f"Timed out waiting for app server at {url}")


@pytest.fixture(scope="session")
def app_server(tmp_path_factory: pytest.TempPathFactory) -> AppServer:
    """Start the NiceGUI app once for all Playwright example tests."""
    port = int(os.getenv("PLAYWRIGHT_SC_APP_PORT", "8093"))
    base_url = f"http://127.0.0.1:{port}"

    log_dir = tmp_path_factory.mktemp("playwright_sc_app")
    log_path = log_dir / "sc_app.log"
    log_file = log_path.open("w", encoding="utf-8")

    env = os.environ.copy()
    env["SC_APP_PORT"] = str(port)
    env["NICEGUI_SCREEN_TEST_PORT"] = str(port)
    env["SC_APP_RECONNECT_TIMEOUT"] = "1.0"
    process = subprocess.Popen(
        ["uv", "run", "sc-legacy-nicegui"],
        cwd=Path(__file__).resolve().parents[3],
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    try:
        _wait_for_server(f"{base_url}/simulation")
        yield AppServer(base_url=base_url, log_path=log_path)
    except Exception as err:
        log_file.flush()
        log_file.close()
        details = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
        raise RuntimeError(f"Failed to start app server. Log:\n{details}") from err
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
        if not log_file.closed:
            log_file.close()


@pytest.fixture(scope="session")
def app_base_url(app_server: AppServer) -> str:
    return app_server.base_url


@pytest.fixture
def page(app_base_url: str) -> Page:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1400})
        page = context.new_page()
        page.goto(f"{app_base_url}/simulation", wait_until="networkidle")
        yield page
        context.close()
        browser.close()


def _latest_trace_batch_bundle_for_circuit(
    *,
    circuit_name: str,
    bundle_type: str,
    role: str | None = None,
) -> ResultBundleRecord:
    with get_unit_of_work() as uow:
        candidates: list[ResultBundleRecord] = []
        for dataset in uow.datasets.list_all(include_hidden=True):
            if dataset.id is None:
                continue
            for bundle in uow.result_bundles.list_by_dataset(int(dataset.id)):
                if str(bundle.bundle_type) != bundle_type:
                    continue
                if role is not None and str(bundle.role) != role:
                    continue
                if str(bundle.source_meta.get("circuit_name", "")) != circuit_name:
                    continue
                if str(bundle.result_payload.get("schema_kind", "")) != "trace_batch_bundle":
                    continue
                candidates.append(bundle)
    assert candidates, f"No trace-batch bundle found for {circuit_name} ({bundle_type}, {role})"
    return max(candidates, key=lambda bundle: int(bundle.id or 0))


def _latest_trace_batch_bundle_for_dataset(
    *,
    dataset_name: str,
    bundle_type: str,
    role: str | None = None,
) -> ResultBundleRecord:
    with get_unit_of_work() as uow:
        dataset = uow.datasets.get_by_name(dataset_name)
        assert dataset is not None, f"Dataset not found for validation matrix: {dataset_name}"
        assert dataset.id is not None, f"Dataset id missing for validation matrix: {dataset_name}"
        candidates = [
            bundle
            for bundle in uow.result_bundles.list_by_dataset(int(dataset.id))
            if str(bundle.bundle_type) == bundle_type
            and (role is None or str(bundle.role) == role)
            and str(bundle.result_payload.get("schema_kind", "")) == "trace_batch_bundle"
        ]
    assert candidates, f"No trace-batch bundle found for dataset {dataset_name} ({bundle_type})"
    return max(candidates, key=lambda bundle: int(bundle.id or 0))


def _assert_trace_batch_payload(
    bundle: ResultBundleRecord,
    *,
    stage_kind: str,
    point_count: int,
    parent_batch_id: int | None = None,
) -> None:
    payload = bundle.result_payload
    assert payload["schema_kind"] == "trace_batch_bundle"
    trace_batch = payload["trace_batch_record"]
    assert trace_batch["stage_kind"] == stage_kind
    assert trace_batch["summary_payload"]["point_count"] == point_count
    assert trace_batch["summary_payload"]["trace_count"] > 0
    if parent_batch_id is not None:
        assert trace_batch["parent_batch_id"] == parent_batch_id

    trace_records = payload["trace_records"]
    assert trace_records
    store_ref = trace_records[0]["store_ref"]
    assert store_ref["store_key"]
    binding = LocalZarrTraceStoreBackend(root_path=get_trace_store_path())
    assert binding.resolve_store_path(store_key=store_ref["store_key"]).exists()


def _set_spinbutton_value(page: Page, label: str, value: float | int | str, index: int = 0) -> None:
    target = page.get_by_role("spinbutton", name=label).nth(index)
    expect(target).to_be_visible(timeout=15000)
    target.click()
    target.fill(str(value))
    target.press("Enter")


def _choose_schema(page: Page, schema_name: str) -> None:
    schema_select = page.get_by_role("combobox").nth(1)
    expect(schema_select).to_be_visible(timeout=15000)
    schema_select.click()
    page.get_by_role("option", name=schema_name, exact=True).click()


def _configure_sources(page: Page, sources: tuple[tuple[float, int, float], ...]) -> None:
    existing_count = page.get_by_text(re.compile(r"^Source \d+$")).count()
    while existing_count < len(sources):
        page.get_by_role("button", name="Add Source").click()
        existing_count += 1

    for idx, (pump_freq_ghz, port, current_amp) in enumerate(sources):
        _set_spinbutton_value(page, "Pump Freq (GHz)", pump_freq_ghz, index=idx)
        _set_spinbutton_value(page, "Source Port", port, index=idx)
        _set_spinbutton_value(page, "Source Current Ip (A)", current_amp, index=idx)


def _configure_multi_axis_sweep(
    page: Page,
    *,
    axes: tuple[dict[str, float | int | str], ...],
) -> None:
    sweep_card = _card_by_testid(
        page,
        "simulation-sweep-setup-card",
        fallback_text="Parameter Sweeps",
    )
    expect(sweep_card).to_be_visible(timeout=30000)
    assert len(axes) >= 1
    enable_switch = sweep_card.get_by_role("switch", name="Enable Sweep")
    if enable_switch.count() == 0:
        enable_switch = sweep_card.get_by_role("checkbox", name="Enable Sweep")
    if enable_switch.count() > 0:
        if not enable_switch.first.is_checked():
            enable_switch.first.click()
    else:
        toggle = sweep_card.locator(".q-toggle").first
        expect(toggle).to_be_visible(timeout=30000)
        classes = str(toggle.get_attribute("class") or "")
        if "q-toggle--truthy" not in classes:
            toggle.click()

    add_axis_button = _locator_by_testid(
        page,
        "simulation-sweep-add-axis-button",
        fallback=sweep_card.get_by_role("button", name="Add Axis"),
    )
    while sweep_card.locator("[data-testid='simulation-sweep-target-select']").count() < len(axes):
        add_axis_button.click()

    target_selects = sweep_card.locator("[data-testid='simulation-sweep-target-select']")
    expect(target_selects).to_have_count(len(axes), timeout=30000)
    for axis_index, axis in enumerate(axes):
        target = str(axis["target"])
        target_select = target_selects.nth(axis_index)
        target_select.click()
        page.get_by_role("option", name=re.compile(rf"^{re.escape(target)}(\s|\(|$)")).first.click()
        _set_spinbutton_value(page, "Sweep Start", axis["start"], index=axis_index)
        _set_spinbutton_value(page, "Sweep Stop", axis["stop"], index=axis_index)
        _set_spinbutton_value(page, "Sweep Points", axis["points"], index=axis_index)


def _configure_single_axis_sweep(
    page: Page,
    *,
    target: str,
    start: float,
    stop: float,
    points: int,
) -> None:
    _configure_multi_axis_sweep(
        page,
        axes=(
            {
                "target": target,
                "start": start,
                "stop": stop,
                "points": points,
            },
        ),
    )


def _run_and_expect_success(page: Page, *, allow_long_running: bool = False) -> bool:
    page.get_by_role("button", name="Run Simulation").click()
    expect(
        page.get_by_text(
            re.compile(
                (
                    r"Preparing simulation|Checking cached results|"
                    r"Submitting job to Julia worker|Simulation completed successfully"
                ),
                re.IGNORECASE,
            )
        ).first
    ).to_be_visible(timeout=3000)
    success_banner = page.get_by_text("Simulation completed successfully")

    if allow_long_running:
        try:
            expect(success_banner).to_be_visible(timeout=20000)
            expect(page.get_by_text("Numerical solver error", exact=False)).to_have_count(0)
            return True
        except AssertionError:
            try:
                expect(page.get_by_text("Submitting job to Julia worker...")).to_be_visible(
                    timeout=15000
                )
            except AssertionError:
                expect(
                    page.get_by_text("Julia worker still running...", exact=False)
                ).to_be_visible(timeout=20000)
            expect(page.get_by_text("Numerical solver error", exact=False)).to_have_count(0)
            return False

    expect(success_banner).to_be_visible(timeout=180000)
    expect(page.get_by_text("Numerical solver error", exact=False)).to_have_count(0)
    return True


def _assert_log_never_contains(
    log_path: Path,
    needle: str,
    *,
    timeout_seconds: float = 4.0,
) -> None:
    deadline = time.time() + timeout_seconds
    latest = ""
    while time.time() < deadline:
        latest = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
        assert needle not in latest, latest
        time.sleep(0.25)
    latest = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    assert needle not in latest, latest


def _run_post_processing_and_expect_output(page: Page, *, configure_steps: bool = True) -> None:
    def _click_retry(locator: Locator, *, attempts: int = 4) -> None:
        last_error: Exception | None = None
        for _ in range(attempts):
            try:
                expect(locator).to_be_visible(timeout=10000)
                locator.click(timeout=10000)
                return
            except Exception as exc:  # pragma: no cover - browser timing behavior
                last_error = exc
                time.sleep(0.3)
        if last_error is not None:
            raise last_error

    ready_text = "Pipeline output ready. Post Processing Result View is updated."
    post_results_card = _card_by_testid(
        page,
        "post-processing-results-card",
        fallback_text="Post Processing Results",
    )
    post_input_card = _card_by_testid(
        page,
        "post-processing-input-card",
        fallback_text="Run Post Processing",
    )
    run_button = _locator_by_testid(
        page,
        "post-processing-run-button",
        fallback=page.get_by_role("button", name="Run Post Processing"),
    )
    save_button = _locator_by_testid(
        page,
        "post-result-view-save-button",
        fallback=page.get_by_role("button", name="Save Post-Processed Results"),
    )
    post_setup_name = f"E2E Post Setup {uuid.uuid4().hex[:6]}"

    expect(run_button).to_be_visible(timeout=30000)
    expect(post_input_card.get_by_role("button", name="Save Post-Processed Results")).to_have_count(
        0
    )

    if configure_steps:
        post_setup_select = post_input_card.get_by_role("combobox", name="Post-Processing Setup")
        expect(post_setup_select).to_be_visible(timeout=30000)
        post_input_card.get_by_role("button", name="Save Setup").click()
        save_setup_dialog = page.get_by_text("Save Post-Processing Setup")
        expect(save_setup_dialog).to_be_visible(timeout=30000)
        setup_name_input = page.get_by_role("textbox", name="Setup Name")
        setup_name_input.click()
        setup_name_input.fill(post_setup_name)
        page.get_by_role("button", name="Save").last.click()
        expect(save_setup_dialog).to_have_count(0, timeout=30000)

        step_type_select = post_input_card.get_by_role("combobox", name="Step Type")
        step_type_select.click()
        page.get_by_role("option", name="Kron Reduction").click()
        post_input_card.get_by_role("button", name="Add Step").click()

        keep_basis_text = page.get_by_text("Keep Basis Labels")
        select_all_button = page.get_by_role("button", name="Select All").first
        clear_button = page.get_by_role("button", name="Clear").first
        try:
            expect(keep_basis_text).to_be_visible(timeout=10000)
            _click_retry(select_all_button)
            _click_retry(clear_button)
            _click_retry(select_all_button)
        except Exception:
            pass

    _click_retry(run_button)
    expect(
        page.get_by_text(
            re.compile(
                r"Running post-processing pipeline|Pipeline output ready",
                re.IGNORECASE,
            )
        ).first
    ).to_be_visible(timeout=10000)
    expect(
        post_results_card.get_by_text(
            re.compile(
                (
                    r"Updating Post Processing Result View|"
                    r"Result View consumes the latest Post Processing pipeline output node"
                ),
                re.IGNORECASE,
            )
        ).first
    ).to_be_visible(timeout=3000)
    expect(page.get_by_text(ready_text)).to_be_visible(timeout=30000)
    expect(page.get_by_text("Running post-processing pipeline...")).to_have_count(0)
    if save_button.count():
        expect(save_button).to_be_enabled(timeout=30000)

    post_results_card.get_by_role("tab", name="Impedance (Z)").click()
    metric_select = post_results_card.get_by_role("combobox", name="Metric")
    metric_select.click()
    metric_select.press("ArrowDown")
    metric_select.press("Enter")

    post_results_card.get_by_role("button", name="Add Trace").click()
    expect(post_results_card.locator(".js-plotly-plot")).to_have_count(1, timeout=30000)


def _save_raw_simulation_results(page: Page, *, dataset_name: str) -> None:
    raw_results_card = _card_by_testid(
        page,
        "simulation-results-card",
        fallback_text="Simulation Results",
    )
    raw_results_card.get_by_role("button", name="Save Raw Simulation Results").click()
    dialog = page.locator('[role="dialog"]').last
    expect(dialog.get_by_text("Save Simulation Results", exact=True)).to_be_visible(timeout=30000)
    name_input = dialog.get_by_role("textbox", name="New Dataset Name")
    name_input.click()
    name_input.fill(dataset_name)
    dialog.get_by_role("button", name="Save").click()
    expect(page.get_by_text(re.compile(r"Saved .* trace\(s\) to:", re.IGNORECASE))).to_be_visible(
        timeout=30000
    )


def _save_post_processed_results(page: Page, *, dataset_name: str) -> None:
    def _open_save_dialog() -> Locator:
        last_error: Exception | None = None
        for _ in range(4):
            try:
                post_results_card.get_by_role("button", name="Save Post-Processed Results").click(
                    timeout=10000
                )
                dialog = page.locator('[role="dialog"]').last
                expect(dialog.get_by_text("Save Post-Processed Results", exact=True)).to_be_visible(
                    timeout=10000
                )
                return dialog
            except Exception as exc:  # pragma: no cover - browser timing behavior
                last_error = exc
                time.sleep(0.3)
        if last_error is not None:
            raise last_error
        raise AssertionError("Save Post-Processed Results dialog did not open.")

    post_results_card = _card_by_testid(
        page,
        "post-processing-results-card",
        fallback_text="Post Processing Results",
    )
    dialog = _open_save_dialog()
    name_input = dialog.get_by_role("textbox", name="New Dataset Name")
    name_input.click()
    name_input.fill(dataset_name)
    dialog.get_by_role("button", name="Save").click()
    expect(
        page.get_by_text(re.compile(r"Saved .* post-processed trace", re.IGNORECASE))
    ).to_be_visible(timeout=30000)


def _select_active_dataset(page: Page, dataset_name: str) -> None:
    active_selector = page.get_by_role("combobox", name="Active Datasets")
    if active_selector.count() == 0:
        active_selector = page.get_by_role("combobox").first
    expect(active_selector).to_be_visible(timeout=15000)
    active_selector.click()
    page.get_by_role("option", name=dataset_name, exact=True).click()
    page.keyboard.press("Escape")


def _select_option(page: Page, label: str, option_text: str, index: int = 0) -> None:
    select = page.get_by_role("combobox", name=label).nth(index)
    expect(select).to_be_visible(timeout=15000)
    select.click()
    page.get_by_role("option", name=re.compile(rf"^{re.escape(option_text)}")).first.click()


def _characterization_run_bundle_count(dataset_name: str) -> int:
    with get_unit_of_work() as uow:
        dataset = uow.datasets.get_by_name(dataset_name)
        if dataset is None or dataset.id is None:
            return 0
        return len(
            [
                bundle
                for bundle in uow.result_bundles.list_by_dataset(int(dataset.id))
                if bundle.bundle_type == "characterization" and bundle.role == "analysis_run"
            ]
        )


def _latest_characterization_run_bundle(dataset_name: str) -> ResultBundleRecord:
    with get_unit_of_work() as uow:
        dataset = uow.datasets.get_by_name(dataset_name)
        assert dataset is not None, (
            f"Dataset not found for characterization verification: {dataset_name}"
        )
        assert dataset.id is not None, (
            f"Dataset id missing for characterization verification: {dataset_name}"
        )
        bundles = [
            bundle
            for bundle in uow.result_bundles.list_by_dataset(int(dataset.id))
            if bundle.bundle_type == "characterization" and bundle.role == "analysis_run"
        ]
    assert bundles, f"No characterization run bundle found for {dataset_name}"
    return bundles[-1]


def _open_characterization_dataset_scope(
    page: Page,
    *,
    app_base_url: str,
    dataset_name: str,
    analysis_label: str,
    expect_compatible_analysis: bool = True,
) -> None:
    page.goto(f"{app_base_url}/characterization", wait_until="networkidle")
    _select_active_dataset(page, dataset_name)
    expect(
        _card_by_testid(
            page,
            "characterization-source-scope-card",
            fallback_text="Design Scope",
        )
    ).to_be_visible(timeout=30000)
    _select_option(page, "Analysis", analysis_label)
    availability_label = _locator_by_testid(
        page,
        "characterization-availability-label",
        fallback=page.get_by_text(re.compile(r"for current (design )?scope$")).first,
    )
    if expect_compatible_analysis:
        expect(availability_label).to_contain_text(
            re.compile(r"^(Available|Recommended) for current (design )?scope$")
        )
        expect(page.get_by_text("No compatible traces found", exact=False)).to_have_count(0)
    else:
        expect(availability_label).to_contain_text(
            re.compile(r"^Unavailable for current (design )?scope$")
        )


def _select_base_traces_for_characterization(page: Page) -> None:
    page.get_by_role("button", name="Base").click()
    expect(page.get_by_text(re.compile(r"^[1-9]\d* / \d+ selected$")).first).to_be_visible(
        timeout=30000
    )


@pytest.fixture(scope="session")
def validation_matrix_saved_datasets(
    app_base_url: str,
    example_cases: tuple[ExampleCase, ...],
) -> dict[str, ValidationMatrixSavedDataset]:
    case = next(c for c in example_cases if c.slug == "linear_series_lc")
    suffix = uuid.uuid4().hex[:8]
    raw_dataset = ValidationMatrixSavedDataset(
        scenario_id="circuit_simulation_save_read",
        dataset_name=f"E2E-ValidationMatrix-Raw-{suffix}",
        bundle_type="circuit_simulation",
        role="manual_export",
        stage_kind="raw",
        analysis_label=_VALIDATION_MATRIX_ANALYSIS_LABEL,
        expects_compatible_analysis=True,
    )
    post_dataset = ValidationMatrixSavedDataset(
        scenario_id="postprocess_save_read",
        dataset_name=f"E2E-ValidationMatrix-Post-{suffix}",
        bundle_type="simulation_postprocess",
        role="derived_from_simulation",
        stage_kind="postprocess",
        analysis_label=_VALIDATION_MATRIX_ANALYSIS_LABEL,
        expects_compatible_analysis=False,
    )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1400})
        page = context.new_page()
        try:
            page.goto(f"{app_base_url}/simulation", wait_until="networkidle")
            _choose_schema(page, case.schema_name)
            _set_spinbutton_value(page, "Start Freq (GHz)", case.start_ghz)
            _set_spinbutton_value(page, "Stop Freq (GHz)", case.stop_ghz)
            _set_spinbutton_value(page, "Points", case.points)
            _set_spinbutton_value(page, "Nmodulation Harmonics", case.n_mod)
            _set_spinbutton_value(page, "Npump Harmonics", case.n_pump)
            _configure_sources(page, case.sources)
            assert _run_and_expect_success(page) is True

            _save_raw_simulation_results(page, dataset_name=raw_dataset.dataset_name)
            _assert_trace_batch_payload(
                _latest_trace_batch_bundle_for_dataset(
                    dataset_name=raw_dataset.dataset_name,
                    bundle_type=raw_dataset.bundle_type,
                    role=raw_dataset.role,
                ),
                stage_kind=raw_dataset.stage_kind,
                point_count=1,
            )

            _run_post_processing_and_expect_output(page)
            _save_post_processed_results(page, dataset_name=post_dataset.dataset_name)
            _assert_trace_batch_payload(
                _latest_trace_batch_bundle_for_dataset(
                    dataset_name=post_dataset.dataset_name,
                    bundle_type=post_dataset.bundle_type,
                    role=post_dataset.role,
                ),
                stage_kind=post_dataset.stage_kind,
                point_count=1,
            )
        finally:
            context.close()
            browser.close()

    yield {
        "raw": raw_dataset,
        "postprocess": post_dataset,
    }

    with get_unit_of_work() as uow:
        for dataset_name in (raw_dataset.dataset_name, post_dataset.dataset_name):
            dataset = uow.datasets.get_by_name(dataset_name)
            if dataset is not None:
                uow.datasets.delete(dataset)
                uow.commit()


def _select_card_option(
    page: Page,
    card,
    label: str,
    option_text: str,
    index: int = 0,
) -> None:  # type: ignore[no-untyped-def]
    desired = re.sub(r"\s+", "", option_text).lower()
    option_pattern = re.compile(re.escape(option_text), re.IGNORECASE)
    for _attempt in range(3):
        select = card.get_by_role("combobox", name=label).nth(index)
        expect(select).to_be_visible(timeout=15000)
        select.click()
        page.keyboard.type(option_text)
        page.keyboard.press("Enter")
        current_value = (select.input_value() or "").strip()
        current_normalized = re.sub(r"\s+", "", current_value).lower()
        if current_normalized == desired or desired in current_normalized:
            return

        select.click()
        controls_id = select.get_attribute("aria-controls")
        option_scope = page.locator(f"#{controls_id}") if controls_id else page.locator("body")
        options = option_scope.get_by_role("option")
        try:
            for idx_option in range(options.count()):
                option_text_value = options.nth(idx_option).inner_text()
                normalized = re.sub(r"\s+", "", option_text_value).lower()
                if normalized == desired or desired in normalized:
                    options.nth(idx_option).click()
                    return
            options.filter(has_text=option_pattern).first.click()
            return
        except PlaywrightTimeoutError:
            continue

    raise AssertionError(f"Failed to select {option_text!r} for {label!r}")


def _locator_by_testid(page: Page, testid: str, *, fallback):  # type: ignore[no-untyped-def]
    candidate = page.locator(f"[data-testid='{testid}']")
    if candidate.count() > 0:
        return candidate.first
    return fallback


def _card_by_testid(page: Page, testid: str, *, fallback_text: str):  # type: ignore[no-untyped-def]
    return _locator_by_testid(
        page,
        testid,
        fallback=page.locator(".q-card").filter(has_text=fallback_text).first,
    )


def _post_plot_title_and_legend(post_results_card) -> tuple[str, list[str]]:  # type: ignore[no-untyped-def]
    plot = post_results_card.locator(".js-plotly-plot").first
    expect(plot).to_be_visible(timeout=30000)
    payload = plot.evaluate(
        "el => ({ title: String(el.layout?.title?.text || ''), "
        "legend: (el.data || []).map(trace => String(trace.name || '')) })"
    )
    title = str(payload.get("title", ""))
    legend = [str(item) for item in payload.get("legend", [])]
    return (title, legend)


def _plot_y_axis_title(card) -> str:  # type: ignore[no-untyped-def]
    plot = card.locator(".js-plotly-plot").first
    expect(plot).to_be_visible(timeout=30000)
    value = plot.evaluate("el => String(el.layout?.yaxis?.title?.text || '')")
    return str(value)


def _expect_plot_y_axis_title(card, expected: str, *, timeout_seconds: float = 12.0) -> None:  # type: ignore[no-untyped-def]
    deadline = time.time() + timeout_seconds
    latest = ""
    while time.time() < deadline:
        latest = _plot_y_axis_title(card)
        if latest == expected:
            return
        time.sleep(0.2)
    raise AssertionError(f"Expected y-axis title {expected!r}, got {latest!r}")


def _nudge_combobox_option(
    page: Page,
    card,
    label: str,
    *,
    direction: str,
    steps: int,
    index: int = 0,
) -> None:  # type: ignore[no-untyped-def]
    select = card.get_by_role("combobox", name=label).nth(index)
    expect(select).to_be_visible(timeout=15000)
    select.click()
    key = "ArrowUp" if direction == "up" else "ArrowDown"
    for _ in range(max(1, steps)):
        select.press(key)
    select.press("Enter")


def _configure_raw_result_to_y22_real(page: Page) -> None:
    raw_results_card = _card_by_testid(
        page,
        "simulation-results-card",
        fallback_text="Raw Simulation Results",
    )
    raw_results_card.get_by_role("tab", name="Admittance (Y)").click()
    output_port_select = raw_results_card.get_by_role("combobox", name="Output Port")
    output_port_select.click()
    output_port_select.press("ArrowDown")
    output_port_select.press("Enter")
    input_port_select = raw_results_card.get_by_role("combobox", name="Input Port")
    input_port_select.click()
    input_port_select.press("ArrowDown")
    input_port_select.press("Enter")
    expect(raw_results_card.locator(".js-plotly-plot")).to_have_count(1, timeout=30000)


def _read_first_plot_y_value(page: Page) -> float:
    raw_results_card = _card_by_testid(
        page,
        "simulation-results-card",
        fallback_text="Raw Simulation Results",
    )
    plot = raw_results_card.locator(".js-plotly-plot").first
    expect(plot).to_be_visible(timeout=30000)
    plot_handle = plot.element_handle(timeout=30000)
    assert plot_handle is not None
    page.wait_for_function(
        (
            "el => Array.isArray(el?.data)"
            " && el.data.length > 0"
            " && Array.isArray(el.data[0]?.y)"
            " && el.data[0].y.length > 0"
        ),
        arg=plot_handle,
        timeout=30000,
    )
    value = plot.evaluate("el => el.data[0].y[0]")
    return float(value)


def _configure_termination_mode_auto(page: Page) -> None:
    term_card = _card_by_testid(
        page,
        "termination-compensation-card",
        fallback_text="Port Termination Compensation (Optional)",
    )
    expect(term_card).to_be_visible(timeout=30000)
    enable_switch = term_card.get_by_role("switch", name="Enable")
    if enable_switch.count() == 0:
        enable_switch = term_card.get_by_role("checkbox", name="Enable")
    if enable_switch.count() > 0:
        if not enable_switch.first.is_checked():
            enable_switch.first.click()
    else:
        toggle = term_card.locator(".q-toggle").first
        expect(toggle).to_be_visible(timeout=30000)
        classes = str(toggle.get_attribute("class") or "")
        if "q-toggle--truthy" not in classes:
            toggle.click()
    mode_select = term_card.get_by_role("combobox", name="Mode")
    mode_select.click()
    page.get_by_role("option", name="Auto (Schema infer)").click()
    expect(term_card.get_by_text("mode=auto", exact=False).first).to_be_visible(timeout=30000)
    expect(term_card.get_by_text("ports=[1, 2]", exact=False).first).to_be_visible(timeout=30000)


def _configure_termination_mode_manual_custom(page: Page) -> None:
    term_card = _card_by_testid(
        page,
        "termination-compensation-card",
        fallback_text="Port Termination Compensation (Optional)",
    )
    mode_select = term_card.get_by_role("combobox", name="Mode")
    mode_select.click()
    page.get_by_role("option", name="Manual").click()
    port1_resistance = term_card.get_by_role("spinbutton", name=re.compile(r"Port 1 .*Manual R"))
    expect(port1_resistance).to_be_visible(timeout=30000)
    port1_resistance.click()
    port1_resistance.fill("75")
    port1_resistance.press("Enter")
    expect(term_card.get_by_text("mode=manual", exact=False).first).to_be_visible(timeout=30000)
    expect(term_card.get_by_text("p1=75 Ohm (manual)", exact=False).first).to_be_visible(
        timeout=30000
    )


def test_simulation_setup_manager_dialog_crud_and_no_metadata_summary(
    page: Page,
    example_cases: tuple[ExampleCase, ...],
) -> None:
    case = next(c for c in example_cases if c.slug == "linear_series_lc")
    _choose_schema(page, case.schema_name)
    expect(page.get_by_text("Dataset Metadata Summary")).to_have_count(0)

    saved_setup_select = page.get_by_test_id("simulation-saved-setup-select").get_by_role(
        "combobox",
        name="Saved Setup",
    )
    manage_button = _locator_by_testid(
        page,
        "simulation-manage-setups-button",
        fallback=page.get_by_role("button", name="Manage Setups"),
    )
    expect(saved_setup_select).to_be_visible(timeout=30000)
    expect(manage_button).to_be_visible(timeout=30000)

    unique_name = f"E2E Setup {uuid.uuid4().hex[:6]}"
    renamed_name = f"{unique_name} Renamed"
    _set_spinbutton_value(page, "Start Freq (GHz)", 6.1)
    manage_button.click()
    expect(page.get_by_text("Manage Simulation Setups")).to_be_visible(timeout=30000)
    page.get_by_role("textbox", name="New Setup Name").fill(unique_name)
    page.get_by_role("button", name="Add New").click()
    page.get_by_role("button", name="Close").click()

    _set_spinbutton_value(page, "Start Freq (GHz)", 7.2)
    manage_button.click()
    expect(page.get_by_text("Manage Simulation Setups")).to_be_visible(timeout=30000)
    manage_saved_setup_select = page.get_by_role("combobox", name="Saved Setup").last
    manage_saved_setup_select.click()
    page.get_by_role("option", name=unique_name, exact=True).click()
    page.get_by_role("button", name="Load").click()
    expect(page.get_by_text("Manage Simulation Setups")).to_have_count(0, timeout=30000)
    loaded_value = float(
        page.get_by_role("spinbutton", name="Start Freq (GHz)").first.input_value()
    )
    assert loaded_value == pytest.approx(6.1, abs=1e-6)

    manage_button.click()
    expect(page.get_by_text("Manage Simulation Setups")).to_be_visible(timeout=30000)
    manage_saved_setup_select = page.get_by_role("combobox", name="Saved Setup").last
    manage_saved_setup_select.click()
    page.get_by_role("option", name=unique_name, exact=True).click()
    page.get_by_role("textbox", name="Rename To").fill(renamed_name)
    page.get_by_role("button", name="Rename").click()
    expect(page.get_by_text(f"Renamed setup: {renamed_name}", exact=False)).to_be_visible(
        timeout=30000
    )
    page.get_by_role("button", name="Close").click()
    expect(page.get_by_text("Manage Simulation Setups")).to_have_count(0, timeout=30000)

    manage_button.click()
    expect(page.get_by_text("Manage Simulation Setups")).to_be_visible(timeout=30000)
    page.get_by_role("button", name="Delete").click()
    expect(page.get_by_text("Deleted setup.", exact=False)).to_be_visible(timeout=30000)
    page.get_by_role("button", name="Close").click()


@pytest.mark.parametrize(
    "example_case",
    ["linear_series_lc", "jpa_single_pump", "jpa_double_pump"],
)
def test_josephson_example_runs_in_ui(
    page: Page,
    example_cases: tuple[ExampleCase, ...],
    example_case: str,
) -> None:
    """Run each example category through the Simulation UI and assert successful completion."""
    case = next(c for c in example_cases if c.slug == example_case)

    _choose_schema(page, case.schema_name)

    _set_spinbutton_value(page, "Start Freq (GHz)", case.start_ghz)
    _set_spinbutton_value(page, "Stop Freq (GHz)", case.stop_ghz)
    _set_spinbutton_value(page, "Points", case.points)
    _set_spinbutton_value(page, "Nmodulation Harmonics", case.n_mod)
    _set_spinbutton_value(page, "Npump Harmonics", case.n_pump)
    _configure_sources(page, case.sources)

    simulation_completed = _run_and_expect_success(
        page,
        allow_long_running=(case.slug == "jpa_double_pump"),
    )
    if simulation_completed:
        raw_bundle = _latest_trace_batch_bundle_for_circuit(
            circuit_name=case.schema_name,
            bundle_type="circuit_simulation",
            role="cache",
        )
        _assert_trace_batch_payload(raw_bundle, stage_kind="raw", point_count=1)
        _run_post_processing_and_expect_output(page)
        saved_dataset_name = f"E2E Post Saved {uuid.uuid4().hex[:8]}"
        _save_post_processed_results(page, dataset_name=saved_dataset_name)
        post_bundle = _latest_trace_batch_bundle_for_circuit(
            circuit_name=case.schema_name,
            bundle_type="simulation_postprocess",
        )
        _assert_trace_batch_payload(
            post_bundle,
            stage_kind="postprocess",
            point_count=1,
            parent_batch_id=int(raw_bundle.id or 0),
        )


def test_flux_pumped_jpa_bias_sweep_result_view_flow(
    page: Page,
    example_cases: tuple[ExampleCase, ...],
    tmp_path: Path,
) -> None:
    case = next(c for c in example_cases if c.slug == "flux_pumped_jpa_bias_sweep")
    _choose_schema(page, case.schema_name)
    _set_spinbutton_value(page, "Start Freq (GHz)", case.start_ghz)
    _set_spinbutton_value(page, "Stop Freq (GHz)", case.stop_ghz)
    _set_spinbutton_value(page, "Points", 21)
    _set_spinbutton_value(page, "Nmodulation Harmonics", 2)
    _set_spinbutton_value(page, "Npump Harmonics", 4)
    _configure_sources(page, case.sources)
    _configure_multi_axis_sweep(
        page,
        axes=(
            {
                "target": "sources[1].current_amp",
                "start": 140.2e-6,
                "stop": 140.4e-6,
                "points": 3,
            },
            {
                "target": "sources[2].current_amp",
                "start": 0.69e-6,
                "stop": 0.71e-6,
                "points": 3,
            },
        ),
    )

    page.get_by_role("button", name="Run Simulation").click()
    expect(page.get_by_text("Parameter sweep completed successfully", exact=False)).to_be_visible(
        timeout=180000
    )
    raw_bundle = _latest_trace_batch_bundle_for_circuit(
        circuit_name=case.schema_name,
        bundle_type="circuit_simulation",
        role="cache",
    )
    _assert_trace_batch_payload(raw_bundle, stage_kind="raw", point_count=9)

    raw_results_card = _card_by_testid(
        page,
        "simulation-results-card",
        fallback_text="Simulation Results",
    )
    expect(
        raw_results_card.get_by_role("button", name="Save Raw Simulation Results")
    ).to_be_visible(timeout=30000)
    raw_results_card.get_by_role("button", name="Save Raw Simulation Results").click()
    expect(page.get_by_text("cached parameter-sweep bundle", exact=False)).to_be_visible(
        timeout=30000
    )
    page.get_by_role("button", name="Cancel").last.click()

    sweep_view = _locator_by_testid(
        page,
        "simulation-sweep-results-view",
        fallback=raw_results_card.get_by_text("Parameter Sweep Compare").first,
    )
    expect(sweep_view).to_be_visible(timeout=30000)

    sweep_plot = _locator_by_testid(
        page,
        "simulation-sweep-plot",
        fallback=raw_results_card.locator(".js-plotly-plot").last,
    )
    expect(sweep_plot).to_be_visible(timeout=30000)

    compare_axis_select = _locator_by_testid(
        page,
        "simulation-sweep-view-axis-select",
        fallback=sweep_view.get_by_role("combobox", name="Compare Axis"),
    )
    compare_axis_select.click()
    compare_axis_select.press("ArrowDown")
    compare_axis_select.press("Enter")

    fixed_axis_select = _locator_by_testid(
        page,
        "simulation-sweep-fixed-axis-select-1",
        fallback=sweep_view.get_by_role("combobox", name=re.compile(r"^Fixed: ")).first,
    )
    fixed_axis_select.click()
    fixed_axis_select.press("ArrowDown")
    fixed_axis_select.press("Enter")

    add_trace_button = _locator_by_testid(
        page,
        "simulation-sweep-add-trace-button",
        fallback=sweep_view.get_by_role("button", name="Add Trace"),
    )
    add_trace_button.click()
    trace_cards = page.locator("[data-testid^='simulation-sweep-trace-card-']")
    expect(trace_cards).to_have_count(2, timeout=30000)
    second_sweep_value_select = _locator_by_testid(
        page,
        "simulation-sweep-sweep-value-select-2",
        fallback=trace_cards.nth(1).get_by_role("combobox", name="Sweep Value"),
    )
    second_sweep_value_select.click()
    second_sweep_value_select.press("ArrowDown")
    second_sweep_value_select.press("Enter")
    expect(sweep_plot).to_be_visible(timeout=30000)

    page.get_by_role("button", name="Run Simulation").click()
    expect(page.get_by_text("Loaded cached parameter sweep payload", exact=False)).to_be_visible(
        timeout=60000
    )
    page.screenshot(path=str(tmp_path / "flux_pumped_jpa_bias_sweep_view.png"), full_page=True)


def test_cached_flux_pumped_jpa_sweep_can_run_post_processing(
    page: Page,
    example_cases: tuple[ExampleCase, ...],
) -> None:
    case = next(c for c in example_cases if c.slug == "flux_pumped_jpa_bias_sweep")
    _choose_schema(page, case.schema_name)
    _set_spinbutton_value(page, "Start Freq (GHz)", case.start_ghz)
    _set_spinbutton_value(page, "Stop Freq (GHz)", case.stop_ghz)
    _set_spinbutton_value(page, "Points", 21)
    _set_spinbutton_value(page, "Nmodulation Harmonics", 2)
    _set_spinbutton_value(page, "Npump Harmonics", 4)
    _configure_sources(page, case.sources)
    _configure_multi_axis_sweep(
        page,
        axes=(
            {
                "target": "sources[1].current_amp",
                "start": 140.2e-6,
                "stop": 140.4e-6,
                "points": 3,
            },
            {
                "target": "sources[2].current_amp",
                "start": 0.69e-6,
                "stop": 0.71e-6,
                "points": 3,
            },
        ),
    )

    page.get_by_role("button", name="Run Simulation").click()
    expect(page.get_by_text("Parameter sweep completed successfully", exact=False)).to_be_visible(
        timeout=180000
    )
    page.get_by_role("button", name="Run Simulation").click()
    expect(page.get_by_text("Loaded cached parameter sweep payload", exact=False)).to_be_visible(
        timeout=60000
    )

    _run_post_processing_and_expect_output(page)
    expect(
        _locator_by_testid(
            page,
            "post-processed-sweep-results-view",
            fallback=page.get_by_text("Post-Processed Sweep Result View"),
        )
    ).to_be_visible(timeout=30000)
    expect(
        page.get_by_text(
            "Post-processing parameter sweep detected:",
            exact=False,
        )
    ).to_be_visible(timeout=30000)


def test_simulation_reload_and_disconnect_do_not_reuse_deleted_root_client(
    page: Page,
    app_server: AppServer,
    example_cases: tuple[ExampleCase, ...],
    tmp_path: Path,
) -> None:
    case = next(c for c in example_cases if c.slug == "jpa_double_pump")

    _choose_schema(page, case.schema_name)
    _set_spinbutton_value(page, "Start Freq (GHz)", case.start_ghz)
    _set_spinbutton_value(page, "Stop Freq (GHz)", case.stop_ghz)
    _set_spinbutton_value(page, "Points", case.points)
    _set_spinbutton_value(page, "Nmodulation Harmonics", case.n_mod)
    _set_spinbutton_value(page, "Npump Harmonics", case.n_pump)
    _configure_sources(page, case.sources)

    _run_and_expect_success(page, allow_long_running=True)
    screenshot_path = tmp_path / "simulation_deleted_client_lifecycle.png"
    page.screenshot(path=str(screenshot_path), full_page=True)
    page.reload(wait_until="domcontentloaded")
    expect(page.get_by_text("Simulation Setup")).to_be_visible(timeout=30000)
    page.goto("about:blank", wait_until="load")
    _assert_log_never_contains(
        app_server.log_path,
        "Client has been deleted but is still being used",
    )
    print(f"LIFECYCLE_SCREENSHOT={screenshot_path}")
    print(f"LIFECYCLE_LOG={app_server.log_path}")


def test_port_termination_compensation_modes_in_ui(
    page: Page,
    example_cases: tuple[ExampleCase, ...],
    tmp_path: Path,
) -> None:
    case = next(c for c in example_cases if c.slug == "two_port_compensation")

    _choose_schema(page, case.schema_name)
    _set_spinbutton_value(page, "Start Freq (GHz)", case.start_ghz)
    _set_spinbutton_value(page, "Stop Freq (GHz)", case.stop_ghz)
    _set_spinbutton_value(page, "Points", case.points)
    _set_spinbutton_value(page, "Nmodulation Harmonics", case.n_mod)
    _set_spinbutton_value(page, "Npump Harmonics", case.n_pump)
    _configure_sources(page, case.sources)

    assert _run_and_expect_success(page) is True
    raw_results_card = _card_by_testid(
        page,
        "simulation-results-card",
        fallback_text="Raw Simulation Results",
    )
    expect(raw_results_card.locator(".js-plotly-plot")).to_have_count(1, timeout=30000)
    baseline_raw_s = _read_first_plot_y_value(page)
    baseline_log_count = page.get_by_text(
        "Simulation completed successfully",
        exact=False,
    ).count()
    page.screenshot(path=str(tmp_path / "termination_case_baseline.png"), full_page=True)

    _configure_termination_mode_auto(page)
    auto_raw_s = _read_first_plot_y_value(page)
    assert auto_raw_s == pytest.approx(baseline_raw_s, abs=1e-9)
    assert (
        page.get_by_text("Simulation completed successfully", exact=False).count()
        == baseline_log_count
    )
    expect(
        page.get_by_text("Termination compensation updated without Julia rerun", exact=False)
    ).to_be_visible(timeout=30000)
    page.screenshot(path=str(tmp_path / "termination_case_auto.png"), full_page=True)

    raw_results_card.get_by_role("tab", name="Admittance (Y)").click()
    _select_card_option(page, raw_results_card, "Output Port", "1")
    _select_card_option(page, raw_results_card, "Input Port", "1")
    _select_card_option(page, raw_results_card, "Y Source", "Raw Y")
    y_source_select = raw_results_card.get_by_role("combobox", name="Y Source")
    assert y_source_select.input_value() == "Raw Y"
    y_source_select.click()
    y_source_select.press("ArrowDown")
    y_source_select.press("Enter")
    assert y_source_select.input_value() in {"Raw Y", "PTC Y"}

    _configure_termination_mode_manual_custom(page)
    assert y_source_select.input_value() in {"Raw Y", "PTC Y"}

    raw_results_card.get_by_role("tab", name="Impedance (Z)").click()
    _select_card_option(page, raw_results_card, "Output Port", "1")
    _select_card_option(page, raw_results_card, "Input Port", "1")
    _select_card_option(page, raw_results_card, "Z Source", "Raw Z")
    z_source_select = raw_results_card.get_by_role("combobox", name="Z Source")
    assert z_source_select.input_value() == "Raw Z"
    z_source_select.click()
    z_source_select.press("ArrowDown")
    z_source_select.press("Enter")
    assert z_source_select.input_value() in {"Raw Z", "PTC Z"}
    assert (
        page.get_by_text("Simulation completed successfully", exact=False).count()
        == baseline_log_count
    )
    page.screenshot(path=str(tmp_path / "termination_case_manual.png"), full_page=True)

    _run_post_processing_and_expect_output(page)
    post_results_card = _card_by_testid(
        page,
        "post-processing-results-card",
        fallback_text="Post Processing Results",
    )
    expect(post_results_card.locator(".js-plotly-plot")).to_have_count(1, timeout=30000)
    page.screenshot(path=str(tmp_path / "termination_case_post_processing.png"), full_page=True)


def test_post_processing_hfss_comparable_status(
    page: Page,
    example_cases: tuple[ExampleCase, ...],
) -> None:
    case = next(c for c in example_cases if c.slug == "two_port_compensation")
    _choose_schema(page, case.schema_name)
    _set_spinbutton_value(page, "Start Freq (GHz)", case.start_ghz)
    _set_spinbutton_value(page, "Stop Freq (GHz)", case.stop_ghz)
    _set_spinbutton_value(page, "Points", case.points)
    _set_spinbutton_value(page, "Nmodulation Harmonics", case.n_mod)
    _set_spinbutton_value(page, "Npump Harmonics", case.n_pump)
    _configure_sources(page, case.sources)

    simulation_completed = _run_and_expect_success(page, allow_long_running=True)
    if not simulation_completed:
        try:
            expect(page.get_by_text("Simulation completed successfully")).to_be_visible(
                timeout=180000
            )
            expect(page.get_by_text("Numerical solver error", exact=False)).to_have_count(0)
        except AssertionError:
            pytest.skip("Two-port compensation simulation is still running in Julia worker.")
    _configure_termination_mode_auto(page)

    post_input_card = _card_by_testid(
        page,
        "post-processing-input-card",
        fallback_text="Run Post Processing",
    )
    _select_card_option(page, post_input_card, "Input Y Source", "Raw Y")
    _locator_by_testid(
        page,
        "post-processing-run-button",
        fallback=post_input_card.get_by_role("button", name="Run Post Processing"),
    ).click()
    expect(page.get_by_text("HFSS Comparable: No", exact=False)).to_be_visible(timeout=30000)
    expect(
        page.get_by_text("Coordinate Transformation step is missing", exact=False).first
    ).to_be_visible(timeout=30000)

    input_source_select = post_input_card.get_by_role("combobox", name="Input Y Source")
    input_source_select.click()
    input_source_select.press("ArrowDown")
    input_source_select.press("Enter")
    assert input_source_select.input_value() in {"Raw Y", "PTC Y"}
    _select_card_option(page, post_input_card, "Step Type", "Coordinate Transformation")
    post_input_card.get_by_role("button", name="Add Step").click()
    expect(page.get_by_text("Step 1 · Coordinate Transformation", exact=False).first).to_be_visible(
        timeout=30000
    )


def test_post_processed_result_view_uses_trace_card_port_labels_for_matrix_names(
    page: Page,
    example_cases: tuple[ExampleCase, ...],
    tmp_path: Path,
) -> None:
    case = next(c for c in example_cases if c.slug == "three_port_basis_labels")

    _choose_schema(page, case.schema_name)
    _set_spinbutton_value(page, "Start Freq (GHz)", case.start_ghz)
    _set_spinbutton_value(page, "Stop Freq (GHz)", case.stop_ghz)
    _set_spinbutton_value(page, "Points", case.points)
    _set_spinbutton_value(page, "Nmodulation Harmonics", case.n_mod)
    _set_spinbutton_value(page, "Npump Harmonics", case.n_pump)
    _configure_sources(page, case.sources)
    assert _run_and_expect_success(page) is True

    post_input_card = _card_by_testid(
        page,
        "post-processing-input-card",
        fallback_text="Run Post Processing",
    )
    _select_card_option(page, post_input_card, "Step Type", "Coordinate Transformation")
    post_input_card.get_by_role("button", name="Add Step").click()

    _locator_by_testid(
        page,
        "post-processing-run-button",
        fallback=post_input_card.get_by_role("button", name="Run Post Processing"),
    ).click()
    post_results_card = _card_by_testid(
        page,
        "post-processing-results-card",
        fallback_text="Post Processing Results",
    )
    expect(post_results_card.locator(".js-plotly-plot")).to_have_count(1, timeout=60000)
    post_results_card.get_by_role("tab", name="Impedance (Z)").click()

    def _assert_name(expected_name: str, screenshot_suffix: str) -> None:
        deadline = time.time() + 12.0
        matched = False
        title = ""
        legend: list[str] = []
        while time.time() < deadline:
            title, legend = _post_plot_title_and_legend(post_results_card)
            if expected_name in title and expected_name in legend:
                matched = True
                break
            time.sleep(0.25)
        assert matched, (
            f"Expected {expected_name} in title+legend, got title={title!r}, legend={legend!r}"
        )
        page.screenshot(
            path=str(tmp_path / f"post_processed_matrix_name_{screenshot_suffix}.png"),
            full_page=True,
        )

    _select_card_option(page, post_results_card, "Output Port", "dm")
    _select_card_option(page, post_results_card, "Input Port", "dm")
    _assert_name("Z_dm_dm", "dm_to_dm")
    _select_card_option(page, post_results_card, "Input Port", "cm")
    _assert_name("Z_dm_cm", "dm_to_cm")
    _select_card_option(page, post_results_card, "Input Port", "3")
    _assert_name("Z_dm_3", "dm_to_3")


def test_result_view_axis_titles_follow_y_z_family_switches(
    page: Page,
    example_cases: tuple[ExampleCase, ...],
) -> None:
    case = next(c for c in example_cases if c.slug == "three_port_basis_labels")
    _choose_schema(page, case.schema_name)
    _set_spinbutton_value(page, "Start Freq (GHz)", case.start_ghz)
    _set_spinbutton_value(page, "Stop Freq (GHz)", case.stop_ghz)
    _set_spinbutton_value(page, "Points", case.points)
    _set_spinbutton_value(page, "Nmodulation Harmonics", case.n_mod)
    _set_spinbutton_value(page, "Npump Harmonics", case.n_pump)
    _configure_sources(page, case.sources)
    assert _run_and_expect_success(page) is True

    raw_results_card = _card_by_testid(
        page,
        "simulation-results-card",
        fallback_text="Raw Simulation Results",
    )
    raw_results_card.get_by_role("tab", name="Admittance (Y)").click()
    _select_card_option(page, raw_results_card, "Metric", "Real")
    _expect_plot_y_axis_title(raw_results_card, "Real (S)")
    raw_results_card.get_by_role("tab", name="Impedance (Z)").click()
    _select_card_option(page, raw_results_card, "Metric", "Real")
    _expect_plot_y_axis_title(raw_results_card, "Real (Ohm)")
    raw_results_card.get_by_role("tab", name="Admittance (Y)").click()
    _select_card_option(page, raw_results_card, "Metric", "Real")
    _expect_plot_y_axis_title(raw_results_card, "Real (S)")

    post_input_card = _card_by_testid(
        page,
        "post-processing-input-card",
        fallback_text="Run Post Processing",
    )
    _select_card_option(page, post_input_card, "Step Type", "Coordinate Transformation")
    post_input_card.get_by_role("button", name="Add Step").click()
    _locator_by_testid(
        page,
        "post-processing-run-button",
        fallback=post_input_card.get_by_role("button", name="Run Post Processing"),
    ).click()

    post_results_card = _card_by_testid(
        page,
        "post-processing-results-card",
        fallback_text="Post Processing Results",
    )
    expect(post_results_card.locator(".js-plotly-plot")).to_have_count(1, timeout=60000)
    post_results_card.get_by_role("tab", name="Admittance (Y)").click()
    _select_card_option(page, post_results_card, "Metric", "Real")
    _expect_plot_y_axis_title(post_results_card, "Real (S)")
    post_results_card.get_by_role("tab", name="Impedance (Z)").click()
    _select_card_option(page, post_results_card, "Metric", "Real")
    _expect_plot_y_axis_title(post_results_card, "Real (Ohm)")
    post_results_card.get_by_role("tab", name="Admittance (Y)").click()
    _select_card_option(page, post_results_card, "Metric", "Real")
    _expect_plot_y_axis_title(post_results_card, "Real (S)")


@pytest.mark.parametrize(
    ("scenario_key", "expected_stage_kind"),
    [
        ("raw", "raw"),
        ("postprocess", "postprocess"),
    ],
)
def test_phase2_validation_matrix_save_read_paths(
    page: Page,
    app_base_url: str,
    validation_matrix_saved_datasets: dict[str, ValidationMatrixSavedDataset],
    scenario_key: str,
    expected_stage_kind: str,
) -> None:
    saved_dataset = validation_matrix_saved_datasets[scenario_key]

    saved_bundle = _latest_trace_batch_bundle_for_dataset(
        dataset_name=saved_dataset.dataset_name,
        bundle_type=saved_dataset.bundle_type,
        role=saved_dataset.role,
    )
    _assert_trace_batch_payload(
        saved_bundle,
        stage_kind=expected_stage_kind,
        point_count=1,
    )

    _open_characterization_dataset_scope(
        page,
        app_base_url=app_base_url,
        dataset_name=saved_dataset.dataset_name,
        analysis_label=saved_dataset.analysis_label,
        expect_compatible_analysis=saved_dataset.expects_compatible_analysis,
    )


def test_phase2_validation_matrix_characterization_over_saved_traces(
    page: Page,
    app_base_url: str,
    validation_matrix_saved_datasets: dict[str, ValidationMatrixSavedDataset],
) -> None:
    saved_dataset = validation_matrix_saved_datasets["raw"]
    _open_characterization_dataset_scope(
        page,
        app_base_url=app_base_url,
        dataset_name=saved_dataset.dataset_name,
        analysis_label=saved_dataset.analysis_label,
        expect_compatible_analysis=saved_dataset.expects_compatible_analysis,
    )
    _select_base_traces_for_characterization(page)

    run_button = _locator_by_testid(
        page,
        "characterization-run-analysis-button",
        fallback=page.get_by_role("button", name="Run Selected Analysis"),
    )
    expect(run_button).to_be_enabled(timeout=15000)
    before_count = _characterization_run_bundle_count(saved_dataset.dataset_name)
    run_button.click()
    deadline = time.time() + 60.0
    while time.time() < deadline:
        if _characterization_run_bundle_count(saved_dataset.dataset_name) > before_count:
            break
        time.sleep(0.5)
    else:
        raise AssertionError("Timed out waiting for characterization over saved traces.")

    run_bundle = _latest_characterization_run_bundle(saved_dataset.dataset_name)
    input_trace_ids = run_bundle.source_meta.get("input_trace_ids")
    assert isinstance(input_trace_ids, list)
    assert len(input_trace_ids) > 0
    assert run_bundle.source_meta.get("input_scope") == "all_dataset_records"
    page.screenshot(path=str(_VALIDATION_MATRIX_SCREENSHOT_PATH), full_page=True)


def test_saved_postprocessed_design_can_rerun_post_processing(
    page: Page,
    app_base_url: str,
    example_cases: tuple[ExampleCase, ...],
    validation_matrix_saved_datasets: dict[str, ValidationMatrixSavedDataset],
) -> None:
    saved_dataset = validation_matrix_saved_datasets["postprocess"]
    case = next(c for c in example_cases if c.slug == "linear_series_lc")

    page.goto(f"{app_base_url}/simulation", wait_until="networkidle")
    _choose_schema(page, case.schema_name)
    _select_active_dataset(page, saved_dataset.dataset_name)
    _run_post_processing_and_expect_output(page, configure_steps=False)

    post_results_card = _card_by_testid(
        page,
        "post-processing-results-card",
        fallback_text="Post Processing Results",
    )
    expect(post_results_card.locator(".js-plotly-plot")).to_have_count(1, timeout=30000)


def test_saved_raw_design_can_run_post_processing_after_reload(
    page: Page,
    app_base_url: str,
    example_cases: tuple[ExampleCase, ...],
    validation_matrix_saved_datasets: dict[str, ValidationMatrixSavedDataset],
) -> None:
    saved_dataset = validation_matrix_saved_datasets["raw"]
    case = next(c for c in example_cases if c.slug == "linear_series_lc")

    page.goto(f"{app_base_url}/simulation", wait_until="networkidle")
    _choose_schema(page, case.schema_name)
    _select_active_dataset(page, saved_dataset.dataset_name)
    _run_post_processing_and_expect_output(page, configure_steps=False)

    post_results_card = _card_by_testid(
        page,
        "post-processing-results-card",
        fallback_text="Post Processing Results",
    )
    expect(post_results_card.locator(".js-plotly-plot")).to_have_count(1, timeout=30000)


@pytest.mark.parametrize("scenario", _BLOCKED_VALIDATION_SCENARIOS)
def test_phase2_validation_matrix_blocked_slots(
    scenario: BlockedValidationScenario,
) -> None:
    raise AssertionError(
        f"Blocked validation scenario should stay skipped until implemented: {scenario.scenario_id}"
    )
