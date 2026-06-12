"""Connectivity binary sensor for TP-Link CPE (SSH)."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import parser
from .const import CONF_HOST, CONF_MAC, DEFAULT_MODEL, DOMAIN, MANUFACTURER
from .coordinator import TpLinkCpeConfigEntry, TpLinkCpeCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TpLinkCpeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([TpLinkCpeConnectivity(entry.runtime_data, entry)])


class TpLinkCpeConnectivity(
    CoordinatorEntity[TpLinkCpeCoordinator], BinarySensorEntity
):
    """Reports whether the device is reachable over SSH."""

    _attr_has_entity_name = True
    _attr_translation_key = "connectivity"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(
        self,
        coordinator: TpLinkCpeCoordinator,
        entry: TpLinkCpeConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        mac = entry.data[CONF_MAC]
        self._attr_unique_id = f"{mac}_connectivity"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model=DEFAULT_MODEL,
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data) and self.coordinator.data.get(
            parser.KEY_ONLINE, False
        )
