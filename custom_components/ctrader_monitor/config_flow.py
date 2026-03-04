"""Config flow for cTrader Monitor."""
import logging
from typing import Any, Dict, Optional

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
        vol.Required("access_token"): str,
        vol.Required("account_id"): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict) -> dict:
    """Validate the user input allows us to connect."""
    api = CTraderAPI(
        access_token=data["access_token"],
        account_id=data["account_id"],
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

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: Dict[str, str] = {}
        
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception as e:
                _LOGGER.exception(f"Unexpected error: {e}")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)
        
        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "docs_url": "https://github.com/max246/hacs-ctrader/wiki"
            },
        )


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
