# Setup and development

An independent, experimental Linux implementation of Logitech Options+ features,
backed by observations of the official application and native device protocol.
Not affiliated with or endorsed by Logitech.

**Status: experimental native device controls for MX Master 4 over Bolt.
This is not a complete Options+ port.**

Verified on hardware: device inspection, DPI write/read/restore, SmartShift
write/read/restore, hardware button remap write/read/restore, and a vibration
physically confirmed by the user. Keyboard inspection also works. Thumb-pad press/release capture is verified. A first GNOME Actions Ring implementation is available; gestures, profiles,
macros, Flow and full ring parity remain unfinished.

Clone the repository and run from its directory. The desktop app needs Python 3,
PyGObject, GTK 4 and libadwaita; the Actions Ring extension currently targets
GNOME 50. Development has been tested on Ubuntu 26.04 with a Bolt receiver.

```sh
git clone https://github.com/enriquemorenotent/logioptions-linux.git
cd logioptions-linux
```

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
app to adjust settings. The ring listener starts automatically at login and keeps running when the window closes. Tap the thumb pad, then click an action; Escape dismisses
it. Holding the pad, moving onto an action, then releasing also selects it.
The eight captured default slots are reproduced, with an empty folder disabled.
Per-app ring profiles support eight slots chosen from the shortcut action library.
Custom shortcuts, submenus and analog controls are not implemented.
See [the ring evidence and checks](../research/ACTIONS-RING.md).

See [the implementation review](../research/REVIEW-2026-10-20.md) for corrections,
test boundaries, Solaar coexistence, and unfinished features.

Direct device inspection (receiver slot numbers depend on your pairing):

```sh
python3 -m logioptions inspect --path /dev/hidraw6 --device-index 2
```

Official binaries and extracted proprietary files stay under the ignored
`artifacts/` directory. Research notes must distinguish observed facts from
hypotheses. An advertised feature is not proof of its protocol or implementation.

Start with [the evidence ledger](../research/EVIDENCE.md) and
[the coverage matrix](../research/COVERAGE.md).
Live Mac observations are in [MAC-RUNTIME.md](../research/MAC-RUNTIME.md).

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

A public checkout does **not** include Logitech's device artwork, fonts, installers,
or the private hardware captures referenced in the research notes. The app uses
system-font/icon fallbacks without the locally extracted UI assets. Tests that
need those research artifacts skip when the files are absent. There is currently
no packaged release or automatic device-permission setup.

The native UI now follows the observed Options+ 2.9 device pages. See
[UI reference and verification](../research/UI-REFERENCE.md) for screenshots,
local asset provenance, and remaining visual/feature differences.

To enable background listening on an existing extension installation, run
`/usr/bin/python3 scripts/install_background.py`. No further logout is needed.
The checkout must stay at its installed path. To disable background listening:
`systemctl --user disable --now logioptions-ring.service`.

Configure ring profiles using the grid button in the app header, or
**Show Actions Ring → Configure per-app ring**. Choose an application and assign
its eight actions. **All apps** is the fallback; **Use All apps** removes an override.
Changes are saved when switching applications or closing the editor, as well as
with **Save profile**. The extension reads the profile at each ring opening and
keeps that choice until the ring closes. The destination window must still be
focused before any shortcut is sent.

Profiles live in `$XDG_CONFIG_HOME/logioptions/ring-profiles.json` (normally
`~/.config/logioptions/ring-profiles.json`). Application matching uses GNOME's
desktop application ID, with a WM_CLASS fallback for unmatched running windows.
After upgrading the extension, log out and back in once to load the new code.
Subsequent profile edits take effect without restarting anything.
