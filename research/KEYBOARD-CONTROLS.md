# MX Keys for Business controls

## Garbled device name (2026-10-28)

The reported name `\x01BL` matches the physical keyboard's firmware entity 0
reply exactly: feature `0x0003`, function 1 starts `01 42 4c`. Firmware function
0 starts `03`, so treating firmware as feature `0x0005` reads three name bytes.
The firmware and name feature indices on this keyboard are 2 and 3 respectively.

ROOT lookup replies do not echo the requested feature ID. A delayed firmware
lookup reply arriving after a new name lookup passes the existing header match;
the pre-request queue drain cannot remove a reply that has not arrived yet.
The original incident's traffic was not captured, but a socket regression
reproduces this timing and the physical firmware bytes explain the exact label.

Lookup now verifies every nonzero index using FEATURE SET's reverse lookup
before returning it, retrying mismatches up to three times. Names containing
control characters are rejected, and discovery retries invalid names without
aborting other devices. Live discovery and an isolated native UI check both
showed `MX Keys for Business`, with no device read errors.

Implemented and read/write/restore tested on the physical keyboard, 2026-10-22.

- Host-specific Fn inversion: feature 0x40A3, functions 0/1. Current host is read
  from 0x1815 function 0, byte 3. The response's host and mode are verified.
- Backlight: feature 0x1982 version 3, functions 0 (configuration), 1 (write),
  and 2 (brightness count). This keyboard advertises automatic/manual modes and
  eight brightness levels. Timer units are five seconds; UI uses seconds.
- Read layout: little-endian BBBHBHHH. Write layout: BBBBHHH, preserving the low
  option bits and using 0xff to leave the lighting effect unchanged. Manual mode
  is 3; only manual mode uses the chosen brightness. Off preserves the mode.

Protocol layout was cross-checked against the locally installed Solaar
hidpp20.Backlight and settings_templates.K375sFnSwap implementations, then tested
with independent native requests. This is not a claim of new macOS capture or
support for other keyboard/backlight protocol versions.

Physical checks: standard F keys -> media keys -> standard F keys;
backlight off -> manual level 2 with timers 10/15/65 seconds -> automatic -> off.
Original values were read before changes and restored in finally blocks. Final
backlight state exactly matched the starting state. Private results are in
artifacts/keyboard-controls-validation.json. Readback verifies device settings;
perceived brightness and actual timer duration have not been user-confirmed.

UI shows Function keys and Backlight together in a persistent keyboard settings
panel, without a sidebar or image callouts. Brightness appears only in Manual
mode. Each Apply writes and verifies readback. Existing unrelated settings remain untouched.
Solaar's six overlapping keyboard controls are locally marked ignore, with a
backup of its configuration, preventing it from overwriting app changes.

Applied settings are now saved by hardware identity and restored by the background
service. See [persistence and validation boundaries](SETTING-PERSISTENCE.md).

Discovery correction: a live keyboard identity lookup timed out at 250 ms and
then succeeded at 1 second. Discovery now retries only unanswered/failed slots
with a 1-second timeout after its fast pass. A regression test covers a slow
keyboard, an immediately responding mouse, and an empty slot without duplicates.
A corrected live scan found both devices with no setting-read errors.
