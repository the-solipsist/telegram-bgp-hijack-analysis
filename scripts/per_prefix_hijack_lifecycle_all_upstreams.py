import json
import os
from typing import Any

hijacked_prefixes = [
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
    "2001:b28:f23c::/48",
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

# All 3 direct upstream ASNs (per count_as18101_hijack_paths_and_upstreams.py)
DIRECT_UPSTREAMS = {
    15412: "FLAG",
    4755: "Tata",
    9498: "Airtel"
}

# Set data directories relative to repository root
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_dir = os.path.join(repo_root, "data", "raw")

results: list[tuple[str, str, str, str, str]] = []

for prefix in hijacked_prefixes:
    safe_name = prefix.replace("/", "_").replace(":", "_")
    file_path = os.path.join(data_dir, f"{safe_name}_full.json")

    if not os.path.exists(file_path):
        results.append((prefix, "File Missing", "N/A", "N/A", "N/A"))
        continue

    with open(file_path, "r") as f:
        try:
            data = json.load(f)
        except Exception as e:
            results.append((prefix, f"JSON Error: {e}", "N/A", "N/A", "N/A"))
            continue

    updates = data.get("data", {}).get("updates", [])
    updates.sort(key=lambda x: x.get("timestamp"))

    # Track hijack events per upstream
    upstream_hijack_events: dict[int, list[tuple[str, str, str, list[int]]]] = {asn: [] for asn in DIRECT_UPSTREAMS}
    upstream_resolution_events: dict[int, list[tuple[str, str, str]]] = {asn: [] for asn in DIRECT_UPSTREAMS}
    # Track which upstream currently has each peer in hijack state
    hijacked_peers: dict[str, int] = {}

    for u in updates:
        timestamp = u.get("timestamp")
        utype = u.get("type")
        source = u.get("attrs", {}).get("source_id")
        target = u.get("attrs", {}).get("target_prefix") if u.get("attrs") else prefix

        if utype == "A":
            path = u.get("attrs", {}).get("path", [])

            if source in hijacked_peers:
                # Peer was in hijacked state - check if it still is
                if not path or path[-1] != 18101:
                    # Switched to legitimate route - resolution
                    prev_upstream = hijacked_peers.pop(source)
                    upstream_resolution_events[prev_upstream].append(
                        (timestamp, "RESOLVED_SWITCH", source)
                    )
                else:
                    # Still hijacked - check if upstream changed
                    clean_path: list[int] = []
                    for asn in path:
                        if not clean_path or clean_path[-1] != asn:
                            clean_path.append(asn)
                    if len(clean_path) >= 2 and clean_path[-2] in DIRECT_UPSTREAMS:
                        new_upstream = clean_path[-2]
                        if hijacked_peers.get(source) != new_upstream:
                            prev_upstream = hijacked_peers[source]
                            upstream_resolution_events[prev_upstream].append(
                                (timestamp, "RESOLVED_SWITCH", source)
                            )
                            hijacked_peers[source] = new_upstream
                            upstream_hijack_events[new_upstream].append(
                                (timestamp, "A", source, clean_path)
                            )
                    # If path[-1] is 18101 but upstream not tracked, treat as resolution
                    elif path[-1] == 18101:
                        prev_upstream = hijacked_peers.pop(source)
                        upstream_resolution_events[prev_upstream].append(
                            (timestamp, "RESOLVED_SWITCH", source)
                        )
            else:
                # Peer not in hijacked state - check if this is a new hijack
                if path and path[-1] == 18101:
                    clean_path = []
                    for asn in path:
                        if not clean_path or clean_path[-1] != asn:
                            clean_path.append(asn)
                    if len(clean_path) >= 2 and clean_path[-2] in DIRECT_UPSTREAMS:
                        upstream_asn = clean_path[-2]
                        hijacked_peers[source] = upstream_asn
                        upstream_hijack_events[upstream_asn].append(
                            (timestamp, "A", source, clean_path)
                        )
        elif utype == "W":
            if source in hijacked_peers:
                prev_upstream = hijacked_peers.pop(source)
                upstream_resolution_events[prev_upstream].append(
                    (timestamp, "RESOLVED_WITHDRAWAL", source)
                )

    # Compute per-upstream start/stop for this prefix
    upstream_summaries: dict[str, dict[str, Any]] = {}
    for upstream_asn, upstream_name in DIRECT_UPSTREAMS.items():
        events = upstream_hijack_events[upstream_asn]
        resolutions = upstream_resolution_events[upstream_asn]
        if not events:
            continue
        events.sort(key=lambda x: x[0])
        resolutions.sort(key=lambda x: x[0])
        upstream_summaries[upstream_name] = {
            "first_seen": events[0][0],
            "last_seen": events[-1][0],
            "last_resolution": resolutions[-1][0] if resolutions else "N/A",
            "count": len(events)
        }

    # Compute FLAG-only stats
    flag_events = upstream_hijack_events[15412]
    flag_resolutions = upstream_resolution_events[15412]
    if flag_events:
        anns = [e for e in flag_events if e[1] == "A"]
        if anns:
            start_time = anns[0][0]
            last_adv = anns[-1][0]
        else:
            start_time = "N/A"
            last_adv = "N/A"

        # Resolution time: last resolution event, or last announcement if no resolution
        if flag_resolutions:
            resolution_time = flag_resolutions[-1][0]
        else:
            resolution_time = flag_events[-1][0]

        upstream_str = ", ".join(
            f"{name}={info['count']}" for name, info in upstream_summaries.items()
        )
        status = f"Hijacked ({upstream_str})"
        results.append((prefix, status, start_time, last_adv, resolution_time))
    elif upstream_summaries:
        upstream_str = ", ".join(
            f"{name}={info['count']}" for name, info in upstream_summaries.items()
        )
        first_overall = min(info["first_seen"] for info in upstream_summaries.values())
        last_overall = max(
            info["last_resolution"] if info["last_resolution"] != "N/A" else info["last_seen"]
            for info in upstream_summaries.values()
        )
        status = f"Hijacked (non-FLAG: {upstream_str})"
        results.append((prefix, status, first_overall, last_overall, last_overall))
    else:
        results.append((prefix, "No Hijack Detected", "N/A", "N/A", "N/A"))

print("\n" + "="*80)
print(f"{'Prefix/Sub-prefix':<20} | {'Status':<55} | {'Start (UTC)':<19} | {'Last Event (UTC)':<19}")
print("="*80)
for r in results:
    pref, status, start, last, res = r
    print(f"{pref:<20} | {status:<55} | {start:<19} | {res:<19}")
print("="*80)

# Write output to json file for later consumption
output_file = os.path.join(repo_root, "data", "per_prefix_per_upstream_timeline.json")
with open(output_file, "w") as f:
    json.dump([{
        "prefix": r[0],
        "status": r[1],
        "start_time": r[2],
        "last_announcement": r[3],
        "resolution_time": r[4]
    } for r in results], f, indent=2)
