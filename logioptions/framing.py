"""Options+ frontend-to-agent framing, recovered from Windows 2.8.981479.

This is transport framing only, not a device driver or an agent implementation.
See research/IPC.md for evidence and direction-specific limitations.
"""
import struct

MAX_FRAME = 16 * 1024 * 1024
LEGACY_MAGIC = b'FARS'


def encode(payload: bytes) -> bytes:
    """Encode the frontend's `json` envelope without altering payload bytes."""
    size = 12 + len(payload)
    if size > MAX_FRAME:
        raise ValueError('Frame exceeds local size limit')
    return struct.pack('<I', size) + struct.pack('>I', 4) + b'json' + struct.pack('>I', len(payload)) + payload


def encode_legacy(payload: bytes) -> bytes:
    """Encode the magic-prefixed framing in official macOS 1.32.363144."""
    return LEGACY_MAGIC + encode(payload)[4:]


class Decoder:
    """Incrementally decode frontend frames; accepts split/coalesced writes."""

    def __init__(self, *, framing='length'):
        if framing not in ('length', 'legacy'):
            raise ValueError('Unknown framing version')
        self.framing = framing
        self.buffer = bytearray()

    def feed(self, chunk: bytes) -> list[bytes]:
        self.buffer.extend(chunk)
        messages = []
        while len(self.buffer) >= 4:
            if self.framing == 'legacy':
                size = None
                invalid = self.buffer[:4] != LEGACY_MAGIC
            else:
                size, = struct.unpack_from('<I', self.buffer)
                invalid = size < 12 or size > MAX_FRAME
            if invalid:
                self.buffer.clear()
                raise ValueError('Invalid frame length')
            if len(self.buffer) < 8:
                break
            protocol_size, = struct.unpack_from('>I', self.buffer, 4)
            if protocol_size != 4:
                self.buffer.clear()
                raise ValueError('Unsupported protocol length')
            if len(self.buffer) < 16:
                break
            payload_size, = struct.unpack_from('>I', self.buffer, 12)
            if size is None:
                size = payload_size + 12
            if self.buffer[8:12] != b'json' or size != payload_size + 12 or size > MAX_FRAME:
                self.buffer.clear()
                raise ValueError('Invalid JSON frame envelope')
            if len(self.buffer) < size + 4:
                break
            messages.append(bytes(self.buffer[16:size + 4]))
            del self.buffer[:size + 4]
        return messages
