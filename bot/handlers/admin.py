"""Admin panel handlers."""

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, func, or_

from bot.models.database import User, Order, Payment, async_session_maker
from bot.services.antilopay import AntilopayClient
from bot.services.cryptobot import CryptoBotClient
from bot.utils.keyboards import admin_keyboard, back_to_main_keyboard
from bot.config import settings

router = Router()


class AdminStates(StatesGroup):
    """States for admin operations."""
    waiting_search_query = State()
    waiting_balance_amount = State()
    waiting_broadcast_message = State()


def is_admin(user_id: int) -> bool:
    """Check if user is admin."""
    return user_id in settings.admin_ids_list


async def notify_admins_new_order(bot: Bot, order_data: dict):
    """Send notification to all admins about new order.
    
    Args:
        bot: Telegram bot instance.
        order_data: Order information.
    """
    text = f"""
🆕 <b>Новый заказ!</b>

👤 Пользователь: <code>{order_data.get('user_id')}</code>
📌 Тип: <b>{order_data.get('action_type')}</b>
📊 Количество: <b>{order_data.get('quantity')}</b>
💵 Сумма: <b>{order_data.get('cost'):.2f} ₽</b>
🔗 Ссылка: <code>{order_data.get('target_link', '')[:50]}...</code>
"""
    
    for admin_id in settings.admin_ids_list:
        try:
            await bot.send_message(admin_id, text, parse_mode="HTML")
        except Exception:
            pass


async def notify_admins_new_payment(bot: Bot, payment_data: dict):
    """Send notification to all admins about new payment.
    
    Args:
        bot: Telegram bot instance.
        payment_data: Payment information.
    """
    text = f"""
💰 <b>Новый платёж!</b>

👤 Пользователь: <code>{payment_data.get('user_id')}</code>
💳 Система: <b>{payment_data.get('payment_system')}</b>
💵 Сумма: <b>{payment_data.get('amount'):.2f} ₽</b>
📊 Статус: <b>{payment_data.get('status')}</b>
"""
    
    for admin_id in settings.admin_ids_list:
        try:
            await bot.send_message(admin_id, text, parse_mode="HTML")
        except Exception:
            pass


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Handle /admin command."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к админ-панели")
        return
    
    await show_admin_panel(message)


async def show_admin_panel(message_or_callback, edit: bool = False):
    """Show admin panel."""
    text = """
🔐 <b>Админ-панель</b>

Выберите действие:
"""
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔍 Поиск пользователя", callback_data="admin:search"),
        ],
        [
            InlineKeyboardButton(text="👥 Все пользователи", callback_data="admin:users"),
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats"),
        ],
        [
            InlineKeyboardButton(text="📋 Последние заказы", callback_data="admin:orders"),
        ],
        [
            InlineKeyboardButton(text="📨 Рассылка", callback_data="admin:broadcast"),
        ],
        [
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main"),
        ]
    ])
    
    if edit and hasattr(message_or_callback, 'message'):
        await message_or_callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await message_or_callback.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "admin:back")
async def callback_admin_back(callback: CallbackQuery, state: FSMContext):
    """Go back to admin panel."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    await state.clear()
    await show_admin_panel(callback, edit=True)
    await callback.answer()


@router.callback_query(F.data == "admin:search")
async def callback_admin_search(callback: CallbackQuery, state: FSMContext):
    """Start user search."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🔍 <b>Поиск пользователя</b>\n\n"
        "Введите <b>Telegram ID</b> или <b>@username</b>:",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_search_query)
    await callback.answer()


@router.message(AdminStates.waiting_search_query)
async def process_search_query(message: Message, state: FSMContext):
    """Process user search query."""
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    
    query = message.text.strip()
    
    async with async_session_maker() as session:
        # Search by telegram_id or username
        if query.startswith("@"):
            username = query[1:]  # Remove @
            result = await session.execute(
                select(User).where(User.username.ilike(f"%{username}%"))
            )
        elif query.isdigit():
            result = await session.execute(
                select(User).where(User.telegram_id == int(query))
            )
        else:
            # Search by username without @
            result = await session.execute(
                select(User).where(
                    or_(
                        User.username.ilike(f"%{query}%"),
                        User.first_name.ilike(f"%{query}%")
                    )
                )
            )
        
        users = result.scalars().all()
    
    await state.clear()
    
    if not users:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Искать снова", callback_data="admin:search")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back")]
        ])
        await message.answer(
            f"❌ Пользователь не найден: <code>{query}</code>",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        return
    
    if len(users) == 1:
        # Show single user
        await show_user_details(message, users[0])
    else:
        # Show list of found users
        text = f"🔍 <b>Найдено пользователей: {len(users)}</b>\n\n"
        
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        buttons = []
        
        for user in users[:10]:  # Max 10 results
            username = f"@{user.username}" if user.username else "—"
            name = user.first_name or "Без имени"
            buttons.append([
                InlineKeyboardButton(
                    text=f"{name} | {username} | {user.balance:.2f}₽",
                    callback_data=f"admin:user:{user.telegram_id}"
                )
            ])
        
        buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


async def show_user_details(message_or_callback, user: User, edit: bool = False):
    """Show user details with balance edit option."""
    username = f"@{user.username}" if user.username else "—"
    name = user.first_name or "Без имени"
    
    # Count orders
    async with async_session_maker() as session:
        orders_count = await session.execute(
            select(func.count(Order.id)).where(Order.user_id == user.id)
        )
        total_orders = orders_count.scalar() or 0
        
        orders_sum = await session.execute(
            select(func.sum(Order.cost)).where(Order.user_id == user.id)
        )
        total_spent = orders_sum.scalar() or 0
    
    text = f"""
👤 <b>Пользователь</b>

🆔 Telegram ID: <code>{user.telegram_id}</code>
👤 Имя: <b>{name}</b>
📧 Username: {username}

💰 Баланс: <b>{user.balance:.2f} ₽</b>
📋 Заказов: <b>{total_orders}</b>
💵 Потрачено: <b>{total_spent:.2f} ₽</b>

📅 Регистрация: {user.created_at.strftime("%d.%m.%Y %H:%M") if user.created_at else "—"}
"""
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="💰 Изменить баланс",
                callback_data=f"admin:balance:{user.telegram_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="📋 Заказы пользователя",
                callback_data=f"admin:user_orders:{user.telegram_id}"
            )
        ],
        [
            InlineKeyboardButton(text="🔍 Искать другого", callback_data="admin:search"),
            InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back")
        ]
    ])
    
    if edit and hasattr(message_or_callback, 'edit_text'):
        await message_or_callback.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    elif hasattr(message_or_callback, 'message'):
        await message_or_callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await message_or_callback.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("admin:user:"))
async def callback_show_user(callback: CallbackQuery):
    """Show user details by telegram_id."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    telegram_id = int(callback.data.split(":")[2])
    
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
    
    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return
    
    await show_user_details(callback, user)
    await callback.answer()


@router.callback_query(F.data.startswith("admin:balance:"))
async def callback_change_balance(callback: CallbackQuery, state: FSMContext):
    """Start balance change flow."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    telegram_id = int(callback.data.split(":")[2])
    await state.update_data(target_user_id=telegram_id)
    
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
    
    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return
    
    await callback.message.edit_text(
        f"💰 <b>Изменение баланса</b>\n\n"
        f"Пользователь: <code>{telegram_id}</code>\n"
        f"Текущий баланс: <b>{user.balance:.2f} ₽</b>\n\n"
        f"Введите новый баланс или изменение:\n"
        f"• <code>100</code> — установить 100₽\n"
        f"• <code>+50</code> — добавить 50₽\n"
        f"• <code>-30</code> — вычесть 30₽",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_balance_amount)
    await callback.answer()


@router.message(AdminStates.waiting_balance_amount)
async def process_balance_amount(message: Message, state: FSMContext):
    """Process new balance amount."""
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    
    data = await state.get_data()
    target_user_id = data.get("target_user_id")
    
    try:
        amount_str = message.text.strip().replace(",", ".")
        
        async with async_session_maker() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == target_user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                await message.answer("❌ Пользователь не найден")
                await state.clear()
                return
            
            old_balance = user.balance
            
            if amount_str.startswith("+"):
                delta = float(amount_str[1:])
                user.balance += delta
                action = f"добавлено {delta:.2f}₽"
            elif amount_str.startswith("-"):
                delta = float(amount_str[1:])
                user.balance -= delta
                action = f"вычтено {delta:.2f}₽"
            else:
                user.balance = float(amount_str)
                action = f"установлено {user.balance:.2f}₽"
            
            await session.commit()
            
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👤 К пользователю", callback_data=f"admin:user:{target_user_id}")],
                [InlineKeyboardButton(text="◀️ Админ-панель", callback_data="admin:back")]
            ])
            
            await message.answer(
                f"✅ <b>Баланс изменён!</b>\n\n"
                f"Пользователь: <code>{target_user_id}</code>\n"
                f"Было: <b>{old_balance:.2f} ₽</b>\n"
                f"Стало: <b>{user.balance:.2f} ₽</b>\n"
                f"Действие: {action}",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            
    except ValueError:
        await message.answer("❌ Введите корректную сумму")
        return
    
    await state.clear()


@router.callback_query(F.data.startswith("admin:user_orders:"))
async def callback_user_orders(callback: CallbackQuery):
    """Show user's orders."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    telegram_id = int(callback.data.split(":")[2])
    
    async with async_session_maker() as session:
        # Get user
        user_result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            await callback.answer("Пользователь не найден", show_alert=True)
            return
        
        # Get orders
        orders_result = await session.execute(
            select(Order)
            .where(Order.user_id == user.id)
            .order_by(Order.created_at.desc())
            .limit(10)
        )
        orders = orders_result.scalars().all()
    
    if not orders:
        text = f"📋 <b>Заказы пользователя</b>\n\nУ пользователя нет заказов."
    else:
        text = f"📋 <b>Заказы пользователя</b> (последние 10)\n\n"
        for order in orders:
            status_emoji = {"pending": "⏳", "processing": "🔄", "completed": "✅", "failed": "❌"}.get(order.status, "❓")
            text += f"{status_emoji} {order.action_type} × {order.quantity} = {order.cost:.2f}₽\n"
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 К пользователю", callback_data=f"admin:user:{telegram_id}")],
        [InlineKeyboardButton(text="◀️ Админ-панель", callback_data="admin:back")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin:stats")
async def callback_admin_stats(callback: CallbackQuery):
    """Show admin statistics."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    async with async_session_maker() as session:
        users_count = await session.execute(select(func.count(User.id)))
        total_users = users_count.scalar() or 0
        
        orders_count = await session.execute(select(func.count(Order.id)))
        total_orders = orders_count.scalar() or 0
        
        completed_count = await session.execute(
            select(func.count(Order.id)).where(Order.status == "completed")
        )
        completed_orders = completed_count.scalar() or 0
        
        orders_sum = await session.execute(select(func.sum(Order.cost)))
        total_revenue = orders_sum.scalar() or 0
        
        payments_sum = await session.execute(
            select(func.sum(Payment.amount)).where(Payment.status == "success")
        )
        total_payments = payments_sum.scalar() or 0
        
        balances_sum = await session.execute(select(func.sum(User.balance)))
        total_balances = balances_sum.scalar() or 0
    
    text = f"""
📊 <b>Статистика</b>

👥 <b>Пользователи:</b> {total_users}

📋 <b>Заказы:</b>
• Всего: {total_orders}
• Выполнено: {completed_orders}
• Сумма: {total_revenue:.2f} ₽

💳 <b>Платежи:</b>
• Сумма: {total_payments:.2f} ₽

💰 <b>Балансы пользователей:</b> {total_balances:.2f} ₽
"""
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin:users")
async def callback_admin_users(callback: CallbackQuery):
    """Show recent users."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    async with async_session_maker() as session:
        users_result = await session.execute(
            select(User).order_by(User.created_at.desc()).limit(10)
        )
        users = users_result.scalars().all()
        
        count_result = await session.execute(select(func.count(User.id)))
        total_count = count_result.scalar() or 0
    
    text = f"👥 <b>Пользователи</b> ({total_count} всего)\n\n"
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = []
    
    for user in users:
        username = f"@{user.username}" if user.username else "—"
        name = user.first_name or "—"
        buttons.append([
            InlineKeyboardButton(
                text=f"{name} | {username} | {user.balance:.2f}₽",
                callback_data=f"admin:user:{user.telegram_id}"
            )
        ])
    
    buttons.append([InlineKeyboardButton(text="🔍 Поиск", callback_data="admin:search")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin:orders")
async def callback_admin_orders(callback: CallbackQuery):
    """Show recent orders."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    async with async_session_maker() as session:
        orders_result = await session.execute(
            select(Order).order_by(Order.created_at.desc()).limit(15)
        )
        orders = orders_result.scalars().all()
    
    if not orders:
        text = "📋 <b>Последние заказы</b>\n\nЗаказов пока нет."
    else:
        text = "📋 <b>Последние заказы</b>\n\n"
        for order in orders:
            status_emoji = {"pending": "⏳", "processing": "🔄", "completed": "✅", "failed": "❌"}.get(order.status, "❓")
            text += f"{status_emoji} {order.action_type} × {order.quantity} = {order.cost:.2f}₽\n"
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
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
        "Поддерживается HTML форматирование.\n"
        "Отправьте /cancel для отмены.",
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
    
    if message.text == "/cancel":
        await state.clear()
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Админ-панель", callback_data="admin:back")]
        ])
        await message.answer("Рассылка отменена", reply_markup=keyboard)
        return
    
    broadcast_text = message.text or message.caption or ""
    
    if not broadcast_text:
        await message.answer("❌ Сообщение пустое")
        return
    
    await state.clear()
    
    async with async_session_maker() as session:
        users_result = await session.execute(select(User.telegram_id))
        user_ids = [row[0] for row in users_result.fetchall()]
    
    if not user_ids:
        await message.answer("❌ Нет пользователей для рассылки")
        return
    
    status_msg = await message.answer(f"📨 Рассылка: 0/{len(user_ids)}...")
    
    success_count = 0
    fail_count = 0
    
    for i, user_id in enumerate(user_ids):
        try:
            await message.bot.send_message(
                chat_id=user_id,
                text=broadcast_text,
                parse_mode="HTML"
            )
            success_count += 1
        except Exception:
            fail_count += 1
        
        if (i + 1) % 10 == 0:
            try:
                await status_msg.edit_text(f"📨 Рассылка: {i+1}/{len(user_ids)}...")
            except Exception:
                pass
        
        import asyncio
        await asyncio.sleep(0.05)
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Админ-панель", callback_data="admin:back")]
    ])
    
    await status_msg.edit_text(
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"Успешно: {success_count}\n"
        f"Ошибок: {fail_count}",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
