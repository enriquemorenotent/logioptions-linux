import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from logioptions.background import BackgroundRing, foreground_access


class Listener:
    def __init__(self, descriptor, status, **kwargs):
        self.alive = True
        self.thread = self
    def is_alive(self): return self.alive
    def stop(self): self.alive = False


class BackgroundTests(unittest.TestCase):
    def test_foreground_waits_for_cleanup_and_background_resumes(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, XDG_RUNTIME_DIR=directory):
            device = dict(device_index=2, controls=[dict(control_id=416, flags=0x20)])
            worker = BackgroundRing(lambda: ([device], []), lambda: True, Listener, restore_settings=lambda: None)
            worker.tick()
            first = worker.listener
            requested, entered, release = threading.Event(), threading.Event(), threading.Event()
            def settings():
                requested.set()
                with foreground_access():
                    entered.set()
                    release.wait(3)
            thread = threading.Thread(target=settings)
            thread.start()
            requested.wait(1)
            try:
                # Tick until the foreground request has obtained its lock.
                for _ in range(100):
                    worker.tick()
                    if entered.wait(.01): break
                self.assertTrue(entered.is_set())
                self.assertFalse(first.alive)
                worker.tick()
                self.assertIsNone(worker.listener)
                release.set()
                thread.join(2)
                worker.tick()
                self.assertIsNotNone(worker.listener)
                self.assertIsNot(first, worker.listener)
            finally:
                release.set()
                thread.join(3)
                worker.stop()

    def test_retries_missing_shell_mouse_and_dead_listener(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, XDG_RUNTIME_DIR=directory):
            device = dict(device_index=2, controls=[dict(control_id=416, flags=0x20)])
            worker = BackgroundRing(lambda: ([], []), lambda: False, Listener, restore_settings=lambda: None)
            worker.tick()
            self.assertIsNone(worker.lease)
            worker.ready = lambda: True
            worker.tick()
            self.assertIsNone(worker.lease)
            worker.discover = lambda: ([device], [])
            worker.tick()
            first = worker.listener
            first.alive = False
            worker.tick()
            self.assertIsNot(first, worker.listener)
            worker.stop()
            self.assertIsNone(worker.lease)

    def test_settings_restore_even_without_shell_extension(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, XDG_RUNTIME_DIR=directory):
            restore = Mock()
            worker = BackgroundRing(lambda: ([], []), lambda: False, Listener, restore_settings=restore)
            worker.tick()
            restore.assert_called_once_with()
            self.assertIsNone(worker.listener)
            self.assertIsNone(worker.lease)

    def test_bad_preferences_do_not_disable_ring(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, XDG_RUNTIME_DIR=directory):
            device = dict(device_index=2, controls=[dict(control_id=416,flags=0x20)])
            worker = BackgroundRing(lambda: ([device],[]), lambda: True, Listener,
                                    restore_settings=Mock(side_effect=ValueError('invalid config')))
            try:
                worker.tick()
                self.assertIsNotNone(worker.listener)
            finally:
                worker.stop()
