#!/bin/sh
set -e

OPTIONS=/data/options.json

LOG_LEVEL=$(jq --raw-output '.log_level // "info"'          "${OPTIONS}")
HTTP_BIND=$(jq --raw-output '.http_bind_address // "0.0.0.0:5380"' "${OPTIONS}")
TCP_BIND=$(jq --raw-output  '.tcp_bind_address  // "0.0.0.0:5333"' "${OPTIONS}")
WIDG_IP=$(jq  --raw-output  '.widg_ip           // ""'             "${OPTIONS}")
ADV_NAME=$(jq --raw-output  '.advertise_name    // ""'             "${OPTIONS}")
ADV_IP=$(jq   --raw-output  '.advertise_ip      // ""'             "${OPTIONS}")

export RUST_LOG="${LOG_LEVEL}"

CONFIG_PATH=/data/minidsp.toml

# http_server block
printf '[http_server]\nbind_address = "%s"\n\n' "${HTTP_BIND}" > "${CONFIG_PATH}"

# [[tcp_server]] block — advertise must be inside this block
printf '[[tcp_server]]\nbind_address = "%s"\n' "${TCP_BIND}" >> "${CONFIG_PATH}"
if [ -n "${ADV_NAME}" ] && [ -n "${ADV_IP}" ]; then
    printf 'advertise = { ip = "%s", name = "%s" }\n' "${ADV_IP}" "${ADV_NAME}" \
        >> "${CONFIG_PATH}"
fi

# [[static_device]] for Wi-DG (comes after tcp_server block)
if [ -n "${WIDG_IP}" ]; then
    printf '\n[[static_device]]\nurl = "tcp://%s:5333"\n' "${WIDG_IP}" >> "${CONFIG_PATH}"
fi

echo "Starting MiniDSP RS daemon"
echo "  HTTP API : http://${HTTP_BIND}"
echo "  TCP server: ${TCP_BIND}"
[ -n "${WIDG_IP}" ]  && echo "  Wi-DG    : tcp://${WIDG_IP}:5333"

exec /usr/local/bin/minidspd --config "${CONFIG_PATH}"
