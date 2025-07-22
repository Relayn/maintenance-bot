"""
Сервисный модуль для инкапсуляции работы с Google API (Sheets, Drive).

Реализует механизм повторных попыток (retry) для повышения отказоустойчивости
и механизм блокировки (asyncio.Lock) для предотвращения состояния гонки.
"""

import asyncio
import io
import logging
from datetime import datetime, timezone
from pathlib import Path

import gspread
import requests.exceptions
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from gspread.exceptions import APIError
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings

logger = logging.getLogger(__name__)

CREDENTIALS_FILE = Path(__file__).parent.parent.parent / "credentials.json"


def is_retryable_gspread_error(exception: BaseException) -> bool:
    return isinstance(exception, APIError) and exception.response.status_code >= 500


google_api_retry = retry(
    retry=(
        retry_if_exception_type(requests.exceptions.RequestException)
        | retry_if_exception(is_retryable_gspread_error)
    ),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    stop=stop_after_attempt(5),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)


class GoogleAPIService:
    """
    Класс для работы с API Google Sheets и Drive.
    """

    def __init__(self) -> None:
        logger.info("Initializing Google API client...")
        if not CREDENTIALS_FILE.exists():
            logger.error(f"Credentials file not found at: {CREDENTIALS_FILE}")
            raise FileNotFoundError(
                f"Google credentials file not found at {CREDENTIALS_FILE}"
            )

        self.scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        self.client = gspread.service_account(
            filename=str(CREDENTIALS_FILE), scopes=self.scopes
        )
        self.lock = asyncio.Lock()
        logger.info("Google API client initialized successfully.")

    @google_api_retry
    def get_users_worksheet(self) -> gspread.Worksheet:
        """Открывает Google-таблицу и возвращает лист 'users'."""
        try:
            spreadsheet = self.client.open_by_key(settings.google_sheet_id)
            return spreadsheet.worksheet("users")
        except gspread.exceptions.SpreadsheetNotFound:
            logger.error(f"Spreadsheet with ID '{settings.google_sheet_id}' not found.")
            raise
        except gspread.exceptions.WorksheetNotFound:
            logger.error("Worksheet 'users' not found in the spreadsheet.")
            raise

    @google_api_retry
    async def add_user(self, user_data: dict) -> None:
        """Добавляет нового пользователя в лист 'users'."""
        logger.info(f"Adding user {user_data.get('telegram_id')} to Google Sheet.")
        async with self.lock:
            logger.debug(
                f"Lock acquired for adding user {user_data.get('telegram_id')}."
            )
            try:
                users_sheet = self.get_users_worksheet()
                row_values = [
                    user_data["telegram_id"],
                    user_data["name"],
                    user_data["role"],
                ]
                users_sheet.append_row(row_values)
                logger.info(f"User {user_data.get('telegram_id')} added successfully.")
            except Exception as e:
                logger.error(f"Failed to add user to Google Sheet: {e}", exc_info=True)
                raise
        logger.debug(f"Lock released for adding user {user_data.get('telegram_id')}.")

    @google_api_retry
    async def delete_user(self, telegram_id: int) -> bool:
        """Удаляет пользователя из листа 'users'."""
        logger.info(f"Attempting to delete user {telegram_id} from Google Sheet.")
        async with self.lock:
            logger.debug(f"Lock acquired for deleting user {telegram_id}.")
            try:
                users_sheet = self.get_users_worksheet()
                cell = users_sheet.find(str(telegram_id), in_column=1)
                if cell:
                    users_sheet.delete_rows(cell.row)
                    logger.info(f"User {telegram_id} deleted successfully.")
                    return True
                logger.warning(f"User {telegram_id} not found for deletion.")
                return False
            except Exception as e:
                logger.error(
                    f"Failed to delete user from Google Sheet: {e}", exc_info=True
                )
                raise
        logger.debug(f"Lock released for deleting user {telegram_id}.")

    @google_api_retry
    async def update_user_name(self, telegram_id: int, new_name: str) -> bool:
        """Обновляет имя пользователя в листе 'users'."""
        logger.info(
            f"Attempting to update name for user {telegram_id} to '{new_name}'."
        )
        async with self.lock:
            logger.debug(f"Lock acquired for updating name for user {telegram_id}.")
            try:
                users_sheet = self.get_users_worksheet()
                cell = users_sheet.find(str(telegram_id), in_column=1)
                if cell:
                    users_sheet.update_cell(cell.row, 2, new_name)
                    logger.info(f"Name for user {telegram_id} updated successfully.")
                    return True
                logger.warning(f"User {telegram_id} not found for name update.")
                return False
            except Exception as e:
                logger.error(
                    f"Failed to update user name in Google Sheet: {e}", exc_info=True
                )
                raise
        logger.debug(f"Lock released for updating name for user {telegram_id}.")

    # --- Методы для работы с заявками ---

    @google_api_retry
    async def upload_photo_to_drive(
        self, file_id: str, file_name: str, bot
    ) -> str | None:
        """Скачивает файл из Telegram и загружает его в Google Drive."""
        logger.info(f"Uploading photo with file_id {file_id} to Google Drive.")
        try:
            tg_file = await bot.get_file(file_id)
            file_content = io.BytesIO()
            await tg_file.download_to_memory(file_content)
            file_content.seek(0)

            creds = Credentials.from_service_account_file(
                CREDENTIALS_FILE, scopes=self.scopes
            )
            drive_service = build("drive", "v3", credentials=creds)

            file_metadata = {
                "name": file_name,
                "parents": [settings.google_drive_folder_id],
            }
            media = MediaIoBaseUpload(
                file_content, mimetype="image/jpeg", resumable=True
            )

            file = (
                drive_service.files()
                .create(body=file_metadata, media_body=media, fields="id,webViewLink")
                .execute()
            )

            file_id = file.get("id")
            drive_service.permissions().create(
                fileId=file_id, body={"type": "anyone", "role": "reader"}
            ).execute()

            logger.info(f"Photo uploaded successfully. Drive file ID: {file_id}")
            return file.get("webViewLink")
        except Exception as e:
            logger.error(f"Failed to upload photo to Google Drive: {e}", exc_info=True)
            return None

    @google_api_retry
    async def create_request_row(self, request_data: dict) -> None:
        """Создает новую строку для заявки в Google Sheets."""
        logger.info(
            f"Creating initial request row for UUID {request_data.get('request_uuid')}"
        )
        async with self.lock:
            try:
                requests_sheet = self.client.open_by_key(
                    settings.google_sheet_id
                ).worksheet("requests")
                headers = requests_sheet.row_values(1)
                row_values = [request_data.get(header) for header in headers]
                requests_sheet.append_row(row_values)
                logger.info("Initial request row created successfully.")
            except Exception as e:
                logger.error(f"Failed to create request row: {e}", exc_info=True)
                raise

    @google_api_retry
    async def update_request_after_upload(
        self, request_uuid: str, photo_url: str
    ) -> None:
        """Обновляет статус заявки и добавляет ссылку на фото."""
        logger.info(f"Updating request row for UUID {request_uuid} with photo URL.")
        async with self.lock:
            try:
                requests_sheet = self.client.open_by_key(
                    settings.google_sheet_id
                ).worksheet("requests")
                cell = requests_sheet.find(request_uuid, in_column=1)
                if cell:
                    requests_sheet.update_cell(cell.row, 2, "new")
                    requests_sheet.update_cell(cell.row, 5, photo_url)
                    logger.info(f"Request {request_uuid} updated successfully.")
            except Exception as e:
                logger.error(f"Failed to update request row: {e}", exc_info=True)
                raise

    @google_api_retry
    async def delete_request_by_uuid(self, request_uuid: str) -> bool:
        """Удаляет строку заявки по её UUID. Используется для отката транзакции."""
        logger.warning(
            f"Rolling back transaction. Deleting request row for UUID {request_uuid}."
        )
        async with self.lock:
            try:
                requests_sheet = self.client.open_by_key(
                    settings.google_sheet_id
                ).worksheet("requests")
                cell = requests_sheet.find(request_uuid, in_column=1)
                if cell:
                    requests_sheet.delete_rows(cell.row)
                    logger.info(
                        f"Request row {request_uuid} deleted successfully during rollback."
                    )
                    return True
                return False
            except Exception as e:
                logger.error(
                    f"Failed to delete request row during rollback: {e}", exc_info=True
                )
                return False

    @google_api_retry
    async def accept_request(
        self, request_uuid: str, user_id: int, user_name: str
    ) -> bool:
        """
        Принимает заявку в работу: обновляет статус, исполнителя и время принятия.
        """
        logger.info(
            f"Accepting request {request_uuid} by user {user_id} ({user_name})."
        )
        async with self.lock:
            try:
                requests_sheet = self.client.open_by_key(
                    settings.google_sheet_id
                ).worksheet("requests")
                cell = requests_sheet.find(request_uuid, in_column=1)
                if not cell:
                    logger.warning(f"Request {request_uuid} not found to be accepted.")
                    return False

                # Проверяем, не принята ли заявка уже кем-то другим
                current_status = requests_sheet.cell(cell.row, 2).value
                if current_status != "new":
                    logger.warning(
                        f"User {user_id} tried to accept request {request_uuid}, "
                        f"but it already has status '{current_status}'."
                    )
                    return False

                # Обновляем ячейки
                requests_sheet.update_cell(cell.row, 2, "in_progress")  # status
                requests_sheet.update_cell(cell.row, 9, user_id)  # assignee_id
                requests_sheet.update_cell(cell.row, 10, user_name)  # assignee_name
                requests_sheet.update_cell(
                    cell.row, 11, datetime.now(timezone.utc).isoformat()
                )  # accepted_at)  # accepted_at

                logger.info(f"Request {request_uuid} accepted successfully.")
                return True
            except Exception as e:
                logger.error(
                    f"Failed to accept request {request_uuid}: {e}", exc_info=True
                )
                raise

    @google_api_retry
    async def complete_request(self, request_uuid: str, user_id: int) -> bool:
        """
        Завершает заявку: обновляет статус и время завершения.
        """
        logger.info(f"Completing request {request_uuid} by user {user_id}.")
        async with self.lock:
            try:
                requests_sheet = self.client.open_by_key(
                    settings.google_sheet_id
                ).worksheet("requests")
                cell = requests_sheet.find(request_uuid, in_column=1)
                if not cell:
                    logger.warning(f"Request {request_uuid} not found to be completed.")
                    return False

                # Проверяем, что заявка находится в работе и что ее завершает тот же сотрудник
                current_status = requests_sheet.cell(cell.row, 2).value
                assignee_id = int(requests_sheet.cell(cell.row, 9).value)

                if current_status != "in_progress":
                    logger.warning(
                        f"User {user_id} tried to complete request {request_uuid}, "
                        f"but it has status '{current_status}'."
                    )
                    return False  # Нельзя завершить то, что не в работе

                if assignee_id != user_id:
                    logger.warning(
                        f"User {user_id} tried to complete request {request_uuid}, "
                        f"but it is assigned to user {assignee_id}."
                    )
                    return False  # Завершить может только тот, кто принял

                # Обновляем ячейки
                requests_sheet.update_cell(cell.row, 2, "completed")  # status
                requests_sheet.update_cell(
                    cell.row, 12, datetime.now(timezone.utc).isoformat()
                )  # completed_at

                logger.info(f"Request {request_uuid} completed successfully.")
                return True
            except Exception as e:
                logger.error(
                    f"Failed to complete request {request_uuid}: {e}", exc_info=True
                )
                raise
