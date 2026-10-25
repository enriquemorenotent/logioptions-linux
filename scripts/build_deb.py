#!/usr/bin/env python3
"""Build only redistributable source files into a root-owned Debian package."""
from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
version = (root/'VERSION').read_text().strip()
if not re.fullmatch(r'\d+\.\d+\.\d+',version): raise ValueError('Invalid VERSION')
output = root/'dist';output.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='logioptions-deb-') as temporary:
    stage = Path(temporary)
    def copy(source,destination,mode=0o644):
        target=stage/destination
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(root/source,target);target.chmod(mode)
    for file in (root/'logioptions').glob('*.py'):
        copy(file.relative_to(root),'usr/lib/logioptions-linux/logioptions/'+file.name)
    for file in (root/'assets').glob('*.svg'):
        copy(file.relative_to(root),'usr/lib/logioptions-linux/assets/'+file.name)
        copy(file.relative_to(root),'usr/share/icons/hicolor/scalable/status/'+file.name)
    copy('VERSION','usr/lib/logioptions-linux/VERSION')
    copy('packaging/logioptions','usr/bin/logioptions',0o755)
    copy('packaging/local.logioptions.Rebuild.desktop','usr/share/applications/local.logioptions.Rebuild.desktop')
    copy('packaging/logioptions-session.desktop','etc/xdg/autostart/logioptions-session.desktop')
    copy('packaging/70-logioptions.rules','usr/lib/udev/rules.d/70-logioptions.rules')
    for name in ('ring','tray'):
        copy(f'packaging/logioptions-{name}.service',f'usr/lib/systemd/user/logioptions-{name}.service')
    for name in ('metadata.json','extension.js','stylesheet.css','profiles.js','actions.json'):
        copy('extensions/logioptions-ring@local/'+name,'usr/share/gnome-shell/extensions/logioptions-ring@local/'+name)
    copy('README.md','usr/share/doc/logioptions-linux/README.md')
    for name in ('postinst','prerm','postrm'):
        copy('packaging/debian/'+name,'DEBIAN/'+name,0o755)
    (stage/'DEBIAN/control').write_text((root/'packaging/debian/control').read_text().replace('@VERSION@',version))
    (stage/'DEBIAN/conffiles').write_text('/etc/xdg/autostart/logioptions-session.desktop\n')
    # APT trust is opt-in; installing a downloaded .deb never adds a repository.
    epoch=os.environ.get('SOURCE_DATE_EPOCH') or subprocess.check_output(['git','log','-1','--format=%ct'],cwd=root,text=True).strip()
    for file in stage.rglob('*'): os.utime(file,(int(epoch),int(epoch)))
    package=output/f'logioptions-linux_{version}_all.deb'
    subprocess.run(['dpkg-deb','--root-owner-group','--build',str(stage),str(package)],check=True,
                   env={**os.environ,'SOURCE_DATE_EPOCH':epoch})
    print(package)
