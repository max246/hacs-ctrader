"""cTrader API Client."""
import logging
import aiohttp
import time
from typing import Any, Dict, Optional

_LOGGER = logging.getLogger(__name__)

CTRADER_API_URL = "https://openapi.ctrader.com/v2"
CTRADER_TOKEN_URL = "https://openapi.ctrader.com/apps/token"


class CTraderAPI:
    """cTrader API client for fetching account data.
    
    Automatically handles token refresh. Access tokens expire after ~30 days,
    and refresh_token is used to obtain a new access_token automatically.
    """

    def __init__(
        self,
        access_token: str,
        refresh_token: str,
        account_id: str,
        client_id: str,
        client_secret: str,
    ):
        """Initialize API client."""
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.account_id = account_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.session: Optional[aiohttp.ClientSession] = None
        self.token_expiry: Optional[float] = None

    async def _refresh_token(self) -> bool:
        """Refresh the access token using refresh_token.
        
        Returns True if successful, False otherwise.
        """
        if not self.refresh_token:
            _LOGGER.error("No refresh token available")
            return False
        
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        params = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        
        try:
            async with self.session.get(
                CTRADER_TOKEN_URL,
                params=params,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if "accessToken" in data:
                        self.access_token = data["accessToken"]
                        if "refreshToken" in data:
                            self.refresh_token = data["refreshToken"]
                        if "expiresIn" in data:
                            self.token_expiry = time.time() + data["expiresIn"]
                        _LOGGER.info("Access token refreshed successfully")
                        return True
                    else:
                        _LOGGER.error(f"Token refresh failed: {data.get('description', 'Unknown error')}")
                        return False
                else:
                    _LOGGER.error(f"Token refresh request failed: {resp.status}")
                    return False
        except Exception as e:
            _LOGGER.error(f"Token refresh exception: {e}")
            return False

    async def _check_and_refresh_token(self) -> bool:
        """Check if token needs refresh and refresh if necessary.
        
        Returns False if token is invalid/expired and can't be refreshed.
        """
        if not self.token_expiry:
            # Set expiry to ~30 days from now if not set
            self.token_expiry = time.time() + (30 * 24 * 60 * 60)
        
        # Refresh if expiry is within 5 minutes
        if time.time() >= (self.token_expiry - 300):
            _LOGGER.info("Token expiry approaching, refreshing...")
            return await self._refresh_token()
        
        return True

    async def _request(self, method: str, endpoint: str) -> Dict[str, Any]:
        """Make an HTTP request to cTrader API."""
        # Check and refresh token if needed
        if not await self._check_and_refresh_token():
            _LOGGER.error("Failed to refresh access token")
            return None
        
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
                    _LOGGER.error("Authentication failed - token may be invalid")
                    # Try refreshing once more
                    if await self._refresh_token():
                        return await self._request(method, endpoint)
                    return None
                else:
                    _LOGGER.error(f"API error: {resp.status}")
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
