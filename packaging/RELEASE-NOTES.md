LogiOptions 0.1.9 for Ubuntu 26.04 amd64 with GNOME 50.

- Add **Add / manage devices** to the app: inspect paired USB receiver devices,
  pair new devices, and remove a selected pairing after confirmation.
- Support Logi Bolt and Unifying receiver protocols, with keyboard passcodes,
  mouse verification instructions, entry progress, and cancellable pairing.
- Preserve receiver notification settings and coordinate access with the
  background listener during receiver operations.

Successful MX Keys for Business pairing is verified on physical Bolt hardware.
If keypresses arrive but verification times out, reconnecting the receiver before
retrying resolved one observed failure; its underlying cause is unconfirmed.
Physical mouse pairing, removal, and Unifying validation remain pending.

Package installation, reinstall, removal, automated tests, and all 19 isolated
UI tests passed in a clean Ubuntu 26.04 container before release preparation.
The release workflow repeats package checks and verifies signed APT installation.

Upgrade through the GitHub Pages APT repository:

```sh
sudo apt update
sudo apt install --only-upgrade logioptions-linux
```

Quit and reopen LogiOptions after upgrading to load receiver management.
Your saved device settings, ring profiles, and startup preference are preserved.

This remains an experimental release.

Third-party artwork and fonts are not GPL-licensed. Their owners retain all
rights; redistribution permission has not been obtained. See assets/logitech/NOTICE.txt.
Independent project, not affiliated with Logitech. Flow and full Options+ parity
are not implemented. Solaar is not required.

APT setup: https://enriquemorenotent.github.io/logioptions-linux/
