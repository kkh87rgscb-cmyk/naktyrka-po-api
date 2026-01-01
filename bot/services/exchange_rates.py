"""Exchange rates from CryptoBot API."""

from typing import Optional
from bot.services.cryptobot import CryptoBotClient


async def get_crypto_rates() -> dict:
    """Get crypto rates from CryptoBot API.
    
    Returns:
        Dictionary with rates: {"USDT": rate_in_rub, "TON": rate_in_rub}
    """
    # Fallback rates
    rates = {
        "USDT": 90.0,
        "TON": 400.0,
    }
    
    try:
        client = CryptoBotClient()
        exchange_rates = await client.get_exchange_rates()
        
        for rate_info in exchange_rates:
            source = rate_info.get("source")
            target = rate_info.get("target")
            rate_value = rate_info.get("rate")
            
            if target == "RUB" and rate_value:
                if source == "USDT":
                    rates["USDT"] = float(rate_value)
                elif source == "TON":
                    rates["TON"] = float(rate_value)
    
    except Exception:
        pass
    
    return rates


async def convert_rub_to_crypto(amount_rub: float, asset: str) -> Optional[float]:
    """Convert RUB amount to cryptocurrency.
    
    Args:
        amount_rub: Amount in RUB.
        asset: Cryptocurrency (USDT or TON).
        
    Returns:
        Amount in crypto or None if failed.
    """
    rates = await get_crypto_rates()
    rate = rates.get(asset)
    
    if rate and rate > 0:
        crypto_amount = amount_rub / rate
        return round(crypto_amount, 2)
    
    return None
