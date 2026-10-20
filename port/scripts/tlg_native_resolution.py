#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Exact EU 01.00 regular-mode 1440p patch; only private patches.bin is written.

Uses PR #79's engine-mode approach, independently mapped for this ELF. Do not
copy the 1.03 address or alter the Pro/checkerboard entries. No game archives,
installed eboot, pointers, code, aspect ratio or UI canvas constants are edited.
"""
import hashlib
from pathlib import Path
import struct

ELF_SHA256 = '580ba4bc7f9b785bfde0948be20ec67a30ca8c9318606ba5cbf28a1a01d54565'
MODE_OFFSET = 0x16BA300
MODE_EXPECTED = bytes.fromhex('80073804800738040000000000000000')
MODE_NEW = struct.pack('<4HQ', 2560, 1440, 2560, 1440, 0)
# Default regular mode plus its name pointer, two lower regular modes and the
# first Pro checkerboard record. The patch changes only the first 16 bytes.
TABLE_EXPECTED = bytes.fromhex(
    '800738048007380400000000000000009f6c5b0100000000'
    'e006de03800738040000000000000000a96c5b0100000000'
    '40068403800738040000000000000000b26c5b0100000000'
    '90066207200d62070100000000000000bb6c5b0100000000')
# The regular-mode selector really loads these 16 bytes, not the Pro entry.
SELECTOR_OFFSET = 0xB8A685
SELECTOR_EXPECTED = bytes.fromhex('488b0584fcb200c5f828056cfcb200')


def mapped_offset(elf, address, length):
    if elf[:4] != b'\x7fELF' or len(elf) < 0x40:
        raise ValueError('Native resolution: not a complete ELF64 image')
    phoff = struct.unpack_from('<Q', elf, 0x20)[0]
    stride, count = struct.unpack_from('<HH', elf, 0x36)
    if stride < 56 or phoff + stride * count > len(elf):
        raise ValueError('Native resolution: invalid program headers')
    for index in range(count):
        kind, _, offset, base, _, size, _, _ = struct.unpack_from('<IIQQQQQQ', elf, phoff+index*stride)
        if kind in (1, 0x61000010) and base <= address and address+length <= base+size:
            result = offset+address-base
            if result+length <= len(elf):
                return result
    raise ValueError(f'Native resolution: unmapped image address {address:#x}')


def checked_writes(elf, verify_hash=True):
    if verify_hash and hashlib.sha256(elf).hexdigest() != ELF_SHA256:
        raise ValueError('Native resolution: unsupported ELF; exact EU 01.00 hash required')
    for address, expected in ((MODE_OFFSET, TABLE_EXPECTED), (SELECTOR_OFFSET, SELECTOR_EXPECTED)):
        offset = mapped_offset(elf, address, len(expected))
        if elf[offset:offset+len(expected)] != expected:
            raise ValueError(f'Native resolution: expected bytes mismatch at guest +{address:#x}')
    return [(MODE_OFFSET, MODE_NEW)]


def decode_patch_file(blob):
    if len(blob) < 24:
        raise ValueError('Native resolution: truncated patch header')
    magic, base, count = struct.unpack_from('<8sQQ', blob)
    if magic != b'G3PATCH2' or base != 0 or count > 64:
        raise ValueError('Native resolution: unsupported patch header')
    cursor = 24
    writes = []
    for _ in range(count):
        if cursor+16 > len(blob):
            raise ValueError('Native resolution: truncated patch entry')
        address, size = struct.unpack_from('<QQ', blob, cursor)
        cursor += 16
        if not size or cursor+size > len(blob):
            raise ValueError('Native resolution: truncated/empty patch data')
        writes.append((address, blob[cursor:cursor+size]))
        cursor += size
    if cursor != len(blob):
        raise ValueError('Native resolution: trailing patch data')
    return writes


def apply_private_patch(elf_path, patch_path):
    import tlg_patches
    elf = Path(elf_path).read_bytes()
    resolution = checked_writes(elf)
    path = Path(patch_path)
    writes = decode_patch_file(path.read_bytes())
    expected_fps = [(offset, data) for offset, data, _ in tlg_patches.mode_writes(
        elf, [*tlg_patches.MODES['60'], *tlg_patches.EU_100_60_EXTRA],
        tlg_patches.EU_100_PATCHES, tlg_patches.EU_100_TEXT_SIZE)]
    if writes != expected_fps:
        raise ValueError('Native resolution: expected exactly the five verified EU 60 FPS writes')
    for address, data in resolution:
        if any(address < old+len(previous) and old < address+len(data) for old, previous in writes):
            raise ValueError('Native resolution: overlapping patches')
    writes += resolution
    blob = struct.pack('<8sQQ', b'G3PATCH2', 0, len(writes))
    for address, data in writes:
        blob += struct.pack('<QQ', address, len(data)) + data
    path.write_bytes(blob)
    return (f'Engine native resolution: CUSA03745 EU 01.00 verified; regular mode guest '
            f'+{MODE_OFFSET:#x}: render/output 2560x1440; checkerboard off; '
            'Pro table, pointers and 16:9 UI/aspect unchanged (6 total writes, 37 bytes)')
