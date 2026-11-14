# USB receiver pairing

This implements the receiver-management part of replacing Solaar. It does not
require Solaar to be installed or running. Bluetooth pairing remains in the
system Bluetooth settings; host/channel switching is a separate feature.

## Implementation

- `receiver.py` adds HID++ 1.0 register access alongside the existing HID++ 2.0
  device transport. Receiver-register reads and notifications have different
  framing/correlation rules from peripheral feature calls.
- Supported USB product IDs: Bolt `046d:c548`, Unifying `046d:c52b` and
  `046d:c532`. Other Logitech receiver families are deliberately not assigned
  a guessed pairing protocol.
- Slot inventory comes from the receiver, so asleep or disconnected paired
  devices can be listed and removed. Unpairing rechecks the receiver serial and
  the selected slot's hardware token, then confirms that the slot is empty.
- `pairing.py` implements bounded discovery, cancellation, Bolt device selection
  and physical authentication, and Unifying pairing. Bolt keyboards use a
  six-digit passcode; mice use a ten-click left/right sequence followed by both
  buttons together. Receiver completion and slot information establish success.
- Notification flags are preserved. Active discovery/pairing is cancelled on
  exit; cleanup failures are reported. No saved device preferences are deleted.
- `receiver_ui.py` runs receiver operations on a worker under the existing
  foreground lease. The background button listener restores diverted controls
  before yielding the receiver and resumes afterward. Closing the window cancels
  a pending pairing flow and waits for cleanup.

## Protocol provenance

The register numbers, packet fields, device authentication and notification
formats were checked against the upstream Solaar implementation at commit
`e7304c4c451cc9bb4f206a914844525e67856a28`:

- [Receiver operations](https://github.com/pwr-Solaar/Solaar/blob/e7304c4c451cc9bb4f206a914844525e67856a28/lib/logitech_receiver/receiver.py)
- [Notifications](https://github.com/pwr-Solaar/Solaar/blob/e7304c4c451cc9bb4f206a914844525e67856a28/lib/logitech_receiver/notifications.py)
- [Transport framing](https://github.com/pwr-Solaar/Solaar/blob/e7304c4c451cc9bb4f206a914844525e67856a28/lib/logitech_receiver/base.py)
- [CLI verification instructions](https://github.com/pwr-Solaar/Solaar/blob/e7304c4c451cc9bb4f206a914844525e67856a28/lib/solaar/cli/pair.py)

Solaar is Copyright Daniel Pavel and Solaar contributors, GPL-2.0-or-later.
The new LogiOptions implementation uses the project's GPL-3.0-only license.

## Validation and limits

On Jupiter's physical Bolt receiver, read the receiver identity and all six
slots, identified MX KEYS B and MX Master 4, started device discovery and
cancelled it. Verified that notification flags and paired-device inventory were
unchanged afterward. This caught an important wire-format distinction: a long
register **read** uses a short request packet; a long register **write** uses a
long packet even with a short payload.

Automated tests cover packet framing, stale slot replies, queued notifications,
Bolt mouse/keyboard verification, user confirmation, cancellation, timeouts,
cleanup errors, Unifying completion, receiver/slot identity checks, and UI
confirmation and close behavior. Native UI tests run in an isolated X display.

Successful physical MX Keys for Business pairing/authentication was verified on
2026-11-14, as recorded below. Physical mouse pairing and actual unpairing remain
unvalidated. Unifying support has protocol and automated coverage, but no
physical receiver test yet.

## Keyboard verification follow-up

Live attempts reported `0x4E` keypress (`1`) and submission (`4`) events, followed
by receiver timeout (`0x54`, error `1`). Thus the keyboard was transmitting entry
activity and Enter submission; this was not simply a missing text-entry field.
The original UI ignored all entry-progress events, making the wait opaque.

The first follow-up enabled both `WIRELESS` and `SOFTWARE_PRESENT` while
preserving the other notification flags, following Solaar's initialization.
This did not resolve the observed timeout. See the additional
[receiver protocol reference](https://openlogi.org/hidpp/receivers) and OpenLogi
`crates/openlogi-device/src/pairing/registers.rs` at
`9ca7ef0cbd1f4577ffdc338f8288f8c3a410f013` for the required mask. The implementation
also waits through non-error intermediate pairing statuses rather than treating
them as terminal failures.

The UI retains the challenge and displays receiver-reported keypress counts and
submission status. It does not claim that the entered digits are correct until
the receiver reports successful pairing. Progress is matched to the discovered
device's address. Diagnostic logs contain phases/statuses, not codes or digits.

## Independent receiver comparison and vendor initialization

Ran upstream Solaar's unchanged `solaar.cli.pair.run` through a temporary native
diagnostic window, using its own receiver transport and initialization. It also
reported six keypress events, submission, and receiver error `1` (device timeout).
The test did not pair a new device. Original receiver flags were restored.

Compared outgoing notification-read/enable, discovery, keyboard-pair, cancel and
slot-read packets against Solaar's serializer: byte-for-byte matches.

Then inspected Logitech's public [Web Connect JavaScript](https://logiwebconnect.com/main.js).
Its `bootHidppRap` reporting setup preserves existing flags and ORs byte 0 with
`0x10` and byte 1 with `0x01`, then requests device-arrival notifications. It
starts Bolt discovery with timeout byte `0`, and `BleppPairDevice` chooses entropy
`10` for authentication method `2`, otherwise `20`, independent of device kind.

The current implementation follows those vendor parameters. Original flags are
still restored; the host timeout still bounds discovery. Vendor initialization
and immediate cancellation passed on the physical Bolt receiver without changing
its paired-slot inventory. Successful keyboard verification with these vendor
parameters remains to be tested. They are a compatibility correction, not yet a
demonstrated explanation for the observed timeout.

The vendor-parameter retry on 2026-11-14 also failed: authentication method `1`,
entropy `20`, six receiver-reported keypresses, submission at 09:37:58.828 local,
then receiver status `2`, error `1`, at 09:38:29.425. Thus changing reporting and
discovery initialization did not resolve the failure. Web Connect's public code
only changes UI state on `ENTRY_COMPLETED`; it sends no extra verification/submit
register command after that event. A missing host-side submit command is not
supported by that implementation. A live test with the official Web Connect app
remains useful because the Solaar and native comparisons can share assumptions.

## Successful keyboard pairing after receiver reconnection

On 2026-11-14, the user unplugged and reconnected Jupiter's Bolt receiver and
retried with the same pairing implementation. At 09:49:04.863 local time the
receiver reported code submission; at 09:49:06.535 it reported pairing status
`2`, error `0`. A subsequent independent receiver inventory read confirmed
`MX KEYS B` in slot 1 and the existing `MX Master 4` in slot 2. The user also
confirmed success.

No pairing code changes were made between the failed vendor-parameter attempt
and this successful attempt. Reconnecting the receiver is therefore a useful
troubleshooting step for this symptom, not proof of a particular firmware,
radio, or host-side cause. Physical mouse pairing, unpairing, and Unifying
validation remain pending; the keyboard result does not establish those paths.
