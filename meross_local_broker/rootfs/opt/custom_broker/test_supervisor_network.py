"""Tests for the Supervisor LAN address selection. Run with python3 -m unittest."""

import unittest

from supervisor_network import lan_ipv4_addresses


class SupervisorNetworkTest(unittest.TestCase):
    def test_primary_interface_comes_first(self):
        payload = {
            "data": {
                "interfaces": [
                    {"interface": "wlan0", "enabled": True, "connected": True,
                     "ipv4": {"address": ["192.168.1.20/24"]}},
                    {"interface": "eth0", "enabled": True, "connected": True,
                     "primary": True,
                     "ipv4": {"address": ["192.168.1.10/24"]}},
                ]
            }
        }
        self.assertEqual(["192.168.1.10", "192.168.1.20"],
                         lan_ipv4_addresses(payload))

    def test_skips_loopback_bridges_and_disconnected_interfaces(self):
        payload = {
            "data": {
                "interfaces": [
                    {"interface": "lo", "ipv4": {"address": ["127.0.0.1/8"]}},
                    {"interface": "hassio", "ipv4": {"address": ["172.30.32.1/23"]}},
                    {"interface": "docker0", "ipv4": {"address": ["172.17.0.1/16"]}},
                    {"interface": "eth1", "connected": False,
                     "ipv4": {"address": ["192.168.1.30/24"]}},
                    {"interface": "wlan0", "enabled": True, "connected": True,
                     "ipv4": {"address": ["169.254.3.4/16"]}},
                ]
            }
        }
        self.assertEqual([], lan_ipv4_addresses(payload))

    def test_keeps_other_private_ranges(self):
        payload = {
            "data": {
                "interfaces": [
                    {"interface": "eth0", "primary": True,
                     "ipv4": {"address": ["10.0.0.10/24", "192.168.50.2/24"]}},
                ]
            }
        }
        self.assertEqual(["10.0.0.10", "192.168.50.2"],
                         lan_ipv4_addresses(payload))


if __name__ == "__main__":
    unittest.main()
