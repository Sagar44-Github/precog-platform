"""Makes the training sequences for Precog: many varied, repeatable attack routes over the demo network.

Each sequence is a route (a list of host ids) taken by one of four attacker styles. A fixed seed always gives the same
sequences. LEAD-CORE's Precog Engine learns "from this host, where does the attacker go next?" from them.
"""
import random

PROFILES = ("opportunist", "data-hunter", "domain-chaser", "wanderer")
ENTRY_WEIGHTS = (("host-a", 0.7), ("host-b", 0.3))
MAX_HOSTS = 6
STOP_CHANCE = 0.15  # after at least two hosts, the attacker may stop here


def _weighted(rng, items, weights):
    total = sum(weights)
    pick = rng.random() * total
    running = 0.0
    for item, weight in zip(items, weights):
        running += weight
        if pick <= running:
            return item
    return items[-1]


def _next_host(rng, topology, profile, here, candidates):
    if profile == "wanderer":
        return rng.choice(candidates)
    if profile in ("data-hunter", "domain-chaser"):
        goal = "db-server" if profile == "data-hunter" else "domain-controller"
        distances = {c: topology.distance(c, goal) for c in candidates}
        reachable = {c: d for c, d in distances.items() if d is not None}
        if reachable and rng.random() < 0.7:  # usually head for the goal
            nearest = min(reachable.values())
            closest = [c for c in reachable if reachable[c] == nearest]
            return max(closest, key=lambda c: (topology.edge_probability(here, c), c))
    weights = [max(topology.edge_probability(here, c), 0.01) for c in candidates]  # easier targets are likelier
    return _weighted(rng, candidates, weights)


def generate_sequences(topology, count=300, seed=0):
    """Returns {"seed", "count", "generator", "profiles", "sequences": [{"profile", "path"}]}."""
    rng = random.Random(seed)
    sequences = []
    for index in range(count):
        profile = PROFILES[index % len(PROFILES)]  # an even mix of the four styles
        here = _weighted(rng, [h for h, _ in ENTRY_WEIGHTS], [w for _, w in ENTRY_WEIGHTS])
        path = [here]
        while len(path) < MAX_HOSTS:
            candidates = topology.candidates(here, exclude=path)
            if not candidates:
                break
            if len(path) >= 2 and rng.random() < STOP_CHANCE:
                break
            here = _next_host(rng, topology, profile, here, candidates)
            path.append(here)
        sequences.append({"profile": profile, "path": path})
    return {"seed": seed, "count": count, "generator": "graph_replay.generator v1", "profiles": list(PROFILES), "sequences": sequences}
