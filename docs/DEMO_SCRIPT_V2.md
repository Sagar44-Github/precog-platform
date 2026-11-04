# Precog SOC Demo Script V2 — B3 cases, reports, and replay

**Length:** about 10–12 minutes

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
11. **Open the incident case.** Select Incidents. Show how the replay session joins alerts, predicted targets, and simulated containment records. Open the case and review involved hosts, technique labels, and the ordered timeline.
12. **Record analyst review.** Add a short note, then change the case status. Point to the audit log entry. These case annotations live in memory during the demo and are not durable records.
13. **Print a session report.** Open Reports and select the completed replay. Explain that its hit and precision counters describe this session, not overall model accuracy, and that precision@3 can be trivial with at most three reachable targets. Export JSON or the timeline CSV, then use Print Report.
14. **Show the phone case view.** Open the PWA, select Cases, and open the same incident. Add a short note or update status from the phone to show both clients act on the same in-memory demo state.
15. **Open the forecast ledger.** Review the prediction history, then open a record. Point to the captured candidate set, transition counts, smoothing alpha, hint-table source, and the model/rule/uniform ranks. Show a miss plainly if the replay produced one.
16. **Run a what-if preview.** Choose a host that is currently compromised. Explain that the preview recomputes predicted rankings for this simulation and does not alter the graph, forecast history, or replay.
17. **Compare evaluation and session counters.** Open Analytics. Contrast the held-out Markov result with both baselines, inspect the calibration curve, then show the separate session tally. State that precision@3 is 1.0 for all current methods because the topology has at most three candidates.
18. **Review DETECT's offline report.** Point out that the CICIDS2017 metrics come from an offline public sample and are not comparable to the live Isolation Forest replay detector.

## If presenting on a narrow screen

At widths below 1024 px, `/app/console` directs the operator to `/app/mobile`; open the PWA route for phone-sized screens. The operational pages remain available with an icon rail and stacked records. The 3D console is designed for wider displays.

## Claims to preserve

- All events are scripted simulation data. The NIDS packet sniffer is not started.
- Containment has no real network effect and requires proposal followed by confirmation.
- A session hit rate is not the model’s overall accuracy. Precision@3 is trivial when at most three candidates are reachable.
- Incident status and analyst notes are volatile annotations; session evidence is kept only within the bounded in-memory archive of 20 sessions.
- The forecast is a prediction; a miss is reported as a miss.
- The what-if page is read-only. Held-out model-level metrics exclude replay rehearsals and session counters.
