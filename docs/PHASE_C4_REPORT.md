# Phase C4 Report — Precog Decision and What-if Lab

## Environment

- Windows 11, PowerShell
- Python 3.11.9 and the repository `.venv`
- Node/npm and Playwright Chromium with SwiftShader
- Branch: `phase-c4-precog-lab`, based on the verified C3 commit

## Delivered

- Forecast history at `/forecasts` and deep-linked formula explanations at `/forecasts/:id`.
- Counterfactual containment sandbox at `/lab`; hypothetical requests do not mutate the active replay, graph, forecast, metrics, or Precog hook state.
- Calibration, baselines, profile breakdown, model card, offline detector context, and parameterized evaluation at `/analytics`.
- Five new API endpoints and six contract/sample pairs. Full endpoint and formula notes are in [PRECOG_LAB.md](PRECOG_LAB.md).
- Bounded evaluation parameter cache and atomic 50-entry experiment history under `lead-core/backend/data/analytics/`.
- C4 browser routes and sample/live interaction flows in the browser audit, with screenshots at all three required viewport sizes.

## Verification

| Command or procedure | Result |
|---|---|
| `.venv/Scripts/python.exe -m pytest -o "addopts=" -p no:cacheprovider --tb=short` | 415 collected; 414 passed, 1 skipped; 2 existing Scapy deprecation warnings. |
| `python -m pytest tests -o "addopts=" -p no:cacheprovider --tb=short` in `detect/offline_model/` using its `.venv` | 50 passed, 1 skipped. |
| `npm test` in `web/` | 126 passed, 0 failed. |
| `python contracts/check_contracts.py` | 42 contracts OK. |
| `npm run audit:browser` with software WebGL | 144 checks across sample/live and 390×844, 820×1180, 1440×900; 0 failures, 0 browser errors and 0 axe violations; 144 screenshots saved. |
| `python lead-core/integration/golden_path.py --runs 2 --speed 1` | 2 of 2 PASS. |
| `python docs/audit/run_hosted_check.py` | 13 readiness checks; `READY for the demo`. |
| `npm run build` and hosted bundle copy | Build succeeded; 30 files copied. Main app chunk 194.17 kB (62.22 kB gzip); 3D renderer 817.38 kB (236.68 kB gzip). Vite still reports its existing large-chunk warning. |
| `git diff --check` and NIDS source path check | Clean; `lead-core/backend/nids/` unchanged. |

Seed 0 reproduces the shipped held-out results: 149 forecasts, P@1 0.6510 (standard error 0.0390), rule baseline 0.6376, uniform baseline 0.5503, and ECE 0.0572. P@3 is labelled trivial because the scripted topology has at most three feasible candidates.

## Limitations

All model claims use a scripted generator and six demo hosts. They do not establish real-world attack detection or protection. Sample fixtures that predate the forecast recorder show a reconstructed-context label. The local hosted-style check passed; public Render deployment and installation on a physical phone were not performed. C5–C7 remain incomplete.
