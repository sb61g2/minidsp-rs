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

# Release snd-usb-audio's claim on MiniDSP FlexHTx audio interfaces and
# deauthorize those interfaces so they cannot be re-claimed.
#
# The Linux UAC driver binds to the FlexHTx audio interfaces and its clock
# negotiation failure (err -71) destabilises the HID interface that minidspd
# uses, causing repeated "Device not ready" / HID errors on USB reconnect.
#
# After unbinding, writing 0 to the interface's authorized sysfs attribute
# prevents ANY driver from re-binding to that interface until the device
# re-enumerates. The HID interface (bInterfaceClass 03) is left authorized.
#
# Race condition: on HAOS boot, udev may not have finished binding snd-usb-audio
# by the time this script starts. We sleep briefly to let enumeration settle,
# then retry the unbind+deauthorize up to 10 times (1 s apart).
if [ -d /sys/bus/usb/drivers/snd-usb-audio ]; then
    sleep 2
    retries=0
    while [ "${retries}" -lt 10 ]; do
        found=0
        for iface in /sys/bus/usb/drivers/snd-usb-audio/*; do
            iface_name=$(basename "${iface}")
            case "${iface_name}" in *:*) ;; *) continue ;; esac
            vendor=$(cat "${iface}/../idVendor"  2>/dev/null || true)
            product=$(cat "${iface}/../idProduct" 2>/dev/null || true)
            if [ "${vendor}" = "2752" ] && [ "${product}" = "004b" ]; then
                echo "Releasing snd-usb-audio from ${iface_name} (MiniDSP FlexHTx, attempt $((retries + 1)))"
                { echo -n "${iface_name}" > /sys/bus/usb/drivers/snd-usb-audio/unbind; } 2>/dev/null || true
                { echo 0 > "/sys/bus/usb/devices/${iface_name}/authorized"; } 2>/dev/null || true
                found=1
            fi
        done
        [ "${found}" -eq 0 ] && break
        retries=$((retries + 1))
        sleep 1
    done
fi

# Deauthorize any remaining FlexHTx audio interfaces (bInterfaceClass 01) that
# snd-usb-audio may not have claimed yet but could claim at any time.
for dev in /sys/bus/usb/devices/*/; do
    vendor=$(cat "${dev}idVendor"  2>/dev/null || true)
    product=$(cat "${dev}idProduct" 2>/dev/null || true)
    if [ "${vendor}" = "2752" ] && [ "${product}" = "004b" ]; then
        devname=$(basename "${dev%/}")
        for iface in "/sys/bus/usb/devices/${devname}:"*/; do
            cls=$(cat "${iface}bInterfaceClass" 2>/dev/null || true)
            if [ "${cls}" = "01" ]; then
                iface_name=$(basename "${iface%/}")
                echo "Deauthorizing FlexHTx audio interface ${iface_name}"
                { echo 0 > "${iface}authorized"; } 2>/dev/null || true
            fi
        done
    fi
done

# Disable USB autosuspend for the FlexHTx device.
# The kernel suspends idle USB devices by default. When the device wakes from
# suspend it re-enumerates, which lets snd-usb-audio rebind to the audio
# interfaces and trigger the same HID failure we just cleared above.
# Setting power/control to "on" keeps the device permanently active.
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

# Background monitor: if snd-usb-audio rebinds (e.g. after USB re-enumeration),
# unbind it and re-deauthorize the audio interfaces to block future rebinds.
(
    while true; do
        sleep 10
        if [ -d /sys/bus/usb/drivers/snd-usb-audio ]; then
            for iface in /sys/bus/usb/drivers/snd-usb-audio/*; do
                iface_name=$(basename "${iface}")
                case "${iface_name}" in *:*) ;; *) continue ;; esac
                vendor=$(cat "${iface}/../idVendor"  2>/dev/null || true)
                product=$(cat "${iface}/../idProduct" 2>/dev/null || true)
                if [ "${vendor}" = "2752" ] && [ "${product}" = "004b" ]; then
                    echo "snd-usb-audio rebind on ${iface_name} — unbinding and deauthorizing"
                    { echo -n "${iface_name}" > /sys/bus/usb/drivers/snd-usb-audio/unbind; } 2>/dev/null || true
                    { echo 0 > "/sys/bus/usb/devices/${iface_name}/authorized"; } 2>/dev/null || true
                fi
            done
        fi
    done
) &

echo "Starting MiniDSP RS daemon"
echo "  HTTP API: http://${HTTP_BIND}"
[ -n "${WIDG_IP}" ] && [ "${WIDG_IP}" != "null" ] && echo "  Wi-DG   : tcp://${WIDG_IP}:5333"

exec /usr/local/bin/minidspd --config "${CONFIG_PATH}"
