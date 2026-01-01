"""SteamSmm API client for interacting with the boosting service."""

import aiohttp
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

from bot.config import settings


class ActionType(str, Enum):
    """Types of available boosting actions."""
    COMMENT = "comment"
    LIKE = "like"
    SUBSCRIBE = "subscribe"
    REVIEW = "review"


@dataclass
class OrderResult:
    """Result of creating an order."""
    success: bool
    order_id: Optional[str] = None
    action_type: Optional[str] = None
    quantity: Optional[int] = None
    cost: Optional[float] = None
    price_per_unit: Optional[float] = None
    price_type: Optional[str] = None
    status: Optional[str] = None
    error: Optional[str] = None


@dataclass
class UserStats:
    """User statistics from API."""
    success: bool
    user_id: Optional[int] = None
    balance: Optional[float] = None
    total_orders: Optional[int] = None
    completed_orders: Optional[int] = None
    total_spent: Optional[float] = None
    action_prices: Optional[Dict] = None
    has_access: Optional[bool] = None
    error: Optional[str] = None


@dataclass
class OrderStatus:
    """Status of an order."""
    success: bool
    order_id: Optional[str] = None
    status: Optional[str] = None
    action_type: Optional[str] = None
    quantity: Optional[int] = None
    completed_count: Optional[int] = None
    failed_count: Optional[int] = None
    cost: Optional[float] = None
    target_link: Optional[str] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None


class SteamSmmClient:
    """Client for interacting with SteamSmm API."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the client.
        
        Args:
            api_key: API key for authentication. If not provided, uses settings.
        """
        self.api_key = api_key or settings.steamsmm_api_key
        self.base_url = settings.steamsmm_api_url
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    async def get_user_stats(self) -> UserStats:
        """Get user statistics and balance.
        
        Returns:
            UserStats with user information and balance.
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/api/user_stats",
                    headers=self._get_headers()
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("status") == "success":
                            user_data = data.get("data", {})
                            return UserStats(
                                success=True,
                                user_id=user_data.get("user_id"),
                                balance=user_data.get("balance", 0.0),
                                total_orders=user_data.get("total_orders", 0),
                                completed_orders=user_data.get("completed_orders", 0),
                                total_spent=user_data.get("total_spent", 0.0),
                                action_prices=user_data.get("action_prices", {}),
                                has_access=user_data.get("has_access", False)
                            )
                        return UserStats(success=False, error=data.get("message", "Unknown error"))
                    
                    error_data = await response.json()
                    return UserStats(
                        success=False,
                        error=error_data.get("message", f"HTTP {response.status}")
                    )
        except Exception as e:
            return UserStats(success=False, error=str(e))
    
    async def create_order(
        self,
        action_type: ActionType,
        quantity: int,
        target_link: str
    ) -> OrderResult:
        """Create a new boosting order.
        
        Args:
            action_type: Type of action (comment, like, subscribe, review).
            quantity: Number of actions to perform.
            target_link: Target Steam URL.
        
        Returns:
            OrderResult with order details.
        """
        try:
            payload = {
                "action_type": action_type.value,
                "quantity": quantity,
                "target_link": target_link
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/action/create",
                    headers=self._get_headers(),
                    json=payload
                ) as response:
                    data = await response.json()
                    
                    if response.status == 200 and data.get("status") == "success":
                        order_data = data.get("data", {})
                        return OrderResult(
                            success=True,
                            order_id=order_data.get("order_id"),
                            action_type=order_data.get("action_type"),
                            quantity=order_data.get("quantity"),
                            cost=order_data.get("cost"),
                            price_per_unit=order_data.get("price_per_unit"),
                            price_type=order_data.get("price_type", "dynamic"),
                            status=order_data.get("status", "pending")
                        )
                    
                    error_msg = data.get("message", data.get("error", f"HTTP {response.status}"))
                    return OrderResult(success=False, error=error_msg)
                    
        except Exception as e:
            return OrderResult(success=False, error=str(e))
    
    async def check_order(self, order_id: str) -> OrderStatus:
        """Check the status of an order.
        
        Args:
            order_id: The order ID to check.
        
        Returns:
            OrderStatus with current order state.
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/action/check",
                    headers=self._get_headers(),
                    json={"order_id": order_id}
                ) as response:
                    data = await response.json()
                    
                    if response.status == 200 and data.get("status") == "success":
                        order_data = data.get("data", {})
                        return OrderStatus(
                            success=True,
                            order_id=order_data.get("order_id"),
                            status=order_data.get("status"),
                            action_type=order_data.get("action_type"),
                            quantity=order_data.get("quantity"),
                            completed_count=order_data.get("completed_count", 0),
                            failed_count=order_data.get("failed_count", 0),
                            cost=order_data.get("cost"),
                            target_link=order_data.get("target_link"),
                            created_at=order_data.get("created_at"),
                            completed_at=order_data.get("completed_at")
                        )
                    
                    return OrderStatus(
                        success=False,
                        error=data.get("message", f"HTTP {response.status}")
                    )
                    
        except Exception as e:
            return OrderStatus(success=False, error=str(e))
    
    async def get_order_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get order history for the user.
        
        Args:
            limit: Maximum number of orders to return.
        
        Returns:
            List of order dictionaries.
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/api/order_history",
                    headers=self._get_headers(),
                    params={"limit": limit}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("status") == "success":
                            return data.get("data", {}).get("orders", [])
                    return []
        except Exception:
            return []


def get_action_emoji(action_type: str) -> str:
    """Get emoji for action type."""
    emojis = {
        "comment": "💬",
        "like": "👍",
        "subscribe": "👥",
        "review": "⭐"
    }
    return emojis.get(action_type, "📌")


def get_action_name(action_type: str) -> str:
    """Get human-readable name for action type."""
    names = {
        "comment": "Комментарии",
        "like": "Лайки",
        "subscribe": "Подписки",
        "review": "Обзоры"
    }
    return names.get(action_type, action_type)


def get_status_emoji(status: str) -> str:
    """Get emoji for order status."""
    emojis = {
        "pending": "⏳",
        "processing": "🔄",
        "completed": "✅",
        "failed": "❌",
        "cancelled": "🚫"
    }
    return emojis.get(status, "❓")
