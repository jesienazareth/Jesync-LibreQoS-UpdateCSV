import csv, json, logging, time, random, string, subprocess
import routeros_api
from collections import OrderedDict
import os, re, argparse, gc, psutil, sys

CSV_FILE_PATH = 'ShapedDevices.csv'
CONFIG_JSON = 'config.json'
SHAPED_DEVICES_CSV = 'ShapedDevices.csv'
NETWORK_JSON = 'network.json'
STATIC_JSON = 'jesync_static_device.json'
STATE_TRACKER = 'last_parent_manual_state.txt'

FIELDNAMES = [
    'Circuit ID', 'Circuit Name', 'Device ID', 'Device Name', 'Parent Node',
    'MAC', 'IPv4', 'IPv6', 'Download Min Mbps', 'Upload Min Mbps',
    'Download Max Mbps', 'Upload Max Mbps', 'Comment'
]

DEFAULT_SCAN_INTERVAL = 600
ERROR_RETRY_INTERVAL = 30
MIN_RATE_PERCENTAGE = 0.3
MAX_RATE_PERCENTAGE = 1.3
ID_LENGTH = 8

parser = argparse.ArgumentParser()
parser.add_argument('--max-cycles', type=int, default=100)
parser.add_argument('--max-runtime', type=int, default=10800)
parser.add_argument('--max-ram-mb', type=int, default=2000, help='Max RAM usage in MB before restart')
parser.add_argument('--debug', action='store_true')
args = parser.parse_args()

start_time = time.time()
cycle_count = 0

logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def generate_short_id(length=ID_LENGTH):
    return ''.join(random.choices(string.digits + string.ascii_uppercase, k=length))

def read_json_data(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r') as json_file:
            return json.load(json_file)
    return {}

def read_shaped_devices_csv():
    shaped = OrderedDict()
    if os.path.exists(SHAPED_DEVICES_CSV):
        with open(SHAPED_DEVICES_CSV, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                row["_last_seen"] = 0
                shaped[row["Device Name"]] = row
    return shaped

def write_shaped_devices_csv(data):
    with open(SHAPED_DEVICES_CSV, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in data.values():
            clean_row = {k: v for k, v in row.items() if k in FIELDNAMES}
            writer.writerow(clean_row)

def wipe_shaped_devices_csv():
    with open(SHAPED_DEVICES_CSV, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()

def connect_to_router(router):
    try:
        pool = routeros_api.RouterOsApiPool(
            router['address'],
            username=router['username'],
            password=router['password'],
            port=router.get('port', 8728),
            plaintext_login=True,
        )
        return pool.get_api(), pool
    except Exception as e:
        logger.error(f"Failed to connect to router {router['name']}: {e}")
        return None, None

def get_global_parent_manual_state(config):
    return any(router.get("parent_manual", False) for router in config.get("routers", []))

def check_and_wipe_on_state_change(current_state):
    last_state = None
    if os.path.exists(STATE_TRACKER):
        with open(STATE_TRACKER, 'r') as f:
            last_state = f.read().strip()

    if str(current_state).lower() != last_state:
        logger.warning(f"Parent manual mode changed: wiping ShapedDevices.csv")
        wipe_shaped_devices_csv()
        with open(STATE_TRACKER, 'w') as f:
            f.write(str(current_state).lower())
    else:
        logger.debug("Parent manual mode unchanged — keeping existing shaped data.")

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

def process_static_devices():
    static_data = read_json_data(STATIC_JSON)
    static_devices = static_data.get("StaticDevices", [])
    shaped = OrderedDict()
    reserved_ips = set()

    for device in static_devices:
        devname = device.get("Device Name", "unknown")
        ip = device.get("IPv4", "")
        key = devname.replace(" ", "-").upper()
        reserved_ips.add(ip)
        logger.info(f"Adding Static device {devname} with IP {ip}")
        shaped[key] = {
            "Circuit ID": generate_short_id(),
            "Device ID": generate_short_id(),
            "Circuit Name": device.get("Circuit Name", devname),
            "Device Name": devname,
            "MAC": device.get("MAC", ""),
            "IPv4": ip,
            "IPv6": device.get("IPv6", ""),
            "Parent Node": device.get("Parent Node", "Static"),
            "Comment": device.get("Comment", "Static"),
            "Download Min Mbps": device.get("Download Min Mbps", "50"),
            "Upload Min Mbps": device.get("Upload Min Mbps", "50"),
            "Download Max Mbps": device.get("Download Max Mbps", "100"),
            "Upload Max Mbps": device.get("Upload Max Mbps", "100")
        }
    return shaped, reserved_ips

def extract_parents_from_network(network_dict, prefix):
    return [name for name in network_dict if name.upper().startswith(prefix.upper())]

def process_pppoe_users(api, router, shaped_data, reserved_ips, parent_nodes, rotate_index=0):
    if not router.get("pppoe", {}).get("enabled"):
        return {}, rotate_index

    users = {}
    name = router["name"]
    secrets = {s["name"]: s for s in api.get_resource("/ppp/secret").get() if "name" in s}
    active = {a["name"]: a for a in api.get_resource("/ppp/active").get() if "name" in a}
    existing_ips = {v["IPv4"]: k for k, v in shaped_data.items() if v["Comment"] == "PPP"}

    for uname, secret in secrets.items():
        if uname in active and "address" in active[uname]:
            addr = active[uname]["address"]

            if addr in reserved_ips:
                logger.info(f"Skipping PPPoE user {uname} — IP {addr} is reserved for static device.")
                continue

            if uname in shaped_data and shaped_data[uname]["IPv4"] == addr:
                shaped_data[uname]["_last_seen"] = time.time()
                logger.debug(f"Skipping PPPoE user {uname} — already up to date.")
                continue

            if uname in shaped_data and shaped_data[uname]["IPv4"] != addr:
                logger.warning(f"{uname} IP changed from {shaped_data[uname]['IPv4']} to {addr}, removing old entry")
                shaped_data.pop(uname, None)

            if addr in existing_ips:
                old_user = existing_ips[addr]
                if old_user != uname:
                    logger.warning(f"IP conflict: {addr} reassigned from {old_user} to {uname}")
                    shaped_data.pop(old_user, None)

            profile = secret.get("profile", "default")
            rate_limit = get_profile_rate_limits(api, profile)
            rx, tx = parse_rate_limit(rate_limit)
            rx_max, tx_max = calculate_max_rates(rx, tx)
            rx_min, tx_min = calculate_min_rates(rx_max, tx_max)

            parent_node = parent_nodes[rotate_index % len(parent_nodes)] if parent_nodes else f"PPP-{name}"
            rotate_index += 1

            logger.info(f"Adding PPPoE user {uname} with IP {addr} -> Parent Node: {parent_node}")
            users[uname] = {
                "Circuit ID": generate_short_id(),
                "Device ID": generate_short_id(),
                "Circuit Name": uname,
                "Device Name": uname,
                "MAC": secret.get("caller-id", ""),
                "IPv4": addr,
                "IPv6": "",
                "Parent Node": parent_node,
                "Comment": "PPP",
                "Download Max Mbps": rx_max,
                "Upload Max Mbps": tx_max,
                "Download Min Mbps": rx_min,
                "Upload Min Mbps": tx_min,
                "_last_seen": time.time()
            }
    return users, rotate_index

def process_hotspot_users(api, router, shaped_data, reserved_ips):
    if not router.get("hotspot", {}).get("enabled"):
        return {}

    users = {}
    name = router["name"]
    dl = str(router.get("hotspot", {}).get("download_limit_mbps", 10))
    ul = str(router.get("hotspot", {}).get("upload_limit_mbps", 10))
    for user in api.get_resource("/ip/hotspot/active").get():
        uname = user.get("user") or user.get("mac-address") or user.get("address")
        ip = user.get("address")
        if not uname or not ip:
            continue

        if ip in reserved_ips:
            logger.info(f"Skipping Hotspot user {uname} — IP {ip} is reserved for static device.")
            continue

        code = f"HS-{uname.replace(':', '').replace('.', '')}"
        if code in shaped_data and shaped_data[code]["IPv4"] == ip:
            shaped_data[code]["_last_seen"] = time.time()
            logger.debug(f"Skipping Hotspot user {code} — already up to date.")
            continue

        logger.info(f"Adding Hotspot user {uname} with IP {ip}")
        users[code] = {
            "Circuit ID": generate_short_id(),
            "Device ID": generate_short_id(),
            "Circuit Name": code,
            "Device Name": code,
            "MAC": user.get("mac-address", ""),
            "IPv4": ip,
            "IPv6": "",
            "Parent Node": f"HS-{name}",
            "Comment": "Hotspot",
            "Download Max Mbps": dl,
            "Upload Max Mbps": ul,
            "Download Min Mbps": str(int(float(dl) * MIN_RATE_PERCENTAGE)),
            "Upload Min Mbps": str(int(float(ul) * MIN_RATE_PERCENTAGE)),
            "_last_seen": time.time()
        }
    return users


def process_cycle():
    global shaped_data, static_data, reserved_ips, config, routers, network_data

    config = read_json_data(CONFIG_JSON)
    routers = config.get("routers", [])
    scan_interval = config.get("scan_interval", DEFAULT_SCAN_INTERVAL)
    parent_manual_state = get_global_parent_manual_state(config)
    check_and_wipe_on_state_change(parent_manual_state)

    shaped_data = read_shaped_devices_csv()
    static_data, reserved_ips = process_static_devices()
    shaped_data.update(static_data)

    network_data = read_json_data(NETWORK_JSON)
    all_parent_nodes = extract_parents_from_network(network_data, "PPPOE-")
    rotate_index = 0

    for router in routers:
        api, pool = connect_to_router(router)
        if not api:
            continue

        try:
            parent_nodes = all_parent_nodes if router.get("parent_manual", False) else []
            if router.get("parent_manual", False) and not parent_nodes:
                logger.warning(f"Router {router['name']} has parent_manual=true but no PPPOE- nodes found")
            pppoe_data, rotate_index = process_pppoe_users(api, router, shaped_data, reserved_ips, parent_nodes, rotate_index)
            shaped_data.update(pppoe_data)
            shaped_data.update(process_hotspot_users(api, router, shaped_data, reserved_ips))
        finally:
            try:
                pool.disconnect()
            except:
                pass

    # Prune inactive dynamic users
    now = time.time()
    shaped_data = {k: v for k, v in shaped_data.items()
                   if v.get("Comment") not in ["PPP", "Hotspot"] or (now - float(v.get("_last_seen", now))) <= 1200}

    write_shaped_devices_csv(shaped_data)
    subprocess.run(["sudo", "/opt/libreqos/src/LibreQoS.py", "--updateonly"], check=True)

    # RAM check and restart
    ram_mb = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
    logger.info(f"RAM usage: {ram_mb:.2f} MB")
    if ram_mb > args.max_ram_mb:
        logger.warning(f"RAM exceeded {args.max_ram_mb} MB. Restarting script...")
        time.sleep(2)
        os.execv(sys.executable, [sys.executable] + sys.argv)

    del shaped_data, static_data, reserved_ips, config, routers, network_data
    gc.collect()

def main():
    global cycle_count
    while True:
        if args.max_cycles and cycle_count >= args.max_cycles:
            logger.info("Reached max cycles limit. Exiting.")
            break
        if args.max_runtime and (time.time() - start_time) >= args.max_runtime:
            logger.info("Reached max runtime limit. Exiting.")
            break
        try:
            process_cycle()
            cycle_count += 1
            logger.info(f"Cycle complete. Sleeping {DEFAULT_SCAN_INTERVAL} seconds...")
            time.sleep(DEFAULT_SCAN_INTERVAL)
        except Exception as e:
            logger.error(f"Error occurred: {e}")
            time.sleep(ERROR_RETRY_INTERVAL)

if __name__ == "__main__":
    main()
