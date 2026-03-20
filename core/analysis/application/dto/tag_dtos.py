"""Data Transfer Objects for Tag Management."""

from pydantic import BaseModel


class TagDTO(BaseModel):
    """Data Transfer Object for Tag."""

    id: int
    name: str
