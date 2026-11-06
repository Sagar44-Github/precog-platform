# Workspace runtime (D2)

## Scope

`DatasetContext` is the active, in-process description of a validated pack: pack identity/path and manifest, hosts, topology, scenario library, training routes, Precog model and evaluation, detector mode, decision policy, and display hints. `WorkspaceManager` owns that context and activates only packs already present under the configured `packs/` root. Pack IDs are identifiers; APIs never accept a filesystem path or URL.

D2 adapts the existing add-on hooks to the active context without changing `/api/x/state` or editing the NIDS copy. It reconstructs the graph topology, host-address/name maps, replay scenario library, Precog model, and workspace-local state paths. `demo-6` remains the boot default and continues to use the existing NIDS live detector. Other packs use only their declared detector mode; the D1 demo-compatible runtime still uses the scripted replay path, so large recorded-data streaming and detector adapters are later phases.

## API

- `GET /api/x/workspaces`: registry candidates and locally installed packs, each with status, counts, capability provenance, and redistribution disposition.
- `GET /api/x/workspaces/active`: active workspace summary.
- `GET /api/x/workspaces/{id}/card`: plain-text dataset card content plus source, licence/redistribution, capabilities, and limitations.
- `POST /api/x/workspaces/install` (admin): validates a local pack by ID beneath `packs/`. It does not accept uploads, paths, shell commands, or remote URLs.
- `POST /api/x/workspaces/{id}/activate` (analyst/admin): requires `{ "confirm": true }`; stops an in-flight replay, saves the outgoing workspace's bounded session/snapshot/incident state, resets transient world/graph/replay state, and rebinds services to the requested pack. The response includes the monotonically increasing process-local `workspace_version`.
- `DELETE /api/x/workspaces/{id}` (admin): deletes only a validated inactive pack and its workspace-owned saved state. `demo-6` cannot be deleted.
- `GET /api/x/feed?since=N`: includes the workspace version with incident/run/action/note versions; old `world_state` remains unchanged.

All writes retain the JSON content-type and same-origin `X-Precog-Request: 1` protection, plus server-side role checks. Viewer requests cannot install, activate, or delete. Activation requires an explicit confirmation to communicate that active replay state is reset. Pack validation/installation, successful switches, and deletion write scrubbed `workspace` records to the active workspace's audit log; a switch is recorded in both the source and destination workspace.

## Persistence and isolation

Workspace-owned records are placed beneath `lead-core/backend/data/workspaces/<pack-id>/` using atomic replacement for `state.json`. The bounded state file holds that workspace's prior session summaries, time-travel snapshots and incident checkpoint (including notes). Existing run/scenario, governance, analytics, and audit services are rebound to workspace-specific directories. The historical `demo-6` data directory stays at its existing path to avoid losing local demo artifacts. Temporary world state is reset on activation; saved workspace history remains isolated and is restored when switching back in the same running process.

The app still starts with the demo context. A hosted ephemeral disk starts with no user packs or saved workspace state unless those packs are in the deployed `packs/` directory. In-memory WorldState remains authoritative for the currently active workspace.

## Current limitation

D2 establishes safe context switching and hook rebinding for validated scenario packs such as `demo-6`. It does not yet stream `pack.sqlite` events through the large-pack pipeline, implement detector modes for real datasets, or guarantee multi-process coordination. Keep one backend worker. D3/D4 generalize evaluation and add bounded event processing before activating large real packs in a hosted demo.
