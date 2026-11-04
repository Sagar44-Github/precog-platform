# TRD Addendum — Phase B1

**Date:** 2026-11-04
**Branch:** `codex/phase-b1-app-shell`

## Frontend structure

- `web/src/App.jsx` owns the authenticated route shell and wraps the current console route with `AppShell`.
- `web/src/shared/AppShell.jsx` provides workspace navigation, breadcrumb, operator sign-out, command trigger, command palette, and the under-1024 px handoff.
- `web/src/shared/icons.jsx` is the local 1.5 px stroke SVG icon set. It adds no runtime dependency.
- `web/src/shared/theme-context.jsx` owns the `ThemeProvider`, `useTheme`, and shared theme toggle. The preference key is `precog-color-theme`; values are `dark` or `light`.
- `web/src/shared/theme.css` owns semantic color tokens and the light theme. Screens continue to read semantic variables rather than declaring color literals.
- `web/src/areas/console/Scene3D.jsx` recreates the six-host scene when the theme changes. Both Chart.js components recreate their chart when the theme changes.

## Route and event behavior

| Route | B1 behavior |
|---|---|
| `/app/login` | Existing login with a theme toggle and permanent simulation notice. |
| `/app/console` | Existing 3D console inside the desktop workspace at viewport widths of 1024 px or more. |
| `/app/console` below 1024 px | A static handoff page links to `/app/mobile`; the heavy console scene is not mounted. |
| `/app/mobile/*` | Existing PWA routes remain unchanged and include the theme toggle. |

The command palette sends a local `precog:console-command` browser event for existing console actions (`view` and `start-demo`). This event is not a backend API and does not bypass replay controls or containment confirmation.

## API and contract table

| Surface | Change |
|---|---|
| `/api/x/*` endpoints | None |
| JSON schemas / contracts | None |
| Authentication / containment rules | Unchanged; sign-out still uses the existing authenticated logout route; containment remains propose then confirm. |

## Verification additions

- `web/src/shared/app-shell.test.jsx` checks shell navigation, simulation labeling, command inventory, and narrow handoff.
- `web/scripts/browser-audit.mjs` now writes to `AUDIT_OUTPUT_DIR` when provided, checks desktop shell/handoff behavior, tests Ctrl+K and theme persistence, and reserves the canvas pixel check for desktop-width console captures.
- B1 evidence is stored in `docs/phase-b1/browser-audit-results.json` and `docs/phase-b1/screenshots/`.

## Phase B2 route and API additions

The existing route entry points remain intact. The following authenticated React routes are deep-linkable below `/app/` and load their data through the same Flask origin:

| React route | Page |
|---|---|
| `/alerts` | Searchable, filterable event table with CSV/JSON export |
| `/alerts/:alertId` | Alert evidence and ATT&CK context |
| `/hosts` | Six-host asset inventory |
| `/hosts/:hostId` | Asset profile, simulated weaknesses, reachability, and state history |
| `/audit` | Filtered read-only audit viewer |
| `/system` | Module, hook, version, and readiness view |
| `/settings` | Local theme, density, and default alert severity controls |

The app shell shows these workspaces at narrow widths too, using an icon rail and stacked record cards. The existing `/console` route keeps its under-1024 px handoff, and the `/mobile/*` PWA routes remain independent.

| Method and endpoint | Auth | Behavior |
|---|---|---|
| `GET /api/x/alerts/search` | Required | Filters by `q`, `severity`, `host`, `technique`, `from`, `to`; sorts by `ts`, `risk_score`, or `severity`; cursor-pages up to 200 buffered alerts. |
| `GET /api/x/assets` | Required | Joins `contracts/data/hosts.json`, the GRAPH topology, current world graph state, and bounded per-host state history. Synthetic weaknesses carry `simulated: true` and `DEMO-` identifiers. |
| `GET /api/x/audit` | Required | Filters the DETECT JSON-lines log by type, reference id, summary, and time; skips invalid lines while retaining valid entries. |
| `GET /api/x/system` | Required | Returns data mode, world version, hook/module registration, Python/Flask/SQLite versions, contract validation, and audit-path availability. |

Alert CSV/JSON generation runs client-side against the same filtered search API. Settings are local browser preferences (`precog-ui-preferences`) and add no server endpoint.

## Phase B2 contracts and verification

Four contracts were added, each with a sample and checker coverage: `alert_page`, `audit_page`, `host_inventory`, and `system_status`. The contract checker then reported **16 contracts OK**. State history is retained in the in-memory `WorldState` as a bounded 20-entry list per host and resets with the current replay state. Audit reads use the existing scrubbed audit log and do not mutate it.

## Phase B3 incidents and session reports

### Routes

| React route | Page |
|---|---|
| `/incidents` | Searchable replay-session case list |
| `/incidents/:incidentId` | Session evidence, timeline, status control, and analyst notes |
| `/reports` | Current and archived session report index |
| `/reports/:sessionId` | Printable report with JSON and timeline CSV export |
| `/mobile/incidents` | PWA session case list |
| `/mobile/incidents/:id` | PWA case timeline, status, evidence, and analyst notes |

### API

| Method and endpoint | Auth | Behavior |
|---|---|---|
| `GET /api/x/incidents` | Required | Filters session cases by query, status, and severity; returns contract-validated pages. |
| `GET /api/x/incidents/{incident_id}` | Required | Returns timeline, involved hosts, techniques, alert records, forecasts/outcomes, actions, notes, and status. |
| `POST /api/x/incidents/{incident_id}/notes` | Required | Adds a 1–2000 character in-memory note attributed to the signed-in operator; writes a scrubbed incident audit record. |
| `PATCH /api/x/incidents/{incident_id}/status` | Required | Sets `open`, `contained`, or `closed`; writes a scrubbed incident audit record. |
| `GET /api/x/reports` | Required | Lists current and bounded archived replay-session summaries. |
| `GET /api/x/reports/{session_id}` | Required | Returns session-specific alerts, forecasts, outcomes, actions, timeline, and computed session counters. |

`WorldState` now keeps up to 200 alert records with the active session and stores those records in the existing bounded session history when a replay completes. Incident annotations are keyed by incident id and remain volatile in-memory state. The active session takes precedence over an archive record with the same id, which keeps the view correct when the sample loader reuses its demonstration id.

Five contracts were added: `incident_detail`, `incident_note`, `incident_page`, `report_page`, and `session_report`. The existing `session_record` allows archived alert evidence, and `audit_entry`/`audit_page` now include incident records. At the B3 gate, `python contracts/check_contracts.py` reported **21 contracts OK**. Every add-on route retains the common JSON error shape and JSON 401 behavior.

Forecast counters use resolved outcomes from that report's session. The report explicitly says that the counters are session scoped and that precision@3 may be trivial with at most three reachable candidates. Print CSS removes the desktop shell from the printed document; CSV values are quoted and formula-like cells are prefixed safely.

The B2 browser audit includes all existing routes and the seven new routes at 390x844, 820x1180, and 1440x900 in sample and live modes. It also checks table filters, both export downloads, saved settings, and the existing two-step live simulation containment flow. Evidence is stored in `docs/phase-b2/`.

## Phase B4 forecast ledger and analytics

### Routes

| React route | Page |
|---|---|
| `/forecasts` | Forecast ledger across current and bounded archived sessions, with read-only what-if preview |
| `/forecasts/:forecastId` | Captured prediction, Top-3 outcome, candidate transition counts, smoothing alpha, and baseline ranks |
| `/analytics` | Held-out Markov and baseline scores, calibration curve, session tally, and DETECT offline report |

### API

| Method and endpoint | Auth | Behavior |
|---|---|---|
| `GET /api/x/forecasts` | Required | Returns current-session forecasts by default; `include_archived=1` includes the bounded archive. Filters by status, source, session id, and starting host. |
| `GET /api/x/forecasts/{forecast_id}` | Required | Returns the recorded forecast including its captured candidate explanation. |
| `GET /api/x/forecasts/what-if?from_host=...` | Required | Requires a currently compromised host and returns a forecast preview without publishing it or mutating WorldState. |
| `GET /api/x/analytics` | Required | Reads held-out evaluation results and combines them with current session metrics, archived forecast tallies, and the offline detection report. |

`PrecogEngine.preview()` is shared by forecast creation and the read-only what-if endpoint. It captures every feasible candidate's training transition count, Markov probability/rank, rule-based edge-likelihood probability/rank, and uniform probability/rank. The explanation records alpha and technique-hint source so a later detail view does not reconstruct evidence from a changed graph. The what-if endpoint checks the selected host against the current graph snapshot and does not write a forecast, increment a model counter, or bump the world version.

When a replay session is archived, `WorldState` retains its forecasts and actions with the existing bounded session record. The ledger and analytics tally aggregate these records up to the existing 20-session limit. Session counters are clearly labelled as session counters; only the checked held-out evaluation artifact supplies model-level performance.

Three contracts were added: `forecast_explanation`, `what_if_forecast`, and `forecast_analytics`. `forecast` now allows an optional saved explanation and session id; archived `session_record` values retain the complete forecast/action lists. The checker reports **24 contracts OK**. Browser audit evidence and screenshots are stored in `docs/phase-b4/`.

## Phase B5 containment and demo roles

### Route

| React route | Page |
|---|---|
| `/containment` | Simulated playbooks, pending confirmations, current/archive action history, and administrator release flow |

### API additions and role gates

| Method and endpoint | Access | Behavior |
|---|---|---|
| `GET /api/x/me` | Signed in | Returns the authenticated username, resolved demo role, display label, and effective capabilities. |
| `POST /api/x/containment/playbooks/propose` | Analyst, admin | Validates a playbook selector, resolves a server-side target list from the current graph/forecast, and records a pending action. |
| `POST /api/x/containment/release/propose` | Admin | Creates a pending release action linked to an executed containment; the existing `/containment/confirm` endpoint completes it. |
| `GET /api/x/containment/actions?include_archived=1` | Signed in | Lists current actions and bounded archived session actions; the default remains current-session-only. |

The built-in demo accounts are `admin` (required), with optional `analyst` and `viewer` accounts seeded at startup when `ANALYST_PASSWORD` and `VIEWER_PASSWORD` are set. Role resolution uses only the authenticated NIDS username; the client cannot submit a role. Unknown usernames resolve to the least-privileged viewer role. Viewers cannot propose, confirm, or cancel containment, or start/pause/resume/restart replay. Analysts can propose/confirm/cancel containment and control replay. Admins can do all of those, plus release containment and restart replay.

The `ContainmentService` resolves host, zone, predicted-path, and Top-3 requests into a unique bounded host list, captures each target's previous state, and leaves the graph untouched while pending. Confirmation applies a contain action to all targets. A release is a separate pending action that restores saved states only after confirmation; it is rejected if any target is no longer contained or the source action was not executed. Contain and release proposals, confirmations, cancellation, expiry, and re-evaluation remain in the audit log. Session archives retain action metadata and the existing bounded retention limit.

Two contracts were added: `operator_profile` and `containment_playbook_request`; `containment_action` now permits the operation, playbook, target list, linked release, prior states, and replay session. The checker reports **26 contracts OK**. Browser screenshots cover `/containment` at 390x844, 820x1180, and 1440x900 in sample and live modes; API role checks prove viewer denial and analyst allowance. Evidence is stored in `docs/phase-b5/`.
