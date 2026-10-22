import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from logioptions import profiles


class ProfileTests(unittest.TestCase):
    def test_round_trip_defaults_override_and_removal(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, XDG_CONFIG_HOME=directory):
            config = profiles.load()
            config['applications']['org.example.Editor.desktop'] = dict(name='Editor', slots=['save'] * 8)
            profiles.save(config)
            self.assertEqual(profiles.load(), config)
            config['applications'].clear()
            profiles.save(config)
            self.assertEqual(profiles.load()['default'], profiles.DEFAULT)

    def test_invalid_data_does_not_replace_good_file(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, XDG_CONFIG_HOME=directory):
            config = profiles.load()
            profiles.save(config)
            before = profiles.config_path().read_bytes()
            config['default'] = ['unknown'] * 8
            with self.assertRaises(ValueError): profiles.save(config)
            self.assertEqual(profiles.config_path().read_bytes(), before)
            profiles.config_path().write_text('{broken')
            with self.assertRaises(ValueError): profiles.load()

    def test_catalog_matches_extension_and_selection(self):
        root = Path(__file__).resolve().parents[1]
        extension = root / 'extensions/logioptions-ring@local'
        catalog = json.loads((extension / 'actions.json').read_text())
        self.assertEqual(catalog, json.loads(json.dumps(profiles.ACTIONS)))
        # Execute the exact pure module used by GNOME, not a Python imitation.
        script = '''import {selectProfile, DEFAULT} from PROFILE;
import assert from 'node:assert/strict';
const catalog = CATALOG;
const config = {version:1, default:Array(8).fill('copy'), applications:{
 'editor.desktop': {name:'Editor', slots:Array(8).fill('save')},
 'wmclass:Legacy': {name:'Legacy', slots:Array(8).fill('paste')}
}};
assert.equal(selectProfile(config,'editor.desktop','Legacy',catalog).slots[0], 'save');
assert.equal(selectProfile(config,null,'Legacy',catalog).slots[0], 'paste');
assert.equal(selectProfile(config,'unknown.desktop',null,catalog).slots[0], 'copy');
assert.deepEqual(selectProfile(null,null,null,catalog).slots, DEFAULT);
config.applications['editor.desktop'].slots = ['bad'];
assert.equal(selectProfile(config,'editor.desktop',null,catalog).slots[0], 'copy');
config.version = 2;
assert.deepEqual(selectProfile(config,'editor.desktop',null,catalog).slots, DEFAULT);
'''.replace('PROFILE', json.dumps((extension / 'profiles.js').as_uri())).replace('CATALOG', json.dumps(catalog))
        subprocess.run(['node', '--input-type=module', '-e', script], check=True, capture_output=True)
