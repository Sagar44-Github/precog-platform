"""Reads the shared host list (contracts/data/hosts.json). GRAPH keeps its own tiny reader so it never imports another role's code."""
import json
from pathlib import Path


def load_hosts(path):
    """Returns a list of host dicts with host_id, name, zone, address. Raises ValueError for a bad list."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    hosts = data.get("hosts")
    if not isinstance(hosts, list) or not hosts:
        raise ValueError("The host file has no 'hosts' list")
    seen_ids, seen_addresses = set(), set()
    for host in hosts:
        for key in ("host_id", "name", "zone", "address"):
            if not isinstance(host.get(key), str) or not host[key].strip():
                raise ValueError("Every host needs a non-empty '%s': %r" % (key, host))
        if host["zone"] not in ("user", "dmz", "internal"):
            raise ValueError("Host %s has an unknown zone '%s'" % (host["host_id"], host["zone"]))
        if host["host_id"] in seen_ids or host["address"] in seen_addresses:
            raise ValueError("Duplicate host id or address: %s / %s" % (host["host_id"], host["address"]))
        seen_ids.add(host["host_id"])
        seen_addresses.add(host["address"])
    return hosts


def address_of(hosts, host_id):
    for host in hosts:
        if host["host_id"] == host_id:
            return host["address"]
    raise ValueError("Unknown host '%s'. Known hosts: %s" % (host_id, ", ".join(h["host_id"] for h in hosts)))
