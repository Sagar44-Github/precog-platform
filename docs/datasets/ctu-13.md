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

## D5 offline builder

- Input: The builder reads comma-delimited text flow exports with StartTime, SrcAddr, DstAddr, Proto, Sport, Dport, and Label. The binary .biargus files need a documented Argus-to-CSV export first; the builder does not execute Argus or parse binary files.
- Capability interpretation: Native flow labels; infected-host status and routes remain scenario-dependent estimates. The builder emits only routes supported by labels and ordering in the chosen CSV window.
- Build and checksums: use `tools/datasets/fetch.py --source ctu-13` to stage user-downloaded files with SHA-256 values, then `tools/datasets/build_real_pack.py --source ctu-13 --raw <verified-folder>`. The output defaults to ignored local data and is not activated.
- Evaluation: `evaluation.json` labels the label-playback baseline as tautological; route metrics are not reported until at least five reviewed ordered routes are available. Fixture tests are not full-dataset metrics.
- Gate: The source overview identifies CC BY. Preserve Stratosphere attribution and the exact paper citation. The binary archive was not downloaded.
