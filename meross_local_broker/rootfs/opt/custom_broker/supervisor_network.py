#!/usr/bin/python3
"""Print the LAN IPv4 addresses Home Assistant can be reached on.

The add-on runs in its own Docker network, so its own address is not usable by
phones on the LAN. The Supervisor knows the host interfaces; we query it with
the add-on token and exclude loopback, link-local and container bridges.
"""

import ipaddress
import json
import os
import sys
import urllib.request


def lan_ipv4_addresses(payload):
    interfaces = (payload.get("data") or {}).get("interfaces") or []
    ordered = sorted(
        interfaces,
        key=lambda iface: (not iface.get("primary", False),
                           iface.get("interface", "")),
    )
    result = []
    for iface in ordered:
        name = (iface.get("interface") or "").lower()
        if name == "lo" or name.startswith(("docker", "veth", "br-", "hassio")):
            continue
        if not iface.get("enabled", True) or not iface.get("connected", True):
            continue
        ipv4 = iface.get("ipv4") or {}
        for address in ipv4.get("address") or []:
            candidate = address.split("/")[0]
            try:
                parsed = ipaddress.ip_address(candidate)
            except ValueError:
                continue
            if parsed.version != 4:
                continue
            if parsed.is_loopback or parsed.is_link_local:
                continue
            if parsed in ipaddress.ip_network("172.30.32.0/23"):
                # Supervisor/Docker bridge, never reachable from the LAN.
                continue
            if candidate not in result:
                result.append(candidate)
    return result


def fetch_network_info():
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        raise RuntimeError("SUPERVISOR_TOKEN is not set")
    request = urllib.request.Request(
        "http://supervisor/network/info",
        headers={"Authorization": "Bearer " + token},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def main():
    try:
        addresses = lan_ipv4_addresses(fetch_network_info())
    except Exception as error:
        print("supervisor_network: %s" % error, file=sys.stderr)
        return 1
    if not addresses:
        print("supervisor_network: no LAN IPv4 address found", file=sys.stderr)
        return 1
    print(",".join(addresses))
    return 0


if __name__ == "__main__":
    sys.exit(main())
