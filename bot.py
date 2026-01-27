"""
Poker Assistant Bot — Telegram бот для помощи в игре в покер

Главный файл с логикой бота.
"""

import logging
from typing import Dict, Any

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters
)

from config import (
    TELEGRAM_BOT_TOKEN,
    validate_config,
    setup_logging,
    States,
    EMOJI,
    STAGES,
    POSITIONS_SHORT
)
from database import get_or_create_user, save_hand, get_user_stats
from utils.keyboards import (
    get_cards_keyboard,
    get_position_keyboard,
    get_stage_keyboard,
    get_players_count_keyboard,
    get_action_keyboard,
    get_hero_action_keyboard,
    get_pot_size_keyboard,
    get_result_keyboard,
    get_winner_showed_keyboard,
    get_main_menu_keyboard,
    get_after_hand_keyboard
)
from utils.helpers import (
    format_cards,
    format_card,
    get_hand_notation,
    get_hand_rank_percentile,
    get_hand_description,
    format_action,
    format_actions_summary,
    calculate_pot_odds
)
from poker_logic.hand_evaluator import get_hand_strength_description
from poker_logic.equity import (
    calculate_equity_vs_position,
    get_recommendation,
    quick_equity_estimate
)

# Настройка логирования
logger = setup_logging()


# ================== КОМАНДЫ ==================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start — приветствие и главное меню."""
    user = update.effective_user

    # Создаём/обновляем пользователя в БД
    get_or_create_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name
    )

    welcome_text = f"""
{EMOJI['cards']} **Poker Assistant Bot**

Привет, {user.first_name}! 👋

Я помогу тебе принимать оптимальные решения за покерным столом.

{EMOJI['target']} **Что я умею:**
• Анализировать твои карты и позицию
• Рассчитывать эквити против диапазонов
• Давать рекомендации по действиям
• Сохранять историю раздач
• Показывать статистику

{EMOJI['tip']} **Команды:**
/new\\_hand — Начать анализ новой раздачи
/stats — Твоя статистика
/help — Помощь

Нажми кнопку ниже, чтобы начать!
"""

    await update.message.reply_text(
        welcome_text,
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help — справка по боту."""
    help_text = f"""
{EMOJI['tip']} **Как пользоваться ботом**

**1. Новая раздача** (/new\\_hand)
Пошаговый ввод данных о текущей раздаче:
• Выбери свои карты (2 карты)
• Укажи позицию за столом
• Выбери стадию (префлоп/флоп/тёрн/ривер)
• Введи количество игроков
• Укажи действия оппонентов
• Получи рекомендацию!

**2. Статистика** (/stats)
Посмотри свою историю:
• Всего сыгранных раздач
• Процент побед
• Любимые позиции
• Последние раздачи

**3. Позиции в покере**
• **UTG** — первый после блайндов (тайтовая игра)
• **MP** — средняя позиция
• **CO** — катофф (перед баттоном)
• **BTN** — баттон (лучшая позиция!)
• **SB** — малый блайнд
• **BB** — большой блайнд

**4. Что такое эквити?**
Эквити — вероятность выиграть раздачу против диапазона оппонента.
Если эквити > шансов банка → выгодно продолжать.

{EMOJI['robot']} Удачной игры!
"""

    await update.message.reply_text(
        help_text,
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard()
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /stats — статистика пользователя."""
    user = update.effective_user
    user_id = get_or_create_user(user.id, user.username, user.first_name)

    stats = get_user_stats(user_id)

    if stats["total_hands"] == 0:
        text = f"""
{EMOJI['stats']} **Твоя статистика**

У тебя пока нет сохранённых раздач.

Начни с команды /new\\_hand, чтобы записать первую раздачу!
"""
    else:
        # Формируем текст статистики
        win_rate = 0
        if stats["wins"] + stats["losses"] > 0:
            win_rate = stats["wins"] / (stats["wins"] + stats["losses"]) * 100

        # Топ позиции
        positions_text = ""
        if stats["positions"]:
            sorted_pos = sorted(stats["positions"].items(), key=lambda x: x[1], reverse=True)
            positions_text = ", ".join([f"{p}: {c}" for p, c in sorted_pos[:3]])

        text = f"""
{EMOJI['stats']} **Твоя статистика**

📊 **Общая информация:**
• Всего раздач: {stats['total_hands']}
• Побед: {stats['wins']}
• Поражений: {stats['losses']}
• Винрейт: {win_rate:.1f}%

{EMOJI['chart']} **Среднее эквити:** {stats['avg_equity']:.1f}% (если есть данные)

🎯 **Позиции:** {positions_text or 'нет данных'}
"""

        # Последние раздачи
        if stats["recent_hands"]:
            text += f"\n{EMOJI['cards']} **Последние раздачи:**\n"
            for hand in stats["recent_hands"][:5]:
                cards = hand.get("hero_cards", "??")
                pos = hand.get("hero_position", "?")
                result = hand.get("result", "?")
                result_emoji = "🏆" if result == "win" else "😔" if result == "loss" else "➡️"
                text += f"• {cards} ({pos}) {result_emoji}\n"

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard()
    )


# ================== CONVERSATION HANDLER ==================

async def new_hand_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало новой раздачи — команда /new_hand."""
    # Инициализируем данные раздачи
    context.user_data["hand"] = {
        "cards": [],
        "position": None,
        "stage": "preflop",
        "players_count": 6,
        "actions": [],
        "pot_size": None,
        "hero_action": None,
        "result": None,
        "current_player": 0
    }

    text = f"""
{EMOJI['cards']} **Новая раздача**

**Шаг 1/7:** Выбери свои карты

Нажми на первую карту:
"""

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_cards_keyboard(prefix="card")
    )

    return States.SELECT_CARDS


async def new_hand_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало новой раздачи через callback."""
    query = update.callback_query
    await query.answer()

    # Инициализируем данные раздачи
    context.user_data["hand"] = {
        "cards": [],
        "position": None,
        "stage": "preflop",
        "players_count": 6,
        "actions": [],
        "pot_size": None,
        "hero_action": None,
        "result": None,
        "current_player": 0
    }

    text = f"""
{EMOJI['cards']} **Новая раздача**

**Шаг 1/7:** Выбери свои карты

Нажми на первую карту:
"""

    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_cards_keyboard(prefix="card")
    )

    return States.SELECT_CARDS


async def select_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора карты."""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "cancel":
        await query.edit_message_text(
            f"{EMOJI['cross']} Раздача отменена.",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END

    if data.startswith("card:"):
        card = data.split(":")[1]
        hand_data = context.user_data.get("hand", {})
        cards = hand_data.get("cards", [])

        if card not in cards:
            cards.append(card)
            hand_data["cards"] = cards
            context.user_data["hand"] = hand_data

        if len(cards) < 2:
            # Нужна ещё одна карта
            text = f"""
{EMOJI['cards']} **Новая раздача**

**Шаг 1/7:** Выбери свои карты

{EMOJI['check']} Первая карта: {format_card(cards[0])}

Выбери вторую карту:
"""
            await query.edit_message_text(
                text,
                parse_mode="Markdown",
                reply_markup=get_cards_keyboard(selected_cards=cards, prefix="card")
            )
            return States.SELECT_CARDS
        else:
            # Обе карты выбраны — переходим к позиции
            notation = get_hand_notation(cards)
            description = get_hand_description(cards)

            text = f"""
{EMOJI['check']} Твои карты: **{format_cards(cards)}**
({notation} — {description})

**Шаг 2/7:** Выбери свою позицию
"""
            await query.edit_message_text(
                text,
                parse_mode="Markdown",
                reply_markup=get_position_keyboard()
            )
            return States.SELECT_POSITION

    return States.SELECT_CARDS


async def select_position(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора позиции."""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "cancel":
        await query.edit_message_text(
            f"{EMOJI['cross']} Раздача отменена.",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END

    if data.startswith("position:"):
        position = data.split(":")[1]
        context.user_data["hand"]["position"] = position

        cards = context.user_data["hand"]["cards"]

        text = f"""
{EMOJI['check']} Твои карты: **{format_cards(cards)}**
{EMOJI['check']} Позиция: **{position}**

**Шаг 3/7:** Стадия раздачи
"""
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_stage_keyboard()
        )
        return States.SELECT_STAGE

    return States.SELECT_POSITION


async def select_stage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора стадии."""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "cancel":
        await query.edit_message_text(
            f"{EMOJI['cross']} Раздача отменена.",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END

    if data.startswith("stage:"):
        stage = data.split(":")[1]
        context.user_data["hand"]["stage"] = stage

        cards = context.user_data["hand"]["cards"]
        position = context.user_data["hand"]["position"]
        stage_name = STAGES.get(stage, stage)

        text = f"""
{EMOJI['check']} Твои карты: **{format_cards(cards)}**
{EMOJI['check']} Позиция: **{position}**
{EMOJI['check']} Стадия: **{stage_name}**

**Шаг 4/7:** Сколько игроков за столом?
"""
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_players_count_keyboard()
        )
        return States.SELECT_PLAYERS

    return States.SELECT_STAGE


async def select_players(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора количества игроков."""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "cancel":
        await query.edit_message_text(
            f"{EMOJI['cross']} Раздача отменена.",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END

    if data.startswith("players:"):
        players_count = int(data.split(":")[1])
        context.user_data["hand"]["players_count"] = players_count
        context.user_data["hand"]["current_player"] = 0

        hand = context.user_data["hand"]
        cards = hand["cards"]
        position = hand["position"]
        stage = hand["stage"]
        stage_name = STAGES.get(stage, stage)

        # Определяем позиции оппонентов
        hero_pos_idx = POSITIONS_SHORT.index(position) if position in POSITIONS_SHORT else 0
        opponent_positions = []

        for i in range(players_count - 1):
            pos_idx = (hero_pos_idx + i + 1) % len(POSITIONS_SHORT)
            if pos_idx != hero_pos_idx:
                opponent_positions.append(POSITIONS_SHORT[pos_idx])

        context.user_data["hand"]["opponent_positions"] = opponent_positions[:players_count - 1]

        text = f"""
{EMOJI['check']} Твои карты: **{format_cards(cards)}**
{EMOJI['check']} Позиция: **{position}**
{EMOJI['check']} Стадия: **{stage_name}**
{EMOJI['check']} Игроков: **{players_count}**

**Шаг 5/7:** Действия оппонентов

Игрок 1 ({opponent_positions[0] if opponent_positions else 'UTG'}):
"""
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_action_keyboard(
                opponent_positions[0] if opponent_positions else "UTG",
                0,
                allow_check=True
            )
        )
        return States.OPPONENT_ACTIONS

    return States.SELECT_PLAYERS


async def opponent_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка действия оппонента."""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "cancel":
        await query.edit_message_text(
            f"{EMOJI['cross']} Раздача отменена.",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END

    if data.startswith("action:"):
        parts = data.split(":")
        player_num = int(parts[1])
        action = parts[2]
        amount = float(parts[3]) if parts[3] else 0

        hand = context.user_data["hand"]
        opponent_positions = hand.get("opponent_positions", [])

        if action != "skip":
            # Сохраняем действие
            hand["actions"].append({
                "position": opponent_positions[player_num] if player_num < len(opponent_positions) else f"Игрок {player_num + 1}",
                "action": action,
                "amount": amount,
                "stage": hand["stage"]
            })

        # Проверяем, есть ли ещё оппоненты
        next_player = player_num + 1
        total_opponents = hand["players_count"] - 1

        if next_player < total_opponents:
            # Следующий оппонент
            hand["current_player"] = next_player
            context.user_data["hand"] = hand

            # Формируем текст с уже введёнными действиями
            actions_text = format_actions_summary(hand["actions"]) if hand["actions"] else "Нет действий"

            next_pos = opponent_positions[next_player] if next_player < len(opponent_positions) else f"Игрок {next_player + 1}"

            text = f"""
{EMOJI['stats']} **Действия:**
{actions_text}

Игрок {next_player + 1} ({next_pos}):
"""
            # Определяем, может ли игрок сделать чек
            has_bet = any(a["action"] in ["raise", "allin"] for a in hand["actions"])

            await query.edit_message_text(
                text,
                parse_mode="Markdown",
                reply_markup=get_action_keyboard(
                    next_pos,
                    next_player,
                    allow_check=not has_bet
                )
            )
            return States.OPPONENT_ACTIONS

        else:
            # Все оппоненты ввели действия — переходим к размеру банка
            actions_text = format_actions_summary(hand["actions"]) if hand["actions"] else "Все скинули"

            text = f"""
{EMOJI['stats']} **Действия префлоп:**
{actions_text}
└─ Твой ход ({hand['position']})

**Шаг 6/7:** Размер банка

Выбери или введи размер банка в bb:
"""
            await query.edit_message_text(
                text,
                parse_mode="Markdown",
                reply_markup=get_pot_size_keyboard()
            )
            return States.POT_SIZE

    return States.OPPONENT_ACTIONS


async def pot_size_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора размера банка."""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "cancel":
        await query.edit_message_text(
            f"{EMOJI['cross']} Раздача отменена.",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END

    if data.startswith("pot:"):
        value = data.split(":")[1]

        if value == "manual":
            await query.edit_message_text(
                f"Введи размер банка в bb (например: 7.5):",
                parse_mode="Markdown"
            )
            return States.POT_SIZE

        pot_size = float(value)
        context.user_data["hand"]["pot_size"] = pot_size

        # Показываем рекомендацию
        return await show_recommendation(query, context)

    return States.POT_SIZE


async def pot_size_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода размера банка текстом."""
    try:
        pot_size = float(update.message.text.replace(",", "."))
        context.user_data["hand"]["pot_size"] = pot_size

        # Показываем рекомендацию
        return await show_recommendation_message(update, context)
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат. Введи число, например: 7.5",
            reply_markup=get_pot_size_keyboard()
        )
        return States.POT_SIZE


async def show_recommendation(query, context: ContextTypes.DEFAULT_TYPE):
    """Показать рекомендацию (для callback)."""
    hand = context.user_data["hand"]

    cards = hand["cards"]
    position = hand["position"]
    stage = hand["stage"]
    pot_size = hand["pot_size"]
    actions = hand["actions"]

    # Определяем позицию последнего агрессора
    villain_position = "UTG"
    call_amount = 1  # По умолчанию 1bb

    for action in reversed(actions):
        if action["action"] in ["raise", "allin"]:
            villain_position = action["position"]
            call_amount = action["amount"] if action["amount"] else 3
            break

    # Получаем рекомендацию
    recommendation = get_recommendation(
        hero_cards=cards,
        hero_position=position,
        villain_position=villain_position,
        villain_action="raise",
        pot_size=pot_size,
        call_amount=call_amount
    )

    notation = get_hand_notation(cards)
    percentile = get_hand_rank_percentile(cards)
    description = get_hand_description(cards)

    # Формируем текст рекомендации
    text = f"""
{EMOJI['robot']} **РЕКОМЕНДАЦИЯ**

{EMOJI['cards']} Твоя рука: **{format_cards(cards)}** ({notation})
{description}
{EMOJI['stats']} Рейтинг: Топ {100 - percentile:.0f}% всех рук

{EMOJI['tip']} **Анализ ситуации:**
• Диапазон {villain_position}: ~{recommendation['villain_range_percent']}% рук
• Твоё эквити: **{recommendation['equity']:.0f}%**
• Шансы банка: {recommendation['pot_odds']:.1f}%

{EMOJI['chart']} **Расчёт:**
{recommendation['reasoning']}

{EMOJI['target']} **Рекомендация: {format_action(recommendation['action']).upper()}**
(уверенность: {recommendation['confidence']})

Частоты (GTO):
• Рейз: {recommendation['frequencies']['raise']}%
• Колл: {recommendation['frequencies']['call']}%
• Фолд: {recommendation['frequencies']['fold']}%

━━━━━━━━━━━━━━━━━━━━━━━━

**Шаг 7/7:** Твоё действие и результат
"""

    # Сохраняем рекомендацию
    hand["recommendation"] = recommendation
    hand["equity"] = recommendation["equity"]
    context.user_data["hand"] = hand

    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_hero_action_keyboard(recommendation["action"])
    )

    return States.MY_ACTION


async def show_recommendation_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать рекомендацию (для message)."""
    hand = context.user_data["hand"]

    cards = hand["cards"]
    position = hand["position"]
    stage = hand["stage"]
    pot_size = hand["pot_size"]
    actions = hand["actions"]

    # Определяем позицию последнего агрессора
    villain_position = "UTG"
    call_amount = 1

    for action in reversed(actions):
        if action["action"] in ["raise", "allin"]:
            villain_position = action["position"]
            call_amount = action["amount"] if action["amount"] else 3
            break

    # Получаем рекомендацию
    recommendation = get_recommendation(
        hero_cards=cards,
        hero_position=position,
        villain_position=villain_position,
        villain_action="raise",
        pot_size=pot_size,
        call_amount=call_amount
    )

    notation = get_hand_notation(cards)
    percentile = get_hand_rank_percentile(cards)
    description = get_hand_description(cards)

    text = f"""
{EMOJI['robot']} **РЕКОМЕНДАЦИЯ**

{EMOJI['cards']} Твоя рука: **{format_cards(cards)}** ({notation})
{description}
{EMOJI['stats']} Рейтинг: Топ {100 - percentile:.0f}% всех рук

{EMOJI['tip']} **Анализ ситуации:**
• Диапазон {villain_position}: ~{recommendation['villain_range_percent']}% рук
• Твоё эквити: **{recommendation['equity']:.0f}%**
• Шансы банка: {recommendation['pot_odds']:.1f}%

{EMOJI['chart']} **Расчёт:**
{recommendation['reasoning']}

{EMOJI['target']} **Рекомендация: {format_action(recommendation['action']).upper()}**
(уверенность: {recommendation['confidence']})

━━━━━━━━━━━━━━━━━━━━━━━━

**Шаг 7/7:** Твоё действие и результат
"""

    hand["recommendation"] = recommendation
    hand["equity"] = recommendation["equity"]
    context.user_data["hand"] = hand

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_hero_action_keyboard(recommendation["action"])
    )

    return States.MY_ACTION


async def hero_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка действия героя."""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("hero:"):
        action = data.split(":")[1]
        context.user_data["hand"]["hero_action"] = action

        text = f"""
{EMOJI['check']} Твоё действие: **{format_action(action)}**

Кто выиграл раздачу?
"""
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_result_keyboard()
        )
        return States.RESULT

    return States.MY_ACTION


async def hand_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка результата раздачи."""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("result:"):
        result = data.split(":")[1]
        hand = context.user_data["hand"]
        hand["result"] = result

        # Сохраняем раздачу в БД
        user = query.from_user
        user_id = get_or_create_user(user.id, user.username, user.first_name)

        hand_id = save_hand(
            user_id=user_id,
            hero_cards=" ".join(hand["cards"]),
            hero_position=hand["position"],
            stage=hand["stage"],
            players_count=hand["players_count"],
            actions=hand["actions"],
            pot_size=hand["pot_size"],
            hero_action=hand["hero_action"],
            result=result,
            recommendation=hand.get("recommendation", {}).get("action"),
            equity=hand.get("equity")
        )

        result_emoji = {
            "win": "🏆 Поздравляю с победой!",
            "loss": "😔 Не повезло в этот раз",
            "fold_win": "🏆 Отлично, забрал банк без борьбы!",
            "folded": "➡️ Фолд — иногда лучшее решение",
            "skip": "📝 Раздача сохранена"
        }

        text = f"""
{EMOJI['check']} **Раздача сохранена!**

{result_emoji.get(result, 'Раздача записана')}

{EMOJI['cards']} Карты: {format_cards(hand['cards'])}
{EMOJI['target']} Позиция: {hand['position']}
{EMOJI['stats']} Эквити: {hand.get('equity', 0):.0f}%

Что дальше?
"""
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_after_hand_keyboard()
        )

        return ConversationHandler.END

    return States.RESULT


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена текущей операции."""
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            f"{EMOJI['cross']} Операция отменена.",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        await update.message.reply_text(
            f"{EMOJI['cross']} Операция отменена.",
            reply_markup=get_main_menu_keyboard()
        )

    return ConversationHandler.END


# ================== MENU CALLBACKS ==================

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопок главного меню."""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "menu:new_hand":
        return await new_hand_callback(update, context)

    elif data == "menu:stats":
        user = query.from_user
        user_id = get_or_create_user(user.id, user.username, user.first_name)
        stats = get_user_stats(user_id)

        if stats["total_hands"] == 0:
            text = f"""
{EMOJI['stats']} **Твоя статистика**

У тебя пока нет сохранённых раздач.
Начни с новой раздачи!
"""
        else:
            win_rate = 0
            if stats["wins"] + stats["losses"] > 0:
                win_rate = stats["wins"] / (stats["wins"] + stats["losses"]) * 100

            text = f"""
{EMOJI['stats']} **Твоя статистика**

• Всего раздач: {stats['total_hands']}
• Побед: {stats['wins']}
• Поражений: {stats['losses']}
• Винрейт: {win_rate:.1f}%
• Среднее эквити: {stats['avg_equity'] or 0:.1f}%
"""

        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )

    elif data == "menu:help":
        help_text = f"""
{EMOJI['tip']} **Быстрая справка**

• /new\\_hand — Новая раздача
• /stats — Статистика
• /help — Полная справка

Выбери действие:
"""
        await query.edit_message_text(
            help_text,
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )

    elif data == "menu:main":
        text = f"""
{EMOJI['cards']} **Poker Assistant Bot**

Выбери действие:
"""
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )

    return ConversationHandler.END


# ================== MAIN ==================

def main():
    """Запуск бота."""
    # Проверяем конфигурацию
    validate_config()

    logger.info("Запуск Poker Assistant Bot...")

    # Создаём приложение
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # ConversationHandler для новой раздачи
    hand_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("new_hand", new_hand_command),
            CallbackQueryHandler(new_hand_callback, pattern="^menu:new_hand$")
        ],
        states={
            States.SELECT_CARDS: [
                CallbackQueryHandler(select_card, pattern="^card:|^cancel$")
            ],
            States.SELECT_POSITION: [
                CallbackQueryHandler(select_position, pattern="^position:|^cancel$")
            ],
            States.SELECT_STAGE: [
                CallbackQueryHandler(select_stage, pattern="^stage:|^cancel$")
            ],
            States.SELECT_PLAYERS: [
                CallbackQueryHandler(select_players, pattern="^players:|^cancel$")
            ],
            States.OPPONENT_ACTIONS: [
                CallbackQueryHandler(opponent_action, pattern="^action:|^cancel$")
            ],
            States.POT_SIZE: [
                CallbackQueryHandler(pot_size_callback, pattern="^pot:|^cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, pot_size_text)
            ],
            States.MY_ACTION: [
                CallbackQueryHandler(hero_action, pattern="^hero:")
            ],
            States.RESULT: [
                CallbackQueryHandler(hand_result, pattern="^result:")
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel, pattern="^cancel$")
        ],
        allow_reentry=True
    )

    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(hand_conv_handler)
    application.add_handler(CallbackQueryHandler(menu_callback, pattern="^menu:"))

    # Запускаем бота
    logger.info("Бот запущен. Нажмите Ctrl+C для остановки.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
