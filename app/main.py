"""
Основная точка входа в приложение.

Этот файл отвечает за инициализацию и запуск Telegram-бота.
"""

import logging

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from app.core.config import settings
from app.core.logging_config import setup_logging
from app.handlers import admin, common
from app.handlers import request as request_handler
from app.services.google_api import GoogleAPIService
from app.services.user_service import UserService

logger = logging.getLogger(__name__)


def main() -> None:
    """Основная функция для запуска бота."""
    setup_logging()

    logger.info("Initializing services...")
    google_api_service = GoogleAPIService()
    user_service = UserService(google_api=google_api_service)

    logger.info("Starting bot...")
    application = Application.builder().token(settings.bot_token).build()

    # Сохраняем экземпляры сервисов в bot_data для доступа из обработчиков
    application.bot_data["user_service"] = user_service
    application.bot_data["google_api_service"] = (
        google_api_service  # Добавьте эту строку
    )
    application.bot_data["settings"] = settings

    # --- Создаем ConversationHandler для создания заявки ---
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("new", request_handler.new_request_start)],
        states={
            request_handler.LOCATION: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, request_handler.get_location
                )
            ],
            request_handler.ISSUE_TYPE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, request_handler.get_issue_type
                )
            ],
            request_handler.PHOTO: [
                MessageHandler(filters.PHOTO, request_handler.get_photo),
                CommandHandler("skip", request_handler.skip_photo),
            ],
        },
        fallbacks=[CommandHandler("cancel", request_handler.cancel)],
    )

    application.add_handler(conv_handler)

    application.add_handler(CommandHandler("start", common.start))
    application.add_handler(
        CallbackQueryHandler(admin.admin_user_callback, pattern=r"^delete_user:")
    )
    application.add_handler(
        CallbackQueryHandler(
            request_handler.request_callback_handler,
            pattern=r"^(accept_req|complete_req):",
        )
    )
    application.add_handler(CommandHandler("myid", common.show_my_id))
    application.add_handler(CommandHandler("listusers", admin.list_users))
    application.add_handler(CommandHandler("adduser", admin.add_user))
    application.add_handler(CommandHandler("deluser", admin.delete_user))
    # --- Регистрируем обработчик ошибок ---
    application.add_error_handler(common.error_handler)
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND, common.unauthorized_user_handler
        )
    )

    logger.info("Bot is running in polling mode.")
    application.run_polling()


if __name__ == "__main__":
    main()
