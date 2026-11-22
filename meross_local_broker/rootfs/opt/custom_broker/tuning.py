# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
"""Backend for the device/profile tuning page (V1).

All writes target /data/device_profiles overrides only. The bundled catalog is
read-only. Parsing is data-only (safe_load); no profile is executed.
"""
from __future__ import annotations

import difflib
import hashlib
import io
import json
import os
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import yaml

import profile_engine
from db_helper import dbhelper
from profile_lint import DEFAULT_SCHEMA, lint_documents, load_schema
from profiles import ProfileCatalog, get_catalog, reload_catalog

MAX_YAML_BYTES = 256 * 1024
MAX_YAML_LINES = 5000
MAX_DEPTH = 32
MAX_BACKUPS_PER_PROFILE = 20
MAX_EXPORT_PROFILES = 200
PROFILE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
DEFAULT_OVERRIDES = Path("/data/device_profiles")
DEFAULT_BACKUPS = Path("/data/profile_backups")
DEFAULT_AUDIT = Path("/data/profile_audit.jsonl")


class TuningError(ValueError):
    """Invalid request or profile content."""


class TuningNotFound(TuningError):
    """Unknown profile or backup."""


class TuningConflict(TuningError):
    """Optimistic-lock conflict."""


@dataclass
class ValidationResult:
    valid: bool
    profile_id: Optional[str]
    errors: List[str]
    warnings: List[str]
    summary: Dict[str, Any]
    data: Optional[Dict[str, Any]] = None
    diff: str = ""
    diff_base: Optional[str] = None

    def serialize(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "profile_id": self.profile_id,
            "errors": self.errors,
            "warnings": self.warnings,
            "summary": self.summary,
            "diff": self.diff,
            "diff_base": self.diff_base,
        }


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hash_text(text: str) -> str:
    return _hash_bytes(text.encode("utf-8"))


def _depth(value: Any, current: int = 1) -> int:
    if isinstance(value, dict):
        return max([current] + [
            _depth(item, current + 1) for item in value.values()])
    if isinstance(value, list):
        return max([current] + [
            _depth(item, current + 1) for item in value])
    return current


def _yaml_text(data: Dict[str, Any]) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


class TuningStore:
    """Profile overrides, validation, import/export and audit."""

    def __init__(self, overrides: Path = DEFAULT_OVERRIDES,
                 backups: Path = DEFAULT_BACKUPS,
                 audit: Path = DEFAULT_AUDIT,
                 schema: Path = DEFAULT_SCHEMA,
                 catalog_getter=get_catalog,
                 catalog_reloader=reload_catalog,
                 devices=dbhelper.get_all_devices,
                 ability=dbhelper.get_device_ability) -> None:
        self.overrides = Path(overrides)
        self.backups = Path(backups)
        self.audit = Path(audit)
        self.schema = Path(schema)
        self._catalog_getter = catalog_getter
        self._catalog_reloader = catalog_reloader
        self._devices = devices
        self._ability = ability
        self._validator = load_schema(self.schema)

    # -- inventory -----------------------------------------------------
    def catalog(self) -> ProfileCatalog:
        return self._catalog_getter()

    def list_profiles(self) -> List[Dict[str, Any]]:
        catalog = self.catalog()
        matches = self._match_devices(catalog)
        impact: Dict[str, int] = {}
        for profile_id in matches.values():
            if profile_id:
                impact[profile_id] = impact.get(profile_id, 0) + 1
        result = []
        for profile_id in sorted(catalog.profiles):
            data = catalog.profiles[profile_id]
            override = self._override_path(profile_id)
            result.append({
                "id": profile_id,
                "version": data["profile"].get("version"),
                "source": catalog.sources.get(profile_id, "bundled"),
                "hash": catalog.profile_hashes()[profile_id],
                "requires_engine": data["profile"].get("requires_engine"),
                "devices_affected": impact.get(profile_id, 0),
                "override_file": override.name if override else None,
            })
        return result

    def list_devices(self) -> List[Dict[str, Any]]:
        catalog = self.catalog()
        matches = self._match_devices(catalog)
        devices = []
        for device in self._devices():
            devices.append({
                "uuid": device.uuid,
                "name": device.dev_name,
                "type": device.device_type,
                "sub_type": device.sub_type,
                "online": (device.online_status.value
                           if device.online_status is not None else None),
                "profile": matches.get(device.uuid),
                "channels": [channel.channel_id for channel in
                             device.channels],
                "subdevices": [
                    {"id": sub.sub_device_id,
                     "type": sub.sub_device_type,
                     "name": sub.sub_device_name}
                    for sub in device.child_subdevices
                ],
            })
        return devices

    def _match_devices(self, catalog: ProfileCatalog) -> Dict[str, str]:
        metas = [
            profile_engine.ProfileMeta(
                id=profile_id,
                version=data["profile"].get("version"),
                source=catalog.sources.get(profile_id, "bundled"),
                digest=catalog.profile_hashes()[profile_id],
                requires_engine=data["profile"].get("requires_engine"),
                data=data,
            )
            for profile_id, data in catalog.profiles.items()
        ]
        matches: Dict[str, str] = {}
        for device in self._devices():
            abilities = set()
            row = self._ability(device.uuid)
            if row is not None and row.ability_json:
                try:
                    payload = json.loads(row.ability_json)
                    if isinstance(payload, dict):
                        abilities = set(payload)
                except (TypeError, ValueError):
                    pass
            context = profile_engine.MatchContext(
                type=device.device_type or "",
                sub_type=device.sub_type,
                mac=device.mac,
                abilities=frozenset(abilities),
                is_hub=bool(device.child_subdevices)
                or (device.device_type or "").startswith("msh"),
            )
            result = profile_engine.match_candidates(metas, context)
            matches[device.uuid] = result.profile.id if result.profile else ""
        return matches

    def get_profile(self, profile_id: str) -> Dict[str, Any]:
        catalog = self.catalog()
        data = catalog.profiles.get(profile_id)
        if data is None:
            raise TuningNotFound(f"unknown profile {profile_id}")
        override = self._override_path(profile_id)
        bundled = self._bundled_path(profile_id)
        override_text = override.read_text() if override else None
        bundled_text = bundled.read_text() if bundled else _yaml_text(data)
        diff = ""
        if override_text is not None:
            diff = self._diff(
                bundled_text, override_text,
                f"{profile_id}.yaml (bundled)",
                f"{profile_id}.yaml (override)")
        return {
            "id": profile_id,
            "version": data["profile"].get("version"),
            "source": catalog.sources.get(profile_id, "bundled"),
            "catalog_hash": catalog.profile_hashes()[profile_id],
            "override_hash": (_hash_text(override_text)
                              if override_text is not None else None),
            "revision": catalog.revision,
            "yaml": _yaml_text(data),
            "override_yaml": override_text,
            "bundled_yaml": bundled_text,
            "diff": diff,
            "devices_affected": next(
                (item["devices_affected"] for item in self.list_profiles()
                 if item["id"] == profile_id), 0),
            "backups": self.list_backups(profile_id),
        }

    # -- validation ----------------------------------------------------
    def validate(self, text: str, profile_id: Optional[str] = None,
                 filename: str = "profile.yaml") -> ValidationResult:
        errors: List[str] = []
        warnings: List[str] = []
        data = None
        if not isinstance(text, str) or not text.strip():
            errors.append("empty YAML document")
        elif len(text.encode("utf-8")) > MAX_YAML_BYTES:
            errors.append(f"YAML exceeds {MAX_YAML_BYTES} bytes")
        elif len(text.splitlines()) > MAX_YAML_LINES:
            errors.append(f"YAML exceeds {MAX_YAML_LINES} lines")
        else:
            try:
                data = yaml.safe_load(text)
            except yaml.YAMLError as error:
                mark = getattr(error, "problem_mark", None)
                location = (f"line {mark.line + 1}, column "
                            f"{mark.column + 1}" if mark else "unknown")
                errors.append(f"YAML parse error ({location}): {error}")
        if data is not None and not errors:
            if not isinstance(data, dict):
                errors.append("profile must be a YAML object")
            elif _depth(data) > MAX_DEPTH:
                errors.append(f"YAML is deeper than {MAX_DEPTH} levels")
            else:
                found_id = (data.get("profile") or {}).get("id")
                if profile_id is not None and found_id != profile_id:
                    errors.append(
                        f"profile id {found_id!r} does not match "
                        f"{profile_id!r}")
                lint_errors, warnings = lint_documents(
                    [(filename, data)], self._validator)
                errors.extend(lint_errors)
                if not errors:
                    meta = profile_engine.ProfileMeta(
                        id=found_id,
                        version=(data.get("profile") or {}).get("version"),
                        source="preview",
                        digest=None,
                        requires_engine=None,
                        data=data,
                    )
                    compiled = profile_engine.compile_profile(meta)
                    errors.extend(compiled.errors)
                    warnings.extend(compiled.warnings)
        summary: Dict[str, Any] = {}
        diff = ""
        diff_base: Optional[str] = None
        if data is not None and isinstance(data, dict):
            profile = data.get("profile") or {}
            summary = {
                "id": profile.get("id"),
                "version": profile.get("version"),
                "requires_engine": profile.get("requires_engine"),
                "entities": self._entity_summary(data),
            }
            found_id = profile.get("id")
            if isinstance(found_id, str) and found_id:
                diff_base, base_text = self._diff_base(found_id)
                diff = self._diff(
                    base_text, text,
                    f"{found_id}.yaml ({diff_base})",
                    f"{found_id}.yaml (proposal)")
        return ValidationResult(
            valid=not errors,
            profile_id=summary.get("id"),
            errors=errors,
            warnings=warnings,
            summary=summary,
            data=data,
            diff=diff,
            diff_base=diff_base,
        )

    def _diff_base(self, profile_id: str) -> Tuple[str, str]:
        override = self._override_path(profile_id)
        if override is not None:
            return "override", override.read_text()
        bundled = self._bundled_path(profile_id)
        if bundled is not None:
            return "bundled", bundled.read_text()
        return "none", ""

    @staticmethod
    def _entity_summary(data: Dict[str, Any]) -> List[Dict[str, Any]]:
        entities = []
        for entity in data.get("entities") or []:
            if isinstance(entity, dict):
                entities.append({
                    "key": entity.get("key"),
                    "platform": entity.get("platform"),
                    "name": entity.get("name"),
                    "channel": entity.get("channel"),
                })
        return entities

    # -- writes --------------------------------------------------------
    def save_override(self, profile_id: str, text: str,
                      expected_hash: Optional[str] = None,
                      actor: str = "unknown") -> Dict[str, Any]:
        if not PROFILE_ID_RE.fullmatch(profile_id):
            raise TuningError("invalid profile id")
        result = self.validate(text, profile_id=profile_id)
        if not result.valid:
            raise TuningError("; ".join(result.errors))
        current = self._current_hash(profile_id)
        if expected_hash is not None and expected_hash != current:
            raise TuningConflict(
                "profile changed since it was loaded; refresh before saving")
        override = (self._override_path(profile_id)
                    or self.overrides / f"{profile_id}.yaml")
        before = override.read_text() if override.exists() else None
        self._backup_override(profile_id, override)
        content = text if text.endswith("\n") else text + "\n"
        self._atomic_write(override, content)
        revision = self._reload()
        diff = self._diff(
            self._bundled_text(profile_id), content,
            f"{profile_id}.yaml (bundled)", f"{profile_id}.yaml (override)")
        self._audit({
            "action": "override.save",
            "profile_id": profile_id,
            "actor": actor,
            "before_hash": _hash_text(before) if before is not None else current,
            "after_hash": _hash_text(content),
            "revision": revision,
        })
        return {
            "id": profile_id,
            "revision": revision,
            "override_hash": _hash_text(content),
            "diff": diff,
            "warnings": result.warnings,
        }

    def delete_override(self, profile_id: str,
                        expected_hash: Optional[str] = None,
                        actor: str = "unknown") -> Dict[str, Any]:
        override = self._override_path(profile_id)
        if override is None:
            raise TuningNotFound(f"no override for {profile_id}")
        current = _hash_text(override.read_text())
        if expected_hash is not None and expected_hash != current:
            raise TuningConflict(
                "profile changed since it was loaded; refresh before deleting")
        before = override.read_text()
        self._backup_override(profile_id, override)
        override.unlink()
        revision = self._reload()
        self._audit({
            "action": "override.delete",
            "profile_id": profile_id,
            "actor": actor,
            "before_hash": _hash_text(before),
            "after_hash": None,
            "revision": revision,
        })
        return {"id": profile_id, "revision": revision,
                "removed": True}

    # -- backups -------------------------------------------------------
    def list_backups(self, profile_id: str) -> List[Dict[str, Any]]:
        if not PROFILE_ID_RE.fullmatch(profile_id):
            return []
        items = []
        for path in self.backups.glob(f"*-{profile_id}.yaml"):
            stat = path.stat()
            items.append({
                "file": path.name,
                "created_at": datetime.fromtimestamp(
                    stat.st_mtime, timezone.utc).isoformat(),
                "hash": _hash_text(path.read_text()),
            })
        return sorted(items, key=lambda item: item["created_at"],
                      reverse=True)

    def restore_backup(self, profile_id: str, filename: str,
                       actor: str = "unknown") -> Dict[str, Any]:
        if not PROFILE_ID_RE.fullmatch(profile_id):
            raise TuningError("invalid profile id")
        source = self.backups / filename
        if source.parent != self.backups or not source.is_file():
            raise TuningNotFound(f"unknown backup {filename}")
        if not filename.endswith(f"-{profile_id}.yaml"):
            raise TuningError("backup does not belong to this profile")
        text = source.read_text()
        result = self.validate(text, profile_id=profile_id)
        if not result.valid:
            raise TuningConflict(
                "backup no longer validates: " + "; ".join(result.errors))
        override = (self._override_path(profile_id)
                    or self.overrides / f"{profile_id}.yaml")
        self._backup_override(profile_id, override)
        self._atomic_write(override, text)
        revision = self._reload()
        self._audit({
            "action": "override.restore",
            "profile_id": profile_id,
            "actor": actor,
            "backup": filename,
            "after_hash": _hash_text(text),
            "revision": revision,
        })
        return {"id": profile_id, "revision": revision,
                "restored": filename}

    # -- import / export ----------------------------------------------
    @staticmethod
    def _export_source(source: str) -> str:
        normalized = (source or "effective").strip().lower()
        if normalized in ("override", "overrides"):
            return "overrides"
        if normalized in ("effective", "bundled", "catalog"):
            return "effective"
        raise TuningError(
            "source must be 'overrides' or 'effective'")

    def export_yaml(self, profile_id: Optional[str] = None,
                    source: str = "effective") -> Tuple[str, str]:
        """Return (filename, YAML text)."""
        if profile_id is None:
            raise TuningError("profile_id is required for YAML export")
        if not PROFILE_ID_RE.fullmatch(profile_id):
            raise TuningError("invalid profile id")
        if self._export_source(source) == "overrides":
            override = self._override_path(profile_id)
            if override is None:
                raise TuningNotFound(f"no override for {profile_id}")
            return f"{profile_id}.yaml", override.read_text()
        profile = self.get_profile(profile_id)
        return f"{profile_id}.yaml", profile["yaml"]

    def export_zip(self, source: str = "overrides") -> Tuple[str, bytes]:
        source = self._export_source(source)
        entries = {}
        if source == "overrides":
            for profile_id in sorted(self._override_ids()):
                override = self._override_path(profile_id)
                if override is not None:
                    entries[f"{profile_id}.yaml"] = override.read_text()
        else:
            catalog = self.catalog()
            for profile_id in sorted(catalog.profiles)[:MAX_EXPORT_PROFILES]:
                entries[f"{profile_id}.yaml"] = _yaml_text(
                    catalog.profiles[profile_id])
        if not entries:
            raise TuningNotFound("nothing to export")
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            manifest = {
                "revision": self.catalog().revision,
                "source": source,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "profiles": [
                    {"id": name[:-5], "hash": _hash_text(text)}
                    for name, text in entries.items()
                ],
            }
            archive.writestr("manifest.json", json.dumps(
                manifest, indent=2, sort_keys=True) + "\n")
            for name, text in entries.items():
                archive.writestr(name, text)
        return "meross-profiles.zip", buffer.getvalue()

    def import_profiles(self, files: Iterable[Tuple[str, str]],
                        dry_run: bool = True,
                        actor: str = "unknown") -> Dict[str, Any]:
        validated = []
        seen = set()
        for filename, text in files:
            result = self.validate(text, filename=filename or "profile.yaml")
            if not result.valid:
                raise TuningError(
                    f"{filename}: " + "; ".join(result.errors))
            profile_id = result.profile_id
            if not profile_id or not PROFILE_ID_RE.fullmatch(profile_id):
                raise TuningError(f"{filename}: invalid profile id")
            if profile_id in seen:
                raise TuningError(f"{filename}: duplicate profile id")
            seen.add(profile_id)
            validated.append((profile_id, filename, text, result))
        if not dry_run:
            for profile_id, _filename, text, _result in validated:
                override = (self._override_path(profile_id)
                            or self.overrides / f"{profile_id}.yaml")
                self._backup_override(profile_id, override)
                self._atomic_write(override,
                                   text if text.endswith("\n")
                                   else text + "\n")
                self._audit({
                    "action": "override.import",
                    "profile_id": profile_id,
                    "actor": actor,
                    "after_hash": _hash_text(text),
                })
            revision = self._reload()
        else:
            revision = self.catalog().revision
        return {
            "dry_run": dry_run,
            "revision": revision,
            "profiles": [
                {"id": profile_id, "filename": filename,
                 "warnings": result.warnings}
                for profile_id, filename, _text, result in validated
            ],
        }

    # -- audit ---------------------------------------------------------
    def audit_entries(self, limit: int = 200,
                      profile_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self.audit.is_file():
            return []
        entries = []
        with self.audit.open(encoding="utf-8") as handle:
            for line in handle:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if profile_id and entry.get("profile_id") != profile_id:
                    continue
                entries.append(entry)
        return entries[-max(1, min(limit, 500)):][::-1]

    def _audit(self, entry: Dict[str, Any]) -> None:
        entry = dict(entry)
        entry["at"] = datetime.now(timezone.utc).isoformat()
        try:
            self.audit.parent.mkdir(parents=True, exist_ok=True)
            with self.audit.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, sort_keys=True) + "\n")
            os.chmod(self.audit, 0o600)
        except OSError:
            pass

    # -- filesystem helpers -------------------------------------------
    def _current_hash(self, profile_id: str) -> Optional[str]:
        override = self._override_path(profile_id)
        if override is not None:
            return _hash_text(override.read_text())
        catalog = self.catalog()
        hashes = catalog.profile_hashes()
        return hashes.get(profile_id)

    def _override_ids(self) -> List[str]:
        ids = []
        for path in self._iter_override_files():
            try:
                data = yaml.safe_load(path.read_text())
            except (OSError, yaml.YAMLError):
                continue
            profile_id = ((data or {}).get("profile") or {}).get("id")
            if isinstance(profile_id, str):
                ids.append(profile_id)
        return ids

    def _iter_override_files(self) -> Iterable[Path]:
        try:
            for path in sorted(self.overrides.iterdir()):
                if path.is_file() and path.suffix in (".yaml", ".yml"):
                    yield path
        except OSError:
            return

    def _override_path(self, profile_id: str) -> Optional[Path]:
        if not PROFILE_ID_RE.fullmatch(profile_id):
            return None
        for path in self._iter_override_files():
            try:
                data = yaml.safe_load(path.read_text())
            except (OSError, yaml.YAMLError):
                continue
            found = ((data or {}).get("profile") or {}).get("id")
            if found == profile_id:
                return path
        return None

    def _bundled_path(self, profile_id: str) -> Optional[Path]:
        catalog = self.catalog()
        for path in Path(catalog.directory).iterdir():
            if path.suffix not in (".yaml", ".yml"):
                continue
            try:
                data = yaml.safe_load(path.read_text())
            except (OSError, yaml.YAMLError):
                continue
            if ((data or {}).get("profile") or {}).get("id") == profile_id:
                return path
        return None

    def _bundled_text(self, profile_id: str) -> str:
        path = self._bundled_path(profile_id)
        if path is not None:
            return path.read_text()
        data = self.catalog().profiles.get(profile_id)
        return _yaml_text(data) if data else ""

    def _backup_override(self, profile_id: str,
                         override: Optional[Path]) -> None:
        if override is None or not override.is_file():
            return
        self.backups.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        target = self.backups / f"{stamp}-{profile_id}.yaml"
        shutil.copyfile(override, target)
        os.chmod(target, 0o600)
        backups = sorted(
            self.backups.glob(f"*-{profile_id}.yaml"))
        for old in backups[:-MAX_BACKUPS_PER_PROFILE]:
            try:
                old.unlink()
            except OSError:
                pass

    @staticmethod
    def _atomic_write(target: Path, content: str) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            dir=target.parent, prefix=f".{target.name}.")
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, target)
            directory = os.open(target.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except Exception:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise

    def _reload(self) -> str:
        result = self._catalog_reloader() or {}
        return result.get("revision") or self.catalog().revision

    @staticmethod
    def _diff(before: str, after: str, before_name: str,
              after_name: str) -> str:
        return "\n".join(difflib.unified_diff(
            before.splitlines(), after.splitlines(),
            fromfile=before_name, tofile=after_name, lineterm=""))


_store: Optional[TuningStore] = None


def get_tuning_store() -> TuningStore:
    global _store
    if _store is None:
        _store = TuningStore()
    return _store
