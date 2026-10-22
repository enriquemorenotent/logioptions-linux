"""Application picker and eight-slot Actions Ring editor."""
import copy
import json
from gi.repository import Adw, Gio, Gtk
from . import profiles
from .ring import shell_call

POSITIONS = ['Top', 'Top right', 'Right', 'Bottom right', 'Bottom', 'Bottom left', 'Left', 'Top left']


class ProfileWindow(Adw.Window):
    def __init__(self, parent):
        super().__init__(title='Actions Ring profiles', transient_for=parent, modal=True,
                         default_width=620, default_height=800)
        self.config = profiles.load()
        self.key = None
        self.dirty = False
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.append(Adw.HeaderBar())
        scroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16,
                       margin_start=24, margin_end=24, margin_top=16, margin_bottom=24)
        scroll.set_child(body)
        outer.append(scroll)
        self.set_content(outer)
        title = Gtk.Label(label='A different ring for each app', xalign=0)
        title.add_css_class('title-1')
        body.append(title)
        body.append(Gtk.Label(label='The ring follows the focused window. Other apps use All apps.',
                              xalign=0, wrap=True))
        self.notice = Gtk.Label(xalign=0, wrap=True)
        try:
            self.active = shell_call('ProfileVersion').unpack() == (1,)
        except Exception:
            self.active = False
        if not self.active:
            self.notice.set_text('Profiles can be saved now. Log out of Ubuntu and back in once to load the updated ring extension.')
        body.append(self.notice)
        apps = {a.get_id(): a.get_display_name() for a in Gio.AppInfo.get_all()
                if a.get_id() and a.should_show()}
        try:
            for app in json.loads(shell_call('ListApplications').unpack()[0]):
                apps[app['id']] = app['name']
        except Exception:
            pass
        apps.update({key: value['name'] for key, value in self.config['applications'].items()})
        self.apps = [(None, 'All apps')] + sorted(apps.items(), key=lambda p: (p[1].casefold(), p[0]))
        # Show launcher IDs only when two apps have the same display name.
        from collections import Counter
        counts = Counter(name for _, name in self.apps)
        names = [name if counts[name] == 1 else f'{name} · {key}' for key, name in self.apps]
        body.append(Gtk.Label(label='Application', xalign=0))
        self.picker = Gtk.DropDown.new_from_strings(names)
        self.picker.set_enable_search(True)
        self.picker.connect('notify::selected', self.choose)
        body.append(self.picker)
        self.description = Gtk.Label(xalign=0, wrap=True)
        body.append(self.description)
        self.action_ids = list(profiles.ACTIONS)
        action_names = [profiles.ACTIONS[key][0] for key in self.action_ids]
        group = Adw.PreferencesGroup(title='Ring actions', description='Clockwise, starting at the top')
        self.slots = []
        for position in POSITIONS:
            row = Adw.ActionRow(title=position)
            choice = Gtk.DropDown.new_from_strings(action_names)
            choice.set_valign(Gtk.Align.CENTER)
            choice.connect('notify::selected', lambda *_: self.changed())
            row.add_suffix(choice)
            group.add(row)
            self.slots.append(choice)
        body.append(group)
        self.feedback = Gtk.Label(xalign=0, wrap=True)
        footer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                         margin_start=24, margin_end=24, margin_top=12, margin_bottom=16)
        outer.append(footer)
        footer.append(self.feedback)
        buttons = Gtk.Box(spacing=12)
        self.reset = Gtk.Button(label='Reset to original')
        self.reset.connect('clicked', self.reset_profile)
        buttons.append(self.reset)
        self.save_button = Gtk.Button(label='Save profile', hexpand=True)
        self.save_button.add_css_class('suggested-action')
        self.save_button.connect('clicked', self.save_profile)
        buttons.append(self.save_button)
        footer.append(buttons)
        body.append(Gtk.Label(label='Actions send keyboard shortcuts. Their effect depends on the app.', xalign=0, wrap=True))
        self.loading = False
        self.load_selection()
        self.connect('close-request', lambda *_: self.dirty and not self.save_profile())

    def changed(self):
        if not getattr(self, 'loading', True):
            self.dirty = True
            self.feedback.set_text('Unsaved changes')

    def choose(self, *_):
        index = self.picker.get_selected()
        # Keep edits when switching apps by saving first; failures retain the
        # previous selection and edits instead of silently discarding them.
        if self.dirty and not self.save_profile():
            self.picker.handler_block_by_func(self.choose)
            self.picker.set_selected(next(i for i, app in enumerate(self.apps) if app[0] == self.key))
            self.picker.handler_unblock_by_func(self.choose)
            return
        self.key = self.apps[index][0]
        self.load_selection()

    def load_selection(self):
        self.loading = True
        profile = self.config['applications'].get(self.key)
        values = profile['slots'] if profile else self.config['default']
        for choice, action in zip(self.slots, values):
            choice.set_selected(self.action_ids.index(action))
        self.description.set_text('Default layout for apps without a profile.' if self.key is None else
                                  'Custom layout for this app.' if profile else 'Using All apps. Change an action and save to create a profile.')
        self.reset.set_label('Reset to original' if self.key is None else 'Use All apps')
        self.feedback.set_text('')
        self.dirty = False
        self.loading = False

    def save_profile(self, *_):
        candidate = copy.deepcopy(self.config)
        slots = [self.action_ids[c.get_selected()] for c in self.slots]
        if self.key is None:
            candidate['default'] = slots
        else:
            candidate['applications'][self.key] = dict(name=dict(self.apps)[self.key], slots=slots)
        try:
            profiles.save(candidate)
        except (OSError, ValueError) as error:
            self.feedback.set_text(f'Could not save: {error}')
            return False
        self.config = candidate
        self.dirty = False
        self.description.set_text('Default layout for apps without a profile.' if self.key is None else 'Custom layout for this app.')
        self.feedback.set_text('Saved. Applies next time you open the ring.' if self.active else 'Saved. Log out and back in to activate the extension update.')
        return True

    def reset_profile(self, *_):
        candidate = copy.deepcopy(self.config)
        if self.key is None: candidate['default'] = list(profiles.DEFAULT)
        else: candidate['applications'].pop(self.key, None)
        try:
            profiles.save(candidate)
        except (OSError, ValueError) as error:
            self.feedback.set_text(f'Could not save: {error}')
            return
        self.config = candidate
        self.load_selection()
        self.feedback.set_text('Original layout restored.' if self.key is None else 'This app now uses All apps.')
