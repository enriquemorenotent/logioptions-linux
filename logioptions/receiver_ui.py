"""Native receiver inventory, pairing instructions, and confirmed removal."""
from concurrent.futures import ThreadPoolExecutor
import threading

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, GLib, Gtk, Pango

from .background import foreground_access
from .pairing import PairingSession
from .receiver import Receiver, ReceiverTransport, receiver_interfaces


class ReceiverWindow(Adw.Window):
    def __init__(self, parent):
        super().__init__(title='Receivers and pairing', transient_for=parent, modal=True,
                         default_width=660, default_height=640)
        self.parent_window = parent
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.closed = self.busy = self.closing = False
        self.session = None
        self.cancelled = threading.Event()
        self.receivers = []
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.append(Adw.HeaderBar())
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18,
                       margin_start=24, margin_end=24, margin_top=12, margin_bottom=24)
        scroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        scroll.set_child(body)
        outer.append(scroll)
        self.set_content(outer)
        title = Gtk.Label(label='Connect your devices', xalign=0)
        title.add_css_class('title-1')
        body.append(title)
        body.append(Gtk.Label(label='Pair Logitech devices with a Logi Bolt or Unifying USB receiver. Each receiver supports its own family of devices.', xalign=0, wrap=True))
        self.picker = Gtk.DropDown()
        self.picker.connect('notify::selected', lambda *_: self.render())
        body.append(self.picker)
        self.devices = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        body.append(self.devices)
        self.progress = Gtk.Label(xalign=0, wrap=True, selectable=True)
        self.progress.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        body.append(self.progress)
        self.verification_status = Gtk.Label(xalign=0, wrap=True, visible=False)
        self.verification_status.add_css_class('accent-value')
        body.append(self.verification_status)
        self.spinner = Gtk.Spinner(halign=Gtk.Align.START)
        body.append(self.spinner)
        buttons = Gtk.Box(spacing=12)
        self.refresh_button = Gtk.Button(label='Refresh receivers')
        self.refresh_button.connect('clicked', lambda *_: self.refresh())
        buttons.append(self.refresh_button)
        self.pair_button = Gtk.Button(label='Pair new device', hexpand=True)
        self.pair_button.add_css_class('suggested-action')
        self.pair_button.connect('clicked', lambda *_: self.pair())
        buttons.append(self.pair_button)
        body.append(buttons)
        self.accept_button = Gtk.Button(label='Pair this device', visible=False)
        self.accept_button.add_css_class('suggested-action')
        self.accept_button.connect('clicked', lambda *_: self.accept())
        body.append(self.accept_button)
        self.cancel_button = Gtk.Button(label='Cancel pairing', visible=False)
        self.cancel_button.connect('clicked', lambda *_: self.cancel())
        body.append(self.cancel_button)
        self.connect('close-request', self.request_close)
        self.refresh()

    def selected(self):
        index = self.picker.get_selected()
        return self.receivers[index] if index < len(self.receivers) else None

    def controls(self):
        descriptor = self.selected()
        self.picker.set_sensitive(not self.busy)
        self.devices.set_sensitive(not self.busy)
        self.refresh_button.set_sensitive(not self.busy)
        self.pair_button.set_sensitive(not self.busy and bool(descriptor)
                                      and 'error' not in descriptor and len(descriptor['devices']) < 6)

    def submit(self, work, done):
        if self.busy or self.closed:
            return
        self.busy = True
        self.controls()
        self.spinner.start()
        def exclusive():
            with foreground_access():
                if self.cancelled.is_set():
                    raise RuntimeError('Operation cancelled.')
                return work()
        future = self.pool.submit(exclusive)
        def finish():
            self.busy = False
            self.session = None
            self.spinner.stop()
            self.cancel_button.set_visible(False)
            self.accept_button.set_visible(False)
            self.verification_status.set_visible(False)
            try:
                result = future.result()
                if not self.closing:
                    done(result)
            except Exception as error:
                self.progress.set_text(str(error))
            self.controls()
            if self.closing:
                self.finish_close()
            return False
        future.add_done_callback(lambda _: GLib.idle_add(finish))

    def refresh(self, message='Reading paired devices…'):
        if self.busy:
            return
        self.cancelled.clear()
        self.progress.set_text(message)
        self.verification_status.set_visible(False)
        def work():
            result = []
            for descriptor in receiver_interfaces():
                try:
                    with ReceiverTransport(descriptor['path']) as transport:
                        result.append(dict(descriptor, **Receiver(transport, descriptor).inventory()))
                except Exception as error:
                    result.append(dict(descriptor, error=str(error)))
            return result
        def done(receivers):
            old = self.selected()
            self.receivers = receivers
            names = [r['name'] for r in receivers]
            labels = [r['name'] if names.count(r['name']) == 1 else
                      f'{r["name"]} · {r.get("serial", str(i + 1))[-8:]}'
                      for i, r in enumerate(receivers)]
            self.picker.set_model(Gtk.StringList.new(labels))
            if old:
                self.picker.set_selected(next((i for i, r in enumerate(receivers) if r['path'] == old['path']), 0))
            self.render()
            if not receivers:
                self.progress.set_text('Plug in a Logi Bolt or Unifying USB receiver, then refresh. Bluetooth pairing is managed in your desktop’s Bluetooth settings.')
            else:
                self.progress.set_text('Select a receiver to add or remove devices.' if message == 'Reading paired devices…' else message)
        self.submit(work, done)

    def render(self):
        while self.devices.get_first_child():
            self.devices.remove(self.devices.get_first_child())
        descriptor = self.selected()
        if not descriptor:
            self.controls()
            return
        if 'error' in descriptor:
            self.devices.append(Gtk.Label(label=descriptor['error'], xalign=0, wrap=True))
        else:
            count = len(descriptor['devices'])
            self.devices.append(Gtk.Label(label=f'{count} of 6 slots used · Paired devices include sleeping and disconnected devices.', xalign=0, wrap=True))
            for device in descriptor['devices']:
                row = Adw.ActionRow(title=GLib.markup_escape_text(device['name']),
                                    subtitle=f'Slot {device["slot"]}')
                remove = Gtk.Button(label='Unpair', valign=Gtk.Align.CENTER)
                remove.add_css_class('destructive-action')
                remove.connect('clicked', lambda _, r=descriptor, d=device: self.confirm_unpair(r, d))
                row.add_suffix(remove)
                self.devices.append(row)
        self.controls()

    def pair(self):
        descriptor = self.selected()
        if self.busy or not descriptor or 'error' in descriptor:
            return
        self.cancelled.clear()
        self.verification_status.set_visible(False)
        self.cancel_button.set_visible(True)
        self.cancel_button.set_sensitive(True)
        self.progress.set_text('Preparing the receiver…')
        def emit(event):
            def update():
                if not self.closed and not self.closing and not self.cancelled.is_set():
                    self.progress.set_text(event['text'])
                    self.accept_button.set_visible(event['state'] == 'found')
                    self.verification_status.set_text(event.get('progress', ''))
                    self.verification_status.set_visible(bool(event.get('progress')))
                return False
            GLib.idle_add(update)
        def work():
            with ReceiverTransport(descriptor['path']) as transport:
                self.session = PairingSession(Receiver(transport, descriptor), descriptor['serial'],
                                              emit, cancelled=self.cancelled)
                return self.session.run()
        def done(device):
            self.parent_window.refresh()
            self.refresh(f'{device["name"]} paired successfully.')
        self.submit(work, done)

    def accept(self):
        if self.session:
            self.session.accept()
            self.accept_button.set_visible(False)
            self.progress.set_text('Connecting. Follow the verification instructions when they appear…')

    def cancel(self):
        self.cancelled.set()
        self.accept_button.set_visible(False)
        self.cancel_button.set_sensitive(False)
        self.progress.set_text('Cancelling pairing and releasing the receiver…')

    def confirm_unpair(self, descriptor, device):
        if self.busy:
            return
        dialog = Adw.MessageDialog(transient_for=self, modal=True,
            heading=f'Unpair {device["name"]}?',
            body='This removes the device from this USB receiver. It will stop controlling this computer through this receiver until paired again. Make sure you have another way to use the computer.')
        dialog.add_response('cancel', 'Keep paired')
        dialog.add_response('unpair', 'Unpair device')
        dialog.set_response_appearance('unpair', Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response('cancel')
        dialog.set_close_response('cancel')
        def respond(_dialog, response):
            if response != 'unpair' or self.closed or self.closing:
                return
            self.cancelled.clear()
            self.progress.set_text(f'Removing {device["name"]}…')
            def work():
                with ReceiverTransport(descriptor['path']) as transport:
                    Receiver(transport, descriptor).unpair(device['slot'], descriptor['serial'], device['token'])
            def done(_):
                self.parent_window.refresh()
                self.refresh(f'{device["name"]} unpaired.')
            self.submit(work, done)
        dialog.connect('response', respond)
        dialog.present()
        return dialog

    def request_close(self, *_):
        self.closing = True
        self.cancelled.set()
        if self.busy:
            self.progress.set_text('Releasing the receiver…')
            self.accept_button.set_visible(False)
            self.cancel_button.set_sensitive(False)
        else:
            self.finish_close()
        return True

    def finish_close(self):
        self.closed = True
        self.pool.shutdown(wait=False, cancel_futures=True)
        self.destroy()
