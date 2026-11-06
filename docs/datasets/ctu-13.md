# CTU-13 botnet captures

D0 dataset-gate record. No raw data or converted dataset is included in this repository. Pack approval remains pending where stated.

- **Source:** https://www.stratosphereips.org/datasets-overview ; https://www.stratosphereips.org/datasets-faq
- **Access:** download via Stratosphere dataset page
- **Licence / redistribution:** Dataset overview identifies CC-BY; use attribution and exact paper citation from Stratosphere.
- **Citation:** Garcia et al., An empirical comparison of botnet detection methods, Computers & Security 45 (2014), and citations listed by Stratosphere.
- **Capability provenance:**
  - Detection labels: **native**
  - Host compromise: **derived**
  - Lateral-movement routes: **derived**
  - Topology: **derived**
- **What the labels mean / limitations:** Binetflow labels distinguish botnet, normal, and background. Botnet origin can support a narrow infected-source interpretation, not arbitrary lateral movement.
- **Conversion and validation gate:** no source file was downloaded in D0, so file names, byte sizes, SHA-256 checksums, exact schema, sampling window, label audit, and resulting pack size remain **unverified**. D5 must record these from the official source, use a tiny hand-made fixture in tests, and refuse to ship a converted pack until redistribution rights and attribution are satisfied.
- **D0 disposition:** candidate for attributed derived pack; gated on per-capture checksum and schema.
