# Changelog

## Phase B1.5 — Interactive 3D landing experience (2026-11-05)

- Replaced the app's public default redirect with a public Precog SOC landing route. Authenticated console and phone routes remain protected.
- Made the 3D Golden Path network the main demonstration: users can orbit it, select hosts, step or scrub through detection, reconstruction, forecasting, and simulated containment.
- Added a designed SVG fallback for reduced motion and low-power browsing, with the same controls and copy.
- Generated forecasts, evaluation results, detector limitations, host details, topology, and credits from repository sources at build time.
- Added evidence and license notes, semantic/keyboard support, a browser audit, and screenshots under `docs/audit/screenshots/landing/interactive/`.
- Changed `/` to open the public landing page and made `/api/x/me` return a null identity for signed-out visitors; protected data routes still require login.
- No NIDS files or data contracts changed.

## Phase B1 — App shell and design system (2026-11-04)

- Added a persistent desktop workspace rail, operator actions, shared SIMULATION label, breadcrumbs, and a compact command launcher.
- Added the Ctrl/Cmd+K command palette with keyboard search, navigation, replay action, and theme switch.
- Added dark and light themes backed by shared CSS tokens. The 3D scene and Chart.js views refresh when the theme changes.
- Added a clear mobile SOC handoff below 1024 px; the desktop 3D console stays on wide screens.
- Restyled shared surfaces and reduced decorative glow while preserving the simulation label, shape-coded states, and two-step containment.
- Added B1 browser evidence and screenshots under `docs/phase-b1/`.
- No API endpoint or data contract changed in this phase.
