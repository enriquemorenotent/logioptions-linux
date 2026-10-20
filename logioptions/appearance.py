"""Options+-style native presentation, measured against the installed Mac UI.

Device renders and fonts are loaded from the user's local research artifacts;
no extracted Logitech assets are bundled with the implementation.
"""
import ctypes
from datetime import datetime
from pathlib import Path
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, Gsk

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'artifacts/ui-reference'
CSS = b'''
window { background: #fbfbfb; color: #242627; font-family: BrownPro, sans-serif; font-size: 14px; }
.topbar { padding: 24px 38px 12px; }
.header-title { font-size: 39px; font-weight: bold; }
.home-title { font-size: 39px; font-weight: bold; }
button { background-image: none; box-shadow: none; text-shadow: none; }
.flat-icon { background: transparent; border: none; border-radius: 4px; padding: 8px; }
.flat-icon:hover { background: #efedf2; }
.reference-icon { font-family: "5thAug2026"; font-size: 24px; font-weight: normal; }
.navigation { padding: 0 22px 0 38px; }
.nav-button { background: transparent; border: 1px solid transparent; border-radius: 3px; padding: 9px 12px; font-size: 13px; font-weight: bold; color: #111; min-height: 20px; }
.nav-button:hover { background: #eeebf4; }
.nav-button.active { background: #814efa; border-color: #7040dd; color: white; }
.device-tile { background: transparent; border: none; padding: 30px 24px; border-radius: 12px; }
.device-tile:hover { background: #f3f1f7; }
.device-name { font-size: 20px; font-weight: bold; }
.battery { font-size: 12px; color: #525657; }
.connection { border: 1px solid #e6e6e6; border-radius: 3px; padding: 10px 14px; font-size: 11px; }
.callout { background: #fbfbfb; color: #1e1730; border: 1px solid #f0f0f0; border-radius: 3px; padding: 12px 16px; box-shadow: 0 7px 20px rgba(0,0,0,0.10); }
.callout:hover { background: #f0eaff; border-color: #c9b5fa; }
.callout.selected { background: #814efa; color: white; border-color: #7040dd; }
.callout-title { font-size: 14px; font-weight: bold; }
.callout-detail { font-size: 13px; font-weight: normal; }
.target-dot { background: transparent; border: 2px solid white; border-radius: 8px; min-width: 12px; min-height: 12px; box-shadow: 0 0 2px #555; }
.drawer { background: white; border-left: 1px solid #e4e4e4; }
.drawer-header { background: #e1e2e3; padding: 20px 26px; font-size: 20px; font-weight: bold; }
.card { background: white; padding: 26px; border: none; border-radius: 0; box-shadow: none; }
.section-title { font-size: 17px; font-weight: bold; }
.muted { color: #616568; }
.accent-value { color: #7040dc; font-weight: bold; }
.control-button { padding: 10px 14px; border-radius: 4px; border: 1px solid #d9d9dd; background: #fff; }
.control-button:hover { background: #f3eefb; }
.control-button.suggested-action { color: white; background: #814efa; border-color: #814efa; }
scale trough { background: #e3e4e6; min-height: 5px; border-radius: 6px; }
scale highlight { background: #814efa; }
scale slider { background: #814efa; border: 3px solid white; min-width: 15px; min-height: 15px; }
switch:checked { background: #814efa; }
.footer { padding: 14px 38px 24px; }
'''


def load_fonts():
    try:
        fc = ctypes.CDLL('libfontconfig.so.1')
        fc.FcConfigGetCurrent.restype = ctypes.c_void_p
        fc.FcConfigAppFontAddFile.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        config = fc.FcConfigGetCurrent()
        for name in ('regular', 'bold', 'light'):
            path = ASSETS / f'BrownPro-{name}.ttf'
            if path.exists(): fc.FcConfigAppFontAddFile(config, str(path).encode())
        icon = ROOT / 'artifacts/mac-live-2.9/ui/assets/120228c0ffbb15c5d091.ttf'
        if icon.exists(): fc.FcConfigAppFontAddFile(config, str(icon).encode())
        from gi.repository import PangoCairo
        PangoCairo.FontMap.get_default().changed()
    except OSError:
        pass


def text(value, css=None):
    widget = Gtk.Label(label=value, xalign=0)
    if css: widget.add_css_class(css)
    return widget


def column(spacing=12): return Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)
def row(spacing=12): return Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=spacing)


class DeviceCanvas(Gtk.Fixed):
    def do_measure(self, orientation, for_size):
        # Absolute callout positions must not feed back into the window's minimum
        # size; the surrounding box gives this canvas its available space.
        return (0, 0, -1, -1)


class ShadowPicture(Gtk.Picture):
    def do_snapshot(self, snapshot):
        shade = Gdk.RGBA()
        shade.parse('rgba(0,0,0,0.28)')
        shadow = Gsk.Shadow()
        shadow.color = shade
        shadow.dx = 16
        shadow.dy = 32
        shadow.radius = 24
        snapshot.push_shadow([shadow])
        Gtk.Picture.do_snapshot(self, snapshot)
        snapshot.pop()


def picture(name, width, height):
    path = ASSETS / name.replace('.webp', '.png')
    if path.exists():
        widget = (ShadowPicture() if name == 'mouse-side.webp' else Gtk.Picture())
        widget.set_filename(str(path))
        widget.set_overflow(Gtk.Overflow.VISIBLE)
        widget.set_content_fit(Gtk.ContentFit.CONTAIN)
        widget.set_can_shrink(True)
    else:
        widget = Gtk.Image.new_from_icon_name('input-mouse-symbolic' if 'mouse' in name else 'input-keyboard-symbolic')
        widget.set_pixel_size(120)
    widget.set_size_request(width, height)
    return widget


class Presentation:
    def build_shell(self):
        self.section = 'buttons'
        self.cards = {}
        self.home = True
        root = column(0)
        header = row(12)
        header.add_css_class('topbar')
        self.back = Gtk.Button(icon_name='go-previous-symbolic', tooltip_text='All devices')
        self.back.add_css_class('flat-icon')
        self.back.connect('clicked', lambda *_: self.go_back())
        header.append(self.back)
        self.heading = text('Good Evening', 'header-title')
        self.heading.set_hexpand(True)
        header.append(self.heading)
        self.global_button = Gtk.Button(icon_name='view-grid-symbolic', tooltip_text='Global settings')
        self.global_button.add_css_class('flat-icon')
        self.global_button.connect('clicked', lambda *_: self.show_section('buttons'))
        header.append(self.global_button)
        self.refresh_button = Gtk.Button(icon_name='view-refresh-symbolic', tooltip_text='Refresh devices')
        self.refresh_button.add_css_class('flat-icon')
        self.refresh_button.connect('clicked', lambda *_: self.refresh())
        header.append(self.refresh_button)
        handle = Gtk.WindowHandle()
        handle.set_child(header)
        header.append(Gtk.WindowControls(side=Gtk.PackType.END))
        root.append(handle)
        self.body = row(0)
        self.body.set_vexpand(True)
        self.navigation = column(16)
        self.navigation.add_css_class('navigation')
        self.navigation.set_valign(Gtk.Align.CENTER)
        self.navigation.set_size_request(225, -1)
        self.nav_buttons = {}
        for key, name, icon in [('buttons','BUTTONS','input-mouse-symbolic'),
            ('point','POINT, SCROLL, PRESS','input-mouse-symbolic'),
            ('haptics','HAPTIC FEEDBACK','media-record-symbolic'),
            ('easy','EASY-SWITCH','video-display-symbolic'),
            ('flow','FLOW','view-dual-symbolic'),('settings','SETTINGS','preferences-system-symbolic')]:
            button = Gtk.Button(halign=Gtk.Align.START)
            content = row(14)
            glyphs = {'buttons':'\ue926', 'point':'\ue976', 'haptics':'\ue9bb', 'easy':'\ue949', 'flow':'\ue94e', 'settings':'\ue960'}
            if (ROOT / 'artifacts/mac-live-2.9/ui/assets/120228c0ffbb15c5d091.ttf').exists():
                content.append(text(glyphs[key], 'reference-icon'))
            else:
                content.append(Gtk.Image.new_from_icon_name(icon))
            content.append(text(name))
            button.set_child(content)
            button.add_css_class('nav-button')
            button.connect('clicked', lambda _, k=key: self.show_section(k))
            self.nav_buttons[key] = button
            self.navigation.append(button)
        self.body.append(self.navigation)
        self.page = column(0)
        self.page.set_hexpand(True)
        self.body.append(self.page)
        self.drawer = column(0)
        self.drawer.add_css_class('drawer')
        self.drawer.set_size_request(370, -1)
        drawer_head = row()
        drawer_head.add_css_class('drawer-header')
        title = text('Modify settings')
        title.set_hexpand(True)
        drawer_head.append(title)
        close = Gtk.Button(icon_name='window-close-symbolic', tooltip_text='Close settings')
        close.add_css_class('flat-icon')
        close.connect('clicked', lambda *_: self.close_panel())
        drawer_head.append(close)
        self.drawer.append(drawer_head)
        self.panel = column(0)
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_child(self.panel)
        self.drawer.append(scroll)
        self.body.append(self.drawer)
        root.append(self.body)
        footer = row(16)
        footer.add_css_class('footer')
        self.connection_label = text('Connecting…', 'connection')
        footer.append(self.connection_label)
        self.spinner = Gtk.Spinner()
        footer.append(self.spinner)
        self.status = text('Looking for connected devices…', 'muted')
        self.status.set_hexpand(True)
        self.status.set_wrap(True)
        footer.append(self.status)
        root.append(footer)
        # Kept as the selection model used by the device refresh code.
        self.device_list = Gtk.ListBox()
        self.device_list.connect('row-selected', self.choose_device)
        self.set_content(root)
        self.drawer.set_visible(False)
        self.navigation.set_visible(False)
        self.back.set_visible(False)
        self.global_button.set_visible(False)

    def go_back(self):
        if self.drawer.get_visible(): self.close_panel()
        else: self.show_home()

    def show_home(self):
        self.home = True
        self.close_panel()
        self.clear_page()
        self.navigation.set_visible(False)
        self.back.set_visible(False)
        self.global_button.set_visible(False)
        hour = datetime.now().hour
        self.heading.set_text('Good Morning' if hour < 12 else 'Good Afternoon' if hour < 18 else 'Good Evening')
        gallery = row(38)
        gallery.set_halign(Gtk.Align.CENTER)
        gallery.set_valign(Gtk.Align.CENTER)
        gallery.set_vexpand(True)
        for index, device in enumerate(self.devices):
            button = Gtk.Button()
            button.add_css_class('device-tile')
            content = column(22)
            mouse = device.get('kind_code') == 3 or 'dpi' in device
            content.append(picture('mouse-front.webp' if mouse else 'keyboard-front.webp', 220 if mouse else 420, 280))
            title = text(device['name'], 'device-name')
            title.set_halign(Gtk.Align.CENTER)
            content.append(title)
            battery = device.get('battery', {}).get('percentage')
            info = text(f'▰  {battery}%' if battery is not None else 'Connected', 'battery')
            info.set_halign(Gtk.Align.CENTER)
            content.append(info)
            button.set_child(content)
            button.connect('clicked', lambda _, i=index: self.open_device(i))
            gallery.append(button)
        self.page.append(gallery)
        self.connection_label.set_text(f'{len(self.devices)} devices')

    def open_device(self, index):
        self.selected = index
        self.section = 'buttons'
        self.render_device()

    def show_section(self, section):
        if not self.devices: return
        self.section = section
        self.render_device()

    def close_panel(self):
        while self.panel.get_first_child(): self.panel.remove(self.panel.get_first_child())
        self.drawer.set_visible(False)
        self.navigation.set_visible(not self.home)
        for button in getattr(self, 'callouts', []): button.remove_css_class('selected')

    def show_panel(self, title, anchor=None):
        self.close_panel()
        self.panel_title = title
        card = self.cards.get(title)
        if card:
            if card.get_parent(): card.get_parent().remove(card)
            self.panel.append(card)
        else:
            note = column(12)
            note.add_css_class('card')
            note.append(text(title, 'section-title'))
            message = text('This feature is not implemented yet.', 'muted')
            message.set_wrap(True)
            note.append(message)
            self.panel.append(note)
        self.drawer.set_visible(True)
        self.navigation.set_visible(False)
        if anchor: anchor.add_css_class('selected')

    def render_device(self):
        if not self.devices: return
        self.home = False
        self.close_panel()
        device = self.devices[self.selected]
        canvas_key = device.get('key', device['name'])
        reuse_canvas = (getattr(self, '_canvas_key', None) == canvas_key
                        and getattr(self, 'canvas', None) is not None
                        and self.canvas.get_parent() is self.page)
        if reuse_canvas:
            # Keep the allocated image and its texture mapped across tabs.
            for widget, _, _ in self.items:
                self.canvas.remove(widget)
            child = self.page.get_first_child()
            while child:
                following = child.get_next_sibling()
                if child is not self.canvas:
                    self.page.remove(child)
                child = following
        else:
            self.clear_page()
        self.cards = {}
        self.controls_box = column()
        self._build_controls()
        device = self.devices[self.selected]
        self.heading.set_text(device['name'])
        self.back.set_visible(True)
        self.global_button.set_visible(self.section not in ('haptics', 'settings'))
        self.navigation.set_visible(True)
        for key, button in self.nav_buttons.items():
            if key == self.section: button.add_css_class('active')
            else: button.remove_css_class('active')
        battery = device.get('battery', {}).get('percentage')
        self.connection_label.set_text(f'CONNECTED  ·  {battery}%' if battery is not None else 'CONNECTED')
        mouse = device.get('kind_code') == 3 or 'dpi' in device
        if not reuse_canvas:
            self._canvas_key = canvas_key
            self.canvas = DeviceCanvas(hexpand=True, vexpand=True)
            self.page.append(self.canvas)
            self.device_picture = picture('mouse-side.webp' if mouse else 'keyboard-front.webp', 308 if mouse else 580, 480)
            self.canvas.put(self.device_picture, 0, 0)
            self.overlay_picture = None
            if mouse:
                self.overlay_picture = picture('mouse-haptic-zone.webp', 125, 219)
                self.canvas.put(self.overlay_picture, 0, 0)
        self.items = []
        self.callouts = []
        if self.overlay_picture:
            self.overlay_picture.set_visible(self.section == 'haptics')
        if not mouse:
            self.add_callout('Keyboard', 'Battery and connection', 'Keyboard', -.2, .55)
        elif self.section == 'buttons':
            for title, card, x, y, cid in [
                ('Middle button','Button actions',.91,.18,82), ('Gesture button','Button actions',-.29,.35,195),
                ('Shift wheel mode','Scroll wheel',.98,.39,196),('Forward','Button actions',.70,.47,86),
                ('Show Actions Ring','Thumb pad',-.34,.49,416),('Horizontal scroll','Horizontal scroll',.90,.56,None),
                ('Back','Button actions',.43,.71,83)]:
                self.add_callout(title, '', card, x, y, cid)
        elif self.section == 'point':
            dpi = device.get('dpi', {}).get('current')
            self.add_callout('Scroll wheel', 'Mode: ' + ('Free-spin' if device.get('smartshift',{}).get('mode_code') == 1 else 'Ratchet'), 'Scroll wheel',.85,.17)
            self.add_callout('Thumb wheel','Horizontal scroll','Horizontal scroll',-.32,.48)
            self.add_callout('Button press sensitivity','Not configured','Button press sensitivity',-.38,.70)
            self.add_callout('Pointer speed',f'{dpi:,} DPI' if dpi else 'Unavailable','Pointer speed',.92,.68)
        elif self.section == 'haptics':
            h = device.get('haptics', {})
            self.add_callout('Haptic feedback', f"Feedback: {'On' if h.get('enabled') else 'Off'}\nIntensity: {h.get('level', 0)}%\nBattery saving mode: {'On' if h.get('power_save') else 'Off'}", 'Haptic feedback', -.42,.48)
        else:
            title = {'easy':'Easy-Switch', 'flow':'Flow', 'settings':'Device settings'}[self.section]
            self.add_callout(title, 'Click to view', title, -.35,.48)
        self._last_size = None
        if reuse_canvas:
            self.layout_canvas(self.canvas, None)
        else:
            self.canvas.add_tick_callback(self.layout_canvas)

    def add_callout(self, title, detail, card, x, y, cid=None):
        button = Gtk.Button()
        button.add_css_class('callout')
        content = column(3)
        content.append(text(title, 'callout-title'))
        if detail: content.append(text(detail, 'callout-detail'))
        button.set_child(content)
        def select(_):
            self.show_panel(card, button)
            if cid is not None and hasattr(self, 'mapping_source'):
                index = next((i for i, c in enumerate(self.mapping_controls) if c['control_id'] == cid), None)
                if index is not None: self.mapping_source.set_selected(index)
        button.connect('clicked', select)
        self.canvas.put(button, 0, 0)
        self.items.append((button, x, y))
        self.callouts.append(button)
        # Mark the corresponding physical control, as on the reference screen.
        if cid is not None or card == 'Haptic feedback':
            points = {82:(.75,.19),195:(.39,.36),196:(.80,.40),86:(.43,.47),416:(.31,.49),83:(.48,.60)}
            dx,dy = points.get(cid,(.31,.49))
            dot = Gtk.Box()
            dot.add_css_class('target-dot')
            dot.set_can_target(False)
            self.canvas.put(dot,0,0)
            self.items.append((dot,dx,dy))

    def layout_canvas(self, canvas, clock):
        if canvas is not self.canvas: return False
        width, height = canvas.get_width(), canvas.get_height()
        size = (width,height)
        if size == self._last_size: return True
        self._last_size = size
        image_width = 308 if self.devices[self.selected].get('kind_code') == 3 or 'dpi' in self.devices[self.selected] else 580
        left = max(135, (width - image_width) / 2 - 15)
        top = max(15, (height - 480) / 2 - 12)
        canvas.move(self.device_picture, left, top)
        if self.overlay_picture: canvas.move(self.overlay_picture, left + 21, top + 195)
        for widget,x,y in self.items: canvas.move(widget, left+x*308, top+y*480)
        return True
