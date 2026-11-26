# Broker on Home Assistant Container (Docker)

This guide covers **Home Assistant Container**: Docker without Supervisor,
therefore without the add-on store. For HA OS or HA Supervised, use the
**Meross Local Broker** add-on, which remains the recommended path.

## Requirements

- Docker Engine with the `docker compose` plugin, on a Linux host.
- Free ports **2001** (MQTT/TLS) and **2004** (HTTPS); **2003** for local
  administration.
- Home Assistant Container with HACS, or a manual copy of
  `custom_components/meross_local_cloud`.
- A Meross device and the Android pairer.

## Quick start

1. Copy the repository's `deploy/` directory to the Docker host.
2. Run `./install.sh`: it creates `.env` and `./data`, starts the container
   and waits for the broker to answer.
3. In Home Assistant: **Settings → Devices & services → Add integration →
   Meross Local Cloud**, then enter the host address, the local account and
   the password. Ports **2004** and **2001** are the broker's (prefilled from
   integration 4.0.4).
4. Pair the device with the pairer using the Docker host address.

## Values to enter

| Field            | Value                               |
| ---------------- | ----------------------------------- |
| Broker address   | Docker host LAN IP                  |
| HTTPS port       | `2004`                              |
| MQTT port        | `2001`                              |
| Login / password | local account created in the broker |

Local administration is at `http://127.0.0.1:2003/`. Remotely, use a tunnel:
`ssh -L 2003:127.0.0.1:2003 <user>@<host>`.

## Configuration

The variables in `deploy/.env` are read by `docker-compose.yml`:

| Variable              | Default     | Purpose                                 |
| --------------------- | ----------- | --------------------------------------- |
| `MEROSS_STANDALONE`   | `1`         | force standalone mode                   |
| `ADVERTISE`           | `false`     | mDNS advertising (advanced)             |
| `DEBUG_MODE`          | `false`     | verbose logs                            |
| `DEVICE_TIMEZONE`     | empty       | device timezone                         |
| `MQTT_INTEGRITY_MODE` | `observe`   | `observe` or `enforce`                  |
| `ADMIN_BIND`          | `127.0.0.1` | admin bind address                      |
| `ADMIN_PORT`          | `2003`      | admin port                              |
| `ADMIN_ALLOW_CIDR`    | `127.0.0.1` | CIDR allowed on the admin               |
| `TLS_SAN_AUTO`        | `1`         | add the host IPv4 addresses to the SANs |
| `TLS_SAN_EXTRA`       | host IP     | extra IP/DNS, comma separated           |

A `/data/options.json` file is also accepted and takes precedence over
environment variables. `install.sh` does not create one.

## Networking

The provided compose file uses `network_mode: host`: the broker takes the
host LAN address, devices and the pairer reach it directly, and the admin
stays on loopback. In bridge mode, publish `2001` and `2004` explicitly, and
`2003` only if needed; the admin has no authentication of its own, so never
expose it to the LAN without protection.

mDNS is disabled by default: automatic integration discovery does not work in
a standard container. Manual configuration above is the normal path. To enable
it, use `network_mode: host`, mount the host D-Bus socket, then set
`ADVERTISE=true`.

## TLS and certificates

The broker generates its CA and certificate on first start in
`/data/mqtt/certs`. The integration downloads and pins `/ca.crt`; the pairer
does the same. If the host IP changes, update `TLS_SAN_EXTRA` or
`TLS_SAN_AUTO`, then reset the pinned certificate on clients.

## Data and updates

The `./data` volume holds the database, certificates, profile signing key,
overrides and captures. Backup = copy the volume.

Update: `docker compose pull && docker compose up -d`. Pin a precise version in
`BROKER_IMAGE` to avoid surprises.

## Troubleshooting

| Problem                           | Check                                                 |
| --------------------------------- | ----------------------------------------------------- |
| Container restarts                | `docker logs meross-local-broker`, image architecture |
| Integration: certificate rejected | `https://<ip>:2004/ca.crt`, SAN, reset pin            |
| Admin unreachable                 | `ADMIN_BIND`, SSH tunnel, firewall                    |
| Device not paired                 | host IP, ports 2001/2004, `docker compose ps`         |
| No mDNS                           | expected in bridge mode; configure manually           |

## Security

- The admin has no authentication: keep `ADMIN_BIND=127.0.0.1` or put an
  authenticated reverse proxy in front.
- Do not expose port 2003 to the Internet.
- The broker's local account is independent from the official Meross account.
