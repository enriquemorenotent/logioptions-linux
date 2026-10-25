Options for Linux 0.1.4 for Ubuntu 26.04 amd64 with GNOME 50.

GitHub Pages is now the sole active APT repository. The setup command installs
the signed repository and migrates the former PPA:

```sh
curl -fsSL https://enriquemorenotent.github.io/logioptions-linux/install.sh | sudo bash
```

Includes Quit in the tray, improved CLI help, --version, status, configurable
login startup, and device visuals. Saved settings stay in place.

Third-party artwork and fonts are not GPL-licensed. Their owners retain all
rights; redistribution permission has not been obtained. See assets/logitech/NOTICE.txt.
Independent project, not affiliated with Logitech. Flow and full Options+ parity
are not implemented. Solaar is not required.

APT setup: https://enriquemorenotent.github.io/logioptions-linux/
