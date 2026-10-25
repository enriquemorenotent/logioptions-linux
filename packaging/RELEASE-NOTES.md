Options for Linux 0.1.2 for Ubuntu 26.04 amd64 with GNOME 50.

- Makes command-line help describe the desktop app and mark device tools as advanced.
- Adds `logioptions --version` and `logioptions status`.
- Opens the app when no command is supplied.
- Shows service status and cached device readings without interrupting the ring.
- Keeps `gui --help` from starting background services.

For existing PPA users, run `sudo apt update` and then
`sudo apt install --only-upgrade logioptions-linux`.

Install the .deb, then open Options for Linux. A first-time extension installation
needs a logout/login. Saved device settings and ring profiles stay in place.

Third-party artwork and fonts are not GPL-licensed. Their owners retain all
rights; redistribution permission has not been obtained. See assets/logitech/NOTICE.txt.
Independent project, not affiliated with Logitech. Flow and full Options+ parity
are not implemented. Solaar is not required.

APT setup: https://enriquemorenotent.github.io/logioptions-linux/
