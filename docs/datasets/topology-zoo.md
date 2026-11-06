# Internet Topology Zoo graphs

D0 dataset-gate record. No raw data or converted dataset is included in this repository. Pack approval remains pending where stated.

- **Source:** https://topology-zoo.org/dataset.html
- **Access:** official site links dataset downloads including GitHub/Figshare
- **Licence / redistribution:** Official summary requests citation but the reviewed page does not state a blanket license for all contributed topology files. Check each source topology license.
- **Citation:** LaNet-vi and Topology Zoo citations as listed on the official Topology Zoo page; cite each source network.
- **Capability provenance:**
  - Detection labels: **none**
  - Host compromise: **none**
  - Lateral-movement routes: **none**
  - Topology: **native**
- **What the labels mean / limitations:** Topology only. It supplies no traffic labels, compromise truth, or attack routes.
- **Conversion and validation gate:** no source file was downloaded in D0, so file names, byte sizes, SHA-256 checksums, exact schema, sampling window, label audit, and resulting pack size remain **unverified**. D5 must record these from the official source, use a tiny hand-made fixture in tests, and refuse to ship a converted pack until redistribution rights and attribution are satisfied.
- **D0 disposition:** builder only; per-topology license allowlist required.

## D5 offline simulation adapter

`tools/datasets/build_topology_zoo.py` accepts one GraphML file plus a per-file JSON record with its source URL, license, citation, explicit redistribution permission, and exact SHA-256. The adapter stores only generated opaque host IDs and TEST-NET placeholder addresses. It generates every attack event, label, route, and timestamp; these are simulation data, not observed properties of the source. Output is restricted to ignored `lead-core/backend/data/`. The license record is an operator gate, not an independent legal review. No Zoo source graph was downloaded, so this remains uninstalled.
