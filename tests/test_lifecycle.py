import subprocess
import unittest
from unittest.mock import patch, Mock
from logioptions.lifecycle import quit_session


class QuitTests(unittest.TestCase):
    @patch('logioptions.lifecycle.subprocess.run')
    def test_quit_closes_window_then_stops_services_without_disabling(self, run):
        run.return_value = Mock(stdout='(true,)')
        quit_session()
        commands = [call.args[0] for call in run.call_args_list]
        self.assertIn('org.gtk.Actions.Activate', commands[1])
        self.assertEqual(commands[2], ['systemctl', '--user', 'stop', 'logioptions-ring.service'])
        self.assertEqual(commands[3], ['systemctl', '--user', '--no-block', 'stop', 'logioptions-tray.service'])
        self.assertFalse(any('disable' in command for command in commands))

    @patch('logioptions.lifecycle.subprocess.run')
    def test_quit_works_with_window_already_closed(self, run):
        run.return_value = Mock(stdout='(false,)')
        quit_session()
        self.assertEqual(run.call_count, 3)

    @patch('logioptions.lifecycle.subprocess.run')
    def test_stop_failure_keeps_tray_available_to_report_error(self, run):
        run.side_effect = [Mock(stdout='(false,)'), subprocess.CalledProcessError(1, 'systemctl')]
        with self.assertRaises(subprocess.CalledProcessError):
            quit_session()
        self.assertEqual(run.call_count, 2)
