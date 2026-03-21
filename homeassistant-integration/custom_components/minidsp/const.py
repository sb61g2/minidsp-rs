"""Constants for the MiniDSP integration."""

DOMAIN = "minidsp"
DEFAULT_PORT = 5380
NUM_PRESETS = 4

# Source names as serialized by serde (PascalCase variant names).
# strum(serialize_all = "lowercase") only affects Display/FromStr;
# serde uses the Rust variant names: Analog, Toslink, Hdmi, etc.
# Maps hw_id -> list of valid source strings, in device order
SOURCES_BY_HW_ID: dict[int, list[str]] = {
    1: ["Spdif", "Toslink", "Aesebu"],          # M4x10Hd / M10x10Hd
    2: ["Toslink", "Spdif"],                     # Nanodigi2x8 / M2x4
    4: ["Spdif", "Toslink", "Aesebu"],           # MSharc4x8
    6: ["Analog", "Toslink", "Usb"],             # DDRC88BM
    10: ["Analog", "Toslink", "Usb"],            # M2x4HD / DDRC24
    11: ["Analog", "Toslink", "Spdif"],          # C8x12v2
    14: ["Analog", "Toslink", "Usb"],            # SHD
    17: ["Toslink", "Spdif", "Aesebu", "Usb", "Lan"],
    18: ["Toslink", "Spdif", "Aesebu", "Usb", "Lan"],
    27: ["Analog", "Toslink", "Spdif", "Usb", "Bluetooth"],  # Flex / FlexDl
    32: ["Analog", "Toslink", "Spdif", "Usb", "Hdmi"],       # FlexHtx
}

SOURCE_LABELS: dict[str, str] = {
    "Analog": "Analog",
    "Toslink": "Toslink (Optical)",
    "Spdif": "S/PDIF (Coaxial)",
    "Usb": "USB",
    "Hdmi": "HDMI",
    "Bluetooth": "Bluetooth",
    "Aesebu": "AES/EBU",
    "I2S": "I2S",
    "Lan": "LAN",
}
