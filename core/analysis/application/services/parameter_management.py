"""Service for managing DerivedParameters."""

from typing import Any, cast

from core.analysis.application.dto.parameter_dtos import (
    DerivedParameterDetailDTO,
    DerivedParameterSummaryDTO,
)
from core.shared.persistence import get_unit_of_work
from core.shared.persistence.models import DerivedParameter, DeviceType


def _normalize_parameter_value(value: float | list[float]) -> float:
    if isinstance(value, list):
        if not value:
            raise ValueError("DerivedParameter value list cannot be empty.")
        return float(value[0])
    return float(value)


def _normalize_parameter_device_type(device_type: str | None) -> DeviceType:
    if device_type is None:
        return DeviceType.OTHER
    try:
        return DeviceType(device_type)
    except ValueError:
        return DeviceType.OTHER


class ParameterManagementService:
    """Service to manage derived parameters."""

    def list_params(self) -> list[DerivedParameterSummaryDTO]:
        """List all parameters."""
        with get_unit_of_work() as uow:
            params = uow.derived_params.list_all()
            return [self._to_summary(p) for p in params]

    def create_or_update_param(
        self,
        dataset_id: int,
        name: str,
        value: float | list[float],
        unit: str = "",
        device_type: str | None = None,
        method: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> DerivedParameterDetailDTO:
        """Create or update a derived parameter for a dataset."""
        with get_unit_of_work() as uow:
            # Simple linear search for now; optimization possible later via specific repo methods
            existing = next(
                (
                    p
                    for p in uow.derived_params.list_all()
                    if p.dataset_id == dataset_id and p.name == name
                ),
                None,
            )
            normalized_value = _normalize_parameter_value(value)
            normalized_device_type = _normalize_parameter_device_type(device_type)
            if existing:
                existing.value = normalized_value
                existing.unit = unit
                existing.method = method
                existing.device_type = normalized_device_type
                if extra is not None:
                    existing.extra = extra
                param = existing
            else:
                param = DerivedParameter(
                    dataset_id=dataset_id,
                    name=name,
                    value=normalized_value,
                    unit=unit,
                    device_type=normalized_device_type,
                    method=method,
                    extra=extra or {},
                )
                uow.derived_params.add(param)
            uow.commit()
            return self._to_detail(param)

    def get_param(self, id: int) -> DerivedParameterDetailDTO | None:
        """Get parameter details."""
        with get_unit_of_work() as uow:
            param = uow.derived_params.get(id)
            return self._to_detail(param) if param else None

    def delete_param(self, id: int) -> bool:
        """Delete a parameter."""
        with get_unit_of_work() as uow:
            param = uow.derived_params.get(id)
            if not param:
                return False

            uow.derived_params.delete(param)
            uow.commit()
            return True

    def auto_reorder(self) -> int:
        """Automatically reorder IDs to be sequential (1..N)."""
        count = 0
        with get_unit_of_work() as uow:
            params = sorted(uow.derived_params.list_all(), key=lambda x: x.id or 0)
            for idx, param in enumerate(params, start=1):
                if param.id is None or param.id == idx:
                    continue
                try:
                    uow.derived_params.reorder_id(param.id, idx)
                    count += 1
                except ValueError:
                    pass
            uow.commit()
            return count

    def _to_summary(self, param: DerivedParameter) -> DerivedParameterSummaryDTO:
        return DerivedParameterSummaryDTO(
            id=cast(int, param.id),
            dataset_id=param.dataset_id,
            name=param.name,
            value=param.value,
            unit=param.unit,
            device_type=param.device_type,
        )

    def _to_detail(self, param: DerivedParameter) -> DerivedParameterDetailDTO:
        return DerivedParameterDetailDTO(
            id=cast(int, param.id),
            dataset_id=param.dataset_id,
            name=param.name,
            value=param.value,
            unit=param.unit,
            device_type=param.device_type,
            method=param.method,
            extra=param.extra or {},
            created_at=param.created_at,
        )
