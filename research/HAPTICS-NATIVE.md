# Native haptics investigation

Evidence: downloaded macOS 2.8.981479 agent, x86_64 slice. Native symbols and
disassembly are retained under `artifacts/`.

| devio::Feature19B0HapticFeedback method | Address | Dispatch selector |
| --- | --- | --- |
| getCapabilities | 0x10039f0d0 | 0 |
| getHapticConfig | 0x10039fcd0 | 1 |
| setHapticConfig | 0x1003a08d0 | 2 |
| getHapticInfo | 0x1003a1540 | 3 |
| playHapticWaveForm | 0x1003a2140 | 4 |
| stopHapticWaveForm | 0x1003a2da0 | 5 |
| getPlayingWaveForm | 0x1003a39a0 | 6 |

Selectors and parameter bytes are observed at native dispatch calls. The seven
command builders are compared against original x86 machine code under Unicorn
by `scripts/haptic_native_oracle.py` and `tests/test_haptics.py`.

`playHapticWaveForm` creates two parameter bytes: waveform ID's low byte, then its
boolean argument. It dispatches selector 4. On the physical Linux Bolt mouse,
feature 19B0 resolves to index 11; waveform 7 produces report
`10 02 0b 4e 07 00 00`. The mouse replied, and the user confirmed feeling the
warned retry. Evidence: `artifacts/linux-mx-master-4-haptic-play-retry.json` and
its traffic recording. This verifies that waveform on this device and transport.

`setHapticConfig` combines the configuration's first byte with bit 1 when its next
byte is true. Its second parameter byte is the low byte of the referenced integer
argument. Semantic names, valid ranges and persistence remain under investigation.

The recovered haptics descriptor defines global/per-event enablement, feedback
level, power saving, waveform capabilities/execution and breathing exercises.
Per-event haptics and force sensing integration remain unfinished. A successful
waveform does not establish full Options+ haptic behavior or device coverage.
