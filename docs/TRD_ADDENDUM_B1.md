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

Four contracts were added, each with a sample and checker coverage: `alert_page`, `audit_page`, `host_inventory`, and `system_status`. The contract checker now reports **16 contracts OK**. State history is retained in the in-memory `WorldState` as a bounded 20-entry list per host and resets with the current replay state. Audit reads use the existing scrubbed audit log and do not mutate it.

The B2 browser audit includes all existing routes and the seven new routes at 390x844, 820x1180, and 1440x900 in sample and live modes. It also checks table filters, both export downloads, saved settings, and the existing two-step live simulation containment flow. Evidence is stored in `docs/phase-b2/`.
