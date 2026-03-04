"""cTrader API Client."""
import logging
import aiohttp
from typing import Any, Dict, Optional

_LOGGER = logging.getLogger(__name__)

CTRADER_API_URL = "https://openapi.ctrader.com/v2"


class CTraderAPI:
    """cTrader API client for fetching account data."""

    def __init__(self, access_token: str, account_id: str):
        """Initialize API client."""
        self.access_token = access_token
        self.account_id = account_id
        self.session: Optional[aiohttp.ClientSession] = None

    async def _request(self, method: str, endpoint: str) -> Dict[str, Any]:
        """Make an HTTP request to cTrader API."""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        
        url = f"{CTRADER_API_URL}{endpoint}"
        
        try:
            async with self.session.request(method, url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return await resp.json()
                elif resp.status == 401:
                    _LOGGER.error("Authentication failed - check access token")
                    return None
                else:
                    _LOGGER.error(f"API error: {resp.status}")
                    return None
        except asyncio.TimeoutError:
            _LOGGER.error("API request timeout")
            return None
        except Exception as e:
            _LOGGER.error(f"API request failed: {e}")
            return None

    async def async_get_balance(self) -> Optional[Dict[str, Any]]:
        """Get account balance and summary."""
        data = await self._request("GET", f"/accounts/{self.account_id}")
        if data and "data" in data:
            account = data["data"]
            return {
                "balance": account.get("balance", 0),
                "equity": account.get("equity", 0),
                "margin_used": account.get("marginUsed", 0),
                "currency": account.get("currency", "USD"),
            }
        return None

    async def async_get_open_trades(self) -> Optional[list]:
        """Get list of open positions."""
        data = await self._request("GET", f"/accounts/{self.account_id}/positions")
        if data and "data" in data:
            return data["data"]
        return []

    async def async_get_closed_trades(self, limit: int = 20) -> Optional[list]:
        """Get list of closed deals/orders."""
        data = await self._request("GET", f"/accounts/{self.account_id}/deals?limit={limit}")
        if data and "data" in data:
            return data["data"]
        return []

    async def async_update(self) -> Dict[str, Any]:
        """Fetch all data from cTrader API."""
        balance = await self.async_get_balance()
        open_trades = await self.async_get_open_trades()
        closed_trades = await self.async_get_closed_trades()
        
        return {
            "balance": balance,
            "open_trades": open_trades or [],
            "closed_trades": closed_trades or [],
        }

    async def close(self):
        """Close the session."""
        if self.session:
            await self.session.close()
