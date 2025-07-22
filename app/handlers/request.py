"""
Обработчики для создания и управления заявками на ремонт.
"""

import logging

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
)

from app.core.config import settings
from app.core.decorators import require_role
from app.models.request import MaintenanceRequest
from app.services.google_api import GoogleAPIService
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

# --- Константы для сообщений ---
SUCCESS_MESSAGE = "✅ Ваша заявка успешно создана и отправлена в техническую службу."

# Определяем состояния диалога
(LOCATION, ISSUE_TYPE, PHOTO, CONFIRMATION) = range(4)


@require_role("housekeeper", "admin")
async def new_request_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начинает диалог создания новой заявки."""
    message = update.effective_message
    user = update.effective_user
    context.user_data["current_request"] = MaintenanceRequest(
        reporter_id=user.id, reporter_name=user.first_name or user.username
    )

    await message.reply_text(
        "Начинаем создание новой заявки.\n\n"
        "<b>Шаг 1/3:</b> Введите местоположение (например, 'Номер 101' или 'Лобби').",
        parse_mode="HTML",
    )
    return LOCATION


async def get_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает местоположение и запрашивает тип поломки."""
    message = update.effective_message
    location_text = message.text
    context.user_data["current_request"].location = location_text

    # Создаем клавиатуру с типами поломок из конфига
    keyboard = [[issue] for issue in settings.issue_types]
    reply_markup = ReplyKeyboardMarkup(
        keyboard, one_time_keyboard=True, resize_keyboard=True
    )

    await message.reply_text(
        f"Местоположение: <b>{location_text}</b>\n\n"
        "<b>Шаг 2/3:</b> Выберите тип поломки с помощью кнопок ниже.",
        reply_markup=reply_markup,
        parse_mode="HTML",
    )
    return ISSUE_TYPE


async def get_issue_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает тип поломки и запрашивает фото."""
    message = update.effective_message
    issue_type_text = message.text

    # Проверяем, что пользователь выбрал один из предложенных вариантов
    if issue_type_text not in settings.issue_types:
        await message.reply_text(
            "Пожалуйста, выберите тип поломки, используя предложенные кнопки."
        )
        return ISSUE_TYPE  # Остаемся на том же шаге

    context.user_data["current_request"].issue_type = issue_type_text

    await message.reply_text(
        f"Тип поломки: <b>{issue_type_text}</b>\n\n"
        "<b>Шаг 3/3:</b> Прикрепите одну фотографию поломки. "
        "Если фото не требуется, нажмите /skip.",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML",
    )
    return PHOTO


async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает фото, сохраняет заявку и завершает диалог."""
    message = update.effective_message
    request: MaintenanceRequest = context.user_data["current_request"]

    photo_file = message.photo[-1]
    request.photo_file_id = photo_file.file_id

    await message.reply_text(
        "Фото получено. Сохраняю заявку, это может занять несколько секунд..."
    )

    google_api: GoogleAPIService = context.application.bot_data["google_api_service"]
    request_uuid_str = str(request.request_uuid)

    try:
        # Шаг 1: Создаем строку со статусом 'creating'
        request.status = "creating"
        await google_api.create_request_row(request.model_dump(mode="json"))

        # Шаг 2: Загружаем фото в Drive
        file_name = f"request_{request_uuid_str}.jpg"
        photo_url = await google_api.upload_photo_to_drive(
            file_id=request.photo_file_id, file_name=file_name, bot=context.bot
        )

        if not photo_url:
            # Используем более конкретный RuntimeError
            raise RuntimeError("Failed to get photo URL from Google Drive")

        # Шаг 3: Обновляем строку, меняя статус на 'new' и добавляя URL
        await google_api.update_request_after_upload(
            request_uuid=request_uuid_str, photo_url=photo_url
        )

        # Шаг 4: Отправляем уведомление в чат техслужбы
        await NotificationService.send_new_request_notification(
            bot=context.bot, chat_id=settings.tech_chat_id, request=request
        )

        await message.reply_text(SUCCESS_MESSAGE)

        logger.info(f"New request with photo successfully saved: {request_uuid_str}")

    except Exception as e:
        logger.error(
            f"Transactional request creation failed for {request_uuid_str}: {e}",
            exc_info=True,
        )

        # Шаг 4 (Откат): Удаляем "черновую" запись, если что-то пошло не так
        logger.info(f"Attempting to roll back creation for request {request_uuid_str}")
        await google_api.delete_request_by_uuid(request_uuid_str)

        await message.reply_text(
            "❌ Произошла ошибка при сохранении вашей заявки. Пожалуйста, попробуйте позже. Администраторы уже уведомлены."
        )

    del context.user_data["current_request"]
    return ConversationHandler.END


async def skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Пропускает шаг с фото и сохраняет заявку."""
    message = update.effective_message
    request: MaintenanceRequest = context.user_data["current_request"]

    await message.reply_text("Сохраняю заявку...")
    google_api: GoogleAPIService = context.application.bot_data["google_api_service"]

    try:
        # Так как фото нет, сразу создаем заявку со статусом 'new'
        request.status = "new"
        await google_api.create_request_row(request.model_dump(mode="json"))

        await NotificationService.send_new_request_notification(
            bot=context.bot, chat_id=settings.tech_chat_id, request=request
        )

        await message.reply_text(SUCCESS_MESSAGE)
        logger.info(
            f"New request without photo successfully saved: {request.request_uuid}"
        )

    except Exception as e:
        logger.error(
            f"Request creation (no photo) failed for {request.request_uuid}: {e}",
            exc_info=True,
        )
        await message.reply_text(
            "❌ Произошла ошибка при сохранении вашей заявки. Пожалуйста, попробуйте позже."
        )

    del context.user_data["current_request"]
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет текущий диалог."""
    if "current_request" in context.user_data:
        del context.user_data["current_request"]

    await update.effective_message.reply_text(
        "Создание заявки отменено.", reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


@require_role("technician", "admin")
async def request_callback_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Обрабатывает нажатия на inline-кнопки под сообщениями с заявками.
    """
    query = update.callback_query
    await query.answer()

    action, request_uuid = query.data.split(":", 1)
    user = update.effective_user
    db_user = context.user_data["db_user"]

    google_api: GoogleAPIService = context.application.bot_data["google_api_service"]

    if action == "accept_req":
        success = await google_api.accept_request(
            request_uuid=request_uuid, user_id=user.id, user_name=db_user.name
        )
        if success:
            original_text = query.message.text
            new_text = original_text.replace(
                "Статус: 🆕 Новый", f"Статус: 🛠 В работе у {db_user.name}"
            )
            keyboard = [
                [
                    InlineKeyboardButton(
                        "✅ Готово", callback_data=f"complete_req:{request_uuid}"
                    )
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text=new_text, reply_markup=reply_markup)
        else:
            await query.answer(
                "⚠️ Эту заявку уже взял в работу другой сотрудник.", show_alert=True
            )

    elif action == "complete_req":
        success = await google_api.complete_request(
            request_uuid=request_uuid, user_id=user.id
        )
        if success:
            original_text = query.message.text
            # Удаляем старого исполнителя и добавляем нового
            text_without_assignee = original_text.split("Статус:")[0]
            new_text = text_without_assignee + f"Статус: ✅ Выполнено ({db_user.name})"
            # Убираем клавиатуру после завершения
            await query.edit_message_text(text=new_text, reply_markup=None)
        else:
            await query.answer(
                "⚠️ Не удалось завершить заявку. Возможно, она уже завершена или вы не являетесь исполнителем.",
                show_alert=True,
            )
