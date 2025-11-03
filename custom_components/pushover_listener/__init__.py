"""Pushover Listener integration for Home Assistant."""

import asyncio
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
# --- UPDATE IMPORTS ---
from .pushover_listener import PushoverClient
from .api import InvalidAuthError

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = []


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Pushover Listener from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    email = entry.data["email"]
    password = entry.data["password"]
    device_name = entry.data["device_name"]

    client = PushoverClient(hass, email, password, device_name)

    try:
        _LOGGER.info("Starting setup for %s", email)
        await asyncio.wait_for(client.start(), timeout=30)
    except InvalidAuthError:
        _LOGGER.error("Authentication failed for %s. Please update credentials.", email)
        return False
    except TimeoutError:
        _LOGGER.error("Pushover client setup for %s timed out", email)
        return False
    except Exception as err:
        _LOGGER.error("Pushover client setup for %s failed: %s", email, err)
        return False

    listen_task = asyncio.create_task(client.listen())

    # Store client and task to be able to stop them later
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "task": listen_task,
    }

    _LOGGER.info("Pushover Listener for %s started", email)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Pushover Listener for %s", entry.data["email"])

    # Retrieve the client and task
    entry_data = hass.data[DOMAIN].pop(entry.entry_id, None)

    if entry_data:
        client: PushoverClient = entry_data["client"]
        task: asyncio.Task = entry_data["task"]

        # Stop the client (which cancels the task)
        await client.stop()

        # Wait for the task to fully cancel
        try:
            await asyncio.wait_for(task, timeout=10)
        except asyncio.CancelledError:
            _LOGGER.debug("Listener task successfully cancelled.")
        except TimeoutError:
            _LOGGER.warning("Listener task did not stop in time.")

    return True