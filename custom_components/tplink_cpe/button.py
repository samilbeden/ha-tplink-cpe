"""Restart button for TP-Link CPE (SSH).

Reboot goes through the device web API (see web_client.py), because the SSH
account is unprivileged and cannot reboot. Pressing the button raises a
persistent notification in Home Assistant (info while rebooting, error on
failure).
"""
from __future__ import annotations

from homeassistant.components import persistent_notification
from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .const import (
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_USERNAME,
    DEFAULT_MODEL,
    DOMAIN,
    MANUFACTURER,
)
from .coordinator import TpLinkCpeConfigEntry, TpLinkCpeCoordinator
from .web_client import TpLinkCpeWebClient, TpLinkCpeWebError

# Auto-dismiss the "rebooting" notification after the device should be back.
_NOTIFY_DISMISS_DELAY = 120


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TpLinkCpeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(
        [
            TpLinkCpeRestartButton(entry),
            TpLinkCpeRefreshButton(entry.runtime_data, entry),
        ]
    )


class TpLinkCpeRefreshButton(ButtonEntity):
    """Triggers an immediate data refresh for the device."""

    _attr_has_entity_name = True
    _attr_translation_key = "refresh"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, coordinator: TpLinkCpeCoordinator, entry: TpLinkCpeConfigEntry
    ) -> None:
        self._coordinator = coordinator
        mac = entry.data[CONF_MAC]
        self._attr_unique_id = f"{mac}_refresh"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model=DEFAULT_MODEL,
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

    async def async_press(self) -> None:
        await self._coordinator.async_request_refresh()


class TpLinkCpeRestartButton(ButtonEntity):
    """Reboots the CPE device via its web API."""

    _attr_has_entity_name = True
    _attr_translation_key = "restart"
    _attr_device_class = ButtonDeviceClass.RESTART

    def __init__(self, entry: TpLinkCpeConfigEntry) -> None:
        self._web = TpLinkCpeWebClient(
            entry.data[CONF_HOST],
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
        )
        self._name = entry.title
        mac = entry.data[CONF_MAC]
        self._notify_id = f"{DOMAIN}_reboot_{mac}"
        self._attr_unique_id = f"{mac}_restart"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model=DEFAULT_MODEL,
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

    async def async_press(self) -> None:
        persistent_notification.async_create(
            self.hass,
            f"**{self._name}** is rebooting… (should be back in about a minute)",
            title="TP-Link CPE",
            notification_id=self._notify_id,
        )
        try:
            await self._web.async_reboot()
        except TpLinkCpeWebError as err:
            persistent_notification.async_create(
                self.hass,
                f"**{self._name}** reboot failed: {err}",
                title="TP-Link CPE",
                notification_id=self._notify_id,
            )
            raise HomeAssistantError(f"CPE reboot failed: {err}") from err

        async_call_later(self.hass, _NOTIFY_DISMISS_DELAY, self._dismiss_notification)

    @callback
    def _dismiss_notification(self, _now) -> None:
        persistent_notification.async_dismiss(self.hass, self._notify_id)
