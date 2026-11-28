#!/usr/bin/with-contenv bashio
# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
# Upstream: https://github.com/albertogeniola/ha-meross-local-broker (Apache-2.0).
source /opt/utils/bashutils.sh
pushd /opt/custom_broker >/dev/null
export PYTHONPATH=/opt/custom_broker${PYTHONPATH:+:$PYTHONPATH}

# MQTT account rate limiting (custom/app only; devices are always exempt).
MQTT_AUTH_RATE_LIMIT=$(get_option 'mqtt_auth_rate_limit' 'false')
export MQTT_AUTH_RATE_LIMIT

DEBUG_MODE=$(get_option 'debug_mode' 'false')
if [[ $DEBUG_MODE == "true" ]]; then
  bashio::log.warning "Verbose logging enabled."
  export LOG_LEVEL=DEBUG
fi

bashio::log.info "Starting the API with waitress"
exec /usr/local/bin/waitress-serve --listen=127.0.0.1:2002 http_api:app
