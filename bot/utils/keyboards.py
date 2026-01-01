"""Keyboard utilities for the Telegram bot."""

from typing import Optional, List
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from bot.config import ACTION_TYPES, get_price_per_unit, PRICE_TIERS


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Create main menu keyboard."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="🚀 Накрутка", callback_data="menu:boost"),
        InlineKeyboardButton(text="💰 Баланс", callback_data="menu:balance")
    )
    builder.row(
        InlineKeyboardButton(text="📋 Мои заказы", callback_data="menu:orders"),
        InlineKeyboardButton(text="💳 Пополнить", callback_data="menu:topup")
    )
    builder.row(
        InlineKeyboardButton(text="📊 Цены", callback_data="menu:prices"),
        InlineKeyboardButton(text="❓ Помощь", callback_data="menu:help")
    )
    
    return builder.as_markup()


def boost_menu_keyboard() -> InlineKeyboardMarkup:
    """Create boost type selection keyboard."""
    builder = InlineKeyboardBuilder()
    
    for action_type, label in ACTION_TYPES.items():
        builder.row(
            InlineKeyboardButton(
                text=label,
                callback_data=f"boost:{action_type}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")
    )
    
    return builder.as_markup()


def quantity_keyboard(action_type: str) -> InlineKeyboardMarkup:
    """Create quantity selection keyboard."""
    builder = InlineKeyboardBuilder()
    
    quantities = [10, 25, 50, 100, 200, 300, 500, 1000]
    
    # Add quantity buttons in rows of 4
    row = []
    for qty in quantities:
        price = get_price_per_unit(qty)
        row.append(
            InlineKeyboardButton(
                text=f"{qty} ({price}₽/шт)",
                callback_data=f"qty:{action_type}:{qty}"
            )
        )
        if len(row) == 2:
            builder.row(*row)
            row = []
    
    if row:
        builder.row(*row)
    
    # Custom quantity button
    builder.row(
        InlineKeyboardButton(
            text="✏️ Своё количество",
            callback_data=f"qty:{action_type}:custom"
        )
    )
    
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="menu:boost")
    )
    
    return builder.as_markup()


def confirm_order_keyboard(action_type: str, quantity: int, target_link: str) -> InlineKeyboardMarkup:
    """Create order confirmation keyboard."""
    builder = InlineKeyboardBuilder()
    
    # Encode data for callback
    builder.row(
        InlineKeyboardButton(
            text="✅ Подтвердить заказ",
            callback_data=f"confirm:{action_type}:{quantity}"
        )
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data=f"qty:{action_type}:select")
    )
    builder.row(
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")
    )
    
    return builder.as_markup()


def payment_method_keyboard(amount: float) -> InlineKeyboardMarkup:
    """Create payment method selection keyboard."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="💳 Банковская карта (Antilopay)",
            callback_data=f"pay:antilopay:{amount}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🪙 Криптовалюта (CryptoBot)",
            callback_data=f"pay:cryptobot:{amount}"
        )
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")
    )
    
    return builder.as_markup()


def crypto_currency_keyboard(amount: float) -> InlineKeyboardMarkup:
    """Create cryptocurrency selection keyboard."""
    builder = InlineKeyboardBuilder()
    
    currencies = [
        ("💵 USDT", "USDT"),
        ("💎 TON", "TON"),
        ("₿ BTC", "BTC"),
        ("Ξ ETH", "ETH"),
    ]
    
    for label, currency in currencies:
        builder.row(
            InlineKeyboardButton(
                text=label,
                callback_data=f"crypto:{currency}:{amount}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data=f"menu:topup")
    )
    
    return builder.as_markup()


def topup_amount_keyboard() -> InlineKeyboardMarkup:
    """Create top-up amount selection keyboard."""
    builder = InlineKeyboardBuilder()
    
    amounts = [100, 250, 500, 1000, 2500, 5000]
    
    row = []
    for amount in amounts:
        row.append(
            InlineKeyboardButton(
                text=f"{amount}₽",
                callback_data=f"topup:{amount}"
            )
        )
        if len(row) == 3:
            builder.row(*row)
            row = []
    
    if row:
        builder.row(*row)
    
    builder.row(
        InlineKeyboardButton(
            text="✏️ Своя сумма",
            callback_data="topup:custom"
        )
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")
    )
    
    return builder.as_markup()


def orders_keyboard(orders: list, page: int = 0, per_page: int = 5) -> InlineKeyboardMarkup:
    """Create orders list keyboard with pagination."""
    builder = InlineKeyboardBuilder()
    
    start = page * per_page
    end = start + per_page
    page_orders = orders[start:end]
    
    for order in page_orders:
        status_emoji = {
            "pending": "⏳",
            "processing": "🔄",
            "completed": "✅",
            "failed": "❌",
            "cancelled": "🚫"
        }.get(order.get("status", ""), "❓")
        
        order_id = order.get("order_id", "???")[:8]
        action = order.get("action_type", "???")
        
        builder.row(
            InlineKeyboardButton(
                text=f"{status_emoji} {order_id} | {action}",
                callback_data=f"order:{order.get('order_id', '')}"
            )
        )
    
    # Pagination
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="◀️ Пред.", callback_data=f"orders:page:{page-1}")
        )
    if end < len(orders):
        nav_buttons.append(
            InlineKeyboardButton(text="След. ▶️", callback_data=f"orders:page:{page+1}")
        )
    
    if nav_buttons:
        builder.row(*nav_buttons)
    
    builder.row(
        InlineKeyboardButton(text="🔄 Обновить", callback_data="menu:orders"),
        InlineKeyboardButton(text="🏠 Меню", callback_data="menu:main")
    )
    
    return builder.as_markup()


def back_to_main_keyboard() -> InlineKeyboardMarkup:
    """Create simple back to main menu keyboard."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")
    )
    return builder.as_markup()


def payment_status_keyboard(payment_id: str) -> InlineKeyboardMarkup:
    """Create payment status check keyboard."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🔄 Проверить оплату",
            callback_data=f"check_payment:{payment_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")
    )
    return builder.as_markup()


def admin_keyboard() -> InlineKeyboardMarkup:
    """Create admin panel keyboard."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="👥 Пользователи", callback_data="admin:users"),
        InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")
    )
    builder.row(
        InlineKeyboardButton(text="💰 Балансы систем", callback_data="admin:balances"),
        InlineKeyboardButton(text="📨 Рассылка", callback_data="admin:broadcast")
    )
    builder.row(
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")
    )
    
    return builder.as_markup()


def prices_keyboard() -> InlineKeyboardMarkup:
    """Create prices info keyboard."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🚀 Начать накрутку", callback_data="menu:boost")
    )
    builder.row(
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")
    )
    return builder.as_markup()


def cancel_keyboard() -> ReplyKeyboardMarkup:
    """Create cancel keyboard for FSM states."""
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="❌ Отмена"))
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def remove_keyboard() -> ReplyKeyboardMarkup:
    """Create empty keyboard to remove custom keyboard."""
    from aiogram.types import ReplyKeyboardRemove
    return ReplyKeyboardRemove()
