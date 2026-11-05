# Network Digital Twin

The Network Twin is a read-only asset and topology explorer for the six-host simulated network. Open `/twin` for the interactive 3D map, `/hosts` for the asset directory, `/hosts/:id` for a host record, or `/mobile/hosts` on a phone.

The 3D map groups assets into user, DMZ, and internal zone slabs. Nodes show their simulation state; attached markers indicate demo services. Select a node to inspect services, simulated weaknesses, estimated risk, criticality, exposure, related alerts, forecasts, actions, incidents, and recent host history. The Lite view presents the same hosts and feasible edges in a keyboard-accessible 2D map and host list.

Overlay choices show host state, estimated risk, forecast probability, or exposure. Size and labels communicate the numeric overlays as well as colour. Camera presets include isometric, top, and side; the host selector flies the camera to the selected asset. The path tracer lists feasible alternatives and their likelihood estimates. The segmentation preview removes a feasible edge in a copied graph and reports which hosts become unreachable from the selected start; it does not change the graph or replay state.

The time slider reads snapshots from the C2 run archive. It switches the displayed host states and forecasts to the selected recorded point. The current in-memory simulation remains authoritative and is not changed by browsing snapshots.

## Read-only endpoints

All endpoints require an authenticated session:

| Route | Result |
|---|---|
| `GET /api/x/topology` | Host assets, zones, feasible and observed edges, simulated weakness metadata, risk basis and current compromised path. |
| `GET /api/x/topology/paths?from=host-a&to=db-server&limit=10` | Feasible routes with edge likelihoods and the product estimate for each route. |
| `GET /api/x/topology/segmentation-preview?from=host-a&remove_from=host-a&remove_to=server-b` | Reachability before and after removing a feasible edge, without mutation. |
| `GET /api/x/hosts/{host_id}` | Host detail and related current alerts, forecasts, actions and incidents. |
| `GET /api/x/hosts/{host_id}/history?limit=200` | Bounded activity derived from the live session and saved C2 snapshots. |
| `GET /api/x/runs/{run_id}/snapshots` and `GET /api/x/snapshots?run={run_id}&version={version}` | C2 snapshot index and one recorded state. |

Contracts and samples are checked by `contracts/check_contracts.py`: `topology`, `topology_paths`, `host_detail`, `host_history`, and `segmentation_preview`.

## Limits and honesty

All hosts, weaknesses and edges are demo data. Risk and likelihood values are model-based estimates from the scripted topology; no real vulnerability scan is performed and they do not indicate real-world protection. The segmentation view is a projection, not a response action. The 3D map is a visualization; the Lite list remains available for keyboard use, accessibility, and environments without WebGL.
