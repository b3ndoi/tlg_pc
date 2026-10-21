#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Offline slow-motion profile guards; no live game/process writes."""
import argparse
import hashlib
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import tlg_native_resolution as n
import tlg_patches
import tlg_slowmotion_60 as s


def pack(writes):
    return struct.pack('<8sQQ', b'G3PATCH2', 0, len(writes)) + b''.join(
        struct.pack('<QQ', at, len(data))+data for at, data in writes)


class SlowMotionTests(unittest.TestCase):
    def test_build_code_constants_and_pause_gates_guarded(self):
        self.assertEqual(hashlib.sha256(ELF).hexdigest(), n.ELF_SHA256)
        self.assertEqual(len(s.checked_writes(ELF)), 2)
        for address in (s.GRID_OFFSET, s.GRID_OFFSET+4, s.RECIPROCAL_OFFSET,
                        s.QUANTIZER_OFFSET, s.SCALE_OFFSET, s.ZERO_GATE_OFFSET):
            damaged = bytearray(ELF)
            damaged[n.mapped_offset(ELF,address,1)] ^= 1
            for verify in (True,False):
                with self.assertRaises(ValueError): s.checked_writes(damaged,verify_hash=verify)

    def test_30_unlocked_unknown_refused_without_any_writes(self):
        for mode in ('30','unlocked','60.0',None):
            with self.assertRaises(ValueError): s.checked_writes(ELF,mode)
        with self.assertRaises(ValueError): s.checked_writes(b'unknown')
        self.assertEqual(tlg_patches.mode_writes(ELF,tlg_patches.MODES['30'],
                         tlg_patches.EU_100_PATCHES,tlg_patches.EU_100_TEXT_SIZE), [])

    def test_only_eight_data_bytes_change_code_bias_and_gates_unchanged(self):
        patched=bytearray(ELF)
        ranges=[]
        for address,data in s.checked_writes(ELF):
            at=n.mapped_offset(ELF,address,len(data)); ranges.append((at,at+len(data)))
            patched[at:at+len(data)]=data
        cursor=0
        for start,end in ranges:
            self.assertEqual(patched[cursor:start],ELF[cursor:start]); cursor=end
        self.assertEqual(patched[cursor:],ELF[cursor:])
        bias=n.mapped_offset(ELF,s.GRID_OFFSET+4,4)
        self.assertEqual(patched[bias:bias+4],ELF[bias:bias+4])

    def test_private_patch_profile_retains_every_prior_write(self):
        base=s.expected_base_writes(ELF)
        with tempfile.TemporaryDirectory() as td:
            elf=Path(td)/'eboot.elf'; elf.write_bytes(ELF)
            patch=Path(td)/'patches.bin'; patch.write_bytes(pack(base))
            note=s.apply_private_patch(elf,patch)
            writes=n.decode_patch_file(patch.read_bytes())
            self.assertEqual(writes,base+s.checked_writes(ELF))
            self.assertEqual(sum(len(data) for _,data in writes),45)
            self.assertIn('30 FPS unchanged',note)
            self.assertEqual(elf.read_bytes(),ELF)
            original=patch.read_bytes()
            with self.assertRaises(ValueError): s.apply_private_patch(elf,patch)
            self.assertEqual(patch.read_bytes(),original)

    def test_wrong_mode_missing_extra_overlap_and_bad_format_fail_atomic(self):
        base=s.expected_base_writes(ELF)
        wrong_fps=[(at,bytes(len(data))) for at,data in base]
        cases=[(base,'30'),(base,'unlocked'),(base[:4],'60'),(base[1:],'60'),
               (base+base[:1],'60'),(wrong_fps,'60'),
               (base+[(s.GRID_OFFSET,b'bad!')],'60')]
        with tempfile.TemporaryDirectory() as td:
            elf=Path(td)/'eboot.elf'; elf.write_bytes(ELF)
            patch=Path(td)/'patches.bin'
            for writes,mode in cases:
                before=pack(writes); patch.write_bytes(before)
                with self.assertRaises(ValueError): s.apply_private_patch(elf,patch,mode)
                self.assertEqual(patch.read_bytes(),before)
            for before in (b'',b'wrong magic'*8,pack(base)[:-1],pack(base)+b'x'):
                patch.write_bytes(before)
                with self.assertRaises(ValueError): s.apply_private_patch(elf,patch)
                self.assertEqual(patch.read_bytes(),before)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--elf',type=Path,required=True)
    args=parser.parse_args(); ELF=args.elf.read_bytes()
    unittest.main(argv=[sys.argv[0]],verbosity=2)
