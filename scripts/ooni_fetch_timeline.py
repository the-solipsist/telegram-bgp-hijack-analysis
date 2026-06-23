#!/usr/bin/env python3
"""Fetch all OONI Telegram measurements from India since a given date,
paginate through the API, and save timeline data."""

import json
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime

API_BASE = "https://api.ooni.io/api/v1/measurements"
OUTPUT_FILE = "data/raw/ooni/ooni_measurements_india_telegram_raw.json"
SUMMARY_FILE = "data/raw/ooni/ooni_measurements_india_telegram_summary.json"
SINCE = "2026-06-16"
LIMIT = 200

def fetch_page(url):
    """Fetch a single page of OONI measurements with retries."""
    for attempt in range(3):
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            print(f"  Attempt {attempt+1} failed: {e}", file=sys.stderr)
            time.sleep(2)
    return None

def fetch_all(params):
    """Fetch all measurements with pagination."""
    all_results = []
    base_url = f"{API_BASE}?{params}&limit={LIMIT}"
    next_url = base_url

    page = 1
    while next_url:
        print(f"  Page {page}...", file=sys.stderr)
        data = fetch_page(next_url)
        if data is None:
            print(f"  ERROR: Failed to fetch page {page}", file=sys.stderr)
            break

        results = data.get("results", [])
        all_results.extend(results)
        print(f"    Got {len(results)} results (total so far: {len(all_results)})", file=sys.stderr)

        # Check if there are more pages
        next_url = data.get("metadata", {}).get("next_url")
        if next_url:
            next_url = f"https://api.ooni.io{next_url}" if next_url.startswith("/") else next_url
        page += 1

        if len(results) < LIMIT:
            break

    return all_results


def main():
    print("Fetching OONI Telegram measurements from India since", SINCE, file=sys.stderr)

    # Fetch ALL measurements (anomaly + non-anomaly) to get full picture
    params_all = f"probe_cc=IN&test_name=telegram&since={SINCE}"
    print("Fetching ALL measurements...", file=sys.stderr)
    all_data = fetch_all(params_all)

    print(f"\nTotal measurements fetched: {len(all_data)}", file=sys.stderr)

    # Save raw data
    results_by_asn = {}
    for r in all_data:
        asn = r.get("probe_asn", "unknown")
        if asn not in results_by_asn:
            results_by_asn[asn] = []
        results_by_asn[asn].append({
            "anomaly": r.get("anomaly"),
            "confirmed": r.get("confirmed"),
            "measurement_start_time": r.get("measurement_start_time"),
            "scores": r.get("scores", {}),
            "report_id": r.get("report_id"),
        })

    with open(OUTPUT_FILE, "w") as f:
        json.dump({"fetched_at": datetime.utcnow().isoformat() + "Z",
                    "since": SINCE,
                    "count": len(all_data),
                    "results": results_by_asn}, f, indent=2)
    print(f"\nRaw data saved to {OUTPUT_FILE}", file=sys.stderr)

    # Build per-ASN timeline summary
    asn_summary = {}
    for asn, measurements in results_by_asn.items():
        measurements.sort(key=lambda m: m["measurement_start_time"])

        first_seen = measurements[0]["measurement_start_time"]
        last_seen = measurements[-1]["measurement_start_time"]

        anomalies = [m for m in measurements if m["anomaly"] is True]
        clean = [m for m in measurements if m["anomaly"] is False]

        first_anomaly = anomalies[0]["measurement_start_time"] if anomalies else None
        last_anomaly = anomalies[-1]["measurement_start_time"] if anomalies else None
        last_clean = clean[-1]["measurement_start_time"] if clean else None

        # Blocking method: look at web_failure codes in anomalies
        failure_codes = set()
        for a in anomalies:
            scores = a.get("scores", {})
            wf = scores.get("web_failure")
            if wf:
                failure_codes.add(wf)

        # Blocking status:
        # - If no anomalies at all -> no blocking ever detected
        # - If last measurement is an anomaly -> still blocked
        # - If last measurement is clean AND occurs after last anomaly -> blocking ended
        #   (find the first clean measurement AFTER the last anomaly)
        if not anomalies:
            status = "no_blocking_detected"
            blocking_started = None
            blocking_ended = None
        elif last_seen == last_anomaly:
            status = "still_blocked"
            blocking_started = first_anomaly
            blocking_ended = None
        else:
            # Last measurement is clean - find transition point
            status = "blocking_lifted"
            blocking_started = first_anomaly
            # Find first clean measurement that occurs AFTER the last anomaly
            first_post_anomaly_clean = None
            for m in measurements:
                if m["anomaly"] is False and m["measurement_start_time"] > last_anomaly:
                    first_post_anomaly_clean = m["measurement_start_time"]
                    break
            blocking_ended = first_post_anomaly_clean

        # Count measurements by date for pattern
        date_counts = {}
        for m in measurements:
            date = m["measurement_start_time"][:10]
            if date not in date_counts:
                date_counts[date] = {"anomaly": 0, "clean": 0}
            if m["anomaly"]:
                date_counts[date]["anomaly"] += 1
            else:
                date_counts[date]["clean"] += 1

        asn_summary[asn] = {
            "total_measurements": len(measurements),
            "anomaly_count": len(anomalies),
            "clean_count": len(clean),
            "first_seen": first_seen,
            "last_seen": last_seen,
            "first_anomaly": first_anomaly,
            "last_anomaly": last_anomaly,
            "last_clean": last_clean,
            "status": status,
            "blocking_started": blocking_started,
            "blocking_ended": blocking_ended,
            "failure_codes": sorted(list(failure_codes)),
            "daily_breakdown": date_counts,
        }

    with open(SUMMARY_FILE, "w") as f:
        json.dump(asn_summary, f, indent=2, sort_keys=True)
    print(f"Summary saved to {SUMMARY_FILE}", file=sys.stderr)

    # Print summary table
    print()
    print(f"{'ASN':<14} {'Total':>5} {'Anom':>5} {'Clean':>5} {'Status':<22} {'Started':<22} {'Ended':<22} {'Method'}")
    print("-" * 130)
    for asn in sorted(asn_summary.keys()):
        s = asn_summary[asn]
        status = s["status"]
        started = s.get("blocking_started") or "N/A"
        ended = s.get("blocking_ended") or "N/A"
        failures = ", ".join(s["failure_codes"]) if s["failure_codes"] else "none"
        print(f"{asn:<14} {s['total_measurements']:>5} {s['anomaly_count']:>5} {s['clean_count']:>5} {status:<22} {started:<22} {ended:<22} {failures}")


if __name__ == "__main__":
    main()
