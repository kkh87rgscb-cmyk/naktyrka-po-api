"""Exchange rates API client using CoinGecko."""

import aiohttp
import ssl
from typing import Optional

# CoinGecko API (free, no API key required)
COINGECKO_API_URL = "https://api.coingecko.com/api/v3"


async def get_crypto_rates() -> dict:
    """Get crypto rates from CoinGecko.
    
    Returns:
        Dictionary with rates: {"USDT": rate_in_rub, "TON": rate_in_rub}
    """
    # Fallback rates
    rates = {
        "USDT": 100.0,
        "TON": 500.0,
    }
    
    try:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(
                f"{COINGECKO_API_URL}/simple/price",
                params={
                    "ids": "tether,the-open-network",
                    "vs_currencies": "rub"
                },
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # USDT (Tether)
                    if "tether" in data and "rub" in data["tether"]:
                        rates["USDT"] = float(data["tether"]["rub"])
                    
                    # TON (The Open Network)
                    if "the-open-network" in data and "rub" in data["the-open-network"]:
                        rates["TON"] = float(data["the-open-network"]["rub"])
    
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
