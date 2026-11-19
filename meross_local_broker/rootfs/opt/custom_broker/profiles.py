# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
# Upstream: https://github.com/albertogeniola/ha-meross-local-broker (Apache-2.0).
"""Load and validate the bundled device profile catalog."""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, List, Optional

import jsonschema
import yaml

from logger import get_logger

_LOG = get_logger(__name__)
_DEFAULT_DIR = os.path.join(os.path.dirname(__file__), "device_profiles")


def _normalize(value: Any) -> Any:
    """Make YAML mappings JSON-safe (some profiles use integer enum keys)."""
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    return value


def _canonical(value: Any) -> bytes:
    return json.dumps(_normalize(value), sort_keys=True,
                      separators=(",", ":")).encode("utf8")


class ProfileCatalog:
    """Bundled profiles validated against the v0 JSON schema.

    An invalid profile is excluded and reported; it never prevents the broker
    from starting.
    """

    def __init__(self, directory: Optional[str] = None):
        self.directory = directory or _DEFAULT_DIR
        self.profiles: Dict[str, Dict[str, Any]] = {}
        self.errors: List[Dict[str, str]] = []
        self.schema_version = 1
        self.revision = ""
        self._load()

    def _load(self) -> None:
        schema_path = os.path.join(self.directory, "schema.json")
        try:
            with open(schema_path, "r", encoding="utf-8") as handle:
                schema = json.load(handle)
            jsonschema.Draft202012Validator.check_schema(schema)
            validator = jsonschema.Draft202012Validator(schema)
        except Exception as ex:  # noqa: BLE001 - keep the broker available
            self.errors.append({"file": "schema.json", "error": str(ex)})
            _LOG.error("Device profile schema is unusable: %s", ex)
            self.revision = hashlib.sha256(_canonical({})).hexdigest()
            return

        try:
            names = sorted(os.listdir(self.directory))
        except OSError as ex:
            self.errors.append({"file": self.directory, "error": str(ex)})
            _LOG.error("Device profile directory is unreadable: %s", ex)
            names = []

        for name in names:
            if not name.endswith((".yaml", ".yml")):
                continue
            path = os.path.join(self.directory, name)
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    data = yaml.safe_load(handle)
                validator.validate(data)
                profile_id = data["profile"]["id"]
                if profile_id in self.profiles:
                    raise ValueError(f"duplicate profile id {profile_id}")
                self.profiles[profile_id] = data
            except Exception as ex:  # noqa: BLE001 - reject only this profile
                self.errors.append({"file": name, "error": str(ex)})
                _LOG.error("Invalid device profile %s: %s", name, ex)

        self.revision = hashlib.sha256(_canonical(self.profiles)).hexdigest()
        _LOG.info(
            "Loaded %d device profile(s), revision %s",
            len(self.profiles), self.revision[:16])

    def revision_payload(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "revision": self.revision,
            "count": len(self.profiles),
            "errors": len(self.errors),
        }

    def payload(self) -> Dict[str, Any]:
        profiles = []
        for profile_id in sorted(self.profiles):
            data = self.profiles[profile_id]
            profiles.append({
                "id": profile_id,
                "version": data["profile"].get("version"),
                "requires_engine": data["profile"].get("requires_engine"),
                "source": "bundled",
                "hash": hashlib.sha256(_canonical(data)).hexdigest(),
                "profile": data,
            })
        return {
            "schema_version": self.schema_version,
            "revision": self.revision,
            "profiles": profiles,
            "errors": list(self.errors),
        }


_catalog: Optional[ProfileCatalog] = None


def get_catalog() -> ProfileCatalog:
    global _catalog
    if _catalog is None:
        _catalog = ProfileCatalog()
    return _catalog
