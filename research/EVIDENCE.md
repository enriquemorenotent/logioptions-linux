# Evidence ledger

## 2026-10-20: local device enumeration

Read-only `lsusb` and `solaar show` on Ubuntu 26.04.1, GNOME, Wayland.
Solaar 1.1.19-1 is already running; no replacement driver started.

- Bolt receiver: USB `046d:c548`, two paired devices.
- MX Keys for Business: WPID `B380`, HID++ 4.5, 34 reported features,
  21 reported reprogrammable controls (not all divertable).
- MX Master 4: WPID `B042`, HID++ 4.5, 46 reported features,
  9 reported controls (not all divertable).
- Mouse features include HAPTIC `19B0`, FORCE SENSING BUTTON `19C0`,
  REPROG CONTROLS V4 `1B04`, SMART SHIFT ENHANCED `2111`,
  HIRES WHEEL `2121`, THUMB WHEEL `2150`, ADJUSTABLE DPI `2201`.

These are observations through Solaar, not captures of Options+ behavior.
No configuration writes were intentionally requested. Solaar's enumeration
itself issues protocol requests and is not a passive bus capture.

## Official installer provenance

Source page: https://hub.sync.logitech.com/options/post/logi-options-offline-manual-I2a7NSJyE6oH2oy

- Windows: https://download01.logi.com/web/ftp/pub/techsupport/optionsplus/logioptionsplus_installer_offline.exe
- macOS: https://download01.logi.com/web/ftp/pub/techsupport/optionsplus/logioptionsplus_installer_offline.zip

HTTP headers reported 724292760 and 766746738 bytes respectively, with
Last-Modified 2026-09-30. Headers are retained beside downloads. Do not treat
Last-Modified as an application version. Hash only completed downloads.

The official manual's FAQ lists offline omissions including Logi account,
cloud backup, Smart Actions and default-disabled Flow. Consequently offline
installers alone cannot establish complete online feature parity.

## Investigation order

1. Finish acquisition, record SHA-256 and extract containers without executing.
2. Identify app version, executable components, IPC schemas, device databases,
   UI bundles, platform integrations, plugin interfaces and embedded payloads.
3. Obtain the corresponding online payloads for offline omissions.
4. Record runtime process tree, IPC and USB/Bluetooth traffic on a supported OS.
5. Change one setting at a time; retain before/after files and timestamped traces.
6. Implement Linux equivalents against recorded fixtures; verify on real hardware.

No packet meaning, internal architecture, feature parity or successful port is
claimed before the relevant evidence exists.

## Completed static extraction, 2026-10-20

Both offline packages identify version **2.8.981479**, build **876310**.
The online macOS update metadata independently reports **2.9.994631**;
the offline packages therefore do not establish latest-version parity.

Completed original download SHA-256:

- Windows: `bcff70d8a90f2da24116821186b52dafda0e1ac61cb6f558d450b41e212d517a`
- macOS: `28d41efa231019b51f51fa54b650f4fe468c5d0a2869c38cfa622242690a826a`

These are locally computed content hashes, not independently verified vendor
signatures. Original headers and binary inventories remain in `artifacts/`.

Windows outer PE resources include:

- `RCDATA/101/1033`: setup .NET assembly, offset 790460, length 49058968.
- `RCDATA/201/1033`: ZIP package archive, offset 49849428, length 674346987.
- Package archive: 223 entries including `offline.json` and 222 depots.
- Main application depot: 705 file entries, including a repeated analytics config
  path. The extractor preserves the repeated entry separately; no installer
  overwrite semantics are assumed.
- Main Electron ASAR: 581 packed files, including main/preload/renderer bundles.

macOS installer bundle contains `Contents/Resources/depots.zip`.
Main application depot: 1062 entries. Its Electron ASAR has 581 packed files.
Native agent is a separate macOS executable, not JavaScript in the Electron UI.

Plain depot layout `10 01 17 20` was decoded and its exact end offset verified
against the main application, keyboard and system-actions depots. Other depots
use different capsule formats and are not decoded by this plaintext extractor.

First compatibility implementation: [IPC framing](IPC.md). Differential tests
compare the Python sender with the recovered official JavaScript sender on both
platforms. Three test methods pass, including both platform subtests.

Mac access is available according to the user. Remote access method and runtime
captures are still pending. `scripts/mac_collect.sh` prepares a baseline without
changing the running app or devices; syntax checked on Linux, not yet run on Mac.
