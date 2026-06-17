# Analyzes FLAG/Tata/Airtel filtering reactions to the RCom hijack.
#
# Updated to track all 3 direct upstreams (FLAG AS15412, Tata AS4755, Airtel AS9498)
# rather than FLAG-only.

import json
import os

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
raw_data_dir = os.path.join(repo_root, "data", "raw")

prefix_files = {
    "95.161.64.0/20": os.path.join(raw_data_dir, "95.161.64.0_20_full.json"),
    "91.108.56.0/22": os.path.join(raw_data_dir, "91.108.56.0_22_full.json"),
    "2a0a:f280::/32": os.path.join(raw_data_dir, "2a0a_f280___32_full.json")
}

# All 3 direct upstream ASNs
DIRECT_UPSTREAMS = {
    15412: "FLAG",
    4755: "Tata",
    9498: "Airtel"
}

for prefix, file_path in prefix_files.items():
    print("\n==========================================")
    print(f"Prefix: {prefix}")
    print("==========================================")

    with open(file_path, "r") as f:
        data = json.load(f)

    updates = data.get("data", {}).get("updates", [])

    # Track hijack state per upstream
    peer_upstream_states: dict[str, int] = {}  # source -> current upstream_asn (if hijacked)
    upstream_anns: dict[int, list[tuple[str, str, list[int]]]] = {asn: [] for asn in DIRECT_UPSTREAMS}
    upstream_wids: dict[int, list[tuple[str, str, list[int]]]] = {asn: [] for asn in DIRECT_UPSTREAMS}
    # type matches (timestamp, event_type, source, path)
    upstream_switches: dict[int, list[tuple[str, str, str, list[int]]]] = {asn: [] for asn in DIRECT_UPSTREAMS}

    for u in updates:
        timestamp = u.get("timestamp")
        utype = u.get("type")
        source = u.get("attrs", {}).get("source_id")

        if utype == "A":
            path = u.get("attrs", {}).get("path", [])

            if path and path[-1] == 18101:
                clean_path: list[int] = []
                for asn in path:
                    if not clean_path or clean_path[-1] != asn:
                        clean_path.append(asn)

                if len(clean_path) >= 2 and clean_path[-2] in DIRECT_UPSTREAMS:
                    upstream_asn = clean_path[-2]
                    prev_upstream = peer_upstream_states.get(source)
                    if prev_upstream is not None and prev_upstream != upstream_asn:
                        # Switched between upstreams
                        upstream_switches[prev_upstream].append(
                            (timestamp, "SWITCH_TO_OTHER_UPSTREAM", source, clean_path))
                    peer_upstream_states[source] = upstream_asn
                    upstream_anns[upstream_asn].append((timestamp, source, clean_path))
                else:
                    # Hijacked via non-tracked upstream; if was hijacked via tracked, drop
                    prev = peer_upstream_states.pop(source, None)
                    if prev is not None:
                        upstream_switches[prev].append(
                            (timestamp, "SWITCH_TO_NON_TRACKED", source, clean_path))
            else:
                # Switched to legitimate route
                prev = peer_upstream_states.pop(source, None)
                if prev is not None:
                    upstream_switches[prev].append((timestamp, "SWITCH_TO_LEGIT", source, path))

        elif utype == "W":
            prev = peer_upstream_states.pop(source, None)
            if prev is not None:
                upstream_wids[prev].append((timestamp, source, []))

    # Print per-upstream summary
    for upstream_asn, upstream_name in DIRECT_UPSTREAMS.items():
        ann_count = len([x for x in upstream_anns[upstream_asn] if x[0] >= '2026-06-16T15:00:00'])
        wid_count = len([x for x in upstream_wids[upstream_asn] if x[0] >= '2026-06-16T15:00:00'])
        sw_count = len([x for x in upstream_switches[upstream_asn] if x[0] >= '2026-06-16T15:00:00'])
        total_count = len(upstream_anns[upstream_asn])

        print(f"\n  --- {upstream_name} (AS{upstream_asn}) ---")
        print(f"    Total hijack announcements: {total_count}")
        print(f"    After 15:00 UTC: {ann_count} announcements, {wid_count} withdrawals, {sw_count} switches")

        if upstream_anns[upstream_asn]:
            last_ann = sorted(upstream_anns[upstream_asn], key=lambda x: x[0])[-1]
            print(f"    Last announcement: {last_ann[0]} | Peer: {last_ann[1]}")
