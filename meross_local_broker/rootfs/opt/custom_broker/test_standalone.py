# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
"""Tests for the standalone (HA Container) helpers.

Run with: python3 -m unittest test_standalone
"""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

BASHUTILS = Path(__file__).resolve().parent.parent / "utils" / "bashutils.sh"


def _run(script: str, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "-c", f'source "$0"; {script}', str(BASHUTILS)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _clean_env() -> dict:
    env = dict(os.environ)
    for key in ("SUPERVISOR_TOKEN", "HASSIO_TOKEN", "MEROSS_STANDALONE",
                "CONFIG_PATH", "advertise", "debug_mode"):
        env.pop(key, None)
    return env


class StandaloneDetectionTest(unittest.TestCase):
    def test_supervisor_token_means_addon(self):
        env = _clean_env()
        env["SUPERVISOR_TOKEN"] = "token"
        result = _run('is_standalone; printf "%s" "$?"', env)
        self.assertEqual(result.stdout, "1")

    def test_no_token_means_standalone(self):
        result = _run('is_standalone; printf "%s" "$?"', _clean_env())
        self.assertEqual(result.stdout, "0")

    def test_explicit_override(self):
        env = _clean_env()
        env["SUPERVISOR_TOKEN"] = "token"
        env["MEROSS_STANDALONE"] = "1"
        result = _run('is_standalone; printf "%s" "$?"', env)
        self.assertEqual(result.stdout, "0")


class GetOptionTest(unittest.TestCase):
    def test_environment_is_used_without_file(self):
        env = _clean_env()
        env["advertise"] = "true"
        env["CONFIG_PATH"] = "/nonexistent/options.json"
        result = _run('get_option advertise false', env)
        self.assertEqual(result.stdout.strip(), "true")

    def test_file_wins_over_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "options.json"
            path.write_text(json.dumps({"advertise": False}))
            env = _clean_env()
            env["advertise"] = "true"
            env["CONFIG_PATH"] = str(path)
            result = _run('get_option advertise true', env)
            self.assertEqual(result.stdout.strip(), "false")

    def test_default_value(self):
        env = _clean_env()
        env["CONFIG_PATH"] = "/nonexistent/options.json"
        result = _run('get_option mqtt_integrity_mode observe', env)
        self.assertEqual(result.stdout.strip(), "observe")


if __name__ == "__main__":
    unittest.main()
