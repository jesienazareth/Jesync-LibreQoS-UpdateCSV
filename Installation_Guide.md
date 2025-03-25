# Installation Guide: LibreQoS MikroTik PPP and Active Hotspot User Sync

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
