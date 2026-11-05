# Phase B3 — Incidents and session reports

Phase B3 adds replay-session casework across desktop and phone, plus printable session reports. Every surface keeps the SIMULATION label and distinguishes predicted targets from observed alerts and response actions.

## What changed

- `/app/incidents` and `/app/incidents/:incidentId` provide searchable session-grouped case records, status, timeline, involved evidence, ATT&CK labels, analyst notes, and associated forecasts/actions.
- `/app/mobile/incidents` and `/app/mobile/incidents/:id` provide the same case review and note/status workflow inside the phone PWA.
- `/app/reports` and `/app/reports/:sessionId` list current and archived sessions and provide per-session counters, print, JSON export, and timeline CSV export.
- `WorldState` associates up to 200 alerts with each active session and retains those alerts in the existing bounded archive of up to 20 sessions. Notes and status are bounded in-memory annotations; they are not durable records.
- Incident note and status changes add scrubbed entries to DETECT's audit log. Reports compute forecast counters from that session's stored outcomes. The report explains that its counters are session scoped and precision@3 may be trivial when no more than three hosts are reachable.
- Added five schemas and samples. Together with the B2 schemas, the contract checker reports 21 valid contracts.

## Verification

- Full Python suite: **383 passed, 1 skipped**.
- Offline detection suite: **50 passed, 1 skipped**.
- Web suite: **106 passed**.
- Contract checker: **21 contracts OK**.
- Vite production build and bundled web copy: passed; the existing Three.js chunk-size warning remains. `npm ci` reports 8 dependency audit findings (3 moderate, 5 high).
- Golden Path: **4 PASS runs** at 1x; detailed timings are in `rehearsals.csv`.
- Browser audit: **120 checks passed** (60 sample, 60 live) at 390x844, 820x1180, and 1440x900, with no failures or browser errors. The live propose-and-confirm containment flow completed and changed the host state in simulation.
- Hosted-style smoke check against the production bundle: **12 checks passed** in live mode, including API health, registered modules, app shell, PWA install assets, sign-in, state, and scenarios.

## Evidence

- `browser-audit-results.json` — route, viewport, console/network, export, print, and workflow checks.
- `rehearsals.csv` — four deterministic replay runs and timing data.
- `screenshots/` — Chromium captures of login, console, mobile PWA, incident pages, reports, and B2 operations pages in sample and live modes.
