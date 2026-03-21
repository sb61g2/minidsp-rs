"""Mute and Dirac Live switch entities."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import MiniDSPCoordinator, MiniDSPDeviceInfo
from .entity import MiniDSPEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: MiniDSPCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[MiniDSPEntity] = []
    for device in coordinator.devices:
        entities.append(MiniDSPMuteSwitch(coordinator, device))
        entities.append(MiniDSPDiracSwitch(coordinator, device))
    async_add_entities(entities)


class MiniDSPMuteSwitch(MiniDSPEntity, SwitchEntity):
    """Master mute toggle."""

    _attr_name = "Mute"
    _attr_icon = "mdi:volume-off"

    def __init__(self, coordinator: MiniDSPCoordinator, device: MiniDSPDeviceInfo) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device.unique_id}_mute"

    @property
    def is_on(self) -> bool | None:
        return self._state.mute

    async def async_turn_on(self, **kwargs) -> None:
        await self._coordinator.async_set_mute(self._device.index, True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._coordinator.async_set_mute(self._device.index, False)


class MiniDSPDiracSwitch(MiniDSPEntity, SwitchEntity):
    """Dirac Live toggle (only meaningful on devices that support it)."""

    _attr_name = "Dirac Live"
    _attr_icon = "mdi:waveform"
    _attr_entity_registry_enabled_default = False  # hidden by default; enable if needed

    def __init__(self, coordinator: MiniDSPCoordinator, device: MiniDSPDeviceInfo) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device.unique_id}_dirac"

    @property
    def is_on(self) -> bool | None:
        return self._state.dirac

    async def async_turn_on(self, **kwargs) -> None:
        await self._coordinator.async_set_dirac(self._device.index, True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._coordinator.async_set_dirac(self._device.index, False)
