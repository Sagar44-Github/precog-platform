"""Turns network addresses into host names, using the shared list in contracts/data/hosts.json."""
import json
from pathlib import Path


class HostMap:
    def __init__(self, hosts):
        """hosts: a list of dicts with at least host_id, name and address."""
        self._by_id = {}
        self._by_address = {}
        for host in hosts:
            for key in ("host_id", "name", "address"):
                if not isinstance(host.get(key), str) or not host[key].strip():
                    raise ValueError("Every host needs a non-empty '%s': %r" % (key, host))
            host_id, address = host["host_id"], host["address"]
            if host_id in self._by_id:
                raise ValueError("Duplicate host_id: %s" % host_id)
            if address in self._by_address:
                raise ValueError("Duplicate address: %s" % address)
            self._by_id[host_id] = dict(host)
            self._by_address[address] = host_id
        if not self._by_id:
            raise ValueError("The host list is empty")

    @classmethod
    def from_file(cls, path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(data["hosts"])

    def host_ids(self):
        return list(self._by_id)

    def is_known(self, host_id):
        return host_id in self._by_id

    def host_for_address(self, address):
        """The host id for an address such as 192.168.1.11, or None if we do not know it."""
        return self._by_address.get(address)

    def name_of(self, value):
        """A readable name for a host id or an address. Unknown values are returned unchanged;
        a missing value becomes 'Unknown host'."""
        if value is None or value == "":
            return "Unknown host"
        if value in self._by_id:
            return self._by_id[value]["name"]
        host_id = self._by_address.get(value)
        return self._by_id[host_id]["name"] if host_id else str(value)

    def host_or_address(self, address):
        """Host id when known, otherwise the address itself (so an unknown machine is still shown).
        A missing address becomes 'unknown'."""
        if address is None or address == "":
            return "unknown"
        return self.host_for_address(address) or str(address)
