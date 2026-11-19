#!/usr/bin/with-contenv bashio
# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
# Upstream: https://github.com/albertogeniola/ha-meross-local-broker (Apache-2.0).
# ==============================================================================
# Configures Meross service
# ==============================================================================
source /opt/utils/bashutils.sh

CERTS_FOLDER=/data/mqtt/certs
CA_KEY_PATH="$CERTS_FOLDER/ca.key"
CA_CRT_PATH="$CERTS_FOLDER/ca.crt"
CA_PASS_PATH="$CERTS_FOLDER/ca.pass"
SERVER_KEY_PATH="$CERTS_FOLDER/server.key"
SERVER_CRT_PATH="$CERTS_FOLDER/server.crt"
SERVER_SAN_PATH="$CERTS_FOLDER/server.san"
CA_CONFIG_PATH=/etc/mosquitto/certs/ca.conf
SERVER_CONFIG_PATH=/etc/mosquitto/certs/server.conf
MOSQUITTO_LOG_DIR_PATH=/var/log/mosquitto

bashio::log.info "Checking for TLS certificates..."
mkdir -p "$CERTS_FOLDER"

# ------------------------------------------------------------------------------
# Decide whether the CA must be (re)generated.
# Legacy brokers created a CA without basicConstraints=CA:TRUE, which makes
# chain verification impossible for clients.
# ------------------------------------------------------------------------------
GEN_CA=false
if [[ ! -f "$CA_KEY_PATH" || ! -f "$CA_CRT_PATH" ]]; then
    GEN_CA=true
elif ! openssl x509 -in "$CA_CRT_PATH" -noout -text 2>/dev/null | grep -q "CA:TRUE"; then
    bashio::log.warning "Legacy TLS CA detected (missing CA:TRUE). Regenerating."
    GEN_CA=true
elif ! openssl x509 -checkend 2592000 -noout -in "$CA_CRT_PATH" >/dev/null 2>&1; then
    bashio::log.warning "TLS CA expires within 30 days. Regenerating."
    GEN_CA=true
fi

if [[ "$GEN_CA" == "true" ]]; then
    if [[ -n "$(ls -A "$CERTS_FOLDER" 2>/dev/null)" ]]; then
        BACKUP_FOLDER="${CERTS_FOLDER}.bak-$(date +%s)"
        cp -a "$CERTS_FOLDER" "$BACKUP_FOLDER"
        bashio::log.warning "Previous certificates backed up to ${BACKUP_FOLDER}"
    fi
    rm -f "$CA_KEY_PATH" "$CA_CRT_PATH" "$SERVER_KEY_PATH" "$SERVER_CRT_PATH" \
        "$SERVER_SAN_PATH" "${CA_CRT_PATH}.srl"
    # Fresh random passphrase for the new CA; never a hardcoded one.
    openssl rand -base64 32 > "$CA_PASS_PATH"
    chmod 600 "$CA_PASS_PATH"

    openssl genrsa -aes256 -passout "file:$CA_PASS_PATH" -out "$CA_KEY_PATH" 2048
    openssl req -new -x509 -days 3600 -key "$CA_KEY_PATH" \
        -passin "file:$CA_PASS_PATH" -out "$CA_CRT_PATH" \
        -config "$CA_CONFIG_PATH" -extensions v3_ca
    bashio::log.warning "TLS CA regenerated. Clients must reset their pinned broker certificate."
fi

# CA passphrase must exist for signing; legacy installs used 'notasecret'.
if [[ ! -f "$CA_PASS_PATH" ]]; then
    if openssl pkey -in "$CA_KEY_PATH" -passin pass:notasecret -noout 2>/dev/null; then
        printf '%s' 'notasecret' > "$CA_PASS_PATH"
        chmod 600 "$CA_PASS_PATH"
        bashio::log.warning "Legacy TLS CA passphrase detected."
    else
        bashio::log.error "TLS CA passphrase is missing and the key cannot be opened. Delete ${CERTS_FOLDER} to regenerate."
        exit 1
    fi
fi

# ------------------------------------------------------------------------------
# Server key: keep the existing one, generate it only when missing.
# ------------------------------------------------------------------------------
if [[ ! -f "$SERVER_KEY_PATH" ]]; then
    bashio::log.info "Generating the TLS server key."
    openssl genrsa -out "$SERVER_KEY_PATH" 2048
fi

# ------------------------------------------------------------------------------
# Subject Alternative Names: static names plus the LAN IPv4 addresses served by
# the add-on, so clients connecting by IP can validate the hostname.
# ------------------------------------------------------------------------------
HOST_IPS=$(python3 /opt/custom_broker/supervisor_network.py 2>/dev/null || true)
SAN="DNS:homeassistant.local, DNS:localhost, IP:127.0.0.1"
if [[ -n "$HOST_IPS" ]]; then
    IFS=',' read -ra IPS <<< "$HOST_IPS"
    for ip in "${IPS[@]}"; do
        ip="${ip//[[:space:]]/}"
        if [[ "$ip" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ && "$ip" != "127.0.0.1" ]]; then
            SAN+=", IP:$ip"
        fi
    done
else
    bashio::log.warning "No LAN IPv4 detected; certificate SAN keeps the static names only."
fi

NEED_SIGN=false
if [[ ! -f "$SERVER_CRT_PATH" || ! -f "$SERVER_SAN_PATH" ]]; then
    NEED_SIGN=true
elif [[ "$(cat "$SERVER_SAN_PATH")" != "$SAN" ]]; then
    bashio::log.info "LAN addresses changed; re-signing the TLS server certificate."
    NEED_SIGN=true
elif ! openssl x509 -checkend 2592000 -noout -in "$SERVER_CRT_PATH" >/dev/null 2>&1; then
    bashio::log.info "TLS server certificate expires within 30 days; re-signing."
    NEED_SIGN=true
fi

if [[ "$NEED_SIGN" == "true" ]]; then
    sed "s#%%SAN%%#${SAN}#" "$SERVER_CONFIG_PATH" > /tmp/server.ext
    openssl req -new -out /tmp/server.csr -key "$SERVER_KEY_PATH" \
        -config "$SERVER_CONFIG_PATH"
    openssl x509 -req -in /tmp/server.csr -CA "$CA_CRT_PATH" \
        -CAkey "$CA_KEY_PATH" -CAcreateserial -out "$SERVER_CRT_PATH" \
        -days 3600 -passin "file:$CA_PASS_PATH" \
        -extfile /tmp/server.ext -extensions v3_req
    printf '%s' "$SAN" > "$SERVER_SAN_PATH"
    bashio::log.info "TLS server certificate signed (SAN: ${SAN})."
    bashio::log.warning "If the certificate changed, reset the pinned broker certificate on clients."
fi

# ------------------------------------------------------------------------------
# Permissions
# ------------------------------------------------------------------------------
bashio::log.info "Aligning permissions for certificates"
chown root:root "$CA_KEY_PATH" "$CA_PASS_PATH"
chmod 600 "$CA_KEY_PATH" "$CA_PASS_PATH"
chown mosquitto:mosquitto "$CA_CRT_PATH" "$SERVER_KEY_PATH" "$SERVER_CRT_PATH" \
    "$SERVER_SAN_PATH"
chmod 644 "$CA_CRT_PATH" "$SERVER_CRT_PATH" "$SERVER_SAN_PATH"
chmod 600 "$SERVER_KEY_PATH"

# Prepare log dir
mkdir -p "$MOSQUITTO_LOG_DIR_PATH"
chown nobody:nogroup "$MOSQUITTO_LOG_DIR_PATH"
chmod 02755 "$MOSQUITTO_LOG_DIR_PATH"
