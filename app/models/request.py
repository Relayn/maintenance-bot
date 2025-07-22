"""
Модели данных, связанные с заявкой на ремонт.
"""

import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

# Определяем возможные статусы заявки для строгой типизации
RequestStatus = Literal["creating", "new", "in_progress", "completed", "cancelled"]


class MaintenanceRequest(BaseModel):
    """
    Модель заявки на техническое обслуживание.
    """

    request_uuid: uuid.UUID = Field(default_factory=uuid.uuid4)
    status: RequestStatus = "new"
    location: str | None = None
    issue_type: str | None = None
    photo_before_url: str | None = None
    reporter_id: int
    reporter_name: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    assignee_id: int | None = None
    assignee_name: str | None = None
    accepted_at: datetime | None = None
    completed_at: datetime | None = None

    # Добавляем поле для хранения file_id фотографии в Telegram
    # Оно не будет сохраняться в Google Sheets, но нужно для диалога
    photo_file_id: str | None = None
