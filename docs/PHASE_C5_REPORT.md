# Phase C5 report — response playbooks and action governance

**Branch:** `phase-c5-response-governance` (branched from `phase-c4-precog-lab`).
**Purpose:** simulation-only governed response with preview, confirmation, release, policy enforcement and audit records.

## Delivered

- Five data-driven playbooks: single host, zone, predicted path, Top-3, and release host.
- A server-side policy matrix: analysts may contain one host; only admins may run broad actions or release a host. Optional two-person approval for zone containment is controlled by `REQUIRE_TWO_PERSON_ZONE_APPROVAL` and defaults off for a one-admin demo.
- Impact preview with affected hosts, feasible edges, summed criticality, estimated forecast probability removed/restored, side effects, and replay re-evaluation wording.
- Two-step proposals, confirmations, cancellations, approvals/rejections, expiry, stale-session rejection, overlap protection, per-host calls through the existing containment service, and reasoned simulated release.
- Atomic bounded governance ledger beneath the ignored backend data folder and audit entries in the existing audit stream. JSON and Markdown exports are available.
- `/containment` workbench with role-aware controls, confirmation dialog, searchable history status filter, exports, links from incident/host/console views, and a phone entry from the Mobile SOC.
- Four contracts and samples; server, policy/state-machine, export, persistence, audit and UI logic tests.

## Routes

- `GET /api/x/containment/playbooks`
- `POST /api/x/containment/preview`
- `GET /api/x/containment/governance`
- `GET /api/x/containment/governance/export?format=json|markdown`
- `POST /api/x/containment/governance/propose`
- `POST /api/x/containment/governance/approve`
- `POST /api/x/containment/governance/confirm`
- `POST /api/x/containment/governance/cancel`
- Web page: `/app/containment`

Existing `/api/x/containment/*` single-host routes and the `containment_action` contract remain unchanged.

## Verification

Targeted C5 verification during implementation:

| Check | Result |
|---|---|
| `.venv/Scripts/python.exe -m pytest -o "addopts=" -p no:cacheprovider --tb=short` | 429 collected; 428 passed, 1 skipped; 2 existing Scapy deprecation warnings |
| Offline model suite from `detect/offline_model/` | 50 passed, 1 skipped |
| `npm test` | 130 passed, 0 failed |
| `python contracts/check_contracts.py` | 46 contracts OK |
| `npm run audit:browser` | 150 checks across sample/live and all three viewports; 0 failures, browser errors or axe violations; 150 screenshots |
| Browser workflow | Both demo modes previewed and confirmed an admin zone action, then proposed and confirmed a reasoned host release. The live run also passed the original single-host containment flow. |
| Production build and hosted bundle | Build succeeded; 32 files copied. Main app chunk 195.96 kB (62.57 kB gzip), renderer stays lazy-loaded; Vite's existing large-chunk warning remains. |

The post-merge Phase A/B/C totals, hosted readiness and Golden Path rerun are recorded after integration. Cloud deployment and physical-phone installation are not claimed.

## Limitations

- Two-person zone approval is optional and off by default so the default classroom demo can complete with one admin account.
- Expiry is materialized by the governance feed/history poll or the next state transition; the browser workbench polls every five seconds.
- Impact uses the current scripted forecast and static demo topology. It does not model business-service dependencies or real enforcement latency.
