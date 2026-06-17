# Downloads raw prefix-specific BGP updates from RIPE Stat API with proper pagination.
#
# IMPORTANT: For very large time windows or busy prefixes, the RIPE Stat API may
# truncate responses and provide continuation URLs in the 'see_also' field.
# This script handles pagination transparently: it follows all 'see_also' URLs
# and merges the updates into a single output file per prefix.
#
# It also verifies that the response covers the full requested window by checking
# the 'query_endtime' field against the requested end time. If the server-returned
# end time is significantly earlier than requested, the script prints a warning.

import urllib.request
import json
import os
import sys

prefixes = [
    "149.154.160.0/22",
    "149.154.160.0/23",
    "149.154.160.0/24",
    "149.154.161.0/24",
    "149.154.162.0/23",
    "149.154.162.0/24",
    "149.154.163.0/24",
    "149.154.164.0/22",
    "149.154.164.0/23",
    "149.154.164.0/24",
    "149.154.165.0/24",
    "149.154.166.0/23",
    "149.154.166.0/24",
    "149.154.167.0/24",
    "149.154.168.0/22",
    "185.76.151.0/24",
    "2001:67c:4e8::/48",
    "2001:b28:f23d::/48",
    "2001:b28:f23f::/48",
    "2a0a:f280::/32",
    "91.105.192.0/23",
    "91.108.10.0/23",
    "91.108.16.0/22",
    "91.108.4.0/22",
    "91.108.4.0/23",
    "91.108.56.0/22",
    "91.108.56.0/23",
    "91.108.6.0/23",
    "91.108.8.0/22",
    "91.108.8.0/23",
    "95.161.64.0/20",
    "95.161.64.0/21",
    "95.161.72.0/21"
]

# Set data directory relative to repository root
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_dir = os.path.join(repo_root, "data", "raw")
if not os.path.exists(data_dir):
    os.makedirs(data_dir)

start_time = "2026-06-16T07:00:00"
end_time = "2026-06-17T06:00:00"

BASE_URL = "https://stat.ripe.net/data/bgp-updates/data.json"

def fetch_with_pagination(url, max_pages=50):
    """Fetch a RIPE Stat API response and follow 'see_also' continuations.

    Returns the merged JSON dict. Raises RuntimeError if pagination exceeds max_pages.
    """
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

        # Capture query metadata from the first page
        data_section = payload.get("data", {})
        if resource is None:
            resource = data_section.get("resource")
            first_query_starttime = data_section.get("query_starttime")
        last_query_endtime = data_section.get("query_endtime")

        updates = data_section.get("updates", [])
        merged_updates.extend(updates)

        # Pagination: see_also contains continuation URLs
        see_also = payload.get("see_also") or []
        url = see_also[0] if see_also else None

    return {
        "resource": resource,
        "query_starttime": first_query_starttime,
        "query_endtime": last_query_endtime,
        "updates": merged_updates,
        "page_count": page_count
    }


for prefix in prefixes:
    safe_name = prefix.replace("/", "_").replace(":", "_")
    file_path = os.path.join(data_dir, f"{safe_name}_full.json")
    url = f"{BASE_URL}?resource={prefix}&starttime={start_time}&endtime={end_time}"
    print(f"Downloading BGP updates for {prefix} from {start_time} to {end_time}...")
    try:
        result = fetch_with_pagination(url)
        if result["query_endtime"] and result["query_endtime"] < end_time:
            print(f"  WARNING: Server returned query_endtime={result['query_endtime']}, "
                  f"requested {end_time}. Data may still be incomplete.")
        with open(file_path, "w") as f:
            json.dump({"data": result}, f, indent=2)
        print(f"  Saved {len(result['updates'])} updates ({result['page_count']} page(s)) to {file_path}")
    except Exception as e:
        print(f"  Error downloading {prefix}: {e}")
        sys.exit(1)
