"""Pydantic DTO Schemas for Follow-Up Task Management (WS-14, TASK-1401)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.followup import FollowUpStatus


class FollowUpCreate(BaseModel):
    """Input payload schema for creating a new follow-up task."""

    lead_id: uuid.UUID = Field(..., description="Target sales lead UUID")
    assigned_user_id: uuid.UUID | None = Field(
        default=None, description="Optional assigned sales agent UUID"
    )
    title: str = Field(..., min_length=1, max_length=255, description="Actionable task title")
    description: str | None = Field(default=None, description="Detailed task notes or context")
    due_at: datetime = Field(..., description="Scheduled due timestamp (UTC)")


class FollowUpUpdate(BaseModel):
    """Input payload schema for updating an existing follow-up task."""

    title: str | None = Field(default=None, min_length=1, max_length=255, description="Task title")
    description: str | None = Field(default=None, description="Task description notes")
    due_at: datetime | None = Field(default=None, description="Due timestamp (UTC)")
    status: FollowUpStatus | str | None = Field(
        default=None, description="Task status (Pending, Completed, Cancelled)"
    )
    assigned_user_id: uuid.UUID | None = Field(
        default=None, description="Assigned sales agent UUID"
    )


class FollowUpRead(BaseModel):
    """Response schema representing a follow-up task record."""

    id: uuid.UUID = Field(..., description="Unique UUIDv7 identifier")
    tenant_id: uuid.UUID = Field(..., description="Tenant organization UUID")
    lead_id: uuid.UUID = Field(..., description="Associated sales lead UUID")
    assigned_user_id: uuid.UUID | None = Field(default=None, description="Assigned user UUID")
    title: str = Field(..., description="Task title")
    description: str | None = Field(default=None, description="Task description")
    due_at: datetime = Field(..., description="Scheduled due timestamp")
    status: str = Field(..., description="Current status (Pending, Completed, Cancelled)")
    reminder_sent: bool = Field(..., description="Whether reminder notification was emitted")
    completed_at: datetime | None = Field(default=None, description="Completion timestamp")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record update timestamp")

    model_config = ConfigDict(from_attributes=True)
