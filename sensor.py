"""Sensor platform for Pushover Listener."""
from __future__ import annotations
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .pushover_listener import PushoverClient

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    # --- WE NEED TO SEE THIS LOG ---
    _LOGGER.info("Pushover Sensor Setup: Starting async_setup_entry for sensor")

    try:
        client: PushoverClient = hass.data[DOMAIN][config_entry.entry_id]["client"]
    except KeyError:
        _LOGGER.error("Pushover Sensor Setup: Could not find client in hass.data. Aborting.")
        return

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, config_entry.entry_id)}
    )

    if not device:
        _LOGGER.error("Pushover Sensor Setup: Could not find matching device in registry. Aborting sensor setup.")
        return
    
    _LOGGER.info("Pushover Sensor Setup: Found device: %s", device.name)

    sensor = PushoverLastMessageSensor(client, device)
    async_add_entities([sensor])
    
    _LOGGER.info("Pushover Sensor Setup: Successfully added sensor entity for %s", device.name)


class PushoverLastMessageSensor(SensorEntity):
    """
    Representation of a sensor that stores the last received Pushover message.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = "Last Message"
    _attr_icon = "mdi:message-text"

    def __init__(self, client: PushoverClient, device: dr.DeviceEntry) -> None:
        """Initialize the sensor."""
        self._client = client
        
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, device.identifiers.copy().pop()[1])}
        )
        self._attr_unique_id = f"{device.id}-last-message"
        
        self._attr_native_value: StateType = None
        self._attr_extra_state_attributes: dict[str, Any] = {}
        _LOGGER.debug("Pushover Sensor (%s): Initialized.", self.unique_id)


    @callback
    def _handle_new_message(self, data: dict[str, Any]) -> None:
        """Handle new message data from the client."""
        _LOGGER.debug("Pushover Sensor (%s): Received new message data.", self.unique_id)
        
        self._attr_native_value = data.get('title', data.get('app', 'New Message'))
        self._attr_extra_state_attributes = data
        
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks when added to HASS."""
        _LOGGER.debug("Pushover Sensor (%s): Added to HASS. Registering callback.", self.unique_id)
        self._client.set_sensor_callback(self._handle_new_message)

    async def async_will_remove_from_hass(self) -> None:
        """Clean up when removed."""
        _LOGGER.debug("Pushover Sensor (%s): Removing from HASS. Unregistering callback.", self.unique_id)
        self._client.set_sensor_callback(None)