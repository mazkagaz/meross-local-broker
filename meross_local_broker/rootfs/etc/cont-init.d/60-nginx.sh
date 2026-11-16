#!/usr/bin/with-contenv bashio
source /opt/utils/bashutils.sh

# ==============================================================================
# Configure NGINX for use with Meross Local Broker
# ==============================================================================
ingress_entry=$(bashio::addon.ingress_entry)
ingress_port=$(bashio::addon.ingress_port)
ingress_interface=$(bashio::addon.ip_address)

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

# Expose API logic
EXPOSE_ADMIN_API=$(get_option 'expose_admin_api' 'false')
if [[ $EXPOSE_ADMIN_API == "true" ]]; then
    bashio::log.warning "Exposing nginx publicly due to expose_admin_api env variable."
    sed -i "s#%%whitelisted_inbound_cidr%%#0.0.0.0/0#g" /etc/nginx/ingress.conf
else
    sed -i "s/%%whitelisted_inbound_cidr%%/172.30.32.2/g" /etc/nginx/ingress.conf
fi

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