# Saved device settings and recovery

Implemented 2026-10-22. Preferences are private per-user JSON in
`$XDG_CONFIG_HOME/logioptions/devices.json` (normally `~/.config/logioptions/`).
Writes use a mode-0600 temporary file and atomic replacement. Hardware identity
comes from HID++ 0x0003: model bytes 7–12 plus unit bytes 1–4. Invalid or unavailable
identity blocks saving/applying from the GUI; names, receiver slots and hidraw
paths are never used to choose a saved device's preferences.

Apply verifies device readback before saving that setting. Different settings are
merged, and Fn-mode preferences are scoped to the active host. Hardware writes
and preference updates hold the foreground/device lease, so background restoration
cannot read stale preferences halfway through an Apply operation. Saving failure
is reported explicitly, without replacing a malformed preference file.

Supported preferences: DPI; haptic enable/strength; wheel mode/threshold/torque;
individual hardware button mappings; Fn mode; backlight mode, manual brightness,
and delays. Restoration compares before writing, verifies readback and never
plays a vibration. Automatic backlight brightness is sensor-controlled and is
not treated as drift. Only explicitly applied settings are saved, except for the
one-time baseline of the user's already configured mouse/keyboard controls made
when this feature was installed. No legacy Solaar values are imported.

The background service restores at startup and after foreground work. While the
ring listener runs, its five-second health checks reconcile the same receiver on
its owned transport and check other Logitech interfaces. This avoids restarting
or hiding the ring on each maintenance pass. Devices absent/asleep retry on later
passes. Settings still restore when the shell extension is unavailable. Corrupt
preferences are reported without disabling the ring. Device requests may delay
recovery beyond the polling interval; no exact latency guarantee is made.

Validation: offline tests cover saving/merging, wrong identities, per-host Fn
scope, missing devices returning, failed writes, corrupt configuration, ignoring
sensor brightness, and avoiding test pulses. Background tests cover receiver
handoff and restoration without the extension. GTK checks pass. A physical test
changed MX Master 4 DPI temporarily with the GUI closed; the real user service
restored the saved DPI and logged it. Original DPI was verified afterward.
Full fresh-boot, physical unplug/replug, and sleep/wake acceptance remain to be
observed; the temporary drift test is not claimed as evidence of those events.
