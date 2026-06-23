"""
Phase 1: Inventory Indian RIPE Atlas probes by ASN.
Saves probe lists for measurement targeting.
"""
import json, urllib.request, urllib.error, os, sys, time

API_KEY = os.environ.get("RIPE_ATLAS_KEY", "")
if not API_KEY:
    API_KEY = "046ba714-f861-4e3c-b8b8-bae9ac303730"
BASE = "https://atlas.ripe.net/api/v2"

def api_get(path):
    req = urllib.request.Request(f"{BASE}{path}")
    req.add_header("Authorization", f"Key {API_KEY}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

print("=== Inventorying Indian RIPE Atlas Probes ===\n")

probes = []
url = "/probes/?country_code=IN&status=1&page_size=500"
while url:
    data = api_get(url)
    probes.extend(data.get("results", []))
    url = data.get("next")
    if url:
        time.sleep(0.5)

print(f"Total active probes in India: {len(probes)}\n")

by_asn = {}
for p in probes:
    asn = p.get("asn_v4") or 0
    if asn == 0:
        continue
    if asn not in by_asn:
        name = p.get("asn_v4_name") or p.get("asn_v6_name") or f"AS{asn}"
        by_asn[asn] = {"name": name, "probes": []}
    by_asn[asn]["probes"].append({
        "id": p["id"],
        "ipv4": p.get("address_v4") is not None,
        "ipv6": p.get("address_v6") is not None,
        "desc": (p.get("description") or "")[:50],
    })

for asn, info in sorted(by_asn.items()):
    v4 = sum(1 for pr in info["probes"] if pr["ipv4"])
    v6 = sum(1 for pr in info["probes"] if pr["ipv6"])
    ids = ",".join(str(pr["id"]) for pr in info["probes"])
    print(f"AS{asn:>8} ({info['name'][:40]:40s}): {len(info['probes']):2d} probes (v4={v4}, v6={v6}) [{ids}]")

with open("/tmp/indian_probes_by_asn.json", "w") as f:
    json.dump(by_asn, f, indent=2)

print(f"\nSaved probe inventory to /tmp/indian_probes_by_asn.json")
print(f"Total ASNs with probes: {len(by_asn)}")

# Map OONI blockers to probe coverage
ooni_interest = {
    9829: "BSNL",
    17488: "Hathway",
    23860: "Alliance Broadband",
    24309: "ACT Fibernet",
    24560: "Bharti Airtel (BB)",
    45609: "Bharti Airtel (BB)",
    9498: "Bharti Airtel (Mobile)",
    55836: "Reliance Jio",
    133982: "Excitel",
    55577: "ACT",
    55824: "NKN",
    138754: "Kerala Vision",
    133661: "Netplus",
    134674: "Tata Play BB",
    58765: "B Tel",
    38266: "Vodafone Idea",
    17465: "Asianet",
    24186: "RailTel",
    17762: "Tata Teleservices",
}

print(f"\n--- OONI ISP Coverage ---")
for asn, name in sorted(ooni_interest.items()):
    if asn in by_asn:
        print(f"✓ {name} (AS{asn}): {len(by_asn[asn]['probes'])} probes available")
    else:
        print(f"✗ {name} (AS{asn}): NO probes")
