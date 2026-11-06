# CIC-IoT-2023 device attack data

D0 dataset-gate record. No raw data or converted dataset is included in this repository. Pack approval remains pending where stated.

- **Source:** https://www.unb.ca/cic/datasets/iotdataset-2023.html
- **Access:** official UNB page links to CICResearch download; source archive size/access needs recheck
- **Licence / redistribution:** Official page presents citation but the reviewed page did not establish a redistribution license. No data redistribution until terms confirmed.
- **Citation:** Use the dataset citation listed on the official UNB/CIC page.
- **Capability provenance:**
  - Detection labels: **native**
  - Host compromise: **derived**
  - Lateral-movement routes: **derived**
  - Topology: **derived**
- **What the labels mean / limitations:** Attack/device classes support detection labels; they do not establish enterprise compromise paths or routes.
- **Conversion and validation gate:** no source file was downloaded in D0, so file names, byte sizes, SHA-256 checksums, exact schema, sampling window, label audit, and resulting pack size remain **unverified**. D5 must record these from the official source, use a tiny hand-made fixture in tests, and refuse to ship a converted pack until redistribution rights and attribution are satisfied.
- **D0 disposition:** builder only pending written licence/redistribution confirmation.

## D5 offline builder

- Input: Selected CSV flow files with timestamp, IPV4_SRC_ADDR, IPV4_DST_ADDR, protocol, ports, and Attack_type.
- Capability interpretation: Native attack labels; topology comes from observed endpoint pairs. Host compromise and routes are derived and shown only as estimates.
- Build and checksums: use `tools/datasets/fetch.py --source cic-iot-2023` to stage user-downloaded files with SHA-256 values, then `tools/datasets/build_real_pack.py --source cic-iot-2023 --raw <verified-folder>`. The output defaults to ignored local data and is not activated.
- Evaluation: `evaluation.json` labels the label-playback baseline as tautological; route metrics are not reported until at least five reviewed ordered routes are available. Fixture tests are not full-dataset metrics.
- Gate: The official page reviewed describes the dataset but does not establish a redistribution grant. Builder output stays local pending permission.
