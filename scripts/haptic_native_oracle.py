#!/usr/bin/env python3
"""Emulate recovered 2.8 native haptic command construction up to dispatch.

No original executable runs on the host. Unicorn interprets the x86_64 slice.
The vector allocation helper is stubbed; dispatch records its arguments and
stops before transport, threads or OS calls. Version/hash are deliberately fixed.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from unicorn import Uc, UC_ARCH_X86, UC_MODE_64, UC_HOOK_CODE
from unicorn.x86_const import (UC_X86_REG_RSP, UC_X86_REG_RIP, UC_X86_REG_RDI,
                              UC_X86_REG_RSI, UC_X86_REG_RDX, UC_X86_REG_RCX,
                              UC_X86_REG_R8)

EXPECTED_SHA256 = '9eaacbd1814bce162f8320ffa1a7704c984b7478160b9bc36f690875503af379'
METHODS = dict(getCapabilities=0x10039f0d0, getHapticConfig=0x10039fcd0,
               setHapticConfig=0x1003a08d0, getHapticInfo=0x1003a1540,
               playHapticWaveForm=0x1003a2140, stopHapticWaveForm=0x1003a2da0,
               getPlayingWaveForm=0x1003a39a0)
APPEND = 0x10033aab0
BASE = 0x600000000000
STACK = 0x700000000000


class NativeOracle:
    def __init__(self, binary):
        original = binary.read_bytes()
        if hashlib.sha256(original).hexdigest() != EXPECTED_SHA256:
            raise ValueError('Oracle only supports the inspected macOS 2.8.981479 agent hash')
        magic, count = struct.unpack_from('>II', original)
        if magic != 0xcafebabe:
            raise ValueError('Expected inspected universal binary')
        image = None
        for index in range(count):
            cpu, subtype, offset, size, alignment = struct.unpack_from('>5I', original, 8 + index * 20)
            if cpu == 0x01000007:
                image = memoryview(original)[offset:offset + size]
                break
        if image is None or struct.unpack_from('<I', image)[0] != 0xfeedfacf:
            raise ValueError('Expected x86_64 Mach-O slice')
        self.uc = Uc(UC_ARCH_X86, UC_MODE_64)
        ncmds = struct.unpack_from('<I', image, 16)[0]
        at = 32
        for _ in range(ncmds):
            command, command_size = struct.unpack_from('<II', image, at)
            if command == 0x19:
                fields = struct.unpack_from('<II16sQQQQiiII', image, at)
                vmaddr, vmsize, fileoff, filesize = fields[3:7]
                if vmsize and vmaddr:
                    self.uc.mem_map(vmaddr, (vmsize + 4095) & ~4095)
                    if filesize:
                        self.uc.mem_write(vmaddr, bytes(image[fileoff:fileoff + filesize]))
            at += command_size
        self.uc.mem_map(0, 4096)  # Unbound stack-guard import points to zero in the static image.
        self.uc.mem_map(BASE, 0x10000)
        self.uc.mem_map(STACK, 0x10000)
        self.uc.mem_write(BASE, struct.pack('<Q', BASE + 0x1000))
        self.uc.mem_write(BASE + 0x1038, struct.pack('<Q', BASE + 0x2000))
        self.uc.mem_write(BASE + 0x2000, b'\xc3')
        self.uc.hook_add(UC_HOOK_CODE, self._append, begin=APPEND, end=APPEND)
        self.uc.hook_add(UC_HOOK_CODE, self._dispatch, begin=BASE + 0x2000, end=BASE + 0x2000)
        self.result = None

    def _append(self, uc, address, size, user_data):
        vector, count, value = (uc.reg_read(reg) for reg in (UC_X86_REG_RDI, UC_X86_REG_RSI, UC_X86_REG_RDX))
        if count > 64:
            raise ValueError('Unexpected vector allocation')
        pointer = BASE + 0x5000
        uc.mem_write(pointer, bytes(uc.mem_read(value, 1)) * count)
        uc.mem_write(vector, struct.pack('<QQQ', pointer, pointer + count, pointer + count))
        rsp = uc.reg_read(UC_X86_REG_RSP)
        ret, = struct.unpack('<Q', uc.mem_read(rsp, 8))
        uc.reg_write(UC_X86_REG_RSP, rsp + 8)
        uc.reg_write(UC_X86_REG_RIP, ret)

    def _dispatch(self, uc, address, size, user_data):
        vector = uc.reg_read(UC_X86_REG_RCX)
        begin, end, cap = struct.unpack('<QQQ', uc.mem_read(vector, 24))
        if not 0 <= end - begin <= 64:
            raise ValueError('Unexpected dispatch parameter length')
        self.result = dict(function=uc.reg_read(UC_X86_REG_RDX),
                           payload_hex=bytes(uc.mem_read(begin, end - begin)).hex() if end > begin else '',
                           dispatch_argument_4=uc.reg_read(UC_X86_REG_R8))
        uc.emu_stop()

    def command(self, method, *, first_byte=0, second_byte=0, integer=0, boolean=False):
        if method not in METHODS:
            raise ValueError('Unknown method')
        self.result = None
        self.uc.mem_write(STACK, bytes(0x10000))
        self.uc.mem_write(BASE + 0x3000, bytes([first_byte, second_byte]))
        self.uc.mem_write(BASE + 0x4000, struct.pack('<i', integer))
        self.uc.reg_write(UC_X86_REG_RSP, STACK + 0x10000 - 8)
        self.uc.reg_write(UC_X86_REG_RDI, BASE + 0x6000)
        self.uc.reg_write(UC_X86_REG_RSI, BASE)
        self.uc.reg_write(UC_X86_REG_RDX, BASE + 0x3000)
        self.uc.reg_write(UC_X86_REG_RCX, BASE + 0x4000 if method == 'setHapticConfig' else int(boolean))
        self.uc.emu_start(METHODS[method], 0, timeout=1000000, count=1000)
        if self.result is None:
            raise ValueError('Native prefix did not reach dispatch')
        return self.result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    args = parser.parse_args()
    oracle = NativeOracle(args.binary)
    for method in METHODS:
        print(json.dumps(dict(method=method, **oracle.command(method, first_byte=7, second_byte=1, integer=60, boolean=True))))
