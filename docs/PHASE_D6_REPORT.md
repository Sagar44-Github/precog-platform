# Phase D6 — scalable topology verification

## Result

Large workspaces use server-paged host inventory, virtualized rows, and selectable zone clusters in 3D and Lite views. Host search, aggregated zone links, and the no-WebGL Lite fallback work with `synth-enterprise-300`.

## Checks

- Python: 559 passed, 1 skipped (560 collected).
- Web: 156 passed.
- Contract checker: 71 contracts OK.
- Playwright scale audit: zero browser errors; Lite view stayed within viewport at 390×844, 820×1180, and 1440×900; no-WebGL fallback rendered without a canvas; server-side host search found `node-0025`; segmentation preview succeeded.
- SwiftShader measurements for this run: topology view mean 17.98 ms/frame (89 samples), twin view mean 24.24 ms/frame (66 samples); measured JS heap 21.2 MB and 29.1 MB respectively. These are software-rendering observations, not hardware performance claims.
- Rebuilt Flask static bundle from the audited Vite build. A Flask smoke check returned HTTP 200 for `/app/` and `/api/x/health`.

Screenshots and probe output are in `docs/audit/screenshots/phase-d6/`. Browser measurements depend on the local Chromium/SwiftShader environment.
