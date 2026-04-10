# MiniDSP Controller
[![GitHub release](https://img.shields.io/github/v/release/mrene/minidsp-rs?include_prereleases)](https://github.com/mrene/minidsp-rs/releases) [![Documentation](https://img.shields.io/badge/docs-online-success)](https://minidsp-rs.pages.dev/) [![Discord](https://img.shields.io/discord/850873168558424095?label=discord&logo=discord)](https://discord.gg/XGHmrcDumf)

> **Fork note:** This is [sb61g2/minidsp-rs](https://github.com/sb61g2/minidsp-rs), a fork of [mrene/minidsp-rs](https://github.com/mrene/minidsp-rs) that adds a Home Assistant OS add-on and custom HA integration. See the [Home Assistant Integration](#home-assistant-integration) section below.

minidsp-rs is an alternative control software for certain MiniDSP products. It exposes most (if not all) of the available configuration parameters in a command line package, with an optional HTTP API in order to integrate with custom DIY audio projects. It can run on a variety of systems with a minimal memory footprint.

## Installation
Pre-built packages and binaries are available [in the project's releases section](https://github.com/mrene/minidsp-rs/releases). 

Debian (`.deb`) packages are available for:
- armhf: Tested on raspbian (Raspberry PI, including the rpi0)
- x86_64 Debian / Ubuntu variants

Single binary builds are also provided for common operating systems:
- Linux: minidsp.x86_64-unknown-linux-gnu.tar.gz
- MacOS: minidsp.x86_64-apple-darwin.tar.gz
- Windows: minidsp.x86_64-pc-windows-msvc.zip


### Building from source
This is only required if you want to make changes to minidsp-rs. If you're just trying to control your device, use one of the [pre-built packages](https://github.com/mrene/minidsp-rs/releases)

If you don't have rust setup, the quickest way to get started is with [rustup](https://rustup.rs/). This is preferred over install rust via your distro's package manager because these are often out of date and will have issues compiling recent code.

```bash
cargo build --release --bin minidsp
# The binary will then available as target/release/minidsp

# If you want to build a debian package
cargo install cargo-deb
cargo deb
# Then look under target/debian/
```

## Usage
See the [complete documentation](https://minidsp-rs.pages.dev/) for more examples.

Running the command without any parameters will return a status summary, in this form:

```
$ minidsp 
MasterStatus { preset: 0, source: Toslink, volume: Gain(-8.0), mute: false, dirac: false }
Input levels: -61.6, -57.9
Output levels: -67.9, -71.6, -120.0, -120.0
```

## Useful commands
```
# Set input source to toslink
minidsp source toslink

# Set master volume to -30dB
minidsp gain -- -30

# Activate the 2nd configuration setting (indexing starts at 0)
minidsp config 1
```

## Home Assistant Integration

This fork adds two Home Assistant integration paths: a **native HA OS add-on** that runs the daemon inside your HA supervisor, and a **custom integration** that connects HA to any running daemon (local or remote).

### Home Assistant OS Add-on

The add-on runs `minidspd` as a supervised service. It exposes the HTTP REST API on port 5380 and the TCP protocol server (for MiniDSP mobile/desktop apps) on port 5333. Docker images are built for `aarch64`, `armv7`, and `amd64`.

**Installation:**

1. In Home Assistant, go to **Settings → Add-ons → Add-on Store → ⋮ → Repositories** and add:
   ```
   https://github.com/sb61g2/minidsp-rs
   ```
2. Find **MiniDSP RS** in the store and install it.
3. In the add-on **Configuration** tab, set any options you need:

| Option | Description |
|---|---|
| `log_level` | Logging verbosity (`trace`, `debug`, `info`, `warn`, `error`) |
| `http_bind_address` | HTTP API bind address (default `0.0.0.0:5380`) |
| `tcp_bind_address` | TCP server bind address (default `0.0.0.0:5333`) |
| `widg_ip` | IP address of a Wi-DG network adapter (leave blank for USB-only) |
| `advertise_name` | mDNS advertisement name |
| `advertise_ip` | mDNS advertisement IP |

4. Start the add-on.

### Home Assistant Custom Integration

A HACS-compatible custom integration that talks to any running `minidspd` HTTP API. It provides the following entity types per discovered device:

| Entity type | What it controls |
|---|---|
| `media_player` | Master volume + mute (compatible with dashboard volume cards; 0.5 dB steps) |
| `number` | Master volume slider (−127 dB to 0 dB, 0.5 dB step) |
| `select` | Input source + preset selection |
| `sensor` | Input and output level meters |
| `switch` | Mute and Dirac Live on/off |

**Installation:**

1. Copy `homeassistant-integration/custom_components/minidsp` into your HA config's `custom_components/` directory (or install via HACS as a custom repository).
2. Restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration** and search for **MiniDSP**.
4. Enter the host and port of your running `minidspd` instance (default port `5380`).

## Supported devices
These device support the full feature set. See the [documentation](https://minidsp-rs.pages.dev/devices) for a more complete list.

- miniDSP 2x4HD
- miniDSP Flex
- DDRC-24
- DDRC-88A/D
- miniSHARC series
- miniDSP 2x8/8x8/4x10/10x10
- nanoDIGI 2x8
- SHD series
- C-DSP 8x12 v2
