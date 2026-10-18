"""GRAPH's package: the live attack graph and the static topology.

register(ctx) plugs the live graph into the backend through the 'graph' hook:

    graph = ctx.hooks.get("graph")
    graph.snapshot()                       -> graph_snapshot dict
    graph.reset()                          -> all hosts normal, no connections
    graph.add_connection(src, dst)         -> True if the connection is new
    graph.mark_compromised(host)           -> True if the host became compromised now
    graph.set_host_state(host, state)      -> normal | compromised | contained   (containment uses this)
    graph.host_state(host)                 -> the state text
    graph.attempt(from_host, to_host)      -> {"result": "blocked" | "success", "from_host", "to_host"}
    graph.feasible_targets(host)           -> one-hop hosts that are still normal (Precog's candidates)
    graph.topology                         -> the static Topology (candidates, paths, edge_probability, risk ...)
"""
import logging
from pathlib import Path

from .hosts_file import address_of, load_hosts
from .live_graph import LiveGraph
from .topology import Topology

log = logging.getLogger("precog.graph")

PACKAGE_DIR = Path(__file__).resolve().parent
TOPOLOGY_FILE = PACKAGE_DIR / "data" / "topology.json"

__all__ = ["register", "LiveGraph", "Topology", "load_hosts", "address_of", "TOPOLOGY_FILE"]


def register(ctx):
    hosts = load_hosts(ctx.config.contracts_dir / "data" / "hosts.json")
    topology = Topology.from_files(hosts, TOPOLOGY_FILE)
    graph = LiveGraph(topology, world=ctx.world)
    ctx.hooks.register("graph", graph)
    log.info("Attack graph ready (%d hosts, engine: %s)", len(hosts), topology.engine)
    if ctx.config.data_mode == "live":  # sample mode keeps the sample graph
        ctx.world.set_graph(graph.snapshot())
