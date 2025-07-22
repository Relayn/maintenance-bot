"""
Обработчики общих команд, доступных всем пользователям.
"""

import json
import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from app.core.decorators import require_role
from app.services.user_service import UserService

logger = logging.getLogger(__name__)


@require_role("admin", "housekeeper", "technician")
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик команды /start.

    Приветствует авторизованного пользователя и обновляет его имя в базе, если оно изменилось.
    """
    user = update.effective_user
    db_user = context.user_data["db_user"]
    user_service: UserService = context.application.bot_data["user_service"]

    # Получаем актуальное имя пользователя из Telegram
    current_name = user.first_name or user.username

    # Проверяем, нужно ли обновить имя
    if db_user.name != current_name:
        logger.info(
            f"Updating name for user {user.id}: '{db_user.name}' -> '{current_name}'"
        )
        user_service.update_user_name(user.id, current_name)
        # Обновляем и локальную копию, чтобы показать актуальные данные
        db_user.name = current_name

    logger.info(
        f"Authorized user {user.id} ({db_user.name}) with role '{db_user.role}' started the bot."
    )

    await update.message.reply_html(
        rf"Привет, {db_user.name}! 👋"
        f"\n\nВаш статус: <b>авторизован</b>."
        f"\nВаша роль: <b>{db_user.role}</b>."
    )


async def show_my_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет пользователю его собственный Telegram ID."""
    user = update.effective_user
    if not user:
        return

    logger.info(f"User {user.id} requested their ID.")
    await update.message.reply_text(
        f"Ваш Telegram ID: <code>{user.id}</code>\n\n"
        f"Пожалуйста, отправьте этот ID вашему администратору для получения доступа.",
        parse_mode="HTML",
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Логирует ошибки и отправляет уведомление администраторам.
    """

    logger.error("Exception while handling an update:", exc_info=context.error)

    # Собираем информацию для отладочного сообщения
    if isinstance(update, Update):
        update_str = json.dumps(update.to_dict(), indent=2, ensure_ascii=False)
    else:
        update_str = str(update)

    message = (
        f"‼️ **Произошла ошибка в боте** ‼️\n\n"
        f"<pre>update = {update_str}</pre>\n\n"
        f"<pre>context.chat_data = {str(context.chat_data)}</pre>\n\n"
        f"<pre>context.user_data = {str(context.user_data)}</pre>\n\n"
        f"<pre>{context.error}</pre>"
    )

    # Отправляем уведомление всем администраторам
    for admin_id in context.bot_data.get("settings", {}).admin_ids:
        try:
            # Разделяем сообщение, если оно слишком длинное
            if len(message) > 4096:
                for x in range(0, len(message), 4096):
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=message[x : x + 4096],
                        parse_mode=ParseMode.HTML,
                    )
            else:
                await context.bot.send_message(
                    chat_id=admin_id, text=message, parse_mode=ParseMode.HTML
                )
        except Exception as e:
            logger.error(f"Failed to send error message to admin {admin_id}: {e}")


async def unauthorized_user_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Обрабатывает сообщения от пользователей, которых нет в базе.
    """
    user = update.effective_user
    if not user:
        return

    logger.warning(
        f"Received message from unauthorized user {user.id} ({user.first_name})."
    )

    # Отправляем уведомление администраторам
    admin_message = (
        f"⚠️ Получено сообщение от неавторизованного пользователя:\n\n"
        f"Имя: {user.first_name}\n"
        f"Username: @{user.username}\n"
        f"ID: <code>{user.id}</code>\n\n"
        f"Чтобы добавить его, используйте команду:\n"
        f"<code>/adduser {user.id} <роль></code>"
    )
    for admin_id in context.bot_data.get("settings", {}).admin_ids:
        try:
            await context.bot.send_message(
                chat_id=admin_id, text=admin_message, parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Failed to send unauthorized notice to admin {admin_id}: {e}")

    # Отвечаем самому пользователю
    await update.message.reply_text(
        "Здравствуйте! К сожалению, у вас нет доступа к этому боту. "
        "Пожалуйста, обратитесь к администратору."
    )
