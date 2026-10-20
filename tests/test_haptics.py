import importlib.util
from pathlib import Path
import unittest

from logioptions import haptics

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(importlib.util.find_spec('unicorn'), 'Requires requirements-research.txt')
class NativeHapticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from scripts.haptic_native_oracle import NativeOracle
        binary = ROOT / 'artifacts/macos-app/logioptionsplus_agent.app/Contents/MacOS/logioptionsplus_agent'
        if not binary.exists():
            raise unittest.SkipTest('Requires the inspected official 2.8 native agent')
        cls.oracle = NativeOracle(binary)

    def assert_native(self, native_method, command, **arguments):
        expected = self.oracle.command(native_method, **arguments)
        self.assertEqual(command.function, expected['function'])
        self.assertEqual(command.payload.hex(), expected['payload_hex'])
        self.assertEqual(command.dispatch_argument_4, expected['dispatch_argument_4'])

    def test_native_empty_parameter_commands(self):
        for method, builder in [('getCapabilities', haptics.get_capabilities),
                                ('getHapticConfig', haptics.get_config),
                                ('getHapticInfo', haptics.get_info),
                                ('stopHapticWaveForm', haptics.stop_waveform),
                                ('getPlayingWaveForm', haptics.get_playing_waveform)]:
            with self.subTest(method=method):
                self.assert_native(method, builder())

    def test_native_waveform_bytes(self):
        for waveform_id in range(256):
            for flag in (False, True):
                self.assert_native('playHapticWaveForm', haptics.play_waveform(waveform_id, flag),
                                   first_byte=waveform_id, boolean=flag)

    def test_native_configuration_bytes(self):
        for flags in (0, 1, 2, 3, 0x80, 0xFD, 0xFF):
            for option in (False, True):
                for level in (0, 1, 60, 100, 127, 255):
                    self.assert_native('setHapticConfig', haptics.set_config(flags, option, level),
                                       first_byte=flags, second_byte=int(option), integer=level)
