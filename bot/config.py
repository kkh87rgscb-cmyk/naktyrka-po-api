"""Configuration settings for the Telegram bot."""

import os
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Telegram Bot
    bot_token: str = ""
    admin_ids: str = ""
    
    # SteamSmm API
    steamsmm_api_url: str = "http://5.129.240.139:8080"
    steamsmm_api_key: str = ""
    
    # Antilopay
    antilopay_secret_id: str = ""
    antilopay_private_key: str = ""
    antilopay_project_id: str = ""
    antilopay_callback_public_key: str = ""
    antilopay_api_url: str = "https://lk.antilopay.com/api/v1"
    
    # CryptoBot
    cryptobot_api_token: str = ""
    cryptobot_test_mode: bool = True
    
    # Webhook
    webhook_host: str = ""
    webhook_port: int = 8443
    
    # Database
    database_url: str = "sqlite+aiosqlite:///./bot_database.db"
    
    @property
    def admin_ids_list(self) -> List[int]:
        """Parse admin IDs from comma-separated string."""
        if not self.admin_ids:
            return []
        return [int(x.strip()) for x in self.admin_ids.split(",") if x.strip()]
    
    @property
    def cryptobot_api_url(self) -> str:
        """Return CryptoBot API URL based on test mode."""
        if self.cryptobot_test_mode:
            return "https://testnet-pay.crypt.bot/api"
        return "https://pay.crypt.bot/api"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()


# Action types mapping
ACTION_TYPES = {
    "comment": "💬 Комментарии",
    "like": "👍 Лайки",
    "subscribe": "👥 Подписки",
    "review": "⭐ Обзоры"
}

# Price tiers for dynamic pricing
PRICE_TIERS = [
    (1, 99, 1.00),
    (100, 199, 0.85),
    (200, 299, 0.75),
    (300, 499, 0.65),
    (500, 999, 0.60),
    (1000, float('inf'), 0.50),
]


def get_price_per_unit(quantity: int) -> float:
    """Get price per unit based on quantity (dynamic pricing)."""
    for min_qty, max_qty, price in PRICE_TIERS:
        if min_qty <= quantity <= max_qty:
            return price
    return 1.00
