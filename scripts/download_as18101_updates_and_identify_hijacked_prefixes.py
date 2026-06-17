# Downloads Telegram's announced prefixes and AS18101 BGP updates with proper pagination.
#
# IMPORTANT: For very large time windows or busy prefixes, the RIPE Stat API may
# truncate responses and provide continuation URLs in the 'see_also' field.
# This script handles pagination transparently and warns when the server-returned
# query_endtime does not match the requested window.

import os
import urllib.request
import json
import ipaddress
import sys

TELEGRAM_ASNS = ["AS62041", "AS62014", "AS59930", "AS211157", "AS205103"]

# Set data directories relative to repository root
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_dir = os.path.join(repo_root, "data")
raw_data_dir = os.path.join(data_dir, "raw")
updates_file = os.path.join(raw_data_dir, "bgp_updates_18101.json")

REQUESTED_START = "2026-06-16T07:00:00"
REQUESTED_END = "2026-06-16T22:00:00"

BASE_URL = "https://stat.ripe.net/data"


def fetch_with_pagination(url, max_pages=50):
    """Fetch a RIPE Stat API response and follow 'see_also' continuations."""
    page_count = 0
    merged_updates = []
    first_query_starttime = None
    last_query_endtime = None
    resource = None

    while url is not None:
        page_count += 1
        if page_count > max_pages:
            raise RuntimeError(f"Pagination exceeded {max_pages} pages; aborting.")

        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                payload = json.loads(response.read().decode())
        except Exception as e:
            raise RuntimeError(f"Failed to fetch {url}: {e}") from e

        if payload.get("status") != "ok":
            raise RuntimeError(f"RIPE API returned non-ok status for {url}: {payload.get('status')}")

        data_section = payload.get("data", {})
        if resource is None:
            resource = data_section.get("resource")
            first_query_starttime = data_section.get("query_starttime")
        last_query_endtime = data_section.get("query_endtime")

        updates = data_section.get("updates", [])
        merged_updates.extend(updates)

        see_also = payload.get("see_also") or []
        url = see_also[0] if see_also else None

    return {
        "resource": resource,
        "query_starttime": first_query_starttime,
        "query_endtime": last_query_endtime,
        "updates": merged_updates,
        "page_count": page_count
    }


def download_data():
    if not os.path.exists(raw_data_dir):
        os.makedirs(raw_data_dir)
        print(f"Created directory: {raw_data_dir}")

    # 1. Download Telegram prefixes
    for asn in TELEGRAM_ASNS:
        file_path = os.path.join(raw_data_dir, f"{asn}_prefixes.json")
        if not os.path.exists(file_path):
            url = f"{BASE_URL}/announced-prefixes/data.json?resource={asn}"
            print(f"Downloading announced prefixes for {asn}...")
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req) as response:
                    with open(file_path, "wb") as f:
                        f.write(response.read())
            except Exception as e:
                print(f"  Error downloading {asn}: {e}")
        else:
            print(f"  Local file for {asn} already exists.")

    # 2. Download AS18101 updates (with pagination)
    if not os.path.exists(updates_file):
        url = f"{BASE_URL}/bgp-updates/data.json?resource=18101&starttime={REQUESTED_START}&endtime={REQUESTED_END}"
        print(f"Downloading BGP updates for AS18101 from {REQUESTED_START} to {REQUESTED_END}...")
        try:
            result = fetch_with_pagination(url)
            if result["query_endtime"] and result["query_endtime"] < REQUESTED_END:
                print(f"  WARNING: Server returned query_endtime={result['query_endtime']}, "
                      f"requested {REQUESTED_END}. This may indicate the API capped the response.")
            with open(updates_file, "w") as f:
                json.dump({"data": result}, f, indent=2)
            print(f"  Saved {len(result['updates'])} updates ({result['page_count']} page(s)) to {updates_file}")
        except Exception as e:
            print(f"  Error downloading updates: {e}")
            sys.exit(1)
    else:
        print("  Local updates file already exists.")

        # If the existing file is truncated, warn the user
        try:
            with open(updates_file, "r") as f:
                existing = json.load(f)
            end = existing.get("data", {}).get("query_endtime", "?")
            if end and end < REQUESTED_END:
                print(f"  WARNING: Existing file has query_endtime={end}, "
                      f"but requested window ends at {REQUESTED_END}.")
                print(f"  Delete {updates_file} to force re-download with full pagination.")
        except Exception:
            pass


def analyze_local_data():
    print("\nLoading Telegram prefixes...")
    telegram_networks = []

    for asn in TELEGRAM_ASNS:
        file_path = os.path.join(raw_data_dir, f"{asn}_prefixes.json")
        if not os.path.exists(file_path):
            continue
        with open(file_path, "r") as f:
            try:
                data = json.load(f)
                prefixes = data.get("data", {}).get("prefixes", [])
                for p in prefixes:
                    net_str = p.get("prefix")
                    if net_str:
                        telegram_networks.append(ipaddress.ip_network(net_str))
            except Exception as e:
                print(f"Error parsing {file_path}: {e}")

    print(f"Loaded {len(telegram_networks)} Telegram networks.")

    print("\nParsing local AS18101 BGP updates...")
    if not os.path.exists(updates_file):
        print("Updates file missing!")
        return

    originated_prefixes = set()
    # Support both nested format (data.query_starttime) and raw format
    with open(updates_file, "r") as f:
        try:
            payload = json.load(f)
            # Handle both wrapped and unwrapped formats
            if "updates" in payload:
                updates = payload["updates"]
            else:
                updates = payload.get("data", {}).get("updates", [])
            for update in updates:
                path = update.get("attrs", {}).get("path", [])
                target = update.get("attrs", {}).get("target_prefix")
                if path and target and path[-1] == 18101:
                    originated_prefixes.add(target)
        except Exception as e:
            print(f"Error reading updates: {e}")
            return

    print(f"Found {len(originated_prefixes)} unique prefixes originated by AS18101.")
    print("Checking for intersections (hijacks)...")

    hijacked_ipv4 = set()
    hijacked_ipv6 = set()

    for p in originated_prefixes:
        try:
            p_net = ipaddress.ip_network(p)
            for t_net in telegram_networks:
                # Check if prefix matches Telegram prefix, is a subnet (more specific),
                # or is a supernet (less specific — covering route).
                if p_net == t_net or p_net.subnet_of(t_net) or t_net.subnet_of(p_net):
                    if ":" in p:
                        hijacked_ipv6.add((p, str(t_net)))
                    else:
                        hijacked_ipv4.add((p, str(t_net)))
        except Exception as e:
            print(f"Error processing prefix {p}: {e}")

    print(f"\nIdentified {len(hijacked_ipv4)} hijacked IPv4 prefixes:")
    for p, parent in sorted(hijacked_ipv4):
        print(f"  {p:<18} | Subnet of Telegram parent: {parent}")

    print(f"\nIdentified {len(hijacked_ipv6)} hijacked IPv6 prefixes:")
    for p, parent in sorted(hijacked_ipv6):
        print(f"  {p:<18} | Subnet of Telegram parent: {parent}")


if __name__ == "__main__":
    download_data()
    analyze_local_data()
