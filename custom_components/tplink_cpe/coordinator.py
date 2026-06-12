"""DataUpdateCoordinator for a single TP-Link CPE device."""
from __future__ import annotations

import logging
import time
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import parser
from .const import (
    CONF_SCAN_INTERVAL,
    CONF_WIFI_IF,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WIFI_IF,
    DOMAIN,
    EXTRA_THROUGHPUT_IFACES,
)
from .ssh_client import TpLinkCpeAuthError, TpLinkCpeSshClient, TpLinkCpeSshError

_LOGGER = logging.getLogger(__name__)

type TpLinkCpeConfigEntry = ConfigEntry["TpLinkCpeCoordinator"]


class TpLinkCpeCoordinator(DataUpdateCoordinator[dict]):
    """Polls one device over SSH and produces the normalized data dict."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: TpLinkCpeConfigEntry,
        client: TpLinkCpeSshClient,
    ) -> None:
        interval = entry.options.get(
            CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {entry.title}",
            update_interval=timedelta(seconds=interval),
        )
        self.client = client
        self.wifi_if = entry.data.get(CONF_WIFI_IF, DEFAULT_WIFI_IF)
        self._throughput_ifaces = [self.wifi_if, *EXTRA_THROUGHPUT_IFACES]
        self._prev_ifaces: dict | None = None
        self._prev_time: float | None = None

    async def _async_update_data(self) -> dict:
        command = parser.build_command(self.wifi_if)
        try:
            raw = await self.client.run(command)
        except TpLinkCpeAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except TpLinkCpeSshError as err:
            # Device unreachable: report offline but keep entities available so the
            # connectivity sensor can flip to "off" instead of going unavailable.
            _LOGGER.debug("Update failed, marking offline: %s", err)
            self._prev_ifaces = None
            self._prev_time = None
            return {parser.KEY_ONLINE: False}

        data = parser.parse_all(raw, self.wifi_if)
        data[parser.KEY_ONLINE] = True
        self._add_throughput(data)
        return data

    def _add_throughput(self, data: dict) -> None:
        now = time.monotonic()
        cur = {
            name: vals
            for name, vals in data.get(parser.KEY_IFACES, {}).items()
            if name in self._throughput_ifaces
        }
        if self._prev_ifaces is not None and self._prev_time is not None:
            dt = now - self._prev_time
            data[parser.KEY_THROUGHPUT] = parser.compute_throughput(
                self._prev_ifaces, cur, dt
            )
        else:
            data[parser.KEY_THROUGHPUT] = {}
        self._prev_ifaces = cur
        self._prev_time = now
