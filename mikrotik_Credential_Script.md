## How the Script Uses These Settings
### Router Connections:
The script reads the "routers" list from `config.json` to know which routers to connect to and how to connect to them (using IP, port, username, and password).

### Service Processing:
Based on the service sections (DHCP, hotspot, PPPoE), the script processes only those services that are enabled. It uses the specified download and upload limits to assign bandwidth for each device or user.

### Network Configuration:
The script uses these limits to update a network configuration file (`network.json`), grouping devices and setting bandwidth parameters accordingly.

This configuration file allows you to customize how each router is handled by the script, ensuring that data from each router is processed with its own specific settings for DHCP, hotspot, and PPPoE services.

# MikroTik Script Configuration

To set up your MikroTik router to work with LibreQoS, follow these steps:

1. **Set Up User and Password:**
   Add a user to your MikroTik router with read permissions. Replace `<Strong Password>` with a strong password and `<LibreQos IP Address>` with the IP address of your LibreQoS server.
   ```shell
   /user add name="libreQos" group=read password="<Strong Password>" address="<LibreQos IP Address>" disabled=no;
   ```

2. **Configure `config.json`:**
   Update your `config.json` file with the details of your MikroTik routers. Below is a sample configuration:
   ```json
   {
     "routers": [
       {
         "name": "Mikrotik Core",
         "address": "192.168.10.12",
         "port": 8728,
         "username": "libreQos",
         "password": "<Strong Password>",
         "dhcp": {
           "enabled": true,
           "download_limit_mbps": 25,
           "upload_limit_mbps": 25,
           "dhcp_server": [
             "dhcpA",
             "dhcpB"
           ]
         },
         "hotspot": {
           "enabled": false,
           "include_mac": false,
           "download_limit_mbps": 15,
           "upload_limit_mbps": 15
         },
         "pppoe": {
           "enabled": false,
           "per_plan_node": false
         }
       },
       {
         "name": "Mikrotik AC",
         "address": "10.0.5.22",
         "port": 8728,
         "username": "libreQos",
         "password": "<Strong Password>",
         "dhcp": {
           "enabled": false,
           "download_limit_mbps": 100,
           "upload_limit_mbps": 100,
           "dhcp_server": [
             "dhcpMain"
           ]
         },
Replace `<Strong Password>` with the password you set on your MikroTik router.
