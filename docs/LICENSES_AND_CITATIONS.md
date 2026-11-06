# Dataset licenses and citations

The checked-in packs contain the project-owned six-host replay and four deterministic
synthetic workspaces only. The real-world sources below are registered for local use;
their raw data are not present in this repository and none were used to produce the
current evaluation numbers. Each dataset card and `datasets/registry.json` retain the
source citation and the current access / redistribution status. Bibliographic entries
are in [`docs/datasets/D5_REFERENCES.bib`](datasets/D5_REFERENCES.bib).

| Source | Current status | Redistribution / use gate | Citation record |
| --- | --- | --- | --- |
| Precog demo-6 | Bundled scripted simulation | Project-owned; not observed network data | Demo card and generator version |
| Precog synthetic enterprise 30 / 120 / 300 | Bundled generated simulations | Project-owned; no third-party dataset redistributed | Each synthetic workspace card |
| Precog synthetic datacenter 300 | Local pack; not in hosted build | Project-owned; no third-party dataset redistributed | Workspace card and generator version |
| LANL Cyber1 | Builder-ready; manual access request and data absent | LANL release terms and selected source files must be checked | `kent2015cyberdata1`, `kent2015dynamicnetworks` |
| CSE-CIC-IDS2018 | Builder-ready; not downloaded | Attribution required; retain source-file hashes and citation | Sharafaldin et al. (2018), dataset card |
| CIC-IDS2017 | Builder-ready; not downloaded | Attribution required; retain dataset and paper citations | Sharafaldin, Lashkari & Ghorbani (2018) |
| CTU-13 | Builder-ready; not downloaded | Dataset card records CC BY and citation requirements | Stratosphere and source paper |
| CIC-IoT-2023 | Builder-only; not downloaded | Redistribution terms not established | Official UNB citation, dataset card |
| ToN_IoT | Builder-only; not downloaded | Academic-use conditions; derived redistribution not established | UNSW publications, dataset card |
| UNSW-NB15 | Builder-only; not downloaded | Academic-use conditions; derived redistribution not established | Moustafa & Slay (2015) |
| CIDDS-001 | Builder-only; not downloaded | Broad redistribution permission not confirmed | Ring et al. (2017) |
| Internet Topology Zoo | Builder-ready; no topology bundled | Review each contributor's license before use | Per-topology source citation |

The reused NIDS application is preserved byte-for-byte and includes its upstream MIT
license at `lead-core/backend/nids/LICENSE`. This table records current repository
contents and declared gates; it is not a claim that an uninstalled source has been
downloaded or independently cleared.
