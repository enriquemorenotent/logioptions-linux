# Options+ for Linux — reverse engineering workspace

Goal: a Linux implementation backed by observations of the official Logitech
Options+ application, including its device protocol and desktop behavior.

**Status: experimental native device controls for MX Master 4 over Bolt.
This is not a complete Options+ port.**

Verified on hardware: device inspection, DPI write/read/restore, SmartShift
write/read/restore, hardware button remap write/read/restore, and a vibration
physically confirmed by the user. Keyboard inspection also works. Thumb-pad press/release capture is verified. A first GNOME Actions Ring implementation is available; gestures, profiles,
macros, Flow and full ring parity remain unfinished.

Launch the GTK 4 desktop app using the system Python with GTK/libadwaita bindings:

```sh
/usr/bin/python3 -m logioptions gui
```

It reads connected devices on startup. Settings change when you click Apply;
Apply and test vibration sends a pulse. The development app currently requires existing
read/write access to the Logitech hidraw interface. It has no installer yet.

The haptic preview is **Apply and test vibration**: it writes the selected
strength, verifies the mouse's response, then plays one pulse. A physical
10%/90% comparison was confirmed by the user on 2026-10-20.

Actions Ring on GNOME 50: install the extension with
`/usr/bin/python3 scripts/install_ring.py`, then log out and back in. Launch this
app and keep it open. Tap the thumb pad, then click an action; Escape dismisses
it. Holding the pad, moving onto an action, then releasing also selects it.
The eight captured default slots are reproduced, with an empty folder disabled.
Custom menus, analog controls and app-specific ring profiles are not implemented.
See [the ring evidence and checks](research/ACTIONS-RING.md).

See [the implementation review](research/REVIEW-2026-10-20.md) for corrections,
test boundaries, Solaar coexistence, and unfinished features.

Direct device inspection (receiver slot numbers depend on your pairing):

```sh
python3 -m logioptions inspect --path /dev/hidraw6 --device-index 2
```

Official binaries and extracted proprietary files stay under the ignored
`artifacts/` directory. Research notes must distinguish observed facts from
hypotheses. An advertised feature is not proof of its protocol or implementation.

Start with [the evidence ledger](research/EVIDENCE.md) and
[the coverage matrix](research/COVERAGE.md).
Live Mac observations are in [MAC-RUNTIME.md](research/MAC-RUNTIME.md).

`python3 scripts/inventory.py PATH --output artifacts/inventory.json` records
file hashes and sizes for an original installer or an extracted tree.

The static extraction tools are `scripts/pe_resources.py`,
`scripts/unpack_depot.py` and `scripts/unpack_asar.py`. They do not launch
the inspected applications. Extracted files and per-file inventories remain local.

`python3 -m unittest discover -s tests -v` validates the first recovered
frontend-to-agent framing component. When both extracted UI bundles are present,
the differential check uses the actual Windows and macOS sender functions.

Install `requirements-research.txt` in a virtual environment to use the native
descriptor recovery and strict schema validator. Run the full evidence checks
with `.venv/bin/python -m unittest discover -s tests -v`.

For the available Mac, `bash scripts/mac_collect.sh` collects a local baseline.
It prints a ZIP path to review and transfer. It does not upload anything or
change running applications. This baseline does not capture protocol traffic.

Do not run original installers against the everyday Linux desktop or assume Wine
implements Logitech's drivers. Runtime investigation needs an isolated Windows
or macOS environment with the relevant hardware and permission to capture it.

The native UI now follows the observed Options+ 2.9 device pages. See
[UI reference and verification](research/UI-REFERENCE.md) for screenshots,
local asset provenance, and remaining visual/feature differences.
