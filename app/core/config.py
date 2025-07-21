"""
Модуль конфигурации проекта.

Загружает настройки из переменных окружения с помощью Pydantic Settings.
Обеспечивает централизованный и безопасный доступ к конфигурационным данным.
"""
from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Основные настройки приложения.

    Атрибуты:
        bot_token (str): Секретный токен для доступа к Telegram Bot API.
        admin_ids_str (str): Список Telegram ID администраторов в виде строки.
        admin_ids (list[int]): Сгенерированный список ID администраторов.
        google_sheet_id (str): ID Google-таблицы для хранения заявок.
        google_drive_folder_id (str): ID папки на Google Drive для хранения фото.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # --- Telegram Bot Settings ---
    bot_token: str = Field(..., description="Telegram Bot API Token")
    # 1. Читаем переменную ADMIN_IDS из .env как простую строку
    admin_ids_str: str = Field(
        ...,
        alias='ADMIN_IDS',
        description="List of admin Telegram IDs, comma-separated"
    )

    # 2. Создаем вычисляемое поле, которое будет доступно как `settings.admin_ids`
    @computed_field
    @property
    def admin_ids(self) -> list[int]:
        """Преобразует строку admin_ids_str в список целых чисел."""
        if not self.admin_ids_str:
            return []
        return [int(item.strip()) for item in self.admin_ids_str.split(',')]

    # --- Google API Settings ---
    google_sheet_id: str = Field(..., description="Google Sheet ID for requests")
    google_drive_folder_id: str = Field(
        ..., description="Google Drive Folder ID for photos"
    )


# Создаем единственный экземпляр настроек, который будет использоваться во всем приложении
settings = Settings()