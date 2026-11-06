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
