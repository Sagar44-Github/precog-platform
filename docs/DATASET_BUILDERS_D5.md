# Phase D5 — real-dataset builder guide

Status: offline builders and fixture checks are implemented. No raw source file or
real-derived pack is checked into this repository. A catalog entry marked
**needs-manual-download** is not an installed or runnable workspace.

## Source and evidence matrix

| Dataset | Source input | Detection labels | Compromise / route truth | Redistribution gate |
| --- | --- | --- | --- | --- |
| LANL Cyber1 | auth.txt[.gz] plus redteam.txt[.gz]; CSV-like rows without a header | Native red-team labels | Host compromise and ordered routes are derived from red-team action endpoints grouped by pseudonymized user; topology is derived from observed auth edges | Manual access process; keep local until exact release terms are reviewed |
| CSE-CIC-IDS2018 | selected CICFlowMeter CSV files | Native flow labels | Derived only by the documented external-to-internal access and later internal lateral-label rule | Attribution required; the official UNB page permits redistribution with citation and AWS link |
| CIC-IDS2017 | selected MachineLearningCSV CSV files | Native flow labels | Derived only from labelled flows; successful host compromise is not directly observed | UNB FAQ permits redistribution with dataset and paper citation |
| CTU-13 | bidirectional Argus flow data exported to CSV with timestamps, endpoints, ports, protocol and label | Native botnet / normal / background labels | Infected-host interpretation is scenario-dependent; the builder only emits routes when the selected labels support its explicit derivation rule | CC BY attribution; use the source's current recommended bidirectional flow files |
| CIC-IoT-2023 | selected flow CSV files | Native attack labels | Device endpoints and attack windows are observations; route/compromise are derived estimates | No redistribution grant was established on the reviewed source page; local builder only |
| ToN_IoT | network-traffic CSV only | Native source labels | Derived from labeled network flows; telemetry is not ingested by this network builder | Academic-use terms; commercial and redistribution rights require confirmation |
| UNSW-NB15 | labeled flow CSV (srcip, dstip, protocol and attack category) | Native labels | No confirmed ordered lateral route ground truth; routes are none and Precog ranking is not evaluated | Academic use; converted-data redistribution requires clarification |
| CIDDS-001 | CSV flow records with time, source/destination, protocol, class and attack type | Native attack-type labels | Derived only where an explicit attacker-to-victim and later internal-flow sequence exists | Citation required; broad redistribution permission remains unconfirmed |

The rows above are dataset-level expectations. Each built manifest reports the
capability actually present in its selected files and event window. No flow label
is described as proof of successful compromise. DoS and DDoS labels are
impact-only; reconnaissance labels do not create compromise state.

Official source records were checked against the dataset owners' pages:
[LANL Cyber1](https://csr.lanl.gov/data/cyber1/),
[CSE-CIC-IDS2018](https://www.unb.ca/cic/datasets/ids-2018.html) and its
[AWS registry](https://registry.opendata.aws/cse-cic-ids2018/),
[CIC-IDS2017](https://www.unb.ca/cic/datasets/ids-2017.html) and
[CIC's redistribution FAQ](https://www.unb.ca/cic/datasets/),
[CTU-13](https://www.stratosphereips.org/datasets-ctu13/) and its
[dataset overview](https://www.stratosphereips.org/datasets-overview),
[CIC IoT 2023](https://www.unb.ca/cic/datasets/iotdataset-2023.html),
[ToN_IoT](https://research.unsw.edu.au/projects/toniot-datasets),
[UNSW-NB15](https://research.unsw.edu.au/projects/unsw-nb15-dataset), and
[CIDDS-001](https://www.hs-coburg.de/forschen/transferstellen-und-institute/kompetenzzentrum-fuer-it-sicherheit/cidds-coburg-intrusion-detection-data-sets/).
The source pages provide bibliographic citations; keep each card's dataset and
paper citation with any permitted derived material.

## Build and verify local data

The project never downloads source data implicitly. Follow the source page's
access procedure, put selected files in a local folder, compute trusted SHA-256
values, then stage only those files under the ignored backend data directory:

~~~powershell
Get-FileHash .\raw\auth.txt.gz -Algorithm SHA256
python tools/datasets/fetch.py --source lanl-cyber1 --raw-dir .\raw --sha256 auth.txt.gz=<trusted-sha256> --sha256 redteam.txt.gz=<trusted-sha256>
python tools/datasets/build_real_pack.py --source lanl-cyber1 --raw .\lead-core\backend\data\raw\lanl-cyber1
python tools/datasets/validate_pack.py .\lead-core\backend\data\real-packs\lanl-cyber1
python tools/datasets/inspect_pack.py .\lead-core\backend\data\real-packs\lanl-cyber1
~~~

Use the equivalent source ID for each of the eight builders. fetch.py requires
the expected digest for every supplied file, verifies it before staging, and
writes atomically. The official pages do not publish hashes for every individual
file. A locally computed hash records the exact input used but is not an
independent authenticity check; use a checksum published by the owner when one
exists. build_real_pack.py accepts one or more files/directories, caps input
scanning at 2,000,000 rows, stored events at 100,000, hosts at 500, and pack
payload at 25 MiB. The default event cap is 50,000 and default host cap is 400.
Adjust --max-events and --max-hosts to make a smaller deterministic window.

Raw IP addresses and LANL account/computer identifiers are replaced by stable,
seeded opaque host IDs before writing the pack. The source files remain in
lead-core/backend/data/raw/, which is ignored by Git. The builder defaults to
lead-core/backend/data/real-packs/; it never activates the pack. Unresolved
license entries are blocked from output under tracked packs/. The two CIC flow
datasets and CTU-13 require explicit --allow-attributed-pack before publishing
under packs/.

## Evaluation limits

Each local build contains a chronological 80/20 **label-playback baseline** in
evaluation.json: its predictions are the source labels themselves, so the
perfect score is tautological and is not an ML detector result. Route-based
Precog scores are marked not evaluated until at least five reviewed ordered
routes exist and a separate held-out evaluation is run. Fixture tests exercise
parsing, pseudonymization, pack integrity, capability disclosure, and
deterministic output; they do not substitute for full-dataset metrics.

The current workspace registry retains the eight records as
needs-manual-download or builder-only-pending-terms; no real-data metrics,
file hashes, event counts or converted pack sizes are invented. Topology Zoo is
builder-ready but no source graph is installed: its local builder creates a
project-generated replay over a selected graph only after an operator records
that graph's exact source, citation, license, redistribution permission and
SHA-256. This record is an explicit input gate, not an independent legal review.
