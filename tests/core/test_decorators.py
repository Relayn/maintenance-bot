"""
Тесты для декоратора @require_role.
"""

import pytest

from app.core.decorators import require_role
from app.models.user import User

# --- Фикстуры для подготовки тестового окружения ---


@pytest.fixture
def mock_update_context(mocker):
    """Фикстура для создания моков Update и Context."""
    mock_update = mocker.MagicMock()
    mock_context = mocker.MagicMock()

    # --- Настраиваем моки для асинхронных вызовов ---
    mock_update.callback_query.answer = mocker.AsyncMock()
    mock_update.effective_message.reply_text = mocker.AsyncMock()
    mock_update.callback_query = None

    # Симулируем наличие user_service в bot_data
    mock_context.application.bot_data = {"user_service": mocker.MagicMock()}
    # Симулируем наличие user_data
    mock_context.user_data = {}

    return mock_update, mock_context


# --- Тесты ---


@pytest.mark.asyncio
async def test_require_role_success(mock_update_context, mocker):
    """
    Тест: Пользователь имеет необходимую роль, доступ разрешен.
    """
    # Arrange (Подготовка)
    mock_update, mock_context = mock_update_context
    user_service = mock_context.application.bot_data["user_service"]

    # Настраиваем мок пользователя и его ID
    mock_update.effective_user.id = 100
    admin_user = User(telegram_id=100, name="Admin", role="admin")
    user_service.get_user_by_id.return_value = admin_user

    # Создаем "шпиона" - асинхронную функцию, за которой будем следить
    dummy_handler = mocker.AsyncMock()

    # Act (Действие)
    # "Оборачиваем" нашего шпиона в декоратор и вызываем его
    decorated_handler = require_role("admin")(dummy_handler)
    await decorated_handler(mock_update, mock_context)

    # Assert (Проверка)
    # Проверяем, что оригинальный обработчик был вызван
    dummy_handler.assert_awaited_once()
    # Проверяем, что данные о пользователе были сохранены в context
    assert mock_context.user_data["db_user"] == admin_user


@pytest.mark.asyncio
async def test_require_role_wrong_role(mock_update_context, mocker):
    """
    Тест: У пользователя другая роль, доступ запрещен.
    """
    # Arrange
    mock_update, mock_context = mock_update_context
    user_service = mock_context.application.bot_data["user_service"]

    mock_update.effective_user.id = 200
    technician_user = User(telegram_id=200, name="Technician", role="technician")
    user_service.get_user_by_id.return_value = technician_user

    dummy_handler = mocker.AsyncMock()

    # Act
    decorated_handler = require_role("admin")(dummy_handler)  # Требуется роль admin
    await decorated_handler(mock_update, mock_context)

    # Assert
    # Проверяем, что оригинальный обработчик НЕ был вызван
    dummy_handler.assert_not_awaited()
    # Проверяем, что бот попытался ответить сообщением об ошибке
    mock_update.effective_message.reply_text.assert_awaited_once_with(
        "⛔️ У вас нет доступа для выполнения этой команды."
    )


@pytest.mark.asyncio
async def test_require_role_unauthorized(mock_update_context, mocker):
    """
    Тест: Пользователь не найден в базе, доступ запрещен.
    """
    # Arrange
    mock_update, mock_context = mock_update_context
    user_service = mock_context.application.bot_data["user_service"]

    mock_update.effective_user.id = 999
    # Симулируем, что пользователь не найден
    user_service.get_user_by_id.return_value = None

    dummy_handler = mocker.AsyncMock()

    # Act
    decorated_handler = require_role("admin")(dummy_handler)
    await decorated_handler(mock_update, mock_context)

    # Assert
    dummy_handler.assert_not_awaited()
    mock_update.effective_message.reply_text.assert_awaited_once_with(
        "⛔️ У вас нет доступа для выполнения этой команды."
    )
