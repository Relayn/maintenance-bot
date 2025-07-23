"""
Обработчики административных команд.
"""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from app.core.decorators import require_role
from app.models.user import User
from app.services.user_service import UserService

logger = logging.getLogger(__name__)


@require_role("admin")
async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Выводит список всех пользователей в виде интерактивных карточек с кнопками.
    Доступно только для администраторов.
    """
    message = update.effective_message
    user_service: UserService = context.application.bot_data["user_service"]
    all_users = user_service.get_all_users()

    if not all_users:
        await message.reply_text("👥 Список пользователей пуст.")
        return

    await message.reply_text(text="--- 👥 Список пользователей ---")
    for user in all_users:
        # Для каждого пользователя создаем свою клавиатуру
        keyboard = [
            [
                InlineKeyboardButton(
                    "🗑️ Удалить", callback_data=f"delete_user:{user.telegram_id}"
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        user_info = (
            f"👤 <b>{user.name}</b>\n"
            f"   ID: <code>{user.telegram_id}</code>\n"
            f"   Роль: <i>{user.role}</i>"
        )
        await message.reply_text(
            text=user_info, parse_mode=ParseMode.HTML, reply_markup=reply_markup
        )


@require_role("admin")
async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Добавляет нового пользователя по его ID.
    Использование: /adduser <telegram_id> <роль>
    Пример: /adduser 123456789 housekeeper
    """
    message = update.effective_message

    if len(context.args) != 2:
        await message.reply_text(
            "⚠️ **Неверный формат.**\n\n"
            "Чтобы добавить пользователя, отправьте команду в формате:\n"
            "`/adduser <ID пользователя> <роль>`\n\n"
            "Пример:\n"
            "`/adduser 123456789 housekeeper`\n\n"
            "(Вы можете скопировать пример выше и изменить данные)"
        )
        return

    try:
        user_id_to_add = int(context.args[0])
    except ValueError:
        await message.reply_text("⚠️ **Ошибка:** Telegram ID должен быть числом.")
        return

    role = context.args[1].lower()
    user_service: UserService = context.application.bot_data["user_service"]

    if user_service.get_user_by_id(user_id_to_add):
        await message.reply_text(
            f"Пользователь с ID <code>{user_id_to_add}</code> уже существует в системе."
        )
        return

    name_placeholder = f"User_{user_id_to_add}"
    new_user = User(telegram_id=user_id_to_add, name=name_placeholder, role=role)

    try:
        user_service.add_user(new_user)
        await message.reply_text(
            f"✅ Пользователь с ID <code>{new_user.telegram_id}</code> успешно добавлен с ролью `{role}`."
        )
        logger.info(
            f"Admin {update.effective_user.id} added user {new_user.telegram_id} with role {role}."
        )
    except Exception as e:
        await message.reply_text("❌ Произошла ошибка при добавлении пользователя.")
        logger.error(f"Failed to add user: {e}", exc_info=True)


@require_role("admin")
async def delete_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Удаляет пользователя по его ID.
    Использование: /deluser <telegram_id>
    Пример: /deluser 123456789
    """
    message = update.effective_message

    if not context.args:
        await message.reply_text(
            "⚠️ **Неверный формат.**\n\n"
            "Чтобы удалить пользователя, отправьте команду в формате:\n"
            "`/deluser <ID пользователя>`\n\n"
            "Пример:\n"
            "`/deluser 123456789`"
        )
        return

    try:
        user_id_to_delete = int(context.args[0])
    except ValueError:
        await message.reply_text("⚠️ **Ошибка:** Telegram ID должен быть числом.")
        return

    user_service: UserService = context.application.bot_data["user_service"]

    if user_service.delete_user(user_id_to_delete):
        await message.reply_text(
            f"✅ Пользователь с ID <code>{user_id_to_delete}</code> успешно удален."
        )
        logger.info(
            f"Admin {update.effective_user.id} deleted user {user_id_to_delete}."
        )
    else:
        await message.reply_text(
            f"⚠️ Пользователь с ID <code>{user_id_to_delete}</code> не найден в системе."
        )


async def admin_user_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Обрабатывает нажатия на inline-кнопки в карточках пользователей.
    """
    query = update.callback_query
    await query.answer()  # Обязательно, чтобы убрать "часики" на кнопке

    # Парсим callback_data. Формат: "действие:id_пользователя"
    action, user_id_str = query.data.split(":", 1)
    user_id = int(user_id_str)

    user_service: UserService = context.application.bot_data["user_service"]

    if action == "delete_user":
        # Проверяем, что кнопку нажал администратор
        # Это дополнительный слой безопасности
        admin_user = user_service.get_user_by_id(query.from_user.id)
        if not (admin_user and admin_user.role == "admin"):
            await query.edit_message_text(text="⚠️ У вас нет прав для этого действия.")
            return

        logger.info(f"Admin {query.from_user.id} initiated deletion of user {user_id}.")
        if user_service.delete_user(user_id):
            await query.edit_message_text(
                text=f"✅ Пользователь <code>{user_id}</code> удален."
            )
        else:
            await query.edit_message_text(
                text=f"⚠️ Не удалось удалить. Пользователь <code>{user_id}</code> не найден."
            )
