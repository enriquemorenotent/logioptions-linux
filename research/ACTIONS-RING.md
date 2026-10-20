# Actions Ring: first Linux implementation, 2026-10-20

This is an original Linux implementation, not the proprietary UI. Full Options+
parity is unfinished.

## Recovered evidence

`artifacts/mac-live-2.9/mx-master-4-baseline.json`, `/v2/profiles`: the mouse's
CID 416 is assigned SYSTEM/SHOW_RADIAL_MENU. The virtual ring device has CIDs
408–415 assigned Cut, Copy, Paste, Forward, Back, Undo, Redo, and an empty folder.
Mac Command shortcuts are translated to Linux Control shortcuts. Back/Forward
use Alt+Left/Right. These shortcuts depend on the target app's conventions.

Recovered descriptor `0051.json` (`logi/protocol/radial_menu.proto`) defines
ShowMenu PRESS/RELEASE, slot_id, button_name and shown/dismissed/action/hover
notifications. Descriptor `0002.json` (`schema/radial_menu.proto`) includes
submenus, analog/wheel/fusion elements, icons, scale and colors. Those advanced
features are not implemented here. Our angular layout and tap/hold interaction
are implementation choices, not claims of matching observed original behavior.

Physical Linux CID416 press/release reports are recorded in
`artifacts/linux-thumbpad-confirmed-window.json`. `ControlTracker` decodes those
reports, with dynamic feature lookup rather than a hardcoded feature index.

## Implementation

The GNOME 50 extension exports Show/Release/Hide/Ping on the user's session bus,
anchors the menu near the pointer, and uses a modal shell actor. Closing restores
focus; shortcuts are sent only if the original window is still focused and the
session is unlocked. Virtual keyboard events stay inside that compositor.
There is no privileged service or uinput requirement.

`RingListener` owns the receiver while the app is idle. Before device settings
or refresh, the GUI stops and joins the listener and verifies thumb-pad reporting
restoration. It restarts afterwards. Closing the app restores reporting. Thus the
first implementation requires the app to remain open, and temporarily pauses
ring input during settings operations. Device disconnects are reported; refresh
is needed to retry. Abrupt process termination or disconnect can prevent cleanup.

Installation adds only this local extension and its enabled preference. GNOME 50's
installed `shellDBus.js` explicitly rejects ReloadExtension as deprecated;
EnableExtension returns false for an extension absent from its loaded registry.
A logout/login is required for initial installation. The installer does not log
the user out or restart their desktop. No unrelated extension is modified.

## Validation

- `tests/test_ring.py`: captured press/release drives Show/Release; normal exit
  and shell-call failure restore original reporting.
- `scripts/check_ring.py`: private D-Bus, temporary XDG directories, headless GNOME
  50, copied extension, separate GTK target. Renders the actual ring and verifies
  Ctrl+C reaches the original target after selection. Test-only entry points exist
  only in the disposable copy. No HID device is opened by this check.
- Screenshot: `artifacts/ring-check/actions-ring.png`; keyboard events:
  `artifacts/ring-check/ring-keys.log`; logs in the same directory.
- Existing backend and isolated GTK suites still pass.
- Real-session thumb-pad-to-ring acceptance remains pending logout/login. This
  is not yet a claim that all seven actions or every target app are verified.

### Test isolation correction

The initial exploratory headless session put XDG isolation after dbus-run-session.
Its D-Bus activated dconf service inherited the real profile and replaced the
stored enabled-extension list. This was detected against the still-running real
shell's extension registry. Every live enabled extension was preserved alongside
the new ring; the before/repair record is
`artifacts/ring-extension-preferences.json`. The maintained harness now supplies
XDG directories to the bus daemon itself. A repeat passed and left the restored
real enabled-extension list unchanged. No extension source besides this project
was changed.
