"""Pushover Listener client for Home Assistant."""

import asyncio
import json
import logging
import os
from aiohttp import ClientSession, WSMsgType, ClientError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .const import PUSHOVER_EVENT
# --- IMPORT FROM OUR NEW API FILE ---
from .api import InvalidAuthError, async_validate_credentials

# --- MOVED LOGIN_URL TO API.PY ---
REGISTER_URL = "https://api.pushover.net/1/devices.json"
MESSAGES_URL = "https://api.pushover.net/1/messages.json"
DELETE_URL_TEMPLATE = (
    "https://api.pushover.net/1/devices/{device_id}/update_highest_message.json"
)
WEBSOCKET_URL = "wss://client.pushover.net/push"

STORAGE_VERSION = 1
STORAGE_KEY_TEMPLATE = "pushover_listener.{device_name}"

_LOGGER = logging.getLogger(__name__)

# Constants for Backoff
INITIAL_RECONNECT_DELAY = 10  # Start with 10 seconds
MAX_RECONNECT_DELAY = 300     # Max 5 minutes (300 seconds)
RECONNECT_FACTOR = 2          # Double the delay each time


# --- THIS CLASS WAS MOVED TO API.PY ---
# class InvalidAuthError(Exception):
#    """Error to indicate there is invalid auth."""


# --- THIS FUNCTION WAS MOVED TO API.PY ---
# async def async_validate_credentials(
# ...
# )


class PushoverClient:
    """Client for interacting with the Pushover Open Client API."""

    def __init__(self, hass: HomeAssistant, email: str, password: str, device_name: str):
        """Initialize the Pushover client."""
        self.hass = hass
        self.email = email
        self.password = password
        self.device_name = device_name
        self.secret = None
        self.device_id = None
        self._running = False
        self._ws_task = None
        self._reconnect_delay = INITIAL_RECONNECT_DELAY

        storage_key = STORAGE_KEY_TEMPLATE.format(
            device_name=self.device_name.replace(" ", "_")
        )
        self._store = Store(hass, STORAGE_VERSION, storage_key)

    async def load_cached_device_id(self) -> str | None:
        """Try to load previously saved device ID from storage helper."""
        data = await self._store.async_load()
        return data.get("device_id") if data else None

    async def save_device_id(self, device_id: str) -> None:
        """Persist the device ID to disk via storage helper."""
        try:
            await self._store.async_save({"device_id": device_id})
        except Exception as err:
            _LOGGER.warning("Failed to save device_id: %s", err)

    async def start(self) -> None:
        """Perform login, device registration (if needed), and discard old messages."""
        self._running = True
        # Use the validation function (now imported)
        self.secret = await async_validate_credentials(
            self.hass, self.email, self.password
        )
        _LOGGER.info("Authentication successful for %s.", self.email)

        self.device_id = await self.load_cached_device_id()
        if not self.device_id:
            await self.register_device()  # This will raise RuntimeError on failure
            await self.save_device_id(self.device_id)
        await self.download_and_discard_old_messages()

    async def stop(self) -> None:
        """Stop the listener."""
        _LOGGER.info("Stopping Pushover listener for %s", self.device_name)
        self._running = False
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                _LOGGER.debug("WebSocket task cancelled.")

    async def register_device(self) -> None:
        """Register this client instance as a Pushover Open Client device."""
        _LOGGER.info("Registering Open Client device %s...", self.device_name)
        session = async_get_clientsession(self.hass)
        try:
            async with session.post(
                REGISTER_URL,
                data={"secret": self.secret, "name": self.device_name, "os": "O"},
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                if data["status"] != 1:
                    raise RuntimeError(f"Device registration failed: {data}")
                self.device_id = data["id"]
                _LOGGER.info("Registered device: %s", self.device_id)
        except ClientError as err:
            _LOGGER.error("Pushover device registration request failed: %s", err)
            raise RuntimeError(
                f"Pushover device registration request failed: {err}"
            ) from err

    async def download_and_discard_old_messages(self) -> None:
        """Check for old queued messages and discard them to start fresh."""
        _LOGGER.info("Checking for old messages to discard...")
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                MESSAGES_URL,
                params={"secret": self.secret, "device_id": self.device_id},
            ) as resp:
                resp.raise_for_status()
                messages = (await resp.json()).get("messages", [])
                if not messages:
                    return
                max_id = max(int(m["id"]) for m in messages)
                _LOGGER.info("Discarding %d old messages...", len(messages))
                await self.delete_messages_up_to(max_id)
        except ClientError as err:
            _LOGGER.warning("Failed to download old messages: %s", err)

    async def delete_messages_up_to(self, max_id: int) -> None:
        """Tell Pushover to delete all messages up to a specific ID."""
        session = async_get_clientsession(self.hass)
        try:
            async with session.post(
                DELETE_URL_TEMPLATE.format(device_id=self.device_id),
                data={"secret": self.secret, "message": max_id},
            ) as resp:
                resp.raise_for_status()
        except ClientError as err:
            _LOGGER.warning("Failed to delete messages: %s", err)

    async def listen(self) -> None:
        """Maintain a persistent connection to Pushover and process new push events."""
        _LOGGER.info("Starting persistent WebSocket listener (binary frame expected).")
        self._ws_task = asyncio.current_task()
        
        while self._running:
            try:
                session = await async_get_clientsession(self.hass).__aenter__()
                async with session.ws_connect(WEBSOCKET_URL) as ws:
                    login_str = f"login:{self.device_id}:{self.secret}\n"
                    await ws.send_str(login_str)
                    _LOGGER.info("WebSocket connection established for %s.", self.device_name)

                    # Reset reconnect delay on successful connection
                    self._reconnect_delay = INITIAL_RECONNECT_DELAY

                    async for msg in ws:
                        if msg.type == WSMsgType.BINARY:
                            _LOGGER.debug("WebSocket binary frame received: %s", msg.data)
                            if msg.data == b"!":
                                await asyncio.sleep(0.5)
                                await self.fetch_and_fire()
                            elif msg.data == b"#":
                                continue  # Keep-alive
                            elif msg.data in (b"R", b"E", "A"):
                                _LOGGER.warning(
                                    "Received binary control frame '%s', reconnecting...",
                                    msg.data,
                                )
                                break  # Break inner loop to reconnect
                        elif msg.type == WSMsgType.ERROR:
                            _LOGGER.error("WebSocket error: %s", msg)
                            break
            except asyncio.CancelledError:
                _LOGGER.info("WebSocket listener task cancelled.")
                raise  # Propagate cancellation
            except (ClientError, Exception) as e:
                _LOGGER.error("WebSocket connection failed: %s", e)
            finally:
                # Ensure the session is always closed if it was opened
                if "session" in locals() and session:
                    await session.__aexit__(None, None, None)
            
            if self._running:
                # Implement exponential backoff
                _LOGGER.info("Waiting %s seconds to reconnect...", self._reconnect_delay)
                await asyncio.sleep(self._reconnect_delay)
                # Increase delay for next time, up to the max
                self._reconnect_delay = min(
                    self._reconnect_delay * RECONNECT_FACTOR, MAX_RECONNECT_DELAY
                )

    async def fetch_and_fire(self) -> None:
        """Fetch any new messages and emit Home Assistant events for each."""
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                MESSAGES_URL,
                params={"secret": self.secret, "device_id": self.device_id},
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                messages = data.get("messages", [])
                for msg in messages:
                    enriched = self._enrich_message_payload(msg)
                    _LOGGER.info("Firing Home Assistant event for message: %s", enriched)
                    self.hass.bus.async_fire(PUSHOVER_EVENT, enriched)
                if messages:
                    max_id = max(int(m["id"]) for m in messages)
                    await self.delete_messages_up_to(max_id)
        except ClientError as e:
            _LOGGER.error("Failed to fetch messages: %s", e)

    def _enrich_message_payload(self, msg: dict) -> dict:
        """Extract key=value pairs embedded in the message body and merge them."""
        enriched = dict(msg)
        enriched["user_email"] = self.email
        enriched["device_name"] = self.device_name
        if "message" in msg:
            lines = msg["message"].split("\n")
            for line in lines:
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip().rstrip("&")
                    value = value.strip().rstrip("&")
                    if key:
                        enriched[key] = value
        return enriched