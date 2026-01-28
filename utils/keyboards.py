"""
Клавиатуры для Telegram бота

Содержит функции для создания инлайн-клавиатур:
- Выбор карт (52 карты)
- Выбор позиций
- Выбор стадий
- Выбор действий игроков
"""

from typing import List, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import (
    SUITS, RANKS, POSITIONS_SHORT, STAGES, ACTIONS, EMOJI,
    OPPONENT_TYPES, LINES, STACK_PRESETS
)


def get_cards_keyboard(
    selected_cards: Optional[List[str]] = None,
    prefix: str = "card"
) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру для выбора карт.

    Args:
        selected_cards: Уже выбранные карты (будут исключены)
        prefix: Префикс для callback_data

    Returns:
        InlineKeyboardMarkup с кнопками карт
    """
    if selected_cards is None:
        selected_cards = []

    keyboard = []

    # Группируем карты по номиналу (4 карты в ряд - по мастям)
    for rank in RANKS:
        row = []
        for suit_code, suit_symbol in SUITS.items():
            card = f"{rank}{suit_code}"
            if card not in selected_cards:
                # Цвет масти: красный для ♥♦, черный для ♠♣
                display = f"{rank}{suit_symbol}"
                row.append(
                    InlineKeyboardButton(
                        display,
                        callback_data=f"{prefix}:{card}"
                    )
                )
        if row:
            keyboard.append(row)

    # Кнопка отмены
    keyboard.append([
        InlineKeyboardButton("❌ Отмена", callback_data="cancel")
    ])

    return InlineKeyboardMarkup(keyboard)


def get_board_cards_keyboard(
    selected_cards: Optional[List[str]] = None,
    hero_cards: Optional[List[str]] = None,
    min_cards: int = 3,
    max_cards: int = 5
) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру для выбора карт борда.

    Args:
        selected_cards: Уже выбранные карты борда
        hero_cards: Карты героя (исключаются из выбора)
        min_cards: Минимум карт (3 для флопа)
        max_cards: Максимум карт (5 для ривера)

    Returns:
        InlineKeyboardMarkup
    """
    if selected_cards is None:
        selected_cards = []
    if hero_cards is None:
        hero_cards = []

    excluded = selected_cards + hero_cards
    keyboard = []

    for rank in RANKS:
        row = []
        for suit_code, suit_symbol in SUITS.items():
            card = f"{rank}{suit_code}"
            if card not in excluded:
                display = f"{rank}{suit_symbol}"
                row.append(
                    InlineKeyboardButton(
                        display,
                        callback_data=f"board:{card}"
                    )
                )
        if row:
            keyboard.append(row)

    # Кнопки управления
    control_row = []
    if len(selected_cards) >= min_cards:
        control_row.append(
            InlineKeyboardButton("✅ Готово", callback_data="board:done")
        )
    control_row.append(
        InlineKeyboardButton("❌ Отмена", callback_data="cancel")
    )
    keyboard.append(control_row)

    return InlineKeyboardMarkup(keyboard)


def get_position_keyboard() -> InlineKeyboardMarkup:
    """
    Создать клавиатуру для выбора позиции.

    Returns:
        InlineKeyboardMarkup с позициями
    """
    keyboard = []

    # Позиции в два ряда
    row1 = [
        InlineKeyboardButton(pos, callback_data=f"position:{pos}")
        for pos in POSITIONS_SHORT[:3]  # UTG, MP, CO
    ]
    row2 = [
        InlineKeyboardButton(pos, callback_data=f"position:{pos}")
        for pos in POSITIONS_SHORT[3:]  # BTN, SB, BB
    ]

    keyboard.append(row1)
    keyboard.append(row2)
    keyboard.append([
        InlineKeyboardButton("❌ Отмена", callback_data="cancel")
    ])

    return InlineKeyboardMarkup(keyboard)


def get_stage_keyboard() -> InlineKeyboardMarkup:
    """
    Создать клавиатуру для выбора стадии игры.

    Returns:
        InlineKeyboardMarkup со стадиями
    """
    keyboard = []

    row = [
        InlineKeyboardButton(
            name,
            callback_data=f"stage:{code}"
        )
        for code, name in STAGES.items()
    ]

    # Разбиваем на 2 ряда по 2 кнопки
    keyboard.append(row[:2])
    keyboard.append(row[2:])
    keyboard.append([
        InlineKeyboardButton("❌ Отмена", callback_data="cancel")
    ])

    return InlineKeyboardMarkup(keyboard)


def get_players_count_keyboard() -> InlineKeyboardMarkup:
    """
    Создать клавиатуру для выбора количества игроков.

    Returns:
        InlineKeyboardMarkup с количеством игроков
    """
    keyboard = []

    # Первый ряд: 2-5 игроков
    row1 = [
        InlineKeyboardButton(str(i), callback_data=f"players:{i}")
        for i in range(2, 6)
    ]
    # Второй ряд: 6-9 игроков
    row2 = [
        InlineKeyboardButton(str(i), callback_data=f"players:{i}")
        for i in range(6, 10)
    ]

    keyboard.append(row1)
    keyboard.append(row2)
    keyboard.append([
        InlineKeyboardButton("❌ Отмена", callback_data="cancel")
    ])

    return InlineKeyboardMarkup(keyboard)


def get_action_keyboard(
    position: str,
    player_num: int,
    allow_check: bool = False,
    current_bet: float = 0
) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру для выбора действия оппонента.

    Args:
        position: Позиция игрока
        player_num: Номер игрока
        allow_check: Разрешить чек (если нет ставки)
        current_bet: Текущая ставка

    Returns:
        InlineKeyboardMarkup с действиями
    """
    keyboard = []

    # Фолд всегда доступен
    row1 = [
        InlineKeyboardButton(
            "Фолд",
            callback_data=f"action:{player_num}:fold:0"
        )
    ]

    # Чек или колл
    if allow_check and current_bet == 0:
        row1.append(
            InlineKeyboardButton(
                "Чек",
                callback_data=f"action:{player_num}:check:0"
            )
        )
    else:
        row1.append(
            InlineKeyboardButton(
                f"Колл",
                callback_data=f"action:{player_num}:call:{current_bet}"
            )
        )

    keyboard.append(row1)

    # Рейзы
    row2 = [
        InlineKeyboardButton(
            "Рейз 2bb",
            callback_data=f"action:{player_num}:raise:2"
        ),
        InlineKeyboardButton(
            "Рейз 3bb",
            callback_data=f"action:{player_num}:raise:3"
        ),
        InlineKeyboardButton(
            "Рейз 4bb",
            callback_data=f"action:{player_num}:raise:4"
        )
    ]
    keyboard.append(row2)

    # Большие рейзы и олл-ин
    row3 = [
        InlineKeyboardButton(
            "Рейз 5bb",
            callback_data=f"action:{player_num}:raise:5"
        ),
        InlineKeyboardButton(
            "Олл-ин",
            callback_data=f"action:{player_num}:allin:0"
        )
    ]
    keyboard.append(row3)

    keyboard.append([
        InlineKeyboardButton("⏭ Пропустить", callback_data=f"action:{player_num}:skip:0"),
        InlineKeyboardButton("❌ Отмена", callback_data="cancel")
    ])

    return InlineKeyboardMarkup(keyboard)


def get_hero_action_keyboard(
    recommendation: str = "call"
) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру для выбора действия героя.

    Args:
        recommendation: Рекомендуемое действие (выделяется)

    Returns:
        InlineKeyboardMarkup с действиями героя
    """
    keyboard = []

    actions = [
        ("fold", "Фолд"),
        ("check", "Чек"),
        ("call", "Колл"),
        ("raise", "Рейз"),
        ("allin", "Олл-ин")
    ]

    row1 = []
    row2 = []

    for code, name in actions[:3]:
        # Выделяем рекомендуемое действие
        display = f"🎯 {name}" if code == recommendation else name
        row1.append(
            InlineKeyboardButton(display, callback_data=f"hero:{code}")
        )

    for code, name in actions[3:]:
        display = f"🎯 {name}" if code == recommendation else name
        row2.append(
            InlineKeyboardButton(display, callback_data=f"hero:{code}")
        )

    keyboard.append(row1)
    keyboard.append(row2)

    return InlineKeyboardMarkup(keyboard)


def get_pot_size_keyboard() -> InlineKeyboardMarkup:
    """
    Создать клавиатуру для выбора размера банка.

    Returns:
        InlineKeyboardMarkup с пресетами размера банка
    """
    keyboard = []

    # Пресеты размеров банка
    presets = [
        ("3bb", 3), ("4.5bb", 4.5), ("6bb", 6),
        ("7.5bb", 7.5), ("10bb", 10), ("15bb", 15),
        ("20bb", 20), ("30bb", 30), ("50bb", 50)
    ]

    for i in range(0, len(presets), 3):
        row = [
            InlineKeyboardButton(
                label,
                callback_data=f"pot:{value}"
            )
            for label, value in presets[i:i+3]
        ]
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton("📝 Ввести вручную", callback_data="pot:manual")
    ])
    keyboard.append([
        InlineKeyboardButton("❌ Отмена", callback_data="cancel")
    ])

    return InlineKeyboardMarkup(keyboard)


def get_result_keyboard() -> InlineKeyboardMarkup:
    """
    Создать клавиатуру для выбора результата раздачи.

    Returns:
        InlineKeyboardMarkup с вариантами результата
    """
    keyboard = [
        [
            InlineKeyboardButton(
                "🏆 Я выиграл",
                callback_data="result:win"
            ),
            InlineKeyboardButton(
                "😔 Я проиграл",
                callback_data="result:loss"
            )
        ],
        [
            InlineKeyboardButton(
                "🤝 Все скинули (забрал банк)",
                callback_data="result:fold_win"
            )
        ],
        [
            InlineKeyboardButton(
                "➡️ Я сфолдил",
                callback_data="result:folded"
            )
        ],
        [
            InlineKeyboardButton(
                "⏭ Пропустить",
                callback_data="result:skip"
            )
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


def get_winner_showed_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура: показал ли победитель карты?

    Returns:
        InlineKeyboardMarkup
    """
    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Да, показал",
                callback_data="showed:yes"
            ),
            InlineKeyboardButton(
                "❌ Нет",
                callback_data="showed:no"
            )
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Главное меню бота.

    Returns:
        InlineKeyboardMarkup
    """
    keyboard = [
        [
            InlineKeyboardButton(
                f"{EMOJI['cards']} Новая раздача",
                callback_data="menu:new_hand"
            )
        ],
        [
            InlineKeyboardButton(
                f"{EMOJI['stats']} Моя статистика",
                callback_data="menu:stats"
            ),
            InlineKeyboardButton(
                f"{EMOJI['tip']} Помощь",
                callback_data="menu:help"
            )
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


def get_after_hand_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура после завершения раздачи.

    Returns:
        InlineKeyboardMarkup
    """
    keyboard = [
        [
            InlineKeyboardButton(
                f"{EMOJI['cards']} Новая раздача",
                callback_data="menu:new_hand"
            )
        ],
        [
            InlineKeyboardButton(
                f"{EMOJI['stats']} Статистика",
                callback_data="menu:stats"
            ),
            InlineKeyboardButton(
                f"🏠 Главное меню",
                callback_data="menu:main"
            )
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


# ================== V2.0 KEYBOARDS ==================

def get_stack_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура для выбора эффективного стека.

    Returns:
        InlineKeyboardMarkup с пресетами стеков
    """
    keyboard = []

    # Пресеты стеков
    row1 = [
        InlineKeyboardButton(f"{s}bb", callback_data=f"stack:{s}")
        for s in [20, 50, 100]
    ]
    row2 = [
        InlineKeyboardButton(f"{s}bb", callback_data=f"stack:{s}")
        for s in [150, 200, 250]
    ]

    keyboard.append(row1)
    keyboard.append(row2)
    keyboard.append([
        InlineKeyboardButton("📝 Другой", callback_data="stack:custom")
    ])
    keyboard.append([
        InlineKeyboardButton("❌ Отмена", callback_data="cancel")
    ])

    return InlineKeyboardMarkup(keyboard)


def get_line_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура для выбора линии/ситуации.

    Returns:
        InlineKeyboardMarkup с линиями
    """
    keyboard = [
        # Основные линии
        [
            InlineKeyboardButton("🎯 RFI (открытие)", callback_data="line:rfi"),
        ],
        [
            InlineKeyboardButton("⚔️ vs Open", callback_data="line:vs_open"),
            InlineKeyboardButton("🔥 vs 3-bet", callback_data="line:vs_3bet"),
        ],
        [
            InlineKeyboardButton("💥 vs 4-bet", callback_data="line:vs_4bet"),
            InlineKeyboardButton("👥 Multiway", callback_data="line:multiway"),
        ],
        [
            InlineKeyboardButton("🎲 Limp pot", callback_data="line:limp"),
            InlineKeyboardButton("🆚 BB vs SB", callback_data="line:bb_vs_sb"),
        ],
        [
            InlineKeyboardButton("❌ Отмена", callback_data="cancel")
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


def get_opponent_type_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура для выбора типа оппонента.

    Returns:
        InlineKeyboardMarkup с типами оппов
    """
    keyboard = [
        [
            InlineKeyboardButton("❓ Unknown", callback_data="opponent:unknown"),
            InlineKeyboardButton("🐟 Fish", callback_data="opponent:fish"),
        ],
        [
            InlineKeyboardButton("🎮 Reg", callback_data="opponent:reg"),
            InlineKeyboardButton("🧊 Nit", callback_data="opponent:nit"),
        ],
        [
            InlineKeyboardButton("🔥 LAG", callback_data="opponent:lag"),
            InlineKeyboardButton("🎰 Maniac", callback_data="opponent:maniac"),
        ],
        [
            InlineKeyboardButton("❌ Отмена", callback_data="cancel")
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


def get_facing_bet_keyboard(line: str = "vs_open") -> InlineKeyboardMarkup:
    """
    Клавиатура для выбора размера ставки, которую фейсим.

    Args:
        line: Тип линии для подбора пресетов

    Returns:
        InlineKeyboardMarkup
    """
    # Разные пресеты для разных линий
    if line == "vs_open":
        presets = [2, 2.5, 3, 3.5, 4, 5]
    elif line == "vs_3bet":
        presets = [7, 8, 9, 10, 12, 15]
    elif line == "vs_4bet":
        presets = [18, 20, 22, 25, 30, "AI"]
    else:
        presets = [2, 3, 4, 5, 6, 8]

    keyboard = []

    # Первый ряд
    row1 = []
    for p in presets[:3]:
        label = f"{p}bb" if isinstance(p, (int, float)) else str(p)
        value = p if isinstance(p, (int, float)) else 0
        row1.append(InlineKeyboardButton(label, callback_data=f"facing:{value}"))
    keyboard.append(row1)

    # Второй ряд
    row2 = []
    for p in presets[3:]:
        label = f"{p}bb" if isinstance(p, (int, float)) else str(p)
        value = p if isinstance(p, (int, float)) else 0
        row2.append(InlineKeyboardButton(label, callback_data=f"facing:{value}"))
    keyboard.append(row2)

    keyboard.append([
        InlineKeyboardButton("📝 Другой", callback_data="facing:custom")
    ])
    keyboard.append([
        InlineKeyboardButton("❌ Отмена", callback_data="cancel")
    ])

    return InlineKeyboardMarkup(keyboard)


def get_recommendation_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура после показа рекомендации.

    Returns:
        InlineKeyboardMarkup
    """
    keyboard = [
        [
            InlineKeyboardButton("📝 Сохранить", callback_data="rec:save"),
            InlineKeyboardButton("🔄 Новая", callback_data="menu:new_hand"),
        ],
        [
            InlineKeyboardButton("📊 Postflop →", callback_data="rec:postflop"),
        ],
        [
            InlineKeyboardButton("🏠 Меню", callback_data="menu:main")
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


def get_aggressor_position_keyboard(hero_position: str) -> InlineKeyboardMarkup:
    """
    Клавиатура для выбора позиции агрессора.

    Args:
        hero_position: Позиция героя (исключаем её)

    Returns:
        InlineKeyboardMarkup
    """
    keyboard = []

    positions = [p for p in POSITIONS_SHORT if p != hero_position]

    # Группируем по 3
    for i in range(0, len(positions), 3):
        row = [
            InlineKeyboardButton(p, callback_data=f"aggressor:{p}")
            for p in positions[i:i+3]
        ]
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton("❌ Отмена", callback_data="cancel")
    ])

    return InlineKeyboardMarkup(keyboard)
