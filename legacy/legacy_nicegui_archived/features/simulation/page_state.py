"""Page authority and block-state coordination for the Simulation workbench."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ExecutionLineage:
    """Execution lineage pointers shared across simulation page blocks."""

    simulation_task_id: int | None = None
    simulation_batch_id: int | None = None
    post_processing_task_id: int | None = None
    post_processing_batch_id: int | None = None
    source_simulation_batch_id: int | None = None
    result_scope: str | None = None
    run_generation: int = 0


@dataclass
class BlockState:
    """Minimal local block lifecycle state."""

    draft_revision: int = 0
    session_revision: int = 0
    authority_revision: int = 0
    view_revision: int = 0
    is_dirty: bool = False
    stale_reason: str | None = None

    def mark_draft(self) -> None:
        self.draft_revision += 1
        self.is_dirty = True

    def mark_session(self) -> None:
        self.session_revision += 1

    def mark_authority(self) -> None:
        self.authority_revision += 1

    def mark_view(self) -> None:
        self.view_revision += 1

    def clear_dirty(self) -> None:
        self.is_dirty = False

    def set_stale(self, reason: str | None) -> None:
        self.stale_reason = str(reason).strip() if reason else None

    def clear_stale(self) -> None:
        self.stale_reason = None


@dataclass
class SimulationSetupBlockState:
    """Draft/session/view-model state for the setup editor block."""

    lifecycle: BlockState = field(default_factory=BlockState)
    termination_summary: str = ""
    termination_warning: str = ""


@dataclass
class RunControlBlockState:
    """Draft/session/view-model state for command controls."""

    lifecycle: BlockState = field(default_factory=BlockState)
    active_command: str | None = None
    is_submitting: bool = False


@dataclass
class SimulationResultBlockState:
    """Authority/view-model state for raw simulation results."""

    lifecycle: BlockState = field(default_factory=BlockState)
    needs_preview_refresh: bool = False


@dataclass
class PostProcessingInputBlockState:
    """Authority/view-model state for post-processing input configuration."""

    lifecycle: BlockState = field(default_factory=BlockState)
    needs_refresh: bool = False


@dataclass
class PostProcessingResultBlockState:
    """Authority/view-model state for post-processing results."""

    lifecycle: BlockState = field(default_factory=BlockState)


@dataclass
class SimulationPageAuthority:
    """Page-global authority cursor for the Simulation workbench."""

    active_design_id: int | None = None
    lineage: ExecutionLineage = field(default_factory=ExecutionLineage)
    restored_simulation_batch_id: int | None = None
    restored_post_processing_batch_id: int | None = None


@dataclass
class SimulationPageBlocks:
    """Top-level block stores owned by the page coordinator."""

    setup: SimulationSetupBlockState = field(default_factory=SimulationSetupBlockState)
    run_control: RunControlBlockState = field(default_factory=RunControlBlockState)
    simulation_result: SimulationResultBlockState = field(default_factory=SimulationResultBlockState)
    post_processing_input: PostProcessingInputBlockState = field(
        default_factory=PostProcessingInputBlockState
    )
    post_processing_result: PostProcessingResultBlockState = field(
        default_factory=PostProcessingResultBlockState
    )


@dataclass
class SimulationPageCoordinator:
    """Single coordination point for block state and execution lineage."""

    authority: SimulationPageAuthority = field(default_factory=SimulationPageAuthority)
    blocks: SimulationPageBlocks = field(default_factory=SimulationPageBlocks)

    def set_active_design(self, design_id: int | None) -> None:
        self.authority.active_design_id = int(design_id) if design_id is not None else None

    def record_simulation_dispatch(self, *, task_id: int | None, trace_batch_id: int | None) -> None:
        self.authority.lineage.simulation_task_id = task_id
        self.authority.lineage.simulation_batch_id = trace_batch_id
        self.authority.lineage.result_scope = (
            f"task:{int(task_id)}" if task_id is not None else "latest"
        )
        self.authority.lineage.run_generation += 1
        self.blocks.run_control.lifecycle.mark_authority()
        self.blocks.run_control.active_command = "run_simulation"
        self.blocks.run_control.is_submitting = False
        self.blocks.simulation_result.lifecycle.mark_authority()
        self.blocks.simulation_result.lifecycle.clear_stale()
        self.blocks.post_processing_input.lifecycle.mark_authority()
        self.blocks.post_processing_input.needs_refresh = True
        self.blocks.post_processing_result.lifecycle.set_stale(
            "Simulation output changed. Re-run post-processing to refresh processed results."
        )

    def sync_simulation_authority(
        self,
        *,
        task_id: int | None,
        trace_batch_id: int | None,
    ) -> None:
        self.authority.lineage.simulation_task_id = task_id
        self.authority.lineage.simulation_batch_id = trace_batch_id
        if task_id is not None:
            self.authority.lineage.result_scope = f"task:{int(task_id)}"
        elif trace_batch_id is not None:
            self.authority.lineage.result_scope = f"batch:{int(trace_batch_id)}"
        self.blocks.run_control.lifecycle.mark_authority()
        self.blocks.simulation_result.lifecycle.mark_authority()
        self.blocks.post_processing_input.lifecycle.mark_authority()

    def record_post_processing_dispatch(
        self,
        *,
        task_id: int | None,
        trace_batch_id: int | None,
        source_batch_id: int | None,
    ) -> None:
        self.authority.lineage.post_processing_task_id = task_id
        self.authority.lineage.post_processing_batch_id = trace_batch_id
        self.authority.lineage.source_simulation_batch_id = source_batch_id
        self.blocks.run_control.lifecycle.mark_authority()
        self.blocks.run_control.active_command = "run_post_processing"
        self.blocks.run_control.is_submitting = False
        self.blocks.post_processing_input.lifecycle.mark_authority()
        self.blocks.post_processing_input.needs_refresh = False
        self.blocks.post_processing_result.lifecycle.mark_authority()
        self.blocks.post_processing_result.lifecycle.clear_stale()

    def sync_post_processing_authority(
        self,
        *,
        task_id: int | None,
        trace_batch_id: int | None,
        source_batch_id: int | None,
    ) -> None:
        self.authority.lineage.post_processing_task_id = task_id
        self.authority.lineage.post_processing_batch_id = trace_batch_id
        self.authority.lineage.source_simulation_batch_id = source_batch_id
        self.blocks.run_control.lifecycle.mark_authority()
        self.blocks.post_processing_input.lifecycle.mark_authority()
        self.blocks.post_processing_result.lifecycle.mark_authority()

    def record_simulation_restore(self, *, batch_id: int | None) -> None:
        self.authority.restored_simulation_batch_id = batch_id
        self.authority.lineage.simulation_batch_id = batch_id
        self.authority.lineage.source_simulation_batch_id = batch_id
        if batch_id is not None:
            self.authority.lineage.result_scope = f"batch:{int(batch_id)}"
        self.blocks.simulation_result.lifecycle.mark_authority()
        self.blocks.post_processing_input.lifecycle.mark_authority()
        self.blocks.post_processing_input.needs_refresh = False

    def record_post_processing_restore(
        self,
        *,
        batch_id: int | None,
        source_batch_id: int | None,
    ) -> None:
        self.authority.restored_post_processing_batch_id = batch_id
        self.authority.lineage.post_processing_batch_id = batch_id
        self.authority.lineage.source_simulation_batch_id = source_batch_id
        self.blocks.post_processing_result.lifecycle.mark_authority()
        self.blocks.post_processing_result.lifecycle.clear_stale()

    def clear_authority(self) -> None:
        self.authority = SimulationPageAuthority()
        self.blocks.run_control.lifecycle.mark_authority()
        self.blocks.simulation_result.lifecycle.mark_authority()
        self.blocks.post_processing_input.lifecycle.mark_authority()
        self.blocks.post_processing_result.lifecycle.mark_authority()

    def set_termination_summary(self, *, summary: str, warning: str = "") -> None:
        self.blocks.setup.termination_summary = summary
        self.blocks.setup.termination_warning = warning
        self.blocks.setup.lifecycle.mark_view()

    def mark_setup_changed(
        self,
        *,
        reason: str,
        refresh_simulation_preview: bool,
        refresh_post_processing_input: bool,
        mark_post_processing_result_stale: bool = True,
    ) -> None:
        self.blocks.setup.lifecycle.mark_draft()
        self.blocks.simulation_result.needs_preview_refresh = refresh_simulation_preview
        if refresh_simulation_preview:
            self.blocks.simulation_result.lifecycle.mark_view()
        self.blocks.post_processing_input.needs_refresh = refresh_post_processing_input
        if refresh_post_processing_input:
            self.blocks.post_processing_input.lifecycle.mark_view()
        if mark_post_processing_result_stale:
            self.blocks.post_processing_result.lifecycle.set_stale(reason)
            self.blocks.post_processing_result.lifecycle.mark_view()

    def consume_simulation_preview_refresh(self) -> bool:
        should_refresh = self.blocks.simulation_result.needs_preview_refresh
        self.blocks.simulation_result.needs_preview_refresh = False
        return should_refresh

    def consume_post_processing_input_refresh(self) -> bool:
        should_refresh = self.blocks.post_processing_input.needs_refresh
        self.blocks.post_processing_input.needs_refresh = False
        return should_refresh

    def clear_post_processing_result_stale(self) -> None:
        self.blocks.post_processing_result.lifecycle.clear_stale()

    @property
    def post_processing_result_stale_reason(self) -> str | None:
        return self.blocks.post_processing_result.lifecycle.stale_reason
