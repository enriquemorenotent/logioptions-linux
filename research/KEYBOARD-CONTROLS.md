# MX Keys for Business controls

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
