#!/usr/bin/with-contenv bashio
source /opt/utils/bashutils.sh
pushd /opt/custom_broker >/dev/null
export PYTHONPATH=/opt/custom_broker${PYTHONPATH:+:$PYTHONPATH}

DEBUG_MODE=$(get_option 'debug_mode' 'false')

# Start flask
bashio::log.info "Starting flask..."
if [[ $DEBUG_MODE == "true" ]]; then
  bashio::log.warning "Setting flask debug flags; debugpy listens on 127.0.0.1:10001 only."
  export ENABLE_DEBUG=True
  export LOG_LEVEL=DEBUG
  exec python3 -m debugpy --listen 127.0.0.1:10001 \
    /usr/local/bin/waitress-serve --listen=127.0.0.1:2002 http_api:app
else
  bashio::log.info "Starting the API with waitress"
  export ENABLE_DEBUG=False
  exec /usr/local/bin/waitress-serve --listen=127.0.0.1:2002 http_api:app
fi
