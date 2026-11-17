#!/usr/bin/with-contenv bashio
source /opt/utils/bashutils.sh
pushd /opt/custom_broker >/dev/null

DEBUG_MODE=$(get_option 'debug_mode' 'false')
EXPOSE_ADMIN_API=$(get_option 'expose_admin_api' 'false')

# Start flask
bashio::log.info "Starting flask..."
if [[ $DEBUG_MODE == "true" ]]; then
  bashio::log.warning "Setting flask debug flags; debugpy listens on 127.0.0.1:10001 only."
  export ENABLE_DEBUG=True
  export LOG_LEVEL=DEBUG
  if [[ $EXPOSE_ADMIN_API == "true" ]]; then
    bashio::log.warning "Allowing admin API without ingress headers for local debugging."
    export ADMIN_ALLOW_INGRESSLESS=true
  fi
  exec python3 -m debugpy --listen 127.0.0.1:10001 ./http_api.py
else
  bashio::log.info "Setting flask production flags"
  export ENABLE_DEBUG=False
  exec python3 ./http_api.py
fi
