#!/usr/bin/env python3
"""Build the same public payload for standalone .deb and Launchpad source builds."""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


def stage_payload(root, stage, version):
    def copy(source,destination,mode=0o644):
        target=stage/destination
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(root/source,target);target.chmod(mode)
    for file in (root/'logioptions').glob('*.py'):
        copy(file.relative_to(root),'usr/lib/logioptions-linux/logioptions/'+file.name)
    for file in (root/'assets').glob('*.svg'):
        copy(file.relative_to(root),'usr/lib/logioptions-linux/assets/'+file.name)
        copy(file.relative_to(root),'usr/share/icons/hicolor/scalable/status/'+file.name)
    for file in (root/'assets/logitech').iterdir():
        if file.suffix in ('.png', '.ttf', '.txt'):
            copy(file.relative_to(root),'usr/lib/logioptions-linux/assets/logitech/'+file.name)
    target = stage/'usr/lib/logioptions-linux/VERSION'
    target.write_text(version+'\n')
    copy('packaging/logioptions','usr/bin/logioptions',0o755)
    copy('packaging/local.logioptions.Rebuild.desktop','usr/share/applications/local.logioptions.Rebuild.desktop')
    copy('packaging/logioptions-session.desktop','etc/xdg/autostart/logioptions-session.desktop')
    copy('packaging/70-logioptions.rules','usr/lib/udev/rules.d/70-logioptions.rules')
    for name in ('ring','tray'):
        copy(f'packaging/logioptions-{name}.service',f'usr/lib/systemd/user/logioptions-{name}.service')
    for name in ('metadata.json','extension.js','stylesheet.css','profiles.js','actions.json'):
        copy('extensions/logioptions-ring@local/'+name,'usr/share/gnome-shell/extensions/logioptions-ring@local/'+name)
    copy('README.md','usr/share/doc/logioptions-linux/README.md')
    if (root/'LICENSE').exists():
        copy('LICENSE','usr/share/doc/logioptions-linux/LICENSE')
        copy('packaging/copyright','usr/share/doc/logioptions-linux/copyright')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--stage', type=Path, help='Stage payload only for debhelper')
    parser.add_argument('--version', help='Debian version for a source-package build')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    version=args.version or (root/'VERSION').read_text().strip()
    if not re.fullmatch(r'[0-9][A-Za-z0-9.+:~\-]*',version): raise ValueError('Invalid version')
    if args.stage:
        args.stage.mkdir(parents=True,exist_ok=True)
        stage_payload(root,args.stage,version)
        return
    output=root/'dist';output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='logioptions-deb-') as temporary:
        stage=Path(temporary)
        stage_payload(root,stage,version)
        (stage/'DEBIAN').mkdir()
        for name in ('postinst','prerm','postrm'):
            target=stage/'DEBIAN'/name
            shutil.copyfile(root/'packaging/debian'/name,target);target.chmod(0o755)
        (stage/'DEBIAN/control').write_text((root/'packaging/debian/control').read_text().replace('@VERSION@',version))
        (stage/'DEBIAN/conffiles').write_text('/etc/xdg/autostart/logioptions-session.desktop\n')
        epoch=os.environ.get('SOURCE_DATE_EPOCH') or subprocess.check_output(['git','log','-1','--format=%ct'],cwd=root,text=True).strip()
        for file in stage.rglob('*'): os.utime(file,(int(epoch),int(epoch)))
        package=output/f'logioptions-linux_{version}_all.deb'
        subprocess.run(['dpkg-deb','--root-owner-group','--build',str(stage),str(package)],check=True,
                       env={**os.environ,'SOURCE_DATE_EPOCH':epoch})
        print(package)


if __name__ == '__main__':
    main()
