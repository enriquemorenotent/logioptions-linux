# SmartShift and wheel resistance, 2026-10-25

MX Master 4 advertises tunable torque in bit 0 of SMART_SHIFT_ENHANCED (0x2111)
function 0. Function 1 reads mode, disengagement threshold, and torque; function
2 writes those three bytes. Existing installed Solaar SmartShiftEnhanced and
ScrollRatchetTorque implementations were used to cross-check field meanings.

UI provides Free-spin (mode 1, preserve threshold), Ratchet (mode 2, threshold
255), and SmartShift (mode 2, threshold 1–49). Lower threshold disengages at a
lower speed. Resistance is 1–100, shown only if supported and clicks are in use.
No physical force units are claimed. Switching speed appears only for SmartShift.

Physical validation set SmartShift threshold 20 / torque 60, Ratchet, and Free-spin,
verified readback for each, then restored the exact original mode 2, threshold 12,
torque 75. Private capture: artifacts/wheel-settings-validation.json. Perceived
click force and automatic disengagement behavior await user acceptance; register
readback does not establish those subjective effects.

Apply verifies all three values, then saves them using existing per-device
preferences. Solaar already ignores smart-shift, scroll-ratchet, and
scroll-ratchet-torque for this mouse; no additional settings were modified.
Tests cover mode encoding, free-spin threshold preservation, rejection of invalid
values and unsupported resistance, failed readback, and GTK conditional visibility.
