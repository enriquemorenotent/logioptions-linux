#!/bin/bash
# Collect a local baseline from the Mac without changing Options+ or devices.
set -eu
umask 077
capture_dir="$(mktemp -d "${TMPDIR:-/tmp}/optionsplus-baseline.XXXXXX")"
app="/Applications/logioptionsplus.app"

/usr/bin/sw_vers > "$capture_dir/os.txt"
/usr/bin/uname -m > "$capture_dir/architecture.txt"
/bin/ps -axo pid,ppid,comm | /usr/bin/awk 'NR == 1 || /[Ll]ogi|[Oo]ptionsplus/' > "$capture_dir/processes.txt"
if [ -f "$app/Contents/Info.plist" ]; then
    /usr/bin/plutil -convert json -o "$capture_dir/app-info.json" "$app/Contents/Info.plist"
fi
if [ -f "$app/Contents/Resources/app.asar" ]; then
    /usr/bin/shasum -a 256 "$app/Contents/Resources/app.asar" > "$capture_dir/ui-sha256.txt"
fi
/usr/sbin/system_profiler SPUSBDataType -json > "$capture_dir/usb.json"
for agent_pid in $(/usr/bin/pgrep -x logioptionsplus_agent || true); do
    /usr/sbin/lsof -nP -a -p "$agent_pid" -U > "$capture_dir/agent-$agent_pid-unix-sockets.txt" 2>&1 || true
    /usr/sbin/lsof -nP -a -p "$agent_pid" -i > "$capture_dir/agent-$agent_pid-network-sockets.txt" 2>&1 || true
done
cat > "$capture_dir/README.txt" <<'EOF'
Options+ runtime baseline only. No IPC or device packets are captured yet.
Includes OS/app versions, process names, socket paths and USB device metadata.
Does not copy account settings, cookies, clipboard content or application logs.
Review before sharing. No network upload is performed.
EOF
/usr/bin/ditto -c -k --keepParent "$capture_dir" "$capture_dir.zip"
/usr/bin/printf 'Baseline saved to: %s.zip\n' "$capture_dir"
