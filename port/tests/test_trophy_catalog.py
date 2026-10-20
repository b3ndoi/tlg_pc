"""Synthetic catalog/PNG fixtures only; never extracts or ships game assets."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'launcher'))
import trophy_catalog as c

XML = b'<trophyconf><trophy id="0" ttype="P" hidden="no"><name>Fixture master</name><detail>Fixture only</detail></trophy><trophy id="1" ttype="B" hidden="yes"><name>SECRET NAME</name><detail>SECRET DETAIL</detail></trophy></trophyconf>'
# Generate a valid transparent 1x1 PNG (synthetic, no game artwork).
import zlib


def png_chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))


ICON = (c.PNG + png_chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 6, 0, 0, 0))
        + png_chunk(b'IDAT', zlib.compress(b'\0\0\0\0\0')) + png_chunk(b'IEND', b''))


def trp(entries):
    table, payload = bytearray(), bytearray()
    start = 96 + len(entries) * 64
    for name, data, flags in entries:
        table += struct.pack('>32sQQI12x', name.encode(), start + len(payload), len(data), flags)
        payload += data
    header = struct.pack('>IIQII', 0xDCA24D00, 3, start + len(payload), len(entries), 64)
    return header.ljust(96, b'\0') + table + payload


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.game, self.metadata = self.root / 'game', self.root / 'metadata'
        self.folder = self.game / 'sce_sys/trophy'
        self.folder.mkdir(parents=True)
        self.metadata.mkdir()
        self.archive = self.folder / 'trophy00.trp'
        self.archive.write_bytes(trp([('TROP000.PNG', ICON, 0), ('TROP001.PNG', ICON, 0),
                                      ('TROP.ESFM', b'encrypted fixture, not XML', 3)]))

    def tearDown(self):
        self.temp.cleanup()

    def test_unknown_metadata_masks_every_icon_and_name_even_if_unlocked(self):
        catalog = c.Catalog(self.game)
        self.assertEqual(set(catalog.trophies), {0, 1})
        self.assertFalse(catalog.complete)
        with patch.object(catalog, 'icon', side_effect=AssertionError('No spoiler icon decode')):
            for unlocked in (False, True):
                self.assertEqual(catalog.view(1, unlocked)['icon'], None)
                self.assertTrue(catalog.view(1, unlocked)['masked'])
                self.assertEqual(catalog.view(1, unlocked)['name'], '')

    def test_complete_catalog_and_hidden_trophy_are_revealed_only_after_unlock(self):
        (self.metadata / 'TROP.XML').write_bytes(XML)
        catalog = c.Catalog(self.game, self.metadata)
        self.assertTrue(catalog.complete)
        self.assertEqual(catalog.view(0)['name'], 'Fixture master')
        self.assertEqual(catalog.view(0)['icon'], ICON)
        with patch.object(catalog, 'icon', side_effect=AssertionError('Hidden icon must not be read')):
            hidden = catalog.view(1)
            self.assertEqual((hidden['name'], hidden['detail'], hidden['grade'], hidden['icon']), ('', '', '', None))
        self.assertEqual(catalog.view(1, True)['name'], 'SECRET NAME')
        self.assertEqual(catalog.view(1, True)['icon'], ICON)

    def test_bad_xml_never_loads(self):
        for data in (XML.replace(b'id="1"', b'id="0"'), XML.replace(b'hidden="yes"', b'hidden="maybe"'),
                     XML.replace(b'id="1"', b'id="128"'), XML.replace(b'ttype="B"', b'ttype="X"'),
                     b'<!DOCTYPE x [<!ENTITY p "hi">]><trophyconf/>', b'bad', b'x' * (c.MAX_XML + 1)):
            with self.subTest(data=data[:50]), self.assertRaises(c.CatalogError):
                c.parse_xml(data)

    def test_case_insensitive_xml_and_english_fallback(self):
        (self.metadata / 'trop.xml').write_bytes(XML)
        self.assertEqual(c.Catalog(self.game, self.metadata).xml_path.name, 'trop.xml')

    def test_bad_archive_bounds_names_duplicates_overlap(self):
        valid = bytearray(self.archive.read_bytes())
        variants = [b'', b'x' * 96, valid + b'0', trp([('../bad', ICON, 0)]),
                    trp([('TROP000.PNG', ICON, 0), ('TROP000.PNG', ICON, 0)])]
        bad = bytearray(valid)
        struct.pack_into('>Q', bad, 96 + 32, 1)
        variants.append(bad)
        for data in variants:
            self.archive.write_bytes(data)
            with self.subTest(size=len(data)), self.assertRaises(c.CatalogError):
                c.Archive(self.archive)

    def test_png_limits(self):
        self.assertEqual(c.png_checked(ICON), ICON)
        bad = bytearray(ICON)
        struct.pack_into('>I', bad, 16, 100000)
        for data in (b'no', bad, b'x' * (c.MAX_ICON + 1)):
            with self.assertRaises(c.CatalogError):
                c.png_checked(data)


if __name__ == '__main__':
    unittest.main()
