"""Synthetic UTF-8/rendering/pack fixtures. Never opens game files or a game process."""
import copy
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unicodedata
import unittest
from unittest.mock import patch

PORT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PORT/'scripts'))
sys.path.insert(0, str(PORT/'launcher'))
import compile_translation as ct
import tlg_run
try:
    from PIL import Image, ImageChops
except ImportError:
    Image = None


class TranslationTests(unittest.TestCase):
    def setUp(self):
        self.targets = ct.read_json(PORT/'translations/targets.json')
        self.sr = ct.read_json(PORT/'translations/sr_Latn_RS.json')

    def test_all_serbian_entries_and_target_geometry(self):
        self.assertEqual(len(ct.validate(self.sr, self.targets)), 72)
        self.assertEqual(set(self.sr['entries']), set(self.targets['targets']))
        self.assertEqual(self.sr['locale'], 'sr_Latn_RS')
        for target in self.targets['targets'].values():
            self.assertEqual((target['width'], target['height'], target['source_bytes']), (512,128,65536))
            self.assertRegex(target['xxh128'], r'^[0-9a-f]{32}$')
        for path in (PORT/'translations').glob('*.json'):
            if path.name != 'targets.json':
                ct.validate(ct.read_json(path), self.targets)

    def test_utf8_catalog_roundtrip_nfc_and_latin_diacritics(self):
        corpus = ''.join(self.sr['entries'].values())
        for char in 'čćžšđ':
            # Some tutorial terms do not use every letter; the full launcher must.
            launcher = ct.read_json(PORT/'launcher/locales/sr_Latn_RS.json')
            self.assertIn(char, corpus + ''.join(launcher.values()))
        paths = [*sorted((PORT/'launcher/locales').glob('*.json')),
                 *sorted((PORT/'translations').glob('*.json'))]
        for path in paths:
            raw = path.read_bytes()
            self.assertFalse(raw.startswith(b'\xef\xbb\xbf'), path)
            decoded = raw.decode('utf-8', errors='strict')
            self.assertEqual(unicodedata.normalize('NFC', decoded), decoded, path)
            self.assertEqual(json.loads(json.dumps(ct.read_json(path), ensure_ascii=False)), ct.read_json(path))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'čćžšđ.json'
            path.write_text(json.dumps(self.sr, ensure_ascii=False), encoding='utf-8')
            self.assertEqual(ct.read_json(path), self.sr)
            for bad in (b'\xff', b'\xef\xbb\xbf{}', b'{"a":"x","a":"y"}'):
                path.write_bytes(bad)
                with self.assertRaises((ValueError, UnicodeError)):
                    ct.read_json(path)

    def test_ids_tokens_line_count_and_unsafe_unicode_fail_closed(self):
        for value in ('Drži {missing}', 'Drži {circle!r}', 'Drži {circle:>8}',
                      'Drži', 'Drži {circle}\n', 'Drži {circle}\u202e', 'Drži {circle}\ud800',
                      'Drz\u030ci {circle}'):
            catalog = copy.deepcopy(self.sr)
            catalog['entries']['hold_circle'] = value
            with self.subTest(value=ascii(value)), self.assertRaises(ValueError):
                ct.validate(catalog, self.targets)
        catalog = copy.deepcopy(self.sr)
        catalog['entries']['../escape'] = 'x'
        with self.assertRaises(ValueError):
            ct.validate(catalog, self.targets)
        catalog = copy.deepcopy(self.sr)
        catalog['entries'] = {'aim': ''}  # A new language may start with English fallback.
        self.assertEqual(ct.validate(catalog, self.targets), {'aim': ''})

    @unittest.skipIf(Image is None, 'Pillow optional locally; installed in translation CI')
    def test_every_serbian_text_renders_without_tofu_or_clipping(self):
        ct.render('čćžšđ ČĆŽŠĐ', {'width':512,'height':128}, ct.default_font())
        for key, text in self.sr['entries'].items():
            with self.subTest(key=key):
                image = ct.render(text, self.targets['targets'][key], ct.default_font())
                self.assertEqual(image.size, (512, 128))
                box = image.getchannel('A').getbbox()
                self.assertIsNotNone(box)
                self.assertGreaterEqual(box[0], 0)
                self.assertLess(box[2], 512)
                self.assertLess(box[3], 128)
        with self.assertRaises(ValueError):
            ct.render('W'*1000, {'width':512,'height':128}, ct.default_font())

    @unittest.skipIf(Image is None, 'Pillow optional locally; installed in translation CI')
    def test_bc7_independent_decoder_preserves_black_white_and_alpha(self):
        im = Image.new('RGBA', (8, 8))
        for y in range(8):
            for x in range(8):
                color = 255 if x%2 else 0
                im.putpixel((x,y), (color,color,color,255 if y%2 else 0))
        blocks = ct.encode_bc7(im)
        self.assertEqual(len(blocks), 64)
        # Pillow's independent DDS decoder, not a mirror of our bit writer.
        header = (b'DDS ' + struct.pack('<7I',124,0x81007,8,8,len(blocks),0,1) + bytes(44)
                  + struct.pack('<II4s5I',32,4,b'DX10',0,0,0,0,0) + struct.pack('<5I',0x1000,0,0,0,0)
                  + struct.pack('<5I',98,3,0,1,0))
        decoded = Image.open(io.BytesIO(header+blocks)).convert('RGBA')
        self.assertLessEqual(max(ImageChops.difference(im,decoded).tobytes()), 1)

    @unittest.skipIf(Image is None, 'Pillow optional locally; installed in translation CI')
    def test_pack_wire_format_aliases_and_conflicts(self):
        catalog = copy.deepcopy(self.sr)
        catalog['entries'] = {'aim': '[ Osvetli ]', 'call': '[ Pozovi Trika ]'}
        data, count = ct.compile_pack(catalog, self.targets, ct.default_font())
        self.assertEqual(data[:8], ct.MAGIC)
        self.assertEqual(struct.unpack_from('<I',data,8)[0], count)
        self.assertEqual(count, 2)
        self.assertEqual(len(data), 12+2*(32+65536))
        catalog['entries'] = {'jump': '[ Skoči ]', 'jump_chain': '[ Skoči ]'}
        # Exact-pixel aliases collapse; different source artwork stays distinct.
        data, count = ct.compile_pack(catalog, self.targets, ct.default_font())
        self.assertIn(count, (1,2))
        targets = copy.deepcopy(self.targets)
        targets['targets']['jump_chain'] = targets['targets']['jump']
        self.assertEqual(ct.compile_pack(catalog, targets, ct.default_font())[1], 1)
        catalog['entries']['jump_chain'] = '[ Drugačije ]'
        with self.assertRaises(ValueError):
            ct.compile_pack(catalog, targets, ct.default_font())
        catalog['entries'] = {}
        with self.assertRaises(ValueError):
            ct.compile_pack(catalog, targets, ct.default_font())

    @unittest.skipIf(Image is None, 'Pillow optional locally; installed in translation CI')
    def test_cli_unicode_paths_utf8_pipe_and_exclusive_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = copy.deepcopy(self.sr)
            catalog['entries'] = {'aim':'[ Osvetli ]'}
            source, output = root/'čćžšđ.json', root/'ČĆŽŠĐ.tlgtrn'
            source.write_text(json.dumps(catalog, ensure_ascii=False), encoding='utf-8')
            argv = [sys.executable, str(PORT/'scripts/compile_translation.py'),
                    '--catalog', str(source), '--output', str(output)]
            env = {**os.environ, 'PYTHONIOENCODING':'ascii'}
            first = subprocess.run(argv, capture_output=True, env=env, timeout=20)
            self.assertEqual(first.returncode, 0, first.stderr.decode('utf-8'))
            self.assertIn(str(output), first.stdout.decode('utf-8'))
            before = output.read_bytes()
            second = subprocess.run(argv, capture_output=True, env=env, timeout=20)
            self.assertNotEqual(second.returncode, 0)
            self.assertEqual(before, output.read_bytes())

    def test_opt_in_environment_does_not_change_30fps_or_game_language(self):
        settings = {**tlg_run.DEFAULT_SETTINGS, 'game_language':'en'}
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(tlg_run,'window_icon',return_value=None), \
             patch.object(tlg_run,'ngs2_module',return_value=None), \
             patch.object(tlg_run,'applied_frame_rate','30'):
            baseline = tlg_run.build_env(settings)
            self.assertNotIn('TLG_TRANSLATION_PACK', baseline)
            translated = tlg_run.build_env({**settings,'translation_pack':'čćžšđ.tlgtrn'})
            self.assertEqual(translated.pop('TLG_TRANSLATION_PACK'), 'čćžšđ.tlgtrn')
            self.assertEqual(translated, baseline)
            self.assertEqual(translated['TLG_ENGINE_FPS'], '30')
            self.assertEqual(translated['TLG_LANGUAGE'], '1')
        for invalid in (None, [], {}, 42, 'bad\0path'):
            self.assertEqual(tlg_run.translation_pack({'translation_pack':invalid}), '')


if __name__ == '__main__':
    unittest.main()
