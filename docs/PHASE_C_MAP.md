# Phase C Map and Verified Starting Baseline

**Started:** 2026-11-05

**Starting point:** `phase-b1.5-precog-landing` at `6d12a82`

**Work branch:** `phase-c1-incidents`

**Scope now:** establish the map and baseline, then implement C1 only. Later C items remain gated on review of the preceding item.

## Phase B inventory

The repository contains `docs/phase-b1/README.md`, `docs/DEMO_SCRIPT_V2.md`, Phase B1 addenda, and the Phase A audit. I found no Phase B3–B7 delivery reports in this checkout. The attached Phase C prompt describes basic B3–B7 features; the table below records what is actually present in the current code and docs so C can extend those pieces without assuming missing workflows were delivered.

| Phase C item | What the current Phase B code delivers | Missing from the full C specification | Likely files or folders to change |
|---|---|---|---|
| **C1 Incident investigation** | Distinct security alerts, ATT&CK technique labels, alert timeline, live graph, forecast summaries, audit log, and single-host simulated containment. Phase B1 adds the workspace shell and mobile SOC routes. | Incident correlation and lifecycle; typed incident timeline; notes and status controls; incident filters, detail, exports, notifications and deep links; incident contracts; analyst/viewer authorization. | `lead-core/backend/addons/` (incident service, routes, role checks and world-state integration), `contracts/schemas/`, `contracts/samples/`, `lead-core/integration/tests/`, `web/src/areas/incidents/`, `web/src/App.jsx`, `web/src/shared/`, `docs/INCIDENTS.md`, `docs/audit/screenshots/phase-c/`. |
| **C2 Replay studio and builder** | Four shipped deterministic replay scenarios and start/pause/resume/restart controls. | Visual scenario authoring, validation and dry run; user scenario library; stepping, breakpoints, seeking, snapshots, run history and comparison. | `graph/graph_replay/`, `lead-core/backend/addons/`, replay contracts and tests, `web/src/areas/replay/`, `web/src/App.jsx`, `docs/`. |
| **C3 Network digital twin** | A live 3D console graph and a separate interactive 3D landing scene, plus graph topology and a phone-friendly SOC view. | Asset/service/weakness inspection, path explanations and alternatives, risk/exposure overlays, camera presets, time travel, segmentation preview and equivalent accessible list. | `graph/graph_net/`, `lead-core/backend/addons/`, `web/src/areas/console/`, new `web/src/areas/twin/` and host views, topology contracts and tests. |
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

## C1 implementation boundary

C1 will add the incident domain and its routes, contracts, tests, incident list/detail UI, note/status audit integration, and cross-links needed by those pages. It will extend the existing alerts, graph, forecast, replay, containment and Phase B1 shell rather than duplicate them. It will not implement C2–C7 in this branch. Any requirement that needs an extension to DETECT or GRAPH will be isolated and documented before changing those modules; `lead-core/backend/nids/` remains protected.

The hosted-check cleanup issue is part of the starting baseline and will be kept distinct from incident behavior. C1 completion will be reported against the verified totals above plus its new checks; later items will wait for approval.
