#!/bin/bash
# install_updatecsv.sh
# This script installs the LibreQoS UpdateCSV script and configuration files into /opt/libreqos/src/,
# sets proper permissions (owned by root), and creates a systemd service for automatic startup.

set -e

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This installation script must be run as root. Try using sudo."
   exit 1
fi

# Define installation paths and filenames
TARGET_DIR="/opt/libreqos/src"
FILES=("config.json" "network.json" "jesync_static_device.json" "updatecsv.py")
SERVICE_FILE="/etc/systemd/system/updatecsv.service"

echo "Creating target directory $TARGET_DIR ..."
mkdir -p "$TARGET_DIR"

echo "Copying configuration and script files to $TARGET_DIR ..."
for file in "${FILES[@]}"; do
    if [[ -f $file ]]; then
        cp "$file" "$TARGET_DIR/"
        echo "Copied $file"
    else
        echo "Warning: $file not found in the current directory."
    fi
done

echo "Setting ownership and permissions..."
chown -R root:root "$TARGET_DIR"
chmod -R 755 "$TARGET_DIR"

echo "Creating systemd service file at $SERVICE_FILE ..."
cat << EOF > "$SERVICE_FILE"
[Unit]
Description=Sync MikroTik to LibreQoS Update Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$TARGET_DIR
ExecStart=/usr/bin/python3 $TARGET_DIR/updatecsv.py
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

echo "Reloading systemd daemon..."
systemctl daemon-reload

echo "Enabling and starting updatecsv.service..."
systemctl enable updatecsv.service
systemctl restart updatecsv.service

echo "Installation complete! Please verify the service status with:"
echo "    sudo systemctl status updatecsv.service"
