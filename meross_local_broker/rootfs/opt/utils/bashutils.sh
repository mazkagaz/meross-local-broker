# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
# Upstream: https://github.com/albertogeniola/ha-meross-local-broker (Apache-2.0).
CONFIG_PATH="${CONFIG_PATH:-/data/options.json}"

# Standalone mode: no Home Assistant Supervisor. Every bashio::app.* call must
# be skipped in that mode, since bashio aborts under set -e when the Supervisor
# API is unreachable.
function is_standalone {
    case "${MEROSS_STANDALONE:-}" in
        1|true|TRUE|yes|YES) return 0 ;;
    esac
    if [[ -z "${SUPERVISOR_TOKEN:-}" && -z "${HASSIO_TOKEN:-}" ]]; then
        return 0
    fi
    return 1
}

# LAN IPv4 addresses, used for mDNS TXT records and TLS SANs. Under the
# Supervisor the add-on network is queried; standalone relies on the host
# network namespace (network_mode: host).
function lan_ipv4_addresses {
    if is_standalone; then
        hostname -I 2>/dev/null \
            | tr ' ' '\n' \
            | grep -E '^[0-9]{1,3}(\.[0-9]{1,3}){3}$' \
            | grep -v '^127\.' \
            | paste -sd, - \
            || true
        return 0
    fi
    python3 /opt/custom_broker/supervisor_network.py 2>/dev/null || true
}

function get_option {
    local parameter_name=$1
    local default_value=$2
    local config_path="${CONFIG_PATH:-/data/options.json}"
    local ha_value
    local env_value

    # Read the key without relying on jq -e: jq exits non-zero for false/null,
    # which aborts the whole script under bashio's set -e.
    ha_value=$(jq -r --arg key "$parameter_name" \
        'if has($key) then .[$key] | tostring else empty end' \
        "$config_path" 2>/dev/null || true)
    if [[ -n "$ha_value" ]]; then
        echo "$ha_value"
        return 0
    fi

    env_value=$(printenv "$parameter_name" 2>/dev/null || true)
    if [[ -n "$env_value" ]]; then
        echo "$env_value"
    else
        echo "$default_value"
    fi
}
