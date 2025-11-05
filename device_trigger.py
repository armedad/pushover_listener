"""Device triggers for Pushover Listener."""
from __future__ import annotations  # <-- This was the SyntaxError fix

from typing import Any

import voluptuous as vol
from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.trigger import TriggerInfo

from .const import DOMAIN, PUSHOVER_EVENT

TRIGGER_TYPES = {
    "all_messages",
    "priority_critical",
    "priority_high",
    "priority_normal",
    "priority_low",
    "custom_level_critical",
    "custom_level_high",
    "custom_level_normal",
    "custom_level_low",
    "custom_type_alert",
}

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
    }
)

async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """List device triggers for Pushover Listener."""
    triggers = []
    for trigger_type in TRIGGER_TYPES:
        triggers.append(
            {
                CONF_PLATFORM: "device",
                CONF_DOMAIN: DOMAIN,
                CONF_DEVICE_ID: device_id,
                CONF_TYPE: trigger_type,
            }
        )
    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: dict[str, Any],
    action: CALLBACK_TYPE,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    
    trigger_type = config[CONF_TYPE]
    event_data = {
        "device_id": config[CONF_DEVICE_ID],
    }

    if trigger_type == "priority_critical":
        event_data["priority"] = 2
    elif trigger_type == "priority_high":
        event_data["priority"] = 1
    elif trigger_type == "priority_normal":
        event_data["priority"] = 0
    elif trigger_type == "priority_low":
        event_data["priority"] = -1
    elif trigger_type == "custom_level_critical":
        event_data["level"] = "critical"
    elif trigger_type == "custom_level_high":
        event_data["level"] = "high"
    elif trigger_type == "custom_level_normal":
        event_data["level"] = "normal"
    elif trigger_type == "custom_level_low":
        event_data["level"] = "low"
    elif trigger_type == "custom_type_alert":
        event_data["type"] = "alert"
        
    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: "event",
            event_trigger.CONF_EVENT_TYPE: PUSHOVER_EVENT,
            event_trigger.CONF_EVENT_DATA: event_data,
        }
    )

    return await event_trigger.async_attach_trigger(
        hass, event_config, action, trigger_info, platform_type="device"
    )