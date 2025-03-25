# Release Notes – Bandwidth Override & Parent Node Update

**Version:** 1.2.0  
**Release Date:** 2025-03-25

## What’s New

### 1. Dynamic Bandwidth Override

We've added a new global option that lets the script use real-time bandwidth data from your MikroTik routers. When the new setting `UseProfileBandwidth` in your `jesync_static_device.json` file is enabled, the script will check the active PPP connection’s comment for a bandwidth value (like “20m/20m”). If it finds a valid value, that value will override the default bandwidth settings derived from the router profile. This means your devices can automatically adjust their bandwidth allocation based on live data, making network management a bit more responsive.

### 2. Custom Parent Node for Static Devices

Static devices are no longer forced into a default “Static” group. You can now specify a custom "Parent Node" for each static device directly in your `jesync_static_device.json` file. For example, you might want to group office routers under “CoreDevices” and backup routers under “BackupDevices.” The script will update your network configuration to include these custom parent nodes automatically. This update makes your network organization more intuitive and easier to manage.

## How to Use

### Update Your Configuration:

1. Open your `jesync_static_device.json` file.
2. Set `"UseProfileBandwidth": true` to enable dynamic bandwidth overrides for devices fetched via the API.
3. Under `"StaticDevices"`, set the `"Parent Node"` field to your desired grouping (e.g., "CoreDevices" or "BackupDevices").

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
```

### Deploy the Script:

1. Follow the installation guide to move the updated files to `/opt/libreqos/src/`.
2. Make sure your configuration files are edited before transferring.
3. Set the proper file permissions so the script can read/write in `/opt/libreqos/src/`.

### Run and Monitor:

- Test the script by running it manually with the `--debug` flag.
- Once verified, set up the systemd service to run the script automatically in the background.
This update makes your network management smarter and more flexible. With dynamic bandwidth overrides, your devices can adjust based on real-time data from the router, and custom parent nodes allow you to better organize static devices according to your network’s unique structure. We hope these improvements make managing your LibreQoS environment easier and more intuitive.
