# FLAG Telecom (AS15412) BGP Hijack & Filtering Report

This report presents the analysis of FLAG Telecom's (AS15412) role as the primary transit provider propagating Reliance Communications' (AS18101 / RCom) BGP hijack of Telegram's IP address space on June 16, 2026.

> [!NOTE]
> This analysis corrects the previous end time of `19:59:18` UTC, which was a truncation artifact of the original 20:00:00 UTC download window. By downloading extended BGP updates up to June 17, 2026, 06:00:00 UTC and analyzing prefix-specific updates (capturing withdrawals and path switches), we have established the exact timeline.

---

## Executive Timeline Summary

| Event Phase | Timestamp (UTC) | Timestamp (IST) | Target Prefix | Description / Event Details |
| :--- | :--- | :--- | :--- | :--- |
| **Leak Begins** | `07:08:57` | **12:38:57 PM** (June 16) | `95.161.64.0/20` | FLAG accepts RCom's hijacked announcement and begins propagating it to downstream peers globally. |
| **Phase 2 Sub-Prefix Waves** | `16:14:19` | **09:44:19 PM** (June 16) | Multiple `/24` sub-prefixes | RCom launches a massive, aggressive wave of more-specific `/24` sub-prefix hijacks to bypass filters. |
| **Phase 2 Resolution** | `20:06:39` | **01:36:39 AM** (June 17) | `/24` sub-prefixes | The `/24` sub-prefix hijacks stop propagating and are resolved globally. |
| **Filtering Begins (Phase 1)** | `21:12:41` | **02:42:41 AM** (June 17) | `95.161.64.0/20` | FLAG deploys network filters, withdrawing the remaining hijacked routes from its peers. |
| **Last Hijack Announcement** | `21:12:44` | **02:42:44 AM** (June 17) | `91.108.56.0/22` | The absolute last BGP advertisement of a hijacked Telegram prefix containing the `18101 -> 15412` path. |
| **Final Resolution** | `21:13:11` | **02:43:11 AM** (June 17) | `91.108.56.0/22` | The last BGP peer switches from the hijacked path via FLAG back to Telegram's legitimate path (`62041`). |

---

## Mapped Parents and Sub-Prefixes Timeline (Disaggregated)

The hijack progressed in two distinct waves: 
1. **Parent Prefixes / Large Blocks (Wave 1)**: Started at `07:08` UTC and remained active all day until FLAG filtered them at `21:12` UTC.
2. **More-specific `/24` Sub-Prefixes (Wave 2)**: Launched at `16:14` UTC to aggressively override routing paths, which resolved earlier around `20:06` UTC.

Below is the disaggregated start and stop/resolution time for all 33 affected subnets propagating via FLAG (AS15412):

| Prefix / Sub-prefix | Status via FLAG | Start Time (UTC) | Stop / Resolution (UTC) |
| :--- | :--- | :--- | :--- |
| **`149.154.160.0/22`** | Hijacked | `2026-06-16T07:18:30` | `2026-06-16T21:13:11` |
| **`149.154.160.0/23`** | Hijacked | `2026-06-16T07:18:30` | `2026-06-16T21:13:11` |
| **`149.154.160.0/24`** | Hijacked | `2026-06-16T16:14:19` | `2026-06-16T20:06:39` |
| **`149.154.161.0/24`** | Hijacked | `2026-06-16T16:14:19` | `2026-06-16T20:06:39` |
| **`149.154.162.0/23`** | Hijacked | `2026-06-16T07:18:30` | `2026-06-16T21:13:11` |
| **`149.154.162.0/24`** | Hijacked | `2026-06-16T16:14:19` | `2026-06-16T20:06:39` |
| **`149.154.163.0/24`** | Hijacked | `2026-06-16T16:14:19` | `2026-06-16T20:06:39` |
| **`149.154.164.0/22`** | Hijacked | `2026-06-16T07:18:30` | `2026-06-16T21:13:11` |
| **`149.154.164.0/23`** | Hijacked | `2026-06-16T07:18:30` | `2026-06-16T21:13:11` |
| **`149.154.164.0/24`** | Hijacked | `2026-06-16T16:14:19` | `2026-06-16T20:06:39` |
| **`149.154.165.0/24`** | Hijacked | `2026-06-16T16:14:19` | `2026-06-16T20:06:39` |
| **`149.154.166.0/23`** | Hijacked | `2026-06-16T07:18:30` | `2026-06-16T21:13:11` |
| **`149.154.166.0/24`** | Hijacked | `2026-06-16T16:14:19` | `2026-06-16T20:06:39` |
| **`149.154.167.0/24`** | Hijacked | `2026-06-16T16:14:19` | `2026-06-16T20:06:39` |
| **`149.154.168.0/22`** | Hijacked | `2026-06-16T16:14:19` | `2026-06-16T20:06:04` |
| **`185.76.151.0/24`**  | Hijacked | `2026-06-16T16:14:19` | `2026-06-16T20:06:39` |
| **`2001:67c:4e8::/48`**| Hijacked | `2026-06-16T07:21:32` | `2026-06-16T20:39:11` |
| **`2001:b28:f23d::/48`**| Hijacked | `2026-06-16T16:29:42` | `2026-06-16T20:39:11` |
| **`2001:b28:f23f::/48`**| Hijacked | `2026-06-16T16:30:41` | `2026-06-16T20:39:11` |
| **`2a0a:f280::/32`**   | Hijacked | `2026-06-16T16:46:04` | `2026-06-16T20:43:54` |
| **`91.105.192.0/23`**  | Hijacked | `2026-06-16T16:14:19` | `2026-06-16T20:06:39` |
| **`91.108.10.0/23`**   | Hijacked | `2026-06-16T16:14:19` | `2026-06-16T20:06:39` |
| **`91.108.16.0/22`**   | Hijacked | `2026-06-16T16:13:16` | `2026-06-16T20:06:05` |
| **`91.108.4.0/22`**    | Hijacked | `2026-06-16T07:17:27` | `2026-06-16T21:13:11` |
| **`91.108.4.0/23`**    | Hijacked | `2026-06-16T16:14:19` | `2026-06-16T20:06:39` |
| **`91.108.56.0/22`**   | Hijacked | `2026-06-16T07:18:30` | `2026-06-16T21:13:11` |
| **`91.108.56.0/23`**   | Hijacked | `2026-06-16T16:16:05` | `2026-06-16T20:06:17` |
| **`91.108.6.0/23`**    | Hijacked | `2026-06-16T16:14:19` | `2026-06-16T20:06:39` |
| **`91.108.8.0/22`**    | Hijacked | `2026-06-16T07:18:30` | `2026-06-16T21:13:11` |
| **`91.108.8.0/23`**    | Hijacked | `2026-06-16T16:14:19` | `2026-06-16T20:06:39` |
| **`95.161.64.0/20`**   | Hijacked | `2026-06-16T07:08:57` | `2026-06-16T21:13:11` |
| **`95.161.64.0/21`**   | Hijacked | `2026-06-16T16:14:19` | `2026-06-16T20:06:39` |
| **`95.161.72.0/21`**   | Hijacked | `2026-06-16T16:14:19` | `2026-06-16T20:06:39` |

---

## Distinguishing Legitimate Transit from Incorrect Advertisements

To ensure analysis validity, we distinguish between two types of traffic transiting FLAG (AS15412):
1. **Legitimate Upstream Transit:** FLAG is one of RCom's (AS18101) primary legitimate transits. Legitimate RCom-owned IP ranges (e.g., `115.248.8.0/22`, `220.226.0.0/16`) were announced through FLAG before, during, and after this timeline.
2. **Incorrect Path Advertisements:** The incorrect paths are BGP advertisements where RCom (AS18101) is the origin for Telegram-allocated IP prefixes. FLAG's filtering reaction specifically applies to dropping these incorrect paths while leaving RCom's legitimate paths untouched.

---

## Evidentiary Verification CLI Commands

You can run the following commands in the root of this repository against the downloaded prefix BGP updates to output the timeline verification for your logs:

### 1. Download the Raw Data
First, run the download script to fetch the prefix-specific BGP updates:
```bash
python3 scripts/download_prefix_updates.py
```

### 2. Run the Unified Python Proof Script
Run this script to output the verified start, last advertisement, and final resolution timestamps for FLAG:
```bash
python3 scripts/analyze_timeline.py
```

### 3. Verify with standard `jq` commands (Bash)

* **To show when the leak first started via FLAG (07:08:57 UTC):**
  ```bash
  jq -r '.data.updates[] | select(.attrs.path != null) | select(.attrs.path[-1] == 18101) | select(.attrs.path | reverse | .[1] == 15412) | "\(.timestamp) \(.attrs.target_prefix) Path: \(.attrs.path | reverse | join(" -> "))"' data/raw/95.161.64.0_20_full.json | sort | head -n 1
  ```

* **To show the last BGP announcement of the hijack via FLAG (21:12:44 UTC):**
  ```bash
  jq -r '.data.updates[] | select(.attrs.path != null) | select(.attrs.path[-1] == 18101) | select(.attrs.path | reverse | .[1] == 15412) | select(.attrs.target_prefix == "91.108.56.0/22") | "\(.timestamp) \(.attrs.target_prefix)"' data/raw/91.108.56.0_22_full.json | sort | tail -n 1
  ```

* **To show the final resolution switches to Telegram's ASN 62041 (21:13:11 UTC):**
  ```bash
  jq -r '.data.updates[] | select(.attrs.path != null) | select(.attrs.path[-1] == 62041) | select(.attrs.target_prefix == "91.108.56.0/22") | select(.timestamp >= "2026-06-16T21:12:40") | "\(.timestamp) \(.attrs.target_prefix) Path: \(.attrs.path | reverse | join(" -> "))"' data/raw/91.108.56.0_22_full.json | sort | head -n 3
  ```
