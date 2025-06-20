"""Pushover Listener integration for Home Assistant."""

import asyncio
import logging
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .pushover_listener import PushoverClient

DOMAIN = "pushover_listener"
PUSHOVER_EVENT = "pushover_event"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required("email"): cv.string,
                vol.Required("password"): cv.string,
                vol.Optional("device_name", default="homeassistant"): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the Pushover Listener component."""
    conf = config[DOMAIN]
    email = conf["email"]
    password = conf["password"]
    device_name = conf.get("device_name", "homeassistant")

    client = PushoverClient(hass, email, password, device_name)
    hass.data[DOMAIN] = client

    try:
        await asyncio.wait_for(client.start(), timeout=30)
    except TimeoutError:
        logging.getLogger(__name__).error("Pushover client setup timed out")
        return False

    asyncio.create_task(client.listen())

    logging.getLogger(__name__).info("Pushover Listener started (async)")
    return True



