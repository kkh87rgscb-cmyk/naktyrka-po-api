"""Start and basic command handlers."""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from bot.models.database import User, async_session_maker
from bot.utils.keyboards import main_menu_keyboard, back_to_main_keyboard
from bot.config import settings

router = Router()


async def get_or_create_user(telegram_id: int, username: str = None, first_name: str = None, last_name: str = None) -> User:
    """Get existing user or create a new one."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                balance=0.0
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        else:
            # Update user info
            user.username = username
            user.first_name = first_name
            user.last_name = last_name
            await session.commit()
        
        return user


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Handle /start command."""
    user = await get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )
    
    welcome_text = f"""
🎮 <b>Добро пожаловать в Steam SMM Bot!</b>

Я помогу вам с накруткой в Steam:
• 💬 <b>Комментарии</b> на профиле
• 👍 <b>Лайки</b> на скриншоты и иллюстрации
• 👥 <b>Подписки</b> на группы
• ⭐ <b>Обзоры</b> на игры

💰 Ваш баланс: <b>{user.balance:.2f} ₽</b>

Выберите действие в меню ниже:
"""
    
    await message.answer(
        welcome_text,
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML"
    )


@router.message(Command("menu"))
async def cmd_menu(message: Message):
    """Handle /menu command."""
    await show_main_menu(message)


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handle /help command."""
    help_text = """
❓ <b>Справка по использованию бота</b>

<b>Основные команды:</b>
/start - Запуск бота
/menu - Главное меню
/balance - Проверить баланс
/orders - Мои заказы
/prices - Цены на услуги
/help - Эта справка

<b>Как сделать заказ:</b>
1. Нажмите "🚀 Накрутка" в меню
2. Выберите тип накрутки
3. Укажите количество
4. Отправьте ссылку на Steam
5. Подтвердите заказ

<b>Как пополнить баланс:</b>
1. Нажмите "💳 Пополнить"
2. Выберите сумму
3. Выберите способ оплаты
4. Оплатите по ссылке

<b>Поддержка:</b>
При возникновении проблем обращайтесь к администратору.
"""
    
    await message.answer(
        help_text,
        reply_markup=back_to_main_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "menu:main")
async def callback_main_menu(callback: CallbackQuery):
    """Handle main menu callback."""
    user = await get_or_create_user(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
        last_name=callback.from_user.last_name
    )
    
    text = f"""
🎮 <b>Steam SMM Bot</b>

💰 Ваш баланс: <b>{user.balance:.2f} ₽</b>

Выберите действие:
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "menu:help")
async def callback_help(callback: CallbackQuery):
    """Handle help menu callback."""
    help_text = """
❓ <b>Справка по использованию бота</b>

<b>Как сделать заказ:</b>
1. Нажмите "🚀 Накрутка"
2. Выберите тип действия
3. Укажите количество
4. Отправьте ссылку на Steam
5. Подтвердите заказ

<b>Типы накрутки:</b>
• 💬 Комментарии - на профиле Steam
• 👍 Лайки - на скриншоты/иллюстрации
• 👥 Подписки - на группы Steam
• ⭐ Обзоры - рейтинг на игры

<b>Оплата:</b>
• 💳 Банковские карты (Antilopay)
• 🪙 Криптовалюты (CryptoBot)
"""
    
    await callback.message.edit_text(
        help_text,
        reply_markup=back_to_main_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


async def show_main_menu(message: Message):
    """Show main menu."""
    user = await get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )
    
    text = f"""
🎮 <b>Steam SMM Bot</b>

💰 Ваш баланс: <b>{user.balance:.2f} ₽</b>

Выберите действие:
"""
    
    await message.answer(
        text,
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML"
    )
