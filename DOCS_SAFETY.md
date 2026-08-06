# Safety Gates

All destructive tools require `confirm=True` to execute. Without it, they return `{"error": "confirm_required"}` without making any changes.

| Tool | Gate | Effect if confirmed |
|------|------|---------------------|
| `apply_rf_recommendation` | `confirm=True` | Push RF channel/power changes to APs |
| `apply_ap_config` | `confirm=True` | Override AP channel/power manually |
| `create_wlan` | `confirm=True` | Create new WLAN/SSID |
| `modify_wlan` | `confirm=True` | Modify existing WLAN config |
| `reboot_ap` | `confirm=True` | Reboot access point |
| `disconnect_client` | `confirm=True` | Disconnect client from AP |
| `toggle_wlan` | `confirm=True` | Enable/disable WLAN |

## Implementation

Each tool function has an early return before any API call:

```python
if not confirm:
    return {"error": "confirm_required", "detail": "Set confirm=True to ..."}
```