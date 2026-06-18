import urllib.request
import json
import os
from typing import Dict, List, Tuple, Any, Set

def run_rpki_analysis() -> None:
    # We analyze the state at the peak of the hijack
    prefixes_to_test: Dict[str, Tuple[str, str]] = {
        "IPv4": ("95.161.64.0/20", "2026-06-16T16:30:00"),
        "IPv6": ("2a0a:f280::/32", "2026-06-16T17:00:00")
    }

    # Known RPKI-validating networks
    rpki_validators: Dict[int, str] = {
        2914: "NTT",
        174: "Cogent",
        6939: "Hurricane Electric",
        1299: "Telia",
        3257: "GTT",
        7018: "AT&T",
        3320: "Deutsche Telekom",
        7922: "Comcast",
        3491: "PCCW",
        6453: "Tata (Global)",
        12956: "Telefonica"
    }

    raw_data: Dict[str, List[Dict[str, Any]]] = {}
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(repo_root, "data", "raw")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    # Fetch data
    for label, (prefix, ts) in prefixes_to_test.items():
        safe_name = prefix.replace("/", "_").replace(":", "_")
        cache_path = os.path.join(data_dir, f"bgp_state_{safe_name}_peak.json")

        if os.path.exists(cache_path):
            print(f"Reading cached bgp-state for {label} ({prefix}) from {cache_path}...")
            try:
                with open(cache_path, "r") as f:
                    data = json.load(f)
            except Exception as e:
                print(f"  Error reading cache {cache_path}: {e}")
                data = {}
        else:
            url = f"https://stat.ripe.net/data/bgp-state/data.json?resource={prefix}&timestamp={ts}"
            print(f"Querying bgp-state for {label} ({prefix}) at {ts}...")
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req) as response:
                    data = json.loads(response.read().decode())
                # Cache the raw response
                with open(cache_path, "w") as f:
                    json.dump(data, f, indent=2)
                print(f"  Saved raw response to {cache_path}")
            except Exception as e:
                print(f"  Error: {e}")
                data = {}

        raw_data[label] = data.get("data", {}).get("bgp_state", [])
        print(f"  Loaded {len(raw_data[label])} BGP state entries.")

    # Analysis results dictionary
    analysis: Dict[str, Any] = {}

    # Classify paths
    ipv4_states = raw_data.get("IPv4", [])
    ipv6_states = raw_data.get("IPv6", [])

    ipv4_hijacked: List[List[int]] = []
    ipv4_legit: List[List[int]] = []
    ipv4_other: List[List[int]] = []

    for state in ipv4_states:
        path = state.get("path", [])
        if not path:
            continue
        origin = path[-1]
        if origin == 18101:
            ipv4_hijacked.append(path)
        elif origin in (62041, 62014, 59930, 211157, 205103):
            ipv4_legit.append(path)
        else:
            ipv4_other.append(path)

    ipv6_hijacked: List[List[int]] = []
    ipv6_legit: List[List[int]] = []
    ipv6_other: List[List[int]] = []

    for state in ipv6_states:
        path = state.get("path", [])
        if not path:
            continue
        origin = path[-1]
        if origin == 18101:
            ipv6_hijacked.append(path)
        elif origin in (62041, 62014, 59930, 211157, 205103):
            ipv6_legit.append(path)
        else:
            ipv6_other.append(path)

    # Peer ASN helper (first element of path)
    def get_peer_asns(paths: List[List[int]]) -> Set[int]:
        return {path[0] for path in paths if path}

    ipv4_hijacked_peers = get_peer_asns(ipv4_hijacked)
    ipv4_legit_peers = get_peer_asns(ipv4_legit)
    ipv6_hijacked_peers = get_peer_asns(ipv6_hijacked)

    print("\nPeer populations:")
    print(f"  IPv4 hijacked peer ASNs: {len(ipv4_hijacked_peers)}")
    print(f"  IPv4 legitimate peer ASNs: {len(ipv4_legit_peers)}")
    print(f"  IPv6 hijacked peer ASNs: {len(ipv6_hijacked_peers)}")

    # Peer overlaps
    ipv4_hijacked_vs_legit_overlap = ipv4_hijacked_peers.intersection(ipv4_legit_peers)
    ipv6_hijacked_vs_ipv4_legit_overlap = ipv6_hijacked_peers.intersection(ipv4_legit_peers)

    print("\nOverlaps:")
    print(f"  Overlap between IPv4 hijacked and IPv4 legitimate peers: {len(ipv4_hijacked_vs_legit_overlap)}")
    print(f"  Overlap between IPv6 hijacked and IPv4 legitimate peers: {len(ipv6_hijacked_vs_ipv4_legit_overlap)}")

    # Validator presence analysis
    validator_analysis: Dict[str, Dict[str, Any]] = {}
    for asn, name in rpki_validators.items():
        ipv4_legit_count = sum(1 for p in ipv4_legit if asn in p)
        ipv4_hijacked_count = sum(1 for p in ipv4_hijacked if asn in p)
        ipv6_hijacked_count = sum(1 for p in ipv6_hijacked if asn in p)
        
        validator_analysis[name] = {
            "asn": asn,
            "ipv4_legitimate_path_appearances": ipv4_legit_count,
            "ipv4_hijacked_path_appearances": ipv4_hijacked_count,
            "ipv6_hijacked_path_appearances": ipv6_hijacked_count
        }

    # Analyze FLAG (AS15412) propagation and adjacencies
    def get_flag_downstreams(paths: List[List[int]]) -> Dict[int, int]:
        downstreams: Dict[int, int] = {}
        for path in paths:
            if 15412 in path:
                idx = path.index(15412)
                if idx > 0:
                    downstream_asn = path[idx - 1]
                    downstreams[downstream_asn] = downstreams.get(downstream_asn, 0) + 1
        return downstreams

    ipv4_flag_downstreams = get_flag_downstreams(ipv4_hijacked)
    ipv6_flag_downstreams = get_flag_downstreams(ipv6_hijacked)

    print("\nFLAG AS15412 downstream adjacencies in IPv4 hijack:")
    for asn, count in ipv4_flag_downstreams.items():
        v_name = rpki_validators.get(asn, "Non-Validator")
        print(f"  AS{asn} ({v_name}): {count} paths")

    print("\nFLAG AS15412 downstream adjacencies in IPv6 hijack:")
    for asn, count in ipv6_flag_downstreams.items():
        v_name = rpki_validators.get(asn, "Non-Validator")
        print(f"  AS{asn} ({v_name}): {count} paths")

    # Save to analysis dictionary
    analysis["summary"] = {
        "ipv4_total_paths_count": len(ipv4_states),
        "ipv4_hijacked_paths_count": len(ipv4_hijacked),
        "ipv4_legitimate_paths_count": len(ipv4_legit),
        "ipv6_total_paths_count": len(ipv6_states),
        "ipv6_hijacked_paths_count": len(ipv6_hijacked),
        "peer_counts": {
            "ipv4_hijacked_peers_count": len(ipv4_hijacked_peers),
            "ipv4_legit_peers_count": len(ipv4_legit_peers),
            "ipv6_hijacked_peers_count": len(ipv6_hijacked_peers)
        },
        "overlaps": {
            "ipv4_hijacked_vs_legit_count": len(ipv4_hijacked_vs_legit_overlap),
            "ipv6_hijacked_vs_ipv4_legit_count": len(ipv6_hijacked_vs_ipv4_legit_overlap),
            "ipv6_hijacked_vs_ipv4_legit_list": sorted(list(ipv6_hijacked_vs_ipv4_legit_overlap))
        }
    }
    analysis["validator_metrics"] = validator_analysis
    analysis["flag_downstreams"] = {
        "ipv4": {str(k): {"name": rpki_validators.get(k, "Non-Validator"), "count": v} for k, v in ipv4_flag_downstreams.items()},
        "ipv6": {str(k): {"name": rpki_validators.get(k, "Non-Validator"), "count": v} for k, v in ipv6_flag_downstreams.items()}
    }

    # Save to json file
    output_path = os.path.join(repo_root, "data", "rpki_enforcement_analysis.json")
    with open(output_path, "w") as f:
        json.dump(analysis, f, indent=2)
    print(f"\nSaved RPKI enforcement analysis to {output_path}")

if __name__ == "__main__":
    run_rpki_analysis()
