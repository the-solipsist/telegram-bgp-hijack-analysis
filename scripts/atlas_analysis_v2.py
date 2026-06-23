"""
Phase 5: Final analysis with proper label extraction.
"""
import json, urllib.request, os, time

API_KEY = os.environ.get("RIPE_ATLAS_KEY", "046ba714-f861-4e3c-b8b8-bae9ac303730")
BASE = "https://atlas.ripe.net/api/v2"

def api_get(path):
    req = urllib.request.Request(f"{BASE}{path}")
    req.add_header("Authorization", f"Key {API_KEY}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read())

with open("/tmp/atlas_measurements_created.json") as f:
    measurements = json.load(f)

# Fetch any missing results
RESULTS_FILE = "/tmp/atlas_results/all_results_raw.json"
if os.path.exists(RESULTS_FILE):
    with open(RESULTS_FILE) as f:
        all_data = json.load(f)
else:
    all_data = {}

print(f"Loaded {len(all_data)} cached results\n")

def extract_label_and_target(desc, defn):
    """Extract ISP label and measurement target from description."""
    mtype = defn.get("type", "")
    target = defn.get("target", defn.get("query_argument", "?"))
    # Descriptions: "ICMP trace BSNL -> 91.108.56.1"
    #               "TCP:443 trace BSNL -> ..."
    #               "DNS A telegram.org from BSNL"
    #               "ICMPv6 trace BSNL -> ..."
    if " -> " in desc:
        left = desc.split(" -> ")[0]
        # left is like "ICMP trace BSNL" or "TCP:443 trace BSNL" or "ICMPv6 trace BSNL"
        if "trace " in left:
            label = left.split("trace ", 1)[1]
        else:
            label = left
    elif " from " in desc:
        label = desc.split("from ", 1)[1]
    else:
        label = desc
    if target == "1.1.1.1":
        target = "1.1.1.1 (control)"
    return label.strip(), target


def analyze_traceroute(results):
    """Return analysis dict."""
    if not isinstance(results, list) or len(results) == 0:
        return None
    # Aggregate across all probes
    all_hops = []
    for report in results:
        if not isinstance(report, dict):
            continue
        hops = report.get("result", [])
        if not isinstance(hops, list):
            continue
        last_ip = None
        last_n = 0
        for hop in hops:
            n = hop.get("hop", 0)
            for r in hop.get("result", []):
                if isinstance(r, dict) and r.get("from"):
                    last_ip = r["from"]
                    last_n = n
        dst = report.get("dst_addr", "")
        all_hops.append({
            "probe_id": report.get("prb_id", "?"),
            "completed": last_ip == dst,
            "hop_count": last_n,
            "last_ip": last_ip,
            "dst": dst,
        })
    return all_hops


def analyze_dns(results):
    """Return analysis dict."""
    if not isinstance(results, list) or len(results) == 0:
        return None
    all_answers = []
    for report in results:
        if not isinstance(report, dict):
            continue
        probe_id = report.get("prb_id", "?")
        result_list = report.get("result", [])
        answers = []
        rcode = None
        for r in result_list if isinstance(result_list, list) else []:
            if isinstance(r, dict):
                if "A" in r and r["A"]:
                    answers.append(r["A"])
                if r.get("rcode") is not None:
                    rcode = r["rcode"]
        all_answers.append({
            "probe_id": probe_id,
            "rcode": rcode,
            "answers": answers,
        })
    return all_answers


# Classify ISP results
isp_data = {}
for m in measurements:
    mid = str(m["id"])
    desc = m["description"]
    defn = m["definition"]
    raw = all_data.get(mid)

    label, target = extract_label_and_target(desc, defn)

    if label not in isp_data:
        isp_data[label] = {}

    mtype = defn.get("type", "")
    if mtype == "traceroute":
        analysis = analyze_traceroute(raw)
    elif mtype == "dns":
        analysis = analyze_dns(raw)
    else:
        analysis = None

    isp_data[label][target] = {
        "type": mtype,
        "analysis": analysis,
        "mid": mid,
    }

# GENERATE REPORT
print("=" * 72)
print("RIPE ATLAS MEASUREMENT ANALYSIS: TELEGRAM BLOCKING IN INDIA")
print("=" * 72)
print(f"\nMeasurements created: {len(measurements)}")
print(f"Date: June 18, 2026 (RIPE Atlas one-off traceroute + DNS)\n")

# Count results
total_blocked_tr = 0
total_ok_tr = 0
blocking_isps = set()
for label in sorted(isp_data.keys()):
    icmp_blocked = 0
    icmp_ok = 0
    for target, data in isp_data[label].items():
        a = data["analysis"]
        if a is None:
            continue
        if isinstance(a, list) and len(a) > 0 and "completed" in a[0]:
            # Traceroute result
            if a[0]["completed"]:
                icmp_ok += 1
            else:
                icmp_blocked += 1

    for label in sorted(isp_data.keys()):
        print(f"\n{'='*60}")
        print(f"ISP: {label}")
        print('='*60)
        for target in sorted(isp_data[label].keys()):
            data = isp_data[label][target]
            a = data["analysis"]
            mtype = data["type"]

            if a is None:
                print(f"  [{mtype:7s}] {target:30s} -> no data")
                continue

            if mtype == "traceroute":
                paths = []
                for probe_result in a:
                    status = "OK" if probe_result["completed"] else "BLOCKED"
                    ip = probe_result["last_ip"] or "-"
                    paths.append(f"{status}@{probe_result['hop_count']} ({ip})")
                print(f"  [{mtype:7s}] {target:30s} -> {', '.join(paths)}")

            elif mtype == "dns":
                for dr in a:
                    if dr["answers"]:
                        print(f"  [DNS    ] {target:30s} -> OK: {', '.join(dr['answers'])}")
                    elif dr["rcode"] == 3:
                        print(f"  [DNS    ] {target:30s} -> BLOCKED (NXDOMAIN)")
                    elif dr["rcode"] is not None:
                        print(f"  [DNS    ] {target:30s} -> rcode={dr['rcode']} (no answers)")
                    else:
                        print(f"  [DNS    ] {target:30s} -> no result data")

print(f"\n{'='*60}")
print("BLOCKING SUMMARY")
print('='*60)

# Re-analyze per ISP
for label in sorted(isp_data.keys()):
    icmp_results = {}
    tcp_results = {}
    dns_results = {}
    for target, data in isp_data[label].items():
        a = data["analysis"]
        if a is None:
            continue
        if "control" in target:
            continue
        is_icmp = data["type"] == "traceroute" and "TCP" not in str(data)
        is_tcp = data["type"] == "traceroute" and "TCP" in str(data)
        if data["type"] == "traceroute" and isinstance(a, list):
            for r in a:
                if not r.get("dst") or r["dst"] == "1.1.1.1":
                    continue
                classification = "OK" if r["completed"] else "BLOCKED"
                if r.get("dst", "").startswith("2a0a"):
                    # IPv6
                    icmp_results[f"v6:{r['dst']}"] = classification
                elif is_tcp or "TCP" in str(data):
                    tcp_results[r['dst']] = classification
                else:
                    icmp_results[r['dst']] = classification
        elif data["type"] == "dns" and isinstance(a, list):
            for r in a:
                if r["answers"]:
                    dns_results["telegram.org"] = "OK"
                else:
                    dns_results["telegram.org"] = "BLOCKED/NXDOMAIN/no-data"

    parts = []
    if icmp_results:
        blocks = sum(1 for v in icmp_results.values() if v == "BLOCKED")
        oks = sum(1 for v in icmp_results.values() if v == "OK")
        parts.append(f"ICMP: {blocks} blocked, {oks} OK")
    if tcp_results:
        blocks = sum(1 for v in tcp_results.values() if v == "BLOCKED")
        oks = sum(1 for v in tcp_results.values() if v == "OK")
        parts.append(f"TCP:443: {blocks} blocked, {oks} OK")
    if dns_results:
        for v in dns_results.values():
            parts.append(f"DNS: {v}")
    print(f"  {label:20s}: {'; '.join(parts)}")
