# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
"""Admin API for the device/profile tuning page (ingress only)."""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file

from tuning import (
    TuningConflict,
    TuningError,
    TuningNotFound,
    get_tuning_store,
)

tuning_blueprint = Blueprint("tuning", __name__)

MAX_IMPORT_BYTES = 2_000_000
MAX_IMPORT_ENTRIES = 200


def _actor() -> str:
    for header in (
            "X-Remote-User-Display-Name",
            "X-Remote-User-Name",
            "X-Remote-User-Id"):
        value = request.headers.get(header)
        if value:
            return value
    return "unknown"


def _error(error: Exception):
    if isinstance(error, TuningNotFound):
        status = 404
    elif isinstance(error, TuningConflict):
        status = 409
    else:
        status = 400
    return jsonify({"error": str(error), "type": type(error).__name__}), status


def _yaml_body() -> tuple[str, str | None]:
    body = request.get_json(silent=True) or {}
    text = body.get("yaml")
    if not isinstance(text, str):
        raise TuningError("yaml must be a string")
    expected = body.get("expected_hash")
    if expected is not None and not isinstance(expected, str):
        raise TuningError("expected_hash must be a string")
    return text, expected


@tuning_blueprint.route("/tuning/devices", methods=["GET"])
def list_devices():
    return jsonify(get_tuning_store().list_devices())


@tuning_blueprint.route("/profiles", methods=["GET"])
def list_profiles():
    return jsonify({
        "revision": get_tuning_store().catalog().revision,
        "profiles": get_tuning_store().list_profiles(),
    })


@tuning_blueprint.route("/profiles/validate", methods=["POST"])
def validate_profile():
    try:
        text, _expected = _yaml_body()
        profile_id = (request.get_json(silent=True) or {}).get("profile_id")
        result = get_tuning_store().validate(
            text, profile_id=profile_id, filename="proposal.yaml")
    except TuningError as error:
        return _error(error)
    return jsonify(result.serialize())


@tuning_blueprint.route("/profiles/<profile_id>", methods=["GET"])
def get_profile(profile_id: str):
    try:
        return jsonify(get_tuning_store().get_profile(profile_id))
    except TuningError as error:
        return _error(error)


@tuning_blueprint.route("/profiles/<profile_id>/override", methods=["PUT"])
def put_override(profile_id: str):
    try:
        text, expected = _yaml_body()
        return jsonify(get_tuning_store().save_override(
            profile_id, text, expected_hash=expected, actor=_actor()))
    except TuningError as error:
        return _error(error)


@tuning_blueprint.route("/profiles/<profile_id>/override", methods=["DELETE"])
def delete_override(profile_id: str):
    try:
        body = request.get_json(silent=True) or {}
        expected = body.get("expected_hash")
        if expected is not None and not isinstance(expected, str):
            raise TuningError("expected_hash must be a string")
        return jsonify(get_tuning_store().delete_override(
            profile_id, expected_hash=expected, actor=_actor()))
    except TuningError as error:
        return _error(error)


@tuning_blueprint.route("/profiles/export", methods=["GET"])
def export_profiles():
    try:
        store = get_tuning_store()
        output_format = request.args.get("format", "zip")
        source = request.args.get("source")
        profile_id = request.args.get("id")
        if output_format == "yaml":
            name, text = store.export_yaml(
                profile_id, source if source is not None else "effective")
            return send_file(
                io.BytesIO(text.encode("utf-8")),
                mimetype="application/yaml", as_attachment=True,
                download_name=name)
        name, payload = store.export_zip(
            source if source is not None else "overrides")
        return send_file(
            io.BytesIO(payload), mimetype="application/zip",
            as_attachment=True, download_name=name)
    except TuningError as error:
        return _error(error)


def _import_sources():
    if request.files.get("file") is not None:
        upload = request.files["file"]
        payload = upload.read(MAX_IMPORT_BYTES + 1)
        if len(payload) > MAX_IMPORT_BYTES:
            raise TuningError("import is too large")
        if upload.filename and upload.filename.lower().endswith(".zip"):
            try:
                archive = zipfile.ZipFile(io.BytesIO(payload))
            except zipfile.BadZipFile as error:
                raise TuningError("invalid ZIP archive") from error
            files = []
            with archive:
                entries = [
                    name for name in archive.namelist()
                    if Path(name).suffix.lower() in (".yaml", ".yml")]
                if len(entries) > MAX_IMPORT_ENTRIES:
                    raise TuningError("too many profiles in the archive")
                total = 0
                for name in entries:
                    info = archive.getinfo(name)
                    if info.file_size > MAX_IMPORT_BYTES:
                        raise TuningError(f"{name}: profile is too large")
                    total += info.file_size
                    if total > MAX_IMPORT_BYTES:
                        raise TuningError("import is too large")
                    try:
                        payload = archive.read(name)
                    except (zipfile.BadZipFile, OSError) as error:
                        raise TuningError(
                            f"{name}: unreadable archive entry") from error
                    files.append((Path(name).name,
                                  payload.decode("utf-8")))
            return files
        return [(upload.filename or "profile.yaml",
                 payload.decode("utf-8"))]
    body = request.get_json(silent=True) or {}
    profiles = body.get("profiles")
    if not isinstance(profiles, list) or not profiles:
        raise TuningError("provide a ZIP file or a profiles list")
    if len(profiles) > MAX_IMPORT_ENTRIES:
        raise TuningError("too many profiles")
    files = []
    total = 0
    for item in profiles:
        if not isinstance(item, dict) or not isinstance(
                item.get("yaml"), str):
            raise TuningError("each profile needs an id and yaml")
        total += len(item["yaml"].encode("utf-8"))
        if total > MAX_IMPORT_BYTES:
            raise TuningError("import is too large")
        files.append((str(item.get("id") or "profile.yaml"),
                      item["yaml"]))
    return files


@tuning_blueprint.route("/profiles/import", methods=["POST"])
def import_profiles():
    try:
        dry_run = request.args.get("dry_run", "true").lower() != "false"
        return jsonify(get_tuning_store().import_profiles(
            _import_sources(), dry_run=dry_run, actor=_actor()))
    except (TuningError, UnicodeDecodeError) as error:
        return _error(error)


@tuning_blueprint.route("/profiles/<profile_id>/backups", methods=["GET"])
def list_backups(profile_id: str):
    return jsonify(get_tuning_store().list_backups(profile_id))


@tuning_blueprint.route(
    "/profiles/<profile_id>/backups/<filename>/restore", methods=["POST"])
def restore_backup(profile_id: str, filename: str):
    try:
        return jsonify(get_tuning_store().restore_backup(
            profile_id, filename, actor=_actor()))
    except TuningError as error:
        return _error(error)


@tuning_blueprint.route("/tuning/audit", methods=["GET"])
def audit():
    try:
        limit = int(request.args.get("limit", "200"))
    except ValueError:
        limit = 200
    return jsonify(get_tuning_store().audit_entries(
        limit=limit, profile_id=request.args.get("profile_id")))
