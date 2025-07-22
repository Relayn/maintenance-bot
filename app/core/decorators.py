"""
Декораторы для проверки авторизации и прав доступа.
"""

import logging
from functools import wraps
from typing import Any, Callable, Coroutine

from telegram import Update
from telegram.ext import ContextTypes

from app.services.user_service import UserService

logger = logging.getLogger(__name__)


def require_role(*roles: str) -> Callable:
    """
    Декоратор для проверки, что пользователь имеет одну из указанных ролей.

    Args:
        *roles: Список строк с названиями ролей, которым разрешен доступ.

    Returns:
        Декоратор, который можно применить к обработчику python-telegram-bot.
    """

    def decorator(
        func: Callable[[Update, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]],
    ):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            user = update.effective_user
            if not user:
                return  # Не должно происходить в обычных чатах

            user_service: UserService = context.application.bot_data["user_service"]
            db_user = user_service.get_user_by_id(user.id)

            if db_user and db_user.role in roles:
                # Сохраняем данные о пользователе в контекст для удобного доступа
                context.user_data["db_user"] = db_user
                return await func(update, context)
            else:
                role_str = db_user.role if db_user else "Unauthorized"
                logger.warning(
                    f"Unauthorized access attempt by user {user.id} ({user.username}). "
                    f"User role: '{role_str}'. Required roles: {roles}"
                )
                # Отвечаем на callback_query, если он есть, иначе в чат
                if update.callback_query:
                    await update.callback_query.answer(
                        "⛔️ У вас нет доступа для этого действия.", show_alert=True
                    )
                elif update.effective_message:
                    await update.effective_message.reply_text(
                        "⛔️ У вас нет доступа для выполнения этой команды."
                    )

        return wrapper

    return decorator
