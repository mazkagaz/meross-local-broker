#!/usr/bin/with-contenv bashio
# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
# Upstream: https://github.com/albertogeniola/ha-meross-local-broker (Apache-2.0).
# ==============================================================================
# Configures the Avahi daemon
# ==============================================================================
# shellcheck disable=SC1091

# Reset the persisted online status while no service is running yet. Doing it
# here, before mosquitto accepts device connections, avoids erasing the ONLINE
# status that devices set when they authenticate during startup.
pushd /opt/custom_broker >/dev/null
python3 -c "from database import init_db; from db_helper import dbhelper; init_db(); dbhelper.reset_device_online_status()"
popd >/dev/null

# Prepare log dir
mkdir -p /var/log/broker
chown nobody:nogroup /var/log/broker
chmod 02755 /var/log/broker