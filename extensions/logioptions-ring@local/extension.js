import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';
import Shell from 'gi://Shell';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import {selectProfile} from './profiles.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const XML = `<node><interface name="local.logioptions.Ring">
<method name="ProfileVersion"><arg type="u" direction="out"/></method>
<method name="ListApplications"><arg type="s" direction="out"/></method>
<method name="Show"/><method name="Release"/><method name="Hide"/>
<method name="Ping"><arg type="s" direction="out"/></method>
</interface></node>`;
function readJSON(path) {
    const [ok, bytes] = GLib.file_get_contents(path);
    if (!ok) throw new Error('Unable to read ring profiles');
    return JSON.parse(new TextDecoder().decode(bytes));
}

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
    ProfileVersion() { return 1; }
    ListApplications() {
        const tracker = Shell.WindowTracker.get_default();
        const apps = new Map();
        for (const actor of global.get_window_actors()) {
            const window = actor.meta_window;
            const app = tracker.get_window_app(window);
            const wm = window.get_wm_class();
            const id = app?.get_id() || (wm ? `wmclass:${wm}` : null);
            if (id) apps.set(id, {id, name: app?.get_name() || wm});
        }
        return JSON.stringify([...apps.values()]);
    }
    _profile(window) {
        const catalog = readJSON(`${this.path}/actions.json`);
        let config = null;
        try { config = readJSON(GLib.build_filenamev([GLib.get_user_config_dir(), 'logioptions', 'ring-profiles.json'])); }
        catch (error) { /* Missing or malformed config safely uses the default. */ }
        const app = window ? Shell.WindowTracker.get_default().get_window_app(window) : null;
        const profile = selectProfile(config, app?.get_id(), window?.get_wm_class(), catalog);
        return {name: profile.name, items: profile.slots.map(id => catalog[id])};
    }
    Show() {
        if (Main.sessionMode.isLocked || Main.sessionMode.isGreeter)
            return;
        if (this._overlay) { this.Hide(); return; }
        this._target = global.display.focus_window;
        const profile = this._profile(this._target);
        this._items = profile.items;
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
        const center = new St.Button({label: `${profile.name.slice(0, 16)}\n×`, x: cx - 49, y: cy - 49,
            width: 98, height: 98, style_class: 'logi-ring-center', can_focus: true});
        center.connect('clicked', () => this.Hide());
        this._overlay.add_child(center);
        this._buttons = this._items.map(([label, icon, keys], i) => {
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
        const keys = this._items?.[index]?.[2];
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
