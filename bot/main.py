"""Main entry point for the Telegram bot."""

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import settings
from bot.models.database import init_db
from bot.handlers import start, balance, boost, orders, admin
from bot.services.webhook import PaymentWebhookServer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


async def main():
    """Main function to run the bot."""
    
    # Check required settings
    if not settings.bot_token:
        logger.error("BOT_TOKEN is not set!")
        sys.exit(1)
    
    # Initialize database
    logger.info("Initializing database...")
    await init_db()
    
    # Initialize bot and dispatcher
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Register routers
    dp.include_router(start.router)
    dp.include_router(balance.router)
    dp.include_router(boost.router)
    dp.include_router(orders.router)
    dp.include_router(admin.router)
    
    # Start webhook server for payments (in background)
    webhook_server = PaymentWebhookServer(bot=bot)
    
    async def start_webhook_server():
        """Start webhook server in background."""
        try:
            await webhook_server.start(
                host="0.0.0.0",
                port=settings.webhook_port
            )
        except Exception as e:
            logger.error(f"Failed to start webhook server: {e}")
    
    # Create background task for webhook server
    webhook_task = asyncio.create_task(start_webhook_server())
    
    # Start bot polling
    logger.info("Starting bot...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        webhook_task.cancel()
        await bot.session.close()


def run():
    """Run the bot."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped")


if __name__ == "__main__":
    run()
