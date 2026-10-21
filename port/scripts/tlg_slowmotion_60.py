#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Exact EU 01.00 60-FPS clock precision; only a private patch file is written.

The native smoother floors positive scaled steps onto a biased 1/360-s grid.
At 0.15x/60 Hz, feedback/jitter can lower the step below its 2.5-ms threshold
and lock gameplay time at zero. A 100000x finer grid preserves the native filter,
feedback, zero-speed/overlay gates and instructions, without per-scene cheats.
The native input epsilon (1e-5 s) remains unchanged; a step at that epsilon has
360 new grid ticks, so it cannot collapse in this quantizer when settled.
30/unlocked/unknown builds and nonexact preceding patch lists fail closed.
"""
import hashlib
from pathlib import Path
import struct

import tlg_native_resolution as native
import tlg_patches

GRID_OFFSET = 0x14D9938
RECIPROCAL_OFFSET = 0x14D9940
GRID_HZ = 36000000.0
EXPECTED_CONSTANTS = bytes.fromhex('0000b443cdcccc3d610b363b')
QUANTIZER_OFFSET = 0xC51AE8
QUANTIZER_EXPECTED = bytes.fromhex(
    'c5fa5905487e8800c5fa5805447e8800c4e3790ac001c5fa59053a7e8800'
    'c5fa11809c030000c5fa11879c010000')
SCALE_OFFSET = 0xC519FF
SCALE_EXPECTED = bytes.fromhex('c5f25987b8010000c5fa11879c010000')
ZERO_GATE_OFFSET = 0xC51A2E
ZERO_GATE_EXPECTED = bytes.fromhex(
    'c5fa1015e67e8800c5fa10819c010000c5f82ed07622')


def checked_writes(elf, mode='60', verify_hash=True):
    if mode != '60':
        raise ValueError('Slow-motion clock: only the explicit 60 FPS profile is supported')
    if verify_hash and hashlib.sha256(elf).hexdigest() != native.ELF_SHA256:
        raise ValueError('Slow-motion clock: exact EU 01.00 ELF hash required')
    for address, expected in ((GRID_OFFSET, EXPECTED_CONSTANTS),
                              (QUANTIZER_OFFSET, QUANTIZER_EXPECTED),
                              (SCALE_OFFSET, SCALE_EXPECTED),
                              (ZERO_GATE_OFFSET, ZERO_GATE_EXPECTED)):
        at = native.mapped_offset(elf, address, len(expected))
        if elf[at:at+len(expected)] != expected:
            raise ValueError(f'Slow-motion clock: expected bytes mismatch at guest +{address:#x}')
    return [(GRID_OFFSET, struct.pack('<f', GRID_HZ)),
            (RECIPROCAL_OFFSET, struct.pack('<f', 1.0 / GRID_HZ))]


def expected_base_writes(elf):
    fps = [(offset, data) for offset, data, _ in tlg_patches.mode_writes(
        elf, [*tlg_patches.MODES['60'], *tlg_patches.EU_100_60_EXTRA], tlg_patches.EU_100_PATCHES,
        tlg_patches.EU_100_TEXT_SIZE)]
    return fps + native.checked_writes(elf)


def apply_private_patch(elf_path, patch_path, mode='60'):
    elf = Path(elf_path).read_bytes()
    clock = checked_writes(elf, mode)
    path = Path(patch_path)
    writes = native.decode_patch_file(path.read_bytes())
    if writes != expected_base_writes(elf):
        raise ValueError('Slow-motion clock: expected exactly five EU 60 FPS writes plus native 1440p')
    for address, data in clock:
        if any(address < old+len(previous) and old < address+len(data)
               for old, previous in writes):
            raise ValueError('Slow-motion clock: overlapping patches')
    writes += clock
    blob = struct.pack('<8sQQ', b'G3PATCH2', 0, len(writes))
    for address, data in writes:
        blob += struct.pack('<QQ', address, len(data)) + data
    path.write_bytes(blob)
    return ('60 FPS slow-motion clock: exact EU 01.00 verified; native quantizer '
            '360 -> 36000000 Hz; zero-speed/overlay gates and 30 FPS unchanged '
            '(8 total writes, 45 bytes; private patch file only)')
