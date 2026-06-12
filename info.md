# TP-Link CPE (SSH)

Monitor and reboot **TP-Link Pharos CPE** devices (CPE210 / CPE220 / CPE510 / CPE610 …) from Home Assistant.

- Multiple devices, added from the UI (one config entry per CPE).
- Sensors: system (uptime, CPU load, memory), wireless (signal, noise, channel, bit rate, SSID …), connected clients, per-interface throughput, connectivity.
- **Restart** button (reboots via the device web API, with a notification) and **Refresh** button.
- Adapts to firmware differences across the Pharos family.

**Requires SSH enabled on the device**, and network reachability between Home Assistant and the CPE (same LAN or remote via VPN such as Tailscale).

Hobby project, provided "as is" — not affiliated with TP-Link.
