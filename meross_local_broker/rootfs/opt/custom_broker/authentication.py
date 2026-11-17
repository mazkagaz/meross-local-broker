# Modified for the MRS100 fork of ha-meross-local-broker (2026-11-13).
# Upstream: https://github.com/albertogeniola/ha-meross-local-broker
# Licensed under the Apache License, Version 2.0. See NOTICE.
# Modifications copyright 2026 the MRS100 fork contributors.

from hashlib import md5, sha256
import hmac
import secrets
from typing import Tuple

from flask import has_request_context, request
from meross_iot.http_api import ErrorCodes
from meross_iot.model.http.exception import HttpApiError

from db_helper import dbhelper
from model.enums import EventType
from model.db_models import User
from model.exception import RateLimitError
from rate_limit import login_rate_limiter
from utilities import (_hash_password, hash_password, hash_token,
                       is_argon2_hash, verify_password)


def verify_token(token):
    """Returns (user, None) for a live session, or (None, reason)."""
    return dbhelper.get_user_by_token(token)


def _user_logout(token: str) -> None:
    user, _ = dbhelper.get_user_by_token(token=token)
    dbhelper.remove_user_token(token=token)
    if user is not None:
        dbhelper.store_event(
            EventType.USER_LOGOUT,
            details=f"User {user.email} has logged out.",
            user_id=user.user_id,
        )


def _client_ip() -> str:
    if not has_request_context():
        return "local"
    # Only nginx can reach the loopback API, and it overwrites this header.
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()[:64] or "unknown"
    return request.remote_addr or "unknown"


def _legacy_password_matches(user: User, effective_password: str) -> bool:
    standard = _hash_password(salt=user.salt, password=effective_password,
                              pre_apply_md5=False)
    if hmac.compare_digest(standard, user.password or ""):
        return True
    # alpha56 (and earlier) created double-hashed passwords through the admin panel.
    double = sha256(
        f"{user.salt}{md5(effective_password.encode('utf8')).hexdigest()}".encode("utf8")
    ).hexdigest()
    return hmac.compare_digest(double, user.password or "")


def verify_account_password(user: User, effective_password: str) -> bool:
    """Verifies the effective secret (clear or its MD5) against the stored hash."""
    if is_argon2_hash(user.password):
        return verify_password(user.password, effective_password)
    return _legacy_password_matches(user, effective_password)


def _upgrade_password_if_legacy(user: User, effective_password: str) -> None:
    if is_argon2_hash(user.password):
        return
    dbhelper.set_user_password_hash(user, hash_password(effective_password))
    dbhelper.store_event(
        EventType.USER_PASSWORD_UPGRADE,
        details=f"User's password has been upgraded for {user.email}.",
    )


def _attempt_password_upgrade(email, password) -> bool:
    # Older HA clients may still send an effective (pre-MD5) password.
    user = dbhelper.get_user_by_email(email=email)
    if user is None:
        dbhelper.store_event(
            EventType.USER_LOGIN_FAILURE,
            details=f"User {email} has failed to log in via Meross Local API: wrong or unexisting email specified.",
        )
        return False
    if not _legacy_password_matches(user, password):
        return False
    _upgrade_password_if_legacy(user, password)
    return True


def _user_login(email: str, password: str,
                providing_pre_hashed_password: bool) -> Tuple[User, str]:
    ip = _client_ip()
    retry_after = login_rate_limiter.check(ip, email)
    if retry_after is not None:
        raise RateLimitError(retry_after)

    if not isinstance(password, str) or not password:
        raise HttpApiError(ErrorCodes.CODE_WRONG_CREDENTIALS)

    # email, userid, salt, password, mqtt_key
    user = dbhelper.get_user_by_email(email=email)
    if user is None:
        login_rate_limiter.record_failure(ip, email)
        dbhelper.store_event(
            EventType.USER_LOGIN_FAILURE,
            details=f"User {email} has failed to log in via Meross Local API: wrong or unexisting email specified.",
        )
        raise HttpApiError(ErrorCodes.CODE_UNEXISTING_ACCOUNT)

    # Both API modes reduce to the same effective secret: the client's MD5.
    effective_password = (password if providing_pre_hashed_password
                          else md5(password.encode("utf8")).hexdigest())

    if not verify_account_password(user, effective_password):
        login_rate_limiter.record_failure(ip, email)
        dbhelper.store_event(
            EventType.USER_LOGIN_FAILURE,
            details=f"User {email} has failed to log in via Meross Local API: wrong password.",
        )
        raise HttpApiError(ErrorCodes.CODE_WRONG_CREDENTIALS)

    _upgrade_password_if_legacy(user, effective_password)
    login_rate_limiter.clear(ip, email)

    token = secrets.token_urlsafe(32)
    dbhelper.store_new_user_token(user.user_id, hash_token(token))
    dbhelper.store_event(
        EventType.USER_LOGIN_SUCCESS,
        details=f"User {email} has successfully logged in via Meross Local API.",
    )
    return user, token
