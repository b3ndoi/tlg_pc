from paths import ROOT
import struct
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import tlg_patches as t


def text_with(names, expected=True, patches=t.PATCHES):
    """A text segment with each patch's expected bytes (or other bytes) at its offset."""
    text = bytearray(t.TEXT_SIZE)
    for name in names:
        for address, original, _, _ in patches[name]:
            offset = address - t.GHIDRA_BASE
            text[offset:offset + len(original)] = original if expected else b'\xcc' * len(original)
    return text


def plain_elf(text):
    data = bytearray(t.TEXT_FILE_OFFSET) + text
    struct.pack_into('<16sHHIQQQIHHHHHH', data, 0,
                     b'\x7fELF\x02\x01\x01\x09', 0xfe10, 62, 1, 0, 64, 0, 0, 64, 56, 1, 0, 0, 0)
    struct.pack_into('<IIQQQQQQ', data, 64, 1, 5, t.TEXT_FILE_OFFSET, 0, 0, len(text), len(text), 0x4000)
    return data


def self_dump(text):
    """The same ELF in a SELF: one plaintext segment, stored at another file offset."""
    data = bytearray(0x200) + text
    data[:4] = t.SELF_MAGIC
    struct.pack_into('<H', data, 24, 1)
    struct.pack_into('<QQQQ', data, 32, 0x800, 0x200, len(text), len(text))
    struct.pack_into('<16sHHIQQQIHHHHHH', data, 64,
                     b'\x7fELF\x02\x01\x01\x09', 0xfe10, 62, 1, 0, 64, 0, 0, 64, 56, 1, 0, 0, 0)
    struct.pack_into('<IIQQQQQQ', data, 128, 1, 5, t.TEXT_FILE_OFFSET, 0, 0, len(text), len(text), 0x4000)
    return data


class FrameRatePatchTests(unittest.TestCase):
    def prepare(self, eboot, mode):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'eboot.bin').write_bytes(eboot)
            applied, lines = t.prepare(tmp, tmp, mode)
            return applied, lines, Path(tmp, 'patches.bin').read_bytes()

    def test_self_dump_of_103_gets_the_patches(self):
        # #40: a SELF dump of 1.03 has another sha256 than the plain dump, but the same code.
        applied, lines, blob = self.prepare(self_dump(text_with(t.MODES['60'])), '60')
        self.assertEqual(applied, '60')
        self.assertIn('Frame rate: 60 FPS mode, 4 patch writes', lines)
        self.assertEqual(struct.unpack_from('<8sQQ', blob), (b'G3PATCH2', 0, 4))

    def test_self_dump_of_another_build_stays_at_30(self):
        applied, lines, blob = self.prepare(self_dump(text_with(t.MODES['unlocked'], expected=False)), 'unlocked')
        self.assertEqual(applied, '30')
        self.assertEqual(struct.unpack_from('<8sQQ', blob), (b'G3PATCH2', 0, 0))

    def test_unreadable_self_stays_at_30(self):
        applied, lines, _ = self.prepare(t.SELF_MAGIC + bytes(60), '60')
        self.assertEqual(applied, '30')
        self.assertTrue(any(line.startswith('Frame rate: cannot read the SELF') for line in lines))

    def test_plain_elf_with_another_hash_stays_at_30(self):
        # Unchanged: a plain ELF is only patched when it is the checked 1.03 dump.
        applied, lines, _ = self.prepare(plain_elf(text_with(t.MODES['60'])), '60')
        self.assertEqual(applied, '30')
        self.assertTrue(any('unsupported eboot.bin' in line for line in lines))

    def test_verified_eu_self_uses_eu_offsets(self):
        eboot = self_dump(text_with(t.MODES['60'], patches=t.EU_100_PATCHES))
        with patch.object(t, 'EBOOT_EU_100_SHA256', hashlib.sha256(eboot).hexdigest()):
            applied, lines, blob = self.prepare(eboot, '60')
        self.assertEqual(applied, '60')
        self.assertTrue(any('CUSA03745 EU 01.00' in line for line in lines))
        self.assertEqual(struct.unpack_from('<8sQQ', blob), (b'G3PATCH2', 0, 4))
        pos, writes = 24, []
        while pos < len(blob):
            offset, size = struct.unpack_from('<QQ', blob, pos)
            pos += 16
            writes.append((offset, blob[pos:pos + size]))
            pos += size
        self.assertEqual(writes, [(0xb8be7c, bytes.fromhex('be00000000')),
                                  (0x14d9920, t.f32(0.0175)),
                                  (0x14d9924, t.f32(1 / 60)),
                                  (0x14d9928, t.f32(0.0158333331))])

    def test_eu_plain_elf_unlocked(self):
        eboot = plain_elf(text_with(t.MODES['unlocked'], patches=t.EU_100_PATCHES))
        with patch.object(t, 'EBOOT_EU_100_ELF_SHA256', hashlib.sha256(eboot).hexdigest()):
            applied, _, blob = self.prepare(eboot, 'unlocked')
        self.assertEqual(applied, 'unlocked')
        self.assertEqual(struct.unpack_from('<8sQQ', blob), (b'G3PATCH2', 0, 1))

    def test_unrecognized_eu_layout_stays_at_30(self):
        eboot = self_dump(text_with(t.MODES['60'], patches=t.EU_100_PATCHES))
        applied, _, blob = self.prepare(eboot, '60')
        self.assertEqual(applied, '30')
        self.assertEqual(struct.unpack_from('<8sQQ', blob), (b'G3PATCH2', 0, 0))

    def test_eu_mismatched_constant_discards_all_writes(self):
        text = text_with(t.MODES['60'], patches=t.EU_100_PATCHES)
        text[0x14d9928] ^= 1
        eboot = self_dump(text)
        with patch.object(t, 'EBOOT_EU_100_SHA256', hashlib.sha256(eboot).hexdigest()):
            applied, lines, blob = self.prepare(eboot, '60')
        self.assertEqual(applied, '30')
        self.assertTrue(any('dt_snap_60' in line and 'expected' in line for line in lines))
        self.assertEqual(struct.unpack_from('<8sQQ', blob), (b'G3PATCH2', 0, 0))

    def test_unmapped_experimental_patch_rejected_for_eu(self):
        eboot = self_dump(text_with(t.MODES['60'], patches=t.EU_100_PATCHES))
        with patch.object(t, 'EBOOT_EU_100_SHA256', hashlib.sha256(eboot).hexdigest()), \
                patch.dict('os.environ', {'TLG_FPS_PATCHES': 'max_fps_off'}):
            applied, lines, blob = self.prepare(eboot, '60')
        self.assertEqual(applied, '30')
        self.assertTrue(any('unavailable for this executable build' in line for line in lines))
        self.assertEqual(struct.unpack_from('<8sQQ', blob), (b'G3PATCH2', 0, 0))

    def test_30_writes_an_empty_patch_file(self):
        applied, lines, blob = self.prepare(b'', '30')
        self.assertEqual((applied, struct.unpack_from('<8sQQ', blob)), ('30', (b'G3PATCH2', 0, 0)))


if __name__ == '__main__':
    unittest.main()
