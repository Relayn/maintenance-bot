"""
Сервисный модуль для инкапсуляции работы с Google API (Sheets, Drive).
"""
import logging
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

from app.core.config import settings

logger = logging.getLogger(__name__)

# Определяем путь к файлу с учетными данными
CREDENTIALS_FILE = Path(__file__).parent.parent.parent / "credentials.json"


class GoogleAPIService:
    """
    Класс для работы с API Google Sheets и Drive.
    """
    def __init__(self) -> None:
        """Инициализирует клиент для работы с Google API."""
        logger.info("Initializing Google API client...")
        if not CREDENTIALS_FILE.exists():
            logger.error(f"Credentials file not found at: {CREDENTIALS_FILE}")
            raise FileNotFoundError(f"Google credentials file not found at {CREDENTIALS_FILE}")

        # Определяем необходимые права доступа
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        # Аутентифицируемся с помощью сервисного аккаунта
        creds = Credentials.from_service_account_file(
            CREDENTIALS_FILE, scopes=scopes
        )
        self.client = gspread.authorize(creds)
        logger.info("Google API client initialized successfully.")

    def get_users_worksheet(self) -> gspread.Worksheet:
        """
        Открывает Google-таблицу и возвращает лист 'users'.

        Returns:
            Объект gspread.Worksheet для листа 'users'.
        """
        try:
            spreadsheet = self.client.open_by_key(settings.google_sheet_id)
            return spreadsheet.worksheet("users")
        except gspread.exceptions.SpreadsheetNotFound:
            logger.error(f"Spreadsheet with ID '{settings.google_sheet_id}' not found.")
            raise
        except gspread.exceptions.WorksheetNotFound:
            logger.error("Worksheet 'users' not found in the spreadsheet.")
            raise

    def add_user(self, user_data: dict) -> None:
        """
        Добавляет нового пользователя в лист 'users'.

        Args:
            user_data: Словарь с данными пользователя {'telegram_id': ..., 'name': ..., 'role': ...}.
        """
        logger.info(f"Adding user {user_data.get('telegram_id')} to Google Sheet.")
        try:
            users_sheet = self.get_users_worksheet()
            # append_row ожидает список значений в том же порядке, что и столбцы
            row_values = [user_data['telegram_id'], user_data['name'], user_data['role']]
            users_sheet.append_row(row_values)
            logger.info(f"User {user_data.get('telegram_id')} added successfully.")
        except Exception as e:
            logger.error(f"Failed to add user to Google Sheet: {e}", exc_info=True)
            raise

    def delete_user(self, telegram_id: int) -> bool:
        """
        Удаляет пользователя из листа 'users' по его telegram_id.

        Args:
            telegram_id: ID пользователя в Telegram.

        Returns:
            True, если пользователь был найден и удален, иначе False.
        """
        logger.info(f"Attempting to delete user {telegram_id} from Google Sheet.")
        try:
            users_sheet = self.get_users_worksheet()
            # Ищем ячейку с нужным telegram_id в первом столбце
            cell = users_sheet.find(str(telegram_id), in_column=1)
            if cell:
                users_sheet.delete_rows(cell.row)
                logger.info(f"User {telegram_id} deleted successfully.")
                return True
            logger.warning(f"User {telegram_id} not found for deletion.")
            return False
        except Exception as e:
            logger.error(f"Failed to delete user from Google Sheet: {e}", exc_info=True)
            raise

    def update_user_name(self, telegram_id: int, new_name: str) -> bool:
        """
        Обновляет имя пользователя в листе 'users'.

        Args:
            telegram_id: ID пользователя для обновления.
            new_name: Новое имя пользователя.

        Returns:
            True, если пользователь был найден и обновлен, иначе False.
        """
        logger.info(f"Attempting to update name for user {telegram_id} to '{new_name}'.")
        try:
            users_sheet = self.get_users_worksheet()
            cell = users_sheet.find(str(telegram_id), in_column=1)
            if cell:
                # Обновляем ячейку в той же строке, но во втором столбце (name)
                users_sheet.update_cell(cell.row, 2, new_name)
                logger.info(f"Name for user {telegram_id} updated successfully.")
                return True
            logger.warning(f"User {telegram_id} not found for name update.")
            return False
        except Exception as e:
            logger.error(f"Failed to update user name in Google Sheet: {e}", exc_info=True)
            raise