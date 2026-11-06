# UNSW-NB15 labeled flows

D0 dataset-gate record. No raw data or converted dataset is included in this repository. Pack approval remains pending where stated.

- **Source:** https://research.unsw.edu.au/projects/unsw-nb15-dataset
- **Access:** download from UNSW project page
- **Licence / redistribution:** UNSW grants free academic research use; commercial use requires an agreement. Redistribution of converted data is not established.
- **Citation:** Moustafa & Slay, UNSW-NB15: a comprehensive data set for network intrusion detection systems (MilCIS 2015).
- **Capability provenance:**
  - Detection labels: **native**
  - Host compromise: **derived**
  - Lateral-movement routes: **derived**
  - Topology: **derived**
- **What the labels mean / limitations:** Flow labels and attack categories support detection evaluation. Host path and compromise truth are limited or derived.
- **Conversion and validation gate:** no source file was downloaded in D0, so file names, byte sizes, SHA-256 checksums, exact schema, sampling window, label audit, and resulting pack size remain **unverified**. D5 must record these from the official source, use a tiny hand-made fixture in tests, and refuse to ship a converted pack until redistribution rights and attribution are satisfied.
- **D0 disposition:** builder only pending explicit redistribution permission.

## D5 offline builder

- Input: Labeled flow CSV files with srcip, dstip, proto, sport, dsport, and attack_cat. Files without timestamps use source row order as a stable replay order.
- Capability interpretation: Native attack labels; topology is derived from observed flow pairs. No ordered lateral routes are assumed, and the pack reports no Precog route evaluation.
- Build and checksums: use `tools/datasets/fetch.py --source unsw-nb15` to stage user-downloaded files with SHA-256 values, then `tools/datasets/build_real_pack.py --source unsw-nb15 --raw <verified-folder>`. The output defaults to ignored local data and is not activated.
- Evaluation: `evaluation.json` labels the label-playback baseline as tautological; route metrics are not reported until at least five reviewed ordered routes are available. Fixture tests are not full-dataset metrics.
- Gate: UNSW documents academic research use. Derived-pack redistribution is not assumed without clarification.
