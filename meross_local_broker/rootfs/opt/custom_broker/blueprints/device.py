# Modified for the MRS100 fork of ha-meross-local-broker (2026-11-13).
# Upstream: https://github.com/albertogeniola/ha-meross-local-broker
# Licensed under the Apache License, Version 2.0. See NOTICE.
# Modifications copyright 2026 the MRS100 fork contributors.

from logger import get_logger
from typing import Dict
import json
from flask import Blueprint, g
from decorator import meross_http_api
from messaging import make_api_response
from model.db_models import Device
from model.exception import BadRequestError
from db_helper import dbhelper

device_blueprint = Blueprint('device', __name__)
_LOGGER = get_logger(__name__)


def _json_or_none(value):
    try:
        return json.loads(value)
    except Exception:
        return None


def serialize_device_metadata(device):
    """Attach ability and roller-shutter metadata to a serialized device.

    Extra keys are ignored by the stock app and by meross_iot's HttpDeviceInfo
    parser (which accepts **kwargs), but they make the local API useful to the
    clone and to diagnostics tooling.
    """
    item = device.serialize()
    ability = dbhelper.get_device_ability(device.uuid)
    if ability is not None:
        parsed = _json_or_none(ability.ability_json)
        if parsed is not None:
            item['ability'] = parsed

    configs = dbhelper.get_roller_shutter_configs(device.uuid)
    statuses = dbhelper.get_roller_shutter_statuses(device.uuid)
    adjusts = dbhelper.get_roller_shutter_adjusts(device.uuid)
    if configs or statuses or adjusts:
        item['rollerShutter'] = {
            'config': [_json_or_none(c.payload_json) for c in configs],
            'position': [{'channel': p.channel, 'position': p.position,
                          'state': p.state} for p in statuses],
            'adjust': [_json_or_none(a.payload_json) for a in adjusts],
        }
    return item


@device_blueprint.route('/devList', methods=['POST'])
@meross_http_api(login_required=True)
def list_devices(api_payload: Dict, *args, **kwargs):
    user = g.user
    _LOGGER.debug("User %s requested deviceList", user)
    data = [serialize_device_metadata(d) for d in user.owned_devices]
    return make_api_response(data=data)


@device_blueprint.route('/delete', methods=['POST'])
@meross_http_api(login_required=True)
def delete_device(api_payload: Dict, *args, **kwargs):
    """Forget a device owned by the authenticated local account."""
    user = g.user
    device_uuid = api_payload.get('uuid')
    if not device_uuid:
        raise BadRequestError("Missing device uuid")
    device = dbhelper.get_device_by_uuid(device_uuid)
    if device is None or str(device.user_id) != str(user.user_id):
        raise BadRequestError("Device not found for this account")
    device_mac = device.mac
    dbhelper.revoke_device(device_mac)
    if not dbhelper.delete_device(device_uuid):
        raise BadRequestError("Device could not be deleted")
    _LOGGER.info("User %s forgot device %s (%s)", user, device_uuid, device_mac)
    return make_api_response(data={'uuid': device_uuid, 'deleted': True})


@device_blueprint.route('/name', methods=['POST'])
@meross_http_api(login_required=True)
def rename_device(api_payload: Dict, *args, **kwargs):
    """Set the broker-side display name of an owned device."""
    user = g.user
    device_uuid = api_payload.get('uuid')
    name = api_payload.get('name')
    if not device_uuid:
        raise BadRequestError("Missing device uuid")
    if name is None:
        raise BadRequestError("Missing device name")
    name = str(name).strip()
    if not name:
        raise BadRequestError("Device name cannot be empty")
    if len(name) > 128:
        raise BadRequestError("Device name must be at most 128 characters")
    device = dbhelper.get_device_by_uuid(device_uuid)
    if device is None or str(device.user_id) != str(user.user_id):
        raise BadRequestError("Device not found for this account")
    if dbhelper.is_device_name_used(name, exclude_uuid=device_uuid):
        raise BadRequestError("Device name is already used")
    device.dev_name = name
    dbhelper.update_device(device)
    _LOGGER.info("User %s renamed device %s to %s", user, device_uuid, name)
    return make_api_response(data={'uuid': device_uuid, 'name': name})


@device_blueprint.route('/claim', methods=['POST'])
@meross_http_api(login_required=True)
def claim_device(api_payload: Dict, *args, **kwargs):
    """Clear a revocation after the device has been paired again."""
    mac = api_payload.get('mac')
    if not mac:
        raise BadRequestError("Missing device mac")
    dbhelper.clear_device_revocation(mac)
    _LOGGER.info("User %s re-claimed device %s", g.user, mac)
    return make_api_response(data={'mac': mac, 'claimed': True})
