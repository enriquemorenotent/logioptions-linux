# Native UI rebuild against Options+ 2.9

Captured the installed Mac app through its loopback debugger on 2026-10-20.
The mouse remained on Linux; the official app allows viewing its inactive device
pages. Navigated only; no settings were written and no haptic pulses sent.

References in ignored artifacts/:
- options-reference.png and options-reference-dom.json: device home.
- options-device-reference.png and options-device-dom.json: Buttons.
- options-pointandscrollandpress.png and matching DOM: pointer/scroll page.
- options-hapticfeedback.png and matching DOM: haptic summary.
- options-haptic-panel.png and matching DOM: right-hand Modify settings panel.
- options-visual-styles.json: measured fonts, colors and element rectangles.

The original BrownPro font, local icon font and MX Master 4 / MX Keys device
renders are loaded from the user's extracted artifacts. The implementation does
not bundle or redistribute those files. prepare_ui_assets.py converts local
WebP and WOFF2 into formats supported by GTK/Pango. Without these local assets,
the UI falls back to system fonts and icons.

Presentation is rebuilt in native GTK: light background, large device title,
vertically centered feature navigation, actual product render, clickable control
labels and a right-hand settings drawer. The device home opens each device.
Native window controls and draggable header preserve Linux window management.
The old backend's readback checks, explicit Apply and explicit vibration test
remain intact. Applied values refresh the callout summaries.

This is not pixel-identical or feature-complete. Unsupported sections explain
that they are unimplemented. Haptic intensity retains the verified 1–100 control
instead of inventing mappings for Logitech's named presets. Application profiles,
plugins, Flow and other unfinished features are not presented as working.

Validation: 30 backend tests plus 3 isolated GTK tests pass. The existing GTK
interaction tests now open the new drawer before exercising DPI steps and haptic
preview. check_gui.py captures home, Buttons, pointer/scroll, haptic summary and
haptic drawer on an isolated display. Rendering used a freshly read device
snapshot after intermittent discovery misses in the isolated harness; this is
recorded as snapshot-based visual verification, not hardware interaction.
Artifacts: redesigned-*.png, ui-device-snapshot.json, ui-redesign-*.log.

Final visual pass uses final-ui-*.png after fixing canvas minimum-size feedback
and allowing the alpha shadow outside the image allocation. Reopened the actual
GNOME desktop app with live discovery: MX Master 4 found, no read errors; Buttons
page allocated at 1015 by 673 with the device image at (338.5, 84.5). No simulated
device data is used by that running app. MX Keys did not respond during this pass.
