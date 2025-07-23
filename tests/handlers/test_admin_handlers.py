"""
Интеграционные тесты для обработчиков административных команд.
"""

from unittest.mock import MagicMock

import pytest

from app.handlers.admin import list_users
from app.models.user import User
from app.services.user_service import UserService

# --- Тестовые данные ---

ADMIN_USER = User(telegram_id=100, name="Admin", role="admin")
SAMPLE_USERS = [
    ADMIN_USER,
    User(telegram_id=200, name="Technician", role="technician"),
]

# --- Фикстуры ---


@pytest.fixture
def mock_update_context_for_handlers(mocker) -> tuple[MagicMock, MagicMock]:
    """Фикстура для создания моков Update и Context для обработчиков."""
    mock_update = mocker.MagicMock()
    mock_context = mocker.MagicMock()

    mock_update.effective_message.reply_text = mocker.AsyncMock()
    # Явно симулируем обычное сообщение, чтобы избежать ошибок в декораторе
    mock_update.callback_query = None

    mock_context.application.bot_data = {
        "user_service": mocker.MagicMock(spec=UserService)
    }
    mock_context.user_data = {}

    return mock_update, mock_context


# --- Тесты ---


@pytest.mark.asyncio
async def test_list_users_success(mock_update_context_for_handlers):
    """
    Тест: Команда /listusers успешно выводит список пользователей.
    """
    # Arrange
    mock_update, mock_context = mock_update_context_for_handlers
    user_service = mock_context.application.bot_data["user_service"]

    mock_update.effective_user.id = ADMIN_USER.telegram_id
    user_service.get_user_by_id.return_value = ADMIN_USER
    user_service.get_all_users.return_value = SAMPLE_USERS

    # Act
    await list_users(mock_update, mock_context)

    # Assert
    reply_mock = mock_update.effective_message.reply_text

    # Проверяем, что было отправлено 3 сообщения: 1 заголовок + 2 пользователя
    assert reply_mock.call_count == 3

    # Проверяем вызов заголовка
    first_call_kwargs = reply_mock.call_args_list[0].kwargs
    assert first_call_kwargs["text"] == "--- 👥 Список пользователей ---"

    # Проверяем карточку первого пользователя (Admin)
    second_call_kwargs = reply_mock.call_args_list[1].kwargs
    admin_card_text = second_call_kwargs["text"]
    assert "👤 <b>Admin</b>" in admin_card_text
    assert "<code>100</code>" in admin_card_text
    assert "<i>admin</i>" in admin_card_text
    assert second_call_kwargs["parse_mode"] == "HTML"
    assert second_call_kwargs["reply_markup"] is not None

    # Проверяем карточку второго пользователя (Technician)
    third_call_kwargs = reply_mock.call_args_list[2].kwargs
    tech_card_text = third_call_kwargs["text"]
    assert "👤 <b>Technician</b>" in tech_card_text
    assert "<code>200</code>" in tech_card_text
    assert "<i>technician</i>" in tech_card_text


@pytest.mark.asyncio
async def test_list_users_empty(mock_update_context_for_handlers):
    """
    Тест: Команда /listusers корректно обрабатывает пустой список.
    """
    # Arrange
    mock_update, mock_context = mock_update_context_for_handlers
    user_service = mock_context.application.bot_data["user_service"]

    # --- КЛЮЧЕВОЕ ИЗМЕНЕНИЕ ---
    # Симулируем, что декоратор нашел пользователя-администратора
    mock_update.effective_user.id = ADMIN_USER.telegram_id
    user_service.get_user_by_id.return_value = ADMIN_USER

    # Настраиваем основной мок для теста
    user_service.get_all_users.return_value = []

    # Act
    await list_users(mock_update, mock_context)

    # Assert
    mock_update.effective_message.reply_text.assert_awaited_once_with(
        "👥 Список пользователей пуст."
    )
