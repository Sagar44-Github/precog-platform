# CIC-IDS2017 labeled flows

D0 dataset-gate record. No raw data or converted dataset is included in this repository. Pack approval remains pending where stated.

- **Source:** https://www.unb.ca/cic/datasets/ids-2017.html ; https://www.unb.ca/cic/datasets/
- **Access:** public researcher download via UNB/CIC
- **Licence / redistribution:** UNB FAQ permits redistribution/republishing/mirroring with dataset and paper citation; use the dataset-specific page and citation.
- **Citation:** Sharafaldin, Lashkari, Ghorbani, Toward Generating a New Intrusion Detection Dataset and Intrusion Traffic Characterization, ICISSP 2018.
- **Capability provenance:**
  - Detection labels: **native**
  - Host compromise: **derived**
  - Lateral-movement routes: **derived**
  - Topology: **derived**
- **What the labels mean / limitations:** Flow labels are native. Network topology is described for the capture environment; route and compromise truth are not generally native.
- **Conversion and validation gate:** no source file was downloaded in D0, so file names, byte sizes, SHA-256 checksums, exact schema, sampling window, label audit, and resulting pack size remain **unverified**. D5 must record these from the official source, use a tiny hand-made fixture in tests, and refuse to ship a converted pack until redistribution rights and attribution are satisfied.
- **D0 disposition:** candidate for attributed derived pack; gated on selected files and validation.

## D5 offline builder

- Input: Selected files from MachineLearningCSV.zip; timestamp, Src IP, Dst IP, protocol, ports, and Label.
- Capability interpretation: Native flow labels. Host and route provenance are derived from the explicit external-to-internal and subsequent lateral-label rule; flow labels do not establish successful access.
- Build and checksums: use `tools/datasets/fetch.py --source cic-ids2017` to stage user-downloaded files with SHA-256 values, then `tools/datasets/build_real_pack.py --source cic-ids2017 --raw <verified-folder>`. The output defaults to ignored local data and is not activated.
- Evaluation: `evaluation.json` labels the label-playback baseline as tautological; route metrics are not reported until at least five reviewed ordered routes are available. Fixture tests are not full-dataset metrics.
- Gate: UNB FAQ permits redistribution with dataset and paper citations. The full source was not downloaded, so no real corpus score is claimed.
