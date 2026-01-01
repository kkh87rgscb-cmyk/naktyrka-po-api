"""CryptoBot payment integration via Crypto Pay API."""

import hashlib
import hmac
import json
import ssl
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import aiohttp

from bot.config import settings


@dataclass
class CryptoInvoice:
    """Result of invoice creation."""
    success: bool
    invoice_id: Optional[int] = None
    bot_invoice_url: Optional[str] = None
    pay_url: Optional[str] = None
    mini_app_invoice_url: Optional[str] = None
    status: Optional[str] = None
    amount: Optional[str] = None
    asset: Optional[str] = None
    error: Optional[str] = None


@dataclass
class InvoiceStatus:
    """Status of an invoice."""
    success: bool
    invoice_id: Optional[int] = None
    status: Optional[str] = None
    amount: Optional[str] = None
    asset: Optional[str] = None
    paid_amount: Optional[str] = None
    paid_asset: Optional[str] = None
    paid_at: Optional[str] = None
    description: Optional[str] = None
    payload: Optional[str] = None
    error: Optional[str] = None


class CryptoBotClient:
    """Client for CryptoBot Crypto Pay API."""
    
    # Supported cryptocurrencies
    SUPPORTED_ASSETS = ["USDT", "TON"]
    
    def __init__(self):
        """Initialize the CryptoBot client."""
        self.api_token = settings.cryptobot_api_token
        self.api_url = settings.cryptobot_api_url
        
        # SSL context (disable verification for compatibility)
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with API token."""
        return {
            "Crypto-Pay-API-Token": self.api_token,
            "Content-Type": "application/json"
        }
    
    def _get_connector(self) -> aiohttp.TCPConnector:
        """Get aiohttp connector with SSL settings."""
        return aiohttp.TCPConnector(ssl=self.ssl_context)
    
    def verify_webhook_signature(self, body: bytes, signature: str) -> bool:
        """Verify webhook signature from CryptoBot.
        
        Args:
            body: Raw request body.
            signature: Signature from crypto-pay-api-signature header.
            
        Returns:
            True if signature is valid.
        """
        try:
            # Create HMAC-SHA-256 hash using the API token as secret
            secret = hashlib.sha256(self.api_token.encode()).digest()
            expected_signature = hmac.new(
                secret,
                body,
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(expected_signature, signature)
        except Exception:
            return False
    
    async def get_me(self) -> Dict[str, Any]:
        """Get information about the app.
        
        Returns:
            App information.
        """
        try:
            async with aiohttp.ClientSession(connector=self._get_connector()) as session:
                async with session.get(
                    f"{self.api_url}/getMe",
                    headers=self._get_headers()
                ) as response:
                    data = await response.json()
                    if data.get("ok"):
                        return data.get("result", {})
                    return {"error": data.get("error", "Unknown error")}
        except Exception as e:
            return {"error": str(e)}
    
    async def get_balance(self) -> List[Dict[str, Any]]:
        """Get app balance for all assets.
        
        Returns:
            List of balance entries.
        """
        try:
            async with aiohttp.ClientSession(connector=self._get_connector()) as session:
                async with session.get(
                    f"{self.api_url}/getBalance",
                    headers=self._get_headers()
                ) as response:
                    data = await response.json()
                    if data.get("ok"):
                        return data.get("result", [])
                    return []
        except Exception:
            return []
    
    async def get_exchange_rates(self) -> List[Dict[str, Any]]:
        """Get current exchange rates.
        
        Returns:
            List of exchange rate entries.
        """
        try:
            async with aiohttp.ClientSession(connector=self._get_connector()) as session:
                async with session.get(
                    f"{self.api_url}/getExchangeRates",
                    headers=self._get_headers()
                ) as response:
                    data = await response.json()
                    if data.get("ok"):
                        return data.get("result", [])
                    return []
        except Exception:
            return []
    
    async def get_currencies(self) -> List[Dict[str, Any]]:
        """Get list of supported currencies.
        
        Returns:
            List of currency entries.
        """
        try:
            async with aiohttp.ClientSession(connector=self._get_connector()) as session:
                async with session.get(
                    f"{self.api_url}/getCurrencies",
                    headers=self._get_headers()
                ) as response:
                    data = await response.json()
                    if data.get("ok"):
                        return data.get("result", [])
                    return []
        except Exception:
            return []
    
    async def create_invoice(
        self,
        amount: float,
        asset: str = "USDT",
        description: str = "",
        payload: str = "",
        paid_btn_name: str = "callback",
        paid_btn_url: str = "",
        allow_comments: bool = True,
        allow_anonymous: bool = True,
        expires_in: int = 3600
    ) -> CryptoInvoice:
        """Create a new payment invoice.
        
        Args:
            amount: Payment amount.
            asset: Cryptocurrency asset (USDT, TON, BTC, etc.).
            description: Invoice description.
            payload: Custom payload data (up to 4096 bytes).
            paid_btn_name: Button type after payment (callback, openBot, openChannel).
            paid_btn_url: URL for the paid button.
            allow_comments: Allow user comments.
            allow_anonymous: Allow anonymous payments.
            expires_in: Invoice expiration time in seconds.
            
        Returns:
            CryptoInvoice with invoice details.
        """
        try:
            params = {
                "asset": asset,
                "amount": str(amount)
            }
            
            if description:
                params["description"] = description[:1024]  # Max 1024 chars
            if payload:
                params["payload"] = payload[:4096]  # Max 4096 bytes
            if paid_btn_url:
                params["paid_btn_name"] = paid_btn_name
                params["paid_btn_url"] = paid_btn_url
            
            params["allow_comments"] = allow_comments
            params["allow_anonymous"] = allow_anonymous
            params["expires_in"] = expires_in
            
            async with aiohttp.ClientSession(connector=self._get_connector()) as session:
                async with session.post(
                    f"{self.api_url}/createInvoice",
                    headers=self._get_headers(),
                    json=params
                ) as response:
                    data = await response.json()
                    
                    if data.get("ok"):
                        result = data.get("result", {})
                        return CryptoInvoice(
                            success=True,
                            invoice_id=result.get("invoice_id"),
                            bot_invoice_url=result.get("bot_invoice_url"),
                            pay_url=result.get("pay_url"),
                            mini_app_invoice_url=result.get("mini_app_invoice_url"),
                            status=result.get("status"),
                            amount=result.get("amount"),
                            asset=result.get("asset")
                        )
                    
                    error = data.get("error", {})
                    return CryptoInvoice(
                        success=False,
                        error=error.get("name", "Unknown error")
                    )
                    
        except Exception as e:
            return CryptoInvoice(success=False, error=str(e))
    
    async def get_invoices(
        self,
        invoice_ids: Optional[List[int]] = None,
        status: Optional[str] = None,
        offset: int = 0,
        count: int = 100
    ) -> List[Dict[str, Any]]:
        """Get list of invoices.
        
        Args:
            invoice_ids: Filter by specific invoice IDs.
            status: Filter by status (active, paid, expired).
            offset: Offset for pagination.
            count: Number of invoices to return.
            
        Returns:
            List of invoice dictionaries.
        """
        try:
            params = {
                "offset": offset,
                "count": min(count, 1000)  # Max 1000
            }
            
            if invoice_ids:
                params["invoice_ids"] = ",".join(map(str, invoice_ids))
            if status:
                params["status"] = status
            
            async with aiohttp.ClientSession(connector=self._get_connector()) as session:
                async with session.get(
                    f"{self.api_url}/getInvoices",
                    headers=self._get_headers(),
                    params=params
                ) as response:
                    data = await response.json()
                    if data.get("ok"):
                        return data.get("result", {}).get("items", [])
                    return []
        except Exception:
            return []
    
    async def get_invoice(self, invoice_id: int) -> InvoiceStatus:
        """Get specific invoice status.
        
        Args:
            invoice_id: Invoice ID to check.
            
        Returns:
            InvoiceStatus with current state.
        """
        try:
            invoices = await self.get_invoices(invoice_ids=[invoice_id])
            
            if invoices:
                invoice = invoices[0]
                return InvoiceStatus(
                    success=True,
                    invoice_id=invoice.get("invoice_id"),
                    status=invoice.get("status"),
                    amount=invoice.get("amount"),
                    asset=invoice.get("asset"),
                    paid_amount=invoice.get("paid_amount"),
                    paid_asset=invoice.get("paid_asset"),
                    paid_at=invoice.get("paid_at"),
                    description=invoice.get("description"),
                    payload=invoice.get("payload")
                )
            
            return InvoiceStatus(success=False, error="Invoice not found")
            
        except Exception as e:
            return InvoiceStatus(success=False, error=str(e))
    
    async def delete_invoice(self, invoice_id: int) -> bool:
        """Delete an invoice.
        
        Args:
            invoice_id: Invoice ID to delete.
            
        Returns:
            True if deleted successfully.
        """
        try:
            async with aiohttp.ClientSession(connector=self._get_connector()) as session:
                async with session.post(
                    f"{self.api_url}/deleteInvoice",
                    headers=self._get_headers(),
                    json={"invoice_id": invoice_id}
                ) as response:
                    data = await response.json()
                    return data.get("ok", False) and data.get("result", False)
        except Exception:
            return False
    
    def parse_webhook(self, body: bytes, signature: str) -> Optional[Dict[str, Any]]:
        """Parse and verify webhook from CryptoBot.
        
        Args:
            body: Raw request body.
            signature: Signature from crypto-pay-api-signature header.
            
        Returns:
            Parsed webhook data if valid, None otherwise.
        """
        if not self.verify_webhook_signature(body, signature):
            return None
        
        try:
            data = json.loads(body.decode('utf-8'))
            return data
        except json.JSONDecodeError:
            return None


async def get_rub_to_crypto_rate(asset: str = "USDT") -> Optional[float]:
    """Get exchange rate from RUB to crypto asset.
    
    Args:
        asset: Cryptocurrency asset.
        
    Returns:
        Exchange rate or None if not available.
    """
    client = CryptoBotClient()
    rates = await client.get_exchange_rates()
    
    # Find rate for asset to RUB
    for rate in rates:
        if rate.get("source") == asset and rate.get("target") == "RUB":
            return float(rate.get("rate", 0))
    
    return None


async def convert_rub_to_crypto(amount_rub: float, asset: str = "USDT") -> Optional[float]:
    """Convert RUB amount to crypto.
    
    Args:
        amount_rub: Amount in RUB.
        asset: Target cryptocurrency.
        
    Returns:
        Amount in crypto or None.
    """
    rate = await get_rub_to_crypto_rate(asset)
    if rate and rate > 0:
        return round(amount_rub / rate, 8)
    return None
