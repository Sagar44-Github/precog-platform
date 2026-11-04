# Phase B2 verification evidence

Phase B2 adds authenticated operations pages for alert review, assets, audit records, system health, and local operator preferences.

## Verification results

- Full backend suite: **379 passed, 1 skipped**.
- Offline detection model suite: **50 passed, 1 skipped**.
- Web suite: **103 passed**.
- Contract checker: **16 contracts OK**.
- Production Vite build: passed. The existing large Three.js bundle warning remains.
- Hosted-style readiness checker: all checks passed against a local Waitress server using the committed `lead-core/backend/web_dist` bundle; it reported **READY for the demo**.
- Golden Path: **2 consecutive PASS runs** at 1x; timing and result rows are in `rehearsals.csv`.
- Chromium audit: **42 checks in sample mode and 42 in live mode**, across 390x844, 820x1180, and 1440x900. All **84 checks passed**, with no browser errors, failed network requests, horizontal document overflow, or missing simulation labels.
- Browser interactions passed for Ctrl/Cmd+K navigation, theme persistence, density persistence, alert filtering, CSV and JSON downloads, and live propose-then-confirm containment.

## Routes and data

- `/app/alerts` and `/app/alerts/:alertId`
- `/app/hosts` and `/app/hosts/:hostId`
- `/app/audit`
- `/app/system`
- `/app/settings`
- New protected API routes: `GET /api/x/alerts/search`, `/api/x/assets`, `/api/x/audit`, and `/api/x/system`.
- New contracts: `alert_page`, `audit_page`, `host_inventory`, and `system_status`.

Host weaknesses are synthetic demo inputs, carry `DEMO-` ids, and are labelled as simulated in the UI and API. UI preferences remain in the browser and do not alter detection or model thresholds.

## Evidence files

- `browser-audit-results.json` — checks, browser diagnostics, containment result, and interaction results.
- `rehearsals.csv` — two successful end-to-end replay rehearsals with stage timing.
- `screenshots/` — login, console, mobile SOC, and B2 routes for both data modes at all three target widths.

## Known output

Vite reports the existing large minified Three.js chunk. `npm ci` reports 8 existing dependency audit findings (3 moderate, 5 high); dependency versions were not changed as part of B2. The web SSR component tests emit React `useLayoutEffect` warnings from existing mobile `MemoryRouter` test rendering; all tests pass. Python output contains the existing Scapy/cryptography TripleDES deprecation warning. No external Render deployment or Firebase project was exercised in B2.
