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

# Release any snd-usb-audio claim on the MiniDSP FlexHTx audio interfaces and
# restore the host modprobe blacklist so this is self-healing across HAOS OS updates.
#
# Root cause: the Linux UAC driver's clock negotiation failure (err -71) on the
# FlexHTx audio interfaces destabilises the HID interface (1-1:1.3) that minidspd
# uses. Steps below:
#   1. Unbind snd-usb-audio from any FlexHTx audio interfaces it has claimed.
#   2. rmmod snd_usb_audio so it cannot immediately rebind (unbind alone is not
#      enough — the loaded module rebinds on the next udev event).
#   3. Restore the blacklist at /etc/modprobe.d/minidsp-no-audio.conf on the HAOS
#      host via /proc/1/root (accessible from this privileged container). This
#      survives add-on restarts and self-heals after HAOS OS updates that wipe the
#      overlay filesystem.
_snd_unbound=0
if [ -d /sys/bus/usb/drivers/snd-usb-audio ]; then
    for iface in /sys/bus/usb/drivers/snd-usb-audio/*; do
        iface_name=$(basename "${iface}")
        case "${iface_name}" in *:*) ;; *) continue ;; esac
        vendor=$(cat "${iface}/../idVendor"  2>/dev/null || true)
        product=$(cat "${iface}/../idProduct" 2>/dev/null || true)
        if [ "${vendor}" = "2752" ] && [ "${product}" = "004b" ]; then
            echo "Releasing snd-usb-audio from ${iface_name} (MiniDSP FlexHTx)"
            { echo -n "${iface_name}" > /sys/bus/usb/drivers/snd-usb-audio/unbind; } 2>/dev/null || true
            _snd_unbound=1
        fi
    done
    if [ "${_snd_unbound}" = "1" ]; then
        rmmod snd_usb_audio 2>/dev/null && echo "Unloaded snd_usb_audio module" || true
    fi
fi

# Restore blacklist on host — idempotent, runs every startup.
_bl=/proc/1/root/etc/modprobe.d/minidsp-no-audio.conf
if ! grep -q "blacklist snd-usb-audio" "${_bl}" 2>/dev/null; then
    mkdir -p "$(dirname "${_bl}")" 2>/dev/null || true
    { echo "blacklist snd-usb-audio" > "${_bl}"; } 2>/dev/null && \
        echo "Restored snd-usb-audio blacklist on host" || \
        echo "Warning: could not write snd-usb-audio blacklist to host"
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
