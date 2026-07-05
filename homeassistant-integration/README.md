# homeassistant-integration

Source for the MiniDSP RS custom integration.

## Distribution

The canonical HA distribution of this integration lives in a separate repo:
**[sb61g2/ha-minidsp-rs](https://github.com/sb61g2/ha-minidsp-rs)**

That repo is what users add to HACS and the add-on store. It also contains the
HAOS add-on config and the watchdog Blueprint.

## Keeping repos in sync

Changes to `custom_components/minidsp/` in this directory must be mirrored to
`ha-minidsp-rs/custom_components/minidsp/` (and vice versa) — there is no
automated sync. See `ha-minidsp-rs/CONTRIBUTING.md` for the copy commands and
design notes on the WebSocket coordinator.
