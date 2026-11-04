# Phase B4 — Forecast intelligence and analytics

Phase B4 adds a forecast ledger and explainability record, a read-only what-if preview, and a model analytics workspace. All predictions and actions remain part of the replay simulation.

## What changed

- `/forecasts` lists active-session predictions and can include the bounded archive; `/forecasts/:forecastId` shows each outcome and the evidence captured when the prediction was created.
- Forecast explanations record all feasible candidates, training transition counts, Markov probabilities/ranks, rule-based edge-likelihood probabilities/ranks, uniform ranks, smoothing alpha, and technique-hint source.
- `GET /api/x/forecasts/what-if?from_host=...` previews a ranking for a currently compromised host without mutating the graph, ledger, replay, or WorldState version.
- `/analytics` separates held-out evaluation results from the current/archived session tally, includes a calibration curve and both baselines, and preserves DETECT's offline report limitations.
- Archived sessions now retain forecasts and actions alongside alert evidence in the existing 20-session in-memory bound.
- Three contracts were added; `python contracts/check_contracts.py` reports **24 contracts OK**.

## Verification

- Full Python suite: **395 passed, 1 skipped**, with two known Scapy/cryptography TripleDES deprecation warnings.
- Web suite: **108 passed**.
- Contract checker: **24 contracts OK**.
- Vite production build: passed; the existing Three.js chunk-size warning remains.
- Golden Path: **2 consecutive PASS runs** at 1× (4.91s to decision and 2.30s to finish on run one; 4.77s and 2.25s on run two).
- Chromium audit: **69 checks in sample mode and 69 in live mode**, at 390x844, 820x1180, and 1440x900; zero failures and zero browser errors. The live propose/confirm containment workflow completed and changed host state only in the simulation.
- Screenshots: **138 Chromium captures** across the three viewports and both modes.
- Hosted-style readiness check: **12 checks passed; READY for the demo** using the built bundle served by Flask over the same-origin `/app/` path.

Build notes: `npm ci` reports 8 dependency audit advisories (3 moderate, 5 high), and Vite reports the existing Three.js chunk above 500 kB. The lockfile was not changed during B4; these are tracked for the final dependency/performance review.

## Evidence

- `browser-audit-results.json` — route, viewport, export, print, and workflow checks.
- `screenshots/` — sample and live Chromium captures.
