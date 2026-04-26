"""Shared base entity for all MiniDSP entities."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .coordinator import MiniDSPCoordinator, MiniDSPDeviceInfo, MiniDSPState


class MiniDSPEntity(Entity):
    """Base class that wires an entity to a coordinator device."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self, coordinator: MiniDSPCoordinator, device: MiniDSPDeviceInfo
    ) -> None:
        self._coordinator = coordinator
        self._device = device
        self._unsubscribe: Callable[[], None] | None = None

    # ------------------------------------------------------------------
    # HA lifecycle
    # ------------------------------------------------------------------

    async def async_added_to_hass(self) -> None:
        self._unsubscribe = self._coordinator.async_add_listener(
            self._device.index, self.async_write_ha_state
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._unsubscribe:
            self._unsubscribe()

    # ------------------------------------------------------------------
    # Device registry entry shared by all entities for this device
    # ------------------------------------------------------------------

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.unique_id)},
            name=f"MiniDSP {self._device.product_name}",
            manufacturer="MiniDSP",
            model=self._device.product_name,
            sw_version=self._device.firmware_version,
            serial_number=str(self._device.serial),
        )

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        return self._coordinator.is_device_available(self._device.index)

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    @property
    def _state(self) -> MiniDSPState:
        return self._coordinator.get_state(self._device.index)
