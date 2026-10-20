import base64
import json
from pathlib import Path
import shutil
import subprocess
import unittest

from logioptions.framing import Decoder, MAX_FRAME, encode, encode_legacy

ROOT = Path(__file__).resolve().parents[1]


class FramingTests(unittest.TestCase):
    def test_legacy_official_encoder_differential(self):
        source = ROOT / 'artifacts/mac-live-1.32/sources/339.txt'
        if not source.exists() or not shutil.which('node'):
            self.skipTest('Requires the extracted 1.32 source map and Node')
        payloads = [b'', b'{}', '{"text":"Grüße 🖱"}'.encode(), b'x' * 65536]
        process = subprocess.run(
            ['node', str(ROOT / 'scripts/official_legacy_frame_oracle.cjs'), str(source)],
            input=json.dumps([base64.b64encode(p).decode() for p in payloads]),
            text=True, capture_output=True, check=True, timeout=10,
        )
        frames = [encode_legacy(p) for p in payloads]
        self.assertEqual(json.loads(process.stdout), [f.hex() for f in frames])
        joined = b''.join(frames)
        for split in range(len(joined) + 1):
            decoder = Decoder(framing='legacy')
            self.assertEqual(decoder.feed(joined[:split]) + decoder.feed(joined[split:]), payloads)

    def test_official_encoder_differential(self):
        bundles = [ROOT / 'artifacts' / (platform + '-ui') / 'main.js'
                   for platform in ('windows', 'macos')]
        available = [bundle for bundle in bundles if bundle.exists()]
        if not available or not shutil.which('node'):
            self.skipTest('Requires extracted official 2.8.981479 main.js and Node')
        payloads = [b'', b'{}', b'{"test":1}',
                    '{"text":"Grüße 🖱"}'.encode(), b'x' * 65536]
        for bundle in available:
            with self.subTest(bundle=bundle):
                process = subprocess.run(
                    ['node', str(ROOT / 'scripts/official_frame_oracle.cjs'), str(bundle)],
                    input=json.dumps([base64.b64encode(p).decode() for p in payloads]),
                    text=True, capture_output=True, check=True, timeout=10,
                )
                self.assertEqual(json.loads(process.stdout), [encode(p).hex() for p in payloads])

    def test_all_split_points_and_coalesced_frames(self):
        payloads = [b'{}', b'abc', '🖱'.encode()]
        data = b''.join(map(encode, payloads))
        for split in range(len(data) + 1):
            decoder = Decoder()
            self.assertEqual(decoder.feed(data[:split]) + decoder.feed(data[split:]), payloads)
        decoder = Decoder()
        messages = []
        for byte in data:
            messages.extend(decoder.feed(bytes([byte])))
        self.assertEqual(messages, payloads)

    def test_malformed_envelopes(self):
        for raw in [b'\0' * 4, (MAX_FRAME + 1).to_bytes(4, 'little'),
                    encode(b'{}')[:8] + b'nope' + encode(b'{}')[12:],
                    encode(b'{}')[:12] + b'\0' * 4 + b'{}']:
            with self.assertRaises(ValueError):
                Decoder().feed(raw)


if __name__ == '__main__':
    unittest.main()
