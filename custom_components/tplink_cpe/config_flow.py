"""Config flow for TP-Link CPE (SSH)."""
from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback

from . import parser
from .const import (
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    CONF_WIFI_IF,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .ssh_client import TpLinkCpeAuthError, TpLinkCpeSshClient, TpLinkCpeSshError

_LOGGER = logging.getLogger(__name__)


class _NoWireless(Exception):
    """No wireless interface detected."""


async def _validate(data: dict[str, Any]) -> dict[str, str]:
    """Connect, detect the wireless interface and MAC. Returns extra entry data."""
    client = TpLinkCpeSshClient(
        data[CONF_HOST], data[CONF_PORT], data[CONF_USERNAME], data[CONF_PASSWORD]
    )
    iwconfig_all = await client.run("iwconfig", timeout=15)
    ifconfig = await client.run("ifconfig", timeout=15)
    wifi_if = parser.detect_wifi_if(iwconfig_all)
    if not wifi_if:
        raise _NoWireless
    mac = parser.parse_mac(ifconfig)
    return {CONF_WIFI_IF: wifi_if, CONF_MAC: mac or data[CONF_HOST]}


class TpLinkCpeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the UI config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                extra = await _validate(user_input)
            except TpLinkCpeAuthError:
                errors["base"] = "invalid_auth"
            except _NoWireless:
                errors["base"] = "no_wireless"
            except TpLinkCpeSshError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001 - surface a friendly error, log the rest
                _LOGGER.exception("Unexpected error validating CPE connection")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(extra[CONF_MAC])
                self._abort_if_unique_id_configured()
                title = user_input.get(CONF_NAME) or user_input[CONF_HOST]
                return self.async_create_entry(
                    title=title, data={**user_input, **extra}
                )

        schema = vol.Schema(
            {
                vol.Optional(CONF_NAME): str,
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Required(CONF_USERNAME, default="admin"): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            new_data = {**entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]}
            try:
                await _validate(new_data)
            except TpLinkCpeAuthError:
                errors["base"] = "invalid_auth"
            except TpLinkCpeSshError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001 - surface a friendly error, log the rest
                _LOGGER.exception("Unexpected error during reauth")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(entry, data=new_data)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
            description_placeholders={"name": entry.title},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        return TpLinkCpeOptionsFlow()


class TpLinkCpeOptionsFlow(OptionsFlow):
    """Edit the scan interval."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(
                    int, vol.Range(min=10, max=3600)
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
