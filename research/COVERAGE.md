# Full feature coverage tracking

This is a development record, not a claim of complete Options+ parity.
Hardware available: MX Master 4 and MX Keys for Business. Evidence is local under
`artifacts/`; proprietary extracted binaries are not distributable implementation.

| Area | Linux implementation | Acceptance evidence / remaining work |
| --- | --- | --- |
| Device discovery and inspection | Direct hidraw, dynamic feature lookup, GTK device list | Both devices inspected on Bolt; Bluetooth and reconnect recovery unverified |
| DPI | Advertised range reader, setter, GTK control | Physical 1000 → 1050 → 1000 readback |
| SmartShift | Raw settings reader/setter, wheel mode UI | Physical threshold 12 → 13 → 12 readback; full automatic behavior unfinished |
| Hardware button remapping | Control table, group validation, setter, current mapping UI | Back → Forward → Back readback; physical click behavior unverified |
| Haptics | Seven native command builders, configuration UI, explicit test pulse | Original native machine-code differential; user confirmed Linux waveform 7 and clearly stronger 90% versus 10% preview |
| Button events, gestures, force sensing, Actions Ring | Native press/release decoder, persistent listener, GNOME 50 ring and seven Linux shortcuts | Thumb-pad capture verified physically; ring render and Ctrl+C delivery verified in isolated GNOME. Current desktop activation needs logout/login; customization and full parity unfinished |
| Application profiles | Official profile APIs recovered | Linux profile engine unfinished |
| Keyboard customization, backlight, Fn | Host-specific Fn mode; backlight mode, level and three timers for 0x1982 v3 | MX Keys for Business read/write/restore verified; see [keyboard controls](KEYBOARD-CONTROLS.md). Reconnect persistence and other keyboard customization unfinished |
| Smart Actions, macros, scheduling | Research only | Unfinished |
| Flow, clipboard and file transfer | Research only | Unfinished |
| Pairing and host switching | Research only | Unfinished |
| Account, backup, restore | Research only | Unfinished |
| Plugins and application integrations | Research only | Unfinished |
| Firmware updates | Research only | Unfinished |
| Installation, autostart, localization, accessibility | Development GTK app | No packaged release; full acceptance unfinished |

Checks: 30 passing offline tests plus 3 isolated GTK tests cover captured device traffic replay, official
frontend framing, version-matched protobuf validation, and original native
haptic builders. An isolated GTK render verified the live mouse and current mapping reads. The isolated GNOME ring check verifies rendering and Ctrl+C delivery to the original test window.
Physical thumb-pad-to-ring acceptance in the real desktop remains pending activation.

The full implementation review and remaining risks are in [REVIEW-2026-10-20.md](REVIEW-2026-10-20.md).
