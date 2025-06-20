"""Pushover Listener client for Home Assistant."""

import asyncio
import json
import logging
import os
from aiohttp import ClientSession, WSMsgType
import requests
import async_timeout

from homeassistant.core import HomeAssistant

LOGIN_URL = "https://api.pushover.net/1/users/login.json"
REGISTER_URL = "https://api.pushover.net/1/devices.json"
MESSAGES_URL = "https://api.pushover.net/1/messages.json"
DELETE_URL_TEMPLATE = (
    "https://api.pushover.net/1/devices/{device_id}/update_highest_message.json"
)
WEBSOCKET_URL = "wss://client.pushover.net/push"
STORAGE_PATH = ".storage/pushover_listener.json"
PUSHOVER_EVENT = "pushover_event"
_LOGGER = logging.getLogger(__name__)

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
        self._running = True

    def _get_storage_path(self) -> str:
        """Return the full path to the local storage file for the device ID."""
        return os.path.join(self.hass.config.path(STORAGE_PATH))

    async def load_cached_device_id(self):
        """Try to load previously saved device ID from disk."""
        try:
            path = self._get_storage_path()

            def read_device_id():
                with open(path) as f:
                    return json.load(f).get("device_id")

            return await self.hass.async_add_executor_job(read_device_id)
        except Exception:
            return None

    async def save_device_id(self, device_id):
        """Persist the device ID to disk."""
        try:
            path = self._get_storage_path()

            def write_device_id():
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w") as f:
                    json.dump({"device_id": device_id}, f)

            await self.hass.async_add_executor_job(write_device_id)
        except Exception as err:
            _LOGGER.warning("Failed to save device_id: %s", err)

    async def start(self):
        """Perform login, device registration (if needed), and discard old messages."""
        await self.authenticate()
        self.device_id = await self.load_cached_device_id()
        if not self.device_id:
            await self.register_device()
            await self.save_device_id(self.device_id)
        await self.download_and_discard_old_messages()

    async def authenticate(self):
        """Authenticate with Pushover to retrieve a session secret."""
        _LOGGER.info("Authenticating with Pushover...")
        resp = await self.hass.async_add_executor_job(
            requests.post,
            LOGIN_URL,
            None,
            {"email": self.email, "password": self.password},
        )
        data = resp.json()
        if data["status"] != 1:
            raise RuntimeError(f"Pushover login failed: {data}")
        self.secret = data["secret"]
        _LOGGER.info("Authentication successful.")

    async def register_device(self):
        """Register this client instance as a Pushover Open Client device."""
        _LOGGER.info("Registering Open Client device...")
        resp = await self.hass.async_add_executor_job(
            requests.post,
            REGISTER_URL,
            None,
            {"secret": self.secret, "name": self.device_name, "os": "O"},
        )
        data = resp.json()
        if data["status"] != 1:
            raise RuntimeError(f"Device registration failed: {data}")
        self.device_id = data["id"]
        _LOGGER.info("Registered device: %s", self.device_id)

    async def download_and_discard_old_messages(self):
        """Check for old queued messages and discard them to start fresh."""
        _LOGGER.info("Checking for old messages to discard...")
        resp = await self.hass.async_add_executor_job(
            lambda: requests.get(
                MESSAGES_URL,
                params={"secret": self.secret, "device_id": self.device_id},
            )
        )
        messages = resp.json().get("messages", [])
        if not messages:
            return
        max_id = max(int(m["id"]) for m in messages)
        _LOGGER.info("Discarding %d old messages...", len(messages))
        await self.delete_messages_up_to(max_id)

    async def delete_messages_up_to(self, max_id):
        """Tell Pushover to delete all messages up to a specific ID."""
        await self.hass.async_add_executor_job(
            lambda: requests.post(
                DELETE_URL_TEMPLATE.format(device_id=self.device_id),
                data={"secret": self.secret, "message": max_id},
            )
        )

    async def listen(self):
        """Maintain a persistent connection to Pushover and process new push events."""
        _LOGGER.info("Starting persistent WebSocket listener (binary frame expected).")
        while self._running:
            try:
                async with ClientSession() as session:
                    async with session.ws_connect(WEBSOCKET_URL) as ws:
                        login_str = f"login:{self.device_id}:{self.secret}\n"
                        await ws.send_str(login_str)
                        _LOGGER.info("WebSocket connection established.")

                        async for msg in ws:
                            if msg.type == WSMsgType.BINARY:
                                _LOGGER.info("WebSocket binary frame received: %s", msg.data)
                                if msg.data == b"!":
                                    await asyncio.sleep(0.5)
                                    await self.fetch_and_fire()
                                elif msg.data == b"#":
                                    continue
                                elif msg.data in (b"R", b"E", b"A"):
                                    _LOGGER.warning(
                                        "Received binary control frame '%s', reconnecting...", msg.data
                                    )
                                    break
                            elif msg.type == WSMsgType.ERROR:
                                _LOGGER.error("WebSocket error: %s", msg)
                                break
            except Exception as e:
                _LOGGER.error("WebSocket connection failed: %s", e)
                await asyncio.sleep(10)

    async def fetch_and_fire(self):
        """Fetch any new messages and emit Home Assistant events for each."""
        try:
            resp = await self.hass.async_add_executor_job(
                lambda: requests.get(
                    MESSAGES_URL,
                    params={"secret": self.secret, "device_id": self.device_id},
                )
            )
            data = resp.json()
            messages = data.get("messages", [])
            for msg in messages:
                enriched = self.unpack_json_payload(msg)
                _LOGGER.info("Firing Home Assistant event for message: %s", enriched)
                self.hass.bus.async_fire(PUSHOVER_EVENT, enriched)
            if messages:
                max_id = max(int(m["id"]) for m in messages)
                await self.delete_messages_up_to(max_id)
        except Exception as e:
            _LOGGER.error("Failed to fetch messages: %s", e)

    def unpack_json_payload(self, msg):
        """Extract key=value pairs embedded in the message body and merge them into the payload."""
        enriched = dict(msg)
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
