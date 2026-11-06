# Synthetic replay on a Topology Zoo graph (deferred reserve)

This remains a **local-only reserve**, not a shipped workspace. D3 builds four project-owned synthetic packs. D5 added a GraphML builder, but no Zoo-derived graph is bundled or installed.

The [official Topology Zoo dataset page](https://topology-zoo.org/dataset.html) asks users to cite the collection, while the [official source repository](https://github.com/sk2/topologyzoo) does not provide a blanket license for every contributed topology file. Each selected source topology needs its own terms and attribution review before copying or redistributing it.

`tools/datasets/build_topology_zoo.py` accepts one GraphML file and a license record containing its source URL, exact citation, license, explicit redistribution permission, and matching SHA-256. It generates the events, labels, routes, and timing itself; only graph structure comes from the cited input. The record is an operator-supplied gate, not an independent legal review. Keep output under ignored local data until the source terms have been reviewed. The fixture test uses a handmade graph and is not evidence that any Topology Zoo file is cleared. No source topology was downloaded for D5.
