# CIDDS-001 flow benchmark

D0 dataset-gate record. No raw data or converted dataset is included in this repository. Pack approval remains pending where stated.

- **Source:** https://www.hs-coburg.de/forschen/cidds-coburg-intrusion-detection-data-sets/
- **Access:** official Coburg page offers a 384 MB zip
- **Licence / redistribution:** Official terms request citation when publishing material based on CIDDS; no explicit redistribution grant was established in the reviewed page.
- **Citation:** Ring et al., Flow-based benchmark data sets for intrusion detection, ECCWS 2017; see official Coburg page for BibTeX.
- **Capability provenance:**
  - Detection labels: **native**
  - Host compromise: **derived**
  - Lateral-movement routes: **derived**
  - Topology: **derived**
- **What the labels mean / limitations:** Flow labels are available; network paths/compromise are not native. Public IPs are anonymized; non-anonymized variants are not publicly shared.
- **Conversion and validation gate:** no source file was downloaded in D0, so file names, byte sizes, SHA-256 checksums, exact schema, sampling window, label audit, and resulting pack size remain **unverified**. D5 must record these from the official source, use a tiny hand-made fixture in tests, and refuse to ship a converted pack until redistribution rights and attribution are satisfied.
- **D0 disposition:** builder only until derived-data redistribution terms are confirmed.

## D5 offline builder

- Input: CSV flow records with Date first seen, Src IP Addr, Dst IP Addr, Proto, ports, Class, and AttackType. AttackType is preferred to Class because Class may describe endpoint perspective.
- Capability interpretation: Native attack-type labels; topology and any route are derived from observed records. Only ordered external-to-internal plus internal lateral-labelled records may form an estimated path.
- Build and checksums: use `tools/datasets/fetch.py --source cidds-001` to stage user-downloaded files with SHA-256 values, then `tools/datasets/build_real_pack.py --source cidds-001 --raw <verified-folder>`. The output defaults to ignored local data and is not activated.
- Evaluation: `evaluation.json` labels the label-playback baseline as tautological; route metrics are not reported until at least five reviewed ordered routes are available. Fixture tests are not full-dataset metrics.
- Gate: The university page requests citation but does not establish broad redistribution permission. Builder output stays local pending clarification.
