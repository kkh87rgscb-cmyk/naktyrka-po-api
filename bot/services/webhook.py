"""Webhook server for payment callbacks."""

import json
import logging
from aiohttp import web
from sqlalchemy import select

from bot.models.database import User, Payment, async_session_maker
from bot.services.antilopay import AntilopayClient
from bot.services.cryptobot import CryptoBotClient
from bot.config import settings

logger = logging.getLogger(__name__)


class PaymentWebhookServer:
    """Webhook server for receiving payment notifications."""
    
    def __init__(self, bot=None):
        """Initialize webhook server.
        
        Args:
            bot: Telegram bot instance for sending notifications.
        """
        self.bot = bot
        self.app = web.Application()
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup webhook routes."""
        self.app.router.add_post("/webhook/antilopay", self.handle_antilopay_webhook)
        self.app.router.add_post("/webhook/cryptobot", self.handle_cryptobot_webhook)
        self.app.router.add_get("/health", self.health_check)
    
    async def health_check(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        return web.json_response({"status": "ok"})
    
    async def handle_antilopay_webhook(self, request: web.Request) -> web.Response:
        """Handle Antilopay payment callback."""
        try:
            # Get raw body and signature
            body = await request.text()
            signature = request.headers.get("X-Apay-Callback", "")
            
            # Verify signature
            client = AntilopayClient()
            callback_data = client.parse_callback(body, signature)
            
            if not callback_data:
                logger.warning("Invalid Antilopay callback signature")
                return web.Response(status=200)  # Return 200 anyway per Antilopay docs
            
            # Process payment callback
            callback_type = callback_data.get("type")
            
            if callback_type == "payment":
                await self._process_antilopay_payment(callback_data)
            
            return web.Response(status=200)
            
        except Exception as e:
            logger.error(f"Error processing Antilopay webhook: {e}")
            return web.Response(status=200)  # Return 200 to prevent retries
    
    async def _process_antilopay_payment(self, data: dict):
        """Process Antilopay payment callback.
        
        Args:
            data: Callback data from Antilopay.
        """
        order_id = data.get("order_id")
        status = data.get("status")
        amount = data.get("original_amount", 0)
        
        logger.info(f"Antilopay payment {order_id}: status={status}, amount={amount}")
        
        if status not in ["SUCCESS", "FAIL"]:
            return
        
        async with async_session_maker() as session:
            # Find payment
            payment_result = await session.execute(
                select(Payment).where(Payment.payment_id == order_id)
            )
            payment = payment_result.scalar_one_or_none()
            
            if not payment:
                logger.warning(f"Payment not found: {order_id}")
                return
            
            if payment.status == "success":
                logger.info(f"Payment {order_id} already processed")
                return
            
            if status == "SUCCESS":
                payment.status = "success"
                from datetime import datetime
                payment.paid_at = datetime.utcnow()
                
                # Update user balance
                user_result = await session.execute(
                    select(User).where(User.id == payment.user_id)
                )
                user = user_result.scalar_one_or_none()
                
                if user:
                    user.balance += payment.amount
                    
                    # Notify user
                    if self.bot:
                        try:
                            await self.bot.send_message(
                                chat_id=user.telegram_id,
                                text=f"✅ <b>Платёж получен!</b>\n\n"
                                     f"Сумма: <b>{payment.amount:.0f} ₽</b>\n"
                                     f"Ваш баланс: <b>{user.balance:.2f} ₽</b>",
                                parse_mode="HTML"
                            )
                        except Exception as e:
                            logger.error(f"Failed to notify user: {e}")
            
            elif status == "FAIL":
                payment.status = "failed"
            
            await session.commit()
    
    async def handle_cryptobot_webhook(self, request: web.Request) -> web.Response:
        """Handle CryptoBot payment callback."""
        try:
            # Get raw body and signature
            body = await request.read()
            signature = request.headers.get("crypto-pay-api-signature", "")
            
            # Verify signature
            client = CryptoBotClient()
            callback_data = client.parse_webhook(body, signature)
            
            if not callback_data:
                logger.warning("Invalid CryptoBot callback signature")
                return web.Response(status=200)
            
            # Process payment callback
            update_type = callback_data.get("update_type")
            
            if update_type == "invoice_paid":
                await self._process_cryptobot_payment(callback_data.get("payload", {}))
            
            return web.Response(status=200)
            
        except Exception as e:
            logger.error(f"Error processing CryptoBot webhook: {e}")
            return web.Response(status=200)
    
    async def _process_cryptobot_payment(self, data: dict):
        """Process CryptoBot payment callback.
        
        Args:
            data: Invoice payload from CryptoBot.
        """
        invoice_id = data.get("invoice_id")
        status = data.get("status")
        paid_amount = data.get("paid_amount")
        paid_asset = data.get("paid_asset")
        payload = data.get("payload", "")
        
        logger.info(f"CryptoBot invoice {invoice_id}: status={status}, amount={paid_amount} {paid_asset}")
        
        if status != "paid":
            return
        
        async with async_session_maker() as session:
            # Find payment by external ID
            payment_result = await session.execute(
                select(Payment).where(Payment.external_payment_id == str(invoice_id))
            )
            payment = payment_result.scalar_one_or_none()
            
            if not payment:
                logger.warning(f"Payment not found for invoice: {invoice_id}")
                return
            
            if payment.status == "success":
                logger.info(f"Invoice {invoice_id} already processed")
                return
            
            payment.status = "success"
            from datetime import datetime
            payment.paid_at = datetime.utcnow()
            
            # Update user balance
            user_result = await session.execute(
                select(User).where(User.id == payment.user_id)
            )
            user = user_result.scalar_one_or_none()
            
            if user:
                user.balance += payment.amount
                
                # Notify user
                if self.bot:
                    try:
                        await self.bot.send_message(
                            chat_id=user.telegram_id,
                            text=f"✅ <b>Крипто-платёж получен!</b>\n\n"
                                 f"Получено: <b>{paid_amount} {paid_asset}</b>\n"
                                 f"Зачислено: <b>{payment.amount:.0f} ₽</b>\n"
                                 f"Ваш баланс: <b>{user.balance:.2f} ₽</b>",
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify user: {e}")
            
            await session.commit()
    
    def get_app(self) -> web.Application:
        """Get the web application."""
        return self.app
    
    async def start(self, host: str = "0.0.0.0", port: int = 8443):
        """Start the webhook server.
        
        Args:
            host: Host to bind to.
            port: Port to listen on.
        """
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()
        logger.info(f"Webhook server started on {host}:{port}")
