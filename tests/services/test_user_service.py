"""
Тесты для UserService.
"""

from unittest.mock import MagicMock

import pytest

from app.models.user import User
from app.services.google_api import GoogleAPIService
from app.services.user_service import UserService

SAMPLE_USER_RECORDS = [
    {"telegram_id": 100, "name": "Admin User", "role": "admin"},
    {"telegram_id": 200, "name": "Technician User", "role": "technician"},
]


@pytest.fixture
def mock_google_api_service(mocker) -> MagicMock:
    """Фикстура для создания мока GoogleAPIService."""
    mock = mocker.Mock(spec=GoogleAPIService)
    mock.get_users_worksheet.return_value.get_all_records.return_value = (
        SAMPLE_USER_RECORDS
    )

    # Делаем изменяющие методы асинхронными моками, чтобы их можно было "await"-ить
    mock.add_user = mocker.AsyncMock()
    mock.delete_user = mocker.AsyncMock()
    mock.update_user_name = mocker.AsyncMock()

    return mock


@pytest.fixture
def user_service(mock_google_api_service) -> UserService:
    """Фикстура для создания экземпляра UserService с моком Google API."""
    return UserService(google_api=mock_google_api_service)


def test_get_all_users_success(user_service, mock_google_api_service):
    """Тест: Успешное получение и парсинг списка пользователей."""
    users = user_service.get_all_users()
    assert len(users) == 2
    assert isinstance(users[0], User)
    assert users[0].telegram_id == 100
    assert users[1].role == "technician"
    mock_google_api_service.get_users_worksheet.return_value.get_all_records.assert_called_once()


def test_get_all_users_caching(user_service, mock_google_api_service):
    """Тест: Проверка работы кэширования."""
    first_call_users = user_service.get_all_users()
    second_call_users = user_service.get_all_users()
    assert first_call_users is second_call_users
    mock_google_api_service.get_users_worksheet.return_value.get_all_records.assert_called_once()


def test_get_all_users_api_error(user_service, mock_google_api_service):
    """Тест: Обработка ошибки от Google API."""
    mock_google_api_service.get_users_worksheet.side_effect = Exception("Network Error")
    users = user_service.get_all_users()
    assert users == []


@pytest.mark.asyncio
async def test_add_user_clears_cache(user_service, mock_google_api_service):
    """Тест: Проверка, что добавление пользователя сбрасывает кэш."""
    # 1. Заполняем кэш
    user_service.get_all_users()
    mock_google_api_service.get_users_worksheet.return_value.get_all_records.assert_called_once()

    new_user = User(telegram_id=300, name="New Guy", role="housekeeper")

    # 2. Добавляем нового пользователя
    await user_service.add_user(new_user)

    # 3. Снова запрашиваем всех пользователей
    user_service.get_all_users()

    # 4. Проверяем, что get_all_records был вызван второй раз
    assert (
        mock_google_api_service.get_users_worksheet.return_value.get_all_records.call_count
        == 2
    )
