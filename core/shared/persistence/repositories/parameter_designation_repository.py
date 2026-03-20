"""Repository for ParameterDesignation operations."""

from typing import Any, cast

from sqlmodel import Session, select

from core.shared.persistence.models import (
    ParameterDesignation,
    resolve_scope_ids_for_compatibility_write,
)


class ParameterDesignationRepository:
    """Repository for ParameterDesignation operations."""

    def __init__(self, session: Session):
        self._session = session

    def list_by_design(self, design_id: int) -> list[ParameterDesignation]:
        """List all designations for one design scope."""
        statement = (
            select(ParameterDesignation)
            .where(ParameterDesignation.design_id == design_id)
            .order_by(cast(Any, ParameterDesignation.id))
        )
        return list(self._session.exec(statement).all())

    def list_by_dataset(self, dataset_id: int) -> list[ParameterDesignation]:
        """Legacy dataset-scoped wrapper."""
        statement = (
            select(ParameterDesignation)
            .where(ParameterDesignation.dataset_id == dataset_id)
            .order_by(cast(Any, ParameterDesignation.id))
        )
        return list(self._session.exec(statement).all())

    def list_all(self) -> list[ParameterDesignation]:
        """List all designations."""
        statement = select(ParameterDesignation).order_by(cast(Any, ParameterDesignation.id))
        return list(self._session.exec(statement).all())

    def find_unique_by_design(
        self,
        *,
        design_id: int,
        designated_name: str,
        source_analysis_type: str,
        source_parameter_name: str,
        exclude_id: int | None = None,
    ) -> ParameterDesignation | None:
        """Find one designation by its logical uniqueness key."""
        statement = select(ParameterDesignation).where(
            ParameterDesignation.design_id == design_id,
            ParameterDesignation.designated_name == designated_name,
            ParameterDesignation.source_analysis_type == source_analysis_type,
            ParameterDesignation.source_parameter_name == source_parameter_name,
        )
        if exclude_id is not None:
            statement = statement.where(ParameterDesignation.id != exclude_id)
        return self._session.exec(statement).first()

    def find_unique(
        self,
        *,
        dataset_id: int,
        designated_name: str,
        source_analysis_type: str,
        source_parameter_name: str,
        exclude_id: int | None = None,
    ) -> ParameterDesignation | None:
        """Legacy dataset-scoped wrapper."""
        statement = select(ParameterDesignation).where(
            ParameterDesignation.dataset_id == dataset_id,
            ParameterDesignation.designated_name == designated_name,
            ParameterDesignation.source_analysis_type == source_analysis_type,
            ParameterDesignation.source_parameter_name == source_parameter_name,
        )
        if exclude_id is not None:
            statement = statement.where(ParameterDesignation.id != exclude_id)
        return self._session.exec(statement).first()

    def add(self, designation: ParameterDesignation) -> ParameterDesignation:
        """Add one designation."""
        resolve_scope_ids_for_compatibility_write(designation)
        self._session.add(designation)
        return designation

    def delete(self, designation: ParameterDesignation) -> None:
        """Delete one designation."""
        self._session.delete(designation)
