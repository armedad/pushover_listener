"""Config flow for Pushover Listener."""

import logging
import re
from typing import Any, TYPE_CHECKING

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .api import InvalidAuthError


class PushoverListenerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Pushover Listener."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        
        from .api import InvalidAuthError, async_validate_credentials

        if user_input is not None:
            device_name = user_input["device_name"]
            
            if not (1 <= len(device_name) <= 25):
                errors["device_name"] = "invalid_length"
            elif not re.match(r"^[a-zA-Z0-9_-]*$", device_name):
                errors["device_name"] = "invalid_chars"
            
            if not errors:
                try:
                    await async_validate_credentials(
                        self.hass, user_input["email"], user_input["password"]
                    )
                except InvalidAuthError:
                    errors["base"] = "invalid_auth"
                except Exception:
                    _LOGGER.exception("Unexpected exception")
                    errors["base"] = "unknown"
                else:
                    await self.async_set_unique_id(user_input["email"])
                    self._abort_if_unique_id_configured()
                    
                    return self.async_create_entry(
                        title=user_input["email"], data=user_input
                    )

        data_schema = vol.Schema(
            {
                vol.Required("email"): TextSelector(
                    config=TextSelectorConfig(type=TextSelectorType.EMAIL)
                ),
                vol.Required("password"): TextSelector(
                    config=TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
                vol.Optional("device_name", default="homeassistant"): str,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return PushoverListenerOptionsFlow(config_entry)


class PushoverListenerOptionsFlow(config_entries.OptionsFlow):
    """Handle an options flow for Pushover Listener."""
    
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        email = self.config_entry.data["email"]

        from .api import InvalidAuthError, async_validate_credentials

        if user_input is not None:
            device_name = user_input["device_name"]
            
            if not (1 <= len(device_name) <= 25):
                errors["device_name"] = "invalid_length"
            elif not re.match(r"^[a-zA-Z0-9_-]*$", device_name):
                errors["device_name"] = "invalid_chars"

            if not errors:
                try:
                    await async_validate_credentials(self.hass, email, user_input["password"])
                except InvalidAuthError:
                    errors["base"] = "invalid_auth"
                except Exception:
                    _LOGGER.exception("Unexpected exception")
                    errors["base"] = "unknown"
                else:
                    new_data = self.config_entry.data.copy()
                    new_data.update(user_input)
                    
                    self.hass.config_entries.async_update_entry(
                        self.config_entry, data=new_data
                    )
                    return self.async_create_entry(title="", data=None)
            
        data_schema = vol.Schema(
            {
                vol.Required(
                    "password", default=self.config_entry.data.get("password")
                ): TextSelector(
                    config=TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
                vol.Optional(
                    "device_name", default=self.config_entry.data.get("device_name")
                ): str,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={"email": email}
        )