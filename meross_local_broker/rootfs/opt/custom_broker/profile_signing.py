# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
# Upstream: https://github.com/albertogeniola/ha-meross-local-broker (Apache-2.0)
"""Ed25519 signing for the served profile catalog.

The key pair is generated on first use with the openssl binary already used
for the TLS material. A signing failure never prevents the broker from
starting: the catalog is then served without a signature and the integration
reports it as unsigned.
"""
from __future__ import annotations

import base64
import hashlib
import os
import subprocess
import tempfile
from typing import Optional

from logger import get_logger

_LOG = get_logger(__name__)

KEY_PATH = "/data/profile_signing.key"
PUB_PATH = "/data/profile_signing.pub"
ALGORITHM = "ed25519"


def _run(args) -> subprocess.CompletedProcess:
    return subprocess.run(args, check=True, capture_output=True)


def ensure_keypair(key_path: Optional[str] = None,
                   pub_path: Optional[str] = None) -> bool:
    key_path = key_path or KEY_PATH
    pub_path = pub_path or PUB_PATH
    if os.path.exists(key_path) and os.path.exists(pub_path):
        return True
    directory = os.path.dirname(key_path) or "."
    if not os.path.isdir(directory):
        _LOG.debug("Signing key directory %s is missing", directory)
        return False
    try:
        _run(["openssl", "genpkey", "-algorithm", "ED25519",
              "-out", key_path])
        os.chmod(key_path, 0o600)
        _run(["openssl", "pkey", "-in", key_path,
              "-pubout", "-out", pub_path])
        os.chmod(pub_path, 0o644)
        _LOG.info("Generated profile signing key %s", key_path)
        return True
    except Exception as ex:  # noqa: BLE001 - signing is best effort
        _LOG.error("Unable to generate the profile signing key: %s", ex)
        return False


def public_key_pem(pub_path: Optional[str] = None) -> Optional[str]:
    pub_path = pub_path or PUB_PATH
    try:
        with open(pub_path, "r", encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return None


def public_key_fingerprint(pub_path: Optional[str] = None) -> Optional[str]:
    pem = public_key_pem(pub_path)
    return hashlib.sha256(pem.encode("utf-8")).hexdigest() if pem else None


def sign(data: bytes, key_path: Optional[str] = None,
         pub_path: Optional[str] = None) -> Optional[str]:
    """Return the base64 Ed25519 signature of data, or None if unavailable."""
    key_path = key_path or KEY_PATH
    pub_path = pub_path or PUB_PATH
    if not ensure_keypair(key_path, pub_path):
        return None
    path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False) as handle:
            handle.write(data)
            path = handle.name
        result = _run(["openssl", "pkeyutl", "-sign", "-rawin",
                       "-inkey", key_path, "-in", path])
        return base64.b64encode(result.stdout).decode("ascii")
    except Exception as ex:  # noqa: BLE001 - signing is best effort
        _LOG.error("Unable to sign the profile catalog: %s", ex)
        return None
    finally:
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass
