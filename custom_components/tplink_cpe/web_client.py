"""Pharos web-API client for rebooting TP-Link CPE devices.

Reboot is NOT possible over SSH (the SSH `admin` account maps to an unprivileged
`guest` user). It goes through the device web API, the same path the web UI's
Reboot button uses:

  1. GET  /data/version.json       -> Set-Cookie: COOKIE=<nonce/session token>
  2. POST /data/version.json       -> encoded = "<user>:" + MD5( MD5(pw).upper() + ":" + cookie ).upper()
                                      body: encoded=<...>&nonce=<cookie>  ; status 0 == success
  3. GET  /data/configReboot.json  -> reboots the device

The session cookie is flagged `Secure`, so a normal cookie jar will not resend it
over HTTP. We therefore manage the cookie manually via the Cookie header.

Tries HTTP :80 first (works on most units), falls back to HTTPS :443 (old TLS +
self-signed cert tolerated) for devices where plain HTTP is disabled.
"""
from __future__ import annotations

import asyncio
import logging
import re
import ssl

import aiohttp

from . import parser

_LOGGER = logging.getLogger(__name__)

_COOKIE_RE = re.compile(r"COOKIE=([0-9a-fA-F]+)")
_STATUS_RE = re.compile(r'"status":\s*(-?\d+)')

# version.json login status codes (from the device web app)
_STATUS_SUCCESS = 0
_STATUS_PASS_ERROR = 1
_STATUS_OTHER_LOGIN = 4  # another admin session is active; must be taken over

_REQUEST_TIMEOUT = 20


class TpLinkCpeWebError(Exception):
    """Web-API error."""


class TpLinkCpeWebAuthError(TpLinkCpeWebError):
    """Web login failed (wrong password)."""


def _build_legacy_ssl_context() -> ssl.SSLContext:
    """SSL context that tolerates the device's old TLS + self-signed cert.

    Uses PROTOCOL_TLS_CLIENT (no default-CA file I/O) so it is safe to build in
    the event loop.
    """
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.minimum_version = ssl.TLSVersion.TLSv1
    try:
        ctx.set_ciphers("DEFAULT@SECLEVEL=0")
    except ssl.SSLError:  # pragma: no cover - depends on OpenSSL build
        pass
    return ctx


class TpLinkCpeWebClient:
    """Reboots a TP-Link CPE device via its Pharos web API."""

    def __init__(self, host: str, username: str, password: str) -> None:
        self._host = host
        self._user = username
        self._pw = password
        self._ssl_ctx: ssl.SSLContext | None = None

    def _encoded(self, nonce: str) -> str:
        return parser.pharos_login_encoded(self._user, self._pw, nonce)

    @staticmethod
    def _status(body: str) -> int | None:
        match = _STATUS_RE.search(body)
        return int(match.group(1)) if match else None

    async def async_reboot(self) -> None:
        """Reboot the device. Raises TpLinkCpeWebError with a clean message."""
        protocol_err: TpLinkCpeWebError | None = None
        for scheme in ("http", "https"):
            try:
                await self._reboot_via(scheme)
                _LOGGER.debug("CPE %s reboot issued via %s", self._host, scheme)
                return
            except TpLinkCpeWebAuthError:
                raise  # wrong password — the other scheme won't help
            except TpLinkCpeWebError as err:
                # Connected, but the web flow failed (login status, missing cookie).
                # This is a meaningful message worth surfacing.
                _LOGGER.debug("CPE %s reboot via %s failed: %s", self._host, scheme, err)
                protocol_err = err
            except (aiohttp.ClientError, OSError, asyncio.TimeoutError) as err:
                # Could not connect on this scheme — log details, try the next one.
                _LOGGER.debug("CPE %s cannot connect via %s: %s", self._host, scheme, err)
        if protocol_err is not None:
            raise protocol_err
        raise TpLinkCpeWebError(
            f"could not reach {self._host} — the device is offline or its web UI is not responding"
        )

    async def _reboot_via(self, scheme: str) -> None:
        base = f"{scheme}://{self._host}"
        if scheme == "https":
            if self._ssl_ctx is None:
                self._ssl_ctx = _build_legacy_ssl_context()
            ssl_arg: ssl.SSLContext | bool = self._ssl_ctx
        else:
            ssl_arg = False  # ignored for http
        base_headers = {"Referer": f"{base}/"}
        timeout = aiohttp.ClientTimeout(total=_REQUEST_TIMEOUT)
        # DummyCookieJar: the device rotates its COOKIE on every response, and on
        # some firmware the cookie is not flagged Secure, so aiohttp's default jar
        # would auto-resend a rotated cookie and clash with our manual Cookie header.
        # We manage the (single, original) session cookie ourselves instead.
        async with aiohttp.ClientSession(
            timeout=timeout, cookie_jar=aiohttp.DummyCookieJar()
        ) as session:
            # 1) obtain session cookie / nonce
            async with session.get(
                f"{base}/data/version.json", headers=base_headers, ssl=ssl_arg
            ) as resp:
                set_cookie = resp.headers.get("Set-Cookie", "")
                await resp.read()
            match = _COOKIE_RE.search(set_cookie)
            if not match:
                raise TpLinkCpeWebError("no session cookie in version.json response")
            cookie = match.group(1)
            auth_headers = {**base_headers, "Cookie": f"COOKIE={cookie}"}

            # 2) login (challenge-response with the cookie as nonce)
            async with session.post(
                f"{base}/data/version.json",
                data={"encoded": self._encoded(cookie), "nonce": cookie},
                headers=auth_headers,
                ssl=ssl_arg,
            ) as resp:
                body = await resp.text()
            status = self._status(body)
            # Single-session devices return otherLogin (4) when a web session is
            # already active (incl. a stale one). Take it over via loginConfirm.json.
            if status == _STATUS_OTHER_LOGIN:
                async with session.get(
                    f"{base}/data/loginConfirm.json", headers=auth_headers, ssl=ssl_arg
                ) as resp:
                    status = self._status(await resp.text())
            if status != _STATUS_SUCCESS:
                if status == _STATUS_PASS_ERROR:
                    raise TpLinkCpeWebAuthError("web login rejected (wrong password)")
                raise TpLinkCpeWebError(f"web login returned status {status}")

            # 3) reboot — device drops the connection right after responding
            try:
                async with session.get(
                    f"{base}/data/configReboot.json", headers=auth_headers, ssl=ssl_arg
                ) as resp:
                    await resp.read()
            except (aiohttp.ClientError, OSError, asyncio.TimeoutError) as err:
                # login succeeded; a dropped connection here means reboot started
                _LOGGER.debug("configReboot.json connection dropped (expected): %s", err)
