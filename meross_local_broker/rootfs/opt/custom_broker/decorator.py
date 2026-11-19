# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
# Upstream: https://github.com/albertogeniola/ha-meross-local-broker (Apache-2.0).
import base64
import binascii
import json

from logger import get_logger
import re
from functools import wraps

from flask import request, g

from authentication import verify_token
from messaging import verify_message_signature
from model.exception import BadRequestError, TokenError

TOKEN_EXTRACTOR = re.compile(r"Basic ([A-Za-z0-9_-]+)")
l = get_logger(__name__)


def meross_http_api(original_function=None, login_required=True):
    def _decorate(f):
        @wraps(f)
        def wrap(*args, **kwargs):
            # AUTH TOKEN VERIFICATION
            # If login_required is specified, we should check the Authorization header
            if login_required:
                auth_str = request.headers.get("Authorization")
                if auth_str is None:
                    raise TokenError("token_invalid")

                res = TOKEN_EXTRACTOR.fullmatch(auth_str)
                if not res:
                    raise TokenError("token_invalid")

                token = res.group(1)
                user, token_error = verify_token(token)
                if user is None:
                    raise TokenError(token_error or "token_invalid")

                l.debug("API user %s authenticated", user.user_id)

                g.user_token = token
                g.user = user

            # MEROSS HTTP API requires a valid json payload that contains the following
            # - params: json-encoded parameters
            # - sign: message signature
            # - timestamp
            # - nonce
            # Flask 3 raises 415 when reading JSON from a form request.
            # Meross clients support both signed JSON and form envelopes.
            if request.is_json:
                j = request.get_json()
                if not isinstance(j, dict):
                    raise BadRequestError("Missing or invalid payload")
                params = j.get('params')
                signature = j.get('sign')
                timestamp = j.get('timestamp')
                nonce = j.get('nonce')
            elif request.form is not None:
                params = request.form.get('params')
                signature = request.form.get('sign')
                timestamp = request.form.get('timestamp')
                nonce = request.form.get('nonce')
            else:
                raise BadRequestError("Missing or invalid payload")

            if params is None:
                raise BadRequestError("Empty params payload")
            if signature is None:
                raise BadRequestError("Missing signature")
            if timestamp is None:
                raise BadRequestError("Missing timestamp")
            if nonce is None:
                raise BadRequestError("Missing nonce")

            if not verify_message_signature(signature, timestamp, nonce, params):
                raise BadRequestError("Key verification failed")

            try:
                jsondata = base64.standard_b64decode(params)
                payload = json.loads(jsondata)
            except (ValueError, binascii.Error, UnicodeDecodeError):
                raise BadRequestError("Malformed params payload")
            if not isinstance(payload, dict):
                raise BadRequestError("Malformed params payload")

            return f(*args, **kwargs, api_payload=payload)
        return wrap

    if original_function:
        return _decorate(original_function)

    return _decorate
