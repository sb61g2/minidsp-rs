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

# Release any snd-usb-audio claim on the MiniDSP FlexHTx audio interfaces.
#
# The Linux UAC driver's clock negotiation failure (err -71) destabilises the
# HID interface that minidspd uses. The permanent fix is a modprobe blacklist
# written to the HAOS host at /etc/modprobe.d/minidsp-no-audio.conf so the
# module never loads. This one-shot unbind is a safety net in case the blacklist
# is absent (e.g. after a HAOS OS update that resets the overlay).
if [ -d /sys/bus/usb/drivers/snd-usb-audio ]; then
    for iface in /sys/bus/usb/drivers/snd-usb-audio/*; do
        iface_name=$(basename "${iface}")
        case "${iface_name}" in *:*) ;; *) continue ;; esac
        vendor=$(cat "${iface}/../idVendor"  2>/dev/null || true)
        product=$(cat "${iface}/../idProduct" 2>/dev/null || true)
        if [ "${vendor}" = "2752" ] && [ "${product}" = "004b" ]; then
            echo "Releasing snd-usb-audio from ${iface_name} (MiniDSP FlexHTx — blacklist may be missing)"
            { echo -n "${iface_name}" > /sys/bus/usb/drivers/snd-usb-audio/unbind; } 2>/dev/null || true
        fi
    done
fi

# Disable USB autosuspend for the FlexHTx device.
# Autosuspend causes re-enumeration, which triggers driver re-binding.
for dev in /sys/bus/usb/devices/*/; do
    vendor=$(cat "${dev}idVendor"  2>/dev/null || true)
    product=$(cat "${dev}idProduct" 2>/dev/null || true)
    if [ "${vendor}" = "2752" ] && [ "${product}" = "004b" ]; then
        devname=$(basename "${dev}")
        echo "Disabling USB autosuspend for FlexHTx (${devname})"
        { echo -1  > "${dev}power/autosuspend_delay_ms"; } 2>/dev/null || true
        { echo on  > "${dev}power/control";               } 2>/dev/null || true
    fi
done

echo "Starting MiniDSP RS daemon"
echo "  HTTP API: http://${HTTP_BIND}"
[ -n "${WIDG_IP}" ] && [ "${WIDG_IP}" != "null" ] && echo "  Wi-DG   : tcp://${WIDG_IP}:5333"

exec /usr/local/bin/minidspd --config "${CONFIG_PATH}"
