# Runtime experiments needed for parity

Use the exact version recorded in each installer inventory. Retain the OS build,
Options+ version, connection transport, device firmware and experiment ID.
Capture on a test profile; traces of clipboard, Flow and macros may contain
whatever test content was used.

For each experiment:

1. Record process tree, listening endpoints, loaded modules and configuration files.
2. Begin USB capture (Windows: USBPcap/Wireshark for the Bolt receiver).
   USB captures do not establish Bluetooth behavior; test that transport separately.
3. Record the initial UI value and the device's initial response.
4. Change exactly one control to one new value; timestamp the change.
5. Record UI-to-agent messages, agent-to-device requests and device responses.
6. Repeat with a different value and restore the initial value.
7. Restart Options+, reconnect the device and reboot separately to test persistence.

First experiments for available devices:

| Experiment | Change | Required distinction |
| --- | --- | --- |
| M01 | Pointer speed through three values | Desktop acceleration versus device DPI |
| M02 | SmartShift enable and threshold | Mode, threshold and ratchet torque |
| M03 | Vertical wheel speed/direction/smooth scrolling | Device setting versus software event processing |
| M04 | Thumb wheel direction and action | Device setting versus diverted notifications |
| M05 | Each remappable button, one at a time | Control ID, diversion, host action and restore |
| M06 | Gesture press and each direction | Motion thresholds, timing and cancellation |
| M07 | Actions Ring open/select/cancel | Button events, pointer handling and haptic sequence |
| M08 | Haptic intensity and each effect | Waveform selection, force threshold and persistence |
| K01 | Fn inversion | Device write and reconnect persistence |
| K02 | Backlight and timers | Units, ranges and power-state behavior |
| K03 | Each remappable key | Fn state, control ID and host action |
| A01 | Switch between two application profiles | Foreground-app matching and restoration |
| A02 | Smart Action with test keystrokes/delays | Execution ordering, cancellation and persistence |
| F01 | Flow between two supported computers | Discovery, pairing, encryption, switching, clipboard and files |
| C01 | Settings export/restore and account sync | Local format versus authenticated server behavior |

Replay fixtures should contain the smallest relevant protocol exchange plus an
expected outcome. Unknown messages remain unknown until experiments explain them.
