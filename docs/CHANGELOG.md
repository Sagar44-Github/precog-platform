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
