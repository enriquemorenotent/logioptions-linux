"""Load recovered official descriptors for strict, version-specific validation.

Requires the protobuf dependency in requirements-research.txt. No schema field
definitions are invented here; each registry is loaded from an inspected binary.
"""
from pathlib import Path

from google.protobuf import descriptor_pb2, descriptor_pool, json_format, message_factory


class SchemaRegistry:
    def __init__(self, descriptor_set: Path):
        bundle = descriptor_pb2.FileDescriptorSet.FromString(descriptor_set.read_bytes())
        self.pool = descriptor_pool.DescriptorPool()
        pending = {}
        for descriptor in bundle.file:
            if descriptor.name in pending:
                raise ValueError(f'Duplicate descriptor: {descriptor.name}')
            pending[descriptor.name] = descriptor
        self.files = set()
        while pending:
            ready = [d for d in pending.values() if all(name in self.files for name in d.dependency)]
            if not ready:
                missing = sorted({name for d in pending.values() for name in d.dependency if name not in self.files})
                raise ValueError(f'Unresolved descriptor dependencies: {missing}')
            for descriptor in ready:
                self.pool.Add(descriptor)
                self.files.add(descriptor.name)
                del pending[descriptor.name]

    def parse_payload(self, payload: dict):
        type_url = payload.get('@type')
        if not isinstance(type_url, str) or '/' not in type_url:
            raise ValueError('Payload has no protobuf type URL')
        name = type_url.rsplit('/', 1)[1]
        descriptor = self.pool.FindMessageTypeByName(name)
        message = message_factory.GetMessageClass(descriptor)()
        json_format.ParseDict({k: v for k, v in payload.items() if k != '@type'}, message,
                              descriptor_pool=self.pool, ignore_unknown_fields=False)
        return message
