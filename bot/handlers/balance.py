"""Balance and payment handlers."""

import uuid
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select

from bot.models.database import User, Payment, async_session_maker
from bot.services.antilopay import AntilopayClient, generate_order_id
from bot.services.cryptobot import CryptoBotClient
from bot.utils.keyboards import (
    topup_amount_keyboard, 
    payment_method_keyboard, 
    crypto_currency_keyboard,
    back_to_main_keyboard,
    payment_status_keyboard,
    cancel_keyboard
)
from bot.handlers.start import get_or_create_user

router = Router()


class TopupStates(StatesGroup):
    """States for top-up flow."""
    waiting_custom_amount = State()
    waiting_email = State()


@router.message(Command("balance"))
async def cmd_balance(message: Message):
    """Handle /balance command."""
    user = await get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )
    
    text = f"""
💰 <b>Ваш баланс</b>

Доступно: <b>{user.balance:.2f} ₽</b>

Для пополнения нажмите кнопку ниже:
"""
    
    await message.answer(
        text,
        reply_markup=topup_amount_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "menu:balance")
async def callback_balance(callback: CallbackQuery):
    """Handle balance menu callback."""
    user = await get_or_create_user(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
        last_name=callback.from_user.last_name
    )
    
    text = f"""
💰 <b>Ваш баланс</b>

Доступно: <b>{user.balance:.2f} ₽</b>
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=topup_amount_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "menu:topup")
async def callback_topup_menu(callback: CallbackQuery):
    """Handle top-up menu callback."""
    text = """
💳 <b>Пополнение баланса</b>

Выберите сумму для пополнения:
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=topup_amount_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("topup:"))
async def callback_topup_amount(callback: CallbackQuery, state: FSMContext):
    """Handle top-up amount selection."""
    amount_str = callback.data.split(":")[1]
    
    if amount_str == "custom":
        await callback.message.edit_text(
            "✏️ <b>Введите сумму пополнения</b>\n\n"
            "Минимальная сумма: 50₽\n"
            "Максимальная сумма: 100000₽",
            parse_mode="HTML"
        )
        await state.set_state(TopupStates.waiting_custom_amount)
        await callback.answer()
        return
    
    amount = float(amount_str)
    await state.update_data(topup_amount=amount)
    
    text = f"""
💳 <b>Пополнение на {amount:.0f} ₽</b>

Выберите способ оплаты:
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=payment_method_keyboard(amount),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(TopupStates.waiting_custom_amount)
async def process_custom_amount(message: Message, state: FSMContext):
    """Process custom top-up amount."""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(
            "Отменено",
            reply_markup=back_to_main_keyboard()
        )
        return
    
    try:
        amount = float(message.text.replace(",", ".").strip())
        
        if amount < 50:
            await message.answer("❌ Минимальная сумма: 50₽")
            return
        
        if amount > 100000:
            await message.answer("❌ Максимальная сумма: 100000₽")
            return
        
        await state.update_data(topup_amount=amount)
        await state.clear()
        
        text = f"""
💳 <b>Пополнение на {amount:.0f} ₽</b>

Выберите способ оплаты:
"""
        
        await message.answer(
            text,
            reply_markup=payment_method_keyboard(amount),
            parse_mode="HTML"
        )
        
    except ValueError:
        await message.answer("❌ Введите корректную сумму числом")


@router.callback_query(F.data.startswith("pay:antilopay:"))
async def callback_antilopay_payment(callback: CallbackQuery, state: FSMContext):
    """Handle Antilopay payment initiation."""
    amount = float(callback.data.split(":")[2])
    
    await state.update_data(topup_amount=amount, payment_method="antilopay")
    
    # Check if we have user email
    await callback.message.edit_text(
        "📧 <b>Введите ваш email</b>\n\n"
        "Email необходим для отправки чека об оплате.",
        parse_mode="HTML"
    )
    await state.set_state(TopupStates.waiting_email)
    await callback.answer()


@router.message(TopupStates.waiting_email)
async def process_email_and_create_payment(message: Message, state: FSMContext):
    """Process email and create Antilopay payment."""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(
            "Отменено",
            reply_markup=back_to_main_keyboard()
        )
        return
    
    email = message.text.strip()
    
    # Basic email validation
    if "@" not in email or "." not in email:
        await message.answer("❌ Введите корректный email адрес")
        return
    
    data = await state.get_data()
    amount = data.get("topup_amount", 0)
    
    if amount <= 0:
        await state.clear()
        await message.answer(
            "❌ Ошибка: сумма не указана",
            reply_markup=back_to_main_keyboard()
        )
        return
    
    await state.clear()
    
    # Create Antilopay payment
    client = AntilopayClient()
    order_id = generate_order_id(f"TG{message.from_user.id}_")
    
    result = await client.create_payment(
        amount=amount,
        order_id=order_id,
        description=f"Пополнение баланса Steam SMM Bot",
        customer_email=email
    )
    
    if result.success:
        # Save payment to database
        async with async_session_maker() as session:
            user_result = await session.execute(
                select(User).where(User.telegram_id == message.from_user.id)
            )
            user = user_result.scalar_one_or_none()
            
            if user:
                payment = Payment(
                    user_id=user.id,
                    payment_id=order_id,
                    payment_system="antilopay",
                    amount=amount,
                    status="pending",
                    payment_url=result.payment_url,
                    external_payment_id=result.payment_id
                )
                session.add(payment)
                await session.commit()
        
        text = f"""
💳 <b>Оплата через Antilopay</b>

Сумма: <b>{amount:.0f} ₽</b>

Нажмите на кнопку ниже для оплаты:
<a href="{result.payment_url}">🔗 Оплатить</a>

После оплаты баланс будет пополнен автоматически.
"""
        
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить", url=result.payment_url)],
            [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_payment:{order_id}")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")]
        ])
        
        await message.answer(
            text,
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    else:
        await message.answer(
            f"❌ Ошибка создания платежа: {result.error}",
            reply_markup=back_to_main_keyboard()
        )


@router.callback_query(F.data.startswith("pay:cryptobot:"))
async def callback_cryptobot_payment(callback: CallbackQuery, state: FSMContext):
    """Handle CryptoBot payment - show currency selection."""
    amount = float(callback.data.split(":")[2])
    
    await state.update_data(topup_amount=amount)
    
    text = f"""
🪙 <b>Оплата криптовалютой</b>

Сумма: <b>{amount:.0f} ₽</b>

Выберите криптовалюту:
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=crypto_currency_keyboard(amount),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("crypto:"))
async def callback_crypto_currency(callback: CallbackQuery, state: FSMContext):
    """Handle cryptocurrency selection and create invoice."""
    parts = callback.data.split(":")
    currency = parts[1]
    amount_rub = float(parts[2])
    
    await callback.message.edit_text(
        "⏳ Создаём счёт на оплату...",
        parse_mode="HTML"
    )
    
    # Fixed exchange rates (approximate)
    # USDT ≈ 90 RUB, TON ≈ 350 RUB
    EXCHANGE_RATES = {
        "USDT": 90.0,
        "TON": 350.0,
    }
    
    rate = EXCHANGE_RATES.get(currency, 90.0)
    crypto_amount = round(amount_rub / rate, 2)
    
    # Minimum amounts
    if currency == "USDT" and crypto_amount < 1:
        crypto_amount = 1.0
    if currency == "TON" and crypto_amount < 0.1:
        crypto_amount = 0.1
    
    # Create CryptoBot invoice
    client = CryptoBotClient()
    
    # Create payload with user info
    payload = f"topup_{callback.from_user.id}_{amount_rub}"
    
    result = await client.create_invoice(
        amount=crypto_amount,
        asset=currency,
        description=f"Пополнение баланса Steam SMM Bot на {amount_rub:.0f} RUB",
        payload=payload,
        expires_in=3600
    )
    
    if result.success:
        # Save payment to database
        async with async_session_maker() as session:
            user_result = await session.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            user = user_result.scalar_one_or_none()
            
            if user:
                payment = Payment(
                    user_id=user.id,
                    payment_id=f"CB{result.invoice_id}",
                    payment_system="cryptobot",
                    amount=amount_rub,
                    crypto_amount=crypto_amount,
                    crypto_currency=currency,
                    status="pending",
                    payment_url=result.pay_url or result.bot_invoice_url,
                    external_payment_id=str(result.invoice_id)
                )
                session.add(payment)
                await session.commit()
        
        pay_url = result.pay_url or result.bot_invoice_url
        
        text = f"""
🪙 <b>Оплата криптовалютой</b>

Сумма: <b>{crypto_amount} {currency}</b>
(≈ {amount_rub:.0f} ₽)

Нажмите кнопку для оплаты.
После оплаты нажмите "Проверить оплату":
"""
        
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🪙 Оплатить", url=pay_url)],
            [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_crypto:{result.invoice_id}")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")]
        ])
        
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            f"❌ Ошибка создания счёта: {result.error}",
            reply_markup=back_to_main_keyboard()
        )
    
    await callback.answer()


@router.callback_query(F.data.startswith("check_payment:"))
async def callback_check_antilopay_payment(callback: CallbackQuery):
    """Check Antilopay payment status."""
    order_id = callback.data.split(":")[1]
    
    client = AntilopayClient()
    status = await client.check_payment(order_id)
    
    if status.success:
        if status.status == "SUCCESS":
            # Update user balance
            async with async_session_maker() as session:
                # Find payment
                payment_result = await session.execute(
                    select(Payment).where(Payment.payment_id == order_id)
                )
                payment = payment_result.scalar_one_or_none()
                
                if payment and payment.status != "success":
                    payment.status = "success"
                    
                    # Update user balance
                    user_result = await session.execute(
                        select(User).where(User.id == payment.user_id)
                    )
                    user = user_result.scalar_one_or_none()
                    
                    if user:
                        user.balance += payment.amount
                    
                    await session.commit()
            
            await callback.message.edit_text(
                f"✅ <b>Оплата успешна!</b>\n\n"
                f"Сумма: <b>{status.original_amount:.0f} ₽</b>\n"
                f"Баланс пополнен.",
                reply_markup=back_to_main_keyboard(),
                parse_mode="HTML"
            )
        elif status.status == "PENDING":
            await callback.answer("⏳ Ожидание оплаты...", show_alert=True)
        elif status.status in ["FAIL", "EXPIRED", "CANCEL"]:
            await callback.message.edit_text(
                "❌ Платёж отменён или истёк срок оплаты.",
                reply_markup=back_to_main_keyboard()
            )
        else:
            await callback.answer(f"Статус: {status.status}", show_alert=True)
    else:
        await callback.answer(f"Ошибка: {status.error}", show_alert=True)


@router.callback_query(F.data.startswith("check_crypto:"))
async def callback_check_crypto_payment(callback: CallbackQuery):
    """Check CryptoBot payment status."""
    invoice_id = int(callback.data.split(":")[1])
    
    client = CryptoBotClient()
    status = await client.get_invoice(invoice_id)
    
    if status.success:
        if status.status == "paid":
            # Update user balance
            async with async_session_maker() as session:
                # Find payment
                payment_result = await session.execute(
                    select(Payment).where(Payment.external_payment_id == str(invoice_id))
                )
                payment = payment_result.scalar_one_or_none()
                
                if payment and payment.status != "success":
                    payment.status = "success"
                    
                    # Update user balance
                    user_result = await session.execute(
                        select(User).where(User.id == payment.user_id)
                    )
                    user = user_result.scalar_one_or_none()
                    
                    if user:
                        user.balance += payment.amount
                    
                    await session.commit()
            
            await callback.message.edit_text(
                f"✅ <b>Оплата успешна!</b>\n\n"
                f"Получено: <b>{status.paid_amount} {status.paid_asset}</b>\n"
                f"Баланс пополнен.",
                reply_markup=back_to_main_keyboard(),
                parse_mode="HTML"
            )
        elif status.status == "active":
            await callback.answer("⏳ Ожидание оплаты...", show_alert=True)
        elif status.status == "expired":
            await callback.message.edit_text(
                "❌ Срок оплаты счёта истёк.",
                reply_markup=back_to_main_keyboard()
            )
        else:
            await callback.answer(f"Статус: {status.status}", show_alert=True)
    else:
        await callback.answer(f"Ошибка: {status.error}", show_alert=True)
