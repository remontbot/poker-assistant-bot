"""
Модуль работы с базой данных SQLite

Хранит историю раздач, игроков и статистику.
"""

import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from config import DATABASE_PATH

logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    """Получить соединение с базой данных."""
    # Создаём директорию для БД если её нет
    db_path = Path(DATABASE_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """Инициализация базы данных и создание таблиц."""
    conn = get_connection()
    cursor = conn.cursor()

    # Таблица пользователей бота
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            telegram_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            first_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Таблица игроков (оппонентов)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            notes TEXT,
            vpip REAL DEFAULT 0,
            pfr REAL DEFAULT 0,
            aggression REAL DEFAULT 0,
            hands_played INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    # Таблица столов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tables (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            name TEXT,
            max_players INTEGER DEFAULT 6,
            stakes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    # Таблица раздач
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hands (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            table_id INTEGER,
            hero_cards TEXT NOT NULL,
            hero_position TEXT NOT NULL,
            board TEXT,
            stage TEXT NOT NULL,
            pot_size REAL,
            players_count INTEGER,
            hero_action TEXT,
            result TEXT,
            winner TEXT,
            winner_cards TEXT,
            recommendation TEXT,
            equity REAL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (table_id) REFERENCES tables (id)
        )
    """)

    # Таблица действий игроков в раздаче
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hand_actions (
            id INTEGER PRIMARY KEY,
            hand_id INTEGER NOT NULL,
            player_position TEXT NOT NULL,
            player_name TEXT,
            action TEXT NOT NULL,
            amount REAL,
            stage TEXT NOT NULL,
            action_order INTEGER,
            FOREIGN KEY (hand_id) REFERENCES hands (id)
        )
    """)

    # Индексы для быстрого поиска
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_hands_user
        ON hands (user_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_hands_created
        ON hands (created_at)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_players_user
        ON players (user_id)
    """)

    conn.commit()
    conn.close()
    logger.info("База данных инициализирована")


def get_or_create_user(
    telegram_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None
) -> int:
    """Получить или создать пользователя."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM users WHERE telegram_id = ?",
        (telegram_id,)
    )
    row = cursor.fetchone()

    if row:
        user_id = row["id"]
        # Обновляем last_active
        cursor.execute(
            "UPDATE users SET last_active = ? WHERE id = ?",
            (datetime.now(), user_id)
        )
    else:
        cursor.execute(
            """
            INSERT INTO users (telegram_id, username, first_name)
            VALUES (?, ?, ?)
            """,
            (telegram_id, username, first_name)
        )
        user_id = cursor.lastrowid

    conn.commit()
    conn.close()
    return user_id


def save_hand(
    user_id: int,
    hero_cards: str,
    hero_position: str,
    stage: str,
    players_count: int,
    actions: List[Dict[str, Any]],
    pot_size: Optional[float] = None,
    board: Optional[str] = None,
    hero_action: Optional[str] = None,
    result: Optional[str] = None,
    winner: Optional[str] = None,
    winner_cards: Optional[str] = None,
    recommendation: Optional[str] = None,
    equity: Optional[float] = None,
    notes: Optional[str] = None
) -> int:
    """Сохранить раздачу в базу данных."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO hands (
            user_id, hero_cards, hero_position, board, stage,
            pot_size, players_count, hero_action, result,
            winner, winner_cards, recommendation, equity, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id, hero_cards, hero_position, board, stage,
            pot_size, players_count, hero_action, result,
            winner, winner_cards, recommendation, equity, notes
        )
    )
    hand_id = cursor.lastrowid

    # Сохраняем действия игроков
    for i, action in enumerate(actions):
        cursor.execute(
            """
            INSERT INTO hand_actions (
                hand_id, player_position, player_name, action,
                amount, stage, action_order
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                hand_id,
                action.get("position"),
                action.get("name"),
                action.get("action"),
                action.get("amount"),
                action.get("stage", stage),
                i
            )
        )

    conn.commit()
    conn.close()
    logger.info(f"Раздача {hand_id} сохранена для пользователя {user_id}")
    return hand_id


def get_user_stats(user_id: int) -> Dict[str, Any]:
    """Получить статистику пользователя."""
    conn = get_connection()
    cursor = conn.cursor()

    # Общее количество раздач
    cursor.execute(
        "SELECT COUNT(*) as total FROM hands WHERE user_id = ?",
        (user_id,)
    )
    total_hands = cursor.fetchone()["total"]

    # Результаты
    cursor.execute(
        """
        SELECT result, COUNT(*) as count
        FROM hands
        WHERE user_id = ? AND result IS NOT NULL
        GROUP BY result
        """,
        (user_id,)
    )
    results = {row["result"]: row["count"] for row in cursor.fetchall()}

    # Статистика по позициям
    cursor.execute(
        """
        SELECT hero_position, COUNT(*) as count
        FROM hands
        WHERE user_id = ?
        GROUP BY hero_position
        """,
        (user_id,)
    )
    positions = {row["hero_position"]: row["count"] for row in cursor.fetchall()}

    # Среднее эквити
    cursor.execute(
        """
        SELECT AVG(equity) as avg_equity
        FROM hands
        WHERE user_id = ? AND equity IS NOT NULL
        """,
        (user_id,)
    )
    avg_equity = cursor.fetchone()["avg_equity"]

    # Последние 10 раздач
    cursor.execute(
        """
        SELECT hero_cards, hero_position, stage, hero_action, result, created_at
        FROM hands
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 10
        """,
        (user_id,)
    )
    recent_hands = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return {
        "total_hands": total_hands,
        "results": results,
        "positions": positions,
        "avg_equity": avg_equity,
        "recent_hands": recent_hands,
        "wins": results.get("win", 0),
        "losses": results.get("loss", 0)
    }


def get_recent_hands(user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Получить последние раздачи пользователя."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT * FROM hands
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (user_id, limit)
    )
    hands = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return hands


def update_hand_result(
    hand_id: int,
    result: str,
    winner: Optional[str] = None,
    winner_cards: Optional[str] = None
):
    """Обновить результат раздачи."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE hands
        SET result = ?, winner = ?, winner_cards = ?
        WHERE id = ?
        """,
        (result, winner, winner_cards, hand_id)
    )

    conn.commit()
    conn.close()


# Инициализируем БД при импорте модуля
init_database()
