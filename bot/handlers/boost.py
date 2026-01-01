"""Boost/SMM order handlers."""

import re
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select

from bot.models.database import User, Order, async_session_maker
from bot.services.steamsmm import SteamSmmClient, ActionType, get_action_name, get_action_emoji
from bot.utils.keyboards import (
    boost_menu_keyboard,
    quantity_keyboard,
    confirm_order_keyboard,
    back_to_main_keyboard,
    cancel_keyboard
)
from bot.config import ACTION_TYPES, get_price_per_unit
from bot.handlers.start import get_or_create_user

router = Router()


class OrderStates(StatesGroup):
    """States for order creation flow."""
    waiting_custom_quantity = State()
    waiting_target_link = State()
    confirming_order = State()


# Steam URL patterns
STEAM_PROFILE_PATTERN = re.compile(
    r'https?://steamcommunity\.com/(id/[a-zA-Z0-9_-]+|profiles/\d+)/?'
)
STEAM_WORKSHOP_PATTERN = re.compile(
    r'https?://steamcommunity\.com/sharedfiles/filedetails/\?id=\d+'
)
STEAM_GROUP_PATTERN = re.compile(
    r'https?://steamcommunity\.com/groups/[a-zA-Z0-9_-]+/?'
)
STEAM_REVIEW_PATTERN = re.compile(
    r'https?://steamcommunity\.com/(id/[a-zA-Z0-9_-]+|profiles/\d+)/recommended/\d+/?'
)


def validate_steam_link(action_type: str, link: str) -> tuple[bool, str]:
    """Validate Steam link based on action type.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    link = link.strip()
    
    if action_type == "comment":
        if STEAM_PROFILE_PATTERN.match(link):
            return True, ""
        return False, (
            "Для комментариев нужна ссылка на профиль Steam:\n"
            "• https://steamcommunity.com/id/username\n"
            "• https://steamcommunity.com/profiles/76561198xxxxxxxxx"
        )
    
    elif action_type == "like":
        if STEAM_WORKSHOP_PATTERN.match(link):
            return True, ""
        return False, (
            "Для лайков нужна ссылка на скриншот/иллюстрацию:\n"
            "• https://steamcommunity.com/sharedfiles/filedetails/?id=1234567890"
        )
    
    elif action_type == "subscribe":
        if STEAM_GROUP_PATTERN.match(link):
            return True, ""
        return False, (
            "Для подписок нужна ссылка на группу Steam:\n"
            "• https://steamcommunity.com/groups/groupname"
        )
    
    elif action_type == "review":
        if STEAM_REVIEW_PATTERN.match(link) or STEAM_PROFILE_PATTERN.match(link):
            return True, ""
        return False, (
            "Для обзоров нужна ссылка на профиль или обзор:\n"
            "• https://steamcommunity.com/id/username/recommended/123456"
        )
    
    return False, "Неизвестный тип действия"


@router.callback_query(F.data == "menu:boost")
async def callback_boost_menu(callback: CallbackQuery, state: FSMContext):
    """Show boost type selection menu."""
    await state.clear()
    
    text = """
🚀 <b>Накрутка Steam</b>

Выберите тип накрутки:
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=boost_menu_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("boost:"))
async def callback_select_boost_type(callback: CallbackQuery, state: FSMContext):
    """Handle boost type selection."""
    action_type = callback.data.split(":")[1]
    
    if action_type not in ACTION_TYPES:
        await callback.answer("Неизвестный тип накрутки", show_alert=True)
        return
    
    await state.update_data(action_type=action_type)
    
    action_name = ACTION_TYPES[action_type]
    
    text = f"""
{action_name}

<b>Выберите количество:</b>

Цены (динамическое ценообразование):
• 1-99 шт: <b>1.00 ₽/шт</b>
• 100-199 шт: <b>0.85 ₽/шт</b> (-15%)
• 200-299 шт: <b>0.75 ₽/шт</b> (-25%)
• 300-499 шт: <b>0.65 ₽/шт</b> (-35%)
• 500-999 шт: <b>0.60 ₽/шт</b> (-40%)
• 1000+ шт: <b>0.55 ₽/шт</b> (-45%)
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=quantity_keyboard(action_type),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("qty:"))
async def callback_select_quantity(callback: CallbackQuery, state: FSMContext):
    """Handle quantity selection."""
    parts = callback.data.split(":")
    action_type = parts[1]
    quantity_str = parts[2]
    
    if quantity_str == "select":
        # Go back to quantity selection
        await callback_select_boost_type(callback, state)
        return
    
    if quantity_str == "custom":
        await state.update_data(action_type=action_type)
        await callback.message.edit_text(
            "✏️ <b>Введите количество</b>\n\n"
            "Минимум: 10\n"
            "Максимум: 1000\n\n"
            "Отправьте число:",
            parse_mode="HTML"
        )
        await state.set_state(OrderStates.waiting_custom_quantity)
        await callback.answer()
        return
    
    quantity = int(quantity_str)
    await state.update_data(action_type=action_type, quantity=quantity)
    
    # Ask for target link
    await ask_for_target_link(callback.message, action_type, quantity, state, edit=True)
    await callback.answer()


@router.message(OrderStates.waiting_custom_quantity)
async def process_custom_quantity(message: Message, state: FSMContext):
    """Process custom quantity input."""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(
            "Отменено",
            reply_markup=back_to_main_keyboard()
        )
        return
    
    try:
        quantity = int(message.text.strip())
        
        if quantity < 10:
            await message.answer("❌ Минимальное количество: 10")
            return
        
        if quantity > 1000:
            await message.answer("❌ Максимальное количество: 1000")
            return
        
        data = await state.get_data()
        action_type = data.get("action_type")
        
        await state.update_data(quantity=quantity)
        await ask_for_target_link(message, action_type, quantity, state, edit=False)
        
    except ValueError:
        await message.answer("❌ Введите число от 10 до 1000")


async def ask_for_target_link(message_or_callback, action_type: str, quantity: int, state: FSMContext, edit: bool = False):
    """Ask user for target Steam link."""
    action_name = get_action_name(action_type)
    action_emoji = get_action_emoji(action_type)
    
    # Use standard dynamic pricing
    price_per_unit = get_price_per_unit(quantity)
    total_cost = quantity * price_per_unit
    
    # Save price to state
    await state.update_data(price_per_unit=price_per_unit, total_cost=total_cost)
    
    link_examples = {
        "comment": "https://steamcommunity.com/id/username",
        "like": "https://steamcommunity.com/sharedfiles/filedetails/?id=123456",
        "subscribe": "https://steamcommunity.com/groups/groupname",
        "review": "https://steamcommunity.com/id/username/recommended/123456"
    }
    
    text = f"""
{action_emoji} <b>{action_name}</b>

📊 Количество: <b>{quantity}</b>
💰 Цена за шт: <b>{price_per_unit:.2f} ₽</b>
💵 Итого: <b>{total_cost:.2f} ₽</b>

📎 <b>Отправьте ссылку на Steam:</b>
Пример: <code>{link_examples.get(action_type, "")}</code>
"""
    
    await state.set_state(OrderStates.waiting_target_link)
    
    if edit and hasattr(message_or_callback, 'edit_text'):
        await message_or_callback.edit_text(
            text,
            parse_mode="HTML"
        )
    else:
        await message_or_callback.answer(
            text,
            parse_mode="HTML"
        )


@router.message(OrderStates.waiting_target_link)
async def process_target_link(message: Message, state: FSMContext):
    """Process target Steam link."""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(
            "Отменено",
            reply_markup=back_to_main_keyboard()
        )
        return
    
    data = await state.get_data()
    action_type = data.get("action_type")
    quantity = data.get("quantity")
    
    target_link = message.text.strip()
    
    # Validate the link
    is_valid, error_msg = validate_steam_link(action_type, target_link)
    
    if not is_valid:
        await message.answer(f"❌ {error_msg}")
        return
    
    await state.update_data(target_link=target_link)
    
    # Show confirmation - use price from state
    action_name = get_action_name(action_type)
    action_emoji = get_action_emoji(action_type)
    
    # Get saved price from state
    price_per_unit = data.get("price_per_unit", get_price_per_unit(quantity))
    total_cost = data.get("total_cost", quantity * price_per_unit)
    
    # Get user balance
    user = await get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )
    
    balance_warning = ""
    if user.balance < total_cost:
        balance_warning = f"\n⚠️ <b>Недостаточно средств!</b>\nНужно: {total_cost:.2f} ₽\nВаш баланс: {user.balance:.2f} ₽"
    
    text = f"""
{action_emoji} <b>Подтверждение заказа</b>

📌 Тип: <b>{action_name}</b>
📊 Количество: <b>{quantity}</b>
💰 Цена за шт: <b>{price_per_unit:.2f} ₽</b>
💵 Итого: <b>{total_cost:.2f} ₽</b>

🔗 Ссылка:
<code>{target_link}</code>

💰 Ваш баланс: <b>{user.balance:.2f} ₽</b>
{balance_warning}
"""
    
    await state.set_state(OrderStates.confirming_order)
    
    await message.answer(
        text,
        reply_markup=confirm_order_keyboard(action_type, quantity, target_link),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("confirm:"))
async def callback_confirm_order(callback: CallbackQuery, state: FSMContext):
    """Confirm and create the order."""
    parts = callback.data.split(":")
    action_type = parts[1]
    quantity = int(parts[2])
    
    data = await state.get_data()
    target_link = data.get("target_link")
    
    if not target_link:
        await callback.answer("Ошибка: ссылка не найдена", show_alert=True)
        await state.clear()
        return
    
    # Get user and check balance
    async with async_session_maker() as session:
        user_result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            await callback.answer("Ошибка: пользователь не найден", show_alert=True)
            await state.clear()
            return
        
        price_per_unit = get_price_per_unit(quantity)
        total_cost = quantity * price_per_unit
        
        if user.balance < total_cost:
            await callback.answer(
                f"Недостаточно средств! Нужно: {total_cost:.2f} ₽",
                show_alert=True
            )
            return
        
        # Create order via SteamSmm API
        client = SteamSmmClient()
        
        await callback.message.edit_text(
            "⏳ Создаём заказ...",
            parse_mode="HTML"
        )
        
        result = await client.create_order(
            action_type=ActionType(action_type),
            quantity=quantity,
            target_link=target_link
        )
        
        if result.success:
            # Deduct balance and save order
            user.balance -= total_cost
            
            order = Order(
                user_id=user.id,
                order_id=result.order_id,
                action_type=action_type,
                quantity=quantity,
                target_link=target_link,
                cost=result.cost or total_cost,
                price_per_unit=result.price_per_unit or price_per_unit,
                price_type=result.price_type or "dynamic",
                status=result.status or "pending"
            )
            session.add(order)
            await session.commit()
            
            action_name = get_action_name(action_type)
            action_emoji = get_action_emoji(action_type)
            
            # Notify admins about new order
            from bot.handlers.admin import notify_admins_new_order
            await notify_admins_new_order(
                callback.bot,
                {
                    "user_id": callback.from_user.id,
                    "action_type": action_name,
                    "quantity": quantity,
                    "cost": result.cost or total_cost,
                    "target_link": target_link
                }
            )
            
            text = f"""
✅ <b>Заказ успешно создан!</b>

{action_emoji} Тип: <b>{action_name}</b>
📊 Количество: <b>{quantity}</b>
💵 Стоимость: <b>{result.cost or total_cost:.2f} ₽</b>

🔖 ID заказа: <code>{result.order_id}</code>

📌 Статус: <b>В обработке</b>

Отслеживать статус можно в разделе "📋 Мои заказы"
"""
            
            await callback.message.edit_text(
                text,
                reply_markup=back_to_main_keyboard(),
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                f"❌ <b>Ошибка создания заказа</b>\n\n{result.error}",
                reply_markup=back_to_main_keyboard(),
                parse_mode="HTML"
            )
    
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "menu:prices")
async def callback_prices(callback: CallbackQuery):
    """Show pricing information."""
    text = """
💰 <b>Цены на услуги</b>

<b>Динамическое ценообразование</b>
Чем больше заказ — тем дешевле!

📊 <b>Тарифы:</b>
• 1-99 шт: <b>1.00 ₽/шт</b>
• 100-199 шт: <b>0.85 ₽/шт</b> (скидка 15%)
• 200-299 шт: <b>0.75 ₽/шт</b> (скидка 25%)
• 300-499 шт: <b>0.65 ₽/шт</b> (скидка 35%)
• 500-999 шт: <b>0.60 ₽/шт</b> (скидка 40%)
• 1000+ шт: <b>0.55 ₽/шт</b> (скидка 45%)

<b>Доступные услуги:</b>
💬 Комментарии на профиле
👍 Лайки на скриншоты и иллюстрации
👥 Подписки на группы
⭐ Обзоры на игры

<b>Примеры расчёта:</b>
• 100 комментариев = 85 ₽
• 500 лайков = 300 ₽
• 1000 подписок = 550 ₽
"""
    
    from bot.utils.keyboards import prices_keyboard
    
    await callback.message.edit_text(
        text,
        reply_markup=prices_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()
