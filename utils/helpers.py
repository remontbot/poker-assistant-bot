"""
Вспомогательные функции

Форматирование карт, парсинг действий, работа с текстом.
"""

import logging
from typing import List, Tuple, Optional, Dict, Any

from config import SUITS, SUITS_REVERSE, RANKS, POSITIONS_SHORT, ACTIONS, EMOJI

logger = logging.getLogger(__name__)


def format_card(card: str) -> str:
    """
    Форматировать карту с символом масти.

    Args:
        card: Карта в формате "As", "Kh", "Td" и т.д.

    Returns:
        Карта с символом масти: "A♠", "K♥", "T♦"
    """
    if len(card) != 2:
        return card

    rank = card[0].upper()
    suit = card[1].lower()

    suit_symbol = SUITS.get(suit, suit)
    return f"{rank}{suit_symbol}"


def format_cards(cards: List[str]) -> str:
    """
    Форматировать список карт.

    Args:
        cards: Список карт ["As", "Kh"]

    Returns:
        Отформатированная строка: "A♠ K♥"
    """
    return " ".join(format_card(card) for card in cards)


def parse_card(card_str: str) -> str:
    """
    Парсить карту из отформатированного вида обратно в код.

    Args:
        card_str: Карта в формате "A♠"

    Returns:
        Карта в формате "As"
    """
    if len(card_str) != 2:
        return card_str

    rank = card_str[0]
    suit_symbol = card_str[1]

    suit_code = SUITS_REVERSE.get(suit_symbol, suit_symbol)
    return f"{rank}{suit_code}"


def get_hand_notation(cards: List[str]) -> str:
    """
    Получить нотацию руки (например, "AKs", "QQ", "T9o").

    Args:
        cards: Список из двух карт ["As", "Kh"]

    Returns:
        Нотация руки: "AKo" (offsuit) или "AKs" (suited) или "AA" (пара)
    """
    if len(cards) != 2:
        return ""

    rank1 = cards[0][0]
    rank2 = cards[1][0]
    suit1 = cards[0][1]
    suit2 = cards[1][1]

    # Сортируем по силе (A > K > Q > ...)
    rank_order = RANKS
    if rank_order.index(rank1) > rank_order.index(rank2):
        rank1, rank2 = rank2, rank1

    if rank1 == rank2:
        return f"{rank1}{rank2}"
    elif suit1 == suit2:
        return f"{rank1}{rank2}s"
    else:
        return f"{rank1}{rank2}o"


def get_hand_rank_percentile(cards: List[str]) -> float:
    """
    Получить процентиль руки (насколько сильная рука).

    Args:
        cards: Список из двух карт

    Returns:
        Процентиль от 0 до 100 (100 = AA, топ рука)
    """
    # Упрощённый рейтинг стартовых рук
    # Основан на популярных чартах стартовых рук

    hand_rankings = {
        # Топ 1%
        "AA": 100, "KK": 99,
        # Топ 2%
        "QQ": 98, "AKs": 97,
        # Топ 3%
        "JJ": 96, "AKo": 95, "AQs": 94,
        # Топ 5%
        "TT": 93, "AQo": 92, "AJs": 91, "KQs": 90,
        # Топ 7%
        "99": 89, "ATs": 88, "AJo": 87, "KJs": 86, "KQo": 85,
        # Топ 10%
        "88": 84, "KTs": 83, "ATo": 82, "QJs": 81, "KJo": 80,
        "QTs": 79, "JTs": 78,
        # Топ 15%
        "77": 77, "A9s": 76, "KTo": 75, "A8s": 74, "Q9s": 73,
        "QJo": 72, "JTo": 71, "A7s": 70, "A5s": 69, "A6s": 68,
        # Топ 20%
        "66": 67, "K9s": 66, "QTo": 65, "T9s": 64, "A4s": 63,
        "J9s": 62, "A3s": 61, "K8s": 60, "A2s": 59,
        # Топ 25%
        "55": 58, "K7s": 57, "Q8s": 56, "K9o": 55, "T8s": 54,
        "K6s": 53, "J8s": 52, "98s": 51,
        # Топ 30%
        "44": 50, "K5s": 49, "Q9o": 48, "T9o": 47, "J9o": 46,
        "K4s": 45, "Q7s": 44, "T7s": 43, "K3s": 42, "97s": 41,
        # Топ 35%
        "33": 40, "K2s": 39, "Q6s": 38, "87s": 37, "J7s": 36,
        "Q5s": 35, "98o": 34, "T8o": 33, "96s": 32,
        # Топ 40%
        "22": 31, "Q4s": 30, "J8o": 29, "76s": 28, "Q3s": 27,
        "86s": 26, "J6s": 25, "Q2s": 24, "T6s": 23,
        # Топ 50%
        "87o": 22, "J5s": 21, "65s": 20, "97o": 19, "75s": 18,
        "J4s": 17, "95s": 16, "54s": 15, "J3s": 14, "T7o": 13,
        # Остальные
        "J2s": 12, "64s": 11, "85s": 10, "76o": 9, "T5s": 8,
        "96o": 7, "86o": 6, "53s": 5, "T4s": 4, "74s": 3,
        "43s": 2, "T3s": 1
    }

    notation = get_hand_notation(cards)
    return hand_rankings.get(notation, 5)  # По умолчанию слабая рука


def get_hand_description(cards: List[str]) -> str:
    """
    Получить описание руки на русском.

    Args:
        cards: Список из двух карт

    Returns:
        Описание руки
    """
    notation = get_hand_notation(cards)
    percentile = get_hand_rank_percentile(cards)

    descriptions = {
        "AA": "Тузы (монстр)",
        "KK": "Короли (монстр)",
        "QQ": "Дамы (премиум)",
        "JJ": "Валеты (премиум)",
        "TT": "Десятки (сильная)",
        "99": "Девятки",
        "88": "Восьмёрки",
        "77": "Семёрки",
        "66": "Шестёрки",
        "55": "Пятёрки",
        "44": "Четвёрки",
        "33": "Тройки",
        "22": "Двойки"
    }

    # Проверка на пару
    if notation in descriptions:
        return descriptions[notation]

    # Проверка на suited/offsuit
    if notation.endswith("s"):
        suited = "одномастные (suited)"
    elif notation.endswith("o"):
        suited = "разномастные (offsuit)"
    else:
        suited = ""

    # Определяем тип руки
    ranks = notation[:2]

    if "A" in ranks:
        if "K" in ranks:
            base = "Туз-Король"
        elif "Q" in ranks:
            base = "Туз-Дама"
        elif "J" in ranks:
            base = "Туз-Валет"
        else:
            base = f"Туз с кикером"
    elif "K" in ranks:
        if "Q" in ranks:
            base = "Король-Дама"
        else:
            base = "Король с кикером"
    else:
        base = "Коннектор" if abs(RANKS.index(ranks[0]) - RANKS.index(ranks[1])) == 1 else "Разрозненные"

    if suited:
        return f"{base} ({suited})"
    return base


def format_action(action: str, amount: float = 0) -> str:
    """
    Форматировать действие игрока.

    Args:
        action: Код действия (fold, call, raise, etc.)
        amount: Размер ставки

    Returns:
        Отформатированное действие
    """
    action_names = {
        "fold": "Фолд",
        "check": "Чек",
        "call": "Колл",
        "raise": "Рейз",
        "allin": "Олл-ин",
        "skip": "Пропуск"
    }

    name = action_names.get(action, action)

    if action == "raise" and amount > 0:
        return f"{name} {amount}bb"
    elif action == "call" and amount > 0:
        return f"{name} {amount}bb"

    return name


def format_actions_summary(actions: List[Dict[str, Any]]) -> str:
    """
    Форматировать сводку действий в раздаче.

    Args:
        actions: Список действий [{position, action, amount}, ...]

    Returns:
        Отформатированная сводка
    """
    lines = []

    for i, act in enumerate(actions):
        position = act.get("position", f"Игрок {i+1}")
        action = act.get("action", "")
        amount = act.get("amount", 0)

        formatted = format_action(action, amount)

        if i == len(actions) - 1:
            prefix = "└─"
        else:
            prefix = "├─"

        lines.append(f"{prefix} {position}: {formatted}")

    return "\n".join(lines)


def get_position_description(position: str, total_players: int = 6) -> str:
    """
    Получить описание позиции.

    Args:
        position: Код позиции (UTG, MP, CO, BTN, SB, BB)
        total_players: Количество игроков за столом

    Returns:
        Описание позиции
    """
    descriptions = {
        "UTG": "Under the Gun (первый после блайндов)",
        "UTG+1": "Under the Gun +1",
        "MP": "Middle Position (средняя позиция)",
        "MP+1": "Middle Position +1",
        "HJ": "Hijack (перед катоффом)",
        "CO": "Cutoff (перед баттоном)",
        "BTN": "Button (баттон, лучшая позиция)",
        "SB": "Small Blind (малый блайнд)",
        "BB": "Big Blind (большой блайнд)"
    }

    return descriptions.get(position, position)


def calculate_pot_odds(pot_size: float, call_amount: float) -> Tuple[float, str]:
    """
    Рассчитать шансы банка (pot odds).

    Args:
        pot_size: Размер банка
        call_amount: Сумма для колла

    Returns:
        Tuple (процент, строка "X:1")
    """
    if call_amount <= 0:
        return 0, "0:1"

    odds_ratio = pot_size / call_amount
    odds_percent = (call_amount / (pot_size + call_amount)) * 100

    return odds_percent, f"{odds_ratio:.1f}:1"


def format_recommendation(
    cards: List[str],
    position: str,
    equity: float,
    pot_odds: float,
    opponent_action: str = "raise",
    recommended_action: str = "call"
) -> str:
    """
    Сформировать текст рекомендации.

    Args:
        cards: Карты героя
        position: Позиция героя
        equity: Эквити героя в процентах
        pot_odds: Шансы банка в процентах
        opponent_action: Действие оппонента
        recommended_action: Рекомендуемое действие

    Returns:
        Отформатированный текст рекомендации
    """
    notation = get_hand_notation(cards)
    percentile = get_hand_rank_percentile(cards)
    description = get_hand_description(cards)

    lines = [
        f"{EMOJI['robot']} РЕКОМЕНДАЦИЯ",
        "",
        f"{EMOJI['cards']} Твоя рука: {format_cards(cards)} ({notation} — {description})",
        f"{EMOJI['stats']} Рейтинг: Топ {100 - percentile:.0f}% всех рук",
        "",
        f"{EMOJI['chart']} Расчёт эквити:",
        f"   • Эквити: ~{equity:.0f}%",
        f"   • Pot odds: {pot_odds:.1f}%",
        "",
    ]

    # Определяем рекомендацию
    if equity > pot_odds + 10:
        lines.append(f"{EMOJI['target']} Рекомендация: **{format_action(recommended_action).upper()}**")
        lines.append("")
        lines.append(f"{EMOJI['tip']} Совет:")
        lines.append(f"   Твоё эквити ({equity:.0f}%) значительно выше")
        lines.append(f"   шансов банка ({pot_odds:.1f}%) — прибыльный колл/рейз.")
    elif equity < pot_odds - 5:
        lines.append(f"{EMOJI['target']} Рекомендация: **ФОЛД**")
        lines.append("")
        lines.append(f"{EMOJI['tip']} Совет:")
        lines.append(f"   Эквити ({equity:.0f}%) ниже шансов банка")
        lines.append(f"   ({pot_odds:.1f}%) — невыгодно продолжать.")
    else:
        lines.append(f"{EMOJI['target']} Рекомендация: **КОЛЛ** (пограничная ситуация)")
        lines.append("")
        lines.append(f"{EMOJI['tip']} Совет:")
        lines.append(f"   Эквити близко к шансам банка.")
        lines.append(f"   Решение зависит от стиля игры оппонента.")

    return "\n".join(lines)


def validate_cards(cards: List[str]) -> bool:
    """
    Проверить валидность карт.

    Args:
        cards: Список карт

    Returns:
        True если все карты валидны
    """
    valid_ranks = set(RANKS)
    valid_suits = set(SUITS.keys())

    for card in cards:
        if len(card) != 2:
            return False
        if card[0].upper() not in valid_ranks:
            return False
        if card[1].lower() not in valid_suits:
            return False

    # Проверка на дубликаты
    if len(cards) != len(set(cards)):
        return False

    return True
