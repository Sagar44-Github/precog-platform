# Precog SOC Demo Script V2 — B2 operations workspaces and replay

**Length:** about 6–8 minutes

**Mode:** local replay simulation
**Screen:** desktop browser at 1024 px or wider; phone view can be opened separately.

## Before the demo

1. Start the local backend using the repository demo script or `python lead-core/backend/run_app.py`.
2. Open `/app/login` and sign in with the local demo account.
3. Confirm the persistent SIMULATION label is visible. No real traffic or network containment is involved.

## Walkthrough

1. **Orient the audience.** Point out the workspace rail, operator identity, theme control, and the SIMULATION label. The console is the desktop view; Mobile SOC opens the phone layout.
2. **Use the command palette.** Press Ctrl+K (Cmd+K on macOS), search for “Mobile SOC”, and press Enter. Show the Home and Alerts tabs, then return to the desktop console.
3. **Review alerts.** Open Alerts from the rail. Filter by severity, host, technique, or explanation; sort the rows and open an event record. Export the current filtered result to CSV or JSON.
4. **Inspect the demo assets.** Open Hosts & Assets and select Workstation A. Point out its zone, simulated risk, reachable hosts, and state history. Make clear that `DEMO-` weaknesses are synthetic scoring inputs, not real CVEs or findings.
5. **Check operations context.** Open Audit Log to show scrubbed detection and response records, then System Health to show loaded modules and data mode. In Settings, change the table density and alert default; reload to show the local preference persisted.
6. **Show theme persistence.** Switch to the light theme and return to dark if time permits. The 3D map and charts use the same semantic tokens as the shell.
7. **Start the deterministic replay.** In Replay Controls, select `golden-path` and choose Start. Explain that the scripted events run through the project’s detection, graph, forecast, and response pipeline.
8. **Explain the forecast.** At the decision point, show the ranked targets and confidence values. Say “Precog predicts”; show the honest session-counter label when discussing results.
9. **Contain with confirmation.** Choose Contain, review the confirmation dialog, and confirm. The action changes only simulated in-memory host state and records a log entry.
10. **Close the loop.** Show the blocked next move, resolved forecast outcome, timeline, and updated graph state. State plainly whether the forecast was a hit or miss.

## If presenting on a narrow screen

At widths below 1024 px, `/app/console` directs the operator to `/app/mobile`; open the PWA route for phone-sized screens. The operational pages remain available with an icon rail and stacked records. The 3D console is designed for wider displays.

## Claims to preserve

- All events are scripted simulation data. The NIDS packet sniffer is not started.
- Containment has no real network effect and requires proposal followed by confirmation.
- A session hit rate is not the model’s overall accuracy. Precision@3 is trivial when at most three candidates are reachable.
- The forecast is a prediction; a miss is reported as a miss.
