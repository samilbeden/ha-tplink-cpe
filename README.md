# TP-Link CPE (SSH) — Home Assistant integration

Monitor and reboot **TP-Link Pharos CPE** devices (CPE210 / CPE220 / CPE510 / CPE610 …) from Home Assistant.
Sensors are polled over **SSH**; the per-device **Restart** button uses the device **web API**.

Each device is added as its own config entry from the UI, so you can manage **multiple CPEs** in one integration.

---

## Features

- **Multiple devices** — one config entry per CPE, added from the UI.
- **Sensors:** uptime, CPU load, memory, wireless (SSID, mode, channel, frequency, bit rate, TX power, signal, noise, link quality), connected clients (count + average / weakest RSSI), per-interface throughput.
- **Connectivity** binary sensor (online / offline).
- **Restart** button — reboots the device through its web API, with a Home Assistant notification (and a clean message when the device is unreachable).
- **Refresh** button — forces an immediate poll.
- **Auto-adapts** to firmware differences: wireless-interface detection, legacy/modern SSH host keys, RSSI column layout, HTTP/HTTPS web API, single-session login.

## Tested devices

| Model | Firmware notes |
|-------|----------------|
| TP-Link **CPE220** | Recent firmware (modern `ecdsa` SSH host key, HTTP + HTTPS web UI) |
| TP-Link **CPE510** | 2017 firmware / dropbear 2016 (legacy `ssh-dss` host key, HTTP-only web UI) |

Other Pharos-family CPEs (CPE210 / CPE510 / CPE610, etc.) are expected to work — the integration adapts to the firmware differences listed above.

## Prerequisites

- **SSH enabled on the CPE.** In the Pharos web UI: **System → SSH Server → Enable** (default port `22`).
- The device **admin username and password** (same credentials as the web UI; default user `admin`).
- **Network connectivity between Home Assistant and the device.** Home Assistant must be able to reach the CPE's IP — either:
  - on the **same LAN / subnet**, or
  - **remotely reachable** via routing / VPN.
- For the **Restart** button, the device **web UI must also be reachable** (HTTP `:80` or HTTPS `:443`). Reboot goes through the web API, not SSH, because the SSH account on these devices is unprivileged and cannot reboot.

### Different networks / remote access (Tailscale)

If Home Assistant and your CPEs are **not on the same network**, the recommended approach is [**Tailscale**](https://tailscale.com/): run a Tailscale **subnet router** on the CPE side (or on a host on that LAN) so Home Assistant can reach the CPE IPs over the tailnet. SSH polling and the HTTP-based reboot both work over Tailscale. (Note: some old CPE HTTPS stacks can be flaky over a reduced-MTU tunnel — the integration prefers HTTP for the reboot and only falls back to HTTPS, so this is normally a non-issue.)

## Installation

### HACS (recommended)

1. **HACS → Integrations → ⋮ → Custom repositories.**
2. Add `https://github.com/samilbeden/ha-tplink-cpe` with category **Integration**.
3. Install **TP-Link CPE (SSH)** and **restart Home Assistant**.

### Manual

Copy `custom_components/tplink_cpe/` into your Home Assistant `config/custom_components/` directory and restart.

## Configuration

**Settings → Devices & Services → Add Integration → TP-Link CPE (SSH)**:

| Field | Notes |
|-------|-------|
| Name | Optional friendly name (defaults to the host). |
| Host / IP address | The device IP, e.g. `192.168.1.2`. |
| SSH port | Default `22`. |
| Username | Default `admin`. |
| Password | The device password. |

Repeat **Add Integration** for each device. The **update interval** is configurable per device (**Configure** → 10–3600 s, default **30 s**).

## Entities (per device)

**Sensors:** Uptime · CPU load (1m / 5m / 15m) · Memory used · SSID · Wireless mode · Channel · Frequency · Bit rate · TX power · Signal · Noise · Link quality · Connected clients · Average client RSSI · Weakest client RSSI · `<iface>` RX/TX rate (Mbps) · `<iface>` RX/TX total (bytes, disabled by default).

**Binary sensor:** Connectivity.

**Buttons:** Restart (reboot via web API) · Refresh (force an immediate poll).

> Mode-specific values (e.g. per-client RSSI on an AP, or direct signal on a client link) populate according to the device's wireless mode; values that don't apply show as *unknown*.

## How it works

- **Sensors:** every poll opens an SSH connection (`asyncssh`), runs one combined command, and parses `uptime` / `loadavg` / `free` / `iwconfig` / `wlanconfig list sta` / `/proc/net/dev` / `ifconfig`.
- **Reboot:** the SSH login maps to an unprivileged account that can't reboot, so the Restart button replicates the web UI's reboot — log in to the web API (MD5 challenge using the session cookie as the nonce), take over the session if another one is active, then call the reboot endpoint. It tries HTTP `:80` first and falls back to HTTPS `:443` (legacy TLS + self-signed certificate tolerated). The web reboot uses the **same credentials** as SSH.

## Troubleshooting

- **"Failed to connect over SSH"** — make sure SSH is enabled on the device and the host/credentials are correct. Older firmware that only offers the legacy `ssh-dss` host key is supported automatically.
- **Restart shows an error / "could not reach …"** — the device web UI must be reachable (HTTP/HTTPS); the device may be momentarily offline.
- **Throughput is empty at first** — rates need two samples, so they appear after ~2 update cycles.
- **Web vs SSH password** — the Restart button assumes the web UI password is the same as the SSH password (true for standard Pharos setups).

## Disclaimer

This is a **personal hobby project**, developed in my spare time and provided **"as is", without any warranty** of any kind (see the [MIT License](LICENSE)).

- It is **not affiliated with, authorized, or endorsed by TP-Link**. "TP-Link", "Pharos", and related names/logos are trademarks of their respective owners.
- The author accepts **no responsibility or liability** for any damage, data loss, device malfunction, downtime, or other consequences arising from the use of this software.
- Managing and **rebooting network equipment is done entirely at your own risk** — make sure you understand what the Restart button does before using it.

If this integration is useful to you, great — but you are responsible for how you use it.

## License

[MIT](LICENSE)
