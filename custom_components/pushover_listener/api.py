"""API utilities for Pushover Listener."""
import logging
from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

LOGIN_URL = "https://api.pushover.net/1/users/login.json"
_LOGGER = logging.getLogger(__name__)


class InvalidAuthError(Exception):
    """Error to indicate there is invalid auth."""


async def async_validate_credentials(
    hass: HomeAssistant, email: str, password: str
) -> str:
    """Validate credentials and return the secret."""
    session = async_get_clientsession(hass)
    try:
        async with session.post(
            LOGIN_URL,
            data={"email": email, "password": password},
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
            if data["status"] != 1:
                _LOGGER.warning("Pushover login failed: %s", data)
                raise InvalidAuthError
            return data["secret"]
    except ClientError as err:
        _LOGGER.error("Pushover authentication request failed: %s", err)
        raise InvalidAuthError from err