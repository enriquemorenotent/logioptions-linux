import json
from pathlib import Path
import unittest

from logioptions.messages import get_request, parse_response

ROOT = Path(__file__).resolve().parents[1]


class MessageTests(unittest.TestCase):
    def test_recorded_official_agent_replies(self):
        baseline = ROOT / 'artifacts/mac-live-1.32/agent-baseline.json'
        if not baseline.exists():
            self.skipTest('Requires the captured official Mac agent baseline')
        for reply in json.loads(baseline.read_text())['replies']:
            with self.subTest(path=reply['path']):
                message_id = int(reply['msgId'])
                request = json.loads(get_request(message_id, reply['path']))
                self.assertEqual(request['msg_id'], reply['msgId'])
                parsed = parse_response(json.dumps(reply).encode(), message_id=message_id, path=reply['path'])
                self.assertEqual(parsed['result']['code'], 'SUCCESS')
                with self.assertRaises(ValueError):
                    parse_response(json.dumps(reply).encode(), message_id=message_id + 1, path=reply['path'])

    def test_invalid_request_identity(self):
        for message_id in (0, -1, True, '1'):
            with self.assertRaises(ValueError):
                get_request(message_id, '/devices/list')


if __name__ == '__main__':
    unittest.main()
