# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
"""Tests for profile catalog signing.

Run with: python3 -m unittest test_profile_signing
"""

import base64
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import profile_signing
from profiles import ProfileCatalog, _canonical

HERE = Path(__file__).parent
PROFILES = HERE / "device_profiles"


class ProfileSigningTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.key = str(Path(self.temporary.name) / "signing.key")
        self.pub = str(Path(self.temporary.name) / "signing.pub")
        patcher = patch.multiple(
            profile_signing, KEY_PATH=self.key, PUB_PATH=self.pub)
        patcher.start()
        self.addCleanup(patcher.stop)

    def verify(self, data: bytes, signature: str) -> None:
        data_path = Path(self.temporary.name) / "data.bin"
        sig_path = Path(self.temporary.name) / "sig.bin"
        data_path.write_bytes(data)
        sig_path.write_bytes(base64.b64decode(signature))
        subprocess.run(
            ["openssl", "pkeyutl", "-verify", "-rawin", "-pubin",
             "-inkey", self.pub, "-sigfile", str(sig_path),
             "-in", str(data_path)],
            check=True, capture_output=True)

    def test_keypair_and_signature(self):
        self.assertTrue(profile_signing.ensure_keypair())
        data = b"profile catalog"
        signature = profile_signing.sign(data)

        self.assertIsNotNone(signature)
        self.verify(data, signature)
        self.assertTrue(profile_signing.public_key_pem().startswith(
            "-----BEGIN PUBLIC KEY-----"))
        self.assertIsNotNone(profile_signing.public_key_fingerprint())

    def test_tampered_data_does_not_verify(self):
        signature = profile_signing.sign(b"original")
        tampered = base64.b64decode(signature)
        data_path = Path(self.temporary.name) / "data.bin"
        sig_path = Path(self.temporary.name) / "sig.bin"
        data_path.write_bytes(b"changed")
        sig_path.write_bytes(tampered)

        result = subprocess.run(
            ["openssl", "pkeyutl", "-verify", "-rawin", "-pubin",
             "-inkey", self.pub, "-sigfile", str(sig_path),
             "-in", str(data_path)],
            capture_output=True)

        self.assertNotEqual(result.returncode, 0)

    def test_missing_directory_disables_signing(self):
        missing = str(Path(self.temporary.name) / "missing" / "key")

        self.assertFalse(profile_signing.ensure_keypair(
            key_path=missing, pub_path=missing + ".pub"))
        self.assertIsNone(profile_signing.sign(
            b"data", key_path=missing, pub_path=missing + ".pub"))

    def test_catalog_payload_carries_a_valid_signature(self):
        catalog = ProfileCatalog(str(PROFILES), "")
        payload = catalog.payload()

        self.assertEqual(payload["algorithm"], "ed25519")
        body = {key: value for key, value in payload.items()
                if key not in ("signature", "algorithm")}
        self.verify(_canonical(body), payload["signature"])


if __name__ == "__main__":
    unittest.main()
