# Phase B6 — Replay Studio

Branch: `codex/phase-b6-replay-studio`

Replay Studio adds controlled scripted runs, one-event stepping, a bounded read-only time-travel history, a visual scenario builder, and side-by-side comparison of completed sessions. Custom scenarios are validated and stored locally by the backend. All events remain simulated.

## Verification

| Check | Result |
| --- | --- |
| Python suite | 428 passed, 1 skipped |
| Web suite | 113 passed |
| Contract checker | 28 contracts OK |
| Browser audit | 78 checks in sample mode and 78 in live mode; 0 failures and 0 console errors |
| Golden Path | 2 of 2 runs passed |
| Chromium screenshots | 158 captures at 390, 820, and 1440 pixel viewports |
| Production build | Passed; the existing Three.js entry chunk remains above Vite's 500 kB advisory threshold |

Browser results: [browser-audit-results.json](browser-audit-results.json).

## Screenshots

- [Replay Studio — desktop](screenshots/sample-replay-1440x900.png)
- [Replay Studio — phone](screenshots/sample-replay-390x844.png)
- [Scenario builder — desktop](screenshots/sample-scenarios-1440x900.png)
- [Scenario builder — phone](screenshots/sample-scenarios-390x844.png)

## Demo

Open **Replay Studio**, choose a scripted scenario, set its speed, and start it. Pause and step through an event, inspect earlier world snapshots without changing the run, then compare two completed sessions. Open **Scenario builder** to compose and save a local scripted sequence; the server validates it before it can be replayed.

Session metrics describe the selected runs only. They do not claim overall model accuracy. Time travel is read-only, and containment still requires explicit confirmation.
