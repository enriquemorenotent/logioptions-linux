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
need those research artifacts skip when the files are absent. The Debian package includes device-access rules and session startup.

The native UI now follows the observed Options+ 2.9 device pages. See
[UI reference and verification](../research/UI-REFERENCE.md) for screenshots,
local asset provenance, and remaining visual/feature differences.

To enable background listening and the tray icon on an existing extension installation, run
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

Device settings applied in the GUI are saved to
`~/.config/logioptions/devices.json` (or under `$XDG_CONFIG_HOME`). The background
service checks and restores them by hardware identity, including devices waking
after startup. No test vibration is played during restoration. Fn settings are
scoped to the active host; automatic backlight brightness remains sensor-driven.
See [validation and implementation details](../research/SETTING-PERSISTENCE.md).

### Tray icon

The installer enables `logioptions-tray.service` for graphical sessions. It uses
GTK 3 and Ayatana AppIndicator in a separate process from the GTK 4 settings UI.
Dependencies on Ubuntu: `gir1.2-ayatanaappindicator3-0.1`, `gir1.2-gtk-3.0`,
and an enabled AppIndicator shell extension (Ubuntu includes one).
Closing settings leaves both the tray and background listener running.
To disable only the tray: `systemctl --user disable --now logioptions-tray.service`.

Battery readings come from the existing receiver owner, refreshed every minute.
The tray never opens HID devices or pauses the ring. Readings older than 90 seconds
are marked last known; service status is checked every five seconds. The tray's
Open settings action uses GApplication activation, reopening or focusing the UI.

The tray uses theme-aware monochrome symbolic icons. A steady warning badge appears
when the background service is stopped or a fresh battery reading is 20% or less.
Old battery readings do not trigger warnings; percentages stay in the menu.

### Debian package and signed updates

`python3 scripts/build_deb.py` builds `dist/logioptions-linux_VERSION_all.deb`.
The public package includes only Python sources, original symbolic icons, and the
GNOME extension. Extracted assets and private captures are excluded. Native files
live under `/usr/lib/logioptions-linux`, with the `logioptions` launcher in `/usr/bin`.

The package targets Ubuntu 26.04 with GNOME 50. The APT repository currently
advertises amd64; the Python payload itself is architecture-independent. Running
`logioptions session` as the desktop user activates services and the extension;
the launcher does this on first open and the session autostart repeats it at login.
Recognized source-install overrides are backed up under
`~/.config/logioptions/source-install-backup` so packaged units can take over.
Device settings and ring profiles remain in their existing user directory.

The manually dispatched release workflow tests package install/reinstall/removal,
installed Python tests, isolated GTK controls, and signed APT installation before
publishing the exact tested `.deb` to GitHub Releases and the repository to Pages.
Set VERSION to a new semantic version before each release. Required repository
secrets are LOGIOPTIONS_APT_GPG_KEY_ID (full fingerprint),
LOGIOPTIONS_APT_GPG_PRIVATE_KEY, and LOGIOPTIONS_APT_GPG_PASSPHRASE.
The signing key is separate from Pulsete's. Unsigned repository builds fail.
Installing a downloaded `.deb` does not silently add an APT source; follow the
Pages setup instructions to opt into updates.

### Launchpad PPA source builds

The project code is GPL-3.0-only. `LICENSE` and `packaging/copyright` are included
in both package formats. The PPA is `ppa:enriquemorenotent-gmail/logioptions-linux`. Launchpad builds
packages from signed source uploads for Ubuntu Resolute. Version
`0.1.0-0ubuntu1~ppa1` is published. Adding the PPA and installing the package were
verified in a clean Ubuntu 26.04 container, including signature verification,
dependency installation, CLI startup, and the installed service/extension files.
This container check does not test a graphical login or physical devices.

With Debian packaging tools (`build-essential`, `debhelper`, `dpkg-dev`, Python 3,
and Node.js for the protocol/profile tests), prepare a source-only upload:

```bash
python3 scripts/build_source.py --maintainer 'Your Name <your-verified-launchpad-email>'
```

This creates a source upload under `dist/ppa`, using an explicit source allowlist.
Private captures, extracted artwork, screenshots, keys, and Git history are not
included. Launchpad rebuilds the binary using `packaging/ppa/rules` and the same
payload staging code used by the standalone `.deb` builder. The local source
build is unsigned; publication requires a registered Launchpad signing key:

```bash
debsign -k YOUR_REGISTERED_KEY dist/ppa/*_source.changes
dput ppa:enriquemorenotent-gmail/logioptions-linux dist/ppa/*_source.changes
```

Use the exact `.changes` filename when multiple versions are present. Confirm
the corresponding source and binary publication on Launchpad before changing
public installation instructions. Existing GitHub releases remain available.
