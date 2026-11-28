# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
# Upstream: https://github.com/albertogeniola/ha-meross-local-broker (Apache-2.0).
"""Flask blueprint for device-specific API"""
import hmac
import re
from hashlib import md5
from typing import Tuple

from authentication import _upgrade_password_if_legacy, verify_account_password
from db_helper import dbhelper
from expiringdict import ExpiringDict
from flask import Blueprint, request
from logger import get_logger
from compat import OnlineStatus
from model.enums import EventType
from rate_limit import LoginRateLimiter


devs_blueprint = Blueprint('_devs', __name__)
_LOGGER = get_logger(__name__)
_DEV_PASSWORD_RE = re.compile("^([0-9]+)_([a-zA-Z0-9]+)$")
_CLIENTID_DEVICE_OR_APP_RE = re.compile(
    '^(fmware|app):([a-zA-Z0-9]+)(_([a-zA-Z0-9]+))?$')

_AGENT_USERNAME = "_agent"
_AGENT_READ_TOPICS = {
    '/appliance/+/publish',
    '/appliance/+/subscribe',
    '/_nat_/#',
    '/_agent',
    '$SYS/client-disconnections',
}
# Subscription checks use the wildcard filters, but message delivery is checked
# against the concrete topic.
_APPLIANCE_DELIVERY_RE = re.compile(
    r'^/appliance/[A-Za-z0-9]+/(publish|subscribe)$')
_NAT_DELIVERY_RE = re.compile(r'^/_nat_/[A-Za-z0-9-]+$')
_ACL_DENIAL_LOG = ExpiringDict(max_age_seconds=300, max_len=5000)
# MQTT authentication is called by Mosquitto from loopback, so the generic
# login limiter's IP bucket would block every account at once. Use a dedicated
# limiter keyed by the account and keep the broker's existing thresholds.
mqtt_login_rate_limiter = LoginRateLimiter()


def _mqtt_rate_limit_account(account: str) -> str:
    return f"mqtt:{account}"


def _mqtt_rate_limit_check(account: str) -> bool:
    retry_after = mqtt_login_rate_limiter.check(
        _mqtt_rate_limit_account(account), account)
    if retry_after is not None:
        _LOGGER.warning(
            "LOGIN_CHECK=> MQTT authentication for %s is rate limited for %s s",
            account, retry_after)
        return False
    return True


def _mqtt_rate_limit_failure(account: str) -> None:
    mqtt_login_rate_limiter.record_failure(
        _mqtt_rate_limit_account(account), account)


def _mqtt_rate_limit_success(account: str) -> None:
    mqtt_login_rate_limiter.clear(_mqtt_rate_limit_account(account), account)


def _accepted_topics(acc: int):
    # 1 = read, 2 = write, 4 = subscribe, 8 = unsubscribe. Unsubscribing does
    # not expose data, so it follows the read policy.
    can_read = bool(acc & 1) or bool(acc & 4) or bool(acc & 8)
    can_write = bool(acc & 2)
    return can_read, can_write


def _agent_topic_allowed(topic: str, can_read: bool, can_write: bool) -> bool:
    if can_read and (
            topic in _AGENT_READ_TOPICS
            or _APPLIANCE_DELIVERY_RE.fullmatch(topic)
            or _NAT_DELIVERY_RE.fullmatch(topic)):
        return True
    if can_write:
        if topic == '/_agent' or topic.startswith('/_nat_/'):
            return True
        if topic.startswith('/appliance/') and (
                topic.endswith('/subscribe') or topic.endswith('/publish')):
            return True
        if topic.startswith('/app/') and topic.endswith('/subscribe'):
            return True
    return False


def _device_topic_allowed(username: str, clientid: str, topic: str,
                          can_read: bool, can_write: bool) -> bool:
    match = _CLIENTID_DEVICE_OR_APP_RE.fullmatch(clientid or '')
    if match is None or match.group(1) != 'fmware':
        return False
    device_uuid = match.group(2)
    device = dbhelper.get_device_by_mac(username)
    if device is None or device.uuid != device_uuid:
        return False
    if can_read and topic == f'/appliance/{device_uuid}/subscribe':
        return True
    if can_write:
        if topic in (f'/appliance/{device_uuid}/publish', '/_agent'):
            return True
        # Devices answer commands on the app response topic carried in the
        # request "from" header. Restrict that write to the owner's topics.
        owner_prefix = f'/app/{device.user_id}'
        if topic == f'{owner_prefix}/subscribe':
            return True
        if topic.startswith(f'{owner_prefix}-') and topic.endswith('/subscribe'):
            return True
    return False


def _resolve_app_user(username: str):
    user = dbhelper.get_user_by_email(username)
    if user is not None:
        return user
    try:
        return dbhelper.get_user_by_id(int(username))
    except (TypeError, ValueError):
        return None


def _app_topic_allowed(user, topic: str, can_read: bool, can_write: bool) -> bool:
    user_topic_prefix = f'/app/{user.user_id}'
    if can_read and (
            topic == f'{user_topic_prefix}/subscribe'
            or (topic.startswith(f'{user_topic_prefix}-')
                and topic.endswith('/subscribe'))):
        return True
    if can_write and topic.startswith('/appliance/') and topic.endswith('/subscribe'):
        device_uuid = topic[len('/appliance/'):-len('/subscribe')]
        device = dbhelper.get_device_by_uuid(device_uuid)
        return device is not None and str(device.user_id) == str(user.user_id)
    return False


@devs_blueprint.route('/acl', methods=['POST'])
def device_acl():
    """Endpoint called by the MQTT broker plugin to verify ACLs."""
    content = request.get_json(silent=True)
    if not isinstance(content, dict):
        return "ko", 403

    username = content.get('username')
    topic = content.get('topic')
    acc = content.get('acc')
    clientid = content.get('clientid')

    try:
        acc = int(acc)
    except (TypeError, ValueError):
        return "ko", 403
    if not username or not isinstance(topic, str):
        return "ko", 403

    can_read, can_write = _accepted_topics(acc)
    allowed = False
    if username == _AGENT_USERNAME:
        allowed = _agent_topic_allowed(topic, can_read, can_write)
    elif (clientid or '').startswith('fmware:'):
        allowed = _device_topic_allowed(username, clientid, topic, can_read, can_write)
    elif (clientid or '').startswith('app:'):
        user = _resolve_app_user(username)
        allowed = user is not None and _app_topic_allowed(user, topic, can_read, can_write)
    else:
        user = _resolve_app_user(username)
        allowed = user is not None and _app_topic_allowed(user, topic, can_read, can_write)

    if allowed:
        _LOGGER.debug("DEVICE_ACL=> allowed username=%s topic=%s acc=%s clientid=%s",
                      str(username), str(topic), str(acc), str(clientid))
        return "ok", 200

    denial_key = f"{username}|{clientid}|{acc}|{topic}"
    if denial_key not in _ACL_DENIAL_LOG:
        _ACL_DENIAL_LOG[denial_key] = True
        _LOGGER.warning(
            "DEVICE_ACL denied username=%s clientid=%s topic=%s acc=%s",
            str(username), str(clientid), str(topic), str(acc))
    else:
        _LOGGER.debug("DEVICE_ACL=> denied username=%s topic=%s acc=%s clientid=%s",
                      str(username), str(topic), str(acc), str(clientid))
    return "ko", 403


@devs_blueprint.route('/superuser', methods=['POST'])
def superuser_acl():
    """Endpoint called by the MQTT broker plugin to verify ACLS for super-users"""
    # TODO: add logging and implement super-user logic
    # For now, just return 403: no one can connect as super-user.
    return "ko", 403


@devs_blueprint.route('/auth', methods=['POST'])
def device_login():
    """Endpoint called by the MQTT broker plugin to authenticate devices."""
    # Keep broker authentication failures as explicit denials, including
    # non-JSON requests which Flask 3 would otherwise reject with 415.
    content = request.get_json(silent=True)

    if not isinstance(content, dict):
        _LOGGER.error(
            "DEVICE_AUTH=> Expected JSON body has not been received.")
        dbhelper.store_event(event_type=EventType.CONNECT_FAILURE, details=f"Invalid connection attempted from {str(request.remote_addr)}")
        return "ko", 403

    username = content.get('username')
    password = content.get('password')
    topic = content.get('topic')
    acc = content.get('acc')
    clientid = content.get('clientid')

    _LOGGER.debug("LOGIN_CHECK=> username: %s, clientid: %s, topic: %s, acc: %s", str(
        username), str(clientid), str(topic), str(acc))

    # Differentiate login based on clientid
    clientid_match = _CLIENTID_DEVICE_OR_APP_RE.fullmatch(clientid)
    if clientid_match is None:
        _LOGGER.debug(
            "LOGIN_CHECK=> clientid (%s) does not belong to app/device: performing custom login.", str(clientid))
        res = _custom_login(email=username, password=password)
        return res

    login_type = clientid_match.group(1)
    if login_type == "fmware":
        # Device authentication basically is basically a "binding" to a given user id
        # Username => device mac addresss
        # Password => userid_md5(mac+key)
        # Clientid: fmware:deviceuuid_<?>
        _LOGGER.debug(
            "LOGIN_CHECK=> recognized device clientid format (clientid: %s). Logging-in as device.", str(clientid))
        pwd_match = _DEV_PASSWORD_RE.match(password)
        if pwd_match is None:
            _LOGGER.error(
                "LOGIN_CHECK=> Provided device password does not comply with expected format for device with clientid: %s.", str(clientid))
            return "ko", 400
        mac = username
        user_id = pwd_match.group(1)
        md5hash = pwd_match.group(2)
        device_uuid = clientid_match.group(2)
        res = _device_login(mac=mac, user_id=user_id,
                            device_uuid=device_uuid, md5hash=md5hash, clientid=clientid)
        return res

    elif login_type == "app":
        _LOGGER.debug(
            "LOGIN_CHECK=> recognized app clientid format (clientid: %s). Logging-in as app.", str(clientid))
        res = _app_login(user_id=username, md5hash=password)
        return res
    else:
        _LOGGER.error(
            "LOGIN_CHECK=> Invalid/unsupported client type derived from client id.")
        return "ko", 400


def _custom_login(email: str, password: str):
    # Skip login for AGENT as it will use another login option
    if email == "_agent":
        _LOGGER.debug("LOGIN_CHECK(custom)=> User \"%s\": skipping login via API, as it will use sql login logic.", email)
        dbhelper.store_event(event_type=EventType.AGENT_LOGIN_ATTEMPTED, details=f"Agent has tried to login to this API from {str(request.remote_addr)}. Atempt will be ignored.")
        return "ko", 401

    if not _mqtt_rate_limit_check(email):
        return "ko", 403

    # Lookup user email by the given username.
    user = dbhelper.get_user_by_email(email=email)
    if user is None:
        _mqtt_rate_limit_failure(email)
        _LOGGER.error(
            "LOGIN_CHECK(custom)=> User \"%s\" does not exist.", email)
        dbhelper.store_event(event_type=EventType.USER_LOGIN_FAILURE, details=f"Custom login from {str(request.remote_addr)} failed: username {email} does not exist.")
        return "ko", 401

    if not isinstance(password, str) or not password:
        return "ko", 400

    if verify_account_password(user, password):
        _upgrade_password_if_legacy(user, password)
        _mqtt_rate_limit_success(email)
        _LOGGER.info(
            "LOGIN_CHECK(custom)=> User login attempt succeeded UserId: %s", email)
        dbhelper.store_event(event_type=EventType.USER_LOGIN_SUCCESS, user_id=user.user_id, details=f"Custom login from {str(request.remote_addr)} succeeded.")
        return "ok", 200
    else:
        _mqtt_rate_limit_failure(email)
        _LOGGER.warning(
            "LOGIN_CHECK(custom)=> User login attempt failed (UserId %s)", email)
        dbhelper.store_event(event_type=EventType.USER_LOGIN_FAILURE, details=f"Custom login from {str(request.remote_addr)} with email {email} failed: wrong credentials.")
        return "ko", 403


def _app_login(user_id: str, md5hash: str) -> Tuple[str, int]:
    account = f"app:{user_id}"
    if not _mqtt_rate_limit_check(account):
        return "ko", 403
    try:
        userid = int(user_id)
    except ValueError:
        _mqtt_rate_limit_failure(account)
        _LOGGER.error("LOGIN_CHECK(app)=> UserId \"%s\" is invalid.", str(user_id))
        dbhelper.store_event(event_type=EventType.USER_LOGIN_FAILURE, user_id=user_id, details=f"App login from {str(request.remote_addr)} with user_id {str(user_id)} failed: invalid user_id, it should be numerical.")
        return "ko", 400

    # Lookup key by the given username.
    user = dbhelper.get_user_by_id(userid=userid)
    if user is None:
        _mqtt_rate_limit_failure(account)
        _LOGGER.error(
            "LOGIN_CHECK(app)=> User with ID \"%s\" does not exist.", str(userid))
        dbhelper.store_event(event_type=EventType.USER_LOGIN_FAILURE, user_id=user_id, details=f"App login from {str(request.remote_addr)} with user_id {str(user_id)} failed: user id does not exist.")
        return "ko", 401

    if not isinstance(md5hash, str):
        return "ko", 400

    # Calculate the expected hash: MD5(<userid><mqtt_key>).hex()
    expected_md5hash = md5()
    expected_md5hash.update(f"{user_id}{user.mqtt_key}".encode())
    expected_digest = expected_md5hash.hexdigest()

    if hmac.compare_digest(expected_digest, md5hash):
        _mqtt_rate_limit_success(account)
        _LOGGER.info(
            "LOGIN_CHECK(app)=> App login attempt succeeded UserId: %s", str(userid))
        dbhelper.store_event(event_type=EventType.USER_LOGIN_SUCCESS, user_id=user_id, details=f"App login from {str(request.remote_addr)} with user_id {str(user_id)} succeeded.")
        return "ok", 200
    else:
        _mqtt_rate_limit_failure(account)
        _LOGGER.warning(
            "LOGIN_CHECK(app)=> App login attempt failed (UserId %s)", str(userid))
        dbhelper.store_event(event_type=EventType.USER_LOGIN_FAILURE, user_id=user_id, details=f"App login from {str(request.remote_addr)} with user_id {str(user_id)} failed: invalid user/password combination.")
        return "ko", 403


def _device_login(mac: str, user_id: str, device_uuid: str, md5hash: str, clientid: str) -> Tuple[str, int]:
    account = f"device:{mac}"
    if not _mqtt_rate_limit_check(account):
        return "ko", 403
    try:
        userid = int(user_id)
    except ValueError:
        _mqtt_rate_limit_failure(account)
        _LOGGER.error(
            "LOGIN_CHECK(device)=> UserId \"%s\" is invalid.", str(user_id))
        dbhelper.store_event(event_type=EventType.DEVICE_CONNECT_FAILURE, user_id=user_id, details=f"Device {device_uuid} ({str(request.remote_addr)}) failed authentication: invalid user_id specified.")
        return "ko", 400

    if dbhelper.is_device_revoked(mac):
        _LOGGER.info("LOGIN_CHECK(device)=> Device %s is revoked until paired again.", mac)
        dbhelper.store_event(
            event_type=EventType.DEVICE_CONNECT_FAILURE, user_id=user_id,
            details=f"Device {device_uuid} ({str(request.remote_addr)}) is revoked.")
        return "ko", 403

    # Lookup key by the given username.
    user = dbhelper.get_user_by_id(userid=userid)
    if user is None:
        _mqtt_rate_limit_failure(account)
        _LOGGER.error(
            "LOGIN_CHECK(device)=> User with ID \"%s\" does not exist.", str(userid))
        dbhelper.store_event(event_type=EventType.DEVICE_CONNECT_FAILURE, user_id=user_id, details=f"Device {device_uuid} ({str(request.remote_addr)}) failed authentication: provided user_id {str(user_id)} does not exist.")
        return "ko", 401

    expected_md5hash = md5()
    expected_md5hash.update(f"{mac}{user.mqtt_key}".encode())
    expected_digest = expected_md5hash.hexdigest()

    if hmac.compare_digest(expected_digest, md5hash):
        _mqtt_rate_limit_success(account)
        dbhelper.associate_user_device(
            userid=userid, mac=mac, uuid=device_uuid, device_client_id=clientid)
        dbhelper.update_device_status(
            device_uuid=device_uuid, status=OnlineStatus.ONLINE)
        _LOGGER.info(
            "Device login attempt succeeded. Device with mac \"%s\" (uuid %s) has been associated to "
            "userid \"%s\"", str(mac), str(device_uuid), str(userid))
        dbhelper.store_event(event_type=EventType.DEVICE_CONNECT_SUCCESS, user_id=user_id, device_uuid=device_uuid, details=f"Device {device_uuid} ({str(request.remote_addr)}) successfully authenticated.")
        return "ok", 200
    else:
        _mqtt_rate_limit_failure(account)
        _LOGGER.warning(
            "Device login attempt failed (device with mac \"%s\", userid \"%s\")", str(mac), str(userid))
        dbhelper.store_event(event_type=EventType.DEVICE_CONNECT_FAILURE, user_id=user_id, device_uuid=device_uuid, details=f"Device {device_uuid} ({str(request.remote_addr)}) failed authentication.")
        return "ko", 403
