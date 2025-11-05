"""Pushover Listener integration for Home Assistant."""

import asyncio
import logging
from typing import Any, TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
# Imports for .pushover_listener and .api are MOVED below

_LOGGER = logging.getLogger(__name__)

# --- CRITICAL FIX 1: This line tells HA to load the sensor platform ---
PLATFORMS: list[str] = ["sensor"]

# --- This block is for type hints only and is not run by Python ---
if TYPE_CHECKING:
    from .pushover_listener import PushoverClient
    from .api import InvalidAuthError


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Pushover Listener from a config entry."""
    
    _LOGGER.info("Pushover Init: Starting async_setup_entry")
    
    # --- IMPORT INSIDE ASYNC FUNCTION (fixes blocking call) ---
    from .pushover_listener import PushoverClient
    from .api import InvalidAuthError

    hass.data.setdefault(DOMAIN, {})

    email = entry.data["email"]
    password = entry.data["password"]
    device_name = entry.data["device_name"]

    # --- START: REGISTER THE DEVICE ---
    _LOGGER.info("Pushover Init: Registering device for %s", email)
    device_registry = dr.async_get(hass)

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=f"Pushover ({device_name})",
        manufacturer="Pushover Listener",
        model=f"Listener ({email})",
        sw_version=entry.version, 
    )
    _LOGGER.info("Pushover Init: Device registration complete for %s", email)
    # --- END: REGISTER THE DEVICE ---

    client = PushoverClient(hass, email, password, device_name, entry.entry_id)
    _LOGGER.info("Pushover Init: Client initialized for %s. Calling client.start()", email)

    try:
        await asyncio.wait_for(client.start(), timeout=30)
    except InvalidAuthError:
        _LOGGER.error("Pushover Init: Authentication failed for %s. Setup cannot continue.", email)
        return False
    except TimeoutError:
        _LOGGER.error("Pushover Init: Client setup timed out for %s. Setup cannot continue.", email)
        return False
    except Exception as err:
        _LOGGER.error("Pushover Init: Unexpected error during client.start() for %s: %s. Setup cannot continue.", email, err, exc_info=True)
        return False

    _LOGGER.info("Pushover Init: client.start() succeeded for %s. Creating listen task.", email)
    listen_task = asyncio.create_task(client.listen())

    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "task": listen_task,
    }

    _LOGGER.info("Pushover Init: Forwarding setup to sensor platform for %s...", email)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.info("Pushover Init: Sensor setup forwarded for %s.", email)

    _LOGGER.info("Pushover Listener for %s started", email)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    
    from .pushover_listener import PushoverClient

    _LOGGER.info("Unloading Pushover Listener for %s", entry.data["email"])

    # --- Unload the platforms FIRST ---
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    entry_data = hass.data[DOMAIN].pop(entry.entry_id, None)

    if entry_data and unloaded:
        client: PushoverClient = entry_data["client"]
        task: asyncio.Task = entry_data["task"]

        await client.stop()

        try:
            await asyncio.wait_for(task, timeout=10)
        except asyncio.CancelledError:
            _LOGGER.debug("Listener task successfully cancelled.")
        except TimeoutError:
            _LOGGER.warning("Listener task did not stop in time.")

    # Return the unload status
    return unloaded