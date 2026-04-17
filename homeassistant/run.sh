#!/bin/sh
set -e

OPTIONS=/data/options.json

LOG_LEVEL=$(jq --raw-output '.log_level // "info"'                "${OPTIONS}")
HTTP_BIND=$(jq --raw-output '.http_bind_address // "0.0.0.0:5380"' "${OPTIONS}")
WIDG_IP=$(jq   --raw-output '.widg_ip           // ""'             "${OPTIONS}")

export RUST_LOG="${LOG_LEVEL}"

CONFIG_PATH=/data/minidsp.toml

# [http_server] block
printf '[http_server]\nbind_address = "%s"\n\n' "${HTTP_BIND}" > "${CONFIG_PATH}"

# One [[tcp_server]] block per entry in tcp_servers
TCP_COUNT=$(jq '.tcp_servers | length' "${OPTIONS}")
i=0
while [ "${i}" -lt "${TCP_COUNT}" ]; do
    BIND=$(jq --raw-output   ".tcp_servers[${i}].bind_address   // \"0.0.0.0:5333\"" "${OPTIONS}")
    SERIAL=$(jq --raw-output ".tcp_servers[${i}].device_serial  // \"null\""          "${OPTIONS}")
    ADV_NAME=$(jq --raw-output ".tcp_servers[${i}].advertise_name // \"\""            "${OPTIONS}")
    ADV_IP=$(jq --raw-output   ".tcp_servers[${i}].advertise_ip   // \"\""            "${OPTIONS}")

    printf '[[tcp_server]]\nbind_address = "%s"\n' "${BIND}" >> "${CONFIG_PATH}"

    if [ "${SERIAL}" != "null" ] && [ "${SERIAL}" != "" ]; then
        printf 'device_serial = %s\n' "${SERIAL}" >> "${CONFIG_PATH}"
    fi

    if [ -n "${ADV_NAME}" ] && [ "${ADV_NAME}" != "null" ] && \
       [ -n "${ADV_IP}" ]   && [ "${ADV_IP}"   != "null" ]; then
        printf 'advertise = { ip = "%s", name = "%s" }\n' "${ADV_IP}" "${ADV_NAME}" >> "${CONFIG_PATH}"
    fi

    printf '\n' >> "${CONFIG_PATH}"

    SERIAL_INFO=""
    if [ "${SERIAL}" != "null" ] && [ "${SERIAL}" != "" ]; then
        SERIAL_INFO=" (serial: ${SERIAL})"
    fi
    echo "  TCP server ${i}: ${BIND}${SERIAL_INFO}"
    i=$((i + 1))
done

# [[static_device]] for Wi-DG
if [ -n "${WIDG_IP}" ] && [ "${WIDG_IP}" != "null" ]; then
    printf '[[static_device]]\nurl = "tcp://%s:5333"\n' "${WIDG_IP}" >> "${CONFIG_PATH}"
fi

echo "Starting MiniDSP RS daemon"
echo "  HTTP API: http://${HTTP_BIND}"
[ -n "${WIDG_IP}" ] && [ "${WIDG_IP}" != "null" ] && echo "  Wi-DG   : tcp://${WIDG_IP}:5333"

exec /usr/local/bin/minidspd --config "${CONFIG_PATH}"
