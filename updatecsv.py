import csv
import json
import logging
import time
import random
import string
import subprocess
import routeros_api
from collections import OrderedDict
from functools import lru_cache
import os
import re

# -------------------------------
# Static Device Merge Helper Functions
# -------------------------------
CSV_FILE_PATH = 'ShapedDevices.csv'
JSON_FILE_PATH = 'jesync_static_device.json'

def read_csv_data(file_path):
    """Read existing data from CSV into a dictionary."""
    data = {}
    if os.path.exists(file_path):
        with open(file_path, mode='r', newline='') as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                # Using "Circuit Name" as the unique key
                data[row['Circuit Name']] = row
    return data

def read_json_data(file_path):
    """Read static devices from JSON into a dictionary or list."""
    if os.path.exists(file_path):
        with open(file_path, mode='r') as json_file:
            return json.load(json_file)
    return {}

def write_csv_data(file_path, data):
    """Write data to CSV from a list of dictionaries."""
    if data:
        fieldnames = list(data[0].keys())
        with open(file_path, mode='w', newline='') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)

def merge_static_devices(existing_data, static_devices):
    """Merge static devices into existing data without duplication."""
    for device_id, device_info in static_devices.items():
        existing_data[device_id] = device_info
    return existing_data

# -------------------------------
# Configuration and Utility Functions
# -------------------------------
CONFIG_JSON = 'config.json'  # JSON file containing router configuration
SHAPED_DEVICES_CSV = 'ShapedDevices.csv'  # Output CSV file
NETWORK_JSON = 'network.json'  # Network configuration JSON file
FIELDNAMES = [
    'Circuit ID', 'Circuit Name', 'Device ID', 'Device Name', 'Parent Node',
    'MAC', 'IPv4', 'IPv6', 'Download Min Mbps', 'Upload Min Mbps',
    'Download Max Mbps', 'Upload Max Mbps', 'Comment'
]
SCAN_INTERVAL = 120  # Time in seconds between router scans
ERROR_RETRY_INTERVAL = 30  # Time in seconds to wait after an error
MIN_RATE_PERCENTAGE = 0.5  # Calculate min rates as this percentage of max rates
MAX_RATE_PERCENTAGE = 1.15  # Calculate max rates as this percentage of bandwidth
ID_LENGTH = 8  # Length of generated short IDs
DEFAULT_BANDWIDTH = 2000  # Default bandwidth for new routers in Mbps

# Logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def generate_short_id(length=ID_LENGTH):
    """Generate a short random ID using numbers and uppercase letters."""
    return ''.join(random.choices(string.digits + string.ascii_uppercase, k=length))

def read_config_json():
    """Read router configuration from the JSON file."""
    try:
        with open(CONFIG_JSON, 'r') as f:
            config = json.load(f)
        routers = config.get('routers', [])
        logger.info(f"Successfully read {len(routers)} routers from {CONFIG_JSON}")
        return routers
    except FileNotFoundError:
        logger.error(f"Config JSON file not found: {CONFIG_JSON}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in config file: {e}")
        return []
    except Exception as e:
        logger.error(f"Error reading config JSON: {e}")
        return []

def read_network_json():
    """Read the network configuration from JSON file."""
    try:
        if os.path.exists(NETWORK_JSON):
            with open(NETWORK_JSON, 'r') as f:
                return json.load(f)
        else:
            logger.info(f"Network JSON file not found: {NETWORK_JSON}, will create a new one.")
            return {}
    except Exception as e:
        logger.error(f"Error reading network JSON: {e}")
        return {}

def write_network_json(data):
    """Write network configuration to JSON file."""
    try:
        with open(NETWORK_JSON, 'w') as f:
            json.dump(data, f, indent=4)
        logger.info(f"Successfully wrote network configuration to {NETWORK_JSON}")
    except Exception as e:
        logger.error(f"Error writing network JSON: {e}")

def update_network_json(routers):
    """Update network.json with any missing routers."""
    network_config = read_network_json()
    updated = False
    
    for router in routers:
        router_name = router['name']
        if router_name not in network_config:
            network_config[router_name] = {
                "downloadBandwidthMbps": DEFAULT_BANDWIDTH,
                "uploadBandwidthMbps": DEFAULT_BANDWIDTH,
                "type": "site",
                "children": {}
            }
        
            if router.get('pppoe', {}).get('enabled', False):
                network_config[router_name]["children"][f"PPP-{router_name}"] = {
                    "downloadBandwidthMbps": DEFAULT_BANDWIDTH,
                    "uploadBandwidthMbps": DEFAULT_BANDWIDTH,
                    "type": "site",
                    "children": {}
                }
            
            if router.get('hotspot', {}).get('enabled', False):
                network_config[router_name]["children"][f"HS-{router_name}"] = {
                    "downloadBandwidthMbps": DEFAULT_BANDWIDTH,
                    "uploadBandwidthMbps": DEFAULT_BANDWIDTH,
                    "type": "site",
                    "children": {}
                }
                
            if router.get('dhcp', {}).get('enabled', False):
                network_config[router_name]["children"][f"DHCP-{router_name}"] = {
                    "downloadBandwidthMbps": DEFAULT_BANDWIDTH,
                    "uploadBandwidthMbps": DEFAULT_BANDWIDTH,
                    "type": "site",
                    "children": {}
                }
                
            logger.info(f"Added router {router_name} to network configuration")
            updated = True
    
    if updated:
        write_network_json(network_config)
    else:
        logger.info("No new routers needed to be added to network configuration")
    
    return network_config

def connect_to_router(router, retries=3):
    """
    Connect to a MikroTik router with enhanced error handling and retry mechanism.
    """
    for attempt in range(retries):
        try:
            connection = routeros_api.RouterOsApiPool(
                router['address'],
                username=router['username'],
                password=router['password'],
                port=router['port'],
                plaintext_login=True,
            )
            api = connection.get_api()
            logger.info(f"Successfully connected to router: {router['name']} ({router['address']}) [Attempt {attempt + 1}]")
            return api
        except Exception as e:
            logger.warning(f"Connection error to {router['name']} ({router['address']}) [Attempt {attempt + 1}/{retries}]: {e}")
            if attempt == retries - 1:
                logger.error(f"Failed to connect to router {router['name']} after {retries} attempts")
                return None
            time.sleep(5)

def get_resource_data(api, resource_path):
    """Get data from a specified resource path."""
    try:
        return api.get_resource(resource_path).get()
    except Exception as e:
        logger.error(f"Failed to get data from {resource_path}: {e}")
        return []

def convert_to_mbps(value_str):
    """
    Convert a bandwidth value to Mbps regardless of the unit (k/K, m/M, g/G).
    Examples: "10m", "10M", "2.5G", "1000k" all get converted to Mbps.
    """
    try:
        if not value_str or value_str == '0':
            return '0'
            
        match = re.match(r'(\d+(?:\.\d+)?)([kmgKMG])?', value_str.strip())
        if not match:
            return '0'
            
        number_str, unit = match.groups()
        number = float(number_str)
        
        if not unit:
            return str(round(number, 2))
        
        unit = unit.lower()
        if unit == 'k':
            return str(round(number / 1000, 2))  # kbps to Mbps
        elif unit == 'm':
            return str(round(number, 2))  # Already in Mbps
        elif unit == 'g':
            return str(round(number * 1000, 2))  # Gbps to Mbps
        else:
            return str(round(number, 2))
            
    except Exception as e:
        logger.warning(f"Could not convert bandwidth value: {value_str} to Mbps: {e}")
        return '0'

@lru_cache(maxsize=32)
def parse_rate_limit(rate_limit):
    """Parse a rate limit string and return rx, tx values in Mbps."""
    try:
        if not rate_limit or rate_limit == '0/0':
            return '0', '0'
        
        first_rate = rate_limit.split()[0]
        rx, tx = first_rate.split('/')
        
        rx_mbps = convert_to_mbps(rx)
        tx_mbps = convert_to_mbps(tx)
        
        return rx_mbps, tx_mbps
        
    except Exception as e:
        logger.warning(f"Could not parse rate limit: {rate_limit}, using defaults: {e}")
        return '3', '3'

def get_profile_rate_limits(api, profile_name, resource_path):
    """
    Fetch rate limits for a profile from the specified resource path.
    **Modified:** This version now uses the PPP profile's comment field exclusively to determine the bandwidth.
    """
    try:
        profiles = api.get_resource(resource_path).get(name=profile_name)
        if not profiles:
            return '50M/50M'
        
        profile = profiles[0]
        # Instead of using 'rate-limit', we now use the profile's comment field for bandwidth.
        comment_value = profile.get('comment', '')
        if comment_value:
            return comment_value
        # Fallback to a default value if no comment is set.
        return '50M/50M'
    
    except Exception as e:
        logger.error(f"Failed to get profile rate limits for {profile_name}: {e}")
        return '50M/50M'

def read_shaped_devices_csv():
    """Read existing shaped devices from the CSV file."""
    data = OrderedDict()
    try:
        with open(SHAPED_DEVICES_CSV, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                data[row['Circuit Name']] = row
        logger.info(f"Successfully read {len(data)} entries from {SHAPED_DEVICES_CSV}")
    except FileNotFoundError:
        logger.info(f"No existing CSV file found at {SHAPED_DEVICES_CSV}, will create a new one.")
    return data

def write_shaped_devices_csv(data):
    """Write shaped devices data to the CSV file."""
    with open(SHAPED_DEVICES_CSV, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in data.values():
            writer.writerow(row)
    logger.info(f"Successfully wrote {len(data)} entries to {SHAPED_DEVICES_CSV}")

def calculate_min_rates(max_rx, max_tx):
    """Calculate minimum rates based on maximum rates with a minimum of 2 Mbps."""
    rx_float = float(max_rx) if max_rx.replace('.', '', 1).isdigit() else 0
    tx_float = float(max_tx) if max_tx.replace('.', '', 1).isdigit() else 0
    
    calculated_min_rx = int(rx_float * MIN_RATE_PERCENTAGE)
    calculated_min_tx = int(tx_float * MIN_RATE_PERCENTAGE)
    
    min_rx = max(calculated_min_rx, 2)
    min_tx = max(calculated_min_tx, 2)
    
    return str(min_rx), str(min_tx)

def calculate_max_rates(rx, tx):
    """Calculate maximum rates with a minimum of 2 Mbps."""
    rx_float = float(rx) if rx.replace('.', '', 1).isdigit() else 0
    tx_float = float(tx) if tx.replace('.', '', 1).isdigit() else 0
    
    calculated_max_rx = int(rx_float * MAX_RATE_PERCENTAGE)
    calculated_max_tx = int(tx_float * MAX_RATE_PERCENTAGE)
    
    max_rx = max(calculated_max_rx, 2)
    max_tx = max(calculated_max_tx, 2)
    
    return str(max_rx), str(max_tx)

def create_new_entry(code, router_name, entry_type, mac='', ipv4=''):
    """Create a new device entry."""
    return {
        'Circuit ID': generate_short_id(),
        'Device ID': generate_short_id(),
        'Circuit Name': code,
        'Device Name': code,
        'MAC': mac,
        'IPv4': ipv4,
        'IPv6': '',
        'Parent Node': f"{entry_type}-{router_name}",
        'Comment': entry_type,
        'Download Max Mbps': '0',
        'Upload Max Mbps': '0',
        'Download Min Mbps': '0',
        'Upload Min Mbps': '0'
    }

def update_entry_values(entry, new_values):
    """Update an entry with new values and return if any changes were made."""
    changed = False
    for k, v in new_values.items():
        if entry.get(k) != v:
            entry[k] = v
            changed = True
    return changed

# --- New helper function for bandwidth override from comment ---
def get_bandwidth_from_comment(comment):
    """
    Check if the comment is in the format "20m/20m" (or similar) and return that string.
    Returns None if the comment does not match.
    """
    pattern = r'^\s*(\d+(?:\.\d+)?[kKmMgG])\s*/\s*(\d+(?:\.\d+)?[kKmMgG])\s*$'
    m = re.match(pattern, comment)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    return None

# --- New helper function to get global bandwidth setting ---
def get_global_bandwidth_setting():
    """
    Read the global "UseProfileBandwidth" setting from jesync_static_device.json.
    Assumes the JSON is a dict with a key "UseProfileBandwidth". If not found or error, returns False.
    """
    try:
        data = read_json_data(JSON_FILE_PATH)
        if isinstance(data, dict):
            return data.get("UseProfileBandwidth", False)
        return False
    except Exception as e:
        logger.warning(f"Could not read global bandwidth setting: {e}")
        return False

def process_pppoe_users(api, router, existing_data, network_config):
    """Process PPPoE users from a router."""
    if not router.get('pppoe', {}).get('enabled', False):
        logger.info(f"PPPoE processing disabled for router: {router['name']}")
        return set(), False
        
    router_name = router['name']
    current_users = set()
    updated = False
    per_plan_node = router.get('pppoe', {}).get('per_plan_node', False)
    
    secrets = {s['name']: s for s in get_resource_data(api, '/ppp/secret') if 'name' in s}
    active = {a['name']: a for a in get_resource_data(api, '/ppp/active') if 'name' in a}

    active_secrets = {}
    for name, data in secrets.items():
        if name in active and 'address' in active[name]:
            active_secrets[name] = {**data, 'address': active[name]['address']}
    
    # Get global setting for using profile bandwidth override.
    USE_PROFILE_BANDWIDTH = get_global_bandwidth_setting()
    
    for code, secret in active_secrets.items():
        current_users.add(code)
        
        if code in existing_data:
            entry = existing_data[code]
        else:
            entry = create_new_entry(
                code, 
                router_name, 
                'PPP', 
                secret.get('caller-id', ''), 
                secret.get('address', '')
            )
            existing_data[code] = entry
            logger.info(f"Created new entry for PPPoE user: {code} with IDs: {entry['Circuit ID']}/{entry['Device ID']}")
            updated = True
        
        # Get rate limit from PPP profile's comment (modified behavior)
        profile_name = secret.get('profile', 'default')
        rate_limit = get_profile_rate_limits(api, profile_name, '/ppp/profile')
        
        # Optionally, you can log the rate limit value
        logger.info(f"Using PPP profile comment rate limit for {code}: {rate_limit}")
        
        rx, tx = parse_rate_limit(rate_limit)
        rx_max, tx_max = calculate_max_rates(rx, tx)
        rx_min, tx_min = calculate_min_rates(rx_max, tx_max)
        
        parent_node = f"PPP-{router_name}"
        if per_plan_node:
            profile_node = f"PLAN-{profile_name}-{router_name}"
            parent_node = profile_node
            
            if profile_node not in network_config.get(router_name, {}).get('children', {}):
                if router_name in network_config:
                    if 'children' not in network_config[router_name]:
                        network_config[router_name]['children'] = {}
                    
                    if profile_node not in network_config[router_name]['children']:
                        network_config[router_name]['children'][profile_node] = {
                            "downloadBandwidthMbps": DEFAULT_BANDWIDTH,
                            "uploadBandwidthMbps": DEFAULT_BANDWIDTH,
                            "type": "plan",
                            "children": {}
                        }
                        logger.info(f"Added PPPoE profile node {profile_node} to network configuration")
                        
        new_values = {
            'Parent Node': parent_node,
            'MAC': secret.get('caller-id', ''),
            'IPv4': secret.get('address', ''),
            'Download Max Mbps': rx_max,
            'Upload Max Mbps': tx_max,
            'Download Min Mbps': rx_min,
            'Upload Min Mbps': tx_min
        }
        
        if update_entry_values(entry, new_values):
            updated = True
    
    return current_users, updated

def process_hotspot_users(api, router, existing_data, network_config):
    """Process hotspot users from a router."""
    if not router.get('hotspot', {}).get('enabled', False):
        logger.info(f"Hotspot processing disabled for router: {router['name']}")
        return set(), False
        
    router_name = router['name']
    current_users = set()
    updated = False
    include_mac = router.get('hotspot', {}).get('include_mac', True)
    
    download_limit = router.get('hotspot', {}).get('download_limit_mbps', 10)
    upload_limit = router.get('hotspot', {}).get('upload_limit_mbps', 10)
    
    hotspot_users = get_resource_data(api, '/ip/hotspot/active')
    
    for user in hotspot_users:
        mac = user.get('mac-address', '')
        ip = user.get('address', '')
        
        if include_mac and mac:
            code = f"HS-{mac.replace(':', '')}"
        else:
            username = user.get('user', '')
            if not username:
                continue
            code = f"HS-{username}"
        
        current_users.add(code)
        
        if code in existing_data:
            entry = existing_data[code]
        else:
            entry = create_new_entry(code, router_name, 'HS', mac, ip)
            existing_data[code] = entry
            logger.info(f"Created new entry for hotspot user: {code} with IDs: {entry['Circuit ID']}/{entry['Device ID']}")
            updated = True
        
        rx_max, tx_max = str(download_limit), str(upload_limit)
        rx_min, tx_min = calculate_min_rates(rx_max, tx_max)
        
        new_values = {
            'Parent Node': f"HS-{router_name}",
            'MAC': mac,
            'IPv4': ip,
            'Download Max Mbps': rx_max,
            'Upload Max Mbps': tx_max,
            'Download Min Mbps': rx_min,
            'Upload Min Mbps': tx_min
        }
        
        if update_entry_values(entry, new_values):
            updated = True
    
    return current_users, updated

def process_dhcp_leases(api, router, existing_data, network_config):
    """Process DHCP leases from a router."""
    if not router.get('dhcp', {}).get('enabled', False):
        logger.info(f"DHCP processing disabled for router: {router['name']}")
        return set(), False
        
    router_name = router['name']
    current_users = set()
    updated = False
    
    download_limit = router.get('dhcp', {}).get('download_limit_mbps', 1000)
    upload_limit = router.get('dhcp', {}).get('upload_limit_mbps', 1000)
    dhcp_servers = router.get('dhcp', {}).get('dhcp_server', ['dhcp1'])
    
    dhcp_leases = []
    for server in dhcp_servers:
        server_leases = get_resource_data(api, f'/ip/dhcp-server/lease')
        if server != '*':
            server_leases = [lease for lease in server_leases if lease.get('server', '') == server]
        dhcp_leases.extend(server_leases)
    
    for lease in dhcp_leases:
        mac = lease.get('mac-address', '')
        if not mac:
            continue
            
        ip = lease.get('address', '')
        hostname = lease.get('host-name', '')
        
        if hostname:
            code = f"DHCP-{hostname}"
        else:
            code = f"DHCP-{mac.replace(':', '')}"
        
        current_users.add(code)
        
        if code in existing_data:
            entry = existing_data[code]
        else:
            entry = create_new_entry(code, router_name, 'DHCP', mac, ip)
            existing_data[code] = entry
            logger.info(f"Created new entry for DHCP lease: {code} with IDs: {entry['Circuit ID']}/{entry['Device ID']}")
            updated = True
        
        rx_max, tx_max = str(download_limit), str(upload_limit)
        rx_min, tx_min = calculate_min_rates(rx_max, tx_max)
        
        new_values = {
            'Parent Node': f"DHCP-{router_name}",
            'MAC': mac,
            'IPv4': ip,
            'Comment': f"{hostname}" if hostname else "DHCP",
            'Download Max Mbps': rx_max,
            'Upload Max Mbps': tx_max,
            'Download Min Mbps': rx_min,
            'Upload Min Mbps': tx_min
        }
        
        if update_entry_values(entry, new_values):
            updated = True
    
    return current_users, updated

def process_static_devices(existing_data):
    """
    Process static devices from jesync_static_device.json and update the existing_data dict.
    The JSON file should contain a dict with a global setting "UseProfileBandwidth" and a "StaticDevices" array.
    Each static device entry can specify a manual parent node via the "Parent Node" field.
    Returns a tuple (set_of_static_codes, set_of_static_parent_nodes, updated_flag).
    """
    try:
        data = read_json_data(JSON_FILE_PATH)
        # If the JSON is a dict, then extract the static devices list; otherwise, assume it's a list.
        if isinstance(data, dict):
            static_devices = data.get("StaticDevices", [])
        else:
            static_devices = data
        logger.info(f"Loaded {len(static_devices)} static devices from jesync_static_device.json")
    except Exception as e:
        logger.error(f"Error processing static devices file: {e}")
        return set(), set(), False

    updated = False
    static_codes = set()
    static_parent_nodes = set()

    for device in static_devices:
        circuit_name = device.get("Circuit Name")
        if not circuit_name:
            logger.warning("Skipping static device entry without 'Circuit Name'")
            continue

        static_codes.add(circuit_name)

        # Use manual input for parent node if provided; otherwise, default to "Static"
        parent_node_manual = device.get("Parent Node", "Static")
        static_parent_nodes.add(parent_node_manual)
        device["Parent Node"] = parent_node_manual  # Ensure the device reflects the manual input

        if circuit_name in existing_data:
            entry = existing_data[circuit_name]
            if update_entry_values(entry, device):
                logger.info(f"Updated static device entry: {circuit_name}")
                updated = True
        else:
            new_entry = {
                'Circuit ID': generate_short_id(),
                'Device ID': generate_short_id(),
                'Circuit Name': circuit_name,
                'Device Name': device.get("Device Name", circuit_name),
                'Parent Node': parent_node_manual,
                'MAC': device.get("MAC", ""),
                'IPv4': device.get("IPv4", ""),
                'IPv6': device.get("IPv6", ""),
                'Download Min Mbps': device.get("Download Min Mbps", "0"),
                'Upload Min Mbps': device.get("Upload Min Mbps", "0"),
                'Download Max Mbps': device.get("Download Max Mbps", "0"),
                'Upload Max Mbps': device.get("Upload Max Mbps", "0"),
                'Comment': device.get("Comment", "")
            }
            existing_data[circuit_name] = new_entry
            logger.info(f"Added static device entry: {circuit_name}")
            updated = True

    return static_codes, static_parent_nodes, updated

def main():
    """Main function to run the script."""
    logger.info("Starting to scan routers")
    
    while True:
        try:
            existing_data = read_shaped_devices_csv()
            routers = read_config_json()
            network_config = update_network_json(routers)
            
            all_current_users = set()
            any_updates = False
            
            for router in routers:
                logger.info(f"Processing router: {router['name']} at {router['address']}")
                
                api = connect_to_router(router)
                if api is None:
                    logger.warning(f"Skipping router {router['name']} due to connection failure.")
                    continue
                
                try:
                    pppoe_users, pppoe_updated = process_pppoe_users(api, router, existing_data, network_config)
                    all_current_users.update(pppoe_users)
                    any_updates = any_updates or pppoe_updated
                    
                    hotspot_users, hotspot_updated = process_hotspot_users(api, router, existing_data, network_config)
                    all_current_users.update(hotspot_users)
                    any_updates = any_updates or hotspot_updated
                    
                    dhcp_users, dhcp_updated = process_dhcp_leases(api, router, existing_data, network_config)
                    all_current_users.update(dhcp_users)
                    any_updates = any_updates or dhcp_updated
                    
                except Exception as e:
                    logger.error(f"Error processing router {router['name']}: {e}")
            
            # Process static devices from jesync_static_device.json
            static_codes, static_parent_nodes, static_updated = process_static_devices(existing_data)
            all_current_users.update(static_codes)
            any_updates = any_updates or static_updated
            
            # Update network configuration for each static parent node specified in the JSON.
            for parent in static_parent_nodes:
                if parent not in network_config:
                    network_config[parent] = {
                        "downloadBandwidthMbps": DEFAULT_BANDWIDTH,
                        "uploadBandwidthMbps": DEFAULT_BANDWIDTH,
                        "type": "static",
                        "children": {}
                    }
                    logger.info(f"Added '{parent}' parent node to network configuration for static devices.")
            
            # Remove inactive users (static devices are preserved because they're in all_current_users)
            for code in list(existing_data.keys()):
                if code not in all_current_users:
                    logger.info(f"Removing inactive user: {code}")
                    del existing_data[code]
                    any_updates = True
            
            if any_updates:
                logger.info("Updating CSV file with new data.")
                write_shaped_devices_csv(existing_data)
                write_network_json(network_config)
            try:
                logger.info("Running LibreQoS update command...")
                subprocess.run(["sudo", "/opt/libreqos/src/LibreQoS.py", "--updateonly"], check=True)
                logger.info("LibreQoS update command executed successfully.")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to execute LibreQoS update command: {e}")
    
            logger.info(f"Completed scan of {len(routers)} routers. Waiting {SCAN_INTERVAL} seconds before next scan.")
            time.sleep(SCAN_INTERVAL)
            
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            logger.info(f"Waiting {ERROR_RETRY_INTERVAL} seconds before retry.")
            time.sleep(ERROR_RETRY_INTERVAL)

if __name__ == "__main__":
    main()
