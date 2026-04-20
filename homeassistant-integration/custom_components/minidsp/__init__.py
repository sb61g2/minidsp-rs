"""MiniDSP integration for Home Assistant."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN
from .coordinator import MiniDSPCoordinator

PLATFORMS = [Platform.MEDIA_PLAYER, Platform.NUMBER, Platform.SELECT, Platform.SENSOR, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = MiniDSPCoordinator(
        hass,
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
    )
    try:
        await coordinator.async_setup()
    except Exception as exc:
        await coordinator.async_shutdown()
        raise ConfigEntryNotReady(f"Cannot connect to MiniDSP daemon: {exc}") from exc

    if not coordinator.devices:
        await coordinator.async_shutdown()
        raise ConfigEntryNotReady(
            "MiniDSP daemon is reachable but no devices are identified yet "
            "(device may still be initialising after a power cycle)"
        )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    _remove_stale_devices(hass, entry, coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


def _remove_stale_devices(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: MiniDSPCoordinator
) -> None:
    """Remove ghost devices left by failed product identification.

    When product identification fails the daemon returns serial=0 and
    product_name=null.  Older versions of this integration registered those
    as "MiniDSP None" with unique_id "0".  We remove them unconditionally
    because serial=0 is never a valid real-device identifier.

    Real devices that are temporarily offline are left alone so their history
    and automations survive a power cycle.
    """
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    valid_ids = {(DOMAIN, d.unique_id) for d in coordinator.devices}
    ghost_id = (DOMAIN, "0")

    for device_entry in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        if device_entry.identifiers & valid_ids:
            continue
        # Only eagerly remove ghost entries (serial=0); leave real devices
        # that are merely offline so their state survives a power cycle.
        if ghost_id not in device_entry.identifiers:
            continue
        for entity_entry in er.async_entries_for_device(
            ent_reg, device_entry.id, include_disabled_entities=True
        ):
            ent_reg.async_remove(entity_entry.entity_id)
        dev_reg.async_remove_device(device_entry.id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        coordinator: MiniDSPCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()
    return ok
