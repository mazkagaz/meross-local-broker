#!/usr/bin/with-contenv bashio
# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
# Upstream: https://github.com/albertogeniola/ha-meross-local-broker (Apache-2.0).
source /opt/utils/bashutils.sh

# ==============================================================================
# Configure NGINX for use with Meross Local Broker
# ==============================================================================
if is_standalone; then
    # No Supervisor: the admin UI is bound to the host loopback by default.
    ingress_entry="${INGRESS_ENTRY:-/}"
    ingress_port="${ADMIN_PORT:-2003}"
    ingress_interface="${ADMIN_BIND:-127.0.0.1}"
    admin_cidr="${ADMIN_ALLOW_CIDR:-127.0.0.1}"
    bashio::log.info "Standalone mode: admin UI on ${ingress_interface}:${ingress_port} (allow ${admin_cidr})."
else
    ingress_entry=$(bashio::app.ingress_entry)
    ingress_port=$(bashio::app.ingress_port)
    ingress_interface=$(bashio::app.ip_address)
    admin_cidr="172.30.32.2"
fi

# Safe defaults
if [[ $ingress_interface = "" ]]; then
    ingress_interface="127.0.0.1"
fi

if [[ $ingress_port = "" ]]; then
    ingress_port="2003"
fi

if [[ $ingress_entry = "" ]]; then
    ingress_entry="/"
fi

if [[ $admin_cidr = "" ]]; then
    admin_cidr="127.0.0.1"
fi

bashio::log.info "Substituting ingress_entry with ${ingress_entry}"
sed -i "s#%%ingress_entry%%#${ingress_entry}#g" /etc/nginx/ingress.conf

bashio::log.info "Substituting interface with ${ingress_interface}"
sed -i "s/%%ingress_interface%%/${ingress_interface}/g" /etc/nginx/ingress.conf

bashio::log.info "Substituting port with ${ingress_port}"
sed -i "s/%%ingress_port%%/${ingress_port}/g" /etc/nginx/ingress.conf

# Admin API access: Supervisor ingress, or the configured standalone CIDR.
sed -i "s#%%whitelisted_inbound_cidr%%#${admin_cidr}#g" /etc/nginx/ingress.conf
bashio::log.info "HTTPS listener enabled on port 2004."

# Prepare log dir
mkdir -p /var/log/nginx
chown nobody:nogroup /var/log/nginx
chmod 02755 /var/log/nginx