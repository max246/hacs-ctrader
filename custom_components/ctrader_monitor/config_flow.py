"""Config flow for cTrader Monitor."""
import logging
from typing import Any, Dict, Optional

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .api import CTraderAPI

_LOGGER = logging.getLogger(__name__)

DOMAIN = "ctrader_monitor"

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("client_id"): str,
        vol.Required("client_secret"): str,
        vol.Required("account_id"): str,
    }
)

STEP_AUTH_CODE_SCHEMA = vol.Schema(
    {
        vol.Required("authorization_code"): str,
    }
)


async def exchange_authorization_code(
    client_id: str,
    client_secret: str,
    authorization_code: str,
    redirect_uri: str = "http://localhost:8123/auth/callback",
) -> Dict[str, Any]:
    """Exchange authorization code for access and refresh tokens."""
    token_url = "https://openapi.ctrader.com/apps/token"
    
    params = {
        "grant_type": "authorization_code",
        "code": authorization_code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                token_url,
                params=params,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    _LOGGER.error(f"Token exchange failed: {resp.status}")
                    return None
    except Exception as e:
        _LOGGER.error(f"Token exchange error: {e}")
        return None


async def validate_tokens(hass: HomeAssistant, data: dict) -> dict:
    """Validate tokens by fetching account data."""
    api = CTraderAPI(
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        account_id=data["account_id"],
        client_id=data["client_id"],
        client_secret=data["client_secret"],
    )
    
    try:
        result = await api.async_get_balance()
        if result is None:
            raise InvalidAuth
    except Exception as e:
        _LOGGER.error(f"Connection failed: {e}")
        raise InvalidAuth
    
    return {"title": f"cTrader Account {data['account_id']}"}


class CTraderConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for cTrader Monitor."""

    VERSION = 1
    
    def __init__(self):
        """Initialize config flow."""
        super().__init__()
        self.client_id = None
        self.client_secret = None
        self.account_id = None
        self.auth_uri = None

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step - get app credentials."""
        errors: Dict[str, str] = {}
        
        if user_input is not None:
            self.client_id = user_input["client_id"]
            self.client_secret = user_input["client_secret"]
            self.account_id = user_input["account_id"]
            
            # Generate authorization URI
            self.auth_uri = (
                f"https://id.ctrader.com/my/settings/openapi/grantingaccess/"
                f"?client_id={self.client_id}"
                f"&redirect_uri=http://localhost:8123/auth/callback"
                f"&scope=accounts"
                f"&product=web"
            )
            
            return await self.async_step_auth_code()
        
        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "docs_url": "https://github.com/max246/hacs-ctrader/wiki"
            },
        )
    
    async def async_step_auth_code(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle authorization code exchange."""
        errors: Dict[str, str] = {}
        
        if user_input is not None:
            auth_code = user_input["authorization_code"]
            
            # Exchange code for tokens
            token_response = await exchange_authorization_code(
                client_id=self.client_id,
                client_secret=self.client_secret,
                authorization_code=auth_code,
            )
            
            if not token_response or "accessToken" not in token_response:
                errors["base"] = "invalid_auth"
            else:
                # Prepare data with tokens from response
                config_data = {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "account_id": self.account_id,
                    "access_token": token_response["accessToken"],
                    "refresh_token": token_response.get("refreshToken", ""),
                }
                
                # Validate tokens work
                try:
                    await validate_tokens(self.hass, config_data)
                except InvalidAuth:
                    errors["base"] = "invalid_auth"
                else:
                    return self.async_create_entry(
                        title=f"cTrader Account {self.account_id}",
                        data=config_data,
                    )
        
        return self.async_show_form(
            step_id="auth_code",
            data_schema=STEP_AUTH_CODE_SCHEMA,
            errors=errors,
            description_placeholders={
                "auth_uri": self.auth_uri,
            },
        )


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
