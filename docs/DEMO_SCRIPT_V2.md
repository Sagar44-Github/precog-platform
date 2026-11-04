# Precog SOC Demo Script V2 — B1 shell and current replay

**Length:** about 4–6 minutes

**Mode:** local replay simulation
**Screen:** desktop browser at 1024 px or wider; phone view can be opened separately.

## Before the demo

1. Start the local backend using the repository demo script or `python lead-core/backend/run_app.py`.
2. Open `/app/login` and sign in with the local demo account.
3. Confirm the persistent SIMULATION label is visible. No real traffic or network containment is involved.

## Walkthrough

1. **Orient the audience.** Point out the workspace rail, operator identity, theme control, and the SIMULATION label. The console is the desktop view; Mobile SOC opens the phone layout.
2. **Use the command palette.** Press Ctrl+K (Cmd+K on macOS), search for “Mobile SOC”, and press Enter. Show the Home and Alerts tabs, then return to the desktop console.
3. **Show theme persistence.** Switch to the light theme, reload once if useful, then return to dark. The 3D map and charts use the same semantic tokens as the shell.
4. **Start the deterministic replay.** In Replay Controls, select `golden-path` and choose Start. Explain that the scripted events run through the project’s detection, graph, forecast, and response pipeline.
5. **Explain the forecast.** At the decision point, show the ranked targets and confidence values. Say “Precog predicts”; show the honest session-counter label when discussing results.
6. **Contain with confirmation.** Choose Contain, review the confirmation dialog, and confirm. The action changes only simulated in-memory host state and records a log entry.
7. **Close the loop.** Show the blocked next move, resolved forecast outcome, timeline, and updated graph state. State plainly whether the forecast was a hit or miss.

## If presenting on a narrow screen

At widths below 1024 px, `/app/console` directs the operator to `/app/mobile`; open the PWA route for phone-sized screens. The 3D console is designed for wider displays.

## Claims to preserve

- All events are scripted simulation data. The NIDS packet sniffer is not started.
- Containment has no real network effect and requires proposal followed by confirmation.
- A session hit rate is not the model’s overall accuracy. Precision@3 is trivial when at most three candidates are reachable.
- The forecast is a prediction; a miss is reported as a miss.
