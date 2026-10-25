"""End the current app session without changing login startup preferences."""
import subprocess


def quit_session():
    def run(command, timeout=10):
        return subprocess.run(command, check=True, capture_output=True, text=True, timeout=timeout)

    owner = run(['gdbus', 'call', '--session', '--dest', 'org.freedesktop.DBus',
                 '--object-path', '/org/freedesktop/DBus', '--method',
                 'org.freedesktop.DBus.NameHasOwner', 'local.logioptions.Rebuild'])
    if 'true' in owner.stdout:
        run(['gdbus', 'call', '--session', '--dest', 'local.logioptions.Rebuild',
             '--object-path', '/local/logioptions/Rebuild', '--method',
             'org.gtk.Actions.Activate', 'quit', '[]', '{}'])
    # Stop the listener first so failures can still be reported by the tray.
    run(['systemctl', '--user', 'stop', 'logioptions-ring.service'], timeout=50)
    # Do not wait for the tray's own process to exit from inside that process.
    run(['systemctl', '--user', '--no-block', 'stop', 'logioptions-tray.service'])
