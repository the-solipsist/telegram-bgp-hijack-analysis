import urllib.request
import json
import os

# We want to check the state at two key timestamps:
# 1. Wave 1 Peak (e.g. 08:30:00 UTC)
# 2. Wave 2 Peak (e.g. 16:30:00 UTC)

tests = [
    # Prefix, Timestamp, Name
    ("95.161.64.0/20", "2026-06-16T08:30:00", "Wave 1 Peak (95.161.64.0/20)"),
    ("95.161.64.0/20", "2026-06-16T16:30:00", "Wave 2 Peak (95.161.64.0/20)"),
    ("91.108.56.0/22", "2026-06-16T08:30:00", "Wave 1 Peak (91.108.56.0/22)"),
    ("91.108.56.0/22", "2026-06-16T16:30:00", "Wave 2 Peak (91.108.56.0/22)"),
    ("91.108.56.0/23", "2026-06-16T16:30:00", "Wave 2 Peak Sub-prefix (91.108.56.0/23)"),
    ("2a0a:f280::/32", "2026-06-16T17:00:00", "IPv6 Hijack Peak (2a0a:f280::/32)")
]

results = []

for prefix, ts, label in tests:
    url = f"https://stat.ripe.net/data/bgp-state/data.json?resource={prefix}&timestamp={ts}"
    print(f"\nQuerying bgp-state for {label} at {ts}...")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            
        bgp_state = data.get("data", {}).get("bgp_state", [])
        total_peers = len(bgp_state)
        
        hijacked_peers = 0
        legit_peers = 0
        other_peers = 0
        
        origins = {}
        
        for state in bgp_state:
            path = state.get("path", [])
            if path:
                origin = path[-1]
                origins[origin] = origins.get(origin, 0) + 1
                if origin == 18101:
                    hijacked_peers += 1
                elif origin in (62041, 62014, 59930, 211157, 205103):
                    legit_peers += 1
                else:
                    other_peers += 1
                    
        print(f"  Total active peers reporting: {total_peers}")
        print(f"  Hijacked peers (AS18101 origin): {hijacked_peers} ({hijacked_peers/total_peers:.2%})")
        print(f"  Legitimate peers (Telegram origin): {legit_peers} ({legit_peers/total_peers:.2%})")
        print(f"  Other peers: {other_peers} ({other_peers/total_peers:.2%})")
        print(f"  Origin distribution: {origins}")
        
        results.append({
            "label": label,
            "prefix": prefix,
            "timestamp": ts,
            "total_reporting_peers": total_peers,
            "hijacked_peers_count": hijacked_peers,
            "hijacked_visibility_pct": hijacked_peers / total_peers if total_peers > 0 else 0,
            "legitimate_peers_count": legit_peers,
            "legitimate_visibility_pct": legit_peers / total_peers if total_peers > 0 else 0,
            "origin_asn_distribution": origins
        })
    except Exception as e:
        print(f"  Error querying: {e}")

# Save the queried snapshot data to a JSON file in the data folder
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
output_path = os.path.join(repo_root, "data", "route_visibility_snapshots.json")
with open(output_path, "w") as f:
    json.dump(results, f, indent=2)
print(f"\nSaved visibility snapshot to {output_path}")
