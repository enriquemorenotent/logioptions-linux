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

The user service `logioptions-ring.service` now owns `RingListener`, independent
of the settings window. It starts with the graphical session and stops on logout.
The GUI holds a foreground request and waits for the background device lease;
the service stops and joins its listener, restoring thumb-pad reporting, before
releasing that lease. It resumes after the operation, including failed operations.
The service retries when GNOME or the mouse is unavailable, or its reader exits.
Closing the settings window does not stop background listening. No root service
or additional device permissions are installed.

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

### Background service validation, 2026-10-21

The extension reports ACTIVE and its session-bus Ping returns ready after login.
The user service is enabled on graphical-session.target. On the real receiver,
opening the settings app releases the listener for discovery and the service
reports ready again afterward. Closing the app leaves the service holding the
HID interface with its actions-ring thread alive. Automated tests cover the
foreground handoff, missing shell/device retries, and dead-listener recovery;
the four isolated GTK checks pass. Physical thumb-pad acceptance remains a user
check; this does not claim a future login has already been tested.

### Per-application rings, 2026-10-21

The native editor stores eight action IDs per desktop application plus a default
layout, using validated atomic JSON replacement. The shell resolves the focused
window before taking a modal grab, prefers Shell.WindowTracker desktop IDs, and
falls back to an exact WM_CLASS key. The selected action list is frozen for each
open ring. Missing, malformed, or invalid profiles fall back safely. Shortcuts
remain constrained to the original focused window. No arbitrary commands execute.

The isolated GNOME check verifies default Ctrl+C delivery, an actual window's
application-specific Ctrl+S delivery, override removal, and malformed-file fallback.
Pure selection tests cover distinct app IDs, WM_CLASS fallback, invalid slots, and
unknown config versions. GTK tests exercise editing, saving, switching, and removal.
The current desktop requires one logout/login to load extension version 2; profile
edits thereafter are read on each ring opening. Background operation was physically
confirmed by the user before this change.
