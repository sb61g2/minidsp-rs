"""Input source and preset select entities."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, NUM_PRESETS, SOURCE_LABELS, SOURCES_BY_HW_ID
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
        sources = SOURCES_BY_HW_ID.get(device.hw_id)
        if sources:
            entities.append(MiniDSPSourceSelect(coordinator, device, sources))
        entities.append(MiniDSPPresetSelect(coordinator, device))
    async_add_entities(entities)


class MiniDSPSourceSelect(MiniDSPEntity, SelectEntity):
    """Input source selector."""

    _attr_name = "Input Source"
    _attr_icon = "mdi:import"

    def __init__(
        self,
        coordinator: MiniDSPCoordinator,
        device: MiniDSPDeviceInfo,
        sources: list[str],
    ) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device.unique_id}_source"
        self._sources = sources  # e.g. ["analog", "toslink", "spdif", "usb", "hdmi"]
        # Display names for the HA UI
        self._attr_options = [SOURCE_LABELS.get(s, s.capitalize()) for s in sources]

    def _source_to_label(self, source: str) -> str:
        return SOURCE_LABELS.get(source, source.capitalize())

    def _label_to_source(self, label: str) -> str:
        reverse = {v: k for k, v in SOURCE_LABELS.items()}
        return reverse.get(label, label.lower())

    @property
    def current_option(self) -> str | None:
        raw = self._state.source
        if raw is None:
            return None
        return self._source_to_label(raw)

    async def async_select_option(self, option: str) -> None:
        source = self._label_to_source(option)
        await self._coordinator.async_set_source(self._device.index, source)


class MiniDSPPresetSelect(MiniDSPEntity, SelectEntity):
    """Configuration preset selector (Preset 1–4)."""

    _attr_name = "Preset"
    _attr_icon = "mdi:bookmark-outline"
    _attr_options = [f"Preset {i + 1}" for i in range(NUM_PRESETS)]

    def __init__(self, coordinator: MiniDSPCoordinator, device: MiniDSPDeviceInfo) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device.unique_id}_preset"

    @property
    def current_option(self) -> str | None:
        preset = self._state.preset
        if preset is None:
            return None
        return f"Preset {preset + 1}"

    async def async_select_option(self, option: str) -> None:
        # "Preset 1" -> 0, "Preset 2" -> 1, etc.
        index = int(option.split()[-1]) - 1
        await self._coordinator.async_set_preset(self._device.index, index)
