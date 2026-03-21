"""Constants for the MiniDSP integration."""

DOMAIN = "minidsp"
DEFAULT_PORT = 5380
NUM_PRESETS = 4

# Source names as serialized by the daemon (strum lowercase)
# Maps hw_id -> list of valid source strings, in device order
SOURCES_BY_HW_ID: dict[int, list[str]] = {
    1: ["spdif", "toslink", "aesebu"],          # M4x10Hd / M10x10Hd
    2: ["toslink", "spdif"],                     # Nanodigi2x8 / M2x4
    4: ["spdif", "toslink", "aesebu"],           # MSharc4x8
    6: ["analog", "toslink", "usb"],             # DDRC88BM
    10: ["analog", "toslink", "usb"],            # M2x4HD / DDRC24
    11: ["analog", "toslink", "spdif"],          # C8x12v2
    14: ["analog", "toslink", "usb"],            # SHD
    17: ["toslink", "spdif", "aesebu", "usb", "lan"],
    18: ["toslink", "spdif", "aesebu", "usb", "lan"],
    27: ["analog", "toslink", "spdif", "usb", "bluetooth"],  # Flex / FlexDl
    32: ["analog", "toslink", "spdif", "usb", "hdmi"],       # FlexHtx
}

SOURCE_LABELS: dict[str, str] = {
    "analog": "Analog",
    "toslink": "Toslink (Optical)",
    "spdif": "S/PDIF (Coaxial)",
    "usb": "USB",
    "hdmi": "HDMI",
    "bluetooth": "Bluetooth",
    "aesebu": "AES/EBU",
    "i2s": "I2S",
    "lan": "LAN",
}
