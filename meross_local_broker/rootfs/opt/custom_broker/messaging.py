# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
# Upstream: https://github.com/albertogeniola/ha-meross-local-broker (Apache-2.0).
from hashlib import md5
import hmac
from typing import Optional

from flask import jsonify
from meross_iot.http_api import ErrorCodes

from constants import _SECRET


def make_api_response(data: Optional[dict], api_status: ErrorCodes = ErrorCodes.CODE_NO_ERROR, info: str = None, status_code: int = 200):
    return jsonify({
        "apiStatus": api_status.value,
        "info": info,
        "data": data
    }), status_code


def verify_message_signature(signature: str, timestamp_millis, nonce, b64params: str):
    # Clients send the timestamp as a JSON number (pairer, meross_iot) or as a
    # string; the signature always uses its decimal representation.
    if not isinstance(signature, str):
        return False
    message_hash = md5()
    datatosign = '%s%s%s%s' % (_SECRET, timestamp_millis, nonce, b64params)
    message_hash.update(datatosign.encode("utf8"))
    md5hash = message_hash.hexdigest()
    try:
        return hmac.compare_digest(md5hash, signature)
    except TypeError:
        return False
