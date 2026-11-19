#!/usr/bin/with-contenv bashio
# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
# Upstream: https://github.com/albertogeniola/ha-meross-local-broker (Apache-2.0).

CONFIG_PATH=/data/options.json

pushd /opt/custom_broker >/dev/null
source /opt/utils/bashutils.sh

# Setup debug flag
DEBUG_MODE=$(get_option 'debug_mode' 'false')
if [[ $DEBUG_MODE == "true" ]]; then
  bashio::log.info "Starting broker agent with debug flag"
  debug="--debug"
else
  debug=""
fi

# MQTT message integrity: observe logs mismatches, enforce drops them.
MQTT_INTEGRITY_MODE=$(get_option 'mqtt_integrity_mode' 'observe')
export MQTT_INTEGRITY_MODE

# Temporary compatibility: keep publishing ACKs on the user topic too.
LEGACY_USER_TOPIC_ACKS=$(get_option 'legacy_user_topic_acks' 'true')
export LEGACY_USER_TOPIC_ACKS

# Generate a random password for agent user
# Timezone pushed to devices (Appliance.System.Time). Falls back to the Home Assistant timezone (TZ env).
DEVICE_TIMEZONE=$(get_option 'device_timezone' '')
if [[ -z "$DEVICE_TIMEZONE" ]]; then
  DEVICE_TIMEZONE="${TZ:-}"
fi
if [[ -n "$DEVICE_TIMEZONE" ]]; then
  bashio::log.info "Devices will be kept in sync with timezone ${DEVICE_TIMEZONE}"
  timezone_args=(--timezone "$DEVICE_TIMEZONE")
else
  bashio::log.warning "No timezone available (device_timezone option or TZ env): device time sync disabled"
  timezone_args=()
fi

AGENT_USERNAME="_agent"
AGENT_PASSWORD=$(openssl rand -base64 32)
AGENT_PBKDF2=$(/usr/share/mosquitto/pw -p $AGENT_PASSWORD)
echo "$AGENT_USERNAME:$AGENT_PBKDF2">/etc/mosquitto/auth.pw

# Static ACL for the files backend; go-auth checks the HTTP backend first.
echo -e "user $AGENT_USERNAME\ntopic readwrite #">/etc/mosquitto/auth.acl

# broker_agent retries its TLS connection until Mosquitto is ready. Avoid a
# raw TCP probe here: it closes before the TLS handshake and makes Mosquitto
# log "unexpected eof while reading" at every startup.
exec python3 broker_agent.py --port 2001 --host localhost --username "$AGENT_USERNAME" --password "$AGENT_PASSWORD" --cert-ca "/data/mqtt/certs/ca.crt" "${timezone_args[@]}" $debug
