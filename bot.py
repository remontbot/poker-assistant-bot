"""
Poker Assistant Bot v2.0 — Telegram бот для помощи в покере

Упрощённый flow с pro-уровнем анализа:
- 5 шагов ввода вместо 7
- Типы оппонентов вместо детальных действий
- Частоты + Confidence + Blockers
"""

import logging
from typing import Dict, Any

from telegram import Update
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
    LINES,
    OPPONENT_TYPES,
    POSITIONS_SHORT,
    ALLOWED_USERS
)
from database import get_or_create_user, save_hand, get_user_stats
from utils.keyboards import (
    get_cards_keyboard,
    get_position_keyboard,
    get_stack_keyboard,
    get_line_keyboard,
    get_opponent_type_keyboard,
    get_facing_bet_keyboard,
    get_recommendation_keyboard,
    get_aggressor_position_keyboard,
    get_main_menu_keyboard,
    get_after_hand_keyboard,
    get_result_keyboard
)
from utils.helpers import (
    format_cards,
    format_card,
    get_hand_notation,
    get_hand_rank_percentile,
    get_hand_description
)
from poker_logic.equity import get_recommendation_v2

# Настройка логирования
logger = setup_logging()

# Сообщение об отказе в доступе
ACCESS_DENIED_MESSAGE = """
🚫 **Доступ запрещён.**

Этот бот находится в закрытом тестировании.
"""


# ================== ПРОВЕРКА ДОСТУПА ==================

def check_access(update: Update) -> bool:
    """Проверяет, есть ли у пользователя доступ к боту."""
    user = update.effective_user
    if not user:
        return False

    if not ALLOWED_USERS:
        return True

    if user.id not in ALLOWED_USERS:
        logger.warning(
            f"Unauthorized access attempt from user_id: {user.id}, "
            f"username: @{user.username or 'unknown'}"
        )
        return False

    return True


async def send_access_denied(update: Update) -> None:
    """Отправляет сообщение об отказе в доступе."""
    if update.callback_query:
        await update.callback_query.answer("Доступ запрещён", show_alert=True)
    elif update.message:
        await update.message.reply_text(ACCESS_DENIED_MESSAGE, parse_mode="Markdown")


# ================== КОМАНДЫ ==================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start."""
    if not check_access(update):
        await send_access_denied(update)
        return

    user = update.effective_user
    get_or_create_user(user.id, user.username, user.first_name)

    text = f"""
🃏 **Poker Assistant Pro v2.0**

Привет, {user.first_name}! 👋

Я помогу принимать решения на уровне профи.

**Что умею:**
• Анализ руки за 5 кликов
• Частоты действий (GTO-стиль)
• Анализ блокеров
• Учёт типа оппонента
• Confidence рекомендаций

**Команды:**
/hand — Быстрый анализ руки
/stats — Статистика
/help — Помощь

Жми кнопку ниже! 👇
"""
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help."""
    if not check_access(update):
        await send_access_denied(update)
        return

    text = f"""
{EMOJI['tip']} **Как пользоваться**

**Быстрый анализ (/hand):**
1️⃣ Выбери карты (2 клика)
2️⃣ Выбери позицию
3️⃣ Укажи стек
4️⃣ Выбери ситуацию (RFI/vs Open/etc)
5️⃣ Выбери тип оппонента
→ Получи рекомендацию!

**Типы оппонентов:**
🐟 **Fish** — слабый, много играет
🎮 **Reg** — регуляр, знает базу
🧊 **Nit** — тайтовый, только премиум
🔥 **LAG** — агрессивный, много рейзит
🎰 **Maniac** — безумный, рейзит всё
❓ **Unknown** — не знаешь ничего

**Что значит вывод:**
• **Частоты** — как часто делать действие (GTO)
• **Confidence** — уверенность рекомендации
• **Blockers** — какие комбо блокируем

Удачи! 🎯
"""
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard()
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /stats."""
    if not check_access(update):
        await send_access_denied(update)
        return

    user = update.effective_user
    user_id = get_or_create_user(user.id, user.username, user.first_name)
    stats = get_user_stats(user_id)

    if stats["total_hands"] == 0:
        text = f"""
{EMOJI['stats']} **Статистика**

Пока нет данных. Начни с /hand!
"""
    else:
        win_rate = 0
        if stats["wins"] + stats["losses"] > 0:
            win_rate = stats["wins"] / (stats["wins"] + stats["losses"]) * 100

        text = f"""
{EMOJI['stats']} **Твоя статистика**

📊 Раздач: {stats['total_hands']}
🏆 Побед: {stats['wins']}
😔 Поражений: {stats['losses']}
📈 Винрейт: {win_rate:.1f}%
🎯 Ср. эквити: {stats['avg_equity'] or 0:.0f}%
"""
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard()
    )


# ================== V2.0 HAND FLOW ==================

async def hand_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало анализа руки — /hand."""
    if not check_access(update):
        await send_access_denied(update)
        return ConversationHandler.END

    context.user_data["hand"] = {
        "cards": [],
        "position": None,
        "stack": 100,
        "line": None,
        "opponent": "unknown",
        "facing_bet": 0,
        "aggressor_pos": None
    }

    text = """
🃏 **Быстрый анализ**

**Шаг 1/5:** Выбери карты
"""
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_cards_keyboard(prefix="card")
    )
    return States.SELECT_CARDS


async def hand_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало через callback."""
    if not check_access(update):
        await send_access_denied(update)
        return ConversationHandler.END

    query = update.callback_query
    await query.answer()

    context.user_data["hand"] = {
        "cards": [],
        "position": None,
        "stack": 100,
        "line": None,
        "opponent": "unknown",
        "facing_bet": 0,
        "aggressor_pos": None
    }

    text = """
🃏 **Быстрый анализ**

**Шаг 1/5:** Выбери карты
"""
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_cards_keyboard(prefix="card")
    )
    return States.SELECT_CARDS


async def select_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор карт."""
    if not check_access(update):
        await send_access_denied(update)
        return ConversationHandler.END

    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "cancel":
        await query.edit_message_text("❌ Отменено", reply_markup=get_main_menu_keyboard())
        return ConversationHandler.END

    if data.startswith("card:"):
        card = data.split(":")[1]
        hand = context.user_data.get("hand", {})
        cards = hand.get("cards", [])

        if card not in cards:
            cards.append(card)
            hand["cards"] = cards
            context.user_data["hand"] = hand

        if len(cards) < 2:
            text = f"""
🃏 **Быстрый анализ**

**Шаг 1/5:** Выбери карты

✅ {format_card(cards[0])} — выбери вторую:
"""
            await query.edit_message_text(
                text,
                parse_mode="Markdown",
                reply_markup=get_cards_keyboard(selected_cards=cards, prefix="card")
            )
            return States.SELECT_CARDS
        else:
            notation = get_hand_notation(cards)
            text = f"""
✅ Карты: **{format_cards(cards)}** ({notation})

**Шаг 2/5:** Твоя позиция
"""
            await query.edit_message_text(
                text,
                parse_mode="Markdown",
                reply_markup=get_position_keyboard()
            )
            return States.SELECT_POSITION

    return States.SELECT_CARDS


async def select_position(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор позиции."""
    if not check_access(update):
        await send_access_denied(update)
        return ConversationHandler.END

    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "cancel":
        await query.edit_message_text("❌ Отменено", reply_markup=get_main_menu_keyboard())
        return ConversationHandler.END

    if data.startswith("position:"):
        position = data.split(":")[1]
        context.user_data["hand"]["position"] = position

        cards = context.user_data["hand"]["cards"]
        text = f"""
✅ {format_cards(cards)} | 📍 {position}

**Шаг 3/5:** Эффективный стек
"""
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_stack_keyboard()
        )
        return States.SELECT_STACK

    return States.SELECT_POSITION


async def select_stack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор стека."""
    if not check_access(update):
        await send_access_denied(update)
        return ConversationHandler.END

    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "cancel":
        await query.edit_message_text("❌ Отменено", reply_markup=get_main_menu_keyboard())
        return ConversationHandler.END

    if data.startswith("stack:"):
        value = data.split(":")[1]
        if value == "custom":
            await query.edit_message_text("Введи стек в bb (например: 85):")
            return States.SELECT_STACK

        stack = int(value)
        context.user_data["hand"]["stack"] = stack

        hand = context.user_data["hand"]
        cards = hand["cards"]
        position = hand["position"]

        text = f"""
✅ {format_cards(cards)} | 📍 {position} | 💰 {stack}bb

**Шаг 4/5:** Ситуация
"""
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_line_keyboard()
        )
        return States.SELECT_LINE

    return States.SELECT_STACK


async def select_stack_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод стека текстом."""
    if not check_access(update):
        await send_access_denied(update)
        return ConversationHandler.END

    try:
        stack = int(update.message.text.strip())
        context.user_data["hand"]["stack"] = stack

        hand = context.user_data["hand"]
        cards = hand["cards"]
        position = hand["position"]

        text = f"""
✅ {format_cards(cards)} | 📍 {position} | 💰 {stack}bb

**Шаг 4/5:** Ситуация
"""
        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_line_keyboard()
        )
        return States.SELECT_LINE
    except ValueError:
        await update.message.reply_text("❌ Введи число. Например: 85")
        return States.SELECT_STACK


async def select_line(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор линии/ситуации."""
    if not check_access(update):
        await send_access_denied(update)
        return ConversationHandler.END

    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "cancel":
        await query.edit_message_text("❌ Отменено", reply_markup=get_main_menu_keyboard())
        return ConversationHandler.END

    if data.startswith("line:"):
        line = data.split(":")[1]
        context.user_data["hand"]["line"] = line

        hand = context.user_data["hand"]
        cards = hand["cards"]
        position = hand["position"]
        stack = hand["stack"]
        line_name = LINES.get(line, line)

        # Для RFI не нужен оппонент — сразу рекомендация
        if line == "rfi":
            context.user_data["hand"]["opponent"] = "unknown"
            return await show_recommendation(query, context)

        text = f"""
✅ {format_cards(cards)} | 📍 {position} | 💰 {stack}bb
📊 {line_name}

**Шаг 5/5:** Тип оппонента
"""
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_opponent_type_keyboard()
        )
        return States.SELECT_OPPONENT

    return States.SELECT_LINE


async def select_opponent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор типа оппонента."""
    if not check_access(update):
        await send_access_denied(update)
        return ConversationHandler.END

    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "cancel":
        await query.edit_message_text("❌ Отменено", reply_markup=get_main_menu_keyboard())
        return ConversationHandler.END

    if data.startswith("opponent:"):
        opponent = data.split(":")[1]
        context.user_data["hand"]["opponent"] = opponent

        hand = context.user_data["hand"]
        line = hand["line"]

        # Для vs_open, vs_3bet нужен facing bet
        if line in ["vs_open", "vs_3bet", "vs_4bet"]:
            text = f"""
👤 Оппонент: {OPPONENT_TYPES[opponent]['name']}

💵 Размер его ставки (bb):
"""
            await query.edit_message_text(
                text,
                parse_mode="Markdown",
                reply_markup=get_facing_bet_keyboard(line)
            )
            return States.FACING_BET

        # Иначе сразу рекомендация
        return await show_recommendation(query, context)

    return States.SELECT_OPPONENT


async def select_facing_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор размера ставки."""
    if not check_access(update):
        await send_access_denied(update)
        return ConversationHandler.END

    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "cancel":
        await query.edit_message_text("❌ Отменено", reply_markup=get_main_menu_keyboard())
        return ConversationHandler.END

    if data.startswith("facing:"):
        value = data.split(":")[1]
        if value == "custom":
            await query.edit_message_text("Введи размер ставки в bb:")
            return States.FACING_BET

        facing = float(value)
        context.user_data["hand"]["facing_bet"] = facing

        return await show_recommendation(query, context)

    return States.FACING_BET


async def select_facing_bet_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод ставки текстом."""
    if not check_access(update):
        await send_access_denied(update)
        return ConversationHandler.END

    try:
        facing = float(update.message.text.replace(",", "."))
        context.user_data["hand"]["facing_bet"] = facing

        # Создаём фейковый query для show_recommendation
        context.user_data["_message"] = update.message
        return await show_recommendation_msg(update.message, context)
    except ValueError:
        await update.message.reply_text("❌ Введи число. Например: 3.5")
        return States.FACING_BET


async def show_recommendation(query, context: ContextTypes.DEFAULT_TYPE):
    """Показать рекомендацию v2.0."""
    hand = context.user_data["hand"]

    rec = get_recommendation_v2(
        hero_cards=hand["cards"],
        hero_position=hand["position"],
        stack_bb=hand["stack"],
        line=hand["line"],
        opponent_type=hand["opponent"],
        facing_bet=hand.get("facing_bet", 0),
        aggressor_position=hand.get("aggressor_pos")
    )

    # Сохраняем рекомендацию
    context.user_data["hand"]["recommendation"] = rec

    text = format_recommendation_text(hand, rec)

    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_recommendation_keyboard()
    )

    return States.SHOW_RECOMMENDATION


async def show_recommendation_msg(message, context: ContextTypes.DEFAULT_TYPE):
    """Показать рекомендацию (для текстового ввода)."""
    hand = context.user_data["hand"]

    rec = get_recommendation_v2(
        hero_cards=hand["cards"],
        hero_position=hand["position"],
        stack_bb=hand["stack"],
        line=hand["line"],
        opponent_type=hand["opponent"],
        facing_bet=hand.get("facing_bet", 0),
        aggressor_position=hand.get("aggressor_pos")
    )

    context.user_data["hand"]["recommendation"] = rec

    text = format_recommendation_text(hand, rec)

    await message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_recommendation_keyboard()
    )

    return States.SHOW_RECOMMENDATION


def format_recommendation_text(hand: Dict, rec: Dict) -> str:
    """Форматирует текст рекомендации."""
    cards_str = format_cards(hand["cards"])
    position = hand["position"]
    stack = hand["stack"]
    line_name = LINES.get(hand["line"], hand["line"])
    opp_name = OPPONENT_TYPES.get(hand["opponent"], {}).get("name", "Unknown")

    # Формируем бар частот
    def freq_bar(pct):
        filled = int(pct / 10)
        return "▓" * filled + "░" * (10 - filled)

    # Confidence dots
    conf_pct = rec["confidence_pct"]
    dots = "●" * (conf_pct // 20) + "○" * (5 - conf_pct // 20)

    # Primary action emoji
    action_emoji = {"raise": "🔥", "call": "📞", "fold": "🚪"}.get(rec["primary_action"], "")

    text = f"""
🎯 **{cards_str}** ({rec['hand']})
📍 {position} | 💰 {stack}bb | {line_name}
👤 {opp_name}

━━━━━━━━━━━━━━━━━━━━

{action_emoji} **{rec['primary_action'].upper()}** — рекомендация

{freq_bar(rec['frequencies']['raise'])} Raise  {rec['frequencies']['raise']}%
{freq_bar(rec['frequencies']['call'])} Call   {rec['frequencies']['call']}%
{freq_bar(rec['frequencies']['fold'])} Fold   {rec['frequencies']['fold']}%

**Confidence:** {dots} ({conf_pct}%)

━━━━━━━━━━━━━━━━━━━━

📊 **Анализ:**
"""

    for reason in rec["reasons"][:4]:
        text += f"• {reason}\n"

    # Blockers
    if rec["blockers"]["effect"] != "none":
        text += f"\n🎯 {rec['blockers']['effect_text']}\n"

    # Opponent advice
    if rec["opponent_advice"]:
        text += f"\n{rec['opponent_advice']}\n"

    # If/then
    if rec["if_then"]:
        text += "\n⚠️ **Если:**\n"
        for it in rec["if_then"][:2]:
            text += f"• {it}\n"

    return text


async def handle_recommendation_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка действий после рекомендации."""
    if not check_access(update):
        await send_access_denied(update)
        return ConversationHandler.END

    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "rec:save":
        # Сохраняем в БД
        user = query.from_user
        user_id = get_or_create_user(user.id, user.username, user.first_name)
        hand = context.user_data["hand"]
        rec = hand.get("recommendation", {})

        save_hand(
            user_id=user_id,
            hero_cards=" ".join(hand["cards"]),
            hero_position=hand["position"],
            stage="preflop",
            players_count=2,
            actions=[],
            pot_size=hand.get("facing_bet", 0) * 2 + 1.5,
            hero_action=rec.get("primary_action"),
            recommendation=rec.get("primary_action"),
            equity=rec.get("equity")
        )

        await query.edit_message_text(
            "✅ Раздача сохранена!\n\nЧто дальше?",
            reply_markup=get_after_hand_keyboard()
        )
        return ConversationHandler.END

    elif data == "rec:postflop":
        await query.edit_message_text(
            "🔜 Postflop анализ в разработке!\n\nПока используй /hand для нового анализа.",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END

    return States.SHOW_RECOMMENDATION


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена."""
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "❌ Отменено",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        await update.message.reply_text(
            "❌ Отменено",
            reply_markup=get_main_menu_keyboard()
        )
    return ConversationHandler.END


# ================== MENU ==================

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка меню."""
    if not check_access(update):
        await send_access_denied(update)
        return ConversationHandler.END

    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "menu:new_hand":
        return await hand_callback(update, context)

    elif data == "menu:stats":
        user = query.from_user
        user_id = get_or_create_user(user.id, user.username, user.first_name)
        stats = get_user_stats(user_id)

        win_rate = 0
        if stats["wins"] + stats["losses"] > 0:
            win_rate = stats["wins"] / (stats["wins"] + stats["losses"]) * 100

        text = f"""
{EMOJI['stats']} **Статистика**

📊 Раздач: {stats['total_hands']}
🏆 Побед: {stats['wins']}
📈 Винрейт: {win_rate:.1f}%
"""
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_main_menu_keyboard())

    elif data == "menu:help":
        text = f"""
{EMOJI['tip']} **Помощь**

/hand — Анализ руки
/stats — Статистика
/help — Справка
"""
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_main_menu_keyboard())

    elif data == "menu:main":
        text = "🃏 **Poker Assistant Pro**\n\nВыбери действие:"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_main_menu_keyboard())

    return ConversationHandler.END


# ================== MAIN ==================

def main():
    """Запуск бота."""
    validate_config()
    logger.info("Запуск Poker Assistant Bot v2.0...")

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # V2.0 Hand Flow
    hand_conv = ConversationHandler(
        entry_points=[
            CommandHandler("hand", hand_command),
            CommandHandler("new_hand", hand_command),
            CallbackQueryHandler(hand_callback, pattern="^menu:new_hand$")
        ],
        states={
            States.SELECT_CARDS: [
                CallbackQueryHandler(select_card, pattern="^card:|^cancel$")
            ],
            States.SELECT_POSITION: [
                CallbackQueryHandler(select_position, pattern="^position:|^cancel$")
            ],
            States.SELECT_STACK: [
                CallbackQueryHandler(select_stack, pattern="^stack:|^cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, select_stack_text)
            ],
            States.SELECT_LINE: [
                CallbackQueryHandler(select_line, pattern="^line:|^cancel$")
            ],
            States.SELECT_OPPONENT: [
                CallbackQueryHandler(select_opponent, pattern="^opponent:|^cancel$")
            ],
            States.FACING_BET: [
                CallbackQueryHandler(select_facing_bet, pattern="^facing:|^cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, select_facing_bet_text)
            ],
            States.SHOW_RECOMMENDATION: [
                CallbackQueryHandler(handle_recommendation_action, pattern="^rec:")
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel, pattern="^cancel$"),
            CallbackQueryHandler(menu_callback, pattern="^menu:")
        ],
        allow_reentry=True
    )

    # Handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(hand_conv)
    application.add_handler(CallbackQueryHandler(menu_callback, pattern="^menu:"))

    logger.info("Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
