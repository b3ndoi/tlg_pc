#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Exact EU 01.00 regular-mode resolution patch; only private patches.bin is written.

Uses PR #79's engine-mode approach, independently mapped for this ELF. Do not
copy the 1.03 address or alter the Pro/checkerboard entries. No game archives,
installed eboot, pointers, code, aspect ratio or UI canvas constants are edited.
"""
import argparse
import hashlib
from pathlib import Path
import struct

ELF_SHA256 = '580ba4bc7f9b785bfde0948be20ec67a30ca8c9318606ba5cbf28a1a01d54565'
MODE_OFFSET = 0x16BA300
MODE_EXPECTED = bytes.fromhex('80073804800738040000000000000000')
DEFAULT_RESOLUTION = '2560x1440'
RESOLUTIONS = {
    '1280x720': (1280, 720),
    '2560x1440': (2560, 1440),
    '3840x2160': (3840, 2160),
}
RESOLUTION_ALIASES = {
    '720p': '1280x720',
    '2k': '2560x1440',
    '1440p': '2560x1440',
    '4k': '3840x2160',
    '2160p': '3840x2160',
}
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


def normalize_resolution(resolution=DEFAULT_RESOLUTION):
    """Return the canonical WxH spelling for a supported native engine mode."""
    key = str(resolution).strip().lower().replace('×', 'x')
    key = RESOLUTION_ALIASES.get(key, key)
    if key not in RESOLUTIONS:
        choices = ', '.join(RESOLUTIONS)
        raise ValueError(f'Native resolution: unsupported {resolution!r}; choose {choices}')
    return key


def mode_bytes(resolution=DEFAULT_RESOLUTION):
    width, height = RESOLUTIONS[normalize_resolution(resolution)]
    return struct.pack('<4HQ', width, height, width, height, 0)


# Compatibility for private callers that imported the original 1440p constant.
MODE_NEW = mode_bytes()


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


def checked_writes(elf, verify_hash=True, resolution=DEFAULT_RESOLUTION):
    resolution = normalize_resolution(resolution)
    if verify_hash and hashlib.sha256(elf).hexdigest() != ELF_SHA256:
        raise ValueError('Native resolution: unsupported ELF; exact EU 01.00 hash required')
    for address, expected in ((MODE_OFFSET, TABLE_EXPECTED), (SELECTOR_OFFSET, SELECTOR_EXPECTED)):
        offset = mapped_offset(elf, address, len(expected))
        if elf[offset:offset+len(expected)] != expected:
            raise ValueError(f'Native resolution: expected bytes mismatch at guest +{address:#x}')
    return [(MODE_OFFSET, mode_bytes(resolution))]


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


def apply_private_patch(elf_path, patch_path, resolution=DEFAULT_RESOLUTION):
    import tlg_patches
    resolution = normalize_resolution(resolution)
    elf = Path(elf_path).read_bytes()
    resolution_writes = checked_writes(elf, resolution=resolution)
    path = Path(patch_path)
    writes = decode_patch_file(path.read_bytes())
    expected_fps = [(offset, data) for offset, data, _ in tlg_patches.mode_writes(
        elf, [*tlg_patches.MODES['60'], *tlg_patches.EU_100_60_EXTRA],
        tlg_patches.EU_100_PATCHES, tlg_patches.EU_100_TEXT_SIZE)]
    if writes != expected_fps:
        raise ValueError('Native resolution: expected exactly the five verified EU 60 FPS writes')
    for address, data in resolution_writes:
        if any(address < old+len(previous) and old < address+len(data) for old, previous in writes):
            raise ValueError('Native resolution: overlapping patches')
    writes += resolution_writes
    blob = struct.pack('<8sQQ', b'G3PATCH2', 0, len(writes))
    for address, data in writes:
        blob += struct.pack('<QQ', address, len(data)) + data
    path.write_bytes(blob)
    width, height = RESOLUTIONS[resolution]
    return (f'Engine native resolution: CUSA03745 EU 01.00 verified; regular mode guest '
            f'+{MODE_OFFSET:#x}: render/output {width}x{height}; checkerboard off; '
            'Pro table, pointers and 16:9 UI/aspect unchanged (6 total writes, 37 bytes)')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--elf', type=Path, required=True, help='owner-provided exact EU 01.00 ELF')
    parser.add_argument('--patch', type=Path, required=True, help='existing verified 60 FPS patches.bin')
    parser.add_argument('--resolution', default=DEFAULT_RESOLUTION,
                        help='720p, 1440p/2k, 2160p/4k, or the corresponding WxH value')
    args = parser.parse_args()
    print(apply_private_patch(args.elf, args.patch, args.resolution))


if __name__ == '__main__':
    main()
