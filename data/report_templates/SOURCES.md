# Structural reference advisories

Our synthetic threat reports mirror the **section layout and reporting style** of the public
advisories below. No text, indicators, or findings are copied from them. They are listed so
reviewers can check that the synthetic reports follow real-world CTI conventions.

Structure was reviewed on 2026-10-17.

| Alert code | Type | URL | What we took from it |
|---|---|---|---|
| AA23-263A | #StopRansomware joint advisory | https://www.cisa.gov/news-events/cybersecurity-advisories/aa23-263a | Top action list; Summary → Technical Details by attack phase → IOCs (one subsection per indicator type, numbered tables) → ATT&CK tables → Mitigations → Validate → Reporting → Disclaimer; defanged domains with `[.]`; separate tables for malicious vs legitimate domains |
| AA24-038A | State-sponsored activity advisory | https://www.cisa.gov/news-events/cybersecurity-advisories/aa24-038a | Detection/Hunt Recommendations with imperative subheadings and a log-indicator table; IOC appendix (file name, description, hashes); one ATT&CK table per tactic |
| AA23-136A | #StopRansomware joint advisory | https://www.cisa.gov/news-events/cybersecurity-advisories/aa23-136a | Three-column IOC table (Name, Hash, Description); ATT&CK IDs in square brackets inside prose; mitigations as nested bullets grouped by theme |

## Conventions adopted

1. **Defanging.** Domains and e-mail addresses are written with `[.]` (e.g. `update-check[.]example[.]net`).
   The `search_logs` tool normalises `[.]` back to `.`, as an analyst would before searching.
2. **ATT&CK.** Technique IDs appear in square brackets in prose (e.g. `[T1566.001]`) and in a
   table with columns *Technique Title | ID | Use*.
3. **IOC tables.** Columns *Indicator | Type | Description*, numbered captions ("Table 1: ...").
4. **Separation of malicious and legitimate indicators.** Like the reference advisories, a report
   may list legitimate domains that were observed or abused. This is how the **noisy** variant
   (V2) adds unrelated-but-mentioned entities in a realistic way.

## What we do NOT do

- We do not use any real advisory's text, indicators, actor names, or victim details.
- We do not present reports as issued by CISA or any real agency. Every report carries a
  fictional issuer and a "SYNTHETIC — RESEARCH USE ONLY" marking.
- All IPs come from RFC 5737 documentation ranges; all domains are under `example.com`,
  `example.net`, or `example.org`.
