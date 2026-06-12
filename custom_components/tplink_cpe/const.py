"""Constants for the TP-Link CPE (SSH) integration."""
from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "tplink_cpe"

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SENSOR,
]

# Config entry keys
CONF_HOST = "host"
CONF_PORT = "port"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_NAME = "name"
CONF_WIFI_IF = "wifi_if"          # detected wireless interface, e.g. "ath0"
CONF_MAC = "mac"                  # device MAC, used as unique_id
CONF_SCAN_INTERVAL = "scan_interval"

# Defaults
DEFAULT_PORT = 22
DEFAULT_SCAN_INTERVAL = 30        # seconds
DEFAULT_WIFI_IF = "ath0"
SSH_TIMEOUT = 20                  # seconds for the data command
SSH_CONNECT_TIMEOUT = 15          # seconds to establish the connection

# Extra interfaces to report throughput for, beyond the detected wifi interface
EXTRA_THROUGHPUT_IFACES = ["eth0"]

# Device info
MANUFACTURER = "TP-Link"
DEFAULT_MODEL = "Pharos CPE"
