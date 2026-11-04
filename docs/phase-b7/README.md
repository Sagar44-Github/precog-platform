# Phase B7 — Topology explorer and Lite mode

Branch: `codex/phase-b7-3d-topology`

`/app/console/topology` adds a standalone topology workspace alongside the live console. It supports host inspection, risk/forecast/synthetic-weakness overlays, isometric/top/side camera presets, selection focus, a mini-map, read-only time travel, and PNG export. Auto mode uses the keyboard-accessible SVG Lite view below desktop width, with reduced motion, or when WebGL is unavailable. Three.js colors are normalized from shared CSS tokens; the renderer drops its pixel ratio if measured frame rate falls below 40 fps.

## Verification

| Check | Result |
| --- | --- |
| Python suite | 428 passed, 1 skipped |
| Web suite | 123 passed |
| Contracts | 28 contracts OK; no new contracts were needed |
| Full Chromium route audit | 81 checks per mode in sample/live, 0 failures, 0 console errors |
| Final topology Chromium audit | 6 checks per mode at 390, 820, and 1440 widths; 0 failures, 0 console errors |
| 3D canvas / Lite workflows | Non-blank desktop canvas, Lite host rendering, overlay/camera controls, and both PNG downloads verified |
| Golden Path | 1 of 1 run passed; 5.48 s to decision and 2.45 s to finish |
| Production build | Passed; Vite reports the 3D chunk above its 500 kB advisory threshold |

Final focused audit: [browser-audit-results.json](browser-audit-results.json). Full application audit: [browser-audit-full-results.json](browser-audit-full-results.json). Golden Path record: [rehearsals.csv](rehearsals.csv).

## Screenshots

- [Topology explorer — desktop 3D](screenshots/sample-topology-1440x900.png)
- [Topology explorer — phone Lite](screenshots/sample-topology-390x844.png)
- [Topology explorer — tablet Lite](screenshots/sample-topology-820x1180.png)
- [Live topology — desktop](screenshots/live-topology-1440x900.png)

Screenshots were captured with Playwright Chromium using SwiftShader. This verifies the fallback and canvas rendering, but does not establish 60 fps on a physical mid-range laptop. Browser checks did observe a low frame rate under SwiftShader and verified that the renderer reduced resolution.
