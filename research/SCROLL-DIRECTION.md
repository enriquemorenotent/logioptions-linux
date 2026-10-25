# Mouse wheel direction, 2026-10-25

Native controls for MX Master 4: vertical HIRES_WHEEL 0x2121 function 1 read /
function 2 write, bit 2 of byte 0; horizontal THUMB_WHEEL 0x2150 functions 1/2,
bit 0 of byte 1. The installed Solaar settings_templates declarations provided
the field definitions. Native hardware read/write/restore verified both fields.
All unrelated bits (including diversion and resolution) are preserved and full
configuration-byte readback is compared. Captures remain private under artifacts/.

The mouse's initial vertical flag was false and horizontal flag true. Each was
briefly toggled, verified, and restored exactly. Physical perceived direction has
not been user-confirmed; GNOME natural scrolling can also reverse the result.
UI therefore labels choices Standard and Reversed rather than claiming an
absolute content direction.

Controls are in Scroll wheel and Horizontal scroll panels. Apply saves the
verified per-device direction using the existing hardware-identity preference
store; background recovery changes only the direction bit. Solaar's two
corresponding settings are locally ignored, with a config backup. Other Solaar
settings are unchanged. Unit tests cover bit preservation, failed readback,
invalid values, restoration, and the two GTK controls targeting the correct wheel.
