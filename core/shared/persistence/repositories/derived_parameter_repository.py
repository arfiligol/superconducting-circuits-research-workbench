"""Repository for DerivedParameter operations."""

from typing import Any, cast

from sqlmodel import Session, select

from core.shared.persistence.models import (
    DerivedParameter,
    resolve_scope_ids_for_compatibility_write,
)


class DerivedParameterRepository:
    """Repository for DerivedParameter operations."""

    def __init__(self, session: Session):
        self._session = session

    def list_by_design(self, design_id: int) -> list[DerivedParameter]:
        """List all derived parameters for one design scope."""
        statement = select(DerivedParameter).where(DerivedParameter.design_id == design_id)
        return list(self._session.exec(statement).all())

    def list_by_dataset(self, dataset_id: int) -> list[DerivedParameter]:
        """Legacy dataset-scoped wrapper."""
        statement = select(DerivedParameter).where(DerivedParameter.dataset_id == dataset_id)
        return list(self._session.exec(statement).all())

    def add(self, param: DerivedParameter) -> DerivedParameter:
        """Add a new derived parameter."""
        resolve_scope_ids_for_compatibility_write(param)
        self._session.add(param)
        return param

    def get_by_design_and_name(self, design_id: int, name: str) -> DerivedParameter | None:
        """Get the first parameter with exact design/name."""
        statement = select(DerivedParameter).where(
            DerivedParameter.design_id == design_id,
            DerivedParameter.name == name,
        )
        return self._session.exec(statement).first()

    def get_by_dataset_and_name(self, dataset_id: int, name: str) -> DerivedParameter | None:
        """Legacy dataset-scoped wrapper."""
        statement = select(DerivedParameter).where(
            DerivedParameter.dataset_id == dataset_id,
            DerivedParameter.name == name,
        )
        return self._session.exec(statement).first()

    def get_by_design_method_and_name(
        self,
        design_id: int,
        method: str,
        name: str,
    ) -> DerivedParameter | None:
        """Get the first parameter with exact design/method/name."""
        statement = select(DerivedParameter).where(
            DerivedParameter.design_id == design_id,
            DerivedParameter.method == method,
            DerivedParameter.name == name,
        )
        return self._session.exec(statement).first()

    def get_by_dataset_method_and_name(
        self,
        dataset_id: int,
        method: str,
        name: str,
    ) -> DerivedParameter | None:
        """Legacy dataset-scoped wrapper."""
        statement = select(DerivedParameter).where(
            DerivedParameter.dataset_id == dataset_id,
            DerivedParameter.method == method,
            DerivedParameter.name == name,
        )
        return self._session.exec(statement).first()

    def get_first_by_design_method_name_prefix(
        self,
        design_id: int,
        method: str,
        name_prefix: str,
    ) -> DerivedParameter | None:
        """Get the first parameter by design/method and name prefix."""
        statement = (
            select(DerivedParameter)
            .where(
                DerivedParameter.design_id == design_id,
                DerivedParameter.method == method,
                cast(Any, DerivedParameter.name).like(f"{name_prefix}%"),
            )
            .order_by(cast(Any, DerivedParameter.id))
        )
        return self._session.exec(statement).first()

    def get_first_by_dataset_method_name_prefix(
        self,
        dataset_id: int,
        method: str,
        name_prefix: str,
    ) -> DerivedParameter | None:
        """Legacy dataset-scoped wrapper."""
        statement = (
            select(DerivedParameter)
            .where(
                DerivedParameter.dataset_id == dataset_id,
                DerivedParameter.method == method,
                cast(Any, DerivedParameter.name).like(f"{name_prefix}%"),
            )
            .order_by(cast(Any, DerivedParameter.id))
        )
        return self._session.exec(statement).first()

    def list_all(self) -> list[DerivedParameter]:
        """List all derived parameters."""
        statement = select(DerivedParameter).order_by(cast(Any, DerivedParameter.id))
        return list(self._session.exec(statement).all())

    def get(self, id: int) -> DerivedParameter | None:
        """Get derived parameter by ID."""
        return self._session.get(DerivedParameter, id)

    def delete(self, param: DerivedParameter) -> None:
        """Delete a derived parameter."""
        self._session.delete(param)

    def reorder_id(self, old_id: int, new_id: int) -> DerivedParameter:
        """Change derived parameter ID."""
        if self.get(new_id):
            raise ValueError(f"Target ID {new_id} already exists.")

        param = self.get(old_id)
        if not param:
            raise ValueError(f"Source ID {old_id} not found.")

        from sqlmodel import update

        from core.shared.persistence.models import DerivedParameter

        self._session.exec(
            update(DerivedParameter)
            .where(cast(Any, DerivedParameter.id) == old_id)
            .values(id=new_id)
        )

        self._session.expire(param)
        updated = self.get(new_id)
        if updated is None:
            raise ValueError(f"Target ID {new_id} was not persisted.")
        return updated
