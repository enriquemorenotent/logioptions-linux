#!/bin/sh
# Runs inside a disposable Ubuntu 26.04 container after package installation.
set -eu
cd /tmp
logioptions --help >/dev/null
/usr/bin/python3 - <<'PY'
import sys
sys.path.insert(0, '/usr/lib/logioptions-linux')
from logioptions import device, background, tray_status, session
from pathlib import Path
assert Path(device.__file__).is_relative_to('/usr/lib/logioptions-linux')
assert not Path('/usr/lib/logioptions-linux/artifacts').exists()
assert Path('/usr/share/gnome-shell/extensions/logioptions-ring@local/metadata.json').is_file()
assert Path('/usr/lib/udev/rules.d/70-logioptions.rules').is_file()
PY
# Use installed modules, while loading tests from the source checkout.
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/usr/lib/logioptions-linux /usr/bin/python3 -m unittest discover -s /src/tests -v
sandbox=$(mktemp -d)
XDG_CONFIG_HOME="$sandbox/config" XDG_DATA_HOME="$sandbox/data" XDG_CACHE_HOME="$sandbox/cache" XDG_RUNTIME_DIR="$sandbox" \
LOGIOPTIONS_ISOLATED_GUI_TEST=1 GDK_BACKEND=x11 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/usr/lib/logioptions-linux \
xvfb-run -a dbus-run-session -- /usr/bin/python3 -m unittest discover -s /src/tests -p "test_*ui.py" -v
