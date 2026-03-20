"""Service for managing Tags."""

from typing import Any, cast

from core.analysis.application.dto.tag_dtos import TagDTO
from core.shared.persistence import get_unit_of_work
from core.shared.persistence.models import Tag


class TagManagementService:
    """Service to manage tags."""

    def list_tags(self) -> list[TagDTO]:
        """List all tags."""
        with get_unit_of_work() as uow:
            tags = uow.tags.list_all()
            return [self._to_dto(t) for t in tags]

    def get_tag(self, identifier: str) -> TagDTO | None:
        """Get tag by ID or Name."""
        with get_unit_of_work() as uow:
            tag = self._find_tag(uow, identifier)
            return self._to_dto(tag) if tag else None

    def create_tag(self, name: str) -> TagDTO:
        """Create a new tag."""
        with get_unit_of_work() as uow:
            tag = uow.tags.get_or_create(name)
            uow.commit()
            return self._to_dto(tag)

    def update_tag(self, identifier: str, new_name: str) -> TagDTO | None:
        """Update a tag name."""
        with get_unit_of_work() as uow:
            tag = self._find_tag(uow, identifier)
            if not tag:
                return None

            tag.name = new_name
            updated = uow.tags.update(tag)
            return self._to_dto(updated)

    def delete_tag(self, identifier: str) -> bool:
        """Delete a tag."""
        with get_unit_of_work() as uow:
            tag = self._find_tag(uow, identifier)
            if not tag:
                return False

            uow.tags.delete(tag)
            uow.commit()
            return True

    def auto_reorder(self) -> int:
        """Automatically reorder IDs to be sequential (1..N)."""
        count = 0
        with get_unit_of_work() as uow:
            tags = sorted(uow.tags.list_all(), key=lambda x: x.id or 0)
            for idx, tag in enumerate(tags, start=1):
                if tag.id is None or tag.id == idx:
                    continue
                try:
                    uow.tags.reorder_id(tag.id, idx)
                    count += 1
                except ValueError:
                    pass
            uow.commit()
            return count

    def _find_tag(self, uow: object, identifier: str) -> Tag | None:
        typed_uow = cast(Any, uow)
        if identifier.isdigit():
            return typed_uow.tags.get(int(identifier))
        return typed_uow.tags.get_by_name(identifier)

    def _to_dto(self, tag: Tag) -> TagDTO:
        return TagDTO(id=cast(int, tag.id), name=tag.name)
