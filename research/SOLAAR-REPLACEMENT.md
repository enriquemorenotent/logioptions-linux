# Solaar replacement checklist for this PC

Inspected 2026-10-22. This is a comparison of the installed Solaar configuration,
installed implementation, and our current source. Saved values below are not a
claim of a fresh hardware read or proof of which settings the user actively uses.
No device settings or Solaar startup preferences were changed during this audit.

## Current devices

| Area | Solaar's saved configuration | Our app | Work before replacement |
| --- | --- | --- | --- |
| MX Keys function row | fn-swap false: standard F1–F12 without Fn | No customization | Read/write/verify Fn mode; preserve preference across reconnect |
| MX Keys backlight | Disabled (255); level 0; saved timer values 6/3/60 | No controls | Backlight mode, level, timers; verify units and device behavior |
| Keyboard platform and disabled keys | Platform 0; no keys disabled | No controls | Verify platform meaning and offer supported controls; default values need not imply custom user requirements |
| Mouse DPI, haptics, button mapping | Seven overlapping settings marked ignore | Native reads/writes; haptic strength physically confirmed | Persist desired settings and safely restore after reconnect; verify button behavior |
| SmartShift and wheel torque | Solaar ignores these for this mouse | Raw setter supports mode/threshold/torque; UI exposes wheel mode | Complete threshold/torque controls and persistence |
| Vertical scrolling | hires-scroll-mode false, invert false, resolution false; not ignored | Not implemented | Decode supported wheel modes/direction/resolution and provide controls |
| Thumb wheel | invert false, mode false; not ignored | Placeholder | Implement direction and mode |
| Thumb-pad force sensitivity | Saved raw value 5935; not ignored | Not implemented | Recover units/range and verify read/write/restore |
| Actions Ring | No custom rules.yaml found | Background listener and per-app editor | Fresh-session acceptance; current shell still reports extension version 1 |
| Pairing and host switching | change-host null; no saved host switch requested | Not implemented | Pair/unpair needed for full receiver-manager replacement, but not for using already-paired devices |
| Device access | Installed /usr/lib/udev/rules.d/60-solaar.rules grants hidraw access | Relies on existing access | Ship appropriate device rules before uninstalling the Solaar package |

Other saved entries include older MX Master 3 and MX Keys devices; their presence
in the config does not establish that they remain connected or in use.

## Coexistence now

The installed Solaar apply_all_settings skips only settings whose sensitivity is
literally `ignore`. False is not an instruction to leave a setting untouched.
Our mouse's ignored keys are dpi, haptic-level, reprogrammable-keys, divert-keys,
scroll-ratchet, scroll-ratchet-torque, and smart-shift. Remaining settings can
still be applied by Solaar. Its global autostart entry starts it hidden at login.

## Recommended order

1. Implement and verify keyboard Fn mode and backlight controls.
2. Add persistent desired settings and recovery after login/reconnect, with
   explicit ownership of each setting so Solaar and our service do not compete.
3. Complete mouse scrolling, SmartShift/torque, and thumb-pad sensitivity controls.
4. Verify a real fresh login with the GUI closed, then a receiver reconnect and
   mouse sleep/wake. The running session's boot time is 2026-10-21; today's audit
   cannot substitute for a new-login test. No automatic logout was performed.
5. Disable Solaar autostart for a reversible trial, preserving its configuration
   and installed device-access rules. Only after acceptance consider uninstalling
   the package, with our own device permissions installed first.

Pairing UI and broader device support are additional requirements for replacing
Solaar generally; they do not block a trial with the user's already-paired devices.
