"""Haptic feature command construction recovered from the official 2.8 agent.

These are feature-call parameters, not complete USB/Bluetooth reports. Native
transport and physical verification remain separate work. Boolean parameter
semantics deliberately remain unnamed where only byte behavior is established.
"""
from dataclasses import dataclass

FEATURE_ID = 0x19B0


def _byte(value):
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 255:
        raise ValueError('Parameter must be an integer from 0 to 255')
    return value


@dataclass(frozen=True)
class HapticCommand:
    function: int
    payload: bytes = b''
    dispatch_argument_4: int = 0
    feature_id: int = FEATURE_ID


def get_capabilities():
    return HapticCommand(0, dispatch_argument_4=1)


def get_config():
    return HapticCommand(1)


def set_config(configuration_byte: int, configuration_option: bool, level_byte: int):
    if not isinstance(configuration_option, bool):
        raise ValueError('Configuration option must be boolean')
    flags = _byte(configuration_byte) | (2 if configuration_option else 0)
    return HapticCommand(2, bytes([flags, _byte(level_byte)]))


def get_info():
    return HapticCommand(3)


def play_waveform(waveform_id: int, flag: bool = False):
    if not isinstance(flag, bool):
        raise ValueError('Waveform flag must be boolean')
    return HapticCommand(4, bytes([_byte(waveform_id), int(flag)]))


def stop_waveform():
    return HapticCommand(5)


def get_playing_waveform():
    return HapticCommand(6)
