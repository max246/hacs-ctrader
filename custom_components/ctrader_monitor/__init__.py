"""cTrader Monitor Integration."""
import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CTraderAPI

_LOGGER = logging.getLogger(__name__)

DOMAIN = "ctrader_monitor"
PLATFORMS = [Platform.SENSOR]
SCAN_INTERVAL = timedelta(minutes=1)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up cTrader Monitor from a config entry."""
    
    api = CTraderAPI(
        access_token=entry.data.get("access_token"),
        refresh_token=entry.data.get("refresh_token"),
        account_id=entry.data.get("account_id"),
        client_id=entry.data.get("client_id"),
        client_secret=entry.data.get("client_secret"),
    )
    
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="cTrader Monitor",
        update_method=api.async_update,
        update_interval=SCAN_INTERVAL,
    )
    
    await coordinator.async_config_entry_first_refresh()
    
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
    }
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok
