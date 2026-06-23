"""
Phase 3: Fetch RIPE Atlas measurement results and analyze Telegram blocking.

Usage:
  python3 atlas_fetch_results.py [--poll] [--interval 30]

Without --poll: check status once, fetch completed results.
With --poll: keep checking until all measurements complete or timeout.
"""
import json, urllib.request, urllib.error, os, sys, time, argparse

API_KEY = os.environ.get("RIPE_ATLAS_KEY", "046ba714-f861-4e3c-b8b8-bae9ac303730")
BASE = "https://atlas.ripe.net/api/v2"
RESULTS_DIR = "/tmp/atlas_results"

def api_get(path):
    req = urllib.request.Request(f"{BASE}{path}")
    req.add_header("Authorization", f"Key {API_KEY}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def fetch_measurement_status(mid):
    try:
        data = api_get(f"/measurements/{mid}/")
        status = data.get("status", {}).get("name", "unknown")
        probes_planned = data.get("probes_planned", 0)
        probes_succeeded = data.get("probes_succeeded", 0)
        probes_failed = data.get("probes_failed", 0)
        return {
            "id": mid,
            "status": status,
            "planned": probes_planned,
            "succeeded": probes_succeeded,
            "failed": probes_failed,
            "finished": data.get("stop_time") is not None,
        }
    except Exception as e:
        return {"id": mid, "status": f"error: {e}", "finished": False}


def fetch_measurement_results(mid):
    try:
        data = api_get(f"/measurements/{mid}/results/")
        return data
    except Exception as e:
        return None


def classify_traceroute_blocking(results, target, af):
    """Analyze traceroute results for blocking patterns.
    
    Returns a dict with path info and blocking classification.
    """
    # results is a list of per-probe reports
    probes_analysis = []
    for report in results if isinstance(results, list) else []:
        if not isinstance(report, dict):
            continue
        probe_id = report.get("prb_id") or report.get("probe_id", "?")
        hops_total = report.get("paris", report.get("result", []))
        if isinstance(hops_total, list) and len(hops_total) > 0:
            # Get last hop with a response
            last_responded = None
            last_ip = None
            all_hops = []
            for hop in hops_total:
                if isinstance(hop, dict):
                    hop_num = hop.get("hop", 0)
                    result_list = hop.get("result", [])
                    for r in result_list if isinstance(result_list, list) else []:
                        if isinstance(r, dict) and r.get("from"):
                            last_responded = hop_num
                            last_ip = r["from"]
                            rtt = r.get("rtt", -1)
                            all_hops.append((hop_num, r["from"], rtt))
                            break
            probes_analysis.append({
                "probe_id": probe_id,
                "total_hops_responded": last_responded,
                "last_responding_ip": last_ip,
                "last_responding_hop": last_responded,
                "all_hops": all_hops,
            })
        else:
            probes_analysis.append({
                "probe_id": probe_id,
                "total_hops_responded": 0,
                "last_responding_ip": None,
                "last_responding_hop": None,
                "all_hops": [],
            })
    return probes_analysis


def classify_dns_blocking(results, domain):
    """Analyze DNS results for blocking."""
    probes_analysis = []
    for report in results if isinstance(results, list) else []:
        if not isinstance(report, dict):
            continue
        probe_id = report.get("prb_id") or report.get("probe_id", "?")
        result_list = report.get("result", [])
        answers = []
        rcode = None
        for r in result_list if isinstance(result_list, list) else []:
            if isinstance(r, dict):
                if "A" in r and r["A"]:
                    answers.append(r["A"])
                if r.get("rcode") is not None:
                    rcode = r["rcode"]
        probes_analysis.append({
            "probe_id": probe_id,
            "rcode": rcode,
            "answers": answers,
        })
    return probes_analysis


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--poll", action="store_true", help="Poll until all complete")
    parser.add_argument("--interval", type=int, default=30, help="Poll interval seconds")
    args = parser.parse_args()

    os.makedirs(RESULTS_DIR, exist_ok=True)

    # Load created measurements
    with open("/tmp/atlas_measurements_created.json") as f:
        measurements = json.load(f)

    total = len(measurements)
    print(f"Tracking {total} measurements\n")

    if args.poll:
        deadline = time.time() + 3600  # 1 hour max
        while time.time() < deadline:
            completed = 0
            for m in measurements:
                status = fetch_measurement_status(m["id"])
                if status["finished"]:
                    completed += 1
            pct = 100 * completed / total
            print(f"  {completed}/{total} completed ({pct:.0f}%)")
            if completed == total:
                print("All measurements complete!")
                break
            time.sleep(args.interval)
        else:
            print(f"Timeout reached. {completed}/{total} completed.")

    # Fetch full results for all finished measurements
    print(f"\n{'='*60}")
    print("Fetching results...")

    all_results = {}
    for m in measurements:
        mid = m["id"]
        desc = m["description"]
        defn = m["definition"]
        mtype = defn.get("type", "?")

        results = fetch_measurement_results(mid)
        if results is None:
            print(f"  [{mid}] {desc} -> no results yet")
            continue

        # Analyze
        if mtype == "traceroute":
            target = defn.get("target", "?")
            af = defn.get("af", 4)
            analysis = classify_traceroute_blocking(results, target, af)
        elif mtype == "dns":
            domain = defn.get("query_argument", "?")
            analysis = classify_dns_blocking(results, domain)
        else:
            analysis = {"raw_count": len(results) if isinstance(results, list) else 0}

        all_results[mid] = {
            "description": desc,
            "definition": defn,
            "results": results,
            "analysis": analysis,
        }

        # Quick summary
        if isinstance(results, list):
            print(f"  [{mid}] {desc} -> {len(results)} probe reports")
        else:
            print(f"  [{mid}] {desc} -> {type(results).__name__}")

    with open(f"{RESULTS_DIR}/all_results.json", "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nFull results saved to {RESULTS_DIR}/all_results.json")

    # Generate analysis summary
    print(f"\n{'='*60}")
    print("ANALYSIS SUMMARY\n")

    by_asn = {}
    for mid, data in all_results.items():
        desc = data["description"]
        # Extract ASN/label from description: "ICMP trace BSNL -> 91.108.56.1"
        parts = desc.split(" -> ")
        if len(parts) == 2:
            left = parts[0]
            target = parts[1]
            # left is like "ICMP trace BSNL" or "TCP:443 trace BSNL" or "DNS A telegram.org from BSNL"
            if "trace" in left:
                method = "traceroute"
                label = left.split("trace ")[-1].strip()
            elif "DNS" in left:
                method = "dns"
                label = left.split("from ")[-1].strip()
            else:
                method = "?"
                label = left
        else:
            label = desc
            target = "?"
            method = "?"

        if label not in by_asn:
            by_asn[label] = {}
        by_asn[label][target] = data["analysis"]

    for label in sorted(by_asn.keys()):
        print(f"\n{'='*60}")
        print(f"ISP: {label}")
        for target, analysis in by_asn[label].items():
            if isinstance(analysis, list) and len(analysis) > 0:
                sample = analysis[0]
                if "last_responding_hop" in sample:
                    hops = sample["total_hops_responded"]
                    last_ip = sample["last_responding_ip"]
                    all_hops = sample.get("all_hops", [])
                    if hops and hops > 0:
                        print(f"  {target}: path complete ({hops} hops, last: {last_ip})")
                    else:
                        print(f"  {target}: BLOCKED - no hops responded")
                elif "answers" in sample:
                    answers = sample.get("answers", [])
                    rcode = sample.get("rcode")
                    if answers:
                        print(f"  {target}: DNS OK -> {answers}")
                    elif rcode == 3:
                        print(f"  {target}: DNS BLOCKED (NXDOMAIN)")
                    else:
                        print(f"  {target}: DNS rcode={rcode}, no answers")

    print(f"\nDetailed results saved to {RESULTS_DIR}/all_results.json")


if __name__ == "__main__":
    main()
