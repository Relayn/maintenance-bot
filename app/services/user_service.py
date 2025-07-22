"""
Сервисный модуль для управления пользователями.

Реализует логику получения пользователей из Google-таблицы,
а также кэширование для повышения производительности и отказоустойчивости.
"""

import logging
import time
from typing import Optional

from app.models.user import User
from app.services.google_api import GoogleAPIService

logger = logging.getLogger(__name__)


class UserService:
    """
    Сервис для работы с данными пользователей.
    """

    def __init__(self, google_api: GoogleAPIService, cache_ttl_seconds: int = 60):
        self.google_api = google_api
        self._cache_ttl = cache_ttl_seconds
        self._user_cache: list[User] | None = None
        self._cache_timestamp: float = 0.0

    def get_all_users(self) -> list[User]:
        current_time = time.time()
        if (
            self._user_cache is not None
            and (current_time - self._cache_timestamp) < self._cache_ttl
        ):
            logger.debug("Returning users from cache.")
            return self._user_cache

        logger.info("Cache is expired or empty. Fetching users from Google Sheet...")
        try:
            users_sheet = self.google_api.get_users_worksheet()
            records = users_sheet.get_all_records()
            self._user_cache = [User(**record) for record in records]
            self._cache_timestamp = current_time
            logger.info(
                f"Successfully fetched and cached {len(self._user_cache)} users."
            )
            return self._user_cache
        except Exception as e:
            logger.error(f"Failed to fetch users from Google Sheet: {e}", exc_info=True)
            if self._user_cache is not None:
                logger.warning("Returning stale user cache due to fetch failure.")
                return self._user_cache
            return []

    def get_user_by_id(self, telegram_id: int) -> Optional[User]:
        all_users = self.get_all_users()
        for user in all_users:
            if user.telegram_id == telegram_id:
                return user
        return None

    async def add_user(self, user: User) -> None:
        await self.google_api.add_user(user.model_dump())
        self._user_cache = None
        self._cache_timestamp = 0
        logger.info(f"User cache cleared after adding user {user.telegram_id}.")

    async def delete_user(self, telegram_id: int) -> bool:
        deleted = await self.google_api.delete_user(telegram_id)
        if deleted:
            self._user_cache = None
            self._cache_timestamp = 0
            logger.info(f"User cache cleared after deleting user {telegram_id}.")
        return deleted

    async def update_user_name(self, telegram_id: int, new_name: str) -> bool:
        updated = await self.google_api.update_user_name(telegram_id, new_name)
        if updated:
            self._user_cache = None
            self._cache_timestamp = 0
            logger.info(
                f"User cache cleared after updating name for user {telegram_id}."
            )
        return updated
