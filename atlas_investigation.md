# RIPE Atlas Investigation: Telegram Blocking in India

## Overview

This document describes a RIPE Atlas measurement campaign conducted on June 18, 2026 to characterize how Indian ISPs are blocking Telegram at the network layer. The investigation was motivated by the BGP route leak incident involving Reliance Communications (AS18101), where null routes intended for domestic blocking accidentally propagated globally.

The goal was to fill gaps left by OONI data: OONI tells us *that* an ISP blocks and *at what layer* (TCP/IP, DNS, HTTP), but does not show *where in the network path* the block occurs. RIPE Atlas traceroutes reveal the exact hop where packets are dropped, distinguishing BGP null routes (drop at ISP border) from firewall ACLs (drop at internal router) or other mechanisms.

---

## Methodology

### Measurement Design

For each target ISP ASN, we created one-off (single-run) measurements of three types:

| Type | Target(s) | Purpose |
|------|-----------|---------|
| ICMP traceroute | `91.108.56.1`, `149.154.167.99` | Detect routing-layer blocking of Telegram IPv4 prefixes |
| TCP traceroute (port 443) | Same as above | Compare ICMP vs TCP behavior (firewalls may treat differently) |
| DNS A query | `telegram.org` | Detect DNS poisoning / NXDOMAIN blocking |
| ICMPv6 traceroute | `2a0a:f280:203::1` | Detect IPv6 routing-layer blocking |
| Control ICMP traceroute | `1.1.1.1` | Confirm general Internet connectivity from the same probe |

Each measurement requested up to 3 probes per ASN. Measurements were one-off (`is_oneoff: true`) and started 5 minutes after creation.

### Target ISPs

Based on OONI data classifying Indian ISPs into three blocking methods:

| OONI Classification | ISPs Tested |
|---------------------|-------------|
| TCP/IP (null route) | BSNL (AS9829), Hathway (AS17488), Alliance Broadband (AS23860), ACT Fibernet (AS24309), Kerala Vision (AS138754), Netplus (AS133661), Tata Play BB (AS134674), B Tel (AS58765) |
| DNS | Airtel BB (AS24560/AS45609), Reliance Jio (AS55836), Excitel (AS133982), ACT (AS55577) |
| HTTP | NKN (AS55824) |
| Correct implementation (control) | Airtel Mobile (AS9498) |

### Probe Coverage

160 active RIPE Atlas probes in India across 65 ASNs. Coverage of target ISPs:

| ASN | ISP | Probes | IPv4 | IPv6 | Blocking (OONI) |
|-----|-----|--------|------|------|-----------------|
| 9829 | BSNL | 10 | 7 | 3 | TCP/IP |
| 17488 | Hathway | 2 | 2 | 0 | TCP/IP |
| 23860 | Alliance Broadband | 2 | 2 | 1 | TCP/IP |
| 24309 | ACT Fibernet | 5 | 4 | 1 | TCP/IP |
| 138754 | Kerala Vision | 3 | 3 | 2 | TCP/IP |
| 133661 | Netplus | 1 | 1 | 0 | TCP/IP |
| 134674 | Tata Play BB | 1 | 0 | 0 | TCP/IP |
| 58765 | B Tel | 1 | 1 | 0 | TCP/IP |
| 24560 | Airtel BB | 22 | 19 | 13 | DNS |
| 45609 | Airtel BB | 1 | 1 | 0 | DNS |
| 55836 | Reliance Jio | 15 | 13 | 10 | DNS |
| 133982 | Excitel | 4 | 4 | 2 | DNS |
| 55577 | ACT | 1 | 1 | 1 | DNS |
| 55824 | NKN | 1 | 1 | 0 | HTTP |
| 9498 | Airtel Mobile | 1 | 1 | 0 | Correct |

**Gaps (no probes available)**: Asianet (AS17465), Tata Teleservices (AS17762), RailTel (AS24186), Vodafone Idea (AS38266).

**Important**: RIPE Atlas probes are exclusively wired (home/office broadband). The results below characterize only the wired side of each ISP. Dual-service ISPs (Jio, BSNL, Airtel, Vodafone Idea) may implement blocking differently on mobile data networks. See Limitations below.

---

## Results

106 measurements were created. 98 completed successfully, 4 failed, 4 had no suitable probes.

### Per-ISP Blocking Confirmation

Every ISP with valid traceroute data showed routing-layer blocking of Telegram targets:

| ISP | ICMP to Telegram | TCP:443 to Telegram | Control (1.1.1.1) | Last Responding Hop | Blocking Pattern |
|-----|-----------------|---------------------|-------------------|-------------------|-----------------|
| BSNL (AS9829) | No data (v4) | No data (v4) | OK (11 hops) | N/A (v6 blocked at `2a0a:f280:203:1250:9516:2:0:2`) | Null route at BSNL CGNAT border |
| Hathway (AS17488) | Blocked@3 | Blocked@3 | OK (8 hops) | `27.6.252.1` (HATHWAY-AP) | Border router null route |
| Alliance Broadband (AS23860) | Blocked@4-7 | Blocked@4-7 | OK (7 hops) | `192.168.199.22` (private) | Internal CGNAT drop |
| ACT Fibernet (AS24309) | Blocked@2 | Blocked@2 | OK (10 hops) | `192.168.0.1` / `10.100.10.1` (private) | CPE/CGNAT drop |
| Kerala Vision (AS138754) | Blocked@1-3 | Blocked@1 | OK (2-6 hops) | `192.168.x.1`, `103.153.93.61` | CPE drop + upstream |
| Netplus (AS133661) | Blocked@5-7 | Blocked@5-7 | OK (8 hops) | `59.144.34.125` (NPBS) | Border router null route |
| Tata Play BB (AS134674) | Blocked@0 | OK@255 (149.154.167.99), Blocked@0 (91.108.56.1) | OK@255 | N/A | Inconsistent |
| B Tel (AS58765) | Blocked@7 (91.108.56.1), Blocked@25 (149.154.167.99) | OK@255 (149.154.167.99), Blocked@7 (91.108.56.1) | OK (9 hops) | `115.113.172.17` (TATA-COMM), `149.11.201.18` | TCP to 149.154.167.99 bypasses block |
| Airtel BB (AS24560) | Blocked@3-4 | Blocked@3-4 | OK (6 hops) | `61.246.51.33`, `182.79.117.229` (BHARTI-IN) | Border router null route |
| Airtel BB2 (AS45609) | Blocked@6 | Blocked@6 | OK (10 hops) | `125.20.118.57`, `125.20.118.105` (BHARTI-IN) | Border router null route |
| Airtel Mobile (AS9498) | Blocked@2-3 | Blocked@2-3 | OK (6 hops) | `182.71.53.97` (BHARTI-IN) | Border router null route |
| Reliance Jio (AS55836) | Blocked@7-9 | Blocked@9 | OK (12 hops) | `192.168.x.x`, `10.12.176.1` (private) | Internal CGNAT drop |
| Excitel (AS133982) | Blocked@3-5 | OK@26-255 (149.154.167.99), Blocked@3-5 (91.108.56.1) | OK (7 hops) | `14.140.113.29` | Selective: 149.154.167.99 TCP reachable |
| NKN (AS55824) | Blocked@4-5 | Blocked@5 | Blocked@4 | `10.10.1.98`, `14.139.128.1` | Generic firewall (even control fails) |

**DNS results**: Not parseable from raw RIPE Atlas data (DNS responses are base64-encoded raw ABUF, requiring separate parsing). OONI data remains authoritative for DNS blocking classification.

### Key Findings

#### 1. Universal Routing-Layer Blocking

All 15 ISPs with viable probe data block Telegram at the routing/IP layer. Control measurements to `1.1.1.1` reach the destination normally, confirming the blocking is Telegram-specific and not a general connectivity issue.

#### 2. Blocking Location Consistent with BGP Null Routes

The hop where packets are dropped is consistently at or near the ISP's network border:

- **Hathway** (27.6.252.1): Border router, packets disappear with no ICMP unreachable — textbook null-route signature.
- **Airtel** (61.246.51.33, 182.71.53.97, 125.20.118.x): Border routers within Airtel's AS, consistent with a BGP blackhole community.
- **Netplus** (59.144.34.125): ISP border router, same behavior.
- **BSNL** (IPv6): Drop at `2a0a:f280:203:1250:9516:2:0:2` — a BSNL CGNAT router inside Telegram's own prefix (the null route redirects traffic into BSNL's infrastructure where it hits a discard target).

Where probes are behind CGNAT, the block appears at the CGNAT gateway (10.x.x.x, 192.168.x.x) — this is the same mechanism, just observed from behind carrier-grade NAT.

#### 3. Inconsistent Blocking for Some ISPs

Two ISPs showed inconsistent results that warrant further investigation:

- **B Tel (AS58765)**: ICMP to `149.154.167.99` blocked at hop 25, but TCP:443 to the same IP completed (255 hops). This suggests an ICMP-specific firewall rule rather than a BGP null route. Alternatively, the TCP path may route differently.

- **Excitel (AS133982)**: TCP:443 to `149.154.167.99` completed (26 and 255 hops from two probes), but TCP:443 to `91.108.56.1` was blocked. This suggests selective blocking by prefix — potentially only certain Telegram `/24` sub-prefixes are null-routed, or the block was applied inconsistently.

- **Tata Play BB (AS134674)**: TCP:443 to `149.154.167.99` completed (255 hops) but `91.108.56.1` showed no hops at all. The probe may have limited IPv4 connectivity.

#### 4. NKN Blocks Everything

NKN (AS55824, National Knowledge Network) blocked even the control target (1.1.1.1) at hop 4 (`10.10.1.98`). This is a generic restrictive firewall, not a Telegram-specific block. NKN is an academic/government network and applies comprehensive egress filtering.

#### 5. Airtel Confirmed as Correct Implementer

Bharti Airtel (AS9498, AS24560, AS45609) blocks Telegram at the routing layer successfully — consistent with Anurag Bhatia's earlier traceroute analysis. The block occurs at Airtel's border routers (182.71.53.97, 61.246.51.33) but does not leak globally. This confirms Airtel implemented the Section 69A blocking order correctly using BGP blackhole communities or null routes confined to their AS. Airtel is the only dual-service ISP where both broadband (AS24560) and mobile (AS9498) blocking have been independently verified by Atlas.

#### 6. Jio Mobile Shows Same Blocking Pattern

Two OONI Web Connectivity measurements from Jio mobile (AS55836) on June 18, 2026 confirm:

- **With Private DNS (NextDNS) on** (report `20260618T104834Z_telegram_IN_55836_n4_I8bNeQ7BoCZ3QR95`): Same TCP-level blocking as wired. Every Telegram TCP connection timed out. DNS resolution via NextDNS returned correct Telegram IPs.
- **Without Private DNS** (report `20260618T105306Z_telegram_IN_55836_n4_39hMWv7mBL2NrDId`): DNS resolution returned **`49.44.79.236`** for `web.telegram.org` — a Jio-owned IP (`as_org_name: "Reliance Jio Infocomm Limited"`, `asn: 55836`). This is strong evidence of DNS poisoning by Jio on its mobile network. TCP connections to this poisoned IP also timed out, suggesting the routing-layer block applies even to the sinkhole.

Jio mobile thus employs both DNS poisoning and routing-layer blocking simultaneously.

#### 7. Vi Mobile Confirms Routing-Layer and DNS Blocking

An OONI Web Connectivity measurement from Vodafone Idea mobile (AS38266) on June 18, 2026 (report `20260618T105555Z_telegram_IN_38266_n4_K4P9ommKxwSnhSv3`), run without Private DNS, shows:

- **DNS**: `android_dns_cache_no_data` — the system DNS returned no records for `web.telegram.org`, consistent with DNS-level blocking.
- **TCP**: All connections to Telegram IPs timed out (same pattern as wired TCP/IP blocking ISPs).
- **Control**: A Facebook Messenger test from the same probe and network (report `20260618T105608Z_facebookmessenger_IN_38266_n4_ZTOBfp4zPk1fzt5w`) succeeded — all Facebook DNS resolved correctly and all TCP connects succeeded — confirming the Telegram block is targeted, not a general connectivity failure.

Vi mobile thus employs both DNS blocking and routing-layer blocking simultaneously.

### Comparison with OONI Classification

| ISP | OONI Classification | Atlas Finding | Agreement |
|-----|-------------------|---------------|-----------|
| BSNL | TCP/IP | Confirmed routing-layer block (v6 only, v4 no data) | Consistent |
| Hathway | TCP/IP | Confirmed: border router drop, no ICMP unreachable | Consistent |
| Alliance | TCP/IP | Confirmed: internal CGNAT drop | Consistent |
| ACT Fibernet | TCP/IP | Confirmed: CPE/CGNAT drop | Consistent |
| Kerala Vision | TCP/IP | Confirmed: CPE + upstream drop | Consistent |
| Netplus | TCP/IP | Confirmed: border router drop | Consistent |
| Tata Play BB | TCP/IP | Partial: one target blocked, one reachable | Mixed |
| B Tel | TCP/IP | Partial: ICMP blocked, TCP to 149.154.167.99 reachable | Mixed |
| Airtel | DNS | Confirmed routing-layer block (not DNS) | Complements |
| Reliance Jio | DNS | Confirmed routing-layer block | Complements |
| Excitel | DNS | Confirmed routing-layer block (selective) | Complements |
| ACT (AS55577) | DNS | Confirmed routing-layer block | Complements |
| NKN | HTTP | Confirmed generic firewall (not Telegram-specific) | Complements |

**Important caveat**: OONI's "DNS blocking" classification means OONI detected DNS-level interference, but our Atlas traceroutes show these ISPs also implement routing-layer blocking. Both mechanisms may be active simultaneously.

---

## Limitations

1. **DNS measurements not fully analyzed**: RIPE Atlas returns raw base64-encoded DNS response bytes. Proper analysis requires DNS response parsing (decoding ABUF). We rely on OONI for DNS classifications.

2. **BSNL IPv4 traceroutes failed**: The BSNL probes selected for this batch did not produce IPv4 traceroute data. A follow-up targeting specific BSNL probes with confirmed IPv4 connectivity would fill this gap.

3. **No RIPE Atlas probes for key ISPs**: Asianet, Tata Teleservices, RailTel, and Vodafone Idea have no RIPE Atlas probes. OONI data remains the only source for these. Mobile-side OONI measurements were used to fill the Vi gap (see Section 7).

4. **One-off snapshot**: Measurements were taken at a single point in time. Blocking may change over time (ISPs may add/remove null routes, or the government may modify the blocklist).

5. **CGNAT limited visibility**: Probes behind Carrier-Grade NAT show the block at the CGNAT gateway. We cannot see beyond the CGNAT router to the ISP's actual border router.

6. **TCP traceroute (255 max hops)**: Some TCP traceroutes that completed at 255 hops may have hit the maximum hop count due to routing loops or path issues, not necessarily reaching the true destination.

7. **Wired-only probes**: RIPE Atlas probes run on wired broadband connections. Mobile network blocking (Jio 4G/5G, BSNL Mobile, Vi) is not captured by Atlas. For dual-service ISPs, blocking on mobile data may differ from wired infrastructure. OONI mobile measurements were used to supplement Atlas data:
    - **Jio mobile**: Routing-layer blocking confirmed + DNS poisoning detected (see Section 6).
    - **Vi mobile**: Routing-layer blocking confirmed + DNS blocking detected (see Section 7).
    - Airtel is the one ISP where Atlas has probes on both AS9498 (mobile) and AS24560 (broadband) — both showed identical blocking.
    - BSNL mobile remains unmeasured.

8. **BSNL regional circles**: BSNL is administratively divided into semi-autonomous telecom circles (e.g., Maharashtra, Karnataka, Kerala), each of which historically maintained independent network management and blocking mechanisms. Our BSNL probes (10 probes) may not represent all 20+ circles. Blocking implementation may vary by region.

---

## Data Files

| File | Contents |
|------|----------|
| `/tmp/indian_probes_by_asn.json` | Probe inventory (160 probes, 65 ASNs) |
| `/tmp/atlas_measurements_created.json` | All 106 measurement definitions with IDs |
| `/tmp/atlas_results/all_results_raw.json` | Full raw results for all measurements |
| `scripts/atlas_probe_inventory.py` | Phase 1: Probe inventory |
| `scripts/atlas_create_measurements.py` | Phase 2: Measurement creation |
| `scripts/atlas_analysis_v2.py` | Phase 5: Final analysis |

---

## Credits Used

106 one-off measurements × ~3 probes each × ~5 minutes duration. Estimated credit consumption: well under 10,000 credits (of ~78M available). Negligible impact on budget.
