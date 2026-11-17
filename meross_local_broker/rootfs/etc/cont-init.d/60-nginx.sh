#!/usr/bin/with-contenv bashio
source /opt/utils/bashutils.sh

# ==============================================================================
# Configure NGINX for use with Meross Local Broker
# ==============================================================================
ingress_entry=$(bashio::app.ingress_entry)
ingress_port=$(bashio::app.ingress_port)
ingress_interface=$(bashio::app.ip_address)

# Safe defaults
if [[ $ingress_interface = "" ]]; then
    ingress_interface="0.0.0.0"
fi

if [[ $ingress_port = "" ]]; then
    ingress_port="2003"
fi

if [[ $ingress_entry = "" ]]; then
    ingress_entry="/"
fi

bashio::log.info "Substituting ingress_entry with ${ingress_entry}"
sed -i "s#%%ingress_entry%%#${ingress_entry}#g" /etc/nginx/ingress.conf

bashio::log.info "Substituting interface with ${ingress_interface}"
sed -i "s/%%ingress_interface%%/${ingress_interface}/g" /etc/nginx/ingress.conf

bashio::log.info "Substituting port with ${ingress_port}"
sed -i "s/%%ingress_port%%/${ingress_port}/g" /etc/nginx/ingress.conf

# Admin API access. Production keeps it on the Home Assistant Supervisor
# ingress only; local development can opt into a public admin API by enabling
# both debug_mode and expose_admin_api.
DEBUG_MODE=$(get_option 'debug_mode' 'false')
EXPOSE_ADMIN_API=$(get_option 'expose_admin_api' 'false')
if [[ $EXPOSE_ADMIN_API == "true" && $DEBUG_MODE == "true" ]]; then
    bashio::log.warning "Exposing nginx publicly because debug_mode and expose_admin_api are enabled."
    ADMIN_CIDR="0.0.0.0/0"
else
    if [[ $EXPOSE_ADMIN_API == "true" ]]; then
        bashio::log.warning "Ignoring expose_admin_api: debug_mode must be enabled as well."
    fi
    ADMIN_CIDR="172.30.32.2"
fi
sed -i "s#%%whitelisted_inbound_cidr%%#${ADMIN_CIDR}#g" /etc/nginx/ingress.conf

# Optional HTTPS listener. Disabling it leaves port 2003 (plain HTTP) and the
# MQTT/TLS listener on 2001 untouched.
ENABLE_HTTPS=$(get_option 'enable_https' 'true')
if [[ $ENABLE_HTTPS == "true" ]]; then
    bashio::log.info "HTTPS listener enabled on port 2004."
else
    bashio::log.warning "HTTPS listener disabled: removing it from nginx.conf."
    sed -i '/# BEGIN HTTPS SERVER/,/# END HTTPS SERVER/d' /etc/nginx/ingress.conf
fi

# Prepare log dir
mkdir -p /var/log/nginx
chown nobody:nogroup /var/log/nginx
chmod 02755 /var/log/nginx