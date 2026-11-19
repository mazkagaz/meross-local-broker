# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
# Upstream: https://github.com/albertogeniola/ha-meross-local-broker (Apache-2.0).
"""Lint device profiles: schema, identities, namespaces and hubs.

Usage: python3 profile_lint.py [--schema PATH] PATH...
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import jsonschema
import yaml

DEFAULT_SCHEMA = Path(__file__).with_name("device_profiles") / "schema.json"
DEFAULT_PROFILES = Path(__file__).with_name("device_profiles")


def load_schema(path: Path) -> jsonschema.Draft202012Validator:
    schema = json.loads(path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


def _check_scope(entities: Iterable[dict], payloads: Dict[str, Any],
                 scope: str, allow_subdevice: bool,
                 errors: List[str]) -> None:
    keys = set()
    for index, entity in enumerate(entities):
        key = entity.get("key")
        if key in keys:
            errors.append(f"{scope}: duplicate entity key {key!r}")
        keys.add(key)
        if entity.get("device") == "subdevice" and not allow_subdevice:
            errors.append(
                f"{scope}: entity {key!r} uses device=subdevice outside a "
                "subdevice template")
        state = entity.get("state") or {}
        namespace = state.get("namespace")
        if namespace and namespace not in payloads:
            errors.append(
                f"{scope}: entity {key!r} state namespace {namespace!r} is not "
                "declared in payloads")
        for command_name, command in (entity.get("commands") or {}).items():
            namespace = (command or {}).get("namespace")
            if namespace and namespace not in payloads:
                errors.append(
                    f"{scope}: entity {key!r} command {command_name!r} "
                    f"namespace {namespace!r} is not declared in payloads")


def lint_documents(
        documents: Iterable[Tuple[str, dict]],
        validator: jsonschema.Draft202012Validator
) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []
    profile_ids: Dict[str, str] = {}

    for filename, profile in documents:
        schema_errors = sorted(
            validator.iter_errors(profile), key=lambda item: list(item.path))
        if schema_errors:
            for item in schema_errors:
                path = "/".join(str(part) for part in item.path) or "<root>"
                errors.append(f"{filename}: schema {path}: {item.message}")
            continue

        profile_id = profile["profile"]["id"]
        if profile_id in profile_ids:
            errors.append(
                f"{filename}: duplicate profile id {profile_id!r} "
                f"(already in {profile_ids[profile_id]})")
        profile_ids[profile_id] = filename

        payloads = profile.get("payloads") or {}
        _check_scope(profile.get("entities") or [], payloads,
                     f"{filename}:{profile_id}", False, errors)

        subdevices = profile.get("subdevices") or []
        if subdevices and profile.get("match", {}).get(
                "kind", "device") not in ("hub", "any"):
            errors.append(
                f"{filename}: subdevices require match.kind hub or any")
        for index, subdevice in enumerate(subdevices):
            scope = f"{filename}:{profile_id}:subdevice[{index}]"
            sub_payloads = dict(payloads)
            sub_payloads.update(subdevice.get("payloads") or {})
            _check_scope(subdevice.get("entities") or [], sub_payloads,
                         scope, True, errors)
            if not subdevice.get("match", {}).get("type"):
                errors.append(f"{scope}: missing match.type")

    return errors, warnings


def expand_paths(paths: List[str]) -> List[Path]:
    files: List[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            files.extend(sorted(path.glob("*.yaml")))
            files.extend(sorted(path.glob("*.yml")))
        else:
            files.append(path)
    return files


def load_documents(files: Iterable[Path]) -> List[Tuple[str, dict]]:
    documents = []
    for path in files:
        with path.open(encoding="utf-8") as handle:
            documents.append((str(path), yaml.safe_load(handle)))
    return documents


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lint Meross device profiles")
    parser.add_argument("paths", nargs="*", default=[str(DEFAULT_PROFILES)])
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    args = parser.parse_args(argv)

    validator = load_schema(Path(args.schema))
    errors, warnings = lint_documents(
        load_documents(expand_paths(args.paths)), validator)

    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    print(f"{len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
