"""The live attack graph: which hosts are normal, compromised or contained, and which connections were seen.

Every change is copied to the shared world state, so both clients see it on their next poll.
All methods are safe to call from several threads.
"""
import threading
from datetime import datetime, timezone

STATES = ("normal", "compromised", "contained")


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class LiveGraph:
    def __init__(self, topology, world=None, clock=utc_now):
        self.topology = topology
        self.world = world
        self._clock = clock
        self._lock = threading.RLock()
        self._reset_locked()

    def _reset_locked(self):
        self._state = {host_id: "normal" for host_id in self.topology.host_ids()}
        self._edges = {}
        self._path = []

    def _check_known(self, host_id):
        if host_id not in self._state:
            raise ValueError("Unknown host '%s'. Known hosts: %s" % (host_id, ", ".join(self._state)))

    def _publish(self):
        if self.world is not None:
            self.world.set_graph(self._snapshot_locked())

    def _snapshot_locked(self):
        hosts = [{"host_id": h, "name": self.topology.hosts[h]["name"], "zone": self.topology.hosts[h]["zone"], "state": self._state[h]}
                 for h in self.topology.host_ids()]
        edges = [{"from_host": s, "to_host": t, "first_seen": seen} for (s, t), seen in self._edges.items()]
        return {"hosts": hosts, "edges": edges, "compromised_path": list(self._path)}

    # ---------- reading ----------
    def snapshot(self):
        with self._lock:
            return self._snapshot_locked()

    def host_state(self, host_id):
        with self._lock:
            self._check_known(host_id)
            return self._state[host_id]

    def states(self):
        with self._lock:
            return dict(self._state)

    def feasible_targets(self, host_id):
        """Hosts one hop away that are neither compromised nor contained: where the attacker could go next."""
        with self._lock:
            self._check_known(host_id)
            return self.topology.candidates(host_id, exclude=[h for h, s in self._state.items() if s != "normal"])

    # ---------- changing ----------
    def reset(self):
        with self._lock:
            self._reset_locked()
            self._publish()

    def add_connection(self, source, target):
        """Record that `source` was seen talking to `target`. The first sighting keeps its time."""
        with self._lock:
            self._check_known(source)
            self._check_known(target)
            if source == target:
                return False
            new = (source, target) not in self._edges
            if new:
                self._edges[(source, target)] = self._clock()
                self._publish()
            return new

    def mark_compromised(self, host_id):
        """True if the host became compromised now. A contained host stays contained; an already compromised one is unchanged."""
        with self._lock:
            self._check_known(host_id)
            if self._state[host_id] != "normal":
                return False
            self._state[host_id] = "compromised"
            self._path.append(host_id)
            self._publish()
            return True

    def set_host_state(self, host_id, state):
        """Used by containment (state 'contained'). Going back to 'normal' is only for tests and manual resets."""
        if state not in STATES:
            raise ValueError("state must be one of %s" % ", ".join(STATES))
        with self._lock:
            self._check_known(host_id)
            self._state[host_id] = state
            if state == "compromised" and host_id not in self._path:
                self._path.append(host_id)
            self._publish()

    def attempt(self, from_host, to_host):
        """The attacker tries to move from one host to another.
        A contained target blocks the move, and so does a contained source (the attacker has lost that host).
        No connection is recorded for a blocked move. Otherwise the move succeeds: the connection is recorded and
        the target becomes compromised."""
        with self._lock:
            self._check_known(from_host)
            self._check_known(to_host)
            if self._state[to_host] == "contained" or self._state[from_host] == "contained":
                return {"result": "blocked", "from_host": from_host, "to_host": to_host}
            self.add_connection(from_host, to_host)
            self.mark_compromised(to_host)
            return {"result": "success", "from_host": from_host, "to_host": to_host}
