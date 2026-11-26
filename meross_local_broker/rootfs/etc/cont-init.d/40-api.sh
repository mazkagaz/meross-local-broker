#!/usr/bin/with-contenv bashio
# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
# Upstream: https://github.com/albertogeniola/ha-meross-local-broker (Apache-2.0).
source /opt/utils/bashutils.sh
# ==============================================================================
# Configures Meross service
# ==============================================================================

DB_PATH=/data/database.db

# If the user has asked to reinit the db, remove it.
# Since we want to expose this functionality both from HA and Stand-Alone container,
# we need to fetch it also from HA
REINIT_DB=$(get_option 'reinit_db' 'false')
if [[ $REINIT_DB == "true" ]]; then
  if [[ -f $DB_PATH ]]; then
    bashio::log.warning "User configuration requires DB reinitialization. Removing previous DB data."
    rm $DB_PATH
  fi
fi

# Configure env-vars. Standalone serves the UI at the root: the backend prefix
# must stay empty, otherwise URLs would become protocol-relative (`//_admin_`).
if is_standalone; then
    api_url="${API_URL:-}"
else
    api_url=$(bashio::app.ingress_entry)
fi
sed -i "s#%%APIURL%%#${api_url}#g" /var/www/assets/env.js

# Initializing DB
pushd /opt/custom_broker >/dev/null

bashio::log.info "Setting up the database in $DB_PATH"
python3 setup.py

if [[ $? -ne 0 ]]; then
  bashio::log.error "Error when setting up the database file. Aborting."
  exit 1
else
  bashio::log.info "DB setup finished"
fi
popd >/dev/null

# Prepare log dir
mkdir -p /var/log/api
chown nobody:nogroup /var/log/api
chmod 02755 /var/log/api