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

## Why the source datasets are not present

This project does not download external datasets during install, startup, or
deployment. The pack registry is metadata; `tools/datasets/fetch.py` only checks
and stages files that an operator has already downloaded. In this checkout, the
installed workspaces are `demo-6` and four project-generated synthetic packs
(`synth-enterprise-30`, `synth-enterprise-120`, `synth-enterprise-300`, and
`synth-datacenter-300`). These are runnable and bundled; they are not raw
research datasets. The eight real-source registry entries have no source files
or hashes here. Topology Zoo also has no source graph installed.

That is intentional, not a missing Python package or a storage/configuration
failure. Some sources require an access request or web form, some are multi-GB,
and source terms differ on whether converted data may be redistributed. The
project will not guess a download URL, select a subset, accept terms, or place
unreviewed research data in a hosted deployment. No background download was
started, so there is no partial-download directory to recover.

### Download and build a local source pack

1. Choose one source in the matrix above and use its official source link. Follow
   its access form or download instructions; select only the flow/event files
   accepted by that builder (not PCAPs, executables, or unrelated host logs).
   LANL Cyber1 requires its own access procedure. CIC-IDS2017's five daily files
   are large (the source page lists roughly 8–13 GB per day); CTU-13's full
   archive is listed as 1.9 GB. A partial, selected CSV subset is usually faster
   to process. Do not redistribute the resulting pack unless the source's terms
   permit it.
2. Put the selected files in one flat local folder. In PowerShell, set the
   source ID and calculate a checksum for each selected file. Prefer a checksum
   published by the data owner; a locally calculated checksum records what you
   used but does not independently prove where it came from.
3. Run the verifier, builder, and pack checks below from the repository root.
   Replace the source ID and raw files for the dataset you chose.

~~~powershell
$SourceId = 'lanl-cyber1'
$RawDir = 'D:\Datasets\precog\lanl-cyber1'
$HashArgs = foreach ($File in Get-ChildItem -LiteralPath $RawDir -File) {
  $Hash = (Get-FileHash -LiteralPath $File.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
  '--sha256'
  "$($File.Name)=$Hash"
}
python tools/datasets/fetch.py --source $SourceId --raw-dir $RawDir @HashArgs
$Staged = ".\lead-core\backend\data\raw\$SourceId"
$Pack = ".\lead-core\backend\data\real-packs\$SourceId"
python tools/datasets/build_real_pack.py --source $SourceId --raw $Staged
python tools/datasets/validate_pack.py $Pack
python tools/datasets/inspect_pack.py $Pack
~~~

`fetch.py` needs at least one `--sha256 FILE=HASH` for every selected file. It
stages verified inputs under ignored `lead-core/backend/data/raw/`; the builder
creates a local-only pack under ignored `lead-core/backend/data/real-packs/`.
These tools do not modify Git-tracked data, activate a workspace, or claim that
source labels prove a successful compromise.

### Make a locally built pack selectable

For local development, copy the validated pack to the configured local pack
root. For a hosted instance, create a ZIP whose root contains `manifest.json`,
then use **Datasets → Upload dataset** as an administrator, inspect it, and
confirm the build. The hosted upload limit is 50 MiB; the pack payload limit is
25 MiB. Render's filesystem is ephemeral, so an uploaded pack can disappear on
restart or redeploy. For durable hosted availability, a pack must be included
in the deployment only after its redistribution terms are cleared.

~~~powershell
$Pack = ".\lead-core\backend\data\real-packs\$SourceId"
$LocalPackRoot = '.\lead-core\backend\data\user_packs'
New-Item -ItemType Directory -Force -Path $LocalPackRoot | Out-Null
Copy-Item -LiteralPath $Pack -Destination (Join-Path $LocalPackRoot $SourceId) -Recurse
~~~

The workspace list discovers valid packs in this local root. Activate one from
the workspace selector or dataset page; the Twin and route explorer then read
that active pack's topology. Dataset-specific capability labels remain
authoritative: for example, UNSW-NB15 does not provide ordered compromise
routes, so Precog route forecasts are unsupported for that source.

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
