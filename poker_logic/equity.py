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


# ================== V2.0 RECOMMENDATION ==================

def get_recommendation_v2(
    hero_cards: List[str],
    hero_position: str,
    stack_bb: float,
    line: str,
    opponent_type: str,
    facing_bet: float = 0,
    aggressor_position: str = None
) -> Dict:
    """
    Получить рекомендацию v2.0 с частотами, confidence и blockers.

    Args:
        hero_cards: Карты героя
        hero_position: Позиция героя
        stack_bb: Эффективный стек в bb
        line: Тип линии (rfi, vs_open, vs_3bet, etc.)
        opponent_type: Тип оппонента
        facing_bet: Размер ставки, которую фейсим
        aggressor_position: Позиция агрессора

    Returns:
        Dict с полной рекомендацией
    """
    from utils.helpers import get_hand_rank_percentile, get_hand_notation, get_hand_description
    from .blockers import analyze_blockers, get_blocker_adjustment

    # Базовая информация о руке
    notation = get_hand_notation(hero_cards)
    percentile = get_hand_rank_percentile(hero_cards)
    description = get_hand_description(hero_cards)

    # Анализ блокеров
    blocker_analysis = analyze_blockers(hero_cards)
    blocker_adj, blocker_reason = get_blocker_adjustment(hero_cards, "3bet")

    # Параметры оппонента
    opponent_params = {
        "unknown": {"open_range": 20, "fold_to_3bet": 55, "4bet_range": 5},
        "fish": {"open_range": 35, "fold_to_3bet": 30, "4bet_range": 3},
        "reg": {"open_range": 18, "fold_to_3bet": 58, "4bet_range": 6},
        "nit": {"open_range": 10, "fold_to_3bet": 70, "4bet_range": 3},
        "lag": {"open_range": 28, "fold_to_3bet": 45, "4bet_range": 10},
        "maniac": {"open_range": 45, "fold_to_3bet": 25, "4bet_range": 15},
    }

    opp = opponent_params.get(opponent_type, opponent_params["unknown"])

    # Расчёт SPR
    pot_estimate = 1.5 if line == "rfi" else (facing_bet * 2 + 1.5)
    spr = stack_bb / pot_estimate if pot_estimate > 0 else 100

    # Определяем позицию агрессора
    if aggressor_position is None:
        aggressor_position = "MP"  # По умолчанию

    # Расчёт эквити
    if line == "rfi":
        # Открытие - не нужен расчёт против диапазона
        equity = percentile
        pot_odds = 0
    else:
        # vs action - считаем против диапазона агрессора
        equity, _ = calculate_equity_vs_position(
            hero_cards,
            aggressor_position,
            "open",
            500
        )
        pot_odds = calculate_pot_odds(pot_estimate, facing_bet) if facing_bet > 0 else 0

    # Базовые частоты по линии и силе руки
    if line == "rfi":
        frequencies = _get_rfi_frequencies(hero_position, percentile)
        primary_action = "raise" if frequencies["raise"] > 50 else "fold"
    elif line == "vs_open":
        frequencies = _get_vs_open_frequencies(
            hero_position, aggressor_position, percentile, opp, blocker_adj
        )
        if frequencies["raise"] >= frequencies["call"] and frequencies["raise"] >= frequencies["fold"]:
            primary_action = "raise"
        elif frequencies["call"] >= frequencies["fold"]:
            primary_action = "call"
        else:
            primary_action = "fold"
    elif line == "vs_3bet":
        frequencies = _get_vs_3bet_frequencies(percentile, opp, stack_bb)
        if frequencies["raise"] >= frequencies["call"] and frequencies["raise"] >= frequencies["fold"]:
            primary_action = "raise"
        elif frequencies["call"] >= frequencies["fold"]:
            primary_action = "call"
        else:
            primary_action = "fold"
    elif line == "vs_4bet":
        frequencies = _get_vs_4bet_frequencies(percentile, stack_bb)
        primary_action = "call" if frequencies["call"] > frequencies["fold"] else "fold"
    else:
        # Default
        frequencies = {"raise": 30, "call": 40, "fold": 30}
        primary_action = "call"

    # Расчёт confidence
    confidence = _calculate_confidence(percentile, opponent_type, line)

    # Расчёт примерного EV
    ev_estimate = _estimate_ev(
        equity, pot_estimate, facing_bet, frequencies, opp["fold_to_3bet"]
    )

    # Формируем reasons
    reasons = []
    reasons.append(f"{notation} — {description}")
    reasons.append(f"Топ {100 - percentile:.0f}% рук")

    if line != "rfi":
        reasons.append(f"Range {aggressor_position}: ~{opp['open_range']}%")
        reasons.append(f"Equity vs range: {equity:.0f}%")

    if blocker_analysis["effect"] != "none":
        reasons.append(blocker_analysis["effect_text"])

    if spr < 4:
        reasons.append(f"⚠️ Low SPR ({spr:.1f}) — commit or fold")
    elif spr > 15:
        reasons.append(f"Deep SPR ({spr:.1f}) — room to maneuver")

    # If/then советы
    if_then = []
    if line == "vs_open" and frequencies["raise"] > 30:
        if_then.append(f"Если 4-bet < {stack_bb * 0.2:.0f}bb → Call")
        if_then.append(f"Если 4-bet > {stack_bb * 0.25:.0f}bb → Fold (без AA/KK)")
    if line == "vs_3bet":
        if_then.append("При AI → считай pot odds")

    # Opponent-specific advice
    opp_advice = _get_opponent_advice(opponent_type, primary_action, percentile)

    return {
        "hand": notation,
        "description": description,
        "percentile": percentile,
        "primary_action": primary_action,
        "frequencies": frequencies,
        "confidence": confidence,
        "confidence_pct": int(confidence * 100),
        "equity": equity,
        "pot_odds": pot_odds,
        "spr": spr,
        "ev_estimate": ev_estimate,
        "blockers": blocker_analysis,
        "reasons": reasons,
        "if_then": if_then,
        "opponent_advice": opp_advice,
        "opponent_type": opponent_type,
        "line": line
    }


def _get_rfi_frequencies(position: str, percentile: float) -> Dict[str, int]:
    """Частоты для RFI (открытия)."""
    # Пороги для RFI по позициям (процентиль руки)
    thresholds = {
        "UTG": 85,  # Топ 15%
        "MP": 80,   # Топ 20%
        "CO": 70,   # Топ 30%
        "BTN": 55,  # Топ 45%
        "SB": 60,   # Топ 40%
        "BB": 100   # Не открываем из BB
    }

    threshold = thresholds.get(position, 75)

    if percentile >= threshold:
        return {"raise": 100, "call": 0, "fold": 0}
    elif percentile >= threshold - 10:
        return {"raise": 70, "call": 0, "fold": 30}
    elif percentile >= threshold - 20:
        return {"raise": 30, "call": 0, "fold": 70}
    else:
        return {"raise": 0, "call": 0, "fold": 100}


def _get_vs_open_frequencies(
    hero_pos: str,
    villain_pos: str,
    percentile: float,
    opp_params: Dict,
    blocker_adj: float
) -> Dict[str, int]:
    """Частоты для vs Open (3-bet или колл)."""
    # Базовые пороги
    three_bet_threshold = 90  # Топ 10% всегда 3bet
    call_threshold = 70       # Топ 30% колл

    # Корректировка на позицию
    if hero_pos in ["BTN", "CO"]:
        three_bet_threshold -= 10
        call_threshold -= 10
    elif hero_pos in ["SB", "BB"]:
        call_threshold -= 5

    # Корректировка на тип оппа
    if opp_params["fold_to_3bet"] > 60:
        three_bet_threshold -= 10  # Больше 3bet vs складывающегося

    # Применяем blocker adjustment
    three_bet_threshold -= blocker_adj

    if percentile >= three_bet_threshold:
        return {"raise": 85, "call": 15, "fold": 0}
    elif percentile >= three_bet_threshold - 10:
        return {"raise": 50, "call": 40, "fold": 10}
    elif percentile >= call_threshold:
        return {"raise": 15, "call": 65, "fold": 20}
    elif percentile >= call_threshold - 15:
        return {"raise": 5, "call": 40, "fold": 55}
    else:
        return {"raise": 0, "call": 10, "fold": 90}


def _get_vs_3bet_frequencies(
    percentile: float,
    opp_params: Dict,
    stack_bb: float
) -> Dict[str, int]:
    """Частоты для vs 3-bet (4-bet или колл)."""
    # Только премиум 4-бетит
    if percentile >= 97:  # AA, KK
        return {"raise": 70, "call": 30, "fold": 0}
    elif percentile >= 93:  # QQ, AKs
        return {"raise": 40, "call": 50, "fold": 10}
    elif percentile >= 85:  # JJ, TT, AK
        return {"raise": 15, "call": 60, "fold": 25}
    elif percentile >= 75:
        return {"raise": 5, "call": 45, "fold": 50}
    else:
        return {"raise": 0, "call": 15, "fold": 85}


def _get_vs_4bet_frequencies(percentile: float, stack_bb: float) -> Dict[str, int]:
    """Частоты для vs 4-bet."""
    if percentile >= 99:  # AA
        return {"raise": 60, "call": 40, "fold": 0}
    elif percentile >= 97:  # KK
        return {"raise": 30, "call": 60, "fold": 10}
    elif percentile >= 93:  # QQ, AKs
        return {"raise": 10, "call": 50, "fold": 40}
    elif percentile >= 88 and stack_bb < 100:  # Short stack considerations
        return {"raise": 5, "call": 35, "fold": 60}
    else:
        return {"raise": 0, "call": 10, "fold": 90}


def _calculate_confidence(percentile: float, opponent_type: str, line: str) -> float:
    """Рассчитать уровень уверенности в рекомендации."""
    base = 0.5

    # Сильные руки = выше confidence
    if percentile >= 90:
        base += 0.25
    elif percentile >= 75:
        base += 0.15
    elif percentile >= 50:
        base += 0.05

    # Unknown оппонент снижает confidence
    if opponent_type == "unknown":
        base -= 0.15
    elif opponent_type in ["fish", "maniac"]:
        base -= 0.05  # Непредсказуемые

    # Простые линии = выше confidence
    if line == "rfi":
        base += 0.1
    elif line == "vs_4bet":
        base += 0.1  # Очевидные решения

    return min(max(base, 0.3), 0.95)


def _estimate_ev(
    equity: float,
    pot: float,
    facing_bet: float,
    frequencies: Dict,
    fold_to_3bet: float
) -> float:
    """Примерная оценка EV (упрощённая)."""
    if frequencies["raise"] > 50:
        # EV 3-бета учитывает fold equity
        fold_eq_ev = (fold_to_3bet / 100) * pot
        call_ev = (1 - fold_to_3bet / 100) * (equity / 100 * (pot + facing_bet * 2) - facing_bet * 2)
        return fold_eq_ev + call_ev
    elif frequencies["call"] > 50:
        # EV колла
        return (equity / 100) * (pot + facing_bet) - facing_bet
    else:
        return 0


def _get_opponent_advice(opponent_type: str, action: str, percentile: float) -> str:
    """Совет, учитывающий тип оппонента."""
    advices = {
        "fish": {
            "raise": "🐟 vs Fish: value bet широко, он заколлит хуже",
            "call": "🐟 vs Fish: можно колл шире, implied odds хорошие",
            "fold": "🐟 vs Fish: даже фиши иногда имеют руку"
        },
        "reg": {
            "raise": "🎮 vs Reg: стандартный 3-bet, он понимает игру",
            "call": "🎮 vs Reg: осторожно постфлоп, он умеет давить",
            "fold": "🎮 vs Reg: правильный фолд, не переплачивай"
        },
        "nit": {
            "raise": "🧊 vs Nit: он сфолдит много, но 4-bet = AA/KK",
            "call": "🧊 vs Nit: осторожно, его range узкий",
            "fold": "🧊 vs Nit: он открывает только премиум"
        },
        "lag": {
            "raise": "🔥 vs LAG: 3-bet для изоляции и value",
            "call": "🔥 vs LAG: готовься к pressure постфлоп",
            "fold": "🔥 vs LAG: иногда лучше дождаться спота получше"
        },
        "maniac": {
            "raise": "🎰 vs Maniac: value 3-bet, он не сфолдит",
            "call": "🎰 vs Maniac: trap с сильными, он сам повесится",
            "fold": "🎰 vs Maniac: даже маньяки попадают в натсы"
        },
        "unknown": {
            "raise": "❓ Unknown: играй GTO, наблюдай за реакцией",
            "call": "❓ Unknown: стандартная игра пока",
            "fold": "❓ Unknown: без инфы не рискуй"
        }
    }

    return advices.get(opponent_type, advices["unknown"]).get(action, "")
