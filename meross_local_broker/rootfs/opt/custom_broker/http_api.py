# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
# Upstream: https://github.com/albertogeniola/ha-meross-local-broker (Apache-2.0).
import logging
from os import getenv

from flask import Flask
from flask_cors import CORS
from meross_iot.http_api import ErrorCodes
from meross_iot.model.http.exception import HttpApiError
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from blueprints.admin import admin_blueprint
from blueprints.auth import auth_blueprint
from blueprints.log import log_blueprint
from blueprints.device import device_blueprint
from blueprints.devs import devs_blueprint
from blueprints.hub import hub_blueprint
from blueprints.profile import profile_blueprint
from database import db_session, init_db
from logger import get_logger
from messaging import make_api_response
from model.exception import BadRequestError, RateLimitError, TokenError

# _LOGOUT_URL = "/v1/Profile/logout"

# Configure the current logger
_LOGGER = get_logger("http_api")

app = Flask(__name__)
# nginx terminates TLS and forwards the original scheme so that request.scheme
# and the login response domain stay https on the 2004 listener.
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1)


class _AclRequestFilter(logging.Filter):
    """Drop per-request ACL log lines; denials are logged with details."""

    def filter(self, record):
        return "/_devs_/acl" not in record.getMessage()


logging.getLogger("werkzeug").addFilter(_AclRequestFilter())

# The web UI is served same-origin through Home Assistant ingress, so CORS is
# off by default. Native clients do not need it either. Set
# CORS_ALLOWED_ORIGINS=origin1,origin2 only for a deliberate cross-origin use.
_cors_origins = [
    origin.strip()
    for origin in getenv("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
if _cors_origins:
    CORS(app, resources={r"/*": {"origins": _cors_origins}})

# Register flask blueprints
app.register_blueprint(auth_blueprint, url_prefix="/v1/Auth")
app.register_blueprint(log_blueprint, url_prefix="/v1/log")
app.register_blueprint(profile_blueprint, url_prefix="/v1/Profile")
app.register_blueprint(device_blueprint, url_prefix="/v1/Device")
app.register_blueprint(hub_blueprint, url_prefix='/v1/Hub')
app.register_blueprint(devs_blueprint, url_prefix="/_devs_")
app.register_blueprint(admin_blueprint, url_prefix="/_admin_")

# Initialize DB
init_db()


@app.teardown_appcontext
def shutdown_session(exception=None):
    """Handles shutdown"""
    db_session.remove()


@app.errorhandler(HTTPException)
def handle_http_status_exception(e):
    """Return Flask HTTP errors (404, 405, ...) without an HTML body."""
    return make_api_response(data=None, info=e.name, api_status=ErrorCodes.CODE_GENERIC_ERROR, status_code=e.code)


@app.errorhandler(Exception)
def handle_exception(e):
    """Uncaught Exception handler"""
    _LOGGER.exception("Uncaught exception")
    return make_api_response(data=None, info="Internal server error", api_status=ErrorCodes.CODE_GENERIC_ERROR,
                             status_code=500)


@app.errorhandler(BadRequestError)
def handle_bad_exception(e):
    """Bad Request handler"""
    _LOGGER.warning("BadRequest error: %s", e.msg)
    return make_api_response(data=None, info=e.msg, api_status=ErrorCodes.CODE_GENERIC_ERROR, status_code=400)


@app.errorhandler(TokenError)
def handle_token_error(e):
    """Expired or invalid session token: clients must log in again.

    meross_iot (used by the HA integration) raises before reading the body on
    any non-200 response, so the Meross status code stays HTTP 200 to keep the
    re-authentication flow working. The distinct reason is exposed in `info`.
    """
    return make_api_response(data=None, info=e.info,
                             api_status=ErrorCodes.CODE_TOKEN_ERROR,
                             status_code=200)


@app.errorhandler(RateLimitError)
def handle_rate_limit_error(e):
    """Too many failed login attempts."""
    response, status = make_api_response(data=None, info="Too many login attempts",
                                         api_status=ErrorCodes.CODE_GENERIC_ERROR,
                                         status_code=429)
    response.headers["Retry-After"] = str(e.retry_after)
    return response, status


@app.errorhandler(HttpApiError)
def handle_http_exception(e):
    """HTTP API exception handler"""
    _LOGGER.error("HttpApiError: %s", e.error_code.name)
    return make_api_response(data=None, info=e.error_code.name, api_status=e.error_code)
