from logger import get_logger
import re
from hashlib import sha256, md5

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError


_LOGGER = get_logger(__name__)
_PASSWORD_HASHER = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
ARGON2_PREFIX = "$argon2"


camel_pat = re.compile(r'([A-Z])')
under_pat = re.compile(r'_([a-z])')


def _camel_to_underscore(key):
    return camel_pat.sub(lambda x: '_' + x.group(1).lower(), key)


def _underscore_to_camel(key):
    return under_pat.sub(lambda x: x.group(1).upper(), key)


def hash_token(token: str) -> str:
    """Returns the stable SHA-256 digest stored in place of a session token."""
    return sha256(token.encode("utf8")).hexdigest()


def is_argon2_hash(value: str) -> bool:
    return isinstance(value, str) and value.startswith(ARGON2_PREFIX)


def hash_password(password: str) -> str:
    """Hashes the effective account secret with Argon2id."""
    return _PASSWORD_HASHER.hash(password)


def verify_password(stored_hash: str, password: str) -> bool:
    """Verifies an Argon2id hash; returns False for any malformed input."""
    if not is_argon2_hash(stored_hash) or not isinstance(password, str):
        return False
    try:
        return _PASSWORD_HASHER.verify(stored_hash, password)
    except (VerificationError, ValueError, TypeError):
        return False


def _hash_password(salt: str, password: str, pre_apply_md5=False) -> str:
    pwd = md5(password.encode("utf8")).hexdigest() if pre_apply_md5 else password
    # Get the salt, compute the hashed password and compare it with the one stored in the db
    clearsaltedpwd = f"{salt}{pwd}"
    hashed_pass = sha256()
    hashed_pass.update(clearsaltedpwd.encode('utf8'))
    computed_hashed_password = hashed_pass.hexdigest()

    return computed_hashed_password