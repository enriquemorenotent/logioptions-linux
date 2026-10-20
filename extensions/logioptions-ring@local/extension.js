import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';
import Shell from 'gi://Shell';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const XML = `<node><interface name="local.logioptions.Ring">
<method name="Show"/><method name="Release"/><method name="Hide"/>
<method name="Ping"><arg type="s" direction="out"/></method>
</interface></node>`;
// Assignments recovered from Options+ 2.9's virtual device, CIDs 408–415.
// The angular layout is our own; Mac Command is translated to Linux Control.
const ITEMS = [
    ['Cut', 'edit-cut-symbolic', ['Control_L', 'x']],
    ['Copy', 'edit-copy-symbolic', ['Control_L', 'c']],
    ['Paste', 'edit-paste-symbolic', ['Control_L', 'v']],
    ['Forward', 'go-next-symbolic', ['Alt_L', 'Right']],
    ['Back', 'go-previous-symbolic', ['Alt_L', 'Left']],
    ['Undo', 'edit-undo-symbolic', ['Control_L', 'z']],
    ['Redo', 'edit-redo-symbolic', ['Control_L', 'Shift_L', 'z']],
    ['Empty folder', 'folder-symbolic', null],
];

export default class ActionsRing extends Extension {
    enable() {
        this._pending = new Set();
        this._keyboard = Clutter.get_default_backend().get_default_seat()
            .create_virtual_device(Clutter.InputDeviceType.KEYBOARD_DEVICE);
        this._dbus = Gio.DBusExportedObject.wrapJSObject(XML, this);
        this._dbus.export(Gio.DBus.session, '/local/logioptions/Ring');
        this._session = Main.sessionMode.connect('updated', () => this.Hide());
    }
    Ping() { return 'ready'; }
    Show() {
        if (Main.sessionMode.isLocked || Main.sessionMode.isGreeter)
            return;
        if (this._overlay) { this.Hide(); return; }
        this._target = global.display.focus_window;
        const [px, py] = global.get_pointer();
        this._origin = [px, py];
        const monitor = Main.layoutManager.findMonitorForPoint(px, py) ?? Main.layoutManager.primaryMonitor;
        const radius = 154;
        const cx = Math.max(monitor.x + 220, Math.min(px, monitor.x + monitor.width - 220));
        const cy = Math.max(monitor.y + 220, Math.min(py, monitor.y + monitor.height - 220));
        this._overlay = new St.Widget({reactive: true, can_focus: true,
            width: global.stage.width, height: global.stage.height});
        Main.layoutManager.addTopChrome(this._overlay);
        this._overlay.connect('key-press-event', (_a, event) => {
            if (event.get_key_symbol() === Clutter.KEY_Escape) this.Hide();
            return Clutter.EVENT_STOP;
        });
        this._overlay.connect('button-press-event', (_a, event) => {
            if (event.get_source() === this._overlay) this.Hide();
            return Clutter.EVENT_PROPAGATE;
        });
        const center = new St.Button({label: 'Actions\n×', x: cx - 49, y: cy - 49,
            width: 98, height: 98, style_class: 'logi-ring-center', can_focus: true});
        center.connect('clicked', () => this.Hide());
        this._overlay.add_child(center);
        this._buttons = ITEMS.map(([label, icon, keys], i) => {
            const angle = -Math.PI / 2 + i * Math.PI / 4;
            const button = new St.Button({x: cx + Math.cos(angle) * radius - 53,
                y: cy + Math.sin(angle) * radius - 40, width: 106, height: 80,
                reactive: Boolean(keys), can_focus: Boolean(keys), track_hover: true,
                style_class: 'logi-ring-item'});
            const content = new St.BoxLayout({orientation: Clutter.Orientation.VERTICAL,
                x_align: Clutter.ActorAlign.CENTER, y_align: Clutter.ActorAlign.CENTER});
            content.add_child(new St.Icon({icon_name: icon, icon_size: 22}));
            content.add_child(new St.Label({text: label, x_align: Clutter.ActorAlign.CENTER}));
            button.set_child(content);
            button.connect('clicked', () => this._activate(i));
            this._overlay.add_child(button);
            return button;
        });
        this._grab = Main.pushModal(this._overlay, {actionMode: Shell.ActionMode.POPUP});
        global.stage.set_key_focus(center);
    }
    Release() {
        if (!this._overlay) return;
        const [x, y] = global.get_pointer();
        if (Math.hypot(x - this._origin[0], y - this._origin[1]) < 10) return;
        const index = this._buttons.findIndex(button => button.hover);
        if (index >= 0) this._activate(index);
        // A short tap leaves the ring open for a subsequent click.
    }
    _activate(index) {
        const keys = ITEMS[index]?.[2];
        if (!keys) return;
        const target = this._target;
        this.Hide();
        const id = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 80, () => {
            this._pending.delete(id);
            // Never deliver a shortcut to a different window or a locked session.
            if (!Main.sessionMode.isLocked && target && global.display.focus_window === target) {
                const values = keys.map(key => Clutter[`KEY_${key}`]);
                const now = GLib.get_monotonic_time();
                for (const value of values) this._keyboard.notify_keyval(now, value, Clutter.KeyState.PRESSED);
                for (const value of values.reverse()) this._keyboard.notify_keyval(now, value, Clutter.KeyState.RELEASED);
            }
            return GLib.SOURCE_REMOVE;
        });
        this._pending.add(id);
    }
    Hide() {
        if (this._grab) { Main.popModal(this._grab); this._grab = null; }
        this._overlay?.destroy();
        this._overlay = null;
        this._buttons = [];
    }
    disable() {
        this.Hide();
        for (const id of this._pending) GLib.source_remove(id);
        this._pending.clear();
        Main.sessionMode.disconnect(this._session);
        this._dbus.unexport();
        this._dbus = null;
        this._keyboard = null;
    }
}
