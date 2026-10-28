LogiOptions 0.1.8 for Ubuntu 26.04 amd64 with GNOME 50.

- Fix MX Keys for Business occasionally appearing as a strange character followed
  by "BL". Verify device feature replies before using them so a late firmware
  reply cannot be mistaken for the keyboard name.
- Reject invalid device names and retry discovery without interrupting other devices.

Verified with the physical MX Keys for Business and MX Master 4, native UI checks,
and a regression test that reproduces the delayed firmware reply.

Upgrade through the GitHub Pages APT repository:

```sh
sudo apt update
sudo apt install --only-upgrade logioptions-linux
```

Quit and reopen LogiOptions after upgrading to load the fix.
Your saved device settings, ring profiles, and startup preference are preserved.

This remains an experimental release.

Third-party artwork and fonts are not GPL-licensed. Their owners retain all
rights; redistribution permission has not been obtained. See assets/logitech/NOTICE.txt.
Independent project, not affiliated with Logitech. Flow and full Options+ parity
are not implemented. Solaar is not required.

APT setup: https://enriquemorenotent.github.io/logioptions-linux/
