# Installation Guide: LibreQoS MikroTik PPPoE and Active Hotspot User Sync

This guide will walk you through installing and setting up the LibreQoS MikroTik PPP and Active Hotspot User Sync script. The script synchronizes MikroTik PPP secrets (PPPoE users) and active hotspot users with a LibreQoS-compatible CSV file (`ShapedDevices.csv`). It continuously monitors your MikroTik routers for changes and updates the CSV file accordingly. The script also supports dynamic bandwidth override and custom parent node updates. It runs as a background service using systemd.

## Prerequisites
Ensure you have the following on your LibreQoS machine:
- Linux-based system (Ubuntu, Debian, etc.)
- Python 3 installed.
- Git installed.
- pipx installed (for installing the `routeros_api` Python library).
- A working MikroTik Router configured with PPP secrets and hotspot users.
- LibreQoS installed and configured to use the `ShapedDevices.csv` file.
- A properly formatted `network.json` file (the script updates this automatically).

## Step 1: Install Python and Required Libraries

Install Python 3 and pip:

```bash
sudo apt update
sudo apt install python3 python3-pip
```

Install pipx and the `routeros_api` library:

```bash
sudo apt install pipx
sudo pipx ensurepath
# You might need to log out and log back in for the PATH to update.
pipx install routeros_api
```

## Step 2: Clone the Repository and Edit Configuration Files

Clone the Repository:

```bash
git clone https://github.com/jesienazareth/Jesync-LibreQoS-UpdateCSV.git
cd Jesync-LibreQoS-UpdateCSV
```
### Edit Before Installation:
Always update your configuration files (`config.json` and `jesync_static_device.json`) to match your network environment before running the installation script.

Edit the Configuration Files:
- `config.json`: Update with your MikroTik router IP addresses, ports, credentials, and other settings.
- `jesync_static_device.json`: Adjust your static device entries, global settings (e.g., `"UseProfileBandwidth": true`), and custom parent node values.
### Setup your Mirkrotik Device Credential and config.json
- https://github.com/jesienazareth/Jesync-LibreQoS-UpdateCSV/blob/main/mikrotik_Credential_Script.md
> Note: Make sure these files are edited to match your environment before proceeding with the installation.

## Step 3: Run the Installation Script

The provided `install_updatecsv.sh` script will automate the installation process by:
- Creating the target directory `/opt/libreqos/src/`.
- Copying `updatecsv.py`, `config.json`, and `jesync_static_device.json` into that directory.
- Setting the correct permissions (ownership as root).
- Creating a systemd service to run the script automatically.

Make the Installation Script Executable:

```bash
chmod +x install_updatecsv.sh
```

Run the Installation Script as Root:

```bash
sudo ./install_updatecsv.sh
```

The script will output status messages as it performs each step.

## Step 4: Verify the Installation

After running the installation script, verify the setup as follows:

Check the Target Directory:

```bash
ls -l /opt/libreqos/src/
```

Ensure that `updatecsv.py`, `config.json`, and `jesync_static_device.json` are present.

Check the Systemd Service File:

```bash
cat /etc/systemd/system/updatecsv.service
```

Check the Service Status:

```bash
sudo systemctl status updatecsv.service
```

The service status should indicate it is active and running.

Review Logs:

```bash
journalctl -u updatecsv.service -f
```

## Final Notes

### Dependencies:
Ensure pipx and `routeros_api` are installed as described in Step 1.

### Automation:
The systemd service will ensure that the script runs automatically on boot and restarts if it fails.

By following these instructions, you'll have the LibreQoS UpdateCSV script installed and running on your LibreQoS machine with minimal manual effort.

# jesync_static_device.json Guide

## Overview
The `jesync_static_device.json` file is used by the LibreQoS UpdateCSV script to define static devices and set global options. In this context, a Static Device is a device that you manually input—its IP address and other details are entered by you rather than being automatically discovered by the script.

## File Structure
You can structure the file in one of two ways:

### Option 1: With Global Settings and a Device List
This format lets you set a global option for bandwidth override along with a list of static devices.

```json
{
  "UseProfileBandwidth": true,
  "StaticDevices": [
    {
      "Circuit Name": "Mikrotik-Static-Device-1",
      "Device Name": "Office Router",
      "Parent Node": "CoreDevices",
      "MAC": "AA:BB:CC:DD:EE:FF",
      "IPv4": "192.168.1.10",
      "IPv6": "2001:db8::1",
      "Comment": "Office router static device"
    },
    {
      "Circuit Name": "Mikrotik-Static-Device-2",
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

### Option 2: As a Simple List of Devices
If you don’t need any global settings, you can simply list the devices:

```json
[
  {
    "Circuit Name": "Mikrotik-Static-Device-1",
    "Device Name": "Office Router",
    "Parent Node": "CoreDevices",
    "MAC": "AA:BB:CC:DD:EE:FF",
    "IPv4": "192.168.1.10",
    "IPv6": "2001:db8::1",
    "Comment": "Office router static device"
  },
  {
    "Circuit Name": "Mikrotik-Static-Device-2",
    "Device Name": "Backup Router",
    "Parent Node": "BackupDevices",
    "MAC": "11:22:33:44:55:66",
    "IPv4": "192.168.1.11",
    "IPv6": "",
    "Comment": "Backup router for redundancy"
  }
]
```

## Key Elements Explained
### Global Setting: `UseProfileBandwidth`
- **Purpose:** When set to `true`, the script uses the PPP profile’s comment (for example, "20m/20m") as the bandwidth value for PPPoE devices fetched from the router.
- **Usage:** This setting is placed at the top of your JSON (as shown in Option 1). If omitted or set to `false`, the script uses the default rate-limit values—i.e., it will use the rx and tx values set on the PPP profile.

### How the Script Uses `jesync_static_device.json`
#### Static Devices:
The script reads this file to get a list of static device entries. It then merges these entries into its device list, ensuring that the devices you manually define are always included in the final output.

#### Custom Parent Nodes:
The `Parent Node` field allows you to group your static devices under a custom name instead of being placed under a generic category. For example, you might set `"Parent Node": "CoreDevices"` or `"Parent Node": "BackupDevices"` to reflect the device's role in your network.

## Final Notes
1. **Edit Carefully:** Always review and update your `jesync_static_device.json` file to match your actual network environment before running the script.
2. **Naming Convention:** Ensure every "Circuit Name" starts with "Mikrotik" to maintain consistency.
3. **Flexibility:** You can choose the file structure that best suits your needs. Option 1 provides a global setting along with a device list, while Option 2 is a simpler list of devices.

This guide should help you understand and configure your `jesync_static_device.json` file for the LibreQoS UpdateCSV script. If you have any questions or need further assistance, please feel free to ask.

# How config.json Work

## Overview
The `config.json` file is used to store the details of the MikroTik routers that the script will connect to. Here’s a breakdown of its structure and how each part is used by the script:

## File Structure
Your `config.json` contains a list of routers under the "routers" key. Each router entry includes:

### Router Details
- **name:** A friendly name for the router. (e.g., "Mikrotik Core", "Mikrotik AC")
  - This name is used in log messages and when grouping devices.
- **address:** The IP address of the router that the script will connect to.
- **port:** The port number on which the MikroTik API is listening (commonly 8728).
- **username & password:** Credentials used by the script to authenticate with the router.

### Specific Router Settings
Each router has its own settings for different services:

#### DHCP Section
- **enabled:** A boolean value that tells the script whether to process DHCP lease data from this router.
- **download_limit_mbps & upload_limit_mbps:** These values specify the bandwidth limits (in Mbps) for DHCP leases.
- **dhcp_server:** A list of DHCP server names on the router. The script will filter DHCP leases by these server names.

#### Hotspot Section
- **enabled:** If true, the script will process active hotspot user data.
- **include_mac:** Determines if the script should use the MAC address to create a unique identifier for hotspot users.
- **download_limit_mbps & upload_limit_mbps:** Define the bandwidth limits for hotspot users.

#### PPPoE Section
- **enabled:** If true, the script processes PPPoE user data.
- **per_plan_node:** If true, the script creates separate nodes in the network configuration based on PPP profile plans. This allows for granular bandwidth management per profile.

## How the Script Uses These Settings
### Router Connections:
The script reads the "routers" list from `config.json` to know which routers to connect to and how to connect to them (using IP, port, username, and password).

### Service Processing:
Based on the service sections (DHCP, hotspot, PPPoE), the script processes only those services that are enabled. It uses the specified download and upload limits to assign bandwidth for each device or user.

### Network Configuration:
The script uses these limits to update a network configuration file (`network.json`), grouping devices and setting bandwidth parameters accordingly.

This configuration file allows you to customize how each router is handled by the script, ensuring that data from each router is processed with its own specific settings for DHCP, hotspot, and PPPoE services.
