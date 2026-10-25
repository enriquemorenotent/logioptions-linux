import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class PackagingTests(unittest.TestCase):
    def test_standalone_and_source_builds_share_public_payload(self):
        spec=importlib.util.spec_from_file_location('build_deb',ROOT/'scripts/build_deb.py')
        builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
        with tempfile.TemporaryDirectory() as directory:
            stage=Path(directory)
            builder.stage_payload(ROOT,stage,'0.1.0-0ubuntu1~ppa1')
            self.assertEqual((stage/'usr/lib/logioptions-linux/VERSION').read_text(),'0.1.0-0ubuntu1~ppa1\n')
            self.assertTrue((stage/'usr/bin/logioptions').stat().st_mode & 0o111)
            self.assertTrue((stage/'usr/lib/udev/rules.d/70-logioptions.rules').is_file())
            self.assertTrue((stage/'usr/share/gnome-shell/extensions/logioptions-ring@local/extension.js').is_file())
            self.assertFalse((stage/'DEBIAN').exists())
            self.assertFalse(any('artifacts' in p.parts for p in stage.rglob('*')))
            for source in (ROOT/'assets/logitech').iterdir():
                self.assertEqual((stage/'usr/lib/logioptions-linux/assets/logitech'/source.name).read_bytes(), source.read_bytes())
