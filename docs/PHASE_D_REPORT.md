# Phase D — dataset workspaces and final verification

Branch: `phase-d10-final-verification`

Environment: Windows PowerShell, Python 3.11.9, Node 24.22.0, npm 11.19.1.

## Delivered

- **D8:** secured admin upload and conversion flow for pack ZIPs and supported CSV, TSV, and JSON inputs. Uploads are validated and bounded, stored under ignored runtime data, and never execute uploaded content. Details and limits are in [DATASET_UPLOADS.md](DATASET_UPLOADS.md).
- **D9:** hosted build selection validates and retains the four approved packs, excluding the larger reserve pack from Render builds. The local repository keeps the reserve pack. Details are in [HOSTED_DATASETS.md](HOSTED_DATASETS.md).
- **D10:** cross-dataset evaluation output and license/citation register; final UI accessibility fixes; production bundle rebuild; test, browser, Golden Path, and hosted-style checks.

## Verification

| Check | Result |
| --- | --- |
| `python -m pytest --tb=short -q` | **570 passed, 1 skipped** (571 collected) |
| Offline detector suite in `detect/offline_model/.venv` | **50 passed, 1 skipped** |
| `npm test` | **163 passed** |
| `python contracts/check_contracts.py` | **71 contracts OK** |
| Browser audit, sample and live | **144 checks, 0 failures, 0 errors**; 72 checks per mode across 390×844, 820×1180, and 1440×900 |
| Browser screenshots | **144** in `docs/audit/screenshots/phase-d10/`; machine-readable results in `docs/audit/phase-d10/browser-audit-results.json` |
| Golden Path, 5 runs at speed 1 | **5/5 PASS** |
| Seed-zero Precog evaluation | **149 held-out forecasts**; Markov P@1 **0.6510**, rule baseline **0.6376**, uniform **0.5503**, Markov ECE **0.0572**; P@3 **1.0** is trivial for this candidate set; matches shipped results |
| Hosted-style check against local live-mode Flask server | **READY for the demo**, 13/13 checks |
| NIDS tree compared with `origin/main` | No changes |

The browser flow also completed propose-and-confirm containment in simulation. The Golden Path and evaluation use deterministic fixtures; they are not evidence of real-world protection.

## Size and data limits

- Hosted pack payload: **2,708,112 bytes (2.59 MiB)** across demo-6 and three synthetic enterprise packs. The synthetic datacenter reserve (**1,365,457 bytes**) is local-only.
- Backend web bundle: **55 files / 2,446,820 bytes**; JavaScript totals **2,080,568 bytes**. The app entry chunk is **218,287 bytes**; the 3D scene (**818,163 bytes**) and Three.js (**586,410 bytes**) remain separate lazy chunks.
- A 100,000-event pipeline memory probe peaked at **223.2 MiB working set** on this local Windows environment. This is not a Render memory measurement.
- Cross-dataset results cover the five installed demo/synthetic packs. Real-source datasets were not installed or evaluated; their registry entries remain explicitly unavailable or gated. See [CROSS_DATASET_RESULTS.md](CROSS_DATASET_RESULTS.md) and [LICENSES_AND_CITATIONS.md](LICENSES_AND_CITATIONS.md).

## Not verified

The local hosted-style check does not verify a public Render deployment. A physical-phone PWA install was not performed. No raw real-world dataset was downloaded. These are not claimed as completed checks.
