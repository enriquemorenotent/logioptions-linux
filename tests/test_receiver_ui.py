import os
import tempfile
import time
import threading
import unittest
from unittest.mock import Mock, patch

try:
    from logioptions.receiver_ui import ReceiverWindow, Gtk, Adw, GLib
except ImportError:
    Gtk = None


@unittest.skipUnless(Gtk is not None and os.environ.get('LOGIOPTIONS_ISOLATED_GUI_TEST') == '1'
                    and os.environ.get('GDK_BACKEND') == 'x11', 'Requires isolated GTK display')
class ReceiverUITests(unittest.TestCase):
    def setUp(self):
        Adw.init()
        self.parent = Gtk.Window()
        self.parent.refresh = Mock()
        self.device = dict(slot=2, name='MX Master 4', kind=2, token='device')
        self.descriptor = dict(path='/dev/test-bolt', product=0xC548, bus=3, kind='bolt', name='Logi Bolt receiver')
        self.inventory = dict(serial='receiver', devices=[self.device])

    def tearDown(self):
        self.parent.destroy()

    def pump(self, condition=lambda: True):
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            while GLib.MainContext.default().pending():
                GLib.MainContext.default().iteration(False)
            if condition(): return
            time.sleep(.01)
        self.fail('UI operation did not finish')

    def create(self):
        window = ReceiverWindow(self.parent)
        self.pump(lambda: not window.busy)
        return window

    def test_inventory_and_unpair_requires_explicit_confirmation(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, XDG_RUNTIME_DIR=directory), \
             patch('logioptions.receiver_ui.receiver_interfaces', return_value=[self.descriptor]), \
             patch('logioptions.receiver_ui.ReceiverTransport'), patch('logioptions.receiver_ui.Receiver') as receiver:
            receiver.return_value.inventory.return_value = self.inventory
            window = self.create()
            try:
                self.assertTrue(window.pair_button.get_sensitive())
                dialog = window.confirm_unpair(window.selected(), self.device)
                receiver.return_value.unpair.assert_not_called()
                dialog.response('cancel')
                receiver.return_value.unpair.assert_not_called()
                dialog = window.confirm_unpair(window.selected(), self.device)
                dialog.response('unpair')
                self.pump(lambda: not window.busy)
                receiver.return_value.unpair.assert_called_once_with(2, 'receiver', 'device')
                self.parent.refresh.assert_called_once_with()
                self.assertIn('unpaired', window.progress.get_text())
            finally:
                window.request_close()

    def test_no_receiver_and_unreadable_receiver_cannot_pair(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, XDG_RUNTIME_DIR=directory), \
             patch('logioptions.receiver_ui.receiver_interfaces', return_value=[]) as interfaces, \
             patch('logioptions.receiver_ui.ReceiverTransport'), patch('logioptions.receiver_ui.Receiver') as receiver:
            window = self.create()
            try:
                self.assertFalse(window.pair_button.get_sensitive())
                self.assertIn('Plug in', window.progress.get_text())
                interfaces.return_value = [self.descriptor]
                receiver.return_value.inventory.side_effect = OSError('Permission denied')
                window.refresh()
                self.pump(lambda: not window.busy)
                self.assertFalse(window.pair_button.get_sensitive())
                self.assertIn('Permission denied', window.devices.get_first_child().get_text())
            finally:
                window.request_close()

    def test_full_receiver_disables_pairing_but_keeps_removal(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, XDG_RUNTIME_DIR=directory), \
             patch('logioptions.receiver_ui.receiver_interfaces', return_value=[self.descriptor]), \
             patch('logioptions.receiver_ui.ReceiverTransport'), patch('logioptions.receiver_ui.Receiver') as receiver:
            receiver.return_value.inventory.return_value = dict(serial='receiver', devices=[self.device] * 6)
            window = self.create()
            try:
                self.assertFalse(window.pair_button.get_sensitive())
                self.assertTrue(window.devices.get_sensitive())
            finally:
                window.request_close()

    def test_pairing_confirmation_and_close_wait_for_receiver_cleanup(self):
        cancelled = threading.Event()
        cleaned = threading.Event()
        class Session:
            def __init__(self, receiver, serial, emit, **kwargs):
                self.cancelled = kwargs['cancelled']
                self.emit = emit
                self.accepted = threading.Event()
            def accept(self): self.accepted.set()
            def run(self):
                self.emit(dict(state='found', text='Found MX Master 4'))
                self.accepted.wait(2)
                if not self.cancelled.is_set():
                    self.emit(dict(state='verify', text='Verification instructions', progress='Code submitted. Waiting for verification…'))
                self.cancelled.wait(2)
                cancelled.set()
                cleaned.wait(2)
                raise RuntimeError('Pairing cancelled.')
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, XDG_RUNTIME_DIR=directory), \
             patch('logioptions.receiver_ui.receiver_interfaces', return_value=[self.descriptor]), \
             patch('logioptions.receiver_ui.ReceiverTransport'), patch('logioptions.receiver_ui.Receiver') as receiver, \
             patch('logioptions.receiver_ui.PairingSession', Session):
            receiver.return_value.inventory.return_value = self.inventory
            window = self.create()
            try:
                window.pair()
                self.pump(lambda: window.accept_button.get_visible())
                self.assertFalse(window.picker.get_sensitive())
                window.accept_button.emit('clicked')
                self.pump(lambda: window.progress.get_text() == 'Verification instructions')
                self.assertTrue(window.verification_status.get_visible())
                self.assertIn('Code submitted', window.verification_status.get_text())
                window.request_close()
                self.assertFalse(window.closed)
                self.assertTrue(cancelled.wait(1))
                cleaned.set()
                self.pump(lambda: window.closed)
            finally:
                cleaned.set()
                window.request_close()

    def test_pairing_success_refreshes_both_windows(self):
        class Session:
            def __init__(inner, *args, **kwargs): pass
            def run(inner): return self.device
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, XDG_RUNTIME_DIR=directory), \
             patch('logioptions.receiver_ui.receiver_interfaces', return_value=[self.descriptor]), \
             patch('logioptions.receiver_ui.ReceiverTransport'), patch('logioptions.receiver_ui.Receiver') as receiver, \
             patch('logioptions.receiver_ui.PairingSession', Session):
            receiver.return_value.inventory.return_value = self.inventory
            window = self.create()
            try:
                window.pair()
                self.pump(lambda: not window.busy)
                self.assertIn('paired successfully', window.progress.get_text())
                self.parent.refresh.assert_called_once_with()
                self.assertFalse(window.cancel_button.get_visible())
                self.assertTrue(window.pair_button.get_sensitive())
            finally:
                window.request_close()
