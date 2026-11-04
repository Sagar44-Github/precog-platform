# Phase B5 — Containment playbooks and demo roles

Phase B5 adds a dedicated containment workspace, multi-target simulated response playbooks, two-step release/undo, action history, and server-enforced viewer, analyst, and admin permissions. Every response remains a simulation and requires a separate proposal and confirmation. The NIDS source tree remains unchanged.

## Verification

- Python 3.11 project-venv suite: **416 passed, 1 skipped**. The skip is the existing optional Precog repository evaluation. Two Scapy/TripleDES deprecation warnings remain.
- Web suite: **111 passed**; the web test-runner path check also passed.
- Contract checker: **26 contracts OK**.
- Golden Path: **2/2 consecutive runs passed**.
- Chromium audit with software WebGL: **72 route and viewport checks in sample mode and 72 in live mode; zero failures and zero errors**. It also verified viewer UI restrictions, analyst proposal permission, analyst restart denial, viewer replay/containment denial, and live propose-then-confirm containment.
- Local hosted readiness against the rebuilt static bundle: **13/13 checks passed; READY for the demo**.

## Browser evidence

The audit captured 146 screenshots (three viewport widths across login and the app routes, plus one viewer containment view per mode). See the [browser audit report](browser-audit-results.json) and the [screenshots folder](screenshots/).

Selected views:

- [Containment workspace, admin](screenshots/sample-containment-1440x900.png)
- [Containment workspace, viewer](screenshots/sample-containment-viewer-1440x900.png)
- [Live 3D console](screenshots/live-console-1440x900.png)
- [Containment workspace on a phone viewport](screenshots/sample-containment-390x844.png)

## Known verification notes

- The main Three.js bundle remains above Vite's 500 kB advisory threshold; the build succeeds and route loading was verified.
- FCM credential signing is optional at runtime. `google-auth[cryptography]` is now declared so the FCM sender implementation and its key-generation test have the required crypto support.
- The skipped Precog evaluation needs `PRECOG_REPO_DIR`; it is unrelated to the containment changes.
