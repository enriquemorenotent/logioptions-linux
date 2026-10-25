# Options for Linux

**Your Logitech mouse. More at home on Linux.**

A native Linux app bringing familiar Options+ controls to your desktop—starting
with the MX Master 4. Adjust how your mouse feels, tune its scrolling, and explore
haptic feedback from one place.

![Options for Linux showing MX Master 4 button controls](docs/screenshots/mx-master-4-window.png)

*The native GTK app. Device artwork and fonts come from Logitech Options+;
these third-party assets are separate from the GPL-licensed application code.*

## Make your mouse feel right

- **Pointer speed:** adjust your mouse’s DPI.
- **Scrolling:** control wheel mode and SmartShift, plus vertical and thumb-wheel direction.
- **Buttons:** inspect and change supported button mappings.
- **Haptics:** adjust vibration strength and feel a preview.
- **Keyboard:** choose F1–F12 or media keys, and adjust MX Keys for Business backlighting.
- **Tray access:** reopen settings, see both batteries, and check background service status from the top bar.
- **Remembered settings:** applied changes are saved and restored by the background service.
- **Device status:** see your connected devices and battery levels.
- **Actions Ring:** an experimental GNOME extension for shortcuts at your thumb,
  with a background listener that starts at login—even with the app closed.
- **Per-app rings:** choose eight actions for each app, with an All apps fallback.

## Built from real devices

This project began with an MX Master 4, a Linux desktop, and a Mac running the
original Options+ app. Its controls are built from observed application behavior,
reverse engineering, and direct device communication.

Mouse controls and haptic intensity have been tested on an MX Master 4 over Bolt.
MX Keys for Business also supports battery readings, function-key mode, and backlight controls. The Actions Ring
works in the tested GNOME desktop session, including after a restart.

## Try the early build

**This is a working experiment, not yet a complete Options+ replacement.**
Broader device profiles, Flow, macros, keyboard customization, and full Actions Ring parity are
still unfinished.

### Install on Ubuntu

**Requires Ubuntu 26.04 (amd64) with GNOME 50.** The package includes the tray,
background service, GNOME extension, and device-access rules. Solaar is not required.

Install with automatic updates:

```bash
curl -fsSL https://enriquemorenotent.github.io/logioptions-linux/install.sh | sudo bash
```

Open **Options for Linux** from the app launcher. **Log out of Ubuntu and back in**
after first-time setup to load Actions Ring. The tray and background service then
start at login; you can close the settings window and keep using the ring.

The setup script adds our signed GitHub Pages APT repository and installs the app.
[Review the script](scripts/setup_repository.sh). Updates then arrive through
Ubuntu’s normal package updates.

**Moving from the PPA?** Run the same command once. It disables our old PPA,
keeps a backup, and switches you to GitHub Pages without changing your settings.
The PPA no longer receives releases.

Alternatively, download the `.deb` from
[GitHub Releases](https://github.com/enriquemorenotent/logioptions-linux/releases)
and open it with Ubuntu’s software installer. Installing the downloaded `.deb`
alone does not add an update repository.

**[Setup and development guide →](docs/DEVELOPMENT.md)**

## From the terminal

- `logioptions` or `logioptions gui` — open the app.
- `logioptions --version` — show the installed version.
- `logioptions status` — show background services and latest device readings.
- `logioptions --help` — list commands, including advanced device tools.

## Help shape what comes next

Have a Logitech device you’d like supported, or a feature you miss on Linux?
[Open an issue](https://github.com/enriquemorenotent/logioptions-linux/issues)
with your device model, Linux distribution, and what you’d like to do.

Curious about the implementation? Explore the [research notes](research/EVIDENCE.md)
and [feature coverage](research/COVERAGE.md).

---

Independent project. Not affiliated with or endorsed by Logitech. Official
installers and private hardware captures are not bundled.

## License

Copyright © 2026 Enrique Moreno Tent and contributors. The original application
code, packaging, tests, and original icons are licensed under
[GNU GPL version 3 only](LICENSE) (`GPL-3.0-only`). This license does not cover
Logitech trademarks or the third-party artwork and fonts bundled in
`assets/logitech`. Those assets retain their owners’ rights; no redistribution
permission has been obtained. See [asset notices](assets/logitech/NOTICE.txt).
