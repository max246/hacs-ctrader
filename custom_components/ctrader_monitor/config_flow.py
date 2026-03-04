"""Config flow for cTrader Monitor."""
import logging
from typing import Any, Dict, Optional

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.network import get_url

from .api import CTraderAPI

_LOGGER = logging.getLogger(__name__)

DOMAIN = "ctrader_monitor"
OAUTH_CALLBACK_PATH = "/auth/external/callback"


def build_redirect_uri(hass) -> str:
    """Build the redirect URI from HA's own URL."""
    try:
        ha_url = get_url(hass, allow_internal=True, allow_ip=True)
        return f"{ha_url.rstrip('/')}{OAUTH_CALLBACK_PATH}"
    except Exception:
        return f"http://localhost:8123{OAUTH_CALLBACK_PATH}"


async def exchange_authorization_code(
    client_id: str,
    client_secret: str,
    authorization_code: str,
    redirect_uri: str,
) -> Optional[Dict[str, Any]]:
    """Exchange authorization code for access and refresh tokens."""
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
                "https://openapi.ctrader.com/apps/token",
                params=params,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()
                if resp.status == 200 and "accessToken" in data:
                    return data
                _LOGGER.error(f"Token exchange failed: {resp.status} — {data}")
                return None
    except Exception as e:
        _LOGGER.error(f"Token exchange error: {e}")
        return None


async def validate_tokens(hass, data: dict) -> None:
    """Validate tokens work by fetching account balance."""
    api = CTraderAPI(
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        account_id=data["account_id"],
        client_id=data["client_id"],
        client_secret=data["client_secret"],
    )
    if await api.async_get_balance() is None:
        raise InvalidAuth


class CTraderConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for cTrader Monitor."""

    VERSION = 2

    def __init__(self):
        super().__init__()
        self.client_id: Optional[str] = None
        self.client_secret: Optional[str] = None
        self.account_id: Optional[str] = None
        self.redirect_uri: Optional[str] = None

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Step 1: show redirect URI, collect app credentials."""
        errors: Dict[str, str] = {}

        self.redirect_uri = build_redirect_uri(self.hass)

        if user_input is not None:
            self.client_id = user_input["client_id"]
            self.client_secret = user_input["client_secret"]
            self.account_id = user_input["account_id"]
            return await self.async_step_auth()

        schema = vol.Schema(
            {
                vol.Required("client_id"): str,
                vol.Required("client_secret"): str,
                vol.Required("account_id"): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={"redirect_uri": self.redirect_uri},
        )

    async def async_step_auth(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Step 2: open cTrader authorization page via external step."""
        auth_uri = (
            f"https://id.ctrader.com/my/settings/openapi/grantingaccess/"
            f"?client_id={self.client_id}"
            f"&redirect_uri={self.redirect_uri}"
            f"&scope=accounts"
            f"&product=web"
        )
        return self.async_external_step(step_id="auth", url=auth_uri)

    async def async_step_auth_callback(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Step 3: HA catches the OAuth redirect, exchange code for tokens."""
        code = (user_input or {}).get("code")

        if not code:
            _LOGGER.error(f"No code in OAuth callback. user_input={user_input}")
            return self.async_abort(reason="missing_code")

        token_response = await exchange_authorization_code(
            client_id=self.client_id,
            client_secret=self.client_secret,
            authorization_code=code,
            redirect_uri=self.redirect_uri,
        )

        if not token_response:
            return self.async_abort(reason="token_exchange_failed")

        config_data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "account_id": self.account_id,
            "redirect_uri": self.redirect_uri,
            "access_token": token_response["accessToken"],
            "refresh_token": token_response.get("refreshToken", ""),
        }

        try:
            await validate_tokens(self.hass, config_data)
        except InvalidAuth:
            return self.async_abort(reason="invalid_auth")

        return self.async_create_entry(
            title=f"cTrader Account {self.account_id}",
            data=config_data,
        )


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
