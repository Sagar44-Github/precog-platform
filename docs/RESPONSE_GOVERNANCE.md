# Response governance

Response playbooks are demonstration controls over the six-host simulation. They never call a firewall, endpoint, identity provider, or production network API. The old single-host `/api/x/containment/propose`, `confirm`, and `cancel` routes remain available to the console and phone app.

## Playbooks and policy

| Playbook | Scope | Roles |
|---|---|---|
| `contain-host` | One selected normal or compromised demo host | analyst, admin |
| `contain-zone` | Every eligible host in one demo zone | admin |
| `contain-predicted-path` | Hosts between the forecast source and its rank-one target | admin |
| `contain-top-three` | Eligible hosts in the current forecast's Top-3 | admin |
| `release-host` | One currently contained host | admin |

The policy table is owned by the add-on in `lead-core/backend/addons/governance.py`. Set `REQUIRE_TWO_PERSON_ZONE_APPROVAL=1` to require a different administrator to approve a zone action before confirmation; the default is `0` for the single-admin classroom demo. Passwords continue to come from the role-specific environment variables.

## Decision flow

1. `POST /api/x/containment/preview` validates the role, host, zone and forecast, then reports affected hosts, changed feasible edges, estimated forecast probability removed or restored, summed asset criticality, side effects, and the expected replay re-evaluation. Preview never mutates `WorldState` or the graph.
2. `POST /api/x/containment/governance/propose` records the proposal and its preview snapshot, actor, role, reason, run id and 60-second expiry. Repeated requests that overlap a pending host set are rejected.
3. With two-person zone approval enabled, a different admin uses `POST /api/x/containment/governance/approve` with `decision: approve|reject`. Rejection requires a reason.
4. `POST /api/x/containment/governance/confirm` performs the second step. Containment delegates one host at a time to the existing containment service, preserving its re-evaluation behavior. Release calls `LiveGraph.set_host_state(host, "normal")` only after proposal and confirmation.
5. `POST /api/x/containment/governance/cancel` cancels a pending request. A session change makes the proposal stale. Pending records expire after 60 seconds and are recorded as expired when the service next checks the governance feed or history.

Read routes are `GET /api/x/containment/playbooks`, `GET /api/x/containment/governance`, and `GET /api/x/containment/governance/export?format=json|markdown`. The action domain version in `/api/x/feed` advances when governance records change. Writes use the shared JSON, request-size, same-origin, CSRF-header, and server-side role checks.

## Records and honest impact labels

Four contracts define `playbook`, `playbook_preview`, `approval_record`, and `release_record`. A bounded ledger is atomically replaced at `lead-core/backend/data/governance/records.json`; audit entries use the existing DETECT audit log. The UI renders analyst text as text and offers JSON and Markdown exports.

Probability removed or restored is the sum of the affected candidates' current forecast probabilities. It is a model-based estimate on a scripted six-host topology, not a guarantee. Containment also interrupts legitimate use in the simulation. Every screen retains the SIMULATION disclosure.

The `/containment` workbench is responsive. Analysts can run the single-host playbook on a phone; zone, predicted-path, Top-3 and release controls appear only for admins. Viewer users can inspect the history but cannot see mutation controls.
