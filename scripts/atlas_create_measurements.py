"""
Phase 2: Create RIPE Atlas measurements to characterize Telegram blocking in India.

Measurement plan:
  A. ICMP traceroute to Telegram IPv4 targets from each ISP
  B. TCP traceroute (port 443) to Telegram IPv4 targets from each ISP
  C. ICMP traceroute to 1.1.1.1 (control) from each ISP
  D. DNS A queries for telegram.org from each ISP (system resolver)
  E. ICMP traceroute to Telegram IPv6 target from IPv6-capable probes

Output: /tmp/atlas_traceroute_measurements_20260623.json
"""
import json, urllib.request, urllib.error, os, sys, time

API_KEY = os.environ.get("RIPE_ATLAS_KEY", "046ba714-f861-4e3c-b8b8-bae9ac303730")
BASE = "https://atlas.ripe.net/api/v2"

def api_post(path, data):
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(data).encode(),
        method="POST",
    )
    req.add_header("Authorization", f"Key {API_KEY}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def create_measurement(defn, probes, description):
    payload = {
        "definitions": [defn],
        "probes": probes,
        "is_oneoff": True,
        "start_time": int(time.time()) + 300,
    }
    desc_short = description[:80]
    print(f"  Creating: {desc_short}")
    try:
        result = api_post("/measurements/", payload)
        raw = result.get("measurements", [])
        if raw and isinstance(raw[0], dict):
            meas_id = raw[0].get("id")
        elif raw and isinstance(raw[0], int):
            meas_id = raw[0]
        else:
            meas_id = None
        if meas_id:
            print(f"    -> ID: {meas_id}")
            return {"id": meas_id, "description": desc_short, "definition": defn}
        else:
            print(f"    -> No ID in response: {json.dumps(result)[:200]}")
            return None
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"    -> Error {e.code}: {body[:300]}")
        return None
    except Exception as e:
        print(f"    -> Error: {e}")
        return None


# Load probe inventory
with open("/tmp/indian_probes_by_asn.json") as f:
    by_asn = json.load(f)

TARGET_ASNS = {
    "9829":   "BSNL",
    "17488":  "Hathway",
    "23860":  "Alliance Broadband",
    "24309":  "ACT Fibernet",
    "138754": "Kerala Vision",
    "133661": "Netplus",
    "134674": "Tata Play BB",
    "58765":  "B Tel",
    "24560":  "Airtel BB",
    "45609":  "Airtel BB2",
    "55836":  "Reliance Jio",
    "133982": "Excitel",
    "55577":  "ACT DNS",
    "55824":  "NKN",
    "9498":   "Airtel Mobile",
}

TG_V4 = ["91.108.56.1", "149.154.167.99"]
CONTROL_V4 = "1.1.1.1"
TG_V6 = "2a0a:f280:203::1"

created = []
total = 0

for asn_str, label in sorted(TARGET_ASNS.items()):
    info = by_asn.get(asn_str, {})
    probes_list = info.get("probes", [])
    if not probes_list:
        print(f"\n[{label} AS{asn_str}] SKIP - no probes\n")
        continue
    has_ipv6 = any(p.get("ipv6", False) for p in probes_list)
    pcfg = [{"type": "asn", "value": asn_str, "requested": 3}]

    pids = [p["id"] for p in probes_list]
    print(f"\n{'='*60}")
    print(f"[{label} AS{asn_str}] {len(probes_list)} probes: {pids[:4]}...")

    # A. ICMP traceroute to Telegram v4
    for t in TG_V4:
        d = {"type": "traceroute", "af": 4, "target": t,
             "protocol": "ICMP", "description": f"TG-ICMP-{label}-{t}"}
        m = create_measurement(d, pcfg, f"ICMP trace {label} -> {t}")
        if m: created.append(m); total += 1
        time.sleep(1)

    # B. TCP traceroute (port 443) to Telegram v4
    for t in TG_V4:
        d = {"type": "traceroute", "af": 4, "target": t,
             "protocol": "TCP", "port": 443,
             "description": f"TG-TCP-{label}-{t}"}
        m = create_measurement(d, pcfg, f"TCP:443 trace {label} -> {t}")
        if m: created.append(m); total += 1
        time.sleep(1)

    # C. Control ICMP traceroute to 1.1.1.1
    d = {"type": "traceroute", "af": 4, "target": CONTROL_V4,
         "protocol": "ICMP", "description": f"CTRL-ICMP-{label}-cf"}
    m = create_measurement(d, pcfg, f"ICMP trace {label} -> {CONTROL_V4} (control)")
    if m: created.append(m); total += 1
    time.sleep(1)

    # D. DNS A for telegram.org via system resolver
    d = {"type": "dns", "af": 4, "query_class": "IN",
         "query_type": "A", "query_argument": "telegram.org",
         "protocol": "UDP", "set_rd_bit": True,
         "use_probe_resolver": True,
         "description": f"TG-DNS-A-{label}"}
    m = create_measurement(d, pcfg, f"DNS A telegram.org from {label}")
    if m: created.append(m); total += 1
    time.sleep(1)

    # DNS AAAA for telegram.org (v6 probes only)
    if has_ipv6:
        d = {"type": "dns", "af": 6, "query_class": "IN",
             "query_type": "AAAA", "query_argument": "telegram.org",
             "protocol": "UDP", "set_rd_bit": True,
             "use_probe_resolver": True,
             "description": f"TG-DNS-AAAA-{label}"}
        m = create_measurement(d, pcfg, f"DNS AAAA telegram.org from {label}")
        if m: created.append(m); total += 1
        time.sleep(1)

    # E. IPv6 ICMP traceroute
    if has_ipv6:
        d = {"type": "traceroute", "af": 6, "target": TG_V6,
             "protocol": "ICMP", "description": f"TG-ICMP6-{label}"}
        m = create_measurement(d, pcfg, f"ICMPv6 trace {label} -> {TG_V6}")
        if m: created.append(m); total += 1
        time.sleep(1)

print(f"\n{'='*60}")
print(f"Total measurements created: {total}")

with open("/tmp/atlas_measurements_created.json", "w") as f:
    json.dump(created, f, indent=2)
print("Saved to /tmp/atlas_measurements_created.json")

with open("/tmp/atlas_measurements_created_summary.txt", "w") as f:
    for m in created:
        f.write(f"{m['id']:>8}  {m['description']}\n")
print("Saved to /tmp/atlas_measurements_created_summary.txt")
