"""
Phase 4: Fetch all results and generate blocking analysis.
"""
import json, urllib.request, urllib.error, os, sys, time

API_KEY = os.environ.get("RIPE_ATLAS_KEY", "046ba714-f861-4e3c-b8b8-bae9ac303730")
BASE = "https://atlas.ripe.net/api/v2"
RESULTS_FILE = "/tmp/atlas_results/all_results_raw.json"

def api_get(path):
    req = urllib.request.Request(f"{BASE}{path}")
    req.add_header("Authorization", f"Key {API_KEY}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read())

os.makedirs("/tmp/atlas_results", exist_ok=True)

with open("/tmp/atlas_measurements_created.json") as f:
    measurements = json.load(f)

print(f"Fetching results for {len(measurements)} measurements...\n")
all_data = {}
fetched = 0
errors = 0

for m in measurements:
    mid = m["id"]
    try:
        data = api_get(f"/measurements/{mid}/results/")
        all_data[mid] = data
        if isinstance(data, list):
            print(f"  [{mid}] {m['description'][:60]} -> {len(data)} probe(s)")
        else:
            print(f"  [{mid}] {m['description'][:60]} -> {json.dumps(data)[:100]}")
        fetched += 1
    except Exception as e:
        print(f"  [{mid}] {m['description'][:60]} -> ERROR: {e}")
        all_data[mid] = None
        errors += 1
    time.sleep(0.3)

with open(RESULTS_FILE, "w") as f:
    json.dump(all_data, f, indent=2, default=str)
print(f"\nDone. Fetched {fetched}, errors {errors}")
print(f"Saved to {RESULTS_FILE}")

# ------------------- ANALYSIS -------------------
print("\n" + "=" * 60)
print("BLOCKING ANALYSIS")
print("=" * 60)

def analyze_traceroute(results):
    """Return (completed: bool, hop_count: int, last_hop_ip: str|None)."""
    if not isinstance(results, list) or len(results) == 0:
        return None
    report = results[0]
    hops = report.get("result", [])
    if not isinstance(hops, list):
        return None
    last_ip = None
    last_hop = 0
    for hop in hops:
        hop_n = hop.get("hop", 0)
        for r in hop.get("result", []):
            if isinstance(r, dict) and r.get("from"):
                last_ip = r["from"]
                last_hop = hop_n
    # Check if destination was reached
    dst = report.get("dst_addr", "")
    completed = (last_ip == dst)
    return {"completed": completed, "hops": last_hop, "last_ip": last_ip, "dst": dst}


def analyze_dns(results):
    """Return DNS responses."""
    if not isinstance(results, list) or len(results) == 0:
        return None
    report = results[0]
    result_list = report.get("result", [])
    answers = []
    rcode = None
    for r in result_list if isinstance(result_list, list) else []:
        if isinstance(r, dict):
            if "A" in r and r["A"]:
                answers.append(r["A"])
            if r.get("rcode") is not None:
                rcode = r["rcode"]
    return {"answers": answers, "rcode": rcode}


with open(RESULTS_FILE) as f:
    all_data = json.load(f)

# Group by ISP label
isp_results = {}
for m in measurements:
    mid = str(m["id"])
    desc = m["description"]
    defn = m["definition"]
    raw = all_data.get(mid)

    # Extract ISP label and target from description
    # e.g. "ICMP trace BSNL -> 91.108.56.1"
    #      "TCP:443 trace BSNL -> 149.154.167.99"
    #      "DNS A telegram.org from BSNL"
    #      "ICMPv6 trace Excitel -> 2a0a:f280:203::1"
    parts = desc.split(" -> ")
    if len(parts) == 2:
        left = parts[0]
        method_label = left  # "ICMP trace BSNL"
        label = left.split(" ")[-1]  # "BSNL"
        method = left.split(" ")[0] if left.split(" ")[0] != "ICMPv6" else "ICMPv6"
        target = parts[1]  # "91.108.56.1"
    elif "from " in desc:
        # DNS format: "DNS A telegram.org from BSNL"
        label = desc.split("from ")[-1]
        method = "DNS"
        target = "telegram.org"
    else:
        label = "unknown"
        method = "?"
        target = "?"

    if label not in isp_results:
        isp_results[label] = {}
    key = f"{method}:{target}"

    if method.startswith("ICMP") or method.startswith("TCP"):
        analysis = analyze_traceroute(raw)
    elif method == "DNS":
        analysis = analyze_dns(raw)
    else:
        analysis = None

    isp_results[label][key] = {
        "analysis": analysis,
        "mid": str(m["id"]),
        "raw": raw,
    }

# Print summary
for label in sorted(isp_results.keys()):
    print(f"\n--- {label} ---")
    tr = isp_results[label]
    for key, data in sorted(tr.items()):
        a = data["analysis"]
        if a is None:
            print(f"  {key}: no data")
            continue
        if "completed" in a:
            if a["completed"]:
                print(f"  {key}: PATH COMPLETE ({a['hops']} hops, last: {a['last_ip']})")
            else:
                print(f"  {key}: BLOCKED at hop {a['hops']} ({a['last_ip']}), never reached {a['dst']}")
        elif "answers" in a:
            if a["answers"]:
                print(f"  {key}: OK -> {', '.join(a['answers'])}")
            elif a["rcode"] == 3:
                print(f"  {key}: BLOCKED (NXDOMAIN)")
            else:
                print(f"  {key}: rcode={a['rcode']}, no answers")

print("\nDone.")
