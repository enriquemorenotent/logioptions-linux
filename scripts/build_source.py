#!/usr/bin/env python3
"""Create a clean Launchpad source package from an explicit public-file allowlist."""
import argparse
from datetime import datetime, timezone
import email.utils
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--maintainer',required=True,help='Name <verified Launchpad email>')
    parser.add_argument('--revision',default='0ubuntu1~ppa1')
    args=parser.parse_args()
    if '\n' in args.maintainer or not re.fullmatch(r'[^<>]+ <[^<>\s]+@[^<>\s]+>',args.maintainer):
        raise ValueError('Use a valid packaging identity')
    if not re.fullmatch(r'[A-Za-z0-9.+~]+',args.revision): raise ValueError('Invalid revision')
    root=Path(__file__).resolve().parents[1]
    if not (root/'LICENSE').is_file():
        raise SystemExit('Choose and add an eligible LICENSE before building a public source upload.')
    upstream=(root/'VERSION').read_text().strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+',upstream): raise ValueError('Invalid VERSION')
    version=upstream+'-'+args.revision
    output=root/'dist/ppa';output.mkdir(parents=True,exist_ok=True)
    tree=output/f'logioptions-linux-{upstream}'
    if tree.exists(): shutil.rmtree(tree)
    tree.mkdir()
    files=[root/'VERSION',root/'README.md',root/'LICENSE',root/'scripts/build_deb.py']
    for folder,pattern in [('logioptions','*.py'),('assets','*.svg'),('tests','*.py'),('tests','*.mjs')]:
        files.extend((root/folder).glob(pattern))
    files.extend(p for p in (root/'packaging').rglob('*') if p.is_file() and p.suffix not in ('.pyc',))
    files.extend(p for p in (root/'extensions/logioptions-ring@local').iterdir() if p.is_file() and p.suffix in ('.js','.json','.css'))
    for file in files:
        target=tree/file.relative_to(root);target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(file,target)
    epoch=int(os.environ.get('SOURCE_DATE_EPOCH') or subprocess.check_output(['git','log','-1','--format=%ct'],cwd=root,text=True).strip())
    with tarfile.open(output/f'logioptions-linux_{upstream}.orig.tar.xz','w:xz') as archive:
        def normalized(info):
            info.uid=info.gid=0;info.uname=info.gname='root';info.mtime=epoch
            return info
        archive.add(tree,arcname=tree.name,filter=normalized)
    debian=tree/'debian';(debian/'source').mkdir(parents=True)
    (debian/'source/format').write_text('3.0 (quilt)\n')
    binary=(root/'packaging/debian/control').read_text()
    binary='\n'.join(line for line in binary.splitlines() if not line.startswith(('Version:','Maintainer:','Section:','Priority:','Homepage:')))
    binary=binary.replace('Depends: ', 'Depends: ${misc:Depends}, ')
    (debian/'control').write_text(f'Source: logioptions-linux\nSection: utils\nPriority: optional\nMaintainer: {args.maintainer}\nBuild-Depends: debhelper-compat (= 13), python3, nodejs\nStandards-Version: 4.7.0\nRules-Requires-Root: no\nHomepage: https://github.com/enriquemorenotent/logioptions-linux\n\n'+binary+'\n')
    (debian/'changelog').write_text(f'logioptions-linux ({version}) resolute; urgency=medium\n\n  * Initial Launchpad packaging for Ubuntu 26.04 and GNOME 50.\n\n -- {args.maintainer}  {email.utils.format_datetime(datetime.fromtimestamp(epoch, timezone.utc))}\n')
    shutil.copyfile(root/'packaging/ppa/rules',debian/'rules');(debian/'rules').chmod(0o755)
    shutil.copyfile(root/'packaging/copyright',debian/'copyright')
    for name in ('postinst','prerm','postrm'):
        shutil.copyfile(root/'packaging/debian'/name,debian/name);(debian/name).chmod(0o755)
    subprocess.run(['dpkg-buildpackage','-S','-us','-uc','-d'],cwd=tree,check=True)
    print('Unsigned source upload prepared:',output/f'logioptions-linux_{version}_source.changes')


if __name__=='__main__': main()
