"""Read-only session diagnostics and an explicit user-requested listener restart."""
import subprocess
from .device_status import read_rows, view

UNITS = {'background':'logioptions-ring.service','tray':'logioptions-tray.service'}


def service_status(unit):
    try:
        result = subprocess.run(['systemctl','--user','show',unit,
            '--property=LoadState,ActiveState,SubState,Result'],capture_output=True,text=True,timeout=5)
    except (OSError,subprocess.TimeoutExpired):
        return dict(status='Unavailable',detail='Could not contact your desktop service manager.')
    values = dict(line.split('=',1) for line in result.stdout.splitlines() if '=' in line)
    if result.returncode != 0:
        return dict(status='Unavailable',detail='Could not read this service. Try checking again.')
    if values.get('LoadState')=='not-found':
        return dict(status='Not installed',detail='Install the LogiOptions package to add its background services.')
    active = values.get('ActiveState')
    if active=='active':
        return dict(status='Running',detail='Shows battery readings and opens settings.' if unit==UNITS['tray'] else 'Restores device settings and handles mouse buttons.')
    if active=='failed':
        reason = values.get('Result','unknown error').replace('-',' ')
        return dict(status='Failed',detail=f'The service stopped with {reason}. '+('Close and reopen LogiOptions to try again.' if unit==UNITS['tray'] else 'Restart it to try again.'))
    if active in ('activating','deactivating','reloading'):
        return dict(status='Starting' if active=='activating' else 'Restarting',detail='Wait a moment for the service to settle.')
    if active=='inactive':
        detail = ('Close and reopen LogiOptions to start the tray icon.' if unit==UNITS['tray']
                  else 'Restart the background service to start device handling.')
        return dict(status='Stopped',detail=detail)
    return dict(status='Unavailable',detail='The desktop service manager returned an unknown state. Check again.')


def extension_status():
    from .ring import shell_call
    try:
        if shell_call('Ping').unpack()!=('ready',):
            return dict(status='Unavailable',detail='The GNOME extension did not report ready.')
        try:
            current = shell_call('ButtonVersion').unpack()
        except Exception:
            current = None
        if current!=(1,):
            return dict(status='Update needs a new login',detail='Actions Ring is available. Log out of Ubuntu and back in once to load button shortcut support.')
        return dict(status='Ready',detail='Actions Ring and button shortcuts are available.')
    except Exception:
        pass
    try:
        info=extension_info()
        if not info:
            return dict(status='Not installed',detail='Install the LogiOptions package, then log out and back in to load its GNOME extension.')
        state=info.get('state')
        if hasattr(state,'unpack'):state=state.unpack()
        if state==3:
            return dict(status='Failed to load',detail='Open GNOME Extensions to inspect the error. A new login can reload the extension.')
        if state==4:
            return dict(status='Incompatible',detail='This extension requires the supported GNOME 50 desktop.')
        enabled=info.get('enabled')
        if hasattr(enabled,'unpack'):enabled=enabled.unpack()
        if enabled is False:
            return dict(status='Disabled',detail='Enable the LogiOptions extension in GNOME Extensions.')
        return dict(status='Not ready',detail='Wait a moment, then check again. A new extension installation needs a new login.')
    except Exception:
        return dict(status='Unavailable',detail='Could not contact the GNOME extension. Use the supported GNOME desktop and check again.')


def extension_info():
    from gi.repository import Gio,GLib
    connection=Gio.bus_get_sync(Gio.BusType.SESSION,None)
    return connection.call_sync('org.gnome.Shell.Extensions','/org/gnome/Shell/Extensions',
        'org.gnome.Shell.Extensions','GetExtensionInfo',GLib.Variant('(s)',('logioptions-ring@local',)),
        None,Gio.DBusCallFlags.NONE,1500,None).unpack()[0]


def device_status():
    rows=read_rows()
    if not rows:
        return dict(status='Waiting for devices',detail='Connect or wake your mouse or keyboard, then refresh the main window.')
    responding=sum(view(row)['state']=='connected' for row in rows)
    if responding:
        return dict(status=f"{responding} device{'s' if responding!=1 else ''} responding",
                    detail='Recent device replies are available. Battery readings are shown in the tray.')
    return dict(status='No recent device replies',detail='Wake your devices or reconnect the receiver, then refresh the main window.')


def collect():
    return {**{key:service_status(unit) for key,unit in UNITS.items()},
            'extension':extension_status(),'devices':device_status()}


def restart_background():
    # Restart only the listener. No enable/disable, settings writes, or extension
    # reinstall: this is safe when login startup has deliberately been disabled.
    subprocess.run(['systemctl','--user','restart',UNITS['background']],
                   check=True,capture_output=True,text=True,timeout=50)
