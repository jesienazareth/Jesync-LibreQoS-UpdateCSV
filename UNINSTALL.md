# Uninstall Guide: Jesync-LibreQoS-UpdateCSV

This guide will walk you through uninstalling the Jesync-LibreQoS-UpdateCSV script and its associated services from your system.

## Step 1: Stop the Service

First, stop the systemd service that runs the Jesync-LibreQoS-UpdateCSV script.

```bash
sudo systemctl stop updatecsv.service
```

## Step 2: Disable the Service

Next, disable the service to prevent it from starting automatically on boot.

```bash
sudo systemctl disable updatecsv.service
```

## Step 3: Remove the Service File

Delete the systemd service file to completely remove the service configuration.

```bash
sudo rm /etc/systemd/system/updatecsv.service
```

## Step 4: Reload Systemd Daemon

Reload the systemd daemon to apply the changes.

```bash
sudo systemctl daemon-reload
```

## Step 5: Remove the Script and Configuration Files

Delete the script and configuration files from the target directory.

```bash
sudo rm -r /opt/libreqos/src/
```

## Step 6: Uninstall Python Dependencies

If you installed the `routeros_api` Python library using pipx, you can uninstall it with the following command:

```bash
pipx uninstall routeros_api
```

## Step 7: Verify the Uninstallation

Ensure that the service has been removed and the files have been deleted by checking the service status and listing the target directory.

```bash
sudo systemctl status updatecsv.service
ls -l /opt/libreqos/src/
```

You should see that the service is no longer active and the target directory does not exist.

## Final Notes

By following these steps, you will have completely uninstalled the Jesync-LibreQoS-UpdateCSV script and its associated services from your system. If you have any issues or need further assistance, please refer to the project documentation or open an issue on GitHub.