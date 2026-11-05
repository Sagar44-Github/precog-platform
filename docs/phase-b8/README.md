# Phase B8 — Onboarding and accessibility

Branch: `codex/phase-b8-polish-onboarding`

B8 adds operator-facing Help and About pages, a six-step route tour, a Golden Path quickstart, shortcuts, and a glossary. The About page sets expectations around the scripted simulation, synthetic host weaknesses, evaluation limits, architecture, and upstream credits. The shared shell adds a skip link; the tour manages keyboard focus and can start replay only when the account is allowed to. It never confirms containment.

## Verification

| Check | Result |
| --- | --- |
| Python suite | 428 passed, 1 skipped, 2 existing Scapy/TripleDES deprecation warnings |
| Web suite | 126 passed |
| Contracts | 28 contracts OK; B8 adds no contract |
| Chromium route audit | 87 checks in sample and 87 in live mode; 0 failures and 0 browser errors |
| Guided tour workflow | Started Golden Path, advanced through all six steps, and finished on Help |
| Live containment workflow | Proposed and confirmed in the simulation; the host state changed in memory |
| Golden Path rehearsal | 5 of 5 consecutive runs passed at 1× speed |
| Production build and bundle | Passed; 48 files copied into `lead-core/backend/web_dist` |
| Hosted readiness | All local live-mode checks passed; checker printed `READY for the demo` |

The rehearsal times and each assertion are in [rehearsals.csv](rehearsals.csv). Hosted readiness output is in [hosted-readiness.txt](hosted-readiness.txt). The full browser results are in [browser-audit-results.json](browser-audit-results.json); 175 viewport and role screenshots are in [browser-audit/](browser-audit/).

## Screenshots

- [Help, desktop](browser-audit/sample-help-1440x900.png)
- [Help, phone width](browser-audit/sample-help-390x844.png)
- [About, desktop](browser-audit/sample-about-1440x900.png)
- [About, full page](about-page.png)
- [Topology, desktop](browser-audit/sample-topology-1440x900.png)
- [Mobile SOC, phone width](browser-audit/sample-mobile-390x844.png)

## Notes

- Chromium ran with SwiftShader; the audit checks route rendering, layout, canvas output, interactions, and browser errors, but does not establish physical-device frame rate.
- Vite still reports the Three.js `Scene3D` chunk above its 500 kB advisory threshold (about 1.42 MB raw / 384 kB gzip).
- `npm ci` reported 8 dependency advisories (3 moderate, 5 high); B8 did not apply potentially breaking dependency upgrades.
- The local hosted-readiness check used a temporary SQLite database and a throwaway local password. No Render deployment was performed.
