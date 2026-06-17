import json
import os

# Set file path relative to repository root
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
file_path = os.path.join(repo_root, "data", "raw", "bgp_updates_18101.json")

if not os.path.exists(file_path):
    print(f"Updates file missing at {file_path}! Please run scripts/download_as18101_updates_and_identify_hijacked_prefixes.py first.")
    exit(1)

# The list of 34 unique hijacked prefixes identified during overlap analysis
hijacked_prefixes = {
    "149.154.160.0/22", "149.154.160.0/23", "149.154.160.0/24", "149.154.161.0/24",
    "149.154.162.0/23", "149.154.162.0/24", "149.154.163.0/24", "149.154.164.0/22",
    "149.154.164.0/23", "149.154.164.0/24", "149.154.165.0/24", "149.154.166.0/23",
    "149.154.166.0/24", "149.154.167.0/24", "149.154.168.0/22", "185.76.151.0/24",
    "2001:67c:4e8::/48", "2001:b28:f23c::/48", "2001:b28:f23d::/48", "2001:b28:f23f::/48", "2a0a:f280::/32",
    "91.105.192.0/23", "91.108.10.0/23", "91.108.16.0/22", "91.108.4.0/22",
    "91.108.4.0/23", "91.108.56.0/22", "91.108.56.0/23", "91.108.6.0/23",
    "91.108.8.0/22", "91.108.8.0/23", "95.161.64.0/20", "95.161.64.0/21",
    "95.161.72.0/21"
}

with open(file_path, "r") as f:
    try:
        data = json.load(f)
    except Exception as e:
        print(f"Error reading JSON: {e}")
        exit(1)

updates = data.get("data", {}).get("updates", [])
print(f"Total BGP updates loaded: {len(updates)}")

unique_paths = set()
for update in updates:
    target = update.get("attrs", {}).get("target_prefix")
    # Filter: ONLY analyze paths for prefixes that are part of the Telegram hijack
    if target in hijacked_prefixes:
        path = update.get("attrs", {}).get("path", [])
        if path and path[-1] == 18101:
            # Normalize prepended paths (e.g. [18101, 18101, 18101] -> [18101])
            clean_path: list[int] = []
            for asn in path:
                if not clean_path or clean_path[-1] != asn:
                    clean_path.append(asn)
            
            # BGP path is stored as [receiver, ..., origin]
            # Reverse to get [origin (18101), transit, ..., receiver]
            reversed_path = list(reversed(clean_path))
            unique_paths.add(tuple(reversed_path))

print(f"Total unique BGP paths originated by AS18101 for Telegram prefixes: {len(unique_paths)}")

# 1. Direct Upstreams (1st hop after AS18101)
direct_upstreams = set()
for path in unique_paths:
    if len(path) > 1:
        direct_upstreams.add(path[1])

# 2. Second-Tier Transits (2nd hop after AS18101)
tier2_transits = set()
for path in unique_paths:
    if len(path) > 2:
        tier2_transits.add(path[2])

# 3. Affected Downstreams (The final receiver / peer reporting the path)
downstreams = set()
for path in unique_paths:
    downstreams.add(path[-1])

print("\n=== DIRECT UPSTREAMS (1st Hop) ===")
for asn in sorted(direct_upstreams):
    print(f"AS{asn}")

print("\n=== SECOND-TIER TRANSITS (2nd Hop) ===")
print(f"Total: {len(tier2_transits)}")
print(", ".join(f"AS{asn}" for asn in sorted(tier2_transits)))

print("\n=== AFFECTED DOWNSTREAMS (Final Receivers) ===")
print(f"Total Unique Networks Affected: {len(downstreams)}")
# Print first 20 as sample
print("Sample of first 20:")
print(", ".join(f"AS{asn}" for asn in sorted(downstreams)[:20]))
