#!/usr/bin/env python3
"""Build a signed Pages APT repository; refuse unsigned publication."""
import gzip
import hashlib
import html
import os
from pathlib import Path
import re
import shutil
import subprocess

root=Path(__file__).resolve().parents[1]
version=(root/'VERSION').read_text().strip()
key=os.environ['APT_GPG_KEY_ID']
passphrase=os.environ['APT_GPG_PASSPHRASE_FILE']
if not re.fullmatch(r'[A-Fa-f0-9]{40,64}',key): raise ValueError('Use a full signing fingerprint')
package=root/'dist'/f'logioptions-linux_{version}_all.deb'
assert subprocess.check_output(['dpkg-deb','-f',str(package),'Package'],text=True).strip()=='logioptions-linux'
assert subprocess.check_output(['dpkg-deb','-f',str(package),'Version'],text=True).strip()==version
pages=root/'pages';apt=pages/'apt'
if pages.exists(): shutil.rmtree(pages)
(apt/'pool/main').mkdir(parents=True)
shutil.copy2(package,apt/'pool/main'/package.name)
index_dir=apt/'dists/resolute/main/binary-amd64';index_dir.mkdir(parents=True)
index=subprocess.check_output(['apt-ftparchive','packages','pool'],cwd=apt)
(index_dir/'Packages').write_bytes(index)
(index_dir/'Packages.gz').write_bytes(gzip.compress(index,mtime=0))
release_dir=apt/'dists/resolute'
release=subprocess.check_output(['apt-ftparchive',
 '-o','APT::FTPArchive::Release::Origin=Options for Linux',
 '-o','APT::FTPArchive::Release::Label=Options for Linux',
 '-o','APT::FTPArchive::Release::Suite=resolute',
 '-o','APT::FTPArchive::Release::Codename=resolute',
 '-o','APT::FTPArchive::Release::Architectures=amd64',
 '-o','APT::FTPArchive::Release::Components=main',
 'release','.'],cwd=release_dir)
(release_dir/'Release').write_bytes(release)
base=['gpg','--batch','--yes','--pinentry-mode','loopback','--passphrase-file',passphrase,'--local-user',key]
subprocess.run(base+['--clearsign','--output',str(release_dir/'InRelease'),str(release_dir/'Release')],check=True)
subprocess.run(base+['--armor','--detach-sign','--output',str(release_dir/'Release.gpg'),str(release_dir/'Release')],check=True)
public=subprocess.check_output(['gpg','--batch','--export',key])
(apt/'logioptions-linux-archive-keyring.gpg').write_bytes(public)
(apt/'logioptions-linux.sources').write_text('Types: deb\nURIs: https://enriquemorenotent.github.io/logioptions-linux/apt\nSuites: resolute\nComponents: main\nArchitectures: amd64\nSigned-By: /usr/share/keyrings/logioptions-linux-archive-keyring.gpg\n')
subprocess.run(['gpgv','--keyring',str(apt/'logioptions-linux-archive-keyring.gpg'),str(release_dir/'InRelease')],check=True)
sha=hashlib.sha256(package.read_bytes()).hexdigest()
(root/'dist/SHA256SUMS').write_text(f'{sha}  {package.name}\n')
(pages/'.nojekyll').touch()
shutil.copyfile(root/'scripts/setup_repository.sh', pages/'install.sh')
(pages/'index.html').write_text(f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Options for Linux</title>
<style>body{{font:18px system-ui;max-width:760px;margin:64px auto;padding:0 24px;background:#faf9ff;color:#242627}}h1{{font-size:48px}}a{{color:#7040dc}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#eeebf4;padding:20px;border-radius:12px;font-size:14px}}</style>
<h1>Options for Linux</h1><p>Native Logitech device controls, a battery tray, and Actions Ring.</p>
<p>Experimental release {html.escape(version)} for Ubuntu 26.04 amd64 with GNOME 50. Independent project; not affiliated with Logitech. Includes third-party device artwork and fonts; see the release asset notices.</p>
<p><a href="https://github.com/enriquemorenotent/logioptions-linux/releases/tag/v{version}">Download the .deb</a> · <a href="https://github.com/enriquemorenotent/logioptions-linux">Project and help</a></p>
<h2>Install with updates</h2><pre>curl -fsSL https://enriquemorenotent.github.io/logioptions-linux/install.sh | sudo bash</pre>
<p>This configures our signed GitHub Pages repository and installs the app. It also migrates the former Launchpad PPA. <a href="install.sh">Review the setup script</a>.</p>
<h2>Already using the PPA?</h2><p>Run the same setup command once. Your settings are preserved; future updates arrive through normal APT upgrades. The PPA no longer receives releases.</p>
<p>Signing-key fingerprint: <code>{key}</code></p><p>Open Options for Linux after installation. The extension needs a logout/login on first installation. Later updates use normal APT upgrades; extension changes may also need a new login.</p></html>''')
print('Signed repository:',apt)
