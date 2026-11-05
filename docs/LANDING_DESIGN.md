# Precog SOC landing experience

The Flask home route opens a public, scene-first Golden Path demonstration. A full-width Three.js network fills the hero; the headline, live forecast, selected-host detail, and replay controls appear as a compact SOC overlay. Users can orbit and inspect the hosts, then step the same network through detection, path reconstruction, forecasting, and confirmed containment.

The scripted landing walkthrough is public. `/api/x/me` reports a null username when signed out so the shell can initialize without an expected 401; protected state, alert, graph, replay, and action endpoints remain authenticated.

## Demonstration states

| State | Scene change | Source |
|---|---|---|
| Network | Six named hosts are arranged across the user, DMZ, and internal zones; feasible connections form the topology. | `contracts/data/hosts.json`, `graph/graph_net/data/topology.json` |
| Detect | Scripted traffic moves along its configured connections. Workstation A changes from a sphere to a red octahedron. | `graph/graph_replay/scenarios/golden-path.json` |
| Reconstruct | A red tube draws the scripted attempted path to Web Server B. | Golden Path scenario and topology |
| Forecast | Three violet paths show feasible next hosts. Their widths and displayed shares come from the node Markov model. | `lead-core/precog/precog_engine/data/node_model.json` |
| Contain | Web Server B becomes a teal cube inside a geometric lattice. The visible copy states that this is a simulation. | Golden Path attempt and forecast sources |

Users can select a state with the numbered step controls, scrub with a keyboard-operable range input, or play the sequence. Dragging the model rotates the view; selecting a host updates its DOM description. The title and forecast overlay let visitors understand the purpose while the network remains the main visual surface.

## Evidence and copy

The build script reads the replay scenario, topology, hosts, ATT&CK table, Precog evaluation, node model, DETECT report, and owner configuration. It hashes those inputs and generates `web/src/landing/data.generated.json`. Build and test hooks regenerate the file; the freshness test fails if it differs from the current sources.

The evidence section compares held-out precision@1 with the rule-based and uniform baselines and includes each standard error. It states that precision@3 is uninformative on the six-host graph and shows the DETECT report's unseen-type results, dataset, and random split limitation. The rehearsal itself is not used to calculate evaluation metrics.

Institution, course, guide, and optional team credits are configured in `web/landing.config.json`. Component credits and license notices are generated into the page from repository metadata and the ATT&CK notice.

## Rendering and fallback

The landing route, 3D scene, and authenticated console are separate lazy-loaded chunks. Three.js reads the current design tokens at runtime; lit host volumes, raised zone platforms, and shape and color distinguish normal, compromised, forecast, and contained states. The scene has no random particles or autoplaying attack sequence. Static states render on interaction; scripted packets animate during the incident steps.

Reduced-motion or save-data users, and browsers without WebGL2, receive a designed SVG network with the same replay controls. The visible version switch lets a user change modes at any time. Renderer quality starts at a device-aware tier, caps pixel ratio at 1.75 in high quality, 1.35 in balanced quality, and 1 in low-power mode, and can step down as frame time rises. Renderer geometries and textures are disposed when the scene unmounts.

All essential copy, forecasts, host selection, and controls are HTML. The canvas is marked decorative; a live DOM description reports the selected host and active state. The page has a skip link, semantic headings, keyboard controls, visible focus, a simulation label, responsive portrait framing, and reduced-motion support.

## Budgets and audit

The Playwright audit runs the built app under Chromium with SwiftShader at 390×844, 820×1180, and 1440×900. It captures each replay state, checks the canvas changes, tests host selection and orbiting, verifies the reduced version and sign-in destination, checks for horizontal overflow and layout shift, and confirms geometry and texture counts stay stable through repeated scrolling.

The current browser report is `docs/audit/landing-browser-report.json`; screenshots are in `docs/audit/screenshots/landing/interactive/`. The audit records gzip sizes for scripts downloaded before the 3D scene, whose target is at most 120 KB, plus FCP and CLS. The full 3D scene is intentionally lazy loaded. The Flask-served desktop Lighthouse 12.6 report is `docs/audit/landing-lighthouse-desktop.json` (performance 93, accessibility 100, best practices 100, SEO 100).

Run from `web/`:

```powershell
npm run build-landing-data
npm run check-landing-data
npm test
npm run build
npm run audit:landing
```

The repository's existing Python integration suites and `lead-core/integration/golden_path.py` continue to cover the backend demo and closed-loop behavior.
