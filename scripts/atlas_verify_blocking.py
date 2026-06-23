#!/usr/bin/env python3
"""Create RIPE Atlas traceroutes for still-blocked ISPs to cross-verify OONI data."""
import json, urllib.request, urllib.error, os, sys, time

API_KEY = os.environ.get("RIPE_ATLAS_KEY", "046ba714-f861-4e3c-b8b8-bae9ac303730")
BASE = "https://atlas.ripe.net/api/v2"

TELEGRAM_IPS = [
    "149.154.167.99",
    "95.161.76.100",
    "149.154.175.50",
]
CONTROL_IP = "1.1.1.1"

# Still-blocked ISPs with Atlas probes, and their OONI status
TARGET_ASNS = {
    "9829": "BSNL",
    "17488": "Hathway",
    "133982": "Excitel",
    "45609": "Airtel (consumer alt)",
    "55824": "NKN",
    "133661": "Netplus",
    "9498": "Airtel (transit)",
}

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


def create_traceroute(target, target_type, asn, description):
    """Create a traceroute measurement for probes in a given ASN."""
    if target_type == "icmp":
        defn = {"type": "traceroute", "af": 4, "target": target, "protocol": "ICMP", "description": description}
    elif target_type == "tcp":
        defn = {"type": "traceroute", "af": 4, "target": target, "protocol": "TCP", "port": 443, "description": description}
    else:
        raise ValueError(f"Unknown type: {target_type}")

    probe_cfg = [{"type": "asn", "value": asn, "requested": 2}]

    payload = {
        "definitions": [defn],
        "probes": probe_cfg,
        "is_oneoff": True,
        "start_time": int(time.time()) + 60,
    }
    try:
        result = api_post("/measurements/", payload)
        raw = result.get("measurements", [])
        if raw and isinstance(raw[0], dict):
            return raw[0].get("id")
        elif raw and isinstance(raw[0], int):
            return raw[0]
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        print(f"    HTTP {e.code}: {body}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"    ERROR: {e}", file=sys.stderr)
        return None


def main():
    with open("data/raw/atlas/atlas_probes_india.json") as f:
        probes_data = json.load(f)

    all_measurements = []

    for asn, name in TARGET_ASNS.items():
        v = probes_data.get(asn, {})
        probes = v.get("probes", [])
        ipv4_probes = [p for p in probes if p.get("ipv4")]
        if not ipv4_probes:
            print(f"AS{asn} ({name}): No IPv4 probes, skipping")
            continue

        print(f"\nAS{asn} ({name}): {len(ipv4_probes)} IPv4 probes available")

        # ICMP traceroute to each Telegram IP
        for ip in TELEGRAM_IPS:
            ip_short = ip.replace(".", "_")
            desc = f"TG-ICMP-AS{asn}-{ip_short}"
            mid = create_traceroute(ip, "icmp", asn, desc)
            if mid:
                all_measurements.append({"id": mid, "asn": asn, "name": name, "target": ip, "type": "icmp"})
                print(f"  ICMP -> {ip}: measurement {mid}")
            time.sleep(0.5)

        # TCP/443 traceroute to first Telegram IP
        ip0 = TELEGRAM_IPS[0].replace(".", "_")
        desc = f"TG-TCP-AS{asn}-{ip0}"
        mid = create_traceroute(TELEGRAM_IPS[0], "tcp", asn, desc)
        if mid:
            all_measurements.append({"id": mid, "asn": asn, "name": name, "target": TELEGRAM_IPS[0], "type": "tcp"})
            print(f"  TCP  -> {TELEGRAM_IPS[0]}: measurement {mid}")
        time.sleep(0.5)

        # Control: ICMP to 1.1.1.1
        desc = f"CTRL-AS{asn}-1_1_1_1"
        mid = create_traceroute(CONTROL_IP, "icmp", asn, desc)
        if mid:
            all_measurements.append({"id": mid, "asn": asn, "name": name, "target": CONTROL_IP, "type": "control"})
            print(f"  CTRL -> {CONTROL_IP}: measurement {mid}")
        time.sleep(0.5)

    # Save measurement IDs
    output = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "measurements": all_measurements,
    }
    with open("data/raw/atlas/atlas_traceroute_measurements_20260623.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nCreated {len(all_measurements)} measurements for {len(TARGET_ASNS)} ASNs")
    print("Saved to data/raw/atlas/atlas_traceroute_measurements_20260623.json")


if __name__ == "__main__":
    main()
