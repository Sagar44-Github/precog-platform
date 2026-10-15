"""The plug-in socket.

Each role puts its finished module into a hook. The backend only ever calls the hook,
so LEAD-CORE's code never has to change when another role finishes their work.

Hook names and what the object behind each one must offer:

  replay        (GRAPH)       list_scenarios() -> list of dicts
                              status() -> replay_status dict
                              start(scenario_id, speed) -> replay_status dict
                              pause() / resume() / restart() -> replay_status dict
  events        (DETECT)      process_packets(rows) -> list of security_event dicts
                              process_technique(host, technique_id, note=None, compromise=False,
                                                severity="HIGH", risk_score=None) -> security_event dict
                              audit_record(entry_type, ref_id, summary) -> audit_entry dict (anyone may call it)
                              reset() -> start a new replay (event numbers begin again)
  graph         (GRAPH)       snapshot() -> graph_snapshot dict
                              reset(); add_connection(src, dst); mark_compromised(host) -> True if it became compromised now
                              set_host_state(host, state) (normal | compromised | contained; containment uses it)
                              host_state(host); attempt(from_host, to_host) -> {"result": "blocked" | "success", ...}
                              feasible_targets(host) -> one-hop hosts still normal; topology -> the static Topology
  precog        (LEAD-CORE)   reset(); on_compromise(host); on_attempt(from_host, to_host, blocked)   (Part 2)
  containment   (VIZ)         propose(world, target_host, forecast_id, requested_by) -> containment_action dict
                              confirm(world, action_id) -> containment_action dict
                              cancel(world, action_id) -> containment_action dict
  push          (VIZ)         register(token) -> None

A role registers its object inside its package's register(ctx) function (ctx.hooks.register(name, obj)).
Until a hook is registered, the matching routes answer with a clear 501 "not built yet".
"""
from .errors import ApiError

KNOWN_HOOKS = ("replay", "events", "graph", "precog", "containment", "push")


class Hooks:
    def __init__(self):
        self._items = {}

    def register(self, name, obj):
        if name not in KNOWN_HOOKS:
            raise ValueError("Unknown hook %r. Known hooks: %s" % (name, ", ".join(KNOWN_HOOKS)))
        self._items[name] = obj

    def get(self, name):
        return self._items.get(name)

    def has(self, name):
        return name in self._items

    
    def require(self, name):
        obj = self._items.get(name)
        if obj is None:
            raise ApiError("not_built", "The '%s' part has not been built yet." % name, 501)
        return obj

    
    def registered(self):
        return sorted(self._items)
