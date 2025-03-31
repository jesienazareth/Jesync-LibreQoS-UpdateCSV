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

CSV_FILE_PATH = 'ShapedDevices.csv'
CONFIG_JSON = 'config.json'
SHAPED_DEVICES_CSV = 'ShapedDevices.csv'
NETWORK_JSON = 'network.json'
FIELDNAMES = [
    'Circuit ID', 'Circuit Name', 'Device ID', 'Device Name', 'Parent Node',
    'MAC', 'IPv4', 'IPv6', 'Download Min Mbps', 'Upload Min Mbps',
    'Download Max Mbps', 'Upload Max Mbps', 'Comment'
]
SCAN_INTERVAL = 120
ERROR_RETRY_INTERVAL = 30
MIN_RATE_PERCENTAGE = 0.3
MAX_RATE_PERCENTAGE = 1
ID_LENGTH = 8
DEFAULT_BANDWIDTH = 2000

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def generate_short_id(length=ID_LENGTH):
    return ''.join(random.choices(string.digits + string.ascii_uppercase, k=length))

def read_json_data(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r') as json_file:
            return json.load(json_file)
    return {}

def write_json_data(file_path, data):
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=4)

def write_shaped_devices_csv(data):
    with open(SHAPED_DEVICES_CSV, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in data.values():
            writer.writerow(row)

def read_shaped_devices_csv():
    data = OrderedDict()
    if os.path.exists(SHAPED_DEVICES_CSV):
        with open(SHAPED_DEVICES_CSV, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                data[row['Circuit Name']] = row
    return data

def connect_to_router(router):
    try:
        connection = routeros_api.RouterOsApiPool(
            router['address'],
            username=router['username'],
            password=router['password'],
            port=router.get('port', 8728),
            plaintext_login=True,
        )
        return connection.get_api()
    except Exception as e:
        logger.error(f"Failed to connect to router {router['name']}: {e}")
        return None

def parse_rate_limit(rate_limit):
    if not rate_limit or rate_limit == '0/0':
        return '0', '0'
    try:
        rate = rate_limit.split()[0]
        rx, tx = rate.split('/')
        return convert_to_mbps(rx), convert_to_mbps(tx)
    except:
        return '0', '0'

def convert_to_mbps(value):
    try:
        match = re.match(r'(\d+(?:\.\d+)?)([kmgKMG])?', value)
        if not match:
            return '0'
        number, unit = match.groups()
        number = float(number)
        unit = unit.lower() if unit else ''
        if unit == 'k':
            return str(round(number / 1000, 2))
        elif unit == 'm':
            return str(round(number, 2))
        elif unit == 'g':
            return str(round(number * 1000, 2))
        return str(round(number, 2))
    except:
        return '0'

def calculate_max_rates(rx, tx):
    return str(max(int(float(rx) * MAX_RATE_PERCENTAGE), 2)), str(max(int(float(tx) * MAX_RATE_PERCENTAGE), 2))

def calculate_min_rates(rx_max, tx_max):
    return str(max(int(float(rx_max) * MIN_RATE_PERCENTAGE), 2)), str(max(int(float(tx_max) * MIN_RATE_PERCENTAGE), 2))

def get_profile_rate_limits(api, profile_name):
    try:
        profiles = api.get_resource('/ppp/profile').get(name=profile_name)
        if profiles:
            return profiles[0].get('rate-limit') or profiles[0].get('comment', '50M/50M')
    except:
        pass
    return '50M/50M'

def get_manual_pppoe_parents(network_config):
    return sorted([key for key in network_config if key.startswith("PPPOE-")])

def process_pppoe_users(api, router, existing_data, network_config, manual_parents=None, global_index=0):
    if not router.get("pppoe", {}).get("enabled"):
        return set(), False, 0

    current_users = set()
    updated = False
    name = router["name"]
    per_plan = router.get("pppoe", {}).get("per_plan_node", False)
    secrets = {s["name"]: s for s in api.get_resource("/ppp/secret").get() if "name" in s}
    active = {a["name"]: a for a in api.get_resource("/ppp/active").get() if "name" in a}
    active_users = {name_: {**s, "address": active[name_]["address"]}
                    for name_, s in secrets.items() if name_ in active and "address" in active[name_]}

    manual_count = len(manual_parents) if manual_parents else 0
    index_offset = global_index

    for offset, (code, secret) in enumerate(active_users.items()):
        current_users.add(code)
        profile_name = secret.get("profile", "default")
        rate_limit = get_profile_rate_limits(api, profile_name)
        rx, tx = parse_rate_limit(rate_limit)
        rx_max, tx_max = calculate_max_rates(rx, tx)
        rx_min, tx_min = calculate_min_rates(rx_max, tx_max)

        if router.get("parent_manual", False) and manual_parents:
            parent_node = manual_parents[(index_offset + offset) % manual_count]
        elif per_plan:
            parent_node = f"PLAN-{profile_name}-{name}"
            if parent_node not in network_config.get(name, {}).get("children", {}):
                network_config[name].setdefault("children", {})[parent_node] = {
                    "downloadBandwidthMbps": DEFAULT_BANDWIDTH,
                    "uploadBandwidthMbps": DEFAULT_BANDWIDTH,
                    "type": "plan",
                    "children": {}
                }
        else:
            parent_node = f"PPP-{name}"

        if code not in existing_data:
            existing_data[code] = {
                "Circuit ID": generate_short_id(),
                "Device ID": generate_short_id(),
                "Circuit Name": code,
                "Device Name": code,
                "MAC": secret.get("caller-id", ""),
                "IPv4": secret.get("address", ""),
                "IPv6": "",
                "Parent Node": parent_node,
                "Comment": "PPP",
                "Download Max Mbps": rx_max,
                "Upload Max Mbps": tx_max,
                "Download Min Mbps": rx_min,
                "Upload Min Mbps": tx_min
            }
            updated = True
    return current_users, updated, len(active_users)

def process_hotspot_users(api, router, existing_data):
    if not router.get("hotspot", {}).get("enabled"):
        return set(), False

    current_users = set()
    updated = False
    name = router["name"]
    dl = str(router.get("hotspot", {}).get("download_limit_mbps", 10))
    ul = str(router.get("hotspot", {}).get("upload_limit_mbps", 10))
    hs_users = api.get_resource("/ip/hotspot/active").get()

    for user in hs_users:
        username = user.get("user")
        if not username:
            continue
        code = f"HS-{username}"
        current_users.add(code)
        if code not in existing_data:
            existing_data[code] = {
                "Circuit ID": generate_short_id(),
                "Device ID": generate_short_id(),
                "Circuit Name": code,
                "Device Name": code,
                "MAC": user.get("mac-address", ""),
                "IPv4": user.get("address", ""),
                "IPv6": "",
                "Parent Node": f"HS-{name}",
                "Comment": "Hotspot",
                "Download Max Mbps": dl,
                "Upload Max Mbps": ul,
                "Download Min Mbps": str(int(float(dl) * MIN_RATE_PERCENTAGE)),
                "Upload Min Mbps": str(int(float(ul) * MIN_RATE_PERCENTAGE))
            }
            updated = True
    return current_users, updated

def main():
    while True:
        try:
            shaped_data = read_shaped_devices_csv()
            config_data = read_json_data(CONFIG_JSON)
            routers = config_data.get("routers", [])
            network_config = read_json_data(NETWORK_JSON)
            manual_parents = get_manual_pppoe_parents(network_config)

            all_users = set()
            updated = False
            pppoe_counter = 0

            for router in routers:
                api = connect_to_router(router)
                if not api:
                    continue

                pppoe_users, ppp_updated, count = process_pppoe_users(
                    api, router, shaped_data, network_config,
                    manual_parents if router.get("parent_manual") else None,
                    pppoe_counter
                )
                pppoe_counter += count

                hs_users, hs_updated = process_hotspot_users(api, router, shaped_data)

                all_users |= pppoe_users | hs_users
                updated |= ppp_updated or hs_updated

            for code in list(shaped_data.keys()):
                if code not in all_users:
                    del shaped_data[code]
                    updated = True

            if updated:
                write_shaped_devices_csv(shaped_data)
                write_json_data(NETWORK_JSON, network_config)
                subprocess.run(["sudo", "/opt/libreqos/src/LibreQoS.py", "--updateonly"], check=True)

            logger.info(f"Cycle complete. Sleeping {SCAN_INTERVAL} seconds...")
            time.sleep(SCAN_INTERVAL)

        except Exception as e:
            logger.error(f"Error occurred: {e}")
            time.sleep(ERROR_RETRY_INTERVAL)

if __name__ == "__main__":
    main()
