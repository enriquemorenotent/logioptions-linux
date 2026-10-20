# Native Linux HID++ implementation

Official 2.8 x86_64 evidence:

- `devio::Feature::sendFeatureCommandNoReply`, address 0x1001ea7c0:
  feature index at byte 2, function shifted left four bits OR software ID at
  byte 3; initial report ID 0x10, promoted to 0x11 when total exceeds seven bytes.
  The native feature object initially uses target byte 0xff; a receiver transport
  must address the paired device instead.
- `devio::Feature0000Root::GetFeature(unsigned int, Cached)`, 0x1002d1300:
  allocates two parameter bytes, stores feature ID high byte then low byte,
  dispatches root function zero.

`logioptions/hidpp.py` implements short/long HID report framing, nonblocking
Linux hidraw requests, timeout and reply correlation, and feature lookup.
Feature indices are discovered at runtime, never hard-coded from another device.
Protocol 5 / very long reports and receiver pairing are not implemented.

`scripts/linux_probe.py` performs an explicit read-only feature lookup and records
the exact packets. It does not set device configuration.

## Physical thumb-pad events

The official `Feature1B04SpecialKeys::onFeatureReport` x86 function at
0x1003d2bb0 reads four big-endian 16-bit control IDs for function zero.
Zero IDs are empty positions. Linux capture on the MX Master 4 confirmed:

- Press: `11 02 0d 00 01 a0 00 00 00 00 00 00 00 00 00 00 00 00 00 00`
- Release: `11 02 0d 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00`

Control 0x01a0 is the haptic thumb pad. Feature index 0x0d is discovered dynamically.
The capture temporarily enabled diversion, read back flag 1, observed both events,
then restored flag 0 and the original self-mapping with matching readback.
Evidence: `artifacts/linux-thumbpad-confirmed-window.json`.

`logioptions/events.py` tracks pressed/released/held controls and ignores unrelated
features/functions without clearing state. Its bounded capture restores previous
reporting in `finally`, including cancellation. GTK exposes this as an explicit
Test thumb pad action. No host shortcut or Actions Ring is invoked yet.
