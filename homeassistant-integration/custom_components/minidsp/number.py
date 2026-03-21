"""Volume number entity."""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfSoundPressureLevel
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import MiniDSPCoordinator
from .entity import MiniDSPEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: MiniDSPCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        MiniDSPVolumeNumber(coordinator, device) for device in coordinator.devices
    )


class MiniDSPVolumeNumber(MiniDSPEntity, NumberEntity):
    """Master volume slider.

    Range: -127 dB (silence) to 0 dB (maximum).
    Step: 0.5 dB — coarse enough for reliable control, fine enough for precision.
    """

    _attr_name = "Volume"
    _attr_device_class = NumberDeviceClass.SOUND_PRESSURE
    _attr_native_unit_of_measurement = UnitOfSoundPressureLevel.DECIBEL
    _attr_native_min_value = -127.0
    _attr_native_max_value = 0.0
    _attr_native_step = 0.5
    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:volume-high"

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device.unique_id}_volume"

    @property
    def native_value(self) -> float | None:
        return self._state.volume

    async def async_set_native_value(self, value: float) -> None:
        await self._coordinator.async_set_volume(self._device.index, value)
