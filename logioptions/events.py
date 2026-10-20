"""Control state changes recovered from Feature1B04 and physical mouse reports."""
from dataclasses import dataclass
import time


@dataclass(frozen=True)
class ControlChange:
    pressed: tuple[int, ...]
    released: tuple[int, ...]
    held: tuple[int, ...]


class ControlTracker:
    def __init__(self, device_index, feature_index):
        self.device_index = device_index
        self.feature_index = feature_index
        self.held = ()

    def feed(self, report):
        # Function zero contains four big-endian control IDs, zero means empty.
        # Other functions include raw movement and must not clear key state.
        if len(report) < 4 or report[1:4] != bytes([self.device_index, self.feature_index, 0]):
            return None
        if len(report) != 20 or report[0] != 0x11:
            raise ValueError('Truncated or unsupported control notification')
        held = tuple(dict.fromkeys(value for offset in range(4, 12, 2)
                     if (value := int.from_bytes(report[offset:offset + 2], 'big'))))
        change = ControlChange(tuple(c for c in held if c not in self.held),
                               tuple(c for c in self.held if c not in held), held)
        self.held = held
        return change


def capture_control(device, control_id, *, seconds=30, ready=lambda: None, cancelled=lambda: False):
    """Temporarily divert a control; attempt and verify restoration on exit.

    Call from a worker: ready runs after the device confirms diversion. No
    haptic waveform or host input injection is performed. A disconnected device
    can prevent restoration; that failure is reported rather than hidden.
    """
    if not 0 < seconds <= 300:
        raise ValueError('Capture duration must be between zero and 300 seconds')
    controls = {row['control_id']: row for row in device.controls()}
    if control_id not in controls or not controls[control_id]['flags'] & 0x20:
        raise ValueError('Control does not advertise diversion')
    before = device.control_reporting(control_id)
    tracker = ControlTracker(device.device_index, device.feature(0x1B04)['index'])
    changes = []
    try:
        device.set_control_reporting_bytes(control_id, 3, before['remapped_to'])
        if not device.control_reporting(control_id)['flags'] & 1:
            raise ValueError('Device did not enable control reporting')
        ready()
        deadline = time.monotonic() + seconds
        saw_press = False
        while time.monotonic() < deadline and not cancelled():
            report = device.transport.read_notification(timeout=min(0.5, max(0.001, deadline - time.monotonic())))
            if report is None:
                continue
            change = tracker.feed(report)
            if change is None:
                continue
            changes.append(change)
            saw_press |= control_id in change.pressed
            if saw_press and control_id in change.released:
                return changes
        raise TimeoutError('No complete press and release received. Click Test thumb pad to try again.')
    finally:
        device.set_control_reporting_bytes(control_id, 2 | (before['flags'] & 1), before['remapped_to'])
        if device.control_reporting(control_id) != before:
            raise RuntimeError('Previous button reporting could not be verified after capture')
