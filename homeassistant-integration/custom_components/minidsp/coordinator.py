"""WebSocket coordinator — maintains one persistent connection per device."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

RECONNECT_DELAY = 5  # seconds between WebSocket reconnect attempts


@dataclass
class MiniDSPDeviceInfo:
    index: int
    url: str
    hw_id: int
    fw_major: int
    fw_minor: int
    dsp_version: int
    serial: int
    product_name: str

    @property
    def firmware_version(self) -> str:
        return f"{self.fw_major}.{self.fw_minor}"

    @property
    def unique_id(self) -> str:
        return str(self.serial)


@dataclass
class MiniDSPState:
    volume: float | None = None
    mute: bool | None = None
    source: str | None = None
    preset: int | None = None
    dirac: bool | None = None
    input_levels: list[float] = field(default_factory=list)
    output_levels: list[float] = field(default_factory=list)


class MiniDSPCoordinator:
    """Manages connections to the minidspd HTTP/WebSocket API.

    One coordinator per config entry (i.e. per daemon instance).
    One WebSocket connection per discovered device.
    """

    def __init__(self, hass: HomeAssistant, host: str, port: int) -> None:
        self.hass = hass
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.ws_url = f"ws://{host}:{port}"

        self.devices: list[MiniDSPDeviceInfo] = []
        self._states: dict[int, MiniDSPState] = {}
        self._ws_connected: dict[int, bool] = {}
        self._listeners: dict[int, set[Callable[[], None]]] = {}
        self._ws_tasks: dict[int, asyncio.Task] = {}
        self._session: aiohttp.ClientSession | None = None
        self._running = False

    # ------------------------------------------------------------------
    # Setup / teardown
    # ------------------------------------------------------------------

    async def async_setup(self, entry: ConfigEntry) -> None:
        self._session = aiohttp.ClientSession()
        self._running = True
        await self._fetch_devices()
        for device in self.devices:
            self._states[device.index] = MiniDSPState()
            self._ws_tasks[device.index] = entry.async_create_background_task(
                self.hass,
                self._ws_loop(device.index),
                f"minidsp_ws_{device.index}",
            )

    async def async_shutdown(self) -> None:
        self._running = False
        for task in self._ws_tasks.values():
            task.cancel()
        if self._session:
            await self._session.close()
            self._session = None

    # ------------------------------------------------------------------
    # Device discovery
    # ------------------------------------------------------------------

    async def _fetch_devices(self) -> None:
        assert self._session
        async with self._session.get(f"{self.base_url}/devices") as resp:
            resp.raise_for_status()
            data: list[dict] = await resp.json()

        devices = []
        for i, d in enumerate(data):
            product_name = d.get("product_name")
            if product_name is None:
                _LOGGER.warning(
                    "Skipping unidentified device at %s (device identification failed)",
                    d.get("url", "unknown"),
                )
                continue
            v = d.get("version") or {}
            devices.append(
                MiniDSPDeviceInfo(
                    index=i,
                    url=d.get("url", ""),
                    hw_id=v.get("hw_id", 0),
                    fw_major=v.get("fw_major", 0),
                    fw_minor=v.get("fw_minor", 0),
                    dsp_version=v.get("dsp_version", 0),
                    serial=v.get("serial", 0),
                    product_name=product_name,
                )
            )
        self.devices = devices

    # ------------------------------------------------------------------
    # WebSocket loop (one per device)
    # ------------------------------------------------------------------

    async def _ws_loop(self, device_index: int) -> None:
        url = f"{self.ws_url}/devices/{device_index}"
        while self._running:
            try:
                assert self._session
                async with self._session.ws_connect(url, heartbeat=60) as ws:
                    _LOGGER.debug("WebSocket connected for device %d", device_index)
                    self._ws_connected[device_index] = True
                    self._fire_listeners(device_index)
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            self._apply_update(device_index, json.loads(msg.data))
                        elif msg.type in (
                            aiohttp.WSMsgType.CLOSED,
                            aiohttp.WSMsgType.ERROR,
                        ):
                            break
            except asyncio.CancelledError:
                self._ws_connected[device_index] = False
                self._fire_listeners(device_index)
                return
            except Exception as exc:
                _LOGGER.warning(
                    "WebSocket error for device %d: %s — reconnecting in %ds",
                    device_index,
                    exc,
                    RECONNECT_DELAY,
                )
            finally:
                self._ws_connected[device_index] = False
            try:
                await asyncio.sleep(RECONNECT_DELAY)
            except asyncio.CancelledError:
                self._fire_listeners(device_index)
                return
            # Signal unavailable after the grace period so brief reconnects
            # don't flash the entity; if reconnect succeeds on the next
            # iteration this fires False just before the loop sets True,
            # but the gap is sub-millisecond and invisible in the UI.
            self._fire_listeners(device_index)

    def _apply_update(self, device_index: int, data: dict) -> None:
        master = data.get("master", {})
        state = self._states.setdefault(device_index, MiniDSPState())
        if "volume" in master:
            state.volume = master["volume"]
        if "mute" in master:
            state.mute = master["mute"]
        if "source" in master:
            state.source = master["source"]
        if "preset" in master:
            state.preset = master["preset"]
        if "dirac" in master:
            state.dirac = master["dirac"]
        if "input_levels" in data:
            state.input_levels = data["input_levels"]
        if "output_levels" in data:
            state.output_levels = data["output_levels"]

        self._fire_listeners(device_index)

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def _fire_listeners(self, device_index: int) -> None:
        for cb in list(self._listeners.get(device_index, set())):
            cb()

    def is_device_available(self, device_index: int) -> bool:
        return self._ws_connected.get(device_index, False)

    # ------------------------------------------------------------------
    # Listener subscription
    # ------------------------------------------------------------------

    def async_add_listener(
        self, device_index: int, callback: Callable[[], None]
    ) -> Callable[[], None]:
        """Subscribe to state updates. Returns an unsubscribe callable."""
        self._listeners.setdefault(device_index, set()).add(callback)

        def unsubscribe() -> None:
            self._listeners.get(device_index, set()).discard(callback)

        return unsubscribe

    # ------------------------------------------------------------------
    # State access
    # ------------------------------------------------------------------

    def get_state(self, device_index: int) -> MiniDSPState:
        return self._states.get(device_index, MiniDSPState())

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    async def async_set_volume(self, device_index: int, volume: float) -> None:
        await self._post(device_index, {"volume": round(volume, 1)})
        self._patch_state(device_index, volume=round(volume, 1))

    async def async_set_mute(self, device_index: int, mute: bool) -> None:
        await self._post(device_index, {"mute": mute})
        self._patch_state(device_index, mute=mute)

    async def async_set_source(self, device_index: int, source: str) -> None:
        await self._post(device_index, {"source": source})
        self._patch_state(device_index, source=source)

    async def async_set_preset(self, device_index: int, preset: int) -> None:
        await self._post(device_index, {"preset": preset})
        self._patch_state(device_index, preset=preset)

    async def async_set_dirac(self, device_index: int, dirac: bool) -> None:
        await self._post(device_index, {"dirac": dirac})
        self._patch_state(device_index, dirac=dirac)

    def _patch_state(self, device_index: int, **kwargs) -> None:
        """Optimistically update local state after a successful command."""
        state = self._states.get(device_index)
        if state is None:
            return
        for key, value in kwargs.items():
            setattr(state, key, value)
        for cb in list(self._listeners.get(device_index, set())):
            cb()

    async def _post(self, device_index: int, payload: dict) -> None:
        assert self._session
        url = f"{self.base_url}/devices/{device_index}"
        last_exc: Exception | None = None
        for attempt in range(4):
            if attempt:
                await asyncio.sleep(1)
            try:
                async with self._session.post(url, json=payload) as resp:
                    if resp.status < 500:
                        resp.raise_for_status()
                        return
                    body = await resp.text()
                    last_exc = aiohttp.ClientResponseError(
                        resp.request_info, resp.history,
                        status=resp.status, message=body,
                    )
            except aiohttp.ClientResponseError:
                raise
            except Exception as exc:
                last_exc = exc
        raise last_exc  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Connection test (used by config flow)
    # ------------------------------------------------------------------

    @staticmethod
    async def async_test_connection(host: str, port: int) -> list[dict]:
        """Try to reach the daemon and return raw device list. Raises on failure."""
        url = f"http://{host}:{port}/devices"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                resp.raise_for_status()
                return await resp.json()
