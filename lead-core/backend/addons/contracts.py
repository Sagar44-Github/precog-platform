"""Loads the JSON Schemas from contracts/schemas and checks data against them."""
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


SCHEMA_SUFFIX = ".schema.json"


class ContractError(ValueError):
    """The data does not follow its contract."""


class Contracts:
    def __init__(self, contracts_dir):
        
        self.schema_dir = Path(contracts_dir) / "schemas"
        self._schemas = {}
        
        for path in sorted(self.schema_dir.glob("*" + SCHEMA_SUFFIX)):
            name = path.name[: -len(SCHEMA_SUFFIX)]
            self._schemas[name] = json.loads(path.read_text(encoding="utf-8"))

        if not self._schemas:
            raise FileNotFoundError("No schema files found in %s" % self.schema_dir)
        
        resources = [
            (schema["$id"], Resource.from_contents(schema)) for schema in self._schemas.values()
        ]
        
        self._registry = Registry().with_resources(resources)
        self._validators = {}

    def names(self):
        return sorted(self._schemas)

    def validator(self, name):
        
        if name not in self._schemas:
            raise KeyError("Unknown contract: %s" % name)
        
        if name not in self._validators:
            self._validators[name] = Draft202012Validator(self._schemas[name], registry=self._registry)
        return self._validators[name]

    def errors(self, name, instance):
        return sorted(self.validator(name).iter_errors(instance), key=lambda e: list(e.path))

    def validate(self, name, instance):
        problems = self.errors(name, instance)
        
        if problems:
            first = problems[0]
            where = "/".join(str(p) for p in first.path) or "(top level)"
        
            raise ContractError("%s does not follow its contract at %s: %s" % (name, where, first.message))
        
        return instance
