"""
Сервис для отправки уведомлений пользователям и в чаты.
"""

import logging
from datetime import datetime

import pytz
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

from app.core.config import settings
from app.models.request import MaintenanceRequest

logger = logging.getLogger(__name__)


def _format_datetime(dt: datetime | None) -> str:
    """
    Форматирует datetime объект в строку с учетом часового пояса из настроек.
    """
    if not dt:
        return "не указано"

    # Убеждаемся, что время в UTC, если оно "наивное"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.utc)

    # Конвертируем в целевой часовой пояс
    display_tz = pytz.timezone(settings.display_timezone)
    local_dt = dt.astimezone(display_tz)

    return local_dt.strftime("%d.%m.%Y в %H:%M")


class NotificationService:
    @staticmethod
    async def send_new_request_notification(
        bot: Bot, chat_id: int, request: MaintenanceRequest
    ):
        """
        Отправляет уведомление о новой заявке в чат техслужбы.
        """
        created_at_str = _format_datetime(request.created_at)
        text = (
            f"🚨 **Новая заявка: #{str(request.request_uuid)[:8]}** 🚨\n\n"
            f"📍 **Локация:** {request.location}\n"
            f"🔧 **Тип поломки:** {request.issue_type}\n"
            f"👤 **Заявитель:** {request.reporter_name}\n"
            f"🕓 **Создана:** {created_at_str}\n\n"
            f"Статус: 🆕 Новый"
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ Принять в работу",
                    callback_data=f"accept_req:{request.request_uuid}",
                ),
            ],
            [InlineKeyboardButton("📄 Открыть фото", url=request.photo_before_url)]
            if request.photo_before_url
            else [],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
            )
            logger.info(
                f"Sent new request notification for {request.request_uuid} to chat {chat_id}."
            )
        except Exception as e:
            logger.error(
                f"Failed to send notification for {request.request_uuid} to chat {chat_id}: {e}",
                exc_info=True,
            )
