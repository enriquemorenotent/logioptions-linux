LogiOptions 0.1.6 for Ubuntu 26.04 amd64 with GNOME 50.

Fixes keyboard backlight Off failing to save when the keyboard resets inactive
brightness, mode, or delay values. Off now verifies the disabled state and
replaces the saved setting, so the background service cannot restore an older
Manual preference. Already disabled backlights are left alone during restoration.

Upgrade through the GitHub Pages APT repository:

```sh
sudo apt update
sudo apt install --only-upgrade logioptions-linux
```

Quit and reopen LogiOptions after upgrading. No new login is required for this fix.

Third-party artwork and fonts are not GPL-licensed. Their owners retain all
rights; redistribution permission has not been obtained. See assets/logitech/NOTICE.txt.
Independent project, not affiliated with Logitech. Flow and full Options+ parity
are not implemented. Solaar is not required.

APT setup: https://enriquemorenotent.github.io/logioptions-linux/
