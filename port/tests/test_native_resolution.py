#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Offline exact EU native-mode regression. No game process or installed writes."""
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


class NativeResolutionTests(unittest.TestCase):
    def test_real_elf_and_selector_are_independently_guarded(self):
        self.assertEqual(hashlib.sha256(ELF).hexdigest(), n.ELF_SHA256)
        self.assertEqual(n.checked_writes(ELF),
                         [(n.MODE_OFFSET, n.MODE_NEW), (n.GARLIC_OFFSET, n.garlic_bytes())])
        for address in (n.MODE_OFFSET, n.MODE_OFFSET+16, n.MODE_OFFSET+72,
                        n.SELECTOR_OFFSET, n.GARLIC_OFFSET):
            corrupted = bytearray(ELF)
            offset = n.mapped_offset(ELF, address, 1)
            corrupted[offset] ^= 1
            with self.assertRaises(ValueError): n.checked_writes(corrupted)
            with self.assertRaises(ValueError): n.checked_writes(corrupted, verify_hash=False)

    def test_regular_mode_not_pro_and_all_buffers_use_same_dimensions(self):
        original = ELF
        for resolution, dimensions in n.RESOLUTIONS.items():
            with self.subTest(resolution=resolution):
                patched = bytearray(ELF)
                for address, value in n.checked_writes(ELF, resolution=resolution):
                    at = n.mapped_offset(ELF, address, len(value))
                    patched[at:at+len(value)] = value
                at = n.mapped_offset(ELF, n.MODE_OFFSET, len(n.TABLE_EXPECTED))
                width, height = dimensions
                self.assertEqual(struct.unpack_from('<4HQ', patched, at),
                                 (width,height,width,height,0))
                self.assertEqual(patched[at+16:at+len(n.TABLE_EXPECTED)],
                                 original[at+16:at+len(n.TABLE_EXPECTED)])
                self.assertEqual(struct.unpack_from('<4HQ', patched, at+72),
                                 (1680,1890,3360,1890,1))
                garlic = n.mapped_offset(ELF, n.GARLIC_OFFSET, len(n.GARLIC_EXPECTED))
                expected = bytearray(original)
                expected[at:at+16] = n.mode_bytes(resolution)
                if n.needs_garlic_growth(resolution):
                    expected[garlic:garlic+len(n.GARLIC_EXPECTED)] = n.garlic_bytes()
                    self.assertEqual(patched[garlic:garlic+6], bytes.fromhex('41bf000000fe'))
                else:
                    self.assertEqual(patched[garlic:garlic+6], n.GARLIC_EXPECTED)
                self.assertEqual(patched, expected)

    def test_resolution_aliases_and_invalid_values(self):
        self.assertEqual(n.normalize_resolution('720p'), '1280x720')
        self.assertEqual(n.normalize_resolution('2K'), '2560x1440')
        self.assertEqual(n.normalize_resolution('4K'), '3840x2160')
        for value in ('', '1920x1080', '8k', None):
            with self.assertRaises(ValueError): n.normalize_resolution(value)

    def test_fps_is_retained_and_private_patch_file_only(self):
        before_elf = hashlib.sha256(ELF).hexdigest()
        old = [(offset,data) for offset,data,_ in tlg_patches.mode_writes(
            ELF,[*tlg_patches.MODES['60'],*tlg_patches.EU_100_60_EXTRA],
            tlg_patches.EU_100_PATCHES,tlg_patches.EU_100_TEXT_SIZE)]
        for resolution in n.RESOLUTIONS:
            with self.subTest(resolution=resolution), tempfile.TemporaryDirectory(dir='.') as directory:
                root = Path(directory)
                elf = root/'eboot.elf'
                elf.write_bytes(ELF)
                patches = root/'patches.bin'
                tlg_patches.write_patch_file(patches, [(offset,data,'test') for offset,data in old])
                note = n.apply_private_patch(elf,patches,resolution)
                writes = n.decode_patch_file(patches.read_bytes())
                self.assertEqual(writes[:5],old)
                self.assertEqual(writes[5:], n.checked_writes(ELF, resolution=resolution))
                expected_bytes = 43 if n.needs_garlic_growth(resolution) else 37
                self.assertEqual(sum(len(data) for _,data in writes), expected_bytes)
                self.assertIn(f'render/output {resolution}',note)
                self.assertIn('checkerboard off',note)
                self.assertEqual('GPU heap 2816->4064 MiB' in note,
                                 n.needs_garlic_growth(resolution))
                self.assertEqual(hashlib.sha256(elf.read_bytes()).hexdigest(),before_elf)
                with self.assertRaises(ValueError): n.apply_private_patch(elf,patches,resolution)

    def test_unknown_build_and_bad_mapping_fail_closed(self):
        with self.assertRaises(ValueError): n.checked_writes(b'unknown')
        with self.assertRaises(ValueError): n.mapped_offset(b'',n.MODE_OFFSET,16)
        with self.assertRaises(ValueError): n.mapped_offset(ELF,0xffffffffffff,16)

    def test_patch_decoder_rejects_truncation_trailing_and_foreign_formats(self):
        for blob in (b'',b'notapatch'*8,struct.pack('<8sQQ',b'G3PATCH2',1,0),
                     struct.pack('<8sQQ',b'G3PATCH2',0,100),
                     struct.pack('<8sQQ',b'G3PATCH2',0,1),
                     struct.pack('<8sQQ',b'G3PATCH2',0,0)+b'x'):
            with self.assertRaises(ValueError): n.decode_patch_file(blob)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--elf',type=Path,required=True)
    args=parser.parse_args()
    ELF=args.elf.read_bytes()
    unittest.main(argv=[sys.argv[0]],verbosity=2)
