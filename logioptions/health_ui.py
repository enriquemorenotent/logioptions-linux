"""Asynchronous diagnostics in App settings; no receiver access or UI blocking."""
from gi.repository import Adw,GLib,Gtk
from . import health


def add(window,dialog,page):
    group=Adw.PreferencesGroup(title='Background status')
    rows={}
    for key,title in [('background','Background service'),('tray','Tray icon'),
                      ('extension','GNOME extension'),('devices','Device communication')]:
        row=Adw.ActionRow(title=title,subtitle='Checking…',subtitle_lines=3)
        rows[key]=row
        group.add(row)
    actions=Gtk.Box(spacing=10,margin_top=12,halign=Gtk.Align.END)
    check=Gtk.Button(label='Check again')
    restart=Gtk.Button(label='Restart background service')
    check.add_css_class('control-button')
    restart.add_css_class('control-button')
    restart.add_css_class('suggested-action')
    actions.append(check);actions.append(restart)
    group.add(actions)
    page.add(group)
    state={'closed':False,'busy':False,'source':None,'parent_handler':None}

    def refresh(*_, restarting=False):
        if state['closed'] or window.closed:
            state['source']=None
            return False
        if state['busy']:
            return True
        state['busy']=True
        check.set_sensitive(False);restart.set_sensitive(False)
        if restarting:
            rows['background'].set_subtitle('Restarting…')
        def work():
            if restarting: health.restart_background()
            return health.collect()
        future=window.pool.submit(work)
        def complete():
            if state['closed'] or window.closed:
                return False
            state['busy']=False
            check.set_sensitive(True);restart.set_sensitive(True)
            try:
                result=future.result()
                rows['background'].set_tooltip_text(None)
                for key,row in rows.items():
                    row.set_subtitle(result[key]['status']+' · '+result[key]['detail'])
                restart.set_sensitive(result['background']['status']!='Not installed')
                if restarting:
                    running=result['background']['status']=='Running'
                    dialog.add_toast(Adw.Toast(title='Background service restarted' if running else 'Service restarted but is not running. Check its status.'))
            except Exception as error:
                rows['background'].set_subtitle('Could not restart. Check again to read its current status.' if restarting else 'Could not check background status. Try again.')
                detail=getattr(error,'stderr',None) or str(error)
                rows['background'].set_tooltip_text(detail.strip()[:500])
                dialog.add_toast(Adw.Toast(title='Could not restart background service' if restarting else 'Could not check background status'))
            return False
        future.add_done_callback(lambda _:GLib.idle_add(complete))
        return True

    check.connect('clicked',refresh)
    restart.connect('clicked',lambda *_:refresh(restarting=True))
    state['source']=GLib.timeout_add_seconds(10,refresh)
    def close(*_):
        if not state['closed']:
            state['closed']=True
            if state['source'] is not None:
                GLib.source_remove(state['source'])
                state['source']=None
            if state['parent_handler'] is not None:
                window.disconnect(state['parent_handler'])
                state['parent_handler']=None
        return False
    dialog.connect('close-request',close)
    # The parent may be closed by the tray's Quit action while this dialog is up.
    state['parent_handler']=window.connect('close-request',close)
    refresh()
