"""
Модуль анализа блокеров

Блокеры — карты в руке, которые уменьшают вероятность
того, что у оппонента определённые комбинации.
"""

from typing import List, Dict, Tuple

# Комбинации карт для анализа блокеров
PREMIUM_HANDS = ["AA", "KK", "QQ", "JJ", "AK"]
STRONG_HANDS = ["TT", "99", "AQ", "AJ", "KQ"]


def analyze_blockers(hero_cards: List[str]) -> Dict:
    """
    Анализирует блокеры в руке героя.

    Args:
        hero_cards: Карты героя ["As", "Kh"]

    Returns:
        Dict с информацией о блокерах
    """
    if len(hero_cards) != 2:
        return {"effect": "unknown", "blocks": [], "description": ""}

    rank1 = hero_cards[0][0].upper()
    rank2 = hero_cards[1][0].upper()

    blocks = []
    descriptions = []
    effect_score = 0  # -100 to +100

    # Блокируем AA
    if rank1 == "A" or rank2 == "A":
        ace_count = (1 if rank1 == "A" else 0) + (1 if rank2 == "A" else 0)
        blocks.append(f"AA ({ace_count}/4 = {ace_count * 25}%)")
        effect_score += ace_count * 15
        if ace_count == 2:
            descriptions.append("Полностью блокируем AA")
        else:
            descriptions.append("Блокируем 50% комбо AA")

    # Блокируем KK
    if rank1 == "K" or rank2 == "K":
        king_count = (1 if rank1 == "K" else 0) + (1 if rank2 == "K" else 0)
        blocks.append(f"KK ({king_count}/4 = {king_count * 25}%)")
        effect_score += king_count * 12
        if king_count == 2:
            descriptions.append("Полностью блокируем KK")
        else:
            descriptions.append("Блокируем 50% комбо KK")

    # Блокируем QQ
    if rank1 == "Q" or rank2 == "Q":
        queen_count = (1 if rank1 == "Q" else 0) + (1 if rank2 == "Q" else 0)
        blocks.append(f"QQ ({queen_count * 25}%)")
        effect_score += queen_count * 10

    # Блокируем AK
    if (rank1 == "A" and rank2 == "K") or (rank1 == "K" and rank2 == "A"):
        blocks.append("AK (75% комбо)")
        effect_score += 20
        descriptions.append("Сильно блокируем AK")
    elif rank1 == "A" or rank2 == "A":
        blocks.append("AK (25% комбо)")
        effect_score += 5
    elif rank1 == "K" or rank2 == "K":
        blocks.append("AK (25% комбо)")
        effect_score += 5

    # Блокируем AQ
    if (rank1 == "A" and rank2 == "Q") or (rank1 == "Q" and rank2 == "A"):
        blocks.append("AQ (75% комбо)")
        effect_score += 15

    # Определяем общий эффект
    if effect_score >= 30:
        effect = "strong"
        effect_text = "🔥 Сильные блокеры"
    elif effect_score >= 15:
        effect = "moderate"
        effect_text = "👍 Хорошие блокеры"
    elif effect_score > 0:
        effect = "weak"
        effect_text = "💡 Слабые блокеры"
    else:
        effect = "none"
        effect_text = "❌ Нет значимых блокеров"

    return {
        "effect": effect,
        "effect_score": effect_score,
        "effect_text": effect_text,
        "blocks": blocks,
        "descriptions": descriptions
    }


def get_blocker_adjustment(
    hero_cards: List[str],
    action: str = "3bet"
) -> Tuple[float, str]:
    """
    Получить корректировку частоты на основе блокеров.

    Args:
        hero_cards: Карты героя
        action: Действие (3bet, bluff, call)

    Returns:
        Tuple (корректировка в %, описание)
    """
    analysis = analyze_blockers(hero_cards)
    score = analysis["effect_score"]

    if action == "3bet":
        # Блокеры увеличивают EV 3-бета
        # (оппонент реже имеет премиум для 4-бета)
        if score >= 30:
            return 10, "Блокеры добавляют +10% к 3-bet"
        elif score >= 15:
            return 5, "Блокеры добавляют +5% к 3-bet"
        return 0, ""

    elif action == "bluff":
        # Блокеры критичны для блефа
        if score >= 30:
            return 15, "Отличные блокеры для блефа"
        elif score >= 15:
            return 8, "Хорошие блокеры для блефа"
        elif score <= 0:
            return -10, "Плохие блокеры, осторожнее с блефом"
        return 0, ""

    elif action == "call":
        # Блокеры менее важны для колла
        if score >= 30:
            return 5, "Блокеры помогают"
        return 0, ""

    return 0, ""


def format_blockers_text(hero_cards: List[str]) -> str:
    """
    Форматировать текст о блокерах для вывода.

    Args:
        hero_cards: Карты героя

    Returns:
        Отформатированный текст
    """
    analysis = analyze_blockers(hero_cards)

    if analysis["effect"] == "none":
        return "• Нет значимых блокеров"

    lines = [f"🎯 {analysis['effect_text']}:"]

    for block in analysis["blocks"][:3]:  # Максимум 3
        lines.append(f"  • Блокируем {block}")

    return "\n".join(lines)


def get_fold_equity_adjustment(
    hero_cards: List[str],
    opponent_type: str = "unknown"
) -> float:
    """
    Корректировка fold equity на основе блокеров и типа оппонента.

    Args:
        hero_cards: Карты героя
        opponent_type: Тип оппонента

    Returns:
        Корректировка fold equity в процентах
    """
    analysis = analyze_blockers(hero_cards)
    base_adjustment = analysis["effect_score"] / 5  # 0-20%

    # Корректировка по типу оппа
    type_multipliers = {
        "unknown": 1.0,
        "fish": 0.3,      # Фиши не думают о наших блокерах
        "reg": 1.2,       # Реги понимают, мы чаще блефуем с блокерами
        "nit": 1.5,       # Ниты боятся, блокеры работают лучше
        "lag": 0.8,       # LAG'и не уважают
        "maniac": 0.2,    # Маньякам всё равно
    }

    multiplier = type_multipliers.get(opponent_type, 1.0)

    return base_adjustment * multiplier
