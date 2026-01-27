"""
Модуль расчёта эквити

Вычисляет вероятность выигрыша руки против диапазона оппонента
методом Монте-Карло симуляции.
"""

import random
import logging
from typing import List, Dict, Tuple, Optional, Set

from .hand_evaluator import evaluate_hand, compare_hands

logger = logging.getLogger(__name__)


# Типичные диапазоны рук для разных позиций и действий
POSITION_RANGES = {
    # UTG открывает тайтово (~15% рук)
    "UTG": {
        "open": [
            "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77",
            "AKs", "AQs", "AJs", "ATs", "KQs", "KJs", "QJs",
            "AKo", "AQo", "AJo", "KQo"
        ],
        "range_percent": 15
    },
    # MP немного шире (~18% рук)
    "MP": {
        "open": [
            "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "66",
            "AKs", "AQs", "AJs", "ATs", "A9s", "KQs", "KJs", "KTs", "QJs", "QTs", "JTs",
            "AKo", "AQo", "AJo", "ATo", "KQo", "KJo"
        ],
        "range_percent": 18
    },
    # CO ещё шире (~25% рук)
    "CO": {
        "open": [
            "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "66", "55",
            "AKs", "AQs", "AJs", "ATs", "A9s", "A8s", "A7s", "A6s", "A5s",
            "KQs", "KJs", "KTs", "K9s", "QJs", "QTs", "Q9s", "JTs", "J9s", "T9s", "98s",
            "AKo", "AQo", "AJo", "ATo", "A9o", "KQo", "KJo", "KTo", "QJo", "QTo", "JTo"
        ],
        "range_percent": 25
    },
    # BTN самый широкий (~35% рук)
    "BTN": {
        "open": [
            "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "66", "55", "44", "33", "22",
            "AKs", "AQs", "AJs", "ATs", "A9s", "A8s", "A7s", "A6s", "A5s", "A4s", "A3s", "A2s",
            "KQs", "KJs", "KTs", "K9s", "K8s", "K7s", "K6s",
            "QJs", "QTs", "Q9s", "Q8s", "JTs", "J9s", "J8s", "T9s", "T8s", "98s", "97s", "87s", "76s", "65s", "54s",
            "AKo", "AQo", "AJo", "ATo", "A9o", "A8o", "A7o", "A6o", "A5o",
            "KQo", "KJo", "KTo", "K9o", "QJo", "QTo", "Q9o", "JTo", "J9o", "T9o"
        ],
        "range_percent": 35
    },
    # SB (~30% рук)
    "SB": {
        "open": [
            "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "66", "55", "44",
            "AKs", "AQs", "AJs", "ATs", "A9s", "A8s", "A7s", "A6s", "A5s", "A4s",
            "KQs", "KJs", "KTs", "K9s", "K8s", "QJs", "QTs", "Q9s", "JTs", "J9s", "T9s", "98s", "87s",
            "AKo", "AQo", "AJo", "ATo", "A9o", "A8o", "KQo", "KJo", "KTo", "QJo", "QTo", "JTo"
        ],
        "range_percent": 30
    },
    # BB защищает широко (~40% рук против рейза)
    "BB": {
        "defend": [
            "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "66", "55", "44", "33", "22",
            "AKs", "AQs", "AJs", "ATs", "A9s", "A8s", "A7s", "A6s", "A5s", "A4s", "A3s", "A2s",
            "KQs", "KJs", "KTs", "K9s", "K8s", "K7s", "K6s", "K5s",
            "QJs", "QTs", "Q9s", "Q8s", "Q7s", "JTs", "J9s", "J8s", "T9s", "T8s", "98s", "97s", "87s", "86s", "76s", "75s", "65s", "64s", "54s", "53s", "43s",
            "AKo", "AQo", "AJo", "ATo", "A9o", "A8o", "A7o", "A6o", "A5o", "A4o", "A3o",
            "KQo", "KJo", "KTo", "K9o", "K8o", "QJo", "QTo", "Q9o", "JTo", "J9o", "T9o", "98o", "87o"
        ],
        "range_percent": 40
    }
}


def expand_hand_notation(notation: str) -> List[Tuple[str, str]]:
    """
    Развернуть нотацию руки в конкретные карты.

    Args:
        notation: Нотация типа "AKs", "QQ", "T9o"

    Returns:
        Список кортежей с конкретными картами
    """
    hands = []
    suits = ['s', 'h', 'd', 'c']

    if len(notation) == 2:
        # Пара (например, "AA")
        rank = notation[0]
        for i, s1 in enumerate(suits):
            for s2 in suits[i+1:]:
                hands.append((f"{rank}{s1}", f"{rank}{s2}"))

    elif notation.endswith('s'):
        # Suited (например, "AKs")
        r1, r2 = notation[0], notation[1]
        for suit in suits:
            hands.append((f"{r1}{suit}", f"{r2}{suit}"))

    elif notation.endswith('o'):
        # Offsuit (например, "AKo")
        r1, r2 = notation[0], notation[1]
        for s1 in suits:
            for s2 in suits:
                if s1 != s2:
                    hands.append((f"{r1}{s1}", f"{r2}{s2}"))

    else:
        # Просто две карты
        r1, r2 = notation[0], notation[1]
        for s1 in suits:
            for s2 in suits:
                if r1 != r2 or s1 != s2:
                    hands.append((f"{r1}{s1}", f"{r2}{s2}"))

    return hands


def get_opponent_range(
    position: str,
    action: str = "open"
) -> List[Tuple[str, str]]:
    """
    Получить диапазон рук оппонента на основе позиции и действия.

    Args:
        position: Позиция оппонента
        action: Действие (open, defend, 3bet)

    Returns:
        Список возможных рук [(card1, card2), ...]
    """
    position_data = POSITION_RANGES.get(position, POSITION_RANGES["CO"])
    notations = position_data.get(action, position_data.get("open", []))

    all_hands = []
    for notation in notations:
        all_hands.extend(expand_hand_notation(notation))

    return all_hands


def calculate_preflop_equity(
    hero_cards: List[str],
    opponent_range: List[Tuple[str, str]],
    num_simulations: int = 1000
) -> float:
    """
    Рассчитать эквити на префлопе методом Монте-Карло.

    Args:
        hero_cards: Карты героя ["As", "Kh"]
        opponent_range: Диапазон оппонента
        num_simulations: Количество симуляций

    Returns:
        Эквити в процентах (0-100)
    """
    if not opponent_range:
        return 50.0

    wins = 0
    ties = 0
    total = 0

    deck = [
        f"{r}{s}"
        for r in "AKQJT98765432"
        for s in "shdc"
    ]

    # Убираем карты героя из колоды
    available_cards = [c for c in deck if c not in hero_cards]

    for _ in range(num_simulations):
        # Выбираем случайную руку из диапазона оппонента
        opp_hand = random.choice(opponent_range)

        # Проверяем, что карты оппонента доступны
        if opp_hand[0] in hero_cards or opp_hand[1] in hero_cards:
            continue
        if opp_hand[0] == opp_hand[1]:
            continue

        # Формируем колоду без карт героя и оппонента
        sim_deck = [c for c in available_cards if c not in opp_hand]

        if len(sim_deck) < 5:
            continue

        # Генерируем борд
        board = random.sample(sim_deck, 5)

        # Сравниваем руки
        result = compare_hands(hero_cards, list(opp_hand), board)

        if result > 0:
            wins += 1
        elif result == 0:
            ties += 1

        total += 1

    if total == 0:
        return 50.0

    # Эквити = выигрыши + половина ничьих
    equity = (wins + ties * 0.5) / total * 100
    return equity


def calculate_equity_vs_position(
    hero_cards: List[str],
    villain_position: str,
    villain_action: str = "open",
    num_simulations: int = 1000
) -> Tuple[float, int]:
    """
    Рассчитать эквити против диапазона позиции.

    Args:
        hero_cards: Карты героя
        villain_position: Позиция оппонента
        villain_action: Действие оппонента
        num_simulations: Количество симуляций

    Returns:
        Tuple (эквити в %, процент диапазона оппонента)
    """
    opponent_range = get_opponent_range(villain_position, villain_action)
    equity = calculate_preflop_equity(hero_cards, opponent_range, num_simulations)

    range_percent = POSITION_RANGES.get(villain_position, {}).get("range_percent", 20)

    return equity, range_percent


def calculate_pot_odds(pot_size: float, call_amount: float) -> float:
    """
    Рассчитать шансы банка.

    Args:
        pot_size: Размер банка
        call_amount: Сумма для колла

    Returns:
        Шансы банка в процентах
    """
    if call_amount <= 0:
        return 0.0

    return (call_amount / (pot_size + call_amount)) * 100


def get_recommendation(
    hero_cards: List[str],
    hero_position: str,
    villain_position: str,
    villain_action: str,
    pot_size: float,
    call_amount: float,
    num_simulations: int = 500
) -> Dict:
    """
    Получить рекомендацию по действию.

    Args:
        hero_cards: Карты героя
        hero_position: Позиция героя
        villain_position: Позиция оппонента
        villain_action: Действие оппонента (raise, call, etc.)
        pot_size: Размер банка
        call_amount: Сумма для колла

    Returns:
        Dict с рекомендацией
    """
    # Рассчитываем эквити
    equity, villain_range_percent = calculate_equity_vs_position(
        hero_cards,
        villain_position,
        "open" if villain_action in ["raise", "open"] else "defend",
        num_simulations
    )

    # Рассчитываем шансы банка
    pot_odds = calculate_pot_odds(pot_size, call_amount)

    # Определяем рекомендацию
    equity_edge = equity - pot_odds

    if equity >= 65:
        # Очень сильное эквити - 3-бет/рейз
        action = "raise"
        confidence = "высокая"
        reasoning = f"Эквити {equity:.0f}% значительно выше среднего"

        # Частоты для GTO
        frequencies = {"raise": 80, "call": 20, "fold": 0}

    elif equity >= 50 and equity_edge > 5:
        # Хорошее эквити - колл или рейз
        action = "call"
        confidence = "средняя"
        reasoning = f"Эквити {equity:.0f}% выше шансов банка {pot_odds:.0f}%"

        frequencies = {"raise": 30, "call": 60, "fold": 10}

    elif equity >= 40 and equity_edge > -5:
        # Пограничная ситуация
        action = "call"
        confidence = "низкая"
        reasoning = f"Пограничная ситуация, эквити близко к шансам банка"

        frequencies = {"raise": 10, "call": 50, "fold": 40}

    else:
        # Слабое эквити - фолд
        action = "fold"
        confidence = "высокая"
        reasoning = f"Эквити {equity:.0f}% ниже шансов банка {pot_odds:.0f}%"

        frequencies = {"raise": 0, "call": 10, "fold": 90}

    return {
        "action": action,
        "confidence": confidence,
        "reasoning": reasoning,
        "equity": equity,
        "pot_odds": pot_odds,
        "villain_range_percent": villain_range_percent,
        "frequencies": frequencies
    }


def quick_equity_estimate(
    hero_cards: List[str],
    num_opponents: int = 1
) -> float:
    """
    Быстрая оценка эквити на основе силы руки.

    Args:
        hero_cards: Карты героя
        num_opponents: Количество оппонентов

    Returns:
        Примерное эквити в процентах
    """
    # Используем предварительно рассчитанные значения для скорости
    from utils.helpers import get_hand_rank_percentile

    percentile = get_hand_rank_percentile(hero_cards)

    # Базовое эквити против случайной руки
    base_equity = 50 + (percentile - 50) * 0.8

    # Корректировка на количество оппонентов
    # Чем больше оппонентов, тем меньше эквити
    multiplier = 1 / (1 + 0.15 * (num_opponents - 1))

    return base_equity * multiplier
