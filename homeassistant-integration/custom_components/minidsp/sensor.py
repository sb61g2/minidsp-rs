"""Input and output level sensors (updated via WebSocket at ~4 Hz)."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry

try:
    from homeassistant.components.sensor import SensorDeviceClass
    _SENSOR_DEVICE_CLASS = SensorDeviceClass.SOUND_PRESSURE
except (ImportError, AttributeError):
    _SENSOR_DEVICE_CLASS = None

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import MiniDSPCoordinator, MiniDSPDeviceInfo
from .entity import MiniDSPEntity

# Level sensors are off by default — they update at ~4 Hz which can stress
# the HA database. Enable per-entity from the UI if you want them recorded.
_LEVELS_ENABLED_DEFAULT = False


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: MiniDSPCoordinator = hass.data[DOMAIN][entry.entry_id]

    # We don't know the channel counts until the first WebSocket frame arrives.
    # Register a one-shot listener per device that creates sensors on first data.
    for device in coordinator.devices:
        _LevelSensorFactory(hass, coordinator, device, async_add_entities)


class _LevelSensorFactory:
    """Waits for the first state update then creates the level sensor entities."""

    def __init__(self, hass, coordinator, device, async_add_entities):
        self._hass = hass
        self._coordinator = coordinator
        self._device = device
        self._async_add_entities = async_add_entities
        self._created = False
        self._unsub = coordinator.async_add_listener(device.index, self._on_update)

    def _on_update(self) -> None:
        if self._created:
            return
        state = self._coordinator.get_state(self._device.index)
        if not state.input_levels and not state.output_levels:
            return  # levels not populated yet

        self._created = True
        self._unsub()  # one-shot

        entities: list[MiniDSPLevelSensor] = [
            MiniDSPLevelSensor(self._coordinator, self._device, "input", i)
            for i in range(len(state.input_levels))
        ] + [
            MiniDSPLevelSensor(self._coordinator, self._device, "output", i)
            for i in range(len(state.output_levels))
        ]
        self._async_add_entities(entities)


class MiniDSPLevelSensor(MiniDSPEntity, SensorEntity):
    """Signal level in dBFS for one input or output channel."""

    _attr_device_class = _SENSOR_DEVICE_CLASS
    _attr_native_unit_of_measurement = "dB"
    _attr_suggested_display_precision = 1
    _attr_entity_registry_enabled_default = _LEVELS_ENABLED_DEFAULT

    def __init__(
        self,
        coordinator: MiniDSPCoordinator,
        device: MiniDSPDeviceInfo,
        channel_type: str,  # "input" or "output"
        index: int,
    ) -> None:
        super().__init__(coordinator, device)
        self._channel_type = channel_type
        self._index = index
        self._attr_unique_id = f"{device.unique_id}_{channel_type}_level_{index}"
        self._attr_name = f"{channel_type.capitalize()} {index + 1} Level"
        self._attr_icon = (
            "mdi:microphone" if channel_type == "input" else "mdi:speaker"
        )

    @property
    def native_value(self) -> float | None:
        state = self._state
        levels = (
            state.input_levels
            if self._channel_type == "input"
            else state.output_levels
        )
        if self._index < len(levels):
            return round(levels[self._index], 1)
        return None
