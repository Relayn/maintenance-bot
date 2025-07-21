"""
Модуль для конфигурации логирования.

Определяет единый формат и настройки для всех логгеров в приложении.
"""
import logging
import sys


def setup_logging(level: int = logging.INFO) -> None:
    """
    Настраивает базовую конфигурацию логирования для вывода в stdout.

    Args:
        level: Уровень логирования (INFO, DEBUG и т.д.).
    """
    # Определяем формат логов для консистентности
    log_format = "%(asctime)s - [%(levelname)s] - %(name)s - (%(filename)s).%(funcName)s(%(lineno)d) - %(message)s"

    # Создаем обработчик, который будет выводить логи в стандартный вывод (консоль)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(logging.Formatter(log_format))

    # Настраиваем корневой логгер
    logging.basicConfig(
        level=level,
        handlers=[stdout_handler]
    )

    # Пример: отключаем слишком "шумные" логгеры сторонних библиотек, если потребуется
    # logging.getLogger("httpx").setLevel(logging.WARNING)