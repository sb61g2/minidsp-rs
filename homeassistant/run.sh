#!/bin/sh
set -e

OPTIONS=/data/options.json

LOG_LEVEL=$(jq --raw-output '.log_level // "info"'                "${OPTIONS}")
HTTP_BIND=$(jq --raw-output '.http_bind_address // "0.0.0.0:5380"' "${OPTIONS}")
WIDG_IP=$(jq   --raw-output '.widg_ip           // ""'             "${OPTIONS}")

export RUST_LOG="${LOG_LEVEL}"

if [ -n "${SUPERVISOR_TOKEN}" ]; then
    HA_TZ=$(curl -sf \
        -H "Authorization: Bearer ${SUPERVISOR_TOKEN}" \
        http://supervisor/core/api/config | jq -r '.time_zone // ""')
    [ -n "${HA_TZ}" ] && export TZ="${HA_TZ}"
fi

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

# Warn if snd_usb_audio has somehow loaded despite the host blacklist
# (/etc/modprobe.d/minidsp-no-audio.conf on the HAOS host). The blacklist
# is maintained manually on p7 and the Docker overlay; this container cannot
# write to the host filesystem (sysfs is ro in add-on containers, and
# /proc/1/root resolves to this container's own root, not the HAOS host).
if [ -d /sys/bus/usb/drivers/snd-usb-audio ]; then
    for iface in /sys/bus/usb/drivers/snd-usb-audio/*; do
        iface_name=$(basename "${iface}" 2>/dev/null)
        case "${iface_name}" in *:*) ;; *) continue ;; esac
        vendor=$(cat "${iface}/../idVendor"  2>/dev/null || true)
        product=$(cat "${iface}/../idProduct" 2>/dev/null || true)
        if [ "${vendor}" = "2752" ] && [ "${product}" = "004b" ]; then
            echo "WARNING: snd_usb_audio is bound to FlexHTx interface ${iface_name}."
            echo "  The host blacklist (/etc/modprobe.d/minidsp-no-audio.conf) may be missing."
            echo "  Run: echo 'blacklist snd-usb-audio' | sudo nsenter --mount=/proc/1/ns/mnt -- tee /etc/modprobe.d/minidsp-no-audio.conf"
            echo "  Then reboot to reload without snd_usb_audio bound."
        fi
    done
fi

echo "Starting MiniDSP RS daemon"
echo "  HTTP API: http://${HTTP_BIND}"
[ -n "${WIDG_IP}" ] && [ "${WIDG_IP}" != "null" ] && echo "  Wi-DG   : tcp://${WIDG_IP}:5333"

exec /usr/local/bin/minidspd --config "${CONFIG_PATH}"
