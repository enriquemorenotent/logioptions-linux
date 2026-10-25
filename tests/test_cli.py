import contextlib
import io
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, patch
from logioptions import __main__ as cli


class CliTests(unittest.TestCase):
    def test_help_and_version_do_not_access_devices(self):
        for args in (['--help'], ['--version'], ['gui', '--help']):
            with self.subTest(args=args), patch.object(cli, 'LinuxHidppTransport') as hid, contextlib.redirect_stdout(io.StringIO()) as output:
                with self.assertRaises(SystemExit) as exit:
                    cli.main(args)
                self.assertEqual(exit.exception.code, 0)
                hid.assert_not_called()
                self.assertTrue(output.getvalue())

    def test_no_arguments_and_gui_open_app(self):
        gui = MagicMock()
        with patch.dict(sys.modules, {'logioptions.gui': gui}):
            cli.main([])
            cli.main(['gui'])
        self.assertEqual(gui.main.call_count, 2)

    @patch('logioptions.tray_status.battery_labels', return_value=['MX Master 4: 40% (last known)'])
    @patch('logioptions.autostart.enabled', return_value=False)
    @patch('subprocess.run', side_effect=OSError('no user bus'))
    def test_status_handles_missing_services_and_marks_old_readings(self, run, enabled, labels):
        with patch.object(cli, 'LinuxHidppTransport') as hid, contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(cli.main(['status']), 0)
        hid.assert_not_called()
        self.assertIn('Background service: unavailable', output.getvalue())
        self.assertIn('Start at login: disabled', output.getvalue())
        self.assertIn('(last known)', output.getvalue())
