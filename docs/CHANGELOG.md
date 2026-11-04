# Changelog

## Phase B1 — App shell and design system (2026-11-04)

- Added a persistent desktop workspace rail, operator actions, shared SIMULATION label, breadcrumbs, and a compact command launcher.
- Added the Ctrl/Cmd+K command palette with keyboard search, navigation, replay action, and theme switch.
- Added dark and light themes backed by shared CSS tokens. The 3D scene and Chart.js views refresh when the theme changes.
- Added a clear mobile SOC handoff below 1024 px; the desktop 3D console stays on wide screens.
- Restyled shared surfaces and reduced decorative glow while preserving the simulation label, shape-coded states, and two-step containment.
- Added B1 browser evidence and screenshots under `docs/phase-b1/`.
- No API endpoint or data contract changed in this phase.

## Phase B2 — Operator workspaces (2026-11-04)

- Added deep-linkable authenticated pages for alert search/detail, host inventory/detail, audit history, system health, and local settings.
- Added alert severity/host/technique/time filters, sort, cursor paging, safe CSV export, and JSON export.
- Added a six-host inventory enriched with topology services, risk, criticality, outbound reachability, synthetic `DEMO-` weaknesses, and replay state history.
- Added filtered audit log access that skips malformed lines and retains valid entries; added runtime health and version details.
- Added persisted browser preferences for theme, table density, and default alert severity.
- Added four JSON contracts and their samples, bringing the checked contract count from 12 to 16.
- Added responsive stacked records for tablet/phone widths and expanded the shared navigation and command palette.
- Phase B2 routes and screenshots are documented under `docs/phase-b2/`.

## Phase B3 — Incidents and session reports (2026-11-04)

- Added incident cases grouped by replay session, combining the session's alerts, predictions, and simulated containment actions into one timeline.
- Added authenticated desktop and PWA incident filtering/detail, analyst notes, open/contained/closed status, and audit records for case changes.
- Preserved session alert evidence in bounded in-memory history so archived incident details remain available after a later replay reset.
- Added current and archived session report pages with printable layout, JSON export, timeline CSV export, and session-only forecast counters with explicit accuracy limitations.
- Added five contract schemas and samples, bringing the checker total to 21.
- Added browser route and interaction coverage for incidents and reports; screenshots and rehearsal evidence are in `docs/phase-b3/`.

## Phase B4 — Forecast intelligence and analytics (2026-11-04)

- Added a forecast ledger across the bounded 20-session archive, with detail routes that show the prediction outcome and the exact candidate evidence stored at generation time.
- Added model transition counts, smoothing alpha, technique-hint table source, and Markov, rule-based, and uniform ranks for each feasible candidate.
- Added a read-only what-if endpoint and preview for currently compromised hosts; it does not mutate world state or replay counters.
- Added model analytics for held-out evaluation, calibration, baselines, archived session tally, and the offline DETECT report with its limitations.
- Added three schemas and samples; the contract checker reports 24 valid contracts.
- Added B4 page tests and Chromium route/workflow evidence at 390, 820, and 1440 px under `docs/phase-b4/`.

## Phase B5 — Containment playbooks and demo roles (2026-11-04)

- Added `/app/containment` with host, zone, predicted-path, and Top-3 playbooks, an explicit target preview, action history, and a two-step administrator release flow.
- Extended containment actions to retain target lists, per-host previous states, operation/playbook metadata, linked release actions, and session ids. History can include the bounded archive.
- Added authenticated role profiles for viewer, analyst, and admin. Server guards deny viewers response/replay mutations, limit release and replay restart to admins, and expose effective permissions to the UI.
- Added optional `ANALYST_PASSWORD` and `VIEWER_PASSWORD` account seeding without modifying NIDS files.
- Added `operator_profile` and `containment_playbook_request` schemas/samples; expanded `containment_action`; the checker reports 26 contracts.
- Added API, service, startup, and page tests. Chromium evidence and screenshots are stored under `docs/phase-b5/`.

## Phase B6 — Replay studio and scenario builder (2026-11-05)

- Added `/app/replay` for scenario control, 1×–8× speed, pause/resume, one-event stepping, read-only time travel, and finished-session comparison.
- Added `/app/scenarios` with the shipped/custom library and a visual builder for technique, traffic, and host-attempt events; server validation checks schema, sequence, offsets, and known hosts before atomic local save.
- Added a 200-snapshot in-memory ring buffer and read-only time-travel and session-comparison endpoints.
- Added the `time_travel_snapshot` and `session_comparison` contracts; bounded GRAPH scenario descriptions and event count.
- Added backend, controller, builder, comparison, and page regression tests. Phase evidence is stored under `docs/phase-b6/`.

## Phase B7 — Topology explorer and Lite mode (2026-11-05)

- Added `/app/console/topology` with host inspection, risk/forecast/synthetic-weakness overlays, camera presets, selection focus, a mini-map/view cube, read-only time travel, and PNG export.
- Consolidated the renderer into a shared 3D component; added lit low-poly host models, zone platforms, attack propagation, forecast cones, compromise shockwaves, and containment shields.
- Added responsive SVG Lite topology for narrow screens, reduced-motion preferences, and environments without WebGL. The Lite view remains interactive and exports PNGs.
- Normalized modern CSS HSL theme values before passing colors to Three.js; added automatic pixel-ratio reduction below 40 fps.
- Added pure scene/camera tests and Chromium checks for desktop WebGL pixels, Lite rendering, no horizontal overflow, camera/overlay controls, and PNG exports.
- Phase evidence is stored under `docs/phase-b7/`.
