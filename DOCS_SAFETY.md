# Safety Gates — 22 destructive tools

All destructive tools require `confirm=True` to execute. Without it, they return `{"error": "confirm_required"}` without making any changes.

## Dry-Run Preview

All 15 ICX config tools support `dry_run=True` to preview commands without execution:

```python
ruckus_device_port_state(host=..., port=..., enable=True, dry_run=True)
# → {"dry_run": True, "commands": ["configure terminal", "interface ethernet 1/1/1", "enable", "end"]}
```

## Tools

| Tool | Gate | Effect if confirmed |
|------|------|---------------------|
| `apply_rf_recommendation` | `confirm=True` | Push RF channel/power changes to APs |
| `apply_ap_config` | `confirm=True` | Override AP channel/power manually |
| `create_wlan` | `confirm=True` | Create new WLAN/SSID |
| `modify_wlan` | `confirm=True` | Modify existing WLAN config |
| `reboot_ap` | `confirm=True` | Reboot access point |
| `disconnect_client` | `confirm=True` | Disconnect client from AP |
| `toggle_wlan` | `confirm=True` | Enable/disable WLAN |
| `ruckus_device_port_state` | `confirm=True` | Enable/disable switch port |
| `ruckus_device_vlan_create` | `confirm=True` | Create VLAN(s) |
| `ruckus_device_vlan_delete` | `confirm=True` | Delete VLAN(s) |
| `ruckus_device_vlan_port` | `confirm=True` | Add/remove port VLAN membership |
| `ruckus_device_poe_port` | `confirm=True` | Enable/disable PoE on port |
| `ruckus_device_ip_route` | `confirm=True` | Add static IPv4 route |
| `ruckus_device_ip_route_delete` | `confirm=True` | Delete static IPv4 route |
| `ruckus_device_ipv6_route` | `confirm=True` | Add static IPv6 route |
| `ruckus_device_ipv6_route_delete` | `confirm=True` | Delete static IPv6 route |
| `ruckus_device_ipv6_unicast_routing` | `confirm=True` | Enable/disable `ipv6 unicast-routing` |
| `ruckus_device_timezone_set` | `confirm=True` | Set system timezone |
| `ruckus_device_clock_set` | `confirm=True` | Set system date/time manually |
| `ruckus_device_ntp_server` | `confirm=True` | Add/remove NTP server |
| `ruckus_device_ntp_control` | `confirm=True` | Enable/disable NTP service |
| `ruckus_device_config_save` | `confirm=True` | Persist running-config (`write memory`) |

## Implementation

Each tool function has an early return before any API call:

```python
if not confirm:
    return {"error": "confirm_required", "detail": "Set confirm=True to ..."}
```