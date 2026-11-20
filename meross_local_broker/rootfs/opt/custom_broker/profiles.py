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
_DEFAULT_OVERRIDES = "/data/device_profiles"


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
    """Bundled profiles validated against the versioned JSON schema.

    An invalid profile is excluded and reported; it never prevents the broker
    from starting.
    """

    def __init__(self, directory: Optional[str] = None,
                 overrides_directory: Optional[str] = None):
        self.directory = directory or _DEFAULT_DIR
        self.overrides_directory = (
            _DEFAULT_OVERRIDES if overrides_directory is None
            else overrides_directory)
        self.profiles: Dict[str, Dict[str, Any]] = {}
        self.sources: Dict[str, str] = {}
        self.errors: List[Dict[str, str]] = []
        self.schema_version = 2
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

        self._load_directory(self.directory, "bundled", validator)
        if (self.overrides_directory
                and os.path.isdir(self.overrides_directory)):
            self._load_directory(
                self.overrides_directory, "override", validator)

        self.revision = hashlib.sha256(_canonical(self.profiles)).hexdigest()
        _LOG.info(
            "Loaded %d device profile(s) (%d overridden), revision %s",
            len(self.profiles),
            sum(1 for source in self.sources.values() if source == "override"),
            self.revision[:16])

    def _load_directory(self, directory: str, source: str, validator) -> None:
        try:
            names = sorted(os.listdir(directory))
        except OSError as ex:
            self.errors.append({"file": directory, "error": str(ex)})
            _LOG.error("Device profile directory is unreadable: %s", ex)
            return

        for name in names:
            if not name.endswith((".yaml", ".yml")):
                continue
            path = os.path.join(directory, name)
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    data = yaml.safe_load(handle)
                validator.validate(data)
                profile_id = data["profile"]["id"]
                if self.sources.get(profile_id) == source:
                    raise ValueError(f"duplicate profile id {profile_id}")
                self.profiles[profile_id] = data
                self.sources[profile_id] = source
                if source == "override":
                    _LOG.info("Profile %s overridden from %s",
                              profile_id, path)
            except Exception as ex:  # noqa: BLE001 - reject only this profile
                self.errors.append(
                    {"file": f"{source}:{name}", "error": str(ex)})
                _LOG.error("Invalid device profile %s (%s): %s",
                           name, source, ex)

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
                "source": self.sources.get(profile_id, "bundled"),
                "hash": hashlib.sha256(_canonical(data)).hexdigest(),
                "profile": data,
            })
        return {
            "schema_version": self.schema_version,
            "revision": self.revision,
            "profiles": profiles,
            "errors": list(self.errors),
        }

    def profile_hashes(self) -> Dict[str, str]:
        return {
            profile_id: hashlib.sha256(_canonical(data)).hexdigest()
            for profile_id, data in self.profiles.items()
        }


def diff_profiles(previous: Dict[str, str],
                  current: Dict[str, str]) -> Dict[str, List[str]]:
    """Return added, removed and changed profile ids between two snapshots."""
    previous_ids = set(previous)
    current_ids = set(current)
    return {
        "added": sorted(current_ids - previous_ids),
        "removed": sorted(previous_ids - current_ids),
        "changed": sorted(
            profile_id for profile_id in previous_ids & current_ids
            if previous[profile_id] != current[profile_id]),
    }


_catalog: Optional[ProfileCatalog] = None


def get_catalog() -> ProfileCatalog:
    global _catalog
    if _catalog is None:
        _catalog = ProfileCatalog()
    return _catalog


def reload_catalog() -> Dict[str, Any]:
    """Reload bundled profiles and /data overrides, reporting the diff."""
    global _catalog
    previous = _catalog.profile_hashes() if _catalog is not None else {}
    catalog = ProfileCatalog()
    diff = diff_profiles(previous, catalog.profile_hashes())
    _catalog = catalog
    return {
        "revision": catalog.revision,
        "count": len(catalog.profiles),
        "errors": catalog.errors,
        "diff": diff,
    }
