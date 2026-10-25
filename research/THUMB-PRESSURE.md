# Thumb-pad pressure, 2026-10-25

Force-sensing feature 0x19C0: function 0 gives button count; function 1 with
button index 0 returns four big-endian 16-bit values: flags, default, maximum,
minimum. Bit 0 allows changes. Function 2 reads the current 16-bit threshold;
function 3 writes button index followed by the big-endian threshold.
Cross-checked against installed Solaar's ForceSensingButton implementation.
Only the single-force-button layout is currently supported.

Live MX Master 4 reported range 4748–7894 and default/current 5935. Changed to
6035, read back, then restored and verified 5935 in a finally block. Evidence
is in ignored artifacts/thumb-pressure-validation.json. These are device units;
no physical units or percentage strength is claimed. Higher threshold requires
more force according to the protocol meaning; subjective feel awaits user testing.

UI shows Lighter press to Firmer press using the advertised range, plus a default
selection button. Apply verifies readback and saves by hardware identity. Background
restoration includes this setting. Solaar force-sensing is ignored for this mouse
so it cannot overwrite the app's setting; other Solaar behavior is unchanged.
Tests cover packet encoding, bounds, failed readback, unsupported layouts,
truncation, restoration, and GTK slider/default/apply behavior.
