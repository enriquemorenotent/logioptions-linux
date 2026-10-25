LogiOptions 0.1.5 for Ubuntu 26.04 amd64 with GNOME 50.

Renames the displayed application to LogiOptions in the launcher, window,
tray, and command-line help. The package remains `logioptions-linux` and
its command remains `logioptions`. Existing settings and startup preferences
are preserved.

Upgrade through the GitHub Pages APT repository:

```sh
sudo apt update
sudo apt install --only-upgrade logioptions-linux
```

Close and reopen the app after upgrading to see the new name.

Third-party artwork and fonts are not GPL-licensed. Their owners retain all
rights; redistribution permission has not been obtained. See assets/logitech/NOTICE.txt.
Independent project, not affiliated with Logitech. Flow and full Options+ parity
are not implemented. Solaar is not required.

APT setup: https://enriquemorenotent.github.io/logioptions-linux/
