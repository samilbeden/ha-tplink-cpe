"""The TP-Link CPE (SSH) integration."""
from __future__ import annotations

from homeassistant.core import HomeAssistant

from .const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    PLATFORMS,
)
from .coordinator import TpLinkCpeConfigEntry, TpLinkCpeCoordinator
from .ssh_client import TpLinkCpeSshClient


async def async_setup_entry(hass: HomeAssistant, entry: TpLinkCpeConfigEntry) -> bool:
    """Set up TP-Link CPE from a config entry."""
    client = TpLinkCpeSshClient(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )
    coordinator = TpLinkCpeCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TpLinkCpeConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload(hass: HomeAssistant, entry: TpLinkCpeConfigEntry) -> None:
    """Reload when options change (e.g. scan interval)."""
    await hass.config_entries.async_reload(entry.entry_id)
