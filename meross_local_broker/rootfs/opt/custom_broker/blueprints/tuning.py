# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
"""Admin API for the device/profile tuning page (ingress only)."""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file

from capture import get_capture_manager
from tuning import (
    TuningConflict,
    TuningError,
    TuningNotFound,
    TuningRateLimited,
    TuningTimeout,
    TuningUnavailable,
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
    elif isinstance(error, TuningTimeout):
        status = 504
    elif isinstance(error, TuningUnavailable):
        status = 503
    elif isinstance(error, TuningRateLimited):
        response = jsonify({
            "error": str(error), "type": type(error).__name__,
            "retry_after": error.retry_after})
        response.status_code = 429
        response.headers["Retry-After"] = str(error.retry_after)
        return response
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


@tuning_blueprint.route("/tuning/devices/<uuid>", methods=["GET"])
def device_state(uuid: str):
    try:
        return jsonify(get_tuning_store().device_state(uuid))
    except TuningError as error:
        return _error(error)


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


@tuning_blueprint.route("/profiles/<profile_id>/preview", methods=["POST"])
def preview_profile(profile_id: str):
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return _error(TuningError("body must be an object"))
    namespace = body.get("namespace")
    method = body.get("method")
    payload = body.get("payload")
    frame = body.get("frame")
    if isinstance(frame, dict):
        header = frame.get("header") or {}
        if isinstance(header, dict):
            namespace = namespace or header.get("namespace")
            method = method or header.get("method")
        if payload is None:
            payload = frame.get("payload")
    if payload is None:
        payload = {}
    try:
        return jsonify(get_tuning_store().simulate(
            profile_id, namespace=namespace, method=method,
            payload=payload, channels=body.get("channels"),
            subdevice=body.get("subdevice")))
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


@tuning_blueprint.route("/tuning/devices/<uuid>/read", methods=["POST"])
def read_device(uuid: str):
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return _error(TuningError("body must be an object"))
    timeout = None
    if body.get("timeout_ms") is not None:
        try:
            timeout = float(body["timeout_ms"]) / 1000.0
        except (TypeError, ValueError):
            return _error(TuningError("timeout_ms must be a number"))
    try:
        return jsonify(get_tuning_store().read_device(
            uuid, namespace=body.get("namespace"),
            payload=body.get("payload"), timeout=timeout))
    except TuningError as error:
        return _error(error)


@tuning_blueprint.route("/tuning/devices/<uuid>/commands", methods=["GET"])
def device_commands(uuid: str):
    try:
        return jsonify(get_tuning_store().device_commands(uuid))
    except TuningError as error:
        return _error(error)


@tuning_blueprint.route(
    "/tuning/devices/<uuid>/commands/<command_id>", methods=["POST"])
def execute_command(uuid: str, command_id: str):
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return _error(TuningError("body must be an object"))
    try:
        return jsonify(get_tuning_store().execute_command(
            uuid, command_id,
            channel=body.get("channel"),
            value=body.get("value"),
            confirm=body.get("confirm") is True,
            token=body.get("token"),
            actor=_actor()))
    except TuningError as error:
        return _error(error)


@tuning_blueprint.route("/tuning/capture/status", methods=["GET"])
def capture_status():
    return jsonify(get_capture_manager().status() or {})


@tuning_blueprint.route("/tuning/capture/start", methods=["POST"])
def capture_start():
    body = request.get_json(silent=True) or {}
    uuid = body.get("uuid") if isinstance(body, dict) else None
    if not uuid:
        return _error(TuningError("missing device uuid"))
    try:
        status = get_capture_manager().start(
            {"uuid": uuid, "type": body.get("type"),
             "firmware": body.get("firmware"),
             "abilities": body.get("abilities") or []},
            duration_s=body.get("duration_s", 300),
            max_bytes=body.get("max_bytes", 2_000_000))
    except (TypeError, ValueError) as error:
        return _error(TuningError(str(error)))
    return jsonify(status)


@tuning_blueprint.route("/tuning/capture/stop", methods=["POST"])
def capture_stop():
    return jsonify(get_capture_manager().stop() or {})


@tuning_blueprint.route("/tuning/capture/draft", methods=["POST"])
def capture_draft():
    body = request.get_json(silent=True) or {}
    device_type = body.get("type") if isinstance(body, dict) else None
    if not device_type:
        return _error(TuningError("missing device type"))
    try:
        return jsonify(get_capture_manager().build_draft(str(device_type)))
    except ValueError as error:
        return _error(TuningError(str(error)))


@tuning_blueprint.route("/tuning/audit", methods=["GET"])
def audit():
    try:
        limit = int(request.args.get("limit", "200"))
    except ValueError:
        limit = 200
    return jsonify(get_tuning_store().audit_entries(
        limit=limit, profile_id=request.args.get("profile_id"),
        device_uuid=request.args.get("device_uuid")))
