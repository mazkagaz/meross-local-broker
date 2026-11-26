#!/usr/bin/with-contenv bashio

MQTT_MOSQUITTO_CONF_PATH=/etc/mosquitto/mosquitto.conf

bashio::log.info "Waiting for local dev server..."
# Portable wait: bashio::net.wait_for depends on the Supervisor.
api_ready=false
for _ in $(seq 1 60); do
    if timeout 1 bash -c 'exec 3<>/dev/tcp/127.0.0.1/2002' 2>/dev/null; then
        api_ready=true
        break
    fi
    sleep 1
done
if [[ "$api_ready" != "true" ]]; then
    bashio::log.warning "Local API did not listen on 127.0.0.1:2002 within 60s; starting mosquitto anyway."
fi

bashio::log.info "Waiting for auth file..."
while [ ! -f /etc/mosquitto/auth.pw ]; do sleep 1; done
bashio::log.info "Waiting for acl file..."
while [ ! -f /etc/mosquitto/auth.acl ]; do sleep 1; done

bashio::log.info "Starting mosquitto..."
exec mosquitto -c $MQTT_MOSQUITTO_CONF_PATH
