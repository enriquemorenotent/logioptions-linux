import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from logioptions import autostart, session


class AutostartTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        env = patch.dict(os.environ, XDG_CONFIG_HOME=self.temp.name)
        env.start()
        self.addCleanup(env.stop)

    @patch('logioptions.autostart.subprocess.run')
    def test_toggle_controls_both_login_paths_without_stopping_session(self, run):
        self.assertTrue(autostart.enabled())
        autostart.set_enabled(False)
        self.assertFalse(autostart.enabled())
        self.assertIn('Hidden=true', autostart.entry_path().read_text())
        self.assertEqual(run.call_args.args[0], ['systemctl', '--user', 'disable', *autostart.UNITS])
        autostart.set_enabled(True)
        self.assertTrue(autostart.enabled())
        self.assertEqual(run.call_args.args[0], ['systemctl', '--user', 'enable', *autostart.UNITS])

    @patch('logioptions.autostart.subprocess.run')
    def test_failed_change_restores_preference(self, run):
        autostart.set_enabled(False)
        before = autostart.entry_path().read_bytes()
        run.side_effect = subprocess.CalledProcessError(1, 'systemctl')
        with self.assertRaises(subprocess.CalledProcessError):
            autostart.set_enabled(True)
        self.assertEqual(autostart.entry_path().read_bytes(), before)

    @patch('logioptions.session.os.getuid', return_value=1000)
    @patch('logioptions.autostart.subprocess.run')
    def test_disabled_login_does_not_activate_services(self, run, uid):
        autostart.set_enabled(False)
        run.reset_mock()
        session.main()
        run.assert_not_called()

    @patch('logioptions.session.os.getuid', return_value=1000)
    @patch('logioptions.session.migrate', return_value=False)
    @patch('logioptions.background.acquire', return_value=True)
    @patch('logioptions.background.lockfile')
    @patch('logioptions.session.subprocess.run')
    def test_manual_activation_preserves_disabled_login(self, run, lock, acquire, migrate, uid):
        from unittest.mock import MagicMock
        import sys
        autostart.set_enabled(False)
        run.reset_mock()
        gio = MagicMock()
        gio.Settings.new.return_value.get_strv.return_value = []
        with patch.dict(sys.modules, {'gi.repository': MagicMock(Gio=gio)}), patch('logioptions.session.Path.home', return_value=Path(self.temp.name)):
            session.main(login=False)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertIn(['systemctl', '--user', 'disable', *autostart.UNITS], commands)
        self.assertIn(['systemctl', '--user', 'restart', *autostart.UNITS], commands)
        self.assertFalse(autostart.enabled())
