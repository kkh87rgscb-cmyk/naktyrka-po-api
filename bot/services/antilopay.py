"""Antilopay payment integration."""

import base64
import json
import uuid
from typing import Optional, Dict, Any
from dataclasses import dataclass
import aiohttp

from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15

from bot.config import settings


@dataclass
class PaymentResult:
    """Result of payment creation."""
    success: bool
    payment_id: Optional[str] = None
    payment_url: Optional[str] = None
    error: Optional[str] = None
    error_code: Optional[int] = None


@dataclass
class PaymentStatus:
    """Status of a payment."""
    success: bool
    payment_id: Optional[str] = None
    order_id: Optional[str] = None
    status: Optional[str] = None
    amount: Optional[float] = None
    original_amount: Optional[float] = None
    fee: Optional[float] = None
    currency: Optional[str] = None
    pay_method: Optional[str] = None
    pay_data: Optional[str] = None
    error: Optional[str] = None


class AntilopayClient:
    """Client for Antilopay payment API."""
    
    def __init__(self):
        """Initialize the Antilopay client."""
        self.secret_id = settings.antilopay_secret_id
        self.private_key = settings.antilopay_private_key
        self.project_id = settings.antilopay_project_id
        self.callback_public_key = settings.antilopay_callback_public_key
        self.api_url = settings.antilopay_api_url
    
    def _create_signature(self, payload: str) -> str:
        """Create RSA-SHA256 signature for the request.
        
        Args:
            payload: JSON string to sign.
            
        Returns:
            Base64 encoded signature.
        """
        try:
            # Decode the private key from base64
            key_bytes = base64.b64decode(self.private_key)
            rsa_key = RSA.import_key(key_bytes)
            
            # Create the signature
            payload_bytes = payload.encode('utf-8')
            hash_obj = SHA256.new(payload_bytes)
            signature = pkcs1_15.new(rsa_key).sign(hash_obj)
            
            return base64.b64encode(signature).decode('utf-8')
        except Exception as e:
            raise ValueError(f"Failed to create signature: {e}")
    
    def _verify_callback_signature(self, payload: str, signature: str) -> bool:
        """Verify callback signature from Antilopay.
        
        Args:
            payload: The callback body as string.
            signature: The signature from X-Apay-Callback header.
            
        Returns:
            True if signature is valid.
        """
        try:
            # Decode the public key from base64
            key_bytes = base64.b64decode(self.callback_public_key)
            rsa_key = RSA.import_key(key_bytes)
            
            # Verify the signature
            payload_bytes = payload.encode('utf-8')
            hash_obj = SHA256.new(payload_bytes)
            signature_bytes = base64.b64decode(signature)
            
            pkcs1_15.new(rsa_key).verify(hash_obj, signature_bytes)
            return True
        except Exception:
            return False
    
    def _get_headers(self, payload: str) -> Dict[str, str]:
        """Get request headers with signature.
        
        Args:
            payload: JSON string payload.
            
        Returns:
            Headers dictionary.
        """
        signature = self._create_signature(payload)
        return {
            "Content-Type": "application/json",
            "X-Apay-Secret-Id": self.secret_id,
            "X-Apay-Sign": signature,
            "X-Apay-Sign-Version": "1"
        }
    
    async def create_payment(
        self,
        amount: float,
        order_id: str,
        description: str,
        customer_email: str,
        customer_phone: Optional[str] = None,
        success_url: Optional[str] = None,
        fail_url: Optional[str] = None,
        prefer_methods: Optional[list] = None
    ) -> PaymentResult:
        """Create a new payment.
        
        Args:
            amount: Payment amount in RUB.
            order_id: Unique order ID.
            description: Payment description.
            customer_email: Customer email.
            customer_phone: Customer phone (optional).
            success_url: URL to redirect after successful payment.
            fail_url: URL to redirect after failed payment.
            prefer_methods: Preferred payment methods.
            
        Returns:
            PaymentResult with payment details.
        """
        try:
            # Build customer data
            customer = {"email": customer_email}
            if customer_phone:
                customer["phone"] = customer_phone
            
            # Build payload
            payload_dict = {
                "project_identificator": self.project_id,
                "amount": amount,
                "order_id": order_id,
                "currency": "RUB",
                "product_name": "Пополнение баланса",
                "product_type": "services",
                "description": description,
                "customer": customer
            }
            
            if success_url:
                payload_dict["success_url"] = success_url
            if fail_url:
                payload_dict["fail_url"] = fail_url
            if prefer_methods:
                payload_dict["prefer_methods"] = prefer_methods
            
            # Create JSON without extra spaces
            payload = json.dumps(payload_dict, separators=(',', ':'), ensure_ascii=False)
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/payment/create",
                    headers=self._get_headers(payload),
                    data=payload.encode('utf-8')
                ) as response:
                    data = await response.json()
                    
                    if data.get("code") == 0:
                        return PaymentResult(
                            success=True,
                            payment_id=data.get("payment_id"),
                            payment_url=data.get("payment_url")
                        )
                    
                    return PaymentResult(
                        success=False,
                        error=data.get("error", "Unknown error"),
                        error_code=data.get("code")
                    )
                    
        except Exception as e:
            return PaymentResult(success=False, error=str(e))
    
    async def check_payment(self, order_id: str) -> PaymentStatus:
        """Check payment status.
        
        Args:
            order_id: Order ID to check.
            
        Returns:
            PaymentStatus with current state.
        """
        try:
            payload_dict = {
                "project_identificator": self.project_id,
                "order_id": order_id
            }
            
            payload = json.dumps(payload_dict, separators=(',', ':'), ensure_ascii=False)
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/payment/check",
                    headers=self._get_headers(payload),
                    data=payload.encode('utf-8')
                ) as response:
                    data = await response.json()
                    
                    if data.get("code") == 0:
                        return PaymentStatus(
                            success=True,
                            payment_id=data.get("payment_id"),
                            order_id=data.get("order_id"),
                            status=data.get("status"),
                            amount=data.get("amount"),
                            original_amount=data.get("original_amount"),
                            fee=data.get("fee"),
                            currency=data.get("currency"),
                            pay_method=data.get("pay_method"),
                            pay_data=data.get("pay_data")
                        )
                    
                    return PaymentStatus(
                        success=False,
                        error=data.get("error", "Unknown error")
                    )
                    
        except Exception as e:
            return PaymentStatus(success=False, error=str(e))
    
    async def get_project_balance(self) -> Dict[str, Any]:
        """Get project balance.
        
        Returns:
            Balance information.
        """
        try:
            payload_dict = {
                "project_identificator": self.project_id
            }
            
            payload = json.dumps(payload_dict, separators=(',', ':'), ensure_ascii=False)
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/project/balance",
                    headers=self._get_headers(payload),
                    data=payload.encode('utf-8')
                ) as response:
                    return await response.json()
                    
        except Exception as e:
            return {"error": str(e)}
    
    def parse_callback(self, payload: str, signature: str) -> Optional[Dict[str, Any]]:
        """Parse and verify callback from Antilopay.
        
        Args:
            payload: Raw callback body.
            signature: Signature from X-Apay-Callback header.
            
        Returns:
            Parsed callback data if valid, None otherwise.
        """
        if not self._verify_callback_signature(payload, signature):
            return None
        
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return None


def generate_order_id(prefix: str = "AP") -> str:
    """Generate a unique order ID for Antilopay.
    
    Args:
        prefix: Prefix for the order ID.
        
    Returns:
        Unique order ID string.
    """
    unique_part = uuid.uuid4().hex[:12].upper()
    return f"{prefix}{unique_part}"
