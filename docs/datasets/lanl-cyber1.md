# LANL Cyber1 authentication and system events

D0 dataset-gate record. No raw data or converted dataset is included in this repository. Pack approval remains pending where stated.

- **Source:** https://csr.lanl.gov/data/cyber1/
- **Access:** request from LANL CSR using intended-use form; source files are multi-GB
- **Licence / redistribution:** LANL states it waived copyright and related rights to the extent possible; request/access conditions still apply. Do not redistribute without reviewing LANL terms for the specific release.
- **Citation:** LANL CSR, Cyber1 dataset, public release LA-UR-15-23810; use citation/BibTeX supplied on official dataset page.
- **Capability provenance:**
  - Detection labels: **native**
  - Host compromise: **derived**
  - Lateral-movement routes: **derived**
  - Topology: **derived**
- **What the labels mean / limitations:** Native authentication/process/flow records and red-team annotations support only narrow event labels. Do not turn red-team annotations into complete host-compromise truth.
- **Conversion and validation gate:** no source file was downloaded in D0, so file names, byte sizes, SHA-256 checksums, exact schema, sampling window, label audit, and resulting pack size remain **unverified**. D5 must record these from the official source, use a tiny hand-made fixture in tests, and refuse to ship a converted pack until redistribution rights and attribution are satisfied.
- **D0 disposition:** builder only until per-release terms and privacy review.
