"""Thin async SSH wrapper around asyncssh for TP-Link CPE devices."""
from __future__ import annotations

import asyncio
import logging

import asyncssh

from .const import SSH_CONNECT_TIMEOUT, SSH_TIMEOUT

_LOGGER = logging.getLogger(__name__)

# Older CPE firmware (e.g. dropbear 2016) offers only a legacy ssh-dss host key,
# which modern asyncssh rejects by default. List modern algorithms first, then the
# legacy ones, so new and old devices both negotiate. (Host key is not verified —
# known_hosts=None — but it must still be a negotiable algorithm.)
HOST_KEY_ALGS = [
    "ssh-ed25519",
    "ecdsa-sha2-nistp521",
    "ecdsa-sha2-nistp384",
    "ecdsa-sha2-nistp256",
    "rsa-sha2-512",
    "rsa-sha2-256",
    "ssh-rsa",
    "ssh-dss",
]


class TpLinkCpeSshError(Exception):
    """Generic SSH/connection error."""


class TpLinkCpeAuthError(TpLinkCpeSshError):
    """Authentication failed."""


class TpLinkCpeSshClient:
    """Open a fresh connection per command. Robust against stale sessions."""

    def __init__(self, host: str, port: int, username: str, password: str) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password

    def _connect_kwargs(self) -> dict:
        # known_hosts=None: do not verify the host key (Pharos devices regenerate
        # keys on firmware ops; this is the "continue on handshake mismatch" behavior).
        return {
            "port": self._port,
            "username": self._username,
            "password": self._password,
            "known_hosts": None,
            "connect_timeout": SSH_CONNECT_TIMEOUT,
            "server_host_key_algs": HOST_KEY_ALGS,
        }

    async def run(self, command: str, timeout: int = SSH_TIMEOUT) -> str:
        """Run a command and return stdout. Raises typed errors on failure."""
        try:
            async with asyncssh.connect(self._host, **self._connect_kwargs()) as conn:
                result = await asyncio.wait_for(
                    conn.run(command, check=False), timeout=timeout
                )
                return result.stdout or ""
        except asyncssh.PermissionDenied as err:
            raise TpLinkCpeAuthError(f"Authentication failed: {err}") from err
        except (OSError, asyncssh.Error, asyncio.TimeoutError) as err:
            raise TpLinkCpeSshError(f"SSH error to {self._host}: {err}") from err
