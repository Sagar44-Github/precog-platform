# ToN_IoT heterogeneous telemetry

D0 dataset-gate record. No raw data or converted dataset is included in this repository. Pack approval remains pending where stated.

- **Source:** https://research.unsw.edu.au/projects/toniot-datasets
- **Access:** request/download instructions from UNSW project page
- **Licence / redistribution:** UNSW grants free academic research use; commercial use requires author approval. Redistribution rights were not established.
- **Citation:** Use UNSW project page publication citations for the selected subset.
- **Capability provenance:**
  - Detection labels: **native**
  - Host compromise: **derived**
  - Lateral-movement routes: **derived**
  - Topology: **derived**
- **What the labels mean / limitations:** Network and telemetry labels are source-specific. Do not infer movement routes or compromise solely from attack labels.
- **Conversion and validation gate:** no source file was downloaded in D0, so file names, byte sizes, SHA-256 checksums, exact schema, sampling window, label audit, and resulting pack size remain **unverified**. D5 must record these from the official source, use a tiny hand-made fixture in tests, and refuse to ship a converted pack until redistribution rights and attribution are satisfied.
- **D0 disposition:** builder only; academic-use terms and redistribution scope must be checked.

## D5 offline builder

- Input: Network-traffic CSV files only. The parser recognizes common timestamp, source/destination IP, protocol, port, and label/type fields. Telemetry CSVs are not ingested by this adapter.
- Capability interpretation: Native source labels; host and routes are derived only from the explicit flow rule. Telemetry and host logs require a future adapter.
- Build and checksums: use `tools/datasets/fetch.py --source ton-iot` to stage user-downloaded files with SHA-256 values, then `tools/datasets/build_real_pack.py --source ton-iot --raw <verified-folder>`. The output defaults to ignored local data and is not activated.
- Evaluation: `evaluation.json` labels the label-playback baseline as tautological; route metrics are not reported until at least five reviewed ordered routes are available. Fixture tests are not full-dataset metrics.
- Gate: UNSW grants academic research use and asks for citations; no general derived-data redistribution grant is assumed. Keep output local.
