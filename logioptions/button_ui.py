"""Hardware and host action choices in the existing button panel."""
from gi.repository import Gdk, Gtk
from . import button_actions as bindings
from .profiles import ACTIONS
from .button_labels import shortcut_label as format_shortcut


def build(window, descriptor):
    from .gui import label, box, CONTROL_NAMES
    controls = descriptor.get('controls', [])
    sources = [c for c in controls if c['flags'] & 0x30]
    if not sources:
        return
    card = window.card('Button actions')
    source = Gtk.DropDown.new_from_strings([CONTROL_NAMES.get(c['control_id'], f"Button {c['index'] + 1}") for c in sources])
    target = Gtk.DropDown(enable_search=True)
    window.mapping_source, window.mapping_controls = source, sources
    card.append(label('Button', 'muted'))
    card.append(source)
    card.append(label('Action · all apps', 'muted'))
    card.append(target)
    recorder = box(spacing=8)
    shortcut_label = label('No shortcut recorded', 'muted')
    record = Gtk.Button(label='Record shortcut')
    recorder.append(shortcut_label)
    recorder.append(record)
    card.append(recorder)
    explanation = label('Shortcuts and desktop actions run in the background. Quit restores normal button behavior.', 'muted')
    explanation.set_wrap(True)
    card.append(explanation)
    host_ready = bindings.available()
    activation_note = label('Button shortcuts need the updated GNOME extension. Log out and back in once after installing this update.', 'muted')
    activation_note.set_wrap(True)
    card.append(activation_note)
    try:
        saved = bindings.for_device(descriptor.get('identity'))
    except (ValueError, OSError) as error:
        saved = {}
        window.status.set_text(f'Cannot read button actions: {error}')
    choices, captured = [], []
    recording = [False]

    def selection(*_):
        index = target.get_selected()
        custom = index < len(choices) and choices[index][0] == 'shortcut'
        recorder.set_visible(custom)
        host_action = index < len(choices) and choices[index][0] in ('host', 'shortcut')
        activation_note.set_visible(host_action and not host_ready)
        apply_button.set_sensitive((not host_action or host_ready) and (not custom or bool(captured)))
        recording[0] = False
        record.set_label('Record shortcut')

    def choose_button(*_):
        row = sources[source.get_selected()]
        cid = row['control_id']
        names = []
        choices.clear()
        captured.clear()
        shortcut_label.set_text('No shortcut recorded')
        def add(kind, value, name):
            choices.append((kind, value))
            names.append(name)
        add('default', None, 'Default behavior')
        if row['flags'] & 0x10:
            for item in controls:
                if item['group'] > 0 and row['group_mask'] & (1 << (item['group'] - 1)):
                    add('hardware', item['control_id'], CONTROL_NAMES.get(item['control_id'], str(item['control_id'])) + ' (built-in)')
        if cid not in (80, 81) and row['flags'] & 0x20:
            for name, _, keys in ACTIONS.values():
                if keys:
                    add('host', {'type':'shortcut', 'keys':keys}, name)
            add('shortcut', None, 'Keyboard shortcut…')
            for action, name in bindings.DESKTOP.items():
                add('host', {'type':'desktop', 'action':action}, name)
            add('host', {'type':'ring'}, 'Actions Ring')
        target.set_model(Gtk.StringList.new(names))
        current = saved.get(str(cid))
        selected = 0
        if current:
            selected = next((i for i, (kind, value) in enumerate(choices) if kind == 'host' and value == current), -1)
            if selected < 0 and current['type'] == 'shortcut':
                selected = next(i for i, (kind, _) in enumerate(choices) if kind == 'shortcut')
                captured.extend(current['keys'])
                shortcut_label.set_text(format_shortcut(captured))
        else:
            mapped = row.get('reporting', {}).get('remapped_to')
            selected = next((i for i, (kind, value) in enumerate(choices) if kind == 'hardware' and value == mapped), 0)
        target.set_selected(max(0, selected))
        selection()

    def record_clicked(*_):
        recording[0] = True
        apply_button.set_sensitive(False)
        record.set_label('Press your shortcut… (Esc cancels)')
        record.grab_focus()

    def record_key(_controller, keyval, _keycode, state):
        if not recording[0]:
            return False
        if keyval == Gdk.KEY_Escape:
            selection()
            return True
        if keyval in (Gdk.KEY_Control_L, Gdk.KEY_Control_R, Gdk.KEY_Shift_L, Gdk.KEY_Shift_R,
                      Gdk.KEY_Alt_L, Gdk.KEY_Alt_R, Gdk.KEY_Super_L, Gdk.KEY_Super_R):
            return True
        modifiers = [(Gdk.ModifierType.CONTROL_MASK, 'Control_L'), (Gdk.ModifierType.SHIFT_MASK, 'Shift_L'),
                     (Gdk.ModifierType.ALT_MASK, 'Alt_L'), (Gdk.ModifierType.SUPER_MASK, 'Super_L')]
        captured[:] = [name for mask, name in modifiers if state & mask]
        captured.append(Gdk.keyval_name(Gdk.keyval_to_lower(keyval)))
        try:
            bindings.validate_action({'type':'shortcut', 'keys':captured})
        except ValueError:
            captured.clear()
            apply_button.set_sensitive(False)
            shortcut_label.set_text('That key cannot be used. Try another shortcut.')
            return True
        shortcut_label.set_text(Gtk.accelerator_get_label(keyval, state & Gtk.accelerator_get_default_mod_mask()))
        selection()
        return True

    def apply():
        row = sources[source.get_selected()]
        cid = row['control_id']
        index = target.get_selected()
        if index >= len(choices):
            window.status.set_text('Choose an action first')
            return
        kind, value = choices[index]
        if kind in ('host', 'shortcut'):
            if not bindings.available():
                window.status.set_text('Load the updated GNOME extension before assigning shortcuts. This extension update needs a new login.')
                return
            value = {'type':'shortcut', 'keys':list(captured)} if kind == 'shortcut' else value
            try:
                bindings.validate_action(value)
            except ValueError as error:
                window.status.set_text(str(error))
                return
        def work(device):
            if device.identity() != descriptor.get('identity'):
                raise RuntimeError('Device changed; refresh before assigning a button')
            if kind in ('hardware', 'default'):
                if row['flags'] & 0x10:
                    destination = cid if kind == 'default' else value
                    device.remap_control(cid, destination)
                    actual = device.control_reporting(cid)
                    if actual['remapped_to'] != destination:
                        raise RuntimeError('Device did not accept the button action')
                    row['reporting'] = actual
                    from .preferences import save
                    save(descriptor['identity'], {f'button:{cid}':destination})
                bindings.save(descriptor['identity'], cid, None)
            else:
                bindings.save(descriptor['identity'], cid, value)
        window.action(work, 'Button action updated')

    source.connect('notify::selected', choose_button)
    target.connect('notify::selected', selection)
    record.connect('clicked', record_clicked)
    controller = Gtk.EventControllerKey.new()
    controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
    controller.connect('key-pressed', record_key)
    record.add_controller(controller)
    apply_button = window.button('Apply button action', apply, True)
    card.append(apply_button)
    choose_button()
