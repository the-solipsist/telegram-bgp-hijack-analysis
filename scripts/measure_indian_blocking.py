"""
Measure Indian ISP blocking of Telegram IPs using RIPE Atlas probes.

Creates ping measurements from Indian probes (grouped by ASN/ISP) to
Telegram IPs and control IPs, then analyzes which ISPs are blocking
at the routing layer.
"""
import urllib.request
import json
import os
import time
import sys
from typing import Dict, List, Any

ATLAS_API = "https://atlas.ripe.net/api/v2"
API_KEY = os.environ.get("RIPE_ATLAS_KEY")
if not API_KEY:
    print("Error: Set RIPE_ATLAS_KEY environment variable")
    sys.exit(1)


def api_get(path: str) -> Any:
    req = urllib.request.Request(f"{ATLAS_API}{path}")
    req.add_header("Authorization", f"Key {API_KEY}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def api_post(path: str, data: dict) -> Any:
    req = urllib.request.Request(
        f"{ATLAS_API}{path}",
        data=json.dumps(data).encode(),
        method="POST"
    )
    req.add_header("Authorization", f"Key {API_KEY}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def get_indian_probes_by_asn() -> Dict[int, Dict[str, Any]]:
    print("\n=== Phase 1: Finding Indian probes ===")
    probes = []
    url = "/probes/?country_code=IN&status=1&page_size=500"
    while url:
        data = api_get(url)
        probes.extend(data.get("results", []))
        url = data.get("next")
    print(f"Total connected Indian probes: {len(probes)}")

    by_asn: Dict[int, Dict[str, Any]] = {}
    for p in probes:
        asn = p.get("asn_v4") or p.get("asn_v6") or 0
        if asn == 0:
            continue
        if asn not in by_asn:
            by_asn[asn] = {
                "name": p.get("asn_v4_name") or p.get("asn_v6_name") or f"AS{asn}",
                "probes": []
            }
        by_asn[asn]["probes"].append({
            "id": p["id"],
            "ipv4": p.get("is_ipv4", False),
            "ipv6": p.get("is_ipv6", False),
            "description": p.get("description", ""),
        })
    for asn, info in sorted(by_asn.items()):
        print(f"  AS{asn} ({info['name']}): {len(info['probes'])} probes")
    return by_asn


# Telegram IPs to test
TG_TARGETS = {
    "91.108.56.1": 4,
    "95.161.64.1": 4,
    "149.154.167.99": 4,
    "2a0a:f280:203::1": 6,
}
CONTROL_TARGETS = {
    "1.1.1.1": 4,
    "2606:4700:4700::1111": 6,
}
DNS_CHECK_HOST = "telegram.org"


def fetch_existing_measurements() -> set:
    existing = set()
    url = "/measurements/?page_size=1000"
    while url:
        data = api_get(url)
        for m in data.get("results", []):
            existing.add(m["id"])
        url = data.get("next")
    return existing


def create_measurements(target_ips: Dict[str, int], asns: List[int], duration: int = 600) -> List[Dict]:
    print(f"\n=== Phase 2: Creating measurements ===")
    measurements = []
    for target, af in target_ips.items():
        for asn in asns:
            desc = f"TG-bgp-hijack-AS{asn}-{target}-{'v6' if af == 6 else 'v4'}"
            definition = {
                "type": "ping",
                "af": af,
                "target": target,
                "interval": 240,
                "description": desc,
            }
            payload = {
                "definitions": [definition],
                "probes": [
                    {"type": "asn", "value": str(asn), "requested": 99}
                ],
            }
            print(f"  Creating: {desc}")
            try:
                result = api_post("/measurements/", payload)
                meas_id = result.get("measurements", [{}])[0].get("id")
                if meas_id:
                    print(f"    ID: {meas_id}")
                    measurements.append({
                        "id": meas_id,
                        "target": target,
                        "af": af,
                        "asn": asn,
                        "description": desc
                    })
            except urllib.error.HTTPError as e:
                body = e.read().decode()
                print(f"    Error: {e.code} - {body[:150]}")
    return measurements


def wait_for_results(measurements: List[Dict]) -> Dict[int, Any]:
    print(f"\n=== Phase 3: Fetching results ===")
    results = {}
    for m in measurements:
        meas_id = m["id"]
        print(f"  Fetching measurement {meas_id} ({m['description']})...")
        try:
            data = api_get(f"/measurements/{meas_id}/results/")
            results[meas_id] = data
            # Print summary
            asn_results = {}
            for r in data if isinstance(data, list) else [data]:
                if isinstance(r, dict):
                    for probe_info in r.get("reports", [r]):
                        probe_asn = probe_info.get("probe_asn", m["asn"])
                        if probe_asn not in asn_results:
                            asn_results[probe_asn] = {"ok": 0, "fail": 0}
                        if probe_info.get("min_rtt") is not None and probe_info.get("max_rtt") is not None:
                            asn_results[probe_asn]["ok"] += 1
                        else:
                            asn_results[probe_asn]["fail"] += 1
            print(f"    Results: {asn_results}")
        except urllib.error.HTTPError as e:
            print(f"    Error: {e.code}")
            results[meas_id] = None
        time.sleep(0.5)
    return results


def analyze_results(by_asn: Dict, results: Dict, measurements: List[Dict]) -> Dict:
    print(f"\n=== Phase 4: Analysis ===")
    blocking = {}
    return blocking


def main():
    api_get("/credits/")  # verify auth
    probes_by_asn = get_indian_probes_by_asn()
    # Focus on consumer ISPs (exclude cloud/data-center ASNs)
    target_asns = [9498, 24560, 45609, 9829, 55836, 24309, 23860,
                   133982, 138754, 45184, 132423, 136342, 137153]
    existing_ids = fetch_existing_measurements()
    print(f"Existing measurements: {len(existing_ids)}")
    measurements = []
    measurements.extend(create_measurements(TG_TARGETS, target_asns, 600))
    measurements.extend(create_measurements(CONTROL_TARGETS, target_asns, 600))
    print(f"\nCreated {len(measurements)} measurements")
    wait_for_results(measurements)
    print("\nDone.")


if __name__ == "__main__":
    main()
