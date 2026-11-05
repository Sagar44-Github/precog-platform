# Incident Investigation Workbench

## Replay and correlation behavior

Incidents are assembled from the active scripted replay, using the existing DETECT event and GRAPH topology hooks. Every new alert is considered once; repeated delivery of the same event ID is ignored. Only incidents in `open` or `reopened` status can receive an alert. Correlation requires the same replay session and follows these ordered rules:

1. An alert for a host already in the incident joins when it falls within `INCIDENT_CORRELATION_WINDOW_SECONDS` of the last alert.
2. An alert for a host one feasible topology hop from an affected host joins inside the same window.
3. A later ATT&CK tactic in the configured tactic order joins as a continuing technique chain, even outside the time window.
4. Otherwise, the alert starts a new incident.

The selected rule is stored beside every alert link in `correlation_reasons`. If more than one open incident qualifies, the latest eligible incident receives the alert. Severity is the maximum severity among its alerts. The title is updated from the first compromising technique and host; a reconnaissance-only case is titled from its reconnaissance technique and host. Quiet Scan uses an optional scenario severity override so its events remain explicitly LOW. The override is a backward-compatible optional `severity` field in GRAPH's scenario schema; omitted values retain DETECT's existing severity output.

Incident IDs begin at `INC-0001` and timeline IDs at `INC-0001-E0001` on each replay. Incident IDs, alert IDs, forecast IDs, action IDs, timestamps, and session IDs follow their owning pipeline's rules; timestamps and the replay session sequence may differ between repeated runs. The incident structure and ordering are deterministic for the same scenario. The service caps retained incidents at 50, alerts per incident at 200, notes per incident at 50, timeline events per incident at 2000, and seen alert IDs at 10,000.

## Status and containment wording

Statuses are `open`, `contained`, `closed`, and `reopened`. Analysts and admins close a case only with an explicit confirmation and a reason; a closed case may be reopened with a reason. Correlation only considers open or manually reopened cases; later alerts after a case is contained or closed start a separate incident.

The Golden Path's accepted response contains Web Server B and blocks the forecasted move while Workstation A remains compromised in the simulation. To preserve that approved demo outcome, this implementation marks the incident `contained` after a confirmed simulated containment and a blocked forecast outcome. The record keeps `compromised_hosts` visible and `containment_basis` explains that the response stopped the scripted next move; this label does not claim that every compromised asset was remediated. The user selected preservation of this Golden Path behavior when the two status definitions conflicted.

## Data, audit and security

Live incidents are in-memory, scoped to the current replay, and rebuilt from the current world state. Notes and status transitions are appended to the add-on-owned bounded ledger at `lead-core/backend/data/audit/incidents.json`, using a temporary file and `os.replace`; no NIDS file or DETECT audit writer is changed. The backend data directory is git-ignored and an empty hosted data directory is valid.

Optional `analyst` and `viewer` accounts are created from `ANALYST_PASSWORD` and `VIEWER_PASSWORD`. The existing `ADMIN_PASSWORD` remains the admin credential. Passwords are never stored in the repository. Viewers can read incidents but cannot annotate, change status, run replay controls, or propose/confirm/cancel containment. Analysts can investigate, annotate, close/reopen cases, run replays, and use the existing single-host propose-then-confirm flow. Admin inherits analyst actions.

Cookie-authenticated writes require JSON, the `X-Precog-Request: 1` custom header, and a same-origin `Origin` when supplied; cross-site Fetch Metadata is rejected. The custom header requires a CORS preflight, and this application does not enable cross-origin CORS. Write bodies are capped at 32 KB. Incident IDs are validated identifiers, not filesystem paths. Notes are plain text with a 2000-character limit and control/markup rejection; React renders them as text. Incident list/detail/timeline reads and exports use per-route in-memory rate limits.

## Estimate and simulation disclosure

Incident grouping is deterministic correlation over scripted replay events and a six-host demo topology. Forecasts remain model estimates; misses are labeled as misses. Containment changes simulated in-memory state only and has no connection to a real network. The incident workbench does not display the invented NIDS threat-actor, ASN, or location fields.
