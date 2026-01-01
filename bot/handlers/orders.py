"""Order management handlers."""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from sqlalchemy import select, desc

from bot.models.database import User, Order, async_session_maker
from bot.services.steamsmm import SteamSmmClient, get_action_name, get_action_emoji, get_status_emoji
from bot.utils.keyboards import orders_keyboard, back_to_main_keyboard
from bot.handlers.start import get_or_create_user

router = Router()


@router.message(Command("orders"))
async def cmd_orders(message: Message):
    """Handle /orders command."""
    await show_orders(message, is_callback=False)


@router.callback_query(F.data == "menu:orders")
async def callback_orders(callback: CallbackQuery):
    """Handle orders menu callback."""
    await show_orders(callback, is_callback=True)
    await callback.answer()


async def show_orders(message_or_callback, is_callback: bool = False, page: int = 0):
    """Show user orders list."""
    if is_callback:
        user_id = message_or_callback.from_user.id
    else:
        user_id = message_or_callback.from_user.id
    
    async with async_session_maker() as session:
        # Get user
        user_result = await session.execute(
            select(User).where(User.telegram_id == user_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            text = "❌ Пользователь не найден"
            if is_callback:
                await message_or_callback.message.edit_text(
                    text,
                    reply_markup=back_to_main_keyboard()
                )
            else:
                await message_or_callback.answer(
                    text,
                    reply_markup=back_to_main_keyboard()
                )
            return
        
        # Get orders
        orders_result = await session.execute(
            select(Order)
            .where(Order.user_id == user.id)
            .order_by(desc(Order.created_at))
            .limit(50)
        )
        orders = orders_result.scalars().all()
        
        if not orders:
            text = """
📋 <b>Мои заказы</b>

У вас пока нет заказов.

Нажмите "🚀 Накрутка" чтобы создать первый заказ!
"""
            if is_callback:
                await message_or_callback.message.edit_text(
                    text,
                    reply_markup=back_to_main_keyboard(),
                    parse_mode="HTML"
                )
            else:
                await message_or_callback.answer(
                    text,
                    reply_markup=back_to_main_keyboard(),
                    parse_mode="HTML"
                )
            return
        
        # Convert orders to list of dicts for keyboard
        orders_data = []
        for order in orders:
            orders_data.append({
                "order_id": order.order_id,
                "action_type": order.action_type,
                "status": order.status,
                "quantity": order.quantity,
                "cost": order.cost
            })
        
        # Count stats
        total_orders = len(orders)
        completed_orders = sum(1 for o in orders if o.status == "completed")
        pending_orders = sum(1 for o in orders if o.status in ["pending", "processing"])
        
        text = f"""
📋 <b>Мои заказы</b>

📊 Всего: <b>{total_orders}</b>
✅ Выполнено: <b>{completed_orders}</b>
⏳ В процессе: <b>{pending_orders}</b>

Нажмите на заказ для подробностей:
"""
        
        if is_callback:
            await message_or_callback.message.edit_text(
                text,
                reply_markup=orders_keyboard(orders_data, page),
                parse_mode="HTML"
            )
        else:
            await message_or_callback.answer(
                text,
                reply_markup=orders_keyboard(orders_data, page),
                parse_mode="HTML"
            )


@router.callback_query(F.data.startswith("orders:page:"))
async def callback_orders_page(callback: CallbackQuery):
    """Handle orders pagination."""
    page = int(callback.data.split(":")[2])
    await show_orders(callback, is_callback=True, page=page)
    await callback.answer()


@router.callback_query(F.data.startswith("order:"))
async def callback_order_details(callback: CallbackQuery):
    """Show order details."""
    order_id = callback.data.split(":")[1]
    
    async with async_session_maker() as session:
        # Get order
        order_result = await session.execute(
            select(Order).where(Order.order_id == order_id)
        )
        order = order_result.scalar_one_or_none()
        
        if not order:
            await callback.answer("Заказ не найден", show_alert=True)
            return
        
        # Get fresh status from API
        client = SteamSmmClient()
        api_status = await client.check_order(order_id)
        
        if api_status.success:
            # Update order status in database
            order.status = api_status.status or order.status
            order.completed_count = api_status.completed_count or order.completed_count
            order.failed_count = api_status.failed_count or order.failed_count
            if api_status.status == "completed" and not order.completed_at:
                from datetime import datetime
                order.completed_at = datetime.utcnow()
            await session.commit()
        
        action_name = get_action_name(order.action_type)
        action_emoji = get_action_emoji(order.action_type)
        status_emoji = get_status_emoji(order.status)
        
        status_text = {
            "pending": "Ожидает",
            "processing": "В процессе",
            "completed": "Выполнен",
            "failed": "Ошибка",
            "cancelled": "Отменён"
        }.get(order.status, order.status)
        
        progress = ""
        if order.completed_count or order.failed_count:
            progress = f"\n📈 Прогресс: {order.completed_count}/{order.quantity}"
            if order.failed_count:
                progress += f" (ошибок: {order.failed_count})"
        
        created_at = order.created_at.strftime("%d.%m.%Y %H:%M") if order.created_at else "—"
        completed_at = order.completed_at.strftime("%d.%m.%Y %H:%M") if order.completed_at else "—"
        
        text = f"""
{action_emoji} <b>Заказ #{order_id[:8]}...</b>

📌 Тип: <b>{action_name}</b>
📊 Количество: <b>{order.quantity}</b>
💵 Стоимость: <b>{order.cost:.2f} ₽</b>

{status_emoji} Статус: <b>{status_text}</b>{progress}

🔗 Ссылка:
<code>{order.target_link}</code>

📅 Создан: {created_at}
{"✅ Выполнен: " + completed_at if order.status == "completed" else ""}
"""
        
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить статус", callback_data=f"order:{order_id}")],
            [InlineKeyboardButton(text="◀️ К списку заказов", callback_data="menu:orders")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")]
        ])
        
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback.answer()
