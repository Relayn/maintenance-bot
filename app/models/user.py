"""
Модели данных, связанные с пользователем.
"""

from pydantic import BaseModel, Field


class User(BaseModel):
    """
    Модель пользователя, представляющая строку из Google-таблицы.

    Атрибуты:
        telegram_id (int): Уникальный идентификатор пользователя в Telegram.
        name (str): Имя пользователя (может быть username или first_name).
        role (str): Роль пользователя в системе (admin, housekeeper, etc.).
    """

    telegram_id: int = Field(..., description="Telegram User ID")
    name: str = Field(..., description="User's name or username")
    role: str = Field(..., description="User's role in the system")
