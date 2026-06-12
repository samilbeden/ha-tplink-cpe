"""Pure parsing helpers for TP-Link CPE SSH output.

NO Home Assistant imports — this module is unit-tested standalone.
"""
from __future__ import annotations

import hashlib
import re

# ── Section markers emitted by build_command() ───────────────────────────────
SEC_SYS = "@@SYS"
SEC_IW = "@@IW"
SEC_STA = "@@STA"
SEC_NET = "@@NET"
SEC_IF = "@@IF"
_MARKERS = {SEC_SYS, SEC_IW, SEC_STA, SEC_NET, SEC_IF}
_BOM = "﻿"  # tolerate a stray UTF-8 BOM at the start of captured output

# ── Data dict keys (shared with sensor.py) ────────────────────────────────────
KEY_ONLINE = "online"
KEY_UPTIME = "uptime_seconds"
KEY_LOAD_1 = "load_1m"
KEY_LOAD_5 = "load_5m"
KEY_LOAD_15 = "load_15m"
KEY_MEM_TOTAL = "mem_total_kb"
KEY_MEM_USED = "mem_used_kb"
KEY_MEM_PCT = "mem_used_percent"
KEY_ESSID = "essid"
KEY_MODE = "mode"
KEY_FREQ = "frequency_ghz"
KEY_CHANNEL = "channel"
KEY_BITRATE = "bit_rate_mbps"
KEY_TXPOWER = "tx_power_dbm"
KEY_SIGNAL = "signal_dbm"
KEY_NOISE = "noise_dbm"
KEY_QUALITY = "link_quality_percent"
KEY_CLIENTS = "connected_clients"
KEY_RSSI_AVG = "avg_client_rssi"
KEY_RSSI_MIN = "min_client_rssi"
KEY_IFACES = "interfaces"
KEY_MAC = "mac"
KEY_THROUGHPUT = "throughput"

_MAC_RE = re.compile(r"^[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5}$")


def build_command(wifi_if: str) -> str:
    """Build the single combined data-collection command."""
    return (
        f"echo {SEC_SYS}; cat /proc/uptime; cat /proc/loadavg; free; "
        f"echo {SEC_IW}; iwconfig {wifi_if}; "
        f"echo {SEC_STA}; wlanconfig {wifi_if} list sta; "
        f"echo {SEC_NET}; cat /proc/net/dev; "
        f"echo {SEC_IF}; ifconfig"
    )


def _split_sections(raw: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current: str | None = None
    buf: list[str] = []
    for line in raw.lstrip(_BOM).splitlines():
        if line.strip() in _MARKERS:
            if current is not None:
                sections[current] = "\n".join(buf)
            current = line.strip()
            buf = []
        elif current is not None:
            buf.append(line)
    if current is not None:
        sections[current] = "\n".join(buf)
    return sections


def _freq_ghz_to_channel(ghz: float) -> int | None:
    mhz = round(ghz * 1000)
    if mhz == 2484:
        return 14
    if 2412 <= mhz <= 2472:
        return (mhz - 2407) // 5
    if 5000 <= mhz <= 5900:
        return (mhz - 5000) // 5
    return None


def parse_sys(text: str) -> dict:
    """Parse the combined uptime + loadavg + free block."""
    out: dict = {}
    m = re.search(r"^\s*([\d.]+)\s+[\d.]+\s*$", text, re.M)
    if m:
        out[KEY_UPTIME] = float(m.group(1))
    m = re.search(r"^\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+\d+/\d+\s+\d+", text, re.M)
    if m:
        out[KEY_LOAD_1] = float(m.group(1))
        out[KEY_LOAD_5] = float(m.group(2))
        out[KEY_LOAD_15] = float(m.group(3))
    m = re.search(r"^\s*Mem:\s+(\d+)\s+(\d+)", text, re.M)
    if m:
        total, used = int(m.group(1)), int(m.group(2))
        out[KEY_MEM_TOTAL] = total
        out[KEY_MEM_USED] = used
        if total:
            out[KEY_MEM_PCT] = round(used / total * 100, 1)
    return out


def parse_iwconfig(text: str) -> dict:
    """Parse `iwconfig <iface>` output for one wireless interface."""
    out: dict = {}

    def grab(pattern: str, conv):
        m = re.search(pattern, text)
        if not m:
            return None
        try:
            return conv(m.group(1))
        except ValueError:
            return None

    essid = grab(r'ESSID:"([^"]*)"', str)
    if essid is not None:
        out[KEY_ESSID] = essid
    mode = grab(r"Mode:(\S+)", str)
    if mode is not None:
        out[KEY_MODE] = mode
    freq = grab(r"Frequency:([\d.]+) ?GHz", float)
    if freq is not None:
        out[KEY_FREQ] = freq
        ch = _freq_ghz_to_channel(freq)
        if ch is not None:
            out[KEY_CHANNEL] = ch
    bitrate = grab(r"Bit Rate[:=]([\d.]+) ?Mb/s", float)
    if bitrate is not None:
        out[KEY_BITRATE] = bitrate
    txpower = grab(r"Tx-Power[:=](-?\d+)", int)
    if txpower is not None:
        out[KEY_TXPOWER] = txpower
    signal = grab(r"Signal level[:=](-?\d+)", int)
    if signal is not None:
        out[KEY_SIGNAL] = signal
    noise = grab(r"Noise level[:=](-?\d+)", int)
    if noise is not None:
        out[KEY_NOISE] = noise
    m = re.search(r"Link Quality[:=](\d+)/(\d+)", text)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if b:
            out[KEY_QUALITY] = round(a / b * 100, 1)
    return out


def parse_stations(text: str) -> dict:
    """Parse `wlanconfig <iface> list sta`.

    The RSSI column index varies by firmware (older units have a single RATE
    column, newer ones split it into TXRATE+RXRATE), so locate RSSI from the
    header row rather than assuming a fixed index.
    """
    lines = text.splitlines()
    rssi_idx: int | None = None
    for line in lines:
        cols = line.split()
        if cols and cols[0].upper() == "ADDR" and "RSSI" in cols:
            rssi_idx = cols.index("RSSI")
            break
    rssis: list[int] = []
    count = 0
    for line in lines:
        parts = line.split()
        if not parts or not _MAC_RE.match(parts[0]):
            continue
        count += 1
        if rssi_idx is not None and len(parts) > rssi_idx:
            try:
                rssis.append(int(parts[rssi_idx]))
            except ValueError:
                pass
    out: dict = {KEY_CLIENTS: count}
    if rssis:
        out[KEY_RSSI_AVG] = round(sum(rssis) / len(rssis), 1)
        out[KEY_RSSI_MIN] = min(rssis)
    return out


def parse_proc_net_dev(text: str) -> dict:
    """Parse /proc/net/dev into {iface: {rx_bytes, tx_bytes}}."""
    ifaces: dict = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        name, _, rest = line.partition(":")
        nums = rest.split()
        if len(nums) >= 9:
            try:
                ifaces[name.strip()] = {
                    "rx_bytes": int(nums[0]),
                    "tx_bytes": int(nums[8]),
                }
            except ValueError:
                continue
    return ifaces


def parse_mac(text: str) -> str | None:
    """Extract the first HWaddr from ifconfig output."""
    m = re.search(r"HWaddr ([0-9A-Fa-f:]{17})", text)
    return m.group(1).upper() if m else None


def detect_wifi_if(text: str) -> str | None:
    """From full `iwconfig` output, return the first wireless interface name."""
    for line in text.splitlines():
        if not line or line[0] in " \t":
            continue
        if "no wireless extensions" in line:
            continue
        if "IEEE 802.11" in line or "ESSID" in line:
            return line.split()[0]
    return None


def compute_throughput(
    prev_ifaces: dict, cur_ifaces: dict, dt_seconds: float
) -> dict:
    """Compute per-interface rx/tx Mbps from byte-counter deltas."""
    out: dict = {}
    if dt_seconds <= 0:
        return out
    for name, cur in cur_ifaces.items():
        prev = prev_ifaces.get(name)
        if not prev:
            continue
        rx = cur["rx_bytes"] - prev["rx_bytes"]
        tx = cur["tx_bytes"] - prev["tx_bytes"]
        if rx < 0 or tx < 0:  # counter reset (e.g. reboot)
            continue
        out[name] = {
            "rx_mbps": round(rx * 8 / dt_seconds / 1e6, 3),
            "tx_mbps": round(tx * 8 / dt_seconds / 1e6, 3),
        }
    return out


def pharos_login_encoded(username: str, password: str, nonce: str) -> str:
    """Build the Pharos web-login `encoded` credential.

    Matches the device JS: ``user + ":" + MD5( MD5(pw).upper() + ":" + nonce ).upper()``.
    """
    pw_md5 = hashlib.md5(password.encode()).hexdigest().upper()
    inner = hashlib.md5(f"{pw_md5}:{nonce}".encode()).hexdigest().upper()
    return f"{username}:{inner}"


def parse_all(raw: str, wifi_if: str) -> dict:
    """Parse the full combined command output into the data dict."""
    sections = _split_sections(raw)
    data: dict = {}
    if SEC_SYS in sections:
        data.update(parse_sys(sections[SEC_SYS]))
    if SEC_IW in sections:
        data.update(parse_iwconfig(sections[SEC_IW]))
    if SEC_STA in sections:
        data.update(parse_stations(sections[SEC_STA]))
    if SEC_NET in sections:
        data[KEY_IFACES] = parse_proc_net_dev(sections[SEC_NET])
    if SEC_IF in sections:
        mac = parse_mac(sections[SEC_IF])
        if mac:
            data[KEY_MAC] = mac
    return data
