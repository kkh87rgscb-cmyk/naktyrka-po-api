"""Admin panel handlers."""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, func

from bot.models.database import User, Order, Payment, async_session_maker
from bot.services.antilopay import AntilopayClient
from bot.services.cryptobot import CryptoBotClient
from bot.utils.keyboards import admin_keyboard, back_to_main_keyboard
from bot.config import settings

router = Router()


class AdminStates(StatesGroup):
    """States for admin operations."""
    waiting_broadcast_message = State()
    waiting_user_id_for_balance = State()
    waiting_balance_amount = State()


def is_admin(user_id: int) -> bool:
    """Check if user is admin."""
    return user_id in settings.admin_ids_list


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Handle /admin command."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к админ-панели")
        return
    
    text = """
🔐 <b>Админ-панель</b>

Выберите действие:
"""
    
    await message.answer(
        text,
        reply_markup=admin_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin:stats")
async def callback_admin_stats(callback: CallbackQuery):
    """Show admin statistics."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    async with async_session_maker() as session:
        # Count users
        users_count = await session.execute(
            select(func.count(User.id))
        )
        total_users = users_count.scalar() or 0
        
        # Count orders
        orders_count = await session.execute(
            select(func.count(Order.id))
        )
        total_orders = orders_count.scalar() or 0
        
        # Count completed orders
        completed_count = await session.execute(
            select(func.count(Order.id)).where(Order.status == "completed")
        )
        completed_orders = completed_count.scalar() or 0
        
        # Sum of all order costs
        orders_sum = await session.execute(
            select(func.sum(Order.cost))
        )
        total_revenue = orders_sum.scalar() or 0
        
        # Sum of successful payments
        payments_sum = await session.execute(
            select(func.sum(Payment.amount)).where(Payment.status == "success")
        )
        total_payments = payments_sum.scalar() or 0
        
        # Count payments
        payments_count = await session.execute(
            select(func.count(Payment.id)).where(Payment.status == "success")
        )
        successful_payments = payments_count.scalar() or 0
        
        # Total user balances
        balances_sum = await session.execute(
            select(func.sum(User.balance))
        )
        total_balances = balances_sum.scalar() or 0
    
    text = f"""
📊 <b>Статистика</b>

👥 <b>Пользователи:</b>
• Всего: <b>{total_users}</b>

📋 <b>Заказы:</b>
• Всего: <b>{total_orders}</b>
• Выполнено: <b>{completed_orders}</b>
• Сумма: <b>{total_revenue:.2f} ₽</b>

💳 <b>Платежи:</b>
• Успешных: <b>{successful_payments}</b>
• Сумма: <b>{total_payments:.2f} ₽</b>

💰 <b>Балансы пользователей:</b>
• Общая сумма: <b>{total_balances:.2f} ₽</b>
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=admin_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin:users")
async def callback_admin_users(callback: CallbackQuery):
    """Show recent users."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    async with async_session_maker() as session:
        # Get recent users
        users_result = await session.execute(
            select(User).order_by(User.created_at.desc()).limit(10)
        )
        users = users_result.scalars().all()
        
        # Total count
        count_result = await session.execute(
            select(func.count(User.id))
        )
        total_count = count_result.scalar() or 0
    
    text = f"""
👥 <b>Пользователи</b> ({total_count} всего)

<b>Последние 10 пользователей:</b>

"""
    
    for user in users:
        username = f"@{user.username}" if user.username else "без username"
        name = user.first_name or "Без имени"
        text += f"• <code>{user.telegram_id}</code> | {name} | {username} | {user.balance:.2f}₽\n"
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Изменить баланс", callback_data="admin:change_balance")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back")]
    ])
    
    await callback.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin:change_balance")
async def callback_change_balance(callback: CallbackQuery, state: FSMContext):
    """Start balance change flow."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "💰 <b>Изменение баланса</b>\n\n"
        "Отправьте Telegram ID пользователя:",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_user_id_for_balance)
    await callback.answer()


@router.message(AdminStates.waiting_user_id_for_balance)
async def process_user_id_for_balance(message: Message, state: FSMContext):
    """Process user ID for balance change."""
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    
    try:
        user_id = int(message.text.strip())
        
        async with async_session_maker() as session:
            user_result = await session.execute(
                select(User).where(User.telegram_id == user_id)
            )
            user = user_result.scalar_one_or_none()
            
            if not user:
                await message.answer("❌ Пользователь не найден")
                return
            
            await state.update_data(target_user_id=user_id)
            
            await message.answer(
                f"👤 Пользователь: {user.first_name or 'Без имени'}\n"
                f"💰 Текущий баланс: {user.balance:.2f} ₽\n\n"
                "Введите новый баланс (или +/-сумма для изменения):",
                parse_mode="HTML"
            )
            await state.set_state(AdminStates.waiting_balance_amount)
            
    except ValueError:
        await message.answer("❌ Введите корректный Telegram ID (число)")


@router.message(AdminStates.waiting_balance_amount)
async def process_balance_amount(message: Message, state: FSMContext):
    """Process new balance amount."""
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    
    data = await state.get_data()
    target_user_id = data.get("target_user_id")
    
    try:
        amount_str = message.text.strip()
        
        async with async_session_maker() as session:
            user_result = await session.execute(
                select(User).where(User.telegram_id == target_user_id)
            )
            user = user_result.scalar_one_or_none()
            
            if not user:
                await message.answer("❌ Пользователь не найден")
                await state.clear()
                return
            
            old_balance = user.balance
            
            if amount_str.startswith("+") or amount_str.startswith("-"):
                # Relative change
                delta = float(amount_str.replace(",", "."))
                user.balance += delta
            else:
                # Absolute value
                user.balance = float(amount_str.replace(",", "."))
            
            await session.commit()
            
            await message.answer(
                f"✅ Баланс изменён!\n\n"
                f"Было: {old_balance:.2f} ₽\n"
                f"Стало: {user.balance:.2f} ₽",
                reply_markup=admin_keyboard()
            )
            
    except ValueError:
        await message.answer("❌ Введите корректную сумму")
        return
    
    await state.clear()


@router.callback_query(F.data == "admin:balances")
async def callback_admin_balances(callback: CallbackQuery):
    """Show payment system balances."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "⏳ Загрузка балансов...",
        parse_mode="HTML"
    )
    
    text = "💰 <b>Балансы платёжных систем</b>\n\n"
    
    # Antilopay balance
    try:
        antilopay = AntilopayClient()
        balance = await antilopay.get_project_balance()
        
        if balance.get("code") == 0:
            rub_balance = balance.get("rub", {})
            available = rub_balance.get("available", 0)
            blocked = rub_balance.get("blocked", 0)
            withdraw = rub_balance.get("withdraw", 0)
            
            text += f"<b>💳 Antilopay:</b>\n"
            text += f"• Доступно: {available:.2f} ₽\n"
            text += f"• Заблокировано: {blocked:.2f} ₽\n"
            text += f"• На вывод: {withdraw:.2f} ₽\n\n"
        else:
            text += f"<b>💳 Antilopay:</b> ❌ {balance.get('error', 'Ошибка')}\n\n"
    except Exception as e:
        text += f"<b>💳 Antilopay:</b> ❌ {str(e)}\n\n"
    
    # CryptoBot balance
    try:
        cryptobot = CryptoBotClient()
        balances = await cryptobot.get_balance()
        
        if balances:
            text += "<b>🪙 CryptoBot:</b>\n"
            for bal in balances:
                currency = bal.get("currency_code", "???")
                available = bal.get("available", "0")
                text += f"• {currency}: {available}\n"
        else:
            text += "<b>🪙 CryptoBot:</b> Нет данных\n"
    except Exception as e:
        text += f"<b>🪙 CryptoBot:</b> ❌ {str(e)}\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=admin_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin:broadcast")
async def callback_admin_broadcast(callback: CallbackQuery, state: FSMContext):
    """Start broadcast message flow."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📨 <b>Рассылка</b>\n\n"
        "Отправьте сообщение для рассылки всем пользователям.\n\n"
        "Поддерживается форматирование HTML.",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_broadcast_message)
    await callback.answer()


@router.message(AdminStates.waiting_broadcast_message)
async def process_broadcast_message(message: Message, state: FSMContext):
    """Process and send broadcast message."""
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(
            "Рассылка отменена",
            reply_markup=admin_keyboard()
        )
        return
    
    broadcast_text = message.text or message.caption or ""
    
    if not broadcast_text:
        await message.answer("❌ Сообщение пустое")
        return
    
    await state.clear()
    
    # Get all users
    async with async_session_maker() as session:
        users_result = await session.execute(
            select(User.telegram_id)
        )
        user_ids = [row[0] for row in users_result.fetchall()]
    
    if not user_ids:
        await message.answer("❌ Нет пользователей для рассылки")
        return
    
    await message.answer(f"📨 Начинаю рассылку для {len(user_ids)} пользователей...")
    
    success_count = 0
    fail_count = 0
    
    from aiogram import Bot
    bot = message.bot
    
    for user_id in user_ids:
        try:
            await bot.send_message(
                chat_id=user_id,
                text=broadcast_text,
                parse_mode="HTML"
            )
            success_count += 1
        except Exception:
            fail_count += 1
        
        # Small delay to avoid flood limits
        import asyncio
        await asyncio.sleep(0.05)
    
    await message.answer(
        f"✅ Рассылка завершена!\n\n"
        f"Успешно: {success_count}\n"
        f"Ошибок: {fail_count}",
        reply_markup=admin_keyboard()
    )


@router.callback_query(F.data == "admin:back")
async def callback_admin_back(callback: CallbackQuery):
    """Go back to admin menu."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    text = """
🔐 <b>Админ-панель</b>

Выберите действие:
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=admin_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()
