"""Media player entity exposing MiniDSP volume/mute for dashboard volume cards."""

from __future__ import annotations

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import MiniDSPCoordinator, MiniDSPDeviceInfo
from .entity import MiniDSPEntity

_VOLUME_MIN = -127.0
_VOLUME_MAX = 0.0
_VOLUME_STEP_DB = 0.5                          # dB per explicit up/down press
_VOLUME_STEP = _VOLUME_STEP_DB / (_VOLUME_MAX - _VOLUME_MIN)  # ≈ 0.004 on 0–1 scale


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: MiniDSPCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        MiniDSPMediaPlayer(coordinator, device) for device in coordinator.devices
    )


class MiniDSPMediaPlayer(MiniDSPEntity, MediaPlayerEntity):
    """Minimal media player that exposes volume and mute for dashboard cards.

    State is always ON — this is a preamp, not a media source.
    Volume is mapped linearly: -127 dB → 0.0, 0 dB → 1.0.
    """

    _attr_name = "Volume Control"
    _attr_icon = "mdi:amplifier"
    _attr_volume_step = _VOLUME_STEP  # tells cards how big each step is
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_STEP
    )

    def __init__(self, coordinator: MiniDSPCoordinator, device: MiniDSPDeviceInfo) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device.unique_id}_media_player"

    @property
    def state(self) -> MediaPlayerState:
        return MediaPlayerState.ON

    @property
    def volume_level(self) -> float | None:
        db = self._state.volume
        if db is None:
            return None
        return (db - _VOLUME_MIN) / (_VOLUME_MAX - _VOLUME_MIN)

    @property
    def is_volume_muted(self) -> bool | None:
        return self._state.mute

    async def async_set_volume_level(self, volume: float) -> None:
        current_level = self.volume_level
        if current_level is not None and abs(volume - current_level) <= 0.06:
            # Small delta → treat as a button press (card hardcodes ±0.05).
            # Apply a fixed dB step instead of the 6 dB jump the linear
            # mapping would produce on a 127 dB range.
            step = _VOLUME_STEP_DB if volume > current_level else -_VOLUME_STEP_DB
            db = max(_VOLUME_MIN, min(_VOLUME_MAX, (self._state.volume or _VOLUME_MIN) + step))
        else:
            # Large delta → slider drag; map linearly across the full range.
            db = round(_VOLUME_MIN + volume * (_VOLUME_MAX - _VOLUME_MIN), 1)
        await self._coordinator.async_set_volume(self._device.index, db)

    async def async_mute_volume(self, mute: bool) -> None:
        await self._coordinator.async_set_mute(self._device.index, mute)

    async def async_volume_up(self) -> None:
        current = self._state.volume or _VOLUME_MIN
        new = min(current + _VOLUME_STEP_DB, _VOLUME_MAX)
        await self._coordinator.async_set_volume(self._device.index, new)

    async def async_volume_down(self) -> None:
        current = self._state.volume or _VOLUME_MAX
        new = max(current - _VOLUME_STEP_DB, _VOLUME_MIN)
        await self._coordinator.async_set_volume(self._device.index, new)
