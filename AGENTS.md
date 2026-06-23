# Session Summary — Telegram BGP Hijack Analysis

## Repository State

BGP route-leak analysis of RCom (AS18101) hijacking Telegram prefixes on June 16, 2026. README.md contains the full narrative with BGP path reconstruction, RPKI analysis, and resolution timeline. All data files in `data/` and scripts in `scripts/`. Two image files in `images/` (Kentik traffic charts).

Git: 20+ commits by Pranesh (via AI agents). Most recent is "Add OONI data showing which Indian ISPs block Telegram and by what method".

## What Has Been Done

### BGP Analysis (previous sessions)
- RIPE RIS BGP update analysis — 35 hijacked prefixes, 2-phase timeline
- Upstream tracking: FLAG (AS15412) dominant, Tata (AS4755), Airtel (AS9498)
- RPKI analysis: IPv4 ~2-4% visibility vs IPv6 100%; RPKI role is well-supported hypothesis (confounded by topology + competing routes)
- Scripts for: prefix overlap, timeline per upstream, per-prefix lifecycle, RPKI enforcement analysis
- All 35 prefix start/stop/resolution timestamps extracted

### Literature Survey (this session)
- Singh, Grover, Bansal (arXiv 1912.08590 / CIS) — standard blocking in India is DNS/SNI/HTTP, not routing-layer
- Karan Saini (dnsblocks.in) — same methodology
- RCom is defunct/insolvent — actual operator of AS18101 is unknown (added to README)

### RIPE Atlas Investigation (this session)
- Probes inventory: 160 active probes in India across 65 ASNs
- 106 measurements created (traceroute + DNS) across 15 ISPs, 98 completed
- **Finding**: Universal routing-layer blocking at every ISP. Packets drop at ISP border routers — consistent with BGP null routes (no ICMP unreachable, just disappearance)
- **Anomalies**: B Tel TCP to 149.154.167.99 bypasses block; Excitel selectively blocks by prefix; NKN generic firewall blocks everything
- Airtel confirmed as correct implementer (block at border, no global leak)
- DNS measurements not parseable from raw Atlas data (base64 ABUF)

### OONI Nationwide Analysis (this session)
- Wrote `scripts/ooni_fetch_timeline.py` to query OONI API for all India `telegram` tests since June 16
- 1,793 measurements across 47 ASNs analyzed; saved to `data/raw/ooni/ooni_measurements_india_telegram_raw.json` and `ooni_measurements_india_telegram_summary.json`
- Used OONI aggregation API for cleaner per-ASN, daily, and hourly blocking/unblocking timelines
- **Blocking onset**: First anomalies appear June 16 05:00 UTC (Tata Teleservices DNS NXDOMAIN); major ISPs by 07:00–11:00 UTC
- **Unblocking order**: Alliance/Jio at 00:00 UTC June 23, ACT at 05:00, Airtel/Tata Play/Kerala Vision at 06:00 — a clear wave
- **Daily aggregate**: 100% anomaly June 17–21, dropping to 34% OK on June 23
- Aggregation data saved to `data/raw/ooni/ooni_aggregation_india_telegram_*.json` (4 files)
- Vi (AS38266): IPv4 blocked, IPv6 works (from OONI aggregation + Atlas)

### RIPE Atlas Cross-Verification (this session)
- Ran 35 traceroutes (ICMP + TCP/443) across 7 ISPs flagged by OONI, plus 1.1.1.1 control
- **BSNL (AS9829)**: Confirmed blocked — all ICMP + TCP fail, control works
- **Hathway (AS17488)**: Confirmed partially blocked — 2/3 ICMP targets fail, TCP blocked
- **Excitel (AS133982)**: UNBLOCKED — OONI data is stale (last Jun 22); TCP reaches all IPs, only residual ICMP block on 149.154.167.99
- **Airtel consumer (AS45609), Airtel transit (AS9498), Netplus (AS133661)**: UNBLOCKED — same pattern, TCP all OK, residual ICMP on 149.154.167.99 only
- **NKN (AS55824)**: Blocks everything including control (1.1.1.1) — generic firewall, not Telegram-specific
- **Key finding**: OONI anomaly flags lag behind reality for ISPs with stale measurements. Atlas reveals unblocking that OONI hasn't picked up yet.

### Data Organization (this session)
- `data/raw/atlas/` — probe inventory, measurement IDs, traceroute results
- `data/raw/ooni/` — OONI aggregation JSONs (4 files), measurements timeline (2 files)

### Documentation Updates (this session)
- README: RCom operator unknown, broadband vs mobile caveat table, TOC linked
- README Section 4: Added ROV bypass caveat (RFC7999 BLACKHOLE community, Herdes CHI-NOG paper)
- README Section 8: Added confirmed BLACKHOLE community mechanism for AS45820, citing Anurag Bhatia lab tests, Lightstorm as secondary actor
- README Postscript: OONI aggregation-based blocking/unblocking timeline + Atlas cross-verification
- atlas_investigation.md: BSNL regional circles limitation, mobile-side OONI supplement

## Stale / Action Items
- RPKI claims were qualified after adversarial audit — now "well-supported hypothesis" with confounders
- BSNL IPv4 traceroutes failed in the batch; follow-up may be needed
- RIPE Atlas DNS parsing not done (relies on OONI for DNS classification)
