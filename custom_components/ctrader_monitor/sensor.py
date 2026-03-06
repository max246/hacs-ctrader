"""Sensors for cTrader Monitor."""
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CURRENCY_DOLLAR
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up cTrader sensors."""
    
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    account_id = config_entry.data.get("account_id")
    
    entities = [
        CTraderBalanceSensor(coordinator, account_id),
        CTraderEquitySensor(coordinator, account_id),
        CTraderMarginUsedSensor(coordinator, account_id),
        CTraderOpenTradesCountSensor(coordinator, account_id),
        CTraderClosedTradesSensor(coordinator, account_id),
    ]
    
    async_add_entities(entities)


class CTraderBalanceSensor(CoordinatorEntity, SensorEntity):
    """Sensor for account balance."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:cash"

    def __init__(self, coordinator, account_id: str):
        """Initialize sensor."""
        super().__init__(coordinator)
        self.account_id = account_id
        self._attr_unique_id = f"ctrader_{account_id}_balance"
        self._attr_name = "cTrader Balance"
        self._attr_native_unit_of_measurement = "USD"

    @property
    def native_value(self):
        """Return the balance."""
        if not self.coordinator.data:
            return None
        balance = self.coordinator.data.get("balance")
        if balance:
            return round(balance.get("balance", 0), 2)
        return None

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra attributes."""
        return {"last_updated": self.coordinator.last_update_success}


class CTraderEquitySensor(CoordinatorEntity, SensorEntity):
    """Sensor for account equity."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:trending-up"

    def __init__(self, coordinator, account_id: str):
        """Initialize sensor."""
        super().__init__(coordinator)
        self.account_id = account_id
        self._attr_unique_id = f"ctrader_{account_id}_equity"
        self._attr_name = "cTrader Equity"
        self._attr_native_unit_of_measurement = "USD"

    @property
    def native_value(self):
        """Return the equity."""
        if not self.coordinator.data:
            return None
        balance = self.coordinator.data.get("balance")
        if balance:
            return round(balance.get("equity", 0), 2)
        return None


class CTraderMarginUsedSensor(CoordinatorEntity, SensorEntity):
    """Sensor for margin used."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:percent"

    def __init__(self, coordinator, account_id: str):
        """Initialize sensor."""
        super().__init__(coordinator)
        self.account_id = account_id
        self._attr_unique_id = f"ctrader_{account_id}_margin_used"
        self._attr_name = "cTrader Margin Used"
        self._attr_native_unit_of_measurement = "USD"

    @property
    def native_value(self):
        """Return margin used."""
        if not self.coordinator.data:
            return None
        balance = self.coordinator.data.get("balance")
        if balance:
            return round(balance.get("margin_used", 0), 2)
        return None


class CTraderOpenTradesCountSensor(CoordinatorEntity, SensorEntity):
    """Sensor for count of open trades."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:chart-line"

    def __init__(self, coordinator, account_id: str):
        """Initialize sensor."""
        super().__init__(coordinator)
        self.account_id = account_id
        self._attr_unique_id = f"ctrader_{account_id}_open_trades"
        self._attr_name = "cTrader Open Trades"

    @property
    def native_value(self):
        """Return count of open trades."""
        if not self.coordinator.data:
            return None
        return len(self.coordinator.data.get("open_trades", []))

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra attributes with open trade details."""
        if not self.coordinator.data:
            return {"last_updated": self.coordinator.last_update_success}
        return {
            "open_trades": self.coordinator.data.get("open_trades", []),
            "last_updated": self.coordinator.last_update_success,
        }


class CTraderClosedTradesSensor(CoordinatorEntity, SensorEntity):
    """Sensor for recent closed trades info."""

    _attr_icon = "mdi:history"

    def __init__(self, coordinator, account_id: str):
        """Initialize sensor."""
        super().__init__(coordinator)
        self.account_id = account_id
        self._attr_unique_id = f"ctrader_{account_id}_closed_trades"
        self._attr_name = "cTrader Recent Closed Trades"

    @property
    def native_value(self) -> str:
        """Return recent closed trades summary."""
        if not self.coordinator.data:
            return None
        closed_trades = self.coordinator.data.get("closed_trades", [])
        return f"{len(closed_trades)} recent"

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra attributes with trade details."""
        if not self.coordinator.data:
            return {"last_updated": self.coordinator.last_update_success}
        closed_trades = self.coordinator.data.get("closed_trades", [])
        return {
            "last_closed_trades": closed_trades[:5],
            "last_updated": self.coordinator.last_update_success,
        }
