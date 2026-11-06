# CSE-CIC-IDS2018 labeled flows

D0 dataset-gate record. No raw data or converted dataset is included in this repository. Pack approval remains pending where stated.

- **Source:** https://www.unb.ca/cic/datasets/ids-2018.html ; https://registry.opendata.aws/cse-cic-ids2018/
- **Access:** public S3 registry; no-account access listed by AWS
- **Licence / redistribution:** UNB page permits redistribution with citation and AWS link. Preserve required attribution; selected file/window must be checked before repackaging.
- **Citation:** Sharafaldin et al., Toward Generating a New Intrusion Detection Dataset and Intrusion Traffic Characterization (2018); dataset page requests citation.
- **Capability provenance:**
  - Detection labels: **native**
  - Host compromise: **derived**
  - Lateral-movement routes: **derived**
  - Topology: **derived**
- **What the labels mean / limitations:** Flow attack labels are native. Host compromise and movement routes are interpretations from scenario schedules and observed traffic, not ground truth.
- **Conversion and validation gate:** no source file was downloaded in D0, so file names, byte sizes, SHA-256 checksums, exact schema, sampling window, label audit, and resulting pack size remain **unverified**. D5 must record these from the official source, use a tiny hand-made fixture in tests, and refuse to ship a converted pack until redistribution rights and attribution are satisfied.
- **D0 disposition:** candidate for attributed derived pack; gated on file/window verification.

## D5 offline builder

- Input: Selected CICFlowMeter CSV rows with timestamp, Src IP, Dst IP, protocol, ports, and Label. The builder accepts the common official CSV header variants.
- Capability interpretation: Native flow labels. Host and route provenance are derived; external access-labelled flows start an estimated path, and later internal lateral-labelled flows may extend it.
- Build and checksums: use `tools/datasets/fetch.py --source cse-cic-ids2018` to stage user-downloaded files with SHA-256 values, then `tools/datasets/build_real_pack.py --source cse-cic-ids2018 --raw <verified-folder>`. The output defaults to ignored local data and is not activated.
- Evaluation: `evaluation.json` labels the label-playback baseline as tautological; route metrics are not reported until at least five reviewed ordered routes are available. Fixture tests are not full-dataset metrics.
- Gate: UNB permits redistribution with citation and the AWS registry link. No files were downloaded here, so no source hash or evaluation metric is asserted.
