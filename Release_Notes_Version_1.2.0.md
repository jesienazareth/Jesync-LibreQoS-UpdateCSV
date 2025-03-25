# Release Notes – Bandwidth Override & Parent Node Update

**Version:** 1.2.0  
**Release Date:** 2025-03-25

## What’s New

### Dynamic Bandwidth Override

#### Global Setting:
- You can now enable the `UseProfileBandwidth` option in your configuration file (`jesync_static_device.json`). When enabled, the script checks the active PPP connection's comment for a bandwidth value (for example, "20m/20m").

#### How It Works:
- If a valid override is found, that value replaces the default profile-derived settings, letting your devices adjust their bandwidth allocation on the fly based on real-time data.

#### Why It Matters:
- This makes managing bandwidth more responsive without needing to manually update router profiles.

### Custom Parent Nodes for Static Devices

#### Custom Grouping:
- Static devices no longer have to be forced into a default "Static" group. You can now specify a custom "Parent Node" for each static device directly in your configuration file.

#### How It Works:
- For example, you can group office routers under "CoreDevices" and backup routers under "BackupDevices". The script automatically updates the network configuration to include these custom parent nodes.

#### Why It Matters:
- This improvement helps keep your network organization intuitive and tailored to your setup.

## How to Use

### Update Your Configuration:

Open your `jesync_static_device.json` file and set `"UseProfileBandwidth": true` if you want dynamic bandwidth override.

Under `"StaticDevices"`, specify the `"Parent Node"` for each static device as desired.

#### Example:
```json
{
  "UseProfileBandwidth": true,
  "StaticDevices": [
    {
      "Circuit Name": "Static-Device-1",
      "Device Name": "Office Router",
      "Parent Node": "CoreDevices",
      "MAC": "AA:BB:CC:DD:EE:FF",
      "IPv4": "192.168.1.10",
      "IPv6": "2001:db8::1",
      "Comment": "Office router static device"
    },
    {
      "Circuit Name": "Static-Device-2",
      "Device Name": "Backup Router",
      "Parent Node": "BackupDevices",
      "MAC": "11:22:33:44:55:66",
      "IPv4": "192.168.1.11",
      "IPv6": "",
      "Comment": "Backup router for redundancy"
    }
  ]
}