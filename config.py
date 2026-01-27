"""
Конфигурация Poker Assistant Bot

Загружает настройки из .env файла и определяет константы проекта.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Базовая директория проекта
BASE_DIR = Path(__file__).resolve().parent

# Настройки Telegram бота
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Режим отладки
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")

# Список разрешённых пользователей (Telegram ID)
_allowed_users_str = os.getenv("ALLOWED_USERS", "")
ALLOWED_USERS = [
    int(uid.strip())
    for uid in _allowed_users_str.split(",")
    if uid.strip().isdigit()
]

# Путь к базе данных
DATABASE_PATH = os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "poker.db"))

# Настройки логирования
LOG_LEVEL = logging.DEBUG if DEBUG else logging.INFO
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Покерные константы
POSITIONS = ["UTG", "UTG+1", "MP", "MP+1", "HJ", "CO", "BTN", "SB", "BB"]
POSITIONS_SHORT = ["UTG", "MP", "CO", "BTN", "SB", "BB"]

STAGES = {
    "preflop": "Префлоп",
    "flop": "Флоп",
    "turn": "Тёрн",
    "river": "Ривер"
}

ACTIONS = {
    "fold": "Фолд",
    "check": "Чек",
    "call": "Колл",
    "raise": "Рейз",
    "allin": "Олл-ин"
}

# Масти и номиналы карт
SUITS = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}
SUITS_REVERSE = {"♠": "s", "♥": "h", "♦": "d", "♣": "c"}

RANKS = ["A", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2"]

# Все 52 карты
ALL_CARDS = [f"{rank}{suit}" for rank in RANKS for suit in SUITS.keys()]

# Эмодзи для интерфейса
EMOJI = {
    "cards": "🃏",
    "target": "🎯",
    "tip": "💡",
    "stats": "📊",
    "check": "✅",
    "cross": "❌",
    "money": "💰",
    "robot": "🤖",
    "chart": "📈",
    "warning": "⚠️",
    "star": "⭐",
    "fire": "🔥",
    "think": "🤔"
}

# Состояния ConversationHandler
class States:
    SELECT_CARDS = 0
    SELECT_POSITION = 1
    SELECT_STAGE = 2
    SELECT_PLAYERS = 3
    OPPONENT_ACTIONS = 4
    POT_SIZE = 5
    MY_ACTION = 6
    RESULT = 7
    WINNER_CARDS = 8


def validate_config():
    """Проверка обязательных настроек."""
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN не установлен! "
            "Создайте файл .env с токеном от @BotFather"
        )
    return True


def setup_logging():
    """Настройка логирования."""
    logging.basicConfig(
        level=LOG_LEVEL,
        format=LOG_FORMAT
    )

    # Уменьшаем логи от httpx
    logging.getLogger("httpx").setLevel(logging.WARNING)

    return logging.getLogger(__name__)
