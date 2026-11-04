# Phase B1 verification evidence

Phase B1 adds the shared SOC workspace shell, responsive console handoff, command palette, persisted light/dark theme, and a calmer visual system around the existing Three.js console and phone PWA.

## Verification

- Python project suite: **372 passed, 1 skipped**.
- Offline detection model suite: **50 passed, 1 skipped**.
- Web suite: **96 passed**.
- Vite production build: passed; the deployment bundle contains 16 files in `lead-core/backend/web_dist`.
- Golden Path rehearsal: **2 consecutive PASS runs**. Each run completed sign-in, replay, forecast, propose/confirm containment, blocked-hit resolution, re-evaluation, and session archival.
- Browser audit: **42 route/viewport checks passed** across sample and live modes at 390, 820, and 1440 pixels. No browser errors, route failures, or horizontal overflow were reported. The desktop console rendered a nonblank 3D canvas; Ctrl/Cmd+K navigation, theme persistence, and confirmed containment were exercised.

## Files

- `browser-audit-results.json` — detailed route checks, shell interactions, and browser diagnostics.
- `rehearsals.csv` — Golden Path rehearsal results and stage timings.
- `screenshots/` — 42 browser screenshots across login, console, and phone views at the three tested widths.

## Known build output

The frontend build succeeds with Vite's existing large-chunk warning (largest minified chunk is about 1.43 MB). The mobile component tests also emit React server-renderer `useLayoutEffect` warnings; the tests pass. `npm ci` reports 8 dependency audit findings (3 moderate, 5 high), which were not changed as part of this shell phase.
