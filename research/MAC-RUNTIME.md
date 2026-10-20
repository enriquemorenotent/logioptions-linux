# Mac runtime observations — 2026-10-20

SSH access verified to the user's Mac mini: macOS 26.6.1, arm64. No password
was requested or received. Hardware connection is Bluetooth.

## Version boundaries

Initial installed frontend/agent: 1.32.363144. During investigation both changed
to 1.44.415778 and restarted. Captures are separated under
`artifacts/mac-live-1.32/` and `artifacts/mac-live-1.44/`.

The downloaded online installer identifies 2.8.981479, with Logitech Developer ID
signature (team QED4VVPZWA) and stapled notarization ticket. It was opened on the
Mac; installation completion is pending the user.

## Original UI and agent

The 1.32 UI includes `app.js.map` with 1220 embedded sources. The legacy transport
matches its compiled bundle and uses `FARS` instead of 2.8's length prefix.

The official interface connects successfully. Standalone Python connections were
closed immediately, including the legacy-framed numeric-ID probe. Cause unknown.
The newer native agent has signature-validation and rejection strings, but those
alone do not prove why the old agent disconnected our client.

The original UI was reopened with its debugger bound to 127.0.0.1:19222. The probe
uses that UI's existing connection for GET requests. No agent checks were patched.
No profile, firmware or pairing writes were requested by the probe.

## Captures

1.32 successful GET: `/devices/list`, `/configuration`, `/permissions`.

1.44 successful GET: `/devices/list`, `/battery/dev00000000/state`,
`/smartshift/dev00000000/params`, `/v2/profiles`.

`/devices/dev00000000/easy_switch` returned `NO_SUCH_PATH`. A frontend declaration
does not prove a route works for every device/version.

MX Master 3 became ACTIVE. Subsequently the Mac reported MX Master 4 PRESENT over
BLE with `supported: false`. The user confirmed connecting MX Master 4. A newer
agent is needed before testing its supported behavior.

## Schemas and implementation

Recovered 57 proto3 descriptors from the live 1.44 agent. All four successful
payload captures strictly validate against the version-matched schemas.

Recovered 83 proto3 descriptors from the downloaded 2.8 agent, with every
dependency present and identical copies in both architecture slices. Offsets and
hashes are indexed. Old payload fields fail strict newer-schema validation;
version boundaries must remain explicit.

The 1.32 source-map index has 126 literal routes and 160 matched call sites.
This is lexical evidence, not exhaustive JavaScript analysis.

Python supports both framing versions, request/response matching and strict
recovered-schema validation. Eight test methods pass with research dependencies
and local evidence. Native Linux control and full parity remain incomplete.
