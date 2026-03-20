"""Repository for Tag operations."""

from typing import Any, cast

from sqlmodel import Session, select

from core.shared.persistence.models import Tag


class TagRepository:
    """Repository for Tag operations."""

    def __init__(self, session: Session):
        self._session = session

    def get_or_create(self, name: str) -> Tag:
        """Get existing tag or create new one."""
        statement = select(Tag).where(Tag.name == name)
        tag = self._session.exec(statement).first()
        if tag is None:
            tag = Tag(name=name)
            self._session.add(tag)
        return tag

    def list_all(self) -> list[Tag]:
        """List all tags."""
        statement = select(Tag).order_by(cast(Any, Tag.id))
        return list(self._session.exec(statement).all())

    def get(self, id: int) -> Tag | None:
        """Get tag by ID."""
        return self._session.get(Tag, id)

    def get_by_name(self, name: str) -> Tag | None:
        """Get tag by name."""
        statement = select(Tag).where(cast(Any, Tag.name) == name)
        return self._session.exec(statement).first()

    def update(self, tag: Tag) -> Tag:
        """Update a tag."""
        self._session.add(tag)
        self._session.commit()
        self._session.refresh(tag)
        return tag

    def delete(self, tag: Tag) -> None:
        """Delete a tag."""
        self._session.delete(tag)

    def reorder_id(self, old_id: int, new_id: int) -> Tag:
        """Change tag ID and update associations."""
        if self.get(new_id):
            raise ValueError(f"Target ID {new_id} already exists.")

        tag = self.get(old_id)
        if not tag:
            raise ValueError(f"Source ID {old_id} not found.")

        # Create new tag with TEMP NAME
        temp_name = f"{tag.name}_TEMP_{new_id}"
        new_tag = Tag(id=new_id, name=temp_name)
        self._session.add(new_tag)
        self._session.flush()

        # Update link table
        from sqlmodel import update

        from core.shared.persistence.models import DatasetTagLink

        self._session.exec(
            update(DatasetTagLink)
            .where(cast(Any, DatasetTagLink.tag_id) == old_id)
            .values(tag_id=new_id)
        )

        original_name = tag.name
        self._session.delete(tag)
        self._session.flush()

        # Restore name
        new_tag.name = original_name
        self._session.add(new_tag)
        self._session.flush()

        return new_tag
