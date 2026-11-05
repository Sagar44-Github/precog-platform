# Phase C Map and Verified Starting Baseline

**Started:** 2026-11-05

**Starting point:** `phase-c2-replay-studio` at `7c64a07`

**Current work branch:** `phase-c3-digital-twin`

**Scope now:** C1, C2 and C3 are complete. C4–C7 remain gated on review and approval of the preceding item.

## Phase B inventory

The repository contains `docs/phase-b1/README.md`, `docs/DEMO_SCRIPT_V2.md`, Phase B1 addenda, and the Phase A audit. I found no Phase B3–B7 delivery reports in this checkout. The attached Phase C prompt describes basic B3–B7 features; the table below records what is actually present in the current code and docs so C can extend those pieces without assuming missing workflows were delivered.

| Phase C item | What the current Phase B code delivers | Missing from the full C specification | Likely files or folders to change |
|---|---|---|---|
| **C1 Incident investigation** | Distinct security alerts, ATT&CK technique labels, alert timeline, live graph, forecast summaries, audit log, and single-host simulated containment. Phase B1 adds the workspace shell and mobile SOC routes. | Incident correlation and lifecycle; typed incident timeline; notes and status controls; incident filters, detail, exports, notifications and deep links; incident contracts; analyst/viewer authorization. | `lead-core/backend/addons/` (incident service, routes, role checks and world-state integration), `contracts/schemas/`, `contracts/samples/`, `lead-core/integration/tests/`, `web/src/areas/incidents/`, `web/src/App.jsx`, `web/src/shared/`, `docs/INCIDENTS.md`, `docs/audit/screenshots/phase-c/`. |
| **C2 Replay studio and builder** | Four shipped deterministic replay scenarios and start/pause/resume/restart controls. | Delivered in this phase: visual timeline builder, server validation and dry run, bounded user scenario library, step/step-back/seek and breakpoints, speed control, snapshots/time travel, persisted run archive and comparisons. | `graph/graph_replay/`, `lead-core/backend/addons/replay_studio.py`, `lead-core/backend/addons/routes.py`, replay contracts and tests, `web/src/areas/replay/`, `web/src/App.jsx`, `web/src/shared/`, `docs/REPLAY_STUDIO.md`. |
| **C3 Network digital twin** | A live 3D console graph and a separate interactive 3D landing scene, plus graph topology and a phone-friendly SOC view. | Delivered: read-only topology, host detail/history, feasible paths and segmentation projection; interactive zone-based 3D map with state/risk/forecast/exposure overlays, camera presets, focus, recorded-run scrubber, Lite map/list and phone host inventory. | `lead-core/backend/addons/network_twin.py`, `lead-core/backend/addons/routes.py`, `contracts/`, `web/src/areas/twin/`, `web/src/areas/console/Scene3D.jsx`, `sceneModel.js`, `sceneDecorations.js`, `objects3d.js`, tests and browser audit. |
| **C4 Precog decision and what-if lab** | Markov top-three forecasts, baseline/session metrics, calibration chart and a reproducible offline evaluation command. | Per-forecast candidate exclusions and formula explanation; read-only what-if; server evaluation runs, cache and experiment log; model card and per-profile analysis. | `lead-core/precog/precog_engine/`, `lead-core/backend/addons/`, forecast/what-if/evaluation contracts and tests, new forecast/lab/analytics web areas. |
| **C5 Response governance** | Propose/confirm/cancel for a single-host simulated containment, expiry, and audit events. | Role and playbook policy; impact previews; zone/path/top-three actions; approval records; release proposal/confirmation; governance history and UI. | `viz/viz_containment/` or a new add-on module, `lead-core/backend/addons/`, containment/approval contracts and tests, `web/src/areas/containment/`, role-aware navigation. |
| **C6 Connected story and final verification** | Phase B1 command palette, workspace navigation, theme persistence, and a 4–6 minute Golden Path demo script. | Entity-wide links/search, case report exports, notification centre, onboarding/help updates, ten-minute script, full Phase C route audits and final report. | `web/src/shared/`, workflow areas delivered by C1–C5, `docs/DEMO_SCRIPT_V3.md`, `docs/PHASE_C_REPORT.md`, audit scripts and screenshots. |
| **C7 Optional maintenance** | Audit documents eight npm advisories and an unverified Node 22 runtime. | Separate, incremental dependency-family upgrades with full regression after each. | `web/package.json`, lockfile, CI/runtime docs; only after C1–C6 are green and approved. |

## Verified baseline

Environment: Windows 11 desktop, PowerShell, Python 3.11.9, repository `.venv`, offline-model `.venv`, Node/npm from the installed environment, Playwright Chromium with SwiftShader.

| Check | Command or procedure | Current result |
|---|---|---|
| Full Python suite | `.venv/Scripts/python.exe -m pytest -o "addopts=" -p no:cacheprovider --tb=short` | **374 collected; 373 passed, 1 skipped**, 2 warnings, 37.88 s. The skip is the optional Precog repository test. |
| Offline detector suite | `detect/offline_model/.venv/Scripts/python.exe -m pytest -o testpaths=. -o "addopts=" -p no:cacheprovider --tb=short` | **51 collected; 50 passed, 1 skipped**, 27.50 s. |
| Web suite | `npm test` in `web/` | **106 passed, 0 failed, 0 skipped**. React server-renderer `useLayoutEffect` warnings are present. |
| Contracts | `.venv/Scripts/python.exe contracts/check_contracts.py` | **12 contracts OK**. |
| Browser audit | `npm run audit:browser` in `web/` | **42 checks** across sample/live and 390×844, 820×1180, 1440×900; **0 failures and 0 browser errors**. Confirmed containment flow passes. |
| Golden Path | `.venv/Scripts/python.exe lead-core/integration/golden_path.py --runs 2 --speed 1` | **2 of 2 PASS**. Decision reached in 4.56 s and 4.61 s; replay completed 2.30 s and 2.31 s after confirmation. |
| Hosted-style readiness | `.venv/Scripts/python.exe docs/audit/run_hosted_check.py` | All 13 application checks pass and print `READY for the demo`, but the wrapper exits 1 because Windows reports `PermissionError [WinError 32]` while deleting its redirected `backend.log`. The application readiness passes; wrapper cleanup is a known baseline defect to repair before claiming a clean hosted-check command. |
| Precog evaluation | `.venv/Scripts/python.exe lead-core/precog/tools/evaluate_precog.py` | **149 held-out forecasts**, 60 test / 240 train, α=.01; P@1 **0.6510**, rule baseline **0.6376**, uniform **0.5503**, P@3 **1.0000** (trivial for at most three candidates), ECE **0.0572**, P@1 standard error **0.0390**. Values reproduce the shipped evaluation. |
| Production web build | `npm run build` in `web/`; copied with `deploy/build_web_bundle.py::copy_dist` | Build succeeds; existing Vite large-chunk warning remains. The Flask-served bundle was refreshed to **20 files** on the starting branch. |

Browser audit artifacts were restored after measurement so baseline verification does not replace the checked-in Phase B evidence. The repository's pre-existing untracked landing audit screenshots were left untouched.

## C1 delivered

C1 extends the existing alerts, graph, forecasts, replay, containment, and Phase B1 shell with an incident workbench; it does not implement C2–C7. Incidents correlate scripted alerts deterministically with explainable grouping reasons, severity roll-up, typed timelines, status transitions, notes, JSON/Markdown export, and an atomic bounded audit ledger. Viewer, analyst, and admin permissions are checked on the server; the UI mirrors those permissions. The Golden Path decision is preserved: once its predicted move is blocked by the one confirmed containment, the incident is marked contained while still listing `host-a` as compromised and explaining that the movement was stopped rather than every affected asset being remediated.

New endpoints: `GET /api/x/feed`, `GET /api/x/role`, `GET /api/x/incidents` (filters and cursor paging), `GET /api/x/incidents/{id}`, `GET /api/x/incidents/{id}/timeline`, `GET /api/x/incidents/{id}/export?format=json|markdown`, `POST /api/x/incidents/{id}/notes`, and `POST /api/x/incidents/{id}/status`. C1 adds six schemas and samples: `incident`, `incident_note`, `timeline_event`, `feed_versions`, `role_info`, and `incident_audit_entry`.

The replay controller extension passes optional severity through only when a hook accepts it; shipped callers remain compatible. `quiet-scan` now marks its scripted alerts LOW so the acceptance scenario has the specified low-severity classification. No NIDS source files changed.

## C1 verification

Environment: Windows 11 desktop, PowerShell, Python 3.11.9, repository `.venv`, offline-model `.venv`, Node/npm, Playwright Chromium with SwiftShader.

| Check | Command or procedure | C1 result |
|---|---|---|
| Full Python suite | `.venv/Scripts/python.exe -m pytest -o "addopts=" -p no:cacheprovider --tb=short` | **390 collected; 389 passed, 1 skipped**, 2 existing Scapy deprecation warnings, 42.25 s. |
| Offline detector suite | `detect/offline_model/.venv/Scripts/python.exe -m pytest -o testpaths=. -o "addopts=" -p no:cacheprovider --tb=short` | **50 passed, 1 skipped**. |
| Web suite | `npm test` in `web/` | **113 passed, 0 failed, 0 skipped** across 22 files. |
| Contracts | `.venv/Scripts/python.exe contracts/check_contracts.py` | **18 contracts OK** (six added). |
| Browser audit | `npm run audit:browser` in `web/` | **54 checks**, sample/live at 390×844, 820×1180, 1440×900; **0 failures, 0 browser errors, 0 axe violations**. The incident note flow and live simulated containment pass. |
| Browser evidence | `docs/audit/phase-c/browser-audit-results.json` and `docs/audit/screenshots/phase-c/` | **54 screenshots** saved. |
| Golden Path | `.venv/Scripts/python.exe lead-core/integration/golden_path.py --runs 2 --speed 1` | **2 of 2 PASS**; both runs confirmed proposal-before-confirmation, one executed simulated containment, blocked-hit outcome, and replay completion. |
| Hosted-style readiness | Local server plus `lead-core/integration/check_hosted.py` | **12 checks OK; READY for the demo**. No public Render deployment or physical-phone installation was performed. |
| Web build and hosted bundle | `npm run build` in `web/`; copied `web/dist` to `lead-core/backend/web_dist` | Build succeeds; hosted bundle refreshed to **22 files**. Vite reports a large-chunk warning; main JS is 827.91 kB (240.10 kB gzip), below the 1.43 MB starting audit figure. |
| Scenario acceptance | `test_golden_path_lateral_spread_quiet_scan_and_repeat_determinism` | Golden Path: exactly one contained incident, one executed action, blocked-hit forecast, source compromise shown. Lateral spread: one growing incident. Quiet scan: one LOW, open incident. Repeated quiet scans normalize identically. |
| Diff hygiene | `git diff --check`; NIDS path check | No whitespace errors and no changes under `lead-core/backend/nids/`. |

C1 is complete on `phase-c1-incidents`. C2 and C3 implementation and verification are recorded below; C4–C7 remain gated on review/approval. The existing dependency advisories and Vite chunk warning remain; Render and physical-phone behavior are unverified.

## C2 delivered

C2 extends the shipped scenario library and replay controls with a scenario builder and replay studio. Analysts can validate and dry-run a scenario, save and edit `user-` scenarios, control playback from 0.25× to 8×, set event breakpoints, step forward and back, and inspect or seek recorded snapshots. Finished runs are saved for comparison, with at most 50 finished runs and 2,000 active snapshots retained. User scenarios are capped at 50 and each scenario is capped at 200 events and two hours. Persisted JSON files are written atomically beneath `lead-core/backend/data/`; no supplied scenario content is executed as code.

The C2 routes cover scenario library/options/detail/export, validation/dry-run/save/delete, studio status/start/step/step-back/seek/speed/breakpoints, finished run list/detail/compare/snapshot index, and the shared snapshot lookup. The shared feed now includes the runs version. New contracts and samples: `breakpoint_set`, `run_comparison`, `run_detail`, `run_snapshot`, `run_summary`, `scenario_builder_options`, `scenario_draft`, `scenario_dry_run`, `scenario_library`, `scenario_summary`, `scenario_validation`, `snapshot_index`, and `studio_status` (13 total). See [REPLAY_STUDIO.md](REPLAY_STUDIO.md) for endpoint and behavior details.

## C2 verification

| Check | Command or procedure | Result |
|---|---|---|
| Full Python suite | `.venv/Scripts/python.exe -m pytest -o "addopts=" -p no:cacheprovider --tb=short` | **400 collected; 399 passed, 1 skipped**, 2 existing warnings. The skip is the optional Precog repository test. |
| Web suite | `npm test` in `web/` | **122 passed, 0 failed, 0 skipped** across 24 web test files. Existing React `useLayoutEffect` server-render warnings remain. |
| Contracts | `.venv/Scripts/python.exe contracts/check_contracts.py` | **31 contracts OK**. |
| Production build | `npm run build` in `web/` | Succeeded. Main application chunk: 189.26 kB (61.29 kB gzip); graph chunks remain split. Vite still warns about the 827.91 kB graph chunk. |
| Browser workflow audit | `npm run audit:browser` in `web/` | **96 checks; 0 failures, 0 browser errors, 0 axe violations**. Sample/live at 390×844, 820×1180 and 1440×900. Builder, validation, dry run, save, stepping, comparison route, and live propose/confirm flow pass. |
| Browser evidence | `docs/audit/phase-c/c2-final/browser-audit-results.json`; `docs/audit/screenshots/phase-c/c2-final/` | **96 screenshots**. |
| Scenario/replay acceptance | C2 integration tests and browser flow | Dry-run does not mutate live state; route-level tests compare two distinct run IDs and verify snapshots, stepping, step-back, speed and breakpoints. |
| Golden Path | C1 integration tests included in the full Python suite | Passed; C2 snapshot capture no longer alters incident correlation. |
| Hosted bundle and readiness | Build/copy `web/dist` into `lead-core/backend/web_dist`; run `lead-core/integration/check_hosted.py` against the local live service | **24 web files copied; 12 readiness checks passed**, including PWA assets, login, live state and scenario library. |
| Golden Path rehearsal | `.venv/Scripts/python.exe lead-core/integration/golden_path.py --runs 2 --speed 1` | **2 of 2 PASS**; propose then confirm, blocked hit, re-evaluation, and replay completion. |
| Diff hygiene | `git diff --cached --check`; NIDS path check | Clean staged diff; no changes under the pinned `lead-core/backend/nids/` tree. |

C2 implementation and verification are complete on `phase-c2-replay-studio`.

## C3 delivered

C3 adds a read-only digital twin on top of the existing graph hook and C2 snapshot archive. The desktop `/twin` workbench combines the 3D zone map, host inspector, path alternatives, model-estimated risk/forecast/exposure overlays, isometric/top/side camera presets, focus controls, snapshot time travel and a read-only segmentation projection. `/hosts`, `/hosts/:id` and `/mobile/hosts` provide asset inventory and host detail/history. The phone-width twin switches to a compact Lite host list; the full Lite topology view remains keyboard operable.

New endpoints: `GET /api/x/topology`, `GET /api/x/topology/paths`, `GET /api/x/topology/segmentation-preview`, `GET /api/x/hosts/{id}`, and `GET /api/x/hosts/{id}/history`. All are authenticated and read-only. Five schema/sample pairs were added: `topology`, `topology_paths`, `host_detail`, `host_history`, and `segmentation_preview`. The existing world-state contract is unchanged. No files under `lead-core/backend/nids/` were changed.

## C3 verification

| Check | Command or procedure | Result |
|---|---|---|
| Full Python suite | `.venv/Scripts/python.exe -m pytest -o "addopts=" -p no:cacheprovider --tb=short` | **406 collected; 405 passed, 1 skipped**, 2 existing Scapy deprecation warnings. The skip is the optional Precog repository test. |
| Offline detector suite | `.venv/Scripts/python.exe -m pytest -o testpaths=. -o "addopts=" -p no:cacheprovider --tb=short` from `detect/offline_model/` | **50 passed, 1 skipped**. |
| Web suite | `npm test` in `web/` | **126 passed, 0 failed, 0 skipped** across 24 files; existing React server-render `useLayoutEffect` warnings remain. |
| Contracts | `.venv/Scripts/python.exe contracts/check_contracts.py` | **36 contracts OK**. |
| Production build | `npm run build` in `web/` | Succeeded. Main app chunk **191.59 kB** (66.21 kB gzip), compared with the C2 main chunk at 189.26 kB. 3D renderer remains a separate lazy chunk at **817.38 kB** (236.68 kB gzip); the existing Vite large-chunk warning remains. |
| Browser audit | `npm run audit:browser` in `web/`, software WebGL/SwiftShader, sample and live modes at 390×844, 820×1180 and 1440×900 | **120 checks; 0 failures, 0 browser errors, 0 axe violations**. Covered the network twin, host inventory/detail and mobile hosts. The interaction flow selected Web Server B, traced routes, changed overlay/camera, switched to Lite and scrubbed a recorded snapshot. |
| Browser screenshots and frame probe | `docs/audit/screenshots/phase-c/c3-final/`; `docs/audit/phase-c/c3-final/browser-audit-results.json` | **120 screenshots**. SwiftShader probe: 24 frames per mode, mean interval **16.06 ms sample / 16.15 ms live**, p95 **16.7 ms** in both runs. These describe the software-rendered audit environment only. |
| Golden Path | `.venv/Scripts/python.exe lead-core/integration/golden_path.py --runs 2 --speed 1` | **2 of 2 PASS**; proposal/confirmation, blocked-hit forecast, containment and re-evaluation passed. |
| Hosted-style readiness | Local live service serving `lead-core/backend/web_dist`, then `lead-core/integration/check_hosted.py http://127.0.0.1:55180 …` | **13 checks pass; READY for the demo**, including the refreshed Flask-served PWA assets. No public Render deployment or physical-phone installation was performed. |
| Hosted bundle | `copy_dist('web/dist', 'lead-core/backend/web_dist')` | **28 files copied**. |
| Diff hygiene | `git diff --check`; pinned NIDS path check | No whitespace errors and no edits under `lead-core/backend/nids/`. |

C3 implementation and verification are complete on `phase-c3-digital-twin`. C4–C7 remain gated. Public hosting and physical-phone installation are not verified.
