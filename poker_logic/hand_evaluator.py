"""
Модуль оценки покерных рук

Использует библиотеку treys для определения силы комбинаций.
"""

import logging
from typing import List, Tuple, Optional

try:
    from treys import Card, Evaluator, Deck
    TREYS_AVAILABLE = True
except ImportError:
    TREYS_AVAILABLE = False
    logging.warning("Библиотека treys не установлена. Используется упрощённая оценка.")

logger = logging.getLogger(__name__)


# Названия комбинаций на русском
HAND_NAMES = {
    1: "Роял-флеш",
    2: "Стрит-флеш",
    3: "Каре",
    4: "Фулл-хаус",
    5: "Флеш",
    6: "Стрит",
    7: "Тройка (сет)",
    8: "Две пары",
    9: "Пара",
    10: "Старшая карта"
}


def convert_card_to_treys(card: str) -> int:
    """
    Конвертировать карту из нашего формата в формат treys.

    Args:
        card: Карта в формате "As", "Kh", "Td"

    Returns:
        Карта в формате treys (int)
    """
    if not TREYS_AVAILABLE:
        return 0

    # Treys использует тот же формат, но с заглавными мастями
    rank = card[0].upper()
    suit = card[1].lower()

    # T -> T (ten) - treys понимает
    return Card.new(f"{rank}{suit}")


def convert_cards_to_treys(cards: List[str]) -> List[int]:
    """
    Конвертировать список карт в формат treys.

    Args:
        cards: Список карт ["As", "Kh"]

    Returns:
        Список карт в формате treys
    """
    if not TREYS_AVAILABLE:
        return []

    return [convert_card_to_treys(card) for card in cards]


def evaluate_hand(
    hole_cards: List[str],
    board: Optional[List[str]] = None
) -> Tuple[int, str, int]:
    """
    Оценить покерную руку.

    Args:
        hole_cards: Карманные карты игрока (2 карты)
        board: Карты на столе (3-5 карт для флопа/тёрна/ривера)

    Returns:
        Tuple (rank, hand_name, score):
            - rank: Ранг руки (1-10, где 1 = лучшая)
            - hand_name: Название комбинации на русском
            - score: Точный скор (меньше = лучше)
    """
    if not TREYS_AVAILABLE or board is None or len(board) < 3:
        # Возвращаем базовую оценку на префлопе
        return evaluate_preflop_hand(hole_cards)

    try:
        evaluator = Evaluator()

        treys_hole = convert_cards_to_treys(hole_cards)
        treys_board = convert_cards_to_treys(board)

        # Получаем скор (меньше = лучше, от 1 до 7462)
        score = evaluator.evaluate(treys_board, treys_hole)

        # Получаем класс руки (1-9)
        rank_class = evaluator.get_rank_class(score)

        # Название комбинации
        hand_name = HAND_NAMES.get(rank_class, "Неизвестно")

        return rank_class, hand_name, score

    except Exception as e:
        logger.error(f"Ошибка оценки руки: {e}")
        return 10, "Старшая карта", 7462


def evaluate_preflop_hand(hole_cards: List[str]) -> Tuple[int, str, int]:
    """
    Оценить руку на префлопе (без борда).

    Args:
        hole_cards: Карманные карты (2 карты)

    Returns:
        Tuple (rank, description, score)
    """
    if len(hole_cards) != 2:
        return 10, "Неверные карты", 7462

    rank1 = hole_cards[0][0].upper()
    rank2 = hole_cards[1][0].upper()
    suit1 = hole_cards[0][1].lower()
    suit2 = hole_cards[1][1].lower()

    is_pair = rank1 == rank2
    is_suited = suit1 == suit2

    ranks = "AKQJT98765432"

    # Премиум пары
    if is_pair:
        pair_rank = ranks.index(rank1)
        if pair_rank <= 1:  # AA, KK
            return 1, f"Пара {rank1}{rank1} (монстр)", 100
        elif pair_rank <= 3:  # QQ, JJ
            return 2, f"Пара {rank1}{rank1} (премиум)", 300
        elif pair_rank <= 5:  # TT, 99
            return 3, f"Пара {rank1}{rank1} (сильная)", 600
        else:
            return 4, f"Пара {rank1}{rank1}", 1000

    # Сортируем карты по силе
    if ranks.index(rank1) > ranks.index(rank2):
        rank1, rank2 = rank2, rank1

    # Бродвеи (высокие карты)
    if rank1 in "AKQJ" and rank2 in "AKQJT":
        if is_suited:
            return 2, f"{rank1}{rank2}s (премиум suited)", 400
        else:
            return 3, f"{rank1}{rank2}o (бродвей)", 700

    # Suited коннекторы
    gap = abs(ranks.index(rank1) - ranks.index(rank2))
    if is_suited and gap <= 2:
        return 4, f"{rank1}{rank2}s (suited коннектор)", 1200

    # Туз с кикером
    if rank1 == "A":
        if is_suited:
            return 5, f"A{rank2}s (suited ace)", 1500
        else:
            return 6, f"A{rank2}o (offsuit ace)", 2000

    # Остальные suited
    if is_suited:
        return 7, f"{rank1}{rank2}s (suited)", 3000

    # Остальные руки
    return 8, f"{rank1}{rank2}o (слабая)", 5000


def compare_hands(
    hand1: List[str],
    hand2: List[str],
    board: List[str]
) -> int:
    """
    Сравнить две руки на данном борде.

    Args:
        hand1: Первая рука (2 карты)
        hand2: Вторая рука (2 карты)
        board: Борд (3-5 карт)

    Returns:
        1 если hand1 выигрывает, -1 если hand2, 0 если ничья
    """
    if not TREYS_AVAILABLE or len(board) < 3:
        # Упрощённое сравнение
        _, _, score1 = evaluate_preflop_hand(hand1)
        _, _, score2 = evaluate_preflop_hand(hand2)
    else:
        _, _, score1 = evaluate_hand(hand1, board)
        _, _, score2 = evaluate_hand(hand2, board)

    if score1 < score2:
        return 1
    elif score1 > score2:
        return -1
    return 0


def get_hand_strength_description(
    hole_cards: List[str],
    board: Optional[List[str]] = None
) -> str:
    """
    Получить текстовое описание силы руки.

    Args:
        hole_cards: Карманные карты
        board: Борд (опционально)

    Returns:
        Описание силы руки
    """
    rank, name, score = evaluate_hand(hole_cards, board)

    if board and len(board) >= 3:
        # Постфлоп оценка
        if rank <= 2:
            strength = "🔥 Очень сильная!"
        elif rank <= 4:
            strength = "💪 Сильная"
        elif rank <= 6:
            strength = "👍 Средняя"
        elif rank <= 8:
            strength = "🤔 Слабая"
        else:
            strength = "😐 Очень слабая"

        return f"{name} ({strength})"
    else:
        # Префлоп оценка
        if rank <= 2:
            return f"🔥 {name}"
        elif rank <= 4:
            return f"💪 {name}"
        elif rank <= 6:
            return f"👍 {name}"
        else:
            return f"🤔 {name}"


def get_outs(
    hole_cards: List[str],
    board: List[str],
    target_hands: Optional[List[str]] = None
) -> Tuple[int, List[str]]:
    """
    Подсчитать ауты (карты, улучшающие руку).

    Args:
        hole_cards: Карманные карты
        board: Текущий борд
        target_hands: Целевые комбинации (опционально)

    Returns:
        Tuple (количество аутов, список аутов)
    """
    if not TREYS_AVAILABLE or len(board) < 3:
        return 0, []

    # Упрощённый подсчёт аутов
    # TODO: Реализовать полный подсчёт

    outs = []
    outs_count = 0

    # Определяем текущую руку
    current_rank, _, current_score = evaluate_hand(hole_cards, board)

    # Создаём колоду без известных карт
    known_cards = set(hole_cards + board)
    deck = [
        f"{r}{s}"
        for r in "AKQJT98765432"
        for s in "shdc"
        if f"{r}{s}" not in known_cards
    ]

    # Проверяем каждую карту
    for card in deck:
        new_board = board + [card]
        if len(new_board) <= 5:
            new_rank, _, new_score = evaluate_hand(hole_cards, new_board)
            if new_score < current_score:
                outs.append(card)
                outs_count += 1

    return outs_count, outs[:10]  # Возвращаем максимум 10 аутов
