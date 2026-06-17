import json
import os
from typing import Any, Set, Dict, List

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
    "2a0a:f280::/48",
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

HIJACK_ASNS = {18101, 45820}

# All direct upstream ASNs (including F5 AS35280 for the Tata leak)
DIRECT_UPSTREAMS = {
    15412: "FLAG",
    4755: "Tata",
    9498: "Airtel",
    35280: "F5"
}

TELEGRAM_ASNS = {62041, 62014, 59930, 211157, 205103, 44907}

# Set data directories relative to repository root
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_dir = os.path.join(repo_root, "data", "raw")

results: List[Tuple[str, str, str, str, str]] = []

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
    upstream_hijack_events: Dict[int, List[Tuple[str, str, str, List[int]]]] = {asn: [] for asn in DIRECT_UPSTREAMS}
    upstream_resolution_events: Dict[int, List[Tuple[str, str, str]]] = {asn: [] for asn in DIRECT_UPSTREAMS}
    
    # Track which upstream currently has each peer in hijack state
    hijacked_peers: Dict[str, int] = {}
    
    # Track peers that are unresolved (hijacked but not yet resolved to Telegram or withdrawn)
    unresolved_peers: Set[str] = set()

    for u in updates:
        timestamp = u.get("timestamp")
        utype = u.get("type")
        source = u.get("attrs", {}).get("source_id")
        target = u.get("attrs", {}).get("target_prefix") if u.get("attrs") else prefix

        if not source:
            continue

        if utype == "A":
            path = u.get("attrs", {}).get("path", [])

            if source in hijacked_peers:
                # Peer was in hijacked state - check if it still is
                if path and path[-1] in HIJACK_ASNS:
                    # Still hijacked - check if upstream changed
                    clean_path: List[int] = []
                    for asn in path:
                        if not clean_path or clean_path[-1] != asn:
                            clean_path.append(asn)
                    if len(clean_path) >= 2 and clean_path[-2] in DIRECT_UPSTREAMS:
                        new_upstream = clean_path[-2]
                        if hijacked_peers[source] != new_upstream:
                            prev_upstream = hijacked_peers[source]
                            upstream_resolution_events[prev_upstream].append(
                                (timestamp, "RESOLVED_SWITCH", source)
                            )
                            hijacked_peers[source] = new_upstream
                            upstream_hijack_events[new_upstream].append(
                                (timestamp, "A", source, clean_path)
                            )
                    # If path[-1] is in HIJACK_ASNS but upstream not tracked, treat as resolution for that upstream
                    else:
                        prev_upstream = hijacked_peers.pop(source)
                        upstream_resolution_events[prev_upstream].append(
                            (timestamp, "RESOLVED_SWITCH", source)
                        )
                elif path and path[-1] in TELEGRAM_ASNS:
                    # Switched to legitimate route - resolution
                    prev_upstream = hijacked_peers.pop(source)
                    upstream_resolution_events[prev_upstream].append(
                        (timestamp, "RESOLVED_SWITCH", source)
                    )
                    unresolved_peers.discard(source)
                else:
                    # Switched to another ASN or path is empty
                    # Not a legitimate resolution, just pop from active hijack tracking
                    prev_upstream = hijacked_peers.pop(source)
            else:
                # Peer not in hijacked state - check if this is a new hijack
                if path and path[-1] in HIJACK_ASNS:
                    clean_path = []
                    for asn in path:
                        if not clean_path or clean_path[-1] != asn:
                            clean_path.append(asn)
                    if len(clean_path) >= 2 and clean_path[-2] in DIRECT_UPSTREAMS:
                        upstream_asn = clean_path[-2]
                        hijacked_peers[source] = upstream_asn
                        unresolved_peers.add(source)
                        upstream_hijack_events[upstream_asn].append(
                            (timestamp, "A", source, clean_path)
                        )
        elif utype == "W":
            if source in hijacked_peers:
                prev_upstream = hijacked_peers.pop(source)
                upstream_resolution_events[prev_upstream].append(
                    (timestamp, "RESOLVED_WITHDRAWAL", source)
                )
                unresolved_peers.discard(source)

    # Compute per-upstream start/stop for this prefix
    upstream_summaries: Dict[str, Dict[str, Any]] = {}
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

        upstream_str = ", ".join(
            f"{name}={info['count']}" for name, info in upstream_summaries.items()
        )
        
        if unresolved_peers:
            status = f"Hijacked (Unresolved: {upstream_str})"
            resolution_time = "Unresolved"
        else:
            status = f"Hijacked ({upstream_str})"
            # Resolution time: last resolution event, or last announcement if no resolution
            if flag_resolutions:
                resolution_time = flag_resolutions[-1][0]
            else:
                resolution_time = flag_events[-1][0]

        results.append((prefix, status, start_time, last_adv, resolution_time))
    elif upstream_summaries:
        upstream_str = ", ".join(
            f"{name}={info['count']}" for name, info in upstream_summaries.items()
        )
        first_overall = min(info["first_seen"] for info in upstream_summaries.values())
        
        last_overall = max(info["last_seen"] for info in upstream_summaries.values())
        if unresolved_peers:
            status = f"Hijacked (Unresolved: {upstream_str})"
            resolution_time = "Unresolved"
        else:
            status = f"Hijacked (non-FLAG: {upstream_str})"
            resolution_time = max(
                info["last_resolution"] if info["last_resolution"] != "N/A" else info["last_seen"]
                for info in upstream_summaries.values()
            )
            
        results.append((prefix, status, first_overall, last_overall, resolution_time))
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
