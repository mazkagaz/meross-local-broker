CONFIG_PATH="${CONFIG_PATH:-/data/options.json}"

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
