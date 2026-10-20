import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
try:
    HAS_PROTOBUF = importlib.util.find_spec('google.protobuf') is not None
except ModuleNotFoundError:
    HAS_PROTOBUF = False


@unittest.skipUnless(HAS_PROTOBUF, 'Requires requirements-research.txt')
class SchemaTests(unittest.TestCase):
    def test_version_matched_live_agent_payloads(self):
        from logioptions.schema import SchemaRegistry
        folder = ROOT / 'artifacts/mac-live-1.44'
        if not (folder / 'descriptors/descriptors.pb').exists():
            self.skipTest('Requires captured 1.44 agent and recovered descriptors')
        registry = SchemaRegistry(folder / 'descriptors/descriptors.pb')
        replies = json.loads((folder / 'agent-baseline.json').read_text())['replies']
        checked = 0
        for reply in replies:
            if reply.get('result', {}).get('code') != 'SUCCESS':
                continue
            with self.subTest(path=reply['path']):
                payload = reply['payload']
                message = registry.parse_payload(payload)
                self.assertEqual(message.DESCRIPTOR.full_name, payload['@type'].rsplit('/', 1)[1])
                checked += 1
        self.assertEqual(checked, 4)

    def test_new_schema_does_not_silently_accept_old_fields(self):
        from logioptions.schema import SchemaRegistry
        from google.protobuf.json_format import ParseError
        descriptors = ROOT / 'artifacts/macos-protocol-descriptors/descriptors.pb'
        baseline = ROOT / 'artifacts/mac-live-1.32/agent-baseline.json'
        if not descriptors.exists() or not baseline.exists():
            self.skipTest('Requires recovered 2.8 schemas and live 1.32 baseline')
        registry = SchemaRegistry(descriptors)
        replies = json.loads(baseline.read_text())['replies']
        config = next(reply['payload'] for reply in replies if reply['path'] == '/configuration')
        with self.assertRaises(ParseError):
            registry.parse_payload(config)
