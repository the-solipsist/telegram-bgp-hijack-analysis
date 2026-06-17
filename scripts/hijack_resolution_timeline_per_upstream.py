# NOTE: This script targets a representative 3-prefix subset to establish the temporal bounds
# of the hijack incident:
# 1. 95.161.64.0/20: The first IPv4 prefix hijacked (marking the start of Wave 1 at 07:08:57 UTC).
# 2. 91.108.56.0/22: The last IPv4 prefix hijacked/announced (marking the end/resolution of Phase 1/2).
# 3. 2a0a:f280::/32: The IPv6 parent prefix used as the validation control group.
# For analyzing all 34 hijacked prefixes, run scripts/per_prefix_hijack_lifecycle_all_upstreams.py.
#
# Tracks all 3 direct upstreams (FLAG AS15412, Tata AS4755, Airtel AS9498)
# and produces per-upstream resolution timestamps.

import json
import os
import ipaddress

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
raw_data_dir = os.path.join(repo_root, "data", "raw")

prefix_files = {
    "95.161.64.0/20": os.path.join(raw_data_dir, "95.161.64.0_20_full.json"),
    "91.108.56.0/22": os.path.join(raw_data_dir, "91.108.56.0_22_full.json"),
    "2a0a:f280::/32": os.path.join(raw_data_dir, "2a0a_f280___32_full.json")
}

# All 3 direct upstream ASNs (per count_as18101_hijack_paths_and_upstreams.py results)
DIRECT_UPSTREAMS = {
    15412: "FLAG Telecom",
    4755: "Tata Communications",
    9498: "Bharti Airtel"
}

def main():
    # Load and combine all updates from the prefix-specific files
    updates = []
    seen = set()
    for prefix, path in prefix_files.items():
        if not os.path.exists(path):
            print(f"Prefix update file missing: {path}")
            continue
        with open(path, "r") as f:
            data = json.load(f)
            for u in data.get("data", {}).get("updates", []):
                # We identify unique updates by (timestamp, type, target_prefix, path, source_id)
                path_tuple = tuple(u.get("attrs", {}).get("path", [])) if u.get("attrs") else ()
                key = (
                    u.get("timestamp"),
                    u.get("type"),
                    u.get("attrs", {}).get("target_prefix") if u.get("attrs") else prefix,
                    path_tuple,
                    u.get("attrs", {}).get("source_id") if u.get("attrs") else ""
                )
                if key not in seen:
                    seen.add(key)
                    updates.append(u)

    print(f"Loaded {len(updates)} unique prefix BGP updates.")

    # Track hijack events per upstream: {upstream_asn: [(timestamp, event_type, ...), ...]}
    upstream_hijacks = {asn: [] for asn in DIRECT_UPSTREAMS}
    # Track which (source, target, upstream) currently has a hijack route
    hijacked_sessions = {}  # (source, target) -> upstream_asn

    # Sort updates chronologically
    updates.sort(key=lambda x: x.get("timestamp"))

    for u in updates:
        timestamp = u.get("timestamp")
        utype = u.get("type")
        source = u.get("attrs", {}).get("source_id")
        target = u.get("attrs", {}).get("target_prefix") if u.get("attrs") else None

        if not target:
            continue

        if utype == "A":
            path = u.get("attrs", {}).get("path", [])

            if path and path[-1] == 18101:
                # Check if path normalized has one of our direct upstreams preceding AS18101
                clean_path = []
                for asn in path:
                    if not clean_path or clean_path[-1] != asn:
                        clean_path.append(asn)

                session_key = (source, target)
                upstream_asn = None
                if len(clean_path) >= 2 and clean_path[-2] in DIRECT_UPSTREAMS:
                    upstream_asn = clean_path[-2]

                if upstream_asn is not None:
                    # Session is hijacked via this upstream
                    prev_upstream = hijacked_sessions.get(session_key)
                    if prev_upstream != upstream_asn:
                        if prev_upstream is not None:
                            upstream_hijacks[prev_upstream].append(
                                (timestamp, "HIJACK_END", target, clean_path, source))
                        upstream_hijacks[upstream_asn].append(
                            (timestamp, "HIJACK_START", target, clean_path, source))
                        hijacked_sessions[session_key] = upstream_asn
                    else:
                        upstream_hijacks[upstream_asn].append(
                            (timestamp, "HIJACK_UPDATE", target, clean_path, source))
                else:
                    # Hijacked but via another upstream (not one we track)
                    if session_key in hijacked_sessions:
                        prev = hijacked_sessions.pop(session_key)
                        upstream_hijacks[prev].append(
                            (timestamp, "SWITCH_TO_OTHER", target, clean_path, source))
            else:
                # It's announced, but not originating from 18101 (resolved to legitimate route)
                session_key = (source, target)
                if session_key in hijacked_sessions:
                    prev = hijacked_sessions.pop(session_key)
                    upstream_hijacks[prev].append(
                        (timestamp, "RESOLVED_SWITCH", target, path, source))
        elif utype == "W":
            session_key = (source, target)
            if session_key in hijacked_sessions:
                prev = hijacked_sessions.pop(session_key)
                upstream_hijacks[prev].append(
                    (timestamp, "RESOLVED_WITHDRAWAL", target, [], source))

    # Print per-upstream summary
    print("\n=== MULTI-UPSTREAM BGP HIJACK TIMELINE PROOF ===")

    for upstream_asn, name in DIRECT_UPSTREAMS.items():
        events = upstream_hijacks[upstream_asn]
        if not events:
            print(f"\n--- {name} (AS{upstream_asn}): No hijack events found ---")
            continue

        events.sort(key=lambda x: x[0])

        starts = [e for e in events if e[1] == "HIJACK_START"]
        last_advertisements = [e for e in events if e[1] in ("HIJACK_START", "HIJACK_UPDATE")]
        resolutions = [e for e in events if e[1] in ("RESOLVED_SWITCH", "RESOLVED_WITHDRAWAL")]

        print(f"\n--- {name} (AS{upstream_asn}) ---")
        print(f"  Total hijack events: {len(events)}")
        if starts:
            print(f"  First hijack start: {starts[0][0]} UTC")
        if last_advertisements:
            la = last_advertisements[-1]
            print(f"  Last hijack announcement: {la[0]} UTC (prefix: {la[2]})")
        if resolutions:
            lr = resolutions[-1]
            print(f"  Last resolution: {lr[0]} UTC (event: {lr[1]}, prefix: {lr[2]})")

    # Cross-upstream summary
    print("\n=== CROSS-UPSTREAM SUMMARY ===")
    all_last_resolutions = []
    for upstream_asn, name in DIRECT_UPSTREAMS.items():
        events = upstream_hijacks[upstream_asn]
        resolutions = [e for e in events if e[1] in ("RESOLVED_SWITCH", "RESOLVED_WITHDRAWAL")]
        if resolutions:
            last_res = resolutions[-1]
            all_last_resolutions.append((last_res[0], name, upstream_asn, last_res[1], last_res[2]))

    if all_last_resolutions:
        all_last_resolutions.sort()
        global_last = all_last_resolutions[-1]
        print(f"Global last resolution across all 3 upstreams: {global_last[0]} UTC")
        print(f"  Last upstream to clear: {global_last[1]} (AS{global_last[2]})")
        print(f"  Event type: {global_last[3]}, prefix: {global_last[4]}")

if __name__ == "__main__":
    main()
