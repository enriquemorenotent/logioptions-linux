#!/usr/bin/env python3
"""Temporarily assign Back to Ctrl+Shift+F12 and verify real GNOME input delivery.

No settings are persisted. The normal listener yields its receiver lease while
this test owns the mouse. The test restores reporting and releases the lease on
success, timeout, or window close. Never starts the packaged session launcher.
"""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--count',type=int,default=1)
    parser.add_argument('--timeout',type=int,default=120)
    args=parser.parse_args()
    if not 1 <= args.count <= 10 or not 10 <= args.timeout <= 300:
        parser.error('count must be 1–10 and timeout 10–300 seconds')
    import gi
    gi.require_version('Gtk','4.0')
    from gi.repository import Gtk,Gdk,GLib
    from logioptions import button_actions
    from logioptions.background import foreground_access
    from logioptions.discovery import discover
    from logioptions.ring import RingListener
    if not button_actions.available():
        raise SystemExit('Updated GNOME extension is not loaded. Log out and back in before testing.')
    output=ROOT/'artifacts/button-mouse-test/live-result.json'
    output.parent.mkdir(parents=True,exist_ok=True)
    result={'started':time.time(),'shortcuts_received':0,'restoration_verified':False,'events':[]}
    def log(event):
        result['events'].append(event)
        output.write_text(json.dumps(result,indent=2)+'\n')
        print(event,flush=True)
    app=Gtk.Application(application_id='local.logioptions.ButtonMouseTest')
    listener=None
    errors=[]
    with foreground_access():
        devices,discovery_errors=discover()
        mouse=next((d for d in devices if d['name']=='MX Master 4'),None)
        if not mouse:
            raise SystemExit('MX Master 4 not found: '+ '; '.join(discovery_errors))
        control=next((c for c in mouse['controls'] if c['control_id']==83 and c['flags'] & 0x20),None)
        if not control:
            raise SystemExit('This mouse does not advertise Back button diversion')
        log('Mouse identity: '+mouse['identity'])
        action={'type':'shortcut','keys':['Control_L','Shift_L','F12']}
        def activate(application):
            nonlocal listener
            window=Gtk.ApplicationWindow(application=application,title='LogiOptions — mouse button test',
                                         default_width=580,default_height=240)
            content=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=18,
                            margin_top=28,margin_bottom=28,margin_start=28,margin_end=28)
            heading=Gtk.Label(label='Preparing the mouse…',wrap=True)
            content.append(heading)
            content.append(Gtk.Label(label='Keep this window focused. The Back button will temporarily send Ctrl+Shift+F12.',wrap=True))
            stop=Gtk.Button(label='Cancel test')
            stop.connect('clicked',lambda *_:app.quit())
            content.append(stop)
            window.set_child(content)
            def status(message):
                log(message)
                if message.startswith('Actions Ring stopped:'):
                    errors.append(message)
                    GLib.idle_add(app.quit)
                def update():
                    if 'ready' in message.lower():
                        heading.set_text(f'Press the rear side button (Back) {args.count} time(s).')
                    return False
                GLib.idle_add(update)
            def key_pressed(_controller,keyval,_code,state):
                if keyval==Gdk.KEY_F12 and state & Gdk.ModifierType.CONTROL_MASK and state & Gdk.ModifierType.SHIFT_MASK:
                    result['shortcuts_received']+=1
                    log(f"Shortcut received: {result['shortcuts_received']}")
                    if result['shortcuts_received']>=args.count:
                        GLib.idle_add(app.quit)
                    return True
                return False
            controller=Gtk.EventControllerKey.new()
            controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
            controller.connect('key-pressed',key_pressed)
            window.add_controller(controller)
            window.present()
            stop.grab_focus()
            listener=RingListener(mouse,status,bindings=lambda:{'83':action})
            GLib.timeout_add_seconds(args.timeout,lambda:(log('Test timed out'),app.quit(),False)[2])
        app.connect('activate',activate)
        try:
            app.run([sys.argv[0]])
        finally:
            if listener:
                listener.stop()
                result['restoration_verified']=not errors
                log('Temporary reporting restored' if not errors else 'Restoration needs inspection; see errors above')
    log('Receiver released to the normal background service')
    return 0 if result['shortcuts_received']==args.count and not errors else 1


if __name__=='__main__':
    raise SystemExit(main())
