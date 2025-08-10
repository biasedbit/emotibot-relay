"""
Shared data models for the EmotiBot Web service.

This module defines the core domain models used across multiple layers
of the application (business logic, CLI, API).
"""

from pydantic import BaseModel, Field


class Mood(BaseModel):
    """Represents a mood state."""

    value: str = Field(..., description="The current mood value")
    timestamp: float | None = Field(
        None, description="Unix timestamp when mood was set"
    )
