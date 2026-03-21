#!/usr/bin/with-contenv bashio

# Read configuration options
LOG_LEVEL=$(bashio::config 'log_level')
HTTP_BIND=$(bashio::config 'http_bind_address')
TCP_BIND=$(bashio::config 'tcp_bind_address')

# Configure Rust log level
export RUST_LOG="${LOG_LEVEL}"

CONFIG_PATH=/data/minidsp.toml

bashio::log.info "Generating configuration..."

# Write base config
cat > "${CONFIG_PATH}" << TOMLEOF
[http_server]
bind_address = "${HTTP_BIND}"

[[tcp_server]]
bind_address = "${TCP_BIND}"
TOMLEOF

# Append advertise settings if both name and IP are provided
if bashio::config.has_value 'advertise_name' && bashio::config.has_value 'advertise_ip'; then
    ADVERTISE_NAME=$(bashio::config 'advertise_name')
    ADVERTISE_IP=$(bashio::config 'advertise_ip')
    bashio::log.info "Advertising device as '${ADVERTISE_NAME}' at ${ADVERTISE_IP}"
    printf 'advertise = { ip = "%s", name = "%s" }\n' "${ADVERTISE_IP}" "${ADVERTISE_NAME}" \
        >> "${CONFIG_PATH}"
fi

bashio::log.info "Starting MiniDSP RS daemon"
bashio::log.info "  HTTP API : http://${HTTP_BIND}"
bashio::log.info "  TCP server: ${TCP_BIND}"

exec /usr/local/bin/minidspd --config "${CONFIG_PATH}"
