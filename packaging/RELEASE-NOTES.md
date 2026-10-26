LogiOptions 0.1.7 for Ubuntu 26.04 amd64 with GNOME 50.

- Assign common actions, recorded keyboard shortcuts, desktop actions, or Actions
  Ring to supported mouse buttons. Assignments currently apply to all apps.
- See button assignments on the mouse image, with connector lines and matching
  highlights. Labels adapt when the settings panel opens or the window resizes.
- See responding, unavailable, and disconnected devices with the age of their
  last battery reading. Unavailable devices remain visible with read-only controls.
- Inspect background services, GNOME extension readiness, and device communication
  in App settings. Restart the listener there without changing login startup.

Upgrade through the GitHub Pages APT repository:

```sh
sudo apt update
sudo apt install --only-upgrade logioptions-linux
```

**Log out of Ubuntu and back in once after upgrading** to load the updated GNOME
extension. Later button assignment edits do not require another login.
Your saved device settings, ring profiles, and startup preference are preserved.

This remains an experimental release. New direct button actions pass automated
listener and native UI checks; physical end-to-end mouse verification is pending.

Third-party artwork and fonts are not GPL-licensed. Their owners retain all
rights; redistribution permission has not been obtained. See assets/logitech/NOTICE.txt.
Independent project, not affiliated with Logitech. Flow and full Options+ parity
are not implemented. Solaar is not required.

APT setup: https://enriquemorenotent.github.io/logioptions-linux/
