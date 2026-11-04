# PRD Addendum — Phase B1

**Date:** 2026-11-04
**Applies to:** desktop shell, current console, login, and mobile SOC entry points.

This addendum extends the original PRD without changing its replay-only safety boundary, API requirements, or data contracts.

## New product requirements

| ID | Requirement | Priority | Acceptance |
|---|---|---:|---|
| FR-UI-1 | The authenticated desktop console shall use a persistent workspace navigation rail and a shared top bar with the current location, operator actions, and a visible SIMULATION label. | M | The rail, route context, sign-out action, and simulation label are present on the console at 1024 px and wider. |
| FR-UI-2 | The desktop shell shall provide a searchable command palette opened by Ctrl+K or Cmd+K. | M | Keyboard search and Enter navigate to the mobile SOC; commands also expose the current alert/report views, deterministic Golden Path start, and theme switch. |
| FR-UI-3 | The product shall offer dark and light themes using the shared semantic design tokens. | M | Theme choice applies to the shell, console, mobile screens, 3D scene, and charts; preference persists across reload. |
| FR-UI-4 | The desktop 3D console shall require a viewport at least 1024 px wide. Narrower viewports shall provide a clear route to the phone SOC. | M | At 390 px and 820 px, the handoff has no horizontal overflow and retains the SIMULATION label. |
| FR-UI-5 | Shared controls shall use a consistent icon set, visible keyboard focus, reduced-motion behavior, and concise operator-facing copy. | S | Keyboard and browser checks cover the shell controls; the existing reduced-motion and simulation behaviors remain active. |

## User flow update

An authenticated operator can move between the desktop console and phone SOC from the shared shell, use the command palette to reach existing console views, and choose a theme without losing the active replay or changing its state.

## Non-goals in B1

Incident, asset, forecast-ledger, playbook, analytics, and scenario-builder pages are scheduled for later B phases. B1 adds no server-side role model and no new backend API.

## Phase B2 product requirements

| ID | Requirement | Priority | Acceptance |
|---|---|---:|---|
| FR-OPS-1 | An operator shall search and filter the current alert buffer by text, severity, host, technique, and time range; select sort order and page through matching results. | M | API results match filters and paging; the browser table links to refresh-safe alert details. |
| FR-OPS-2 | An operator shall export the filtered alert result as CSV or JSON. | M | Both downloads contain the applied filter result; CSV cells are quoted and formula-like values are neutralized. |
| FR-OPS-3 | An operator shall inspect the six-host demo inventory, current state, zone, risk, criticality, services, simulated weaknesses, reachable demo hosts, and state history. | M | Host list and detail pages use live replay state and clearly label every synthetic weakness with a `DEMO-` id. |
| FR-OPS-4 | An operator shall search the scrubbed detection/forecast/containment audit records by type, reference, summary, and date range. | M | The reader skips corrupt lines without dropping valid records; the API remains authenticated and read-only. |
| FR-OPS-5 | An operator shall inspect module/hook registration, Python/Flask/SQLite versions, data mode, and basic readiness checks. | M | System status is available through a protected route and displays actual process values. |
| FR-OPS-6 | An operator may persist display density and default alert severity locally, alongside the existing theme. | S | Preferences survive reload in the same browser and do not alter model or detection behavior. |

The new pages preserve the replay-only safety boundary and show the shared SIMULATION label from the authenticated application shell. The audit and system workspaces are read-only.

## Phase B3 product requirements

| ID | Requirement | Priority | Acceptance |
|---|---|---:|---|
| FR-CASE-1 | An operator shall review one incident case per replay session, combining alerts, predicted targets, simulated actions, hosts, and ATT&CK labels into a time-ordered view on desktop and phone. | M | Desktop and PWA case lists/detail are deep-linkable; the desktop list is filtered by text, severity, and status. |
| FR-CASE-2 | An operator shall add bounded analyst notes and set case status to open, contained, or closed. | M | Mutations require login, are validated, remain in-memory, and create scrubbed audit records. |
| FR-REPORT-1 | An operator shall open a report for the current or an archived replay session. | M | The report contains session alerts, forecasts and outcomes, simulated actions, a timeline, and per-session counters. |
| FR-REPORT-2 | An operator shall print a report or export the report as JSON and its timeline as CSV. | S | The print stylesheet hides workspace chrome, and CSV formula-like values are neutralized. |

Incident cases are session groupings because the replay controller provides a stable session boundary for the scripted attack chain. Notes and case status are volatile demo annotations, not durable records. Report counters are calculated from the outcomes stored in that single session; they are not model-wide accuracy claims.

## Phase B4 product requirements

| ID | Requirement | Priority | Acceptance |
|---|---|---:|---|
| FR-PRE-1 | An operator shall review current and bounded archived forecasts, including whether each prediction hit, missed, or was superseded. | M | The ledger filters by status and opens a refresh-safe detail route; misses remain explicit. |
| FR-PRE-2 | A forecast detail shall explain the exact candidate set and ranks captured when it was made. | M | The record exposes transition counts, smoothing alpha, hint-table source, model probability, and rule-based/uniform rankings. |
| FR-PRE-3 | An operator shall request a what-if forecast from a currently compromised host. | M | The preview is read-only, validates host state, and leaves WorldState version, graph, forecast ledger, and replay unchanged. |
| FR-AN-1 | An operator shall compare Precog against held-out rule-based and uniform baselines and inspect calibration. | M | The page separates static held-out results from live session counters, shows calibration bins/curve, and states the precision@3 limitation. |
| FR-AN-2 | An operator shall inspect DETECT's offline model report and its dataset limitations beside, but distinct from, Precog results. | M | The page preserves report notes and explains that offline CICIDS2017 results are not comparable with the live Isolation Forest detector. |

The forecast ledger spans the existing bounded replay archive. Session counters remain session-scoped; the held-out evaluation file remains the source of model-level numbers, and Golden Path rehearsals never contribute to those numbers.

## Phase B5 product requirements

| ID | Requirement | Priority | Acceptance |
|---|---|---:|---|
| FR-RESP-1 | An operator shall propose simulated containment for one host, a zone, the known compromised path plus predicted candidates, or the forecast Top-3. | M | The action records every resolved target and prior state; no graph state changes until a permitted operator confirms. |
| FR-RESP-2 | An administrator shall propose and confirm release of an executed containment. | M | Release restores saved pre-containment states, creates its own audited action, and cannot bypass confirmation. |
| FR-RESP-3 | Operators shall inspect current and bounded archived containment history. | M | The page distinguishes contain/release actions, pending/confirmed outcomes, target scope, replay session, and re-evaluation text. |
| FR-ROLE-1 | The platform shall expose viewer, analyst, and admin demo roles layered over authenticated NIDS accounts. | M | `/api/x/me` returns the server-resolved role and permissions; no request field can select or raise a role. |
| FR-ROLE-2 | Viewers shall be prevented from containing hosts or starting, pausing, resuming, or restarting replay. | M | Mutating API calls return the common JSON 403 error for a viewer, even when called without the UI. |
| FR-ROLE-3 | Analysts may propose/confirm/cancel containment and control a replay; only admins may release containment or restart replay. | S | Capability response and server guards agree; the UI hides unavailable controls and displays the signed-in role. |

Containment playbooks remain fully simulated. The service publishes one explicit multi-target proposal and applies its targets together only after confirmation. Release stores the original state for each host, then restores those values after a second confirmation. Optional local passwords provision analyst and viewer NIDS accounts without changing NIDS source.

## Phase B6 replay studio and scenario design

| ID | Requirement | Priority | Acceptance |
|---|---|---:|---|
| FR-REPLAY-1 | An analyst shall select a shipped or locally authored scenario, set replay speed from 1× to 8×, pause, resume, restart when permitted, and step exactly one event while paused. | M | Replay state and event position stay synchronized with the replay controller; the server enforces role permissions. |
| FR-TIME-1 | An operator shall scrub a bounded history of world snapshots and inspect the graph, alerts, forecast, actions, replay position, and session metrics at each version. | M | Snapshots are captured as world versions change, retained in a fixed-size ring buffer, and never restore or mutate the live world. |
| FR-SCENARIO-1 | An analyst shall compose technique, traffic, and host-attempt events using the simulated host inventory, validate the scenario, and save it to the local scenario library. | M | The server applies the existing JSON Schema plus host/order checks, rejects invalid/duplicate ids, and only persists locally under the runtime data directory. |
| FR-COMPARE-1 | An operator shall compare two finished replay sessions side by side. | M | Alert volume, severity, forecast outcomes, and confirmed containment are derived from those sessions, with an explicit session-only accuracy note. |

All B6 capabilities remain replay-only. Custom scenario files are runtime data; time travel and comparison are read-only views of the bounded in-memory evidence.

## Phase B7: Topology explorer and Lite mode

Operators can open `/console/topology` to explore the same simulated network in 3D or a 2D isometric SVG fallback. Host selection reveals its state, simulated risk and synthetic weaknesses. The explorer provides forecast and risk overlays, camera presets, mini-map selection, time travel, and PNG export. Auto mode uses Lite for narrow viewports, reduced-motion preferences, or missing WebGL. The 3D renderer reads the shared theme tokens and reduces resolution when frame rate falls below 40 fps. No real vulnerability scan or network action is performed.
